"""Old versions of the same act, and conflicting numbers between documents (day-4 GPU run, 8-noyabr).

The Hugging Face copy of Lex.uz marks every document «in-force», but it holds several generations of the
same act: the 1995 and the 2022 Labour Code, the 1997, 2007 and 2019 Tax Codes… They have the same title, so
for the QQS (VAT) question the LLM got 12 %, 15 %, 20 % and 30 % from four of them — each one «supported» by
its own source, and all four shown as one answer.

1. `superseded(con)` — for codes, the Constitution and laws: documents with the same title (prefix
   «Oʻzbekiston Respublikasining», case and quotes ignored) are one act; the one with the largest Lex.uz id
   (ids grow with time: -142859 → 1995, -6257288 → 2022) is current, the others are dropped from retrieval.
   Amending and approving acts («…ga oʻzgartish kiritish…», «…ni tasdiqlash…») are separate acts and are
   never grouped.
2. `drop_outdated(con, ctx)` — before generation: a by-law that cites an article of a code re-enacted after it (the
   1995 Labour Code's «134-modda, 15 ish kuni»), and a lower act whose sentence is the same sentence as a higher act's
   with a different amount («Prezident besh yil…» in the 1991 election law vs «yetti yil» in the Saylov kodeksi).
3. `resolve_numbers(...)` — when a question asks for a quantity («necha», «qancha», «foiz»…) and verified
   sentences from different documents state different numbers, only the most authoritative document's numeric
   sentences stay (Constitution → code → law → decree → resolution → order; then the newer document).
"""

from __future__ import annotations

import re
from functools import lru_cache

from .textnorm import normalize_uz, number_words, stem

TYPES = ("constitution", "code", "law")
SEPARATE = re.compile(r"oʻzgartish|qoʻshimcha|kiritish|tasdiqlash|oʻz kuchini yoʻqotgan|deb hisoblash|bekor qilish")
PREFIX = re.compile(r"^(oʻzbekiston respublikasining|oʻzbekiston respublikasi)\s+")
QUANTITY = re.compile(r"\b(necha|nechta|nechanchi|qancha|qanchalik|miqdor\w*|foiz\w*|stavka\w*|muddat\w*)\b")
DOC_RANK = {"constitution": 0, "code": 1, "law": 2, "decree": 3, "resolution": 4, "order": 5}
NUM_RE = re.compile(r"\d+")

_cache: dict[str, dict[str, str]] = {}


def title_key(title: str | None) -> str:
    t = normalize_uz(title or "").lower()
    t = re.sub(r"[«»“”„\"']", "", t)
    t = PREFIX.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


def doc_num(doc_id) -> int:
    d = re.sub(r"\D", "", str(doc_id or ""))
    return int(d) if d else 0


def find_superseded(rows, articles: dict[str, set] | None = None, overlap: float = 0.5) -> dict[str, str]:
    """rows: (doc_id, doc_title, doc_type); articles: {doc_id: its article numbers}.
    Returns {old doc_id: current doc_id}.

    Same title is not enough: the Civil Code is ONE act in TWO documents with the same title (part 1:
    articles 1–386, part 2: 387–1199 — the 8-noyabr GPU run would have dropped part 1). With `articles`, an
    older document is a previous version only if at least `overlap` of the smaller document's article numbers
    also occur in the newer one (a new version renumbers from 1; a second part continues the numbering)."""
    groups: dict[str, list[str]] = {}
    for doc_id, title, kind in rows:
        key = title_key(title)
        if kind not in TYPES or not key or SEPARATE.search(key):
            continue
        groups.setdefault(f"{kind}|{key}", []).append(str(doc_id))

    def same_act(a: str, b: str) -> bool:
        if articles is None:
            return True
        x, y = articles.get(a) or set(), articles.get(b) or set()
        if not x or not y:
            return False
        return len(x & y) / min(len(x), len(y)) >= overlap

    out = {}
    for ids in groups.values():
        ids = sorted(set(ids), key=doc_num)
        for i, old in enumerate(ids[:-1]):
            newer = next((n for n in reversed(ids[i + 1:]) if same_act(old, n)), None)
            if newer:
                out[old] = newer
    return out


