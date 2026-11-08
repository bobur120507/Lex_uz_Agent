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
2. `resolve_numbers(...)` — when a question asks for a quantity («necha», «qancha», «foiz»…) and verified
   sentences from different documents state different numbers, only the most authoritative document's numeric
   sentences stay (Constitution → code → law → decree → resolution → order; then the newer document).
"""

from __future__ import annotations

import re

from .textnorm import normalize_uz, number_words

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


def find_superseded(rows) -> dict[str, str]:
    """rows: (doc_id, doc_title, doc_type). Returns {old doc_id: current doc_id}."""
    groups: dict[str, list[str]] = {}
    for doc_id, title, kind in rows:
        key = title_key(title)
        if kind not in TYPES or not key or SEPARATE.search(key):
            continue
        groups.setdefault(f"{kind}|{key}", []).append(str(doc_id))
    out = {}
    for ids in groups.values():
        ids = sorted(set(ids), key=doc_num)
        for old in ids[:-1]:
            out[old] = ids[-1]
    return out


def superseded(con) -> dict[str, str]:
    """{old doc_id: current doc_id} for this database — computed once per database (its label/path)."""
    key = str(getattr(con, "label", None) or id(con))
    if key not in _cache:
        marks = ", ".join("?" for _ in TYPES)
        rows = con.execute(f"SELECT DISTINCT doc_id, doc_title, doc_type FROM articles WHERE doc_type IN ({marks})",
                           TYPES).fetchall()
        _cache[key] = find_superseded((r["doc_id"], r["doc_title"], r["doc_type"]) for r in rows)
    return _cache[key]


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