def superseded(con) -> dict[str, str]:
    """{old doc_id: current doc_id} for this database — computed once per database (its label/path)."""
    key = str(getattr(con, "label", None) or id(con))
    if key not in _cache:
        marks = ", ".join("?" for _ in TYPES)
        rows = con.execute(f"SELECT DISTINCT doc_id, doc_title, doc_type FROM articles WHERE doc_type IN ({marks})",
                           TYPES).fetchall()
        arts: dict[str, set] = {}
        for r in con.execute(f"SELECT doc_id, article_number FROM articles WHERE doc_type IN ({marks})", TYPES).fetchall():
            if r["article_number"]:
                arts.setdefault(str(r["doc_id"]), set()).add(str(r["article_number"]))
        _cache[key] = find_superseded(((r["doc_id"], r["doc_title"], r["doc_type"]) for r in rows), arts)
    return _cache[key]


# Amending and repealing acts («…ga oʻzgartish va qoʻshimchalar kiritish toʻgʻrisida», «…ni oʻz kuchini yoʻqotgan deb
# hisoblash toʻgʻrisida»). Their text is either already consolidated into the act they amend, or belongs to an act that
# was replaced — 8-noyabr, 100-question test: amendments to the repealed 1995 «Mehnat qonunlari kodeksi» are typed
# «code» in the data, got the code's authority boost and answered «how many days of annual leave» with the old
# maternity-leave text. So they are left out of retrieval, unless the question itself is about amendments.
AMENDING = re.compile(r"(oʻzgartish|oʻzgartirish|qoʻshimcha)\w*\s+(va\s+\S+\s+)?kiritish|oʻz kuchini yoʻqotgan deb (hisoblash|topish)")
ASKS_AMENDMENT = re.compile(r"oʻzgartish|oʻzgartirish|qoʻshimcha\w* kirit|tahrir|qachon oʻzgar|oʻz kuchini yoʻqot|bekor qilingan")
_amend_cache: dict[str, dict[str, str]] = {}


def amending(con) -> dict[str, str]:
    """{doc_id: ""} — amending / repealing acts of this database (computed once per database)."""
    key = str(getattr(con, "label", None) or id(con))
    if key not in _amend_cache:
        rows = con.execute("SELECT DISTINCT doc_id, doc_title FROM articles").fetchall()
        _amend_cache[key] = {str(r["doc_id"]): "" for r in rows if AMENDING.search(title_key(r["doc_title"]))}
    return _amend_cache[key]


def excluded(con, question: str) -> dict[str, str]:
    """Documents left out of retrieval for this question: older versions of an act ({old: current}) and amending acts
    ({doc: ""}) — the latter only when the question is not about amendments."""
    out = dict(superseded(con))
    if not ASKS_AMENDMENT.search(normalize_uz(question or "").lower()):
        for d in amending(con):
            out.setdefault(d, "")
    return out


# ---- outdated chunks (100-question test, 8-noyabr 22:00): the old-version filter works on titles, so two kinds of
# outdated text still reached the model and were cited — q005 «15 ish kuni» from a 2018 resolution quoting the 1995
# Labour Code's article 134, and q043 «Prezident besh yil muddatga saylanadi» from the 1991 presidential election law
# (replaced by the 2019 Saylov kodeksi; the Constitution and the code say «yetti yil»).

UNIT = {"kun": "kun", "yil": "yil", "oy": "oy", "hafta": "hafta", "soat": "soat", "foiz": "foiz", "baravar": "baravar",
        "yosh": "yosh", "daqiqa": "daqiqa"}
_NUMW = re.compile(r"^(bir|ikki|uch|toʻrt|besh|olti|yetti|sakkiz|toʻqqiz|oʻn|yigirma|oʻttiz|qirq|ellik|oltmish|yetmish"
                   r"|sakson|toʻqson|yuz|ming)")
_TOK = re.compile(r"\d+|[a-zʻ]+")
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_STOP = set("va yoki bilan uchun boʻyicha hamda ham esa bu ushbu shu oʻz ular kerak mumkin emas boʻlsa boʻladi etib "
            "qilib".split())


def _toks(text: str) -> list[str]:
    return _TOK.findall(normalize_uz(text or "").lower().replace("ʼ", "ʻ").replace("'", "ʻ"))


def _unit(w: str) -> str | None:
    for u in UNIT:
        if w == u or (w.startswith(u) and len(w) - len(u) <= 4 and not (u == "oy" and w.startswith("oyi"))):
            return UNIT[u]
    return None


def quantities(text: str) -> set[tuple[str, str]]:
    """{(unit, number)}: «15 ish kunidan» → {("kun", "15")}, «yigirma bir kalendar kun» → {("kun", "21")}."""
    toks, out, i = _toks(text), set(), 0
    while i < len(toks):
        j = i
        while j < len(toks) and (toks[j].isdigit() or _NUMW.match(toks[j])):
            j += 1
        if j == i:
            i += 1
            continue
        nums = {t for t in toks[i:j] if t.isdigit()} | number_words(" ".join(toks[i:j]))
        for t in toks[j:j + 3]:                       # «15 ish kuni», «yigirma bir kalendar kun»
            if _unit(t):
                out |= {(_unit(t), n) for n in nums}
                break
        i = j
    return out


def _content(text: str) -> set[str]:
    return {stem(w) for w in _toks(text) if not w.isdigit() and not _NUMW.match(w) and not _unit(w)
            and w not in _STOP and len(w) > 2}


@lru_cache(maxsize=4096)
def _sentences(text: str) -> tuple:
    """(sentence, {(unit, number)}, {content stems}) for the sentences of `text` that state an amount."""
    out = []
    for a in _SENT.split(text or ""):
        q = quantities(a)
        if q:
            w = _content(a)
            if len(w) >= 3:
                out.append((a.strip(), frozenset(q), frozenset(w)))
    return tuple(out)


def same_rule_other_amount(low: str, high: str, overlap: float = 0.6) -> tuple[str, str] | None:
    """A sentence of `low` that is the same sentence as one of `high` (≥ `overlap` of the content words both ways)
    but with a different amount of the same unit → (low sentence, high sentence)."""
    for a, qa, wa in _sentences(low or ""):
        for b, qb, wb in _sentences(high or ""):
            units = {u for u, _ in qa} & {u for u, _ in qb}
            if not units or any({n for x, n in qa if x == u} & {n for x, n in qb if x == u} for u in units):
                continue
            both = len(wa & wb)
            if both / len(wa) >= overlap and both / len(wb) >= overlap:
                return a, b
    return None


_reenact_cache: dict[str, dict[str, int]] = {}


def reenacted(con) -> dict[str, int]:
    """{«mehnat kodeksi»: number of the current code's Lex.uz id} for codes that have an older version in this database."""
    key = str(getattr(con, "label", None) or id(con))
    if key not in _reenact_cache:
        cur = sorted(set(superseded(con).values()))
        out: dict[str, int] = {}
        if cur:
            marks = ", ".join("?" for _ in cur)
            for r in con.execute(f"SELECT DISTINCT doc_id, doc_title, doc_type FROM articles WHERE doc_id IN ({marks})", cur):
                name = title_key(r["doc_title"])
                if r["doc_type"] == "code" and name.endswith("kodeksi"):
                    out[name] = doc_num(r["doc_id"])
        _reenact_cache[key] = out
    return _reenact_cache[key]


def drop_outdated(con, ctx: list, exact=()) -> tuple[list, list[dict]]:
    """Leaves out (never an explicit reference):
    • a chunk of a lower act that cites «<code> N-moddasi» of a code re-enacted after it — it cites the old numbering;
    • a chunk of a lower act with the same sentence as a higher act among `ctx` and another amount (hierarchy of norms).
    Returns (kept, [{chunk_id, doc_id, doc_title, reason}])."""
    exact, codes = set(exact), reenacted(con)
    rank = lambda c: DOC_RANK.get(c.meta.get("doc_type"), 9)
    kept, dropped = [], []
    for c in ctx:
        why = None
        if c.chunk_id not in exact and c.meta.get("doc_type") not in ("constitution", "code"):
            text = " ".join(_toks(c.text))
            num = doc_num(c.meta.get("doc_id"))
            for name, cur in codes.items():
                if num < cur and re.search(re.escape(name) + r"(ning)?\s+\d+\s*(moddas|moddalar)", text):
                    why = f"«{name}»ning eski tahriridagi moddaga havola (hujjat yangi kodeksdan oldin qabul qilingan)"
                    break
            if not why:
                for h in ctx:
                    if h is c or rank(h) >= rank(c) or h.meta.get("doc_id") == c.meta.get("doc_id"):
                        continue
                    pair = same_rule_other_amount(c.text, h.text)
                    if pair:
                        why = f"ustun hujjatda boshqa miqdor: «{pair[1][:120]}» — {h.meta.get('doc_title')}"
                        break
        if why:
            dropped.append({"chunk_id": c.chunk_id, "doc_id": c.meta.get("doc_id"), "doc_title": c.meta.get("doc_title"),
                            "reason": why})
        else:
            kept.append(c)
    return kept, dropped


def numbers(text: str) -> set[str]:
    return set(NUM_RE.findall(text)) | number_words(text)


def is_quantity_question(question: str) -> bool:
    return bool(QUANTITY.search(normalize_uz(question).lower()))


def resolve_numbers(question: str, kept: list[dict], meta_of) -> tuple[list[dict], list[dict], str | None]:
    """kept: verified sentences ({text, chunk_ids, …}); meta_of(chunk_id) → that chunk's meta.
    Returns (kept, dropped, winning doc title)."""
    if not is_quantity_question(question):
        return kept, [], None
    doc_of = lambda s: meta_of(s["chunk_ids"][0]) if s.get("chunk_ids") else {}
    numeric = [s for s in kept if numbers(s["text"])]
    docs = {str(doc_of(s).get("doc_id")) for s in numeric}
    if len(docs) < 2:
        return kept, [], None
    by_doc: dict[str, set] = {}
    for s in numeric:
        by_doc.setdefault(str(doc_of(s).get("doc_id")), set()).update(numbers(s["text"]))
    if len({frozenset(v) for v in by_doc.values()}) < 2:
        return kept, [], None
    first = {d: i for i, d in reversed(list(enumerate(str(doc_of(s).get("doc_id")) for s in numeric)))}

    def rank(d: str):
        m = next(doc_of(s) for s in numeric if str(doc_of(s).get("doc_id")) == d)
        return DOC_RANK.get(m.get("doc_type"), 9), -doc_num(d), first[d]

    best = min(by_doc, key=rank)
    title = next(doc_of(s).get("doc_title") for s in numeric if str(doc_of(s).get("doc_id")) == best)
    dropped = [s for s in numeric if str(doc_of(s).get("doc_id")) != best]
    return [s for s in kept if s not in dropped], dropped, title


# Higher acts move up a few places among the retrieved chunks (hierarchy of norms: a resolution quoting an
# article of the 1995 Labour Code must not outrank the 2022 Code itself). A shift, not a filter: a by-law
# still wins when it is clearly the better match. Measured as eval mode `hybrid_auth`; on with AUTHORITY_PRIOR=on.
SHIFT = {"constitution": 3.0, "code": 3.0, "law": 1.5}


def arrange(ctx: list, old: dict, exact=(), k: int = 5, authority: bool = False) -> list:
    """Drops older versions (never an explicit reference), optionally applies the authority shift, keeps
    max(k, len(exact)) chunks and renumbers them 1…n."""
    exact = set(exact)
    keep = [c for c in ctx if str(c.meta.get("doc_id")) not in old or c.chunk_id in exact]
    if authority:
        first = [c for c in keep if c.chunk_id in exact]
        rest = [c for c in keep if c.chunk_id not in exact]
        rest = [c for _, c in sorted(((i - SHIFT.get(c.meta.get("doc_type"), 0.0), i), c)
                                     for i, c in enumerate(rest))]
        keep = first + rest
    keep = keep[:max(k, len(exact))]
    for n, c in enumerate(keep, start=1):
        c.n = n
    return keep
