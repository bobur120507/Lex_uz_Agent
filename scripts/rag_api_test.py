"""100-question test of the RAG API — «RAG API — test spetsifikatsiyasi (lex.uz)» §1, §6, §7.

What it does (tester side, standard library only; python-docx optional for the .docx report):
  1. GET /v1/health, /v1/meta                         → health.json, meta.json
  2. API checklist §7 (auth 401/403, 11 items → 400, empty question / duplicate id → 400, rate limit 429,
     an error in one question does not break the batch, meta/health)
  3. the 100 questions in 10 batches b01…b10, one after another (202 → polling, 5xx → retry 5/15/45 s,
     429 → Retry-After, retryable item errors → the same batch_id again)  → batches/b01.json …
  4. after the run: idempotency (same batch_id → saved result), 409 (same id, other content), determinism
     (/v1/rag/query twice → same sources), Latin/Cyrillic/Russian
  5. scoring (§6): Hit@5 document / article, MRR, context precision, answer correctness 0/1/2 (LLM judge +
     the test set's key facts), faithfulness, citation accuracy, fabricated / outdated sources, no-answer
     accuracy, latency p50/p95, error share; every wrong answer gets ONE cause: retrieval / generation / source
  6. report: HISOBOT.md, HISOBOT.html, HISOBOT.docx (all 100 questions with answers and sources),
     results.csv, metrics.json, checks.json

Usage:
  python scripts/rag_api_test.py --base-url http://127.0.0.1:8080 --api-key <KEY>
  python scripts/rag_api_test.py --rescore data/reports/rag100/<run_id>     # score saved batches again (no API calls)
Options: --testset data/testset/test100.csv · --judge auto|none|cache|<ollama model> · --ollama-url · --db (local corpus
check of document ids and old versions; default: the project's database when run inside the repo).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=5))
TARGETS = {  # spec §6 «Maqsad (taklif)»
    "hit5_doc": (0.90, ">="), "hit5_article": (0.80, ">="), "mrr": (0.70, ">="), "context_precision": (0.60, ">="),
    "answer_correctness": (1.6, ">="), "faithfulness": (0.95, ">="), "citation_accuracy": (0.90, ">="),
    "fabricated_sources": (0, "=="), "outdated_norms": (0, "=="), "no_answer_accuracy": (0.9, ">="),
    "latency_p50_s": (5.0, "<="), "latency_p95_s": (12.0, "<="), "error_rate": (0.02, "<="),
}
OPTIONS = {"top_k": 5, "return_contexts": True, "return_debug": True, "temperature": 0, "seed": 42,
           "as_of_date": None, "answer_language": "auto"}
APOS = "'`‘’ʻʼ´ʹ"


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"{datetime.now(TZ):%H:%M:%S} {msg}", flush=True)


# =========================================================================== HTTP

class Api:
    def __init__(self, base: str, key: str | None, timeout: float = 180):
        self.base, self.key, self.timeout = base.rstrip("/"), key, timeout
        self.last_post = 0.0

    def call(self, method: str, path: str, body=None, key: str | None = "default", raw: bytes | None = None):
        """→ (status, json-or-None, headers, seconds). Never raises on HTTP errors."""
        k = self.key if key == "default" else key
        data = raw if raw is not None else (json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
        hdr = {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}
        if k:
            hdr["Authorization"] = f"Bearer {k}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=hdr)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                txt = r.read().decode("utf-8")
                return r.status, _loads(txt), dict(r.headers), time.perf_counter() - t0
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            return e.code, _loads(txt), dict(e.headers), time.perf_counter() - t0
        except Exception as e:  # connection refused, timeout…
            return 0, {"error": {"code": "NETWORK", "message": str(e)[:200]}}, {}, time.perf_counter() - t0

    def post_batch(self, body: dict) -> tuple[int, dict, dict, float]:
        """POST with the spec's client rules: ≤ 1 batch/s, 429 → Retry-After, 5xx/network → 5, 15, 45 s."""
        delays = [5, 15, 45]
        while True:
            gap = time.monotonic() - self.last_post
            if gap < 1.1:
                time.sleep(1.1 - gap)
            self.last_post = time.monotonic()
            st, js, hd, secs = self.call("POST", "/v1/rag/batch", body)
            if st == 429:
                wait = float({k.lower(): v for k, v in hd.items()}.get("retry-after", "1") or 1)
                log(f"  429 — {wait:.0f} s kutiladi")
                time.sleep(wait)
                continue
            if (st == 0 or st >= 500) and delays:
                d = delays.pop(0)
                log(f"  HTTP {st or 'tarmoq xatosi'} — {d} s dan keyin qayta")
                time.sleep(d)
                continue
            return st, js, hd, secs


def _loads(txt: str):
    try:
        return json.loads(txt) if txt else None
    except json.JSONDecodeError:
        return {"_raw": txt[:300]}


# =========================================================================== test set

def load_testset(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    need = {"id", "batch", "category", "question", "expected_answer", "expected_doc_id", "expected_article", "answerable"}
    if not rows or need - set(rows[0]):
        sys.exit(f"{path}: ustunlar yetishmaydi: {sorted(need - set(rows[0] if rows else []))}")
    for r in rows:
        r["answerable"] = str(r["answerable"]).strip().lower() in ("true", "1", "ha", "yes")
        docs = [d.strip() for d in (r["expected_doc_id"] or "").split(";") if d.strip()]
        arts = [a.strip() for a in (r["expected_article"] or "").split(";") if a.strip()]
        if arts and len(docs) == 1 and len(arts) > 1:
            docs = docs * len(arts)
        r["exp_pairs"] = [(docnum(d), artnum(a)) for d, a in zip(docs, arts)] if arts else []
        r["exp_docs"] = sorted({docnum(d) for d in docs})
        r["facts"] = [f.split("|") for f in (r.get("key_facts") or "").split(";") if f.strip()]
        r.setdefault("language", "")
    return rows


def docnum(d) -> str:
    return re.sub(r"\D", "", str(d or ""))


def artnum(a) -> str:
    m = re.search(r"\d+(?:\^\d+)?", str(a or ""))
    return m.group(0) if m else ""


# =========================================================================== text support (deterministic)

_NUM_WORDS = None


def _numwords(text: str) -> set[str]:
    global _NUM_WORDS
    if _NUM_WORDS is None:
        try:
            sys.path.insert(0, str(ROOT / "src"))
            from modda.textnorm import number_words      # «yigirma bir» → 21 (laws write numbers in words)
            _NUM_WORDS = number_words
        except Exception:
            _NUM_WORDS = lambda t: set()
    return _NUM_WORDS(text)


def norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(f"([og])[{re.escape(APOS)}]", r"\1ʻ", t)
    t = re.sub(f"[{re.escape(APOS)}]", "ʼ", t)
    return re.sub(r"\s+", " ", t)


def words(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-zʻʼа-яёўқғҳ]+", norm(text)) if len(w) >= 4}


def numbers(text: str) -> set[str]:
    t = norm(text)
    return set(re.findall(r"\d+", t)) | _numwords(t)


def supported(claim: str, source: str, overlap: float = 0.5) -> tuple[bool, float]:
    """A claim is supported when every number in it occurs in the source and ≥ `overlap` of its content words do."""
    cw = words(claim)
    share = len(cw & words(source)) / len(cw) if cw else 1.0
    nums_ok = set(re.findall(r"\d+", norm(claim))) <= numbers(source)
    return nums_ok and share >= overlap, round(share, 2)


def claims(answer: str) -> list[tuple[str, list[int]]]:
    """«text [1] text [2][3]» → [(text, [1]), (text, [2, 3])]."""
    out, parts = [], re.split(r"((?:\s*\[\d+\])+)", answer or "")
    for i in range(0, len(parts), 2):
        txt = parts[i].strip(" .;")
        refs = [int(x) for x in re.findall(r"\d+", parts[i + 1])] if i + 1 < len(parts) else []
        if len(re.findall(r"\w+", txt)) >= 3:
            out.append((txt, refs))
    return out


# =========================================================================== judge (Ollama, optional)

def ref_facts(expected: str) -> list[str]:
    """The reference answer's facts: its «;»-separated clauses (a «;» inside brackets or quotes does not split)."""
    parts, cur, depth = [], "", 0
    for ch in expected or "":
        depth += ch in "([«" and 1 or 0
        depth -= ch in ")]»" and 1 or 0
        if ch == ";" and depth <= 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip(" .") for p in parts if p.strip(" .")][:6]


def real_conflict(c, answer: str, facts: list[str]) -> str | None:
    """The judge's «conflict», kept only when it can be checked: the quoted part is in the answer and states a number
    that the reference does not state anywhere. The reference's «quoted» parts are left out — they name the outdated
    figure («eski kodeksdagi «15 ish kuni» emas»); its brackets are kept — they can hold a second figure («umumiy holda
    — ellik foiz», q062, 9-noyabr). A bare «bir» is the article «a» as often as the number one (q052 «bir bola uchun»).
    At 22:00 the judge called «qirq sakkiz soat» a contradiction of «48 soat» (q013); at 18:11 it pointed at the wrong
    fact (q099)."""
    if not isinstance(c, dict) or not isinstance(c.get("answer_says"), str):
        return None
    says = c["answer_says"].strip(" .")
    if not says or not (norm(says) in norm(answer) or len(words(says) & words(answer)) >= 0.8 * max(1, len(words(says)))):
        return None
    n_says = numbers(says) - {"1"}
    n_ref = numbers(re.sub(r"«[^»]*»", " ", " ".join(facts)))
    return says if n_says and n_ref and not n_says <= n_ref else None


class Judge:
    PREFER = ["qwen3:8b", "qwen2.5:7b", "llama3.1:8b", "mistral:7b", "gemma3:12b", "gemma3:4b"]

    def __init__(self, url: str, model: str | None):
        self.url, self.model, self.calls = url.rstrip("/"), model, 0

    @classmethod
    def pick(cls, url: str, want: str, system_llm: str | None) -> "Judge":
        if want == "none":
            return cls(url, None)
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=10) as r:
                have = [m["name"] for m in json.loads(r.read())["models"]]
        except Exception as e:
            log(f"Hakam: Ollama’ga ulanib boʻlmadi ({e}) — faqat kalit faktlar bilan baholanadi")
            return cls(url, None)
        if want != "auto":
            return cls(url, want if want in have else None)
        for m in cls.PREFER:                              # another model than the one being tested, if installed
            if m in have and m != system_llm:
                return cls(url, m)
        return cls(url, system_llm if system_llm in have else (have[0] if have else None))

    def ask(self, prompt: str) -> dict | None:
        if not self.model:
            return None
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False, "format": "json",
                "think": False, "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 400}, "keep_alive": "30m"}
        for attempt in range(2):
            try:
                req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    txt = json.loads(r.read())["message"]["content"]
                self.calls += 1
                return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            except urllib.error.HTTPError as e:
                if e.code == 400 and "think" in body:
                    body.pop("think")
                    continue
                return None
            except Exception:
                if attempt:
                    return None
        return None

    def grade(self, q: dict, res: dict) -> dict | None:
        cited = {c.get("chunk_id") for c in res.get("citations") or []}
        src = "\n\n".join(f"[{c['rank']}] {c.get('doc_title')} {c.get('article') or ''}\n{(c.get('text') or '')[:1800]}"
                          for c in res.get("contexts") or [] if c.get("chunk_id") in cited) or "(manba keltirilmagan)"
        uz = (res.get("debug") or {}).get("answer_uz")
        facts = ref_facts(q.get("expected_answer") or "")
        if not facts:
            return None
        # A checklist with the facts given, not found by the judge: on 8-noyabr 20:14 a holistic 0–2 grade gave 2 to wrong
        # answers; at 22:00 a judge that listed «the reference's facts» itself took them from the cited law instead (q021,
        # q034, q038, q098…) and marked correct answers as partial. The facts are now the reference answer's own clauses.
        listed = "\n".join(f"{i}. {f}" for i, f in enumerate(facts, 1))
        prompt = (
            "You check an Uzbek legal question-answering system against reference facts taken from the law.\n"
            f"QUESTION: {q['question']}\nREFERENCE FACTS:\n{listed}\n"
            f"SYSTEM ANSWER: {res.get('answer')}\n" + (f"SYSTEM ANSWER (Uzbek original): {uz}\n" if uz else "") +
            f"SOURCE TEXTS THE SYSTEM CITED:\n{src}\n\n"
            "1. For EACH numbered reference fact: is it stated in the SYSTEM ANSWER? Wording and language may differ; a "
            "number written in words equals the digits; text in brackets is a note, not required. A different number, "
            "period, age or subject is NOT the same fact. Check only these facts — do not add others.\n"
            "2. same_topic — does the system answer talk about what the QUESTION asks?\n"
            "3. conflict — if the SYSTEM ANSWER states a DIFFERENT number, period or amount for the same thing as a "
            "reference fact, copy that part of the system answer word for word into answer_says; otherwise null.\n"
            "4. faithful — is every claim of the system answer stated in the cited source texts?\n"
            "Return JSON only: {\"present\": [true|false for fact 1, fact 2, …], \"same_topic\": true|false, "
            "\"conflict\": {\"answer_says\": \"…\", \"fact\": 1} or null, \"faithful\": true|false, \"reason\": \"one short sentence\"}")
        out = self.ask(prompt)
        if not out or not isinstance(out.get("present"), list):
            return None
        present = [x is True for x in out["present"][:len(facts)]] + [False] * max(0, len(facts) - len(out["present"]))
        found = sum(present)
        conflict = real_conflict(out.get("conflict"), " ".join(filter(None, [res.get("answer"), uz])), facts)
        if out.get("same_topic") is False or conflict:
            grade = 0
        else:
            grade = 2 if found == len(facts) else 1 if found else 0
        return {"facts": [{"fact": f, "present": p} for f, p in zip(facts, present)], "same_topic": out.get("same_topic"),
                "conflict": conflict, "faithful": out.get("faithful"), "reason": out.get("reason"),
                "correctness": grade, "facts_present": f"{found}/{len(facts)}"}

    def relevance(self, q: dict, res: dict) -> list[int] | None:
        ctx = res.get("contexts") or []
        if not ctx:
            return []
        blocks = "\n\n".join(f"[{c['rank']}] {c.get('doc_title')} {c.get('article') or ''}\n{(c.get('text') or '')[:1200]}" for c in ctx[:5])
        out = self.ask(f"QUESTION: {q['question']}\n\nPASSAGES:\n{blocks}\n\nWhich passages contain information that helps "
                       "answer the question? Return JSON only: {\"relevant\": [list of passage numbers]}.")
        if not out or not isinstance(out.get("relevant"), list):
            return None
        return [int(x) for x in out["relevant"] if str(x).isdigit()]


# =========================================================================== local corpus checks (optional)

class CachedJudge(Judge):
    """`--judge cache` with `--rescore`: the saved run's own judge verdicts (judge.jsonl) graded again by the current
    rules, with no LLM call — the same verdict always gives the same grade. 9-noyabr: the 18:11 run's verdicts re-graded
    after the «conflict» check was corrected (q052, q062, q099)."""

    def __init__(self, path: Path):
        super().__init__("", None)
        self.saved = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                j = json.loads(line)
                self.saved[j["id"]] = j
        self.model = f"saqlangan hakam bahosi ({path.name}, {len(self.saved)} ta)" if self.saved else None

    def grade(self, q: dict, res: dict) -> dict | None:
        g = (self.saved.get(q["id"]) or {}).get("grade")
        if not g or not isinstance(g.get("facts"), list):
            return g
        facts = [f.get("fact") or "" for f in g["facts"]]
        present = [f.get("present") is True for f in g["facts"]]
        uz = (res.get("debug") or {}).get("answer_uz")
        conflict = real_conflict({"answer_says": g["conflict"]} if g.get("conflict") else None,
                                 " ".join(filter(None, [res.get("answer"), uz])), facts)
        found = sum(present)
        grade = 0 if g.get("same_topic") is False or conflict else 2 if found == len(facts) else 1 if found else 0
        return {**g, "conflict": conflict, "correctness": grade, "facts_present": f"{found}/{len(facts)}"}

    def relevance(self, q: dict, res: dict):
        return (self.saved.get(q["id"]) or {}).get("relevant")


class Corpus:
    def __init__(self):
        self.docs, self.old, self.note, self.con, self.types = None, {}, "tekshirilmadi (loyiha bazasi topilmadi)", None, {}

    @classmethod
    def open(cls, db: str | None) -> "Corpus":
        c = cls()
        try:
            sys.path.insert(0, str(ROOT / "src"))
            from modda.config import get_settings
            from modda.corpus import connect
            from modda.versions import superseded
            s = get_settings()
            con = connect(db or s.db_path, url=None if db else (s.database_url or None))
            rows = con.execute("SELECT DISTINCT doc_id, doc_type FROM articles").fetchall()
            c.docs = {docnum(r[0]) for r in rows}
            c.types = {docnum(r[0]): r[1] for r in rows}
            c.old = {docnum(k): docnum(v) for k, v in superseded(con).items()}
            c.con = con
            c.note = f"loyiha bazasi: {len(c.docs)} hujjat, {len(c.old)} ta eski nusxa (versions.py)"
        except Exception as e:
            c.note = f"tekshirilmadi ({type(e).__name__}: {str(e)[:120]})"
        return c

    def outdated_chunks(self, contexts: list[dict]) -> dict[str, str]:
        """{chunk_id: why} — contexts of this answer that are outdated by the project's rules (versions.drop_outdated): a
        by-law citing the old numbering of a re-enacted code, or a lower act stating another amount than a higher one."""
        if self.con is None or not contexts:
            return {}
        try:
            from modda.rag import Context
            from modda.versions import drop_outdated
            ctx = [Context(i, c.get("chunk_id"), 0.0, "", c.get("text") or "",
                           {"doc_id": "-" + docnum(c.get("doc_id")), "doc_title": c.get("doc_title"),
                            "doc_type": self.types.get(docnum(c.get("doc_id")))}) for i, c in enumerate(contexts, 1)]
            return {d["chunk_id"]: d["reason"] for d in drop_outdated(self.con, ctx)[1]}
        except Exception:
            return {}


# =========================================================================== API checklist (§7)

def check(checks: list, name: str, ok: bool | None, detail: str = "") -> None:
    checks.append({"check": name, "ok": ok, "detail": detail})
    log(f"  {'✅' if ok else '⚠️' if ok is None else '❌'} {name} {('— ' + detail) if detail else ''}")


def checks_before(api: Api, checks: list, run_id: str) -> None:
    st, js, _, _ = api.call("GET", "/v1/health")
    check(checks, "GET /v1/health ishlaydi", st == 200 and (js or {}).get("status") == "ok", f"HTTP {st}, {str((js or {}).get('status'))}")
    st, js, _, _ = api.call("GET", "/v1/meta")
    sysobj = (js or {}).get("system") or {}
    need = ["llm_model", "embedding_model", "index_version", "lex_snapshot_date"]
    check(checks, "GET /v1/meta: model, embedding, indeks versiyasi, lex.uz snapshot sanasi",
          st == 200 and all(sysobj.get(k) for k in need), f"HTTP {st}, " + ", ".join(f"{k}={sysobj.get(k)}" for k in need))
    if api.key:
        st, _, _, _ = api.call("GET", "/v1/meta", key=None)
        st2, _, _, _ = api.call("GET", "/v1/meta", key="wrong-key-" + str(int(time.time())))   # ASCII: HTTP headers are latin-1
        check(checks, "Autentifikatsiya: kalitsiz 401, notoʻgʻri kalit 401/403", st == 401 and st2 in (401, 403), f"{st}, {st2}")
    else:
        check(checks, "Autentifikatsiya: kalitsiz 401, notoʻgʻri kalit 401/403", None, "--api-key berilmagan — tekshirilmadi")

    def post(body):
        time.sleep(1.15)
        return api.call("POST", "/v1/rag/batch", body)[:2]

    base = {"run_id": run_id, "batch_index": 0, "total_batches": 0, "options": OPTIONS}
    st, _ = post({**base, "batch_id": f"{run_id}-chk-11", "items": [{"id": f"q{i:03d}", "question": "Mehnat taʼtili necha kun?"} for i in range(11)]})
    check(checks, "11 ta savol → 400", st == 400, f"HTTP {st}")
    st, _ = post({**base, "batch_id": f"{run_id}-chk-empty", "items": [{"id": "q001", "question": "  "}]})
    check(checks, "Boʻsh question → 400", st == 400, f"HTTP {st}")
    st, _ = post({**base, "batch_id": f"{run_id}-chk-dup", "items": [{"id": "q001", "question": "a?"}, {"id": "q001", "question": "b?"}]})
    check(checks, "Takroriy id → 400", st == 400, f"HTTP {st}")
    time.sleep(1.15)
    a = api.call("POST", "/v1/rag/batch", {**base, "batch_id": f"{run_id}-chk-rl1", "items": []})
    b = api.call("POST", "/v1/rag/batch", {**base, "batch_id": f"{run_id}-chk-rl2", "items": []})
    ra = {k.lower(): v for k, v in b[2].items()}.get("retry-after")
    check(checks, "Rate limit: 1 batch/s dan tez → 429 + Retry-After", b[0] == 429 and bool(ra), f"{a[0]}, {b[0]}, Retry-After={ra}")
    time.sleep(1.15)
    st, js, _, _ = api.call("POST", "/v1/rag/batch", {**base, "batch_id": f"{run_id}-chk-iso", "items": [
        {"id": "q001", "question": "Mehnat kodeksiga koʻra haftalik ish vaqti necha soat?", "language": "uz-Latn"},
        {"id": "q002", "question": "Test savol", "language": "xx-INVALID"}]})
    res = {r.get("id"): r for r in (js or {}).get("results") or []}
    ok = st == 200 and res.get("q001", {}).get("status") in ("ok", "no_answer") and res.get("q002", {}).get("status") == "error" \
        and (res.get("q002", {}).get("error") or {}).get("code")
    check(checks, "Bitta savoldagi xato boshqalarga taʼsir qilmaydi (status: error + error obyekti)", bool(ok),
          f"HTTP {st}; q001={res.get('q001', {}).get('status')}, q002={res.get('q002', {}).get('status')} "
          f"{(res.get('q002', {}).get('error') or {}).get('code')}")


def checks_after(api: Api, checks: list, rows: list[dict], sent: dict, got: dict, run_id: str) -> None:
    # results = items, every id once
    bad = [b for b, body in sent.items() if sorted(i["id"] for i in body["items"]) != sorted(r.get("id") for r in (got.get(b) or {}).get("results") or [])]
    check(checks, "Javobda har bir id bitta marta, savollar soniga teng", not bad, "hammasi mos" if not bad else f"mos emas: {bad}")
    sysok = all(((got.get(b) or {}).get("system") or {}).get("llm_model") for b in sent)
    check(checks, "Har bir javobda system obyekti", sysok)
    # citations fields, contexts, chunk ids
    allres = [r for b in got.values() for r in (b or {}).get("results") or []]
    fields = ["doc_id", "url", "article", "edition_date", "doc_status", "quote"]
    # «article» may be empty only for a document that is not divided into articles (court plenum resolutions, amending
    # acts…): it is a defect when the same document appears with article numbers in this run
    with_articles = {c.get("doc_id") for r in allres for c in (r.get("contexts") or []) + (r.get("citations") or []) if c.get("article")}
    miss = sorted({f for r in allres for c in r.get("citations") or [] for f in fields
                   if not c.get(f) and not (f == "article" and c.get("doc_id") not in with_articles)})
    check(checks, "Har citations’da: doc_id, url, article, edition_date, doc_status, quote", not miss, "toʻliq" if not miss else f"boʻsh maydonlar: {miss}")
    noctx = [r["id"] for r in allres if r.get("status") == "ok" and not r.get("contexts")]
    bad_ctx = [r["id"] for r in allres for c in r.get("contexts") or [] if c.get("text") is None or c.get("retrieval_score") is None]
    check(checks, "Har javobda contexts (top-k, matni va ballari bilan)", not noctx and not bad_ctx,
          "toʻliq" if not (noctx or bad_ctx) else f"contexts yoʻq: {noctx[:5]}, matn/ball yoʻq: {sorted(set(bad_ctx))[:5]}")
    stray = [r["id"] for r in allres for c in r.get("citations") or [] if c.get("chunk_id") not in {x.get("chunk_id") for x in r.get("contexts") or []}]
    check(checks, "Har citations[].chunk_id contexts ichida bor", not stray, "hammasi" if not stray else f"yoʻq: {sorted(set(stray))[:8]}")
    # idempotency and 409
    b01 = sorted(sent)[0]
    time.sleep(1.15)
    t0 = time.perf_counter()
    st, js, _, _ = api.call("POST", "/v1/rag/batch", sent[b01])
    secs = time.perf_counter() - t0
    same = st == 200 and json.dumps((js or {}).get("results"), sort_keys=True) == json.dumps((got.get(b01) or {}).get("results"), sort_keys=True)
    check(checks, "Bir xil batch_id qayta yuborilsa saqlangan natija qaytadi", same, f"HTTP {st}, {secs:.1f} s, natija {'bir xil' if same else 'farq qiladi'}")
    time.sleep(1.15)
    other = {**sent[b01], "items": sent[b01]["items"][:1]}
    st, _, _, _ = api.call("POST", "/v1/rag/batch", other)
    check(checks, "Shu batch_id boshqa mazmun bilan → 409", st == 409, f"HTTP {st}")
    st, js, _, _ = api.call("GET", f"/v1/rag/batch/{sent[b01]['batch_id']}")
    check(checks, "GET /v1/rag/batch/{batch_id} saqlangan natijani qaytaradi", st == 200 and (js or {}).get("status") == "completed", f"HTTP {st}, {(js or {}).get('status')}")
    # determinism
    q = next(r for r in rows if r["answerable"])
    outs = []
    for _ in range(2):
        st, js, _, _ = api.call("POST", "/v1/rag/query", {"question": q["question"], "options": {"temperature": 0, "seed": 42, "top_k": 5}})
        r = (js or {}).get("result") or {}
        outs.append(([c.get("chunk_id") for c in r.get("contexts") or []], [c.get("chunk_id") for c in r.get("citations") or []], r.get("answer")))
    det = len(outs) == 2 and outs[0][:2] == outs[1][:2] and outs[0][0]
    check(checks, "temperature = 0 va seed bilan bir xil savol bir xil manbalarni qaytaradi", bool(det),
          f"/v1/rag/query ×2 ({q['id']}): manbalar {'bir xil' if det else 'farq qiladi'}, javob matni {'bir xil' if outs[0][2] == outs[1][2] else 'farq qiladi'}")
    # scripts
    lang_rows = [r for r in rows if (r.get("language") or "") in ("ru", "uz-Cyrl")]
    res_by = {r["id"]: r for r in allres}
    bad_lang = [r["id"] for r in lang_rows if res_by.get(r["id"], {}).get("status") in ("error", "timeout", None)]
    moji = [r["id"] for r in allres if re.search("Ã|Ð|�|â€", r.get("answer") or "")]
    uz_ok = any("ʻ" in (r.get("answer") or "") or "'" in (r.get("answer") or "") for r in allres if r.get("answer_language") == "uz-Latn")
    check(checks, "Lotin, kirill va rus tilidagi savollar toʻgʻri ishlaydi, oʻ / gʻ buzilmaydi",
          not bad_lang and not moji and uz_ok, f"xato: {bad_lang or 'yoʻq'}; buzilgan belgi: {moji or 'yoʻq'}; oʻ/gʻ: {'bor' if uz_ok else 'topilmadi'}")
    slow = [b for b, x in got.items() if (x or {}).get("_client_seconds", 0) > 120 and not (x or {}).get("_async")]
    asyn = [b for b, x in got.items() if (x or {}).get("_async")]
    check(checks, "Batch ≤ 120 s yoki async 202 + GET ishlaydi", not slow,
          f"eng uzun: {max(((x or {}).get('_client_seconds', 0) for x in got.values()), default=0):.0f} s" + (f"; async: {asyn}" if asyn else ""))
    check(checks, "Test uchun alohida API kalit va base URL berilgan", bool(api.key), f"base URL: {api.base}; kalit: {'bor' if api.key else 'yoʻq'}")


# =========================================================================== run

def run_batches(api: Api, rows: list[dict], run_id: str, out: Path) -> tuple[dict, dict]:
    batches = sorted({r["batch"] for r in rows})
    sent, got = {}, {}
    (out / "batches").mkdir(parents=True, exist_ok=True)
    (out / "requests").mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(batches, start=1):
        items = [{"id": r["id"], "question": r["question"], **({"language": r["language"]} if r.get("language") else {})}
                 for r in rows if r["batch"] == b]
        body = {"run_id": run_id, "batch_id": f"{run_id}-{b}", "batch_index": i, "total_batches": len(batches),
                "options": {**OPTIONS, "as_of_date": datetime.now(TZ).date().isoformat()}, "items": items}
        sent[b] = body
        (out / "requests" / f"{b}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{b}: {len(items)} ta savol yuborildi …")
        t0 = time.perf_counter()
        st, js, _, _ = api.post_batch(body)
        is_async = False
        if st == 202:                                     # async: poll until completed / failed
            is_async = True
            deadline = time.time() + 1800
            while time.time() < deadline:
                time.sleep(3)
                st, js, _, _ = api.call("GET", f"/v1/rag/batch/{body['batch_id']}")
                if st == 200 and (js or {}).get("status") in ("completed", "failed"):
                    break
        for attempt in range(2):                          # retryable item errors → the same batch_id again (spec §3)
            retry = [r["id"] for r in (js or {}).get("results") or [] if r.get("status") in ("error", "timeout") and (r.get("error") or {}).get("retryable")]
            if st != 200 or not retry:
                break
            log(f"  {b}: {len(retry)} ta savolda qayta urinish mumkin boʻlgan xato — qayta yuboriladi")
            time.sleep(5)
            st, js, _, _ = api.post_batch(body)
        secs = time.perf_counter() - t0
        if st != 200 or not isinstance(js, dict) or "results" not in js:
            log(f"  ❌ {b}: HTTP {st} {str(js)[:200]}")
            js = {"status": "failed", "http_status": st, "body": js, "results": []}
        js["_client_seconds"], js["_async"] = round(secs, 1), is_async
        got[b] = js
        (out / "batches" / f"{b}.json").write_text(json.dumps(js, ensure_ascii=False, indent=1), encoding="utf-8")
        sm = js.get("summary") or {}
        log(f"  {b}: {secs:.1f} s · ok {sm.get('ok', '—')} · javobsiz {sm.get('no_answer', '—')} · xato {sm.get('error', '—')}")
    return sent, got


# =========================================================================== scoring

def score(rows: list[dict], got: dict, judge: Judge, corpus: Corpus, out: Path) -> tuple[list[dict], dict]:
    res_by = {r.get("id"): r for b in got.values() for r in (b or {}).get("results") or []}
    per, jlog = [], (out / "judge.jsonl").open("w", encoding="utf-8")
    for n, q in enumerate(rows, start=1):
        r = res_by.get(q["id"]) or {"id": q["id"], "status": "missing", "citations": [], "contexts": []}
        ctx = (r.get("contexts") or [])[:5]
        top = [(docnum(c.get("doc_id")), artnum(c.get("article"))) for c in ctx]
        exp = set(q["exp_pairs"])
        p = {"id": q["id"], "batch": q["batch"], "category": q["category"], "answerable": q["answerable"],
             "status": r.get("status"), "no_answer": bool(r.get("no_answer")), "error": (r.get("error") or {}).get("code"),
             "total_ms": (r.get("timing") or {}).get("total_ms"), "answer_language": r.get("answer_language")}
        # retrieval
        if q["answerable"] and exp:
            p["hit_doc"] = any(d in q["exp_docs"] for d, _ in top)
            ranks = [i for i, t in enumerate(top, start=1) if t in exp]
            p["hit_article"] = bool(ranks)
            p["rank"] = ranks[0] if ranks else None
            p["rr"] = 1 / ranks[0] if ranks else 0.0
            p["all_articles"] = exp <= set(top)
            p["ctx_precision_doc"] = (sum(d in q["exp_docs"] for d, _ in top) / len(top)) if top else 0.0
        # citations
        cits = r.get("citations") or []
        ctx_by = {c.get("chunk_id"): c for c in r.get("contexts") or []}
        # a claim may name its act or the passage heading the model was shown (contexts[].header, if the API gives it)
        body = lambda c: f"{c.get('doc_title') or ''} {c.get('article') or ''} {c.get('header') or ''}\n{c.get('text') or ''}"
        cl = claims((r.get("debug") or {}).get("answer_uz") or r.get("answer") or "") if r.get("status") == "ok" else []
        cit_rows, fabricated, outdated = [], [], []
        stale = corpus.outdated_chunks(r.get("contexts") or [])
        for c in cits:
            src = ctx_by.get(c.get("chunk_id"))
            in_ctx = src is not None
            quote_ok = in_ctx and norm(c.get("quote") or "").strip(" .") in norm(src.get("text") or "")
            mine = [t for t, refs in cl if c.get("ref") in refs]
            sup = in_ctx and bool(mine) and all(supported(t, body(src))[0] for t in mine)
            url_ok = bool(re.fullmatch(r"https?://(www\.)?lex\.uz/(uz/|ru/)?docs/-?\d+/?", c.get("url") or "")) and docnum(c.get("url")) == docnum(c.get("doc_id"))
            known = corpus.docs is None or docnum(c.get("doc_id")) in corpus.docs
            if not in_ctx or not url_ok or not known:
                fabricated.append({"ref": c.get("ref"), "doc_id": c.get("doc_id"), "why": "; ".join(w for w, bad in (
                    ("contexts’da yoʻq", not in_ctx), ("url lex.uz hujjatiga mos emas", not url_ok), ("korpusda yoʻq", not known)) if bad)})
            old = docnum(c.get("doc_id")) in corpus.old
            if (c.get("doc_status") or "").lower() not in ("amalda", "in-force") or old or c.get("chunk_id") in stale:
                outdated.append({"ref": c.get("ref"), "doc_id": c.get("doc_id"), "doc_status": c.get("doc_status"),
                                 "why": f"yangi nusxasi: {corpus.old[docnum(c.get('doc_id'))]}" if old else
                                 stale.get(c.get("chunk_id")) or f"doc_status={c.get('doc_status')}"})
            cit_rows.append({"ref": c.get("ref"), "in_contexts": in_ctx, "quote_verbatim": bool(quote_ok), "supports": bool(sup),
                             "accurate": bool(in_ctx and quote_ok and sup), "expected": (docnum(c.get("doc_id")), artnum(c.get("article"))) in exp})
        p["citations"] = cit_rows
        p["fabricated"], p["outdated"] = fabricated, outdated
        # faithfulness (claims of the answer against the contexts they cite)
        fa = []
        for t, refs in cl:
            srcs = [body(ctx_by[c["chunk_id"]]) for c in cits if c.get("ref") in refs and c.get("chunk_id") in ctx_by] \
                or [body(c) for c in r.get("contexts") or []]
            fa.append(supported(t, "\n".join(srcs))[0])
        p["claims"], p["claims_supported"] = len(fa), sum(fa)
        # correctness: key facts + judge
        ans_all = norm(" ".join(filter(None, [r.get("answer"), (r.get("debug") or {}).get("answer_uz")])))
        if q["answerable"]:
            if r.get("status") != "ok":
                p["facts_found"], p["facts_total"], p["correct_facts"] = 0, len(q["facts"]), 0
            else:
                found = sum(any(norm(alt).strip() and norm(alt).strip() in ans_all for alt in f) for f in q["facts"])
                p["facts_found"], p["facts_total"] = found, len(q["facts"])
                p["correct_facts"] = 2 if q["facts"] and found == len(q["facts"]) else 1 if found else 0 if q["facts"] else None
            g = judge.grade(q, r) if judge.model and r.get("status") == "ok" else None
            rel = judge.relevance(q, r) if judge.model and r.get("contexts") else None
            p["judge"] = g
            p["correct_judge"] = int(g["correctness"]) if g and str(g.get("correctness")) in ("0", "1", "2") else (0 if judge.model and r.get("status") != "ok" else None)
            p["faithful_judge"] = bool(g.get("faithful")) if g else None
            if rel is not None:
                p["ctx_relevant"] = rel
                p["ctx_precision_judge"] = len({x for x in rel if 1 <= x <= len(ctx)}) / len(ctx) if ctx else 0.0
            # final grade: the judge's checklist, capped by the test set's key facts (a judge can be fooled by fluent
            # text on the wrong subject; a missing key number cannot) — the lower of the two
            cands = [x for x in (p.get("correct_judge"), p.get("correct_facts")) if x is not None]
            p["correctness"] = min(cands) if cands else None
            jlog.write(json.dumps({"id": q["id"], "grade": g, "relevant": rel}, ensure_ascii=False) + "\n")
            # one cause per wrong answer (spec §6)
            if (p["correctness"] or 0) < 2 or r.get("status") != "ok":
                p["cause"] = "retrieval" if not p.get("hit_article") else "generatsiya"
            elif not any(c["expected"] and c["accurate"] for c in cit_rows):
                p["cause"] = "manba"
        else:
            p["refused_ok"] = bool(r.get("no_answer"))
            if not p["refused_ok"]:
                p["cause"] = "gallyutsinatsiya (javobsiz savolga javob)"
        per.append(p)
        if n % 10 == 0:
            log(f"  baholandi: {n}/{len(rows)}" + (f" (hakam soʻrovlari: {judge.calls})" if judge.model else ""))
    jlog.close()
    return per, metrics(per, rows, got)


def metrics(per: list[dict], rows: list[dict], got: dict) -> dict:
    ans = [p for p in per if p["answerable"] and "hit_doc" in p]
    una = [p for p in per if not p["answerable"]]
    multi = {r["id"]: len(set(r["exp_pairs"])) > 1 for r in rows}
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    cits = [c for p in per for c in p["citations"]]
    lat = sorted(p["total_ms"] / 1000 for p in per if isinstance(p.get("total_ms"), (int, float)))
    pct = lambda q: round(lat[min(len(lat) - 1, max(0, int(round(q * len(lat) + 0.5)) - 1))], 2) if lat else None
    cp_j = [p["ctx_precision_judge"] for p in ans if "ctx_precision_judge" in p]
    m = {
        "n_total": len(per), "n_answerable": len(ans), "n_unanswerable": len(una),
        "hit5_doc": avg([p["hit_doc"] for p in ans]), "hit5_article": avg([p["hit_article"] for p in ans]),
        "mrr": avg([p["rr"] for p in ans]), "all_articles_found": avg([p["all_articles"] for p in ans if multi.get(p["id"])]),
        "context_precision": avg(cp_j) if cp_j else avg([p["ctx_precision_doc"] for p in ans]),
        "context_precision_method": "LLM-hakam" if cp_j else "hujjat darajasida",
        "context_precision_doc": avg([p["ctx_precision_doc"] for p in ans]),
        "answer_correctness": avg([p["correctness"] for p in ans if p.get("correctness") is not None]),
        "answer_correctness_judge": avg([p["correct_judge"] for p in ans if p.get("correct_judge") is not None]),
        "answer_correctness_facts": avg([p["correct_facts"] for p in ans if p.get("correct_facts") is not None]),
        "faithfulness": round(sum(p["claims_supported"] for p in per) / max(1, sum(p["claims"] for p in per)), 3) if any(p["claims"] for p in per) else None,
        "faithfulness_judge": avg([p["faithful_judge"] for p in ans if p.get("faithful_judge") is not None]),
        "citation_accuracy": avg([c["accurate"] for c in cits]),
        "citations_total": len(cits),
        "fabricated_sources": sum(len(p["fabricated"]) for p in per),
        "outdated_norms": sum(len(p["outdated"]) for p in per),
        "no_answer_accuracy": avg([p["refused_ok"] for p in una]),
        "no_answer_correct": sum(p["refused_ok"] for p in una),
        "false_refusals": sum(1 for p in per if p["answerable"] and p.get("no_answer")),
        "latency_p50_s": pct(0.5), "latency_p95_s": pct(0.95),
        "error_rate": round(sum(p["status"] in ("error", "timeout", "missing") for p in per) / max(1, len(per)), 3),
        "batch_seconds": {b: (x or {}).get("_client_seconds") for b, x in sorted(got.items())},
        "causes": {},
    }
    for p in per:
        if p.get("cause"):
            m["causes"].setdefault(p["cause"], []).append(p["id"])
    cats = {}
    for c in dict.fromkeys(r["category"] for r in rows):
        ps = [p for p in per if p["category"] == c]
        a = [p for p in ps if p["answerable"] and "hit_doc" in p]
        cats[c] = {"n": len(ps), "hit5_article": avg([p["hit_article"] for p in a]), "mrr": avg([p["rr"] for p in a]),
                   "correctness": avg([p["correctness"] for p in a if p.get("correctness") is not None]),
                   "no_answer_ok": avg([p["refused_ok"] for p in ps if not p["answerable"]]),
                   "errors": sum(p["status"] in ("error", "timeout", "missing") for p in ps)}
    m["by_category"] = cats
    m["targets_met"] = {k: met(k, m.get(k)) for k in TARGETS}
    return m


def met(k: str, v) -> bool | None:
    if v is None:
        return None
    t, op = TARGETS[k]
    return v >= t if op == ">=" else v <= t if op == "<=" else v == t


# =========================================================================== report (md / html / docx)

CAT_NAME = {"faktik": "Faktik, bitta modda", "raqam": "Raqamlar: muddat, summa, foiz, BHM", "kop_modda": "Bir nechta modda / hujjat",
            "ozgargan": "Oʻzgargan / kuchini yoʻqotgan normalar", "til": "Rus tili va kirill yozuvi", "javobsiz": "Javobi yoʻq / qonundan tashqari",
            "noaniq": "Noaniq / ogʻzaki ifodalangan"}
METRIC_ROWS = [
    ("Retrieval", "Hit@5 (hujjat)", "hit5_doc", "≥ 90%", "pct"), ("Retrieval", "Hit@5 (modda)", "hit5_article", "≥ 80%", "pct"),
    ("Retrieval", "MRR", "mrr", "≥ 0.70", "num"), ("Retrieval", "Context precision", "context_precision", "≥ 60%", "pct"),
    ("Generatsiya", "Answer correctness (0–2)", "answer_correctness", "oʻrtacha ≥ 1.6", "num"),
    ("Generatsiya", "Faithfulness", "faithfulness", "≥ 95%", "pct"), ("Manba", "Citation accuracy", "citation_accuracy", "≥ 90%", "pct"),
    ("Manba", "Toʻqilgan manba", "fabricated_sources", "0 ta", "int"), ("Manba", "Eskirgan norma", "outdated_norms", "0 ta", "int"),
    ("Xavfsizlik", "No-answer aniqligi", "no_answer_accuracy", "≥ 9 / 10", "na"), ("Operatsion", "Latency p50", "latency_p50_s", "≤ 5 s", "sec"),
    ("Operatsion", "Latency p95", "latency_p95_s", "≤ 12 s", "sec"), ("Operatsion", "Xato ulushi", "error_rate", "≤ 2%", "pct"),
]


def fmt(v, kind, m=None):
    if v is None:
        return "—"
    if kind == "pct":
        return f"{v * 100:.1f}%"
    if kind == "num":
        return f"{v:.3f}"
    if kind == "sec":
        return f"{v:.2f} s"
    if kind == "na":
        return f"{m['no_answer_correct']} / {m['n_unanswerable']}"
    return str(v)


def mark(ok) -> str:
    return "✅" if ok else "⚠️" if ok is None else "❌"


def build_blocks(rows, per, got, m, checks, meta, info) -> list[tuple]:
    """The report as blocks: ('h', level, text) · ('p', text) · ('table', header, rows) · ('qa', dict)."""
    sysobj = (meta or {}).get("system") or {}
    met_n = sum(1 for v in m["targets_met"].values() if v)
    chk_n = sum(1 for c in checks if c["ok"])
    B = [("h", 1, "RAG API — 100 savollik test hisoboti (lex.uz)"),
         ("p", f"Run: **{info['run_id']}** · {info['started']} → {info['finished']} · API: {info['base_url']} · "
               f"test toʻplami: {info['testset']} (sha256 {info['testset_sha'][:12]}…) · hakam: {info['judge']}"),
         ("h", 2, "Xulosa"),
         ("p", f"Metrikalar: **{met_n} / {len(TARGETS)}** maqsadga yetdi. API checklist: **{chk_n} / {len(checks)}** ✅. "
               f"Savollar: {m['n_total']} (javobi bor {m['n_answerable']}, javobsiz {m['n_unanswerable']}); "
               f"xato ulushi {fmt(m['error_rate'], 'pct')}; p50 {fmt(m['latency_p50_s'], 'sec')}, p95 {fmt(m['latency_p95_s'], 'sec')}."),
         ("table", ["Tizim", "Qiymat"], [[k, str(sysobj.get(k))] for k in ("pipeline_version", "llm_model", "embedding_model", "reranker",
                                                                         "index_version", "lex_snapshot_date", "dense_tau", "authority_prior") if k in sysobj]),
         ("h", 2, "1. Metrikalar (spetsifikatsiya §6)"),
         ("table", ["Qatlam", "Metrika", "Natija", "Maqsad", ""],
          [[layer, name, fmt(m.get(k), kind, m), target, mark(m["targets_met"].get(k))] for layer, name, k, target, kind in METRIC_ROWS]),
         ("p", f"Qoʻshimcha: barcha kutilgan moddalar top-5’da (koʻp moddali savollar) — {fmt(m['all_articles_found'], 'pct')}; "
               f"context precision hujjat darajasida — {fmt(m['context_precision_doc'], 'pct')} (asosiy: {m['context_precision_method']}); "
               f"correctness: hakam {fmt(m['answer_correctness_judge'], 'num')}, kalit faktlar {fmt(m['answer_correctness_facts'], 'num')}; "
               f"faithfulness (hakam, javob darajasida) {fmt(m['faithfulness_judge'], 'pct')}; keltirilgan manbalar: {m['citations_total']}; "
               f"javobi bor savolga «javob yoʻq» — {m['false_refusals']} ta."),
         ("h", 2, "2. API checklist (spetsifikatsiya §7)"),
         ("table", ["", "Talab", "Natija"], [[mark(c["ok"]), c["check"], c["detail"]] for c in checks]),
         ("h", 2, "3. Kategoriyalar boʻyicha"),
         ("table", ["Kategoriya", "Soni", "Hit@5 (modda)", "MRR", "Correctness", "No-answer", "Xato"],
          [[CAT_NAME.get(c, c), str(v["n"]), fmt(v["hit5_article"], "pct"), fmt(v["mrr"], "num"), fmt(v["correctness"], "num"),
            fmt(v["no_answer_ok"], "pct"), str(v["errors"])] for c, v in m["by_category"].items()]),
         ("h", 2, "4. Xatolar tahlili — har notoʻgʻri javob bitta sababga"),
         ("table", ["Sabab", "Soni", "Savollar"], [[c, str(len(ids)), ", ".join(ids)] for c, ids in sorted(m["causes"].items())] or [["—", "0", "notoʻgʻri javob yoʻq"]]),
         ("p", "retrieval — toʻgʻri modda top-5 kontekstda topilmagan; generatsiya — modda topilgan, lekin javob notoʻgʻri yoki toʻliq emas; "
               "manba — javob toʻgʻri, lekin kutilgan moddaga aniq havola yoʻq."),
         ("h", 2, "5. Kechikish va batch’lar"),
         ("table", ["Batch", "Vaqt (s)", "ok", "javobsiz", "xato"],
          [[b, str((x or {}).get("_client_seconds")), str(((x or {}).get("summary") or {}).get("ok")), str(((x or {}).get("summary") or {}).get("no_answer")),
            str(((x or {}).get("summary") or {}).get("error"))] for b, x in sorted(got.items())]),
         ("h", 2, "6. Barcha 100 savol va javoblar")]
    res_by = {r.get("id"): r for b in got.values() for r in (b or {}).get("results") or []}
    per_by = {p["id"]: p for p in per}
    for q in rows:
        B.append(("qa", {"q": q, "r": res_by.get(q["id"]) or {}, "p": per_by[q["id"]]}))
    B += [("h", 2, "7. Metodika"),
          ("p", "Hit@5 — kutilgan hujjat / modda (`expected_doc_id`, `expected_article`) top-5 `contexts` ichida; MRR — toʻgʻri moddaning "
                "birinchi oʻrni (N = javobi bor savollar). Context precision — top-5 dan savolga tegishli boʻlaklar ulushi (LLM-hakam; hakam "
                "boʻlmasa — kutilgan hujjatdan boʻlganlar). Answer correctness 0/1/2 — ikki bahoning **kichigi**: (a) LLM-hakam "
                "kutilgan javobning asosiy faktlarini sanab, har birini tizim javobida tekshiradi (mavzu boshqa yoki zid boʻlsa — 0; "
                "hamma fakt bor — 2; bir qismi — 1); (b) test toʻplamidagi kalit faktlar (hammasi bor — 2, bir qismi — 1, yoʻq — 0). "
                "Hakamning yaxlit bahosi (8-noyabr, birinchi versiya) notoʻgʻri mavzudagi silliq javoblarga ham 2 qoʻygan edi."),
          ("p", "Faithfulness — javobdagi har bir daʼvo (gap) oʻzi havola qilgan kontekst bilan solishtiriladi: gapdagi har bir son kontekstda "
                "boʻlishi va mazmunli soʻzlarining kamida 50% i kontekstda uchrashi kerak (rus javoblari — tekshirilgan oʻzbekcha asli boʻyicha). "
                "Citation accuracy — havola `contexts` ichida, `quote` kontekst matnidan aynan olingan va shu havolali gap manba bilan tasdiqlanadi. "
                "Toʻqilgan manba — `contexts` da yoʻq, URL lex.uz hujjatiga mos emas yoki korpusda yoʻq hujjat. Eskirgan norma — `doc_status` "
                f"«amalda» emas yoki hujjatning yangi nusxasi bor ({info['corpus']})."),
          ("p", f"Hakam: {info['judge']}. Agar hakam tekshirilayotgan model bilan bir xil boʻlsa, uning bahosi oʻziga nisbatan yumshoqroq "
                "boʻlishi mumkin — shuning uchun kalit faktlar bahosi ham alohida koʻrsatilgan. Xom maʼlumot: batches/*.json, judge.jsonl, "
                "results.csv, metrics.json, checks.json.")]
    return B


def md_inline(t: str) -> str:
    return t


def render_md(B) -> str:
    out = []
    for b in B:
        if b[0] == "h":
            out.append("#" * b[1] + " " + b[2] + "\n")
        elif b[0] == "p":
            out.append(b[1] + "\n")
        elif b[0] == "table":
            out.append("| " + " | ".join(b[1]) + " |\n|" + "---|" * len(b[1]))
            out += ["| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in row) + " |" for row in b[2]]
            out.append("")
        elif b[0] == "qa":
            out.append(qa_md(**b[1]))
    return "\n".join(out)


def qa_lines(q, r, p) -> dict:
    status = {"ok": "javob", "no_answer": "javob yoʻq", "error": "xato", "timeout": "timeout"}.get(r.get("status"), r.get("status") or "javob kelmadi")
    if q["answerable"]:
        verdict = f"correctness {p.get('correctness') if p.get('correctness') is not None else '—'}/2" + \
                  (f" (hakam {p['correct_judge']}, kalit faktlar {p.get('facts_found')}/{p.get('facts_total')})" if p.get("correct_judge") is not None else
                   f" (kalit faktlar {p.get('facts_found')}/{p.get('facts_total')})") + \
                  f" · modda top-5: {'ha, ' + str(p.get('rank')) + '-oʻrin' if p.get('hit_article') else 'yoʻq'}" + \
                  f" · daʼvolar manbada: {p['claims_supported']}/{p['claims']}"
    else:
        verdict = "toʻgʻri: «javob yoʻq»" if p.get("refused_ok") else "❌ javobsiz savolga javob berildi"
    if p.get("cause"):
        verdict += f" · sabab: {p['cause']}"
    head = f"{q['id']} · {CAT_NAME.get(q['category'], q['category'])} · {q['batch']} · {status}" + \
           (f" · {p['total_ms'] / 1000:.1f} s" if isinstance(p.get("total_ms"), (int, float)) else "")
    exp_src = ", ".join(f"lex:{d} {a}-modda" for d, a in q["exp_pairs"]) or "—"
    cites = []
    for c in r.get("citations") or []:
        acc = next((x for x in p["citations"] if x["ref"] == c.get("ref")), {})
        cites.append(f"[{c.get('ref')}] {c.get('doc_title')}, {c.get('article') or '—'} ({c.get('doc_status')}, {c.get('edition_date')}) — {c.get('url')}"
                     f" {'✓' if acc.get('accurate') else '✗'}\n    «{(c.get('quote') or '')[:300]}»")
    return {"head": head, "question": q["question"], "expected": q["expected_answer"] or "— (javobi yoʻq savol)", "exp_src": exp_src,
            "answer": r.get("answer") or (f"xato: {(r.get('error') or {}).get('code')} — {(r.get('error') or {}).get('message')}" if r.get("error") else "—"),
            "answer_uz": (r.get("debug") or {}).get("answer_uz"), "cites": cites, "verdict": verdict,
            "judge": (p.get("judge") or {}).get("reason") if p.get("judge") else None,
            "ctx": ", ".join(f"{c.get('rank')}. {c.get('doc_title', '')[:40]} {c.get('article') or ''}" for c in (r.get("contexts") or [])[:5])}


def qa_md(q, r, p) -> str:
    L = qa_lines(q, r, p)
    s = [f"### {L['head']}", f"**Savol:** {L['question']}  ", f"**Kutilgan javob:** {L['expected']}  ", f"**Kutilgan manba:** {L['exp_src']}  ",
         f"**Tizim javobi:** {L['answer']}  "]
    if L["answer_uz"]:
        s.append(f"**Tekshirilgan asli (oʻzbekcha):** {L['answer_uz']}  ")
    if L["cites"]:
        s.append("**Manbalar:**\n" + "\n".join("- " + c.replace("\n    ", "  \n  ") for c in L["cites"]))
    s.append(f"**Top-5 kontekst:** {L['ctx'] or '—'}  ")
    s.append(f"**Baho:** {L['verdict']}" + (f"  \n**Hakam:** {L['judge']}" if L["judge"] else ""))
    return "\n".join(s) + "\n"


CSS = """
:root{--bg:#fbfaf6;--fg:#1d2420;--muted:#5b675f;--line:#dcd8cc;--gold:#9a7417;--ok:#1f7a4d;--bad:#b3261e;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#0f1412;--fg:#e8ece9;--muted:#9fb0a6;--line:#2c3631;--gold:#e0b45c;--ok:#5fd39a;--bad:#ff8a80;--card:#151c19}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 16px 80px}h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:36px 0 10px;
padding-bottom:6px;border-bottom:1px solid var(--line)}h3{font-size:15px;margin:0 0 8px;color:var(--gold)}p{margin:8px 0}
table{width:100%;border-collapse:collapse;margin:10px 0 4px;font-size:14px;display:block;overflow-x:auto}th,td{text-align:left;
padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
.qa{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0;break-inside:avoid}
.qa dl{display:grid;grid-template-columns:150px 1fr;gap:4px 12px;margin:0}.qa dt{color:var(--muted)}.qa dd{margin:0}
.qa ul{margin:0;padding-left:18px}.q{font-weight:600}.muted{color:var(--muted)}a{color:var(--gold)}
@media (max-width:640px){.qa dl{grid-template-columns:1fr}.qa dt{margin-top:6px}}@media print{body{background:#fff;color:#000}.qa{break-inside:avoid}}
"""


def render_html(B, title: str) -> str:
    esc = html.escape
    bold = lambda t: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(t))
    out = [f"<!doctype html><html lang='uz'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{esc(title)}</title><style>{CSS}</style></head><body><main>"]
    for b in B:
        if b[0] == "h":
            out.append(f"<h{b[1]}>{esc(b[2])}</h{b[1]}>")
        elif b[0] == "p":
            out.append(f"<p>{bold(b[1])}</p>")
        elif b[0] == "table":
            out.append("<table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in b[1]) + "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{esc(str(c))}</td>" for c in row) + "</tr>" for row in b[2]) + "</tbody></table>")
        elif b[0] == "qa":
            L = qa_lines(**b[1])
            link = lambda c: re.sub(r"(https?://\S+)", r"<a href='\1'>\1</a>", esc(c)).replace("\n    ", "<br><span class='muted'>") + ("</span>" if "\n    " in c else "")
            rows = [("Savol", f"<span class='q'>{esc(L['question'])}</span>"), ("Kutilgan javob", esc(L["expected"])),
                    ("Kutilgan manba", esc(L["exp_src"])), ("Tizim javobi", esc(L["answer"]))]
            if L["answer_uz"]:
                rows.append(("Asli (oʻzbekcha)", esc(L["answer_uz"])))
            if L["cites"]:
                rows.append(("Manbalar", "<ul>" + "".join(f"<li>{link(c)}</li>" for c in L["cites"]) + "</ul>"))
            rows.append(("Top-5 kontekst", esc(L["ctx"] or "—")))
            rows.append(("Baho", esc(L["verdict"]) + (f"<br><span class='muted'>Hakam: {esc(L['judge'])}</span>" if L["judge"] else "")))
            out.append(f"<section class='qa'><h3>{esc(L['head'])}</h3><dl>" + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + "</dl></section>")
    out.append("</main></body></html>")
    return "\n".join(out)


def render_docx(B, path: Path) -> str | None:
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
    except ImportError:
        return "python-docx oʻrnatilmagan — .docx yaratilmadi (pip install python-docx)"
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10)

    def para(text, bold_all=False):
        p = doc.add_paragraph()
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
            run = p.add_run(part)
            run.bold = bold_all or i % 2 == 1
        return p

    for b in B:
        if b[0] == "h":
            doc.add_heading(b[2], level=min(b[1], 3))
        elif b[0] == "p":
            para(b[1])
        elif b[0] == "table":
            t = doc.add_table(rows=1, cols=len(b[1]))
            t.style = "Light Grid Accent 1"
            for i, h in enumerate(b[1]):
                t.rows[0].cells[i].text = h
            for row in b[2]:
                cells = t.add_row().cells
                for i, c in enumerate(row):
                    cells[i].text = str(c)
        elif b[0] == "qa":
            L = qa_lines(**b[1])
            h = doc.add_heading(L["head"], level=3)
            for run in h.runs:
                run.font.color.rgb = RGBColor(0x9A, 0x74, 0x17)
            for k, v in (("Savol", L["question"]), ("Kutilgan javob", L["expected"]), ("Kutilgan manba", L["exp_src"]),
                         ("Tizim javobi", L["answer"]), ("Asli (oʻzbekcha)", L["answer_uz"])):
                if v:
                    p = doc.add_paragraph()
                    p.add_run(f"{k}: ").bold = True
                    p.add_run(v)
            for c in L["cites"]:
                doc.add_paragraph(c.replace("\n    ", "\n"), style="List Bullet")
            p = doc.add_paragraph()
            p.add_run("Baho: ").bold = True
            p.add_run(L["verdict"] + (f"\nHakam: {L['judge']}" if L["judge"] else ""))
    doc.save(path)
    return None


def write_outputs(out: Path, rows, per, got, m, checks, meta, info) -> None:
    (out / "metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
    res_by = {r.get("id"): r for b in got.values() for r in (b or {}).get("results") or []}
    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "batch", "category", "question", "expected_answer", "expected_doc_id", "expected_article", "answerable",
                    "status", "answer", "citations", "hit5_doc", "hit5_article", "rank", "correctness", "correct_judge", "facts",
                    "claims_supported", "citations_accurate", "fabricated", "outdated", "cause", "total_ms"])
        for q in rows:
            p, r = next(x for x in per if x["id"] == q["id"]), res_by.get(q["id"]) or {}
            w.writerow([q["id"], q["batch"], q["category"], q["question"], q["expected_answer"], q["expected_doc_id"], q["expected_article"],
                        q["answerable"], p["status"], r.get("answer") or "",
                        " | ".join(f"[{c.get('ref')}] {c.get('doc_id')} {c.get('article')}" for c in r.get("citations") or []),
                        p.get("hit_doc"), p.get("hit_article"), p.get("rank"), p.get("correctness"), p.get("correct_judge"),
                        f"{p.get('facts_found')}/{p.get('facts_total')}" if q["answerable"] else "",
                        f"{p['claims_supported']}/{p['claims']}", f"{sum(c['accurate'] for c in p['citations'])}/{len(p['citations'])}",
                        len(p["fabricated"]), len(p["outdated"]), p.get("cause") or "", p.get("total_ms")])
    B = build_blocks(rows, per, got, m, checks, meta, info)
    title = f"RAG API test — {info['run_id']}"
    (out / "HISOBOT.md").write_text(render_md(B), encoding="utf-8")
    (out / "HISOBOT.html").write_text(render_html(B, title), encoding="utf-8")
    why = render_docx(B, out / "HISOBOT.docx")
    if why:
        log("  " + why)


# =========================================================================== main

def read_env_key() -> str | None:
    if os.environ.get("MODDA_API_KEY"):
        return os.environ["MODDA_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("MODDA_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'") or None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--api-key", default=None, help="default: MODDA_API_KEY (env or .env)")
    ap.add_argument("--testset", default=str(ROOT / "data" / "testset" / "test100.csv"))
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--judge", default="auto", help="auto | none | cache (with --rescore: the saved verdicts) | <ollama model>")
    ap.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    ap.add_argument("--db", default=None, help="SQLite corpus for the local checks (default: the project's)")
    ap.add_argument("--skip-checks", action="store_true", help="only the 100 questions, no API checklist")
    ap.add_argument("--rescore", default=None, help="a previous run folder: score its saved batches again (no API calls)")
    a = ap.parse_args()

    testset = Path(a.testset)
    rows = load_testset(testset)
    started = now()
    if a.rescore:
        out = Path(a.rescore)
        prev = json.loads((out / "run.json").read_text(encoding="utf-8"))
        run_id, base_url = prev["run_id"], prev["base_url"]
        got = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((out / "batches").glob("b*.json"))}
        checks = json.loads((out / "checks.json").read_text(encoding="utf-8")) if (out / "checks.json").exists() else []
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8")) if (out / "meta.json").exists() else {}
        started = prev.get("started", started)
    else:
        run_id = a.run_id or f"eval-{datetime.now(TZ):%Y-%m-%d-%H%M}"
        out = Path(a.out or ROOT / "data" / "reports" / "rag100" / run_id)
        out.mkdir(parents=True, exist_ok=True)
        base_url = a.base_url
        api = Api(base_url, a.api_key or read_env_key())
        log(f"Run {run_id} → {out}")
        st, health, _, _ = api.call("GET", "/v1/health")
        (out / "health.json").write_text(json.dumps(health, ensure_ascii=False, indent=1), encoding="utf-8")
        if st not in (200, 503):
            log(f"❌ {base_url}/v1/health → HTTP {st}: {health}. Server ishlayaptimi?")
            return 2
        st, meta, _, _ = api.call("GET", "/v1/meta")
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        if st != 200:
            log(f"❌ /v1/meta → HTTP {st}: {meta}" + (" — API kaliti kerak (--api-key yoki .env MODDA_API_KEY)" if st in (401, 403) else ""))
            return 2
        (out / "run.json").write_text(json.dumps({"run_id": run_id, "base_url": base_url, "started": started}, ensure_ascii=False), encoding="utf-8")
        checks: list = []
        if not a.skip_checks:
            log("API checklist (§7) — oldin:")
            checks_before(api, checks, run_id)
        log(f"100 savol, {len({r['batch'] for r in rows})} batch:")
        sent, got = run_batches(api, rows, run_id, out)
        if not a.skip_checks:
            log("API checklist (§7) — keyin:")
            checks_after(api, checks, rows, sent, got, run_id)
        (out / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.judge == "cache":
        if not a.rescore or not (out / "judge.jsonl").exists():
            log("❌ --judge cache faqat --rescore bilan va papkada judge.jsonl boʻlsa ishlaydi")
            return 2
        judge = CachedJudge(out / "judge.jsonl")
    else:
        judge = Judge.pick(a.ollama_url, a.judge, ((meta or {}).get("system") or {}).get("llm_model"))
    corpus = Corpus.open(a.db)
    log(f"Baholash: hakam — {judge.model or 'yoʻq (kalit faktlar)'}; {corpus.note}")
    per, m = score(rows, got, judge, corpus, out)
    sys_llm = ((meta or {}).get("system") or {}).get("llm_model")
    info = {"run_id": run_id, "started": started, "finished": now(), "base_url": base_url, "testset": testset.name,
            "testset_sha": hashlib.sha256(testset.read_bytes()).hexdigest(),
            "judge": (f"{judge.model}" + (" (tekshirilayotgan model bilan bir xil)" if judge.model == sys_llm else " (boshqa model)")) if judge.model else "yoʻq — kalit faktlar",
            "corpus": corpus.note}
    write_outputs(out, rows, per, got, m, checks, meta, info)
    log("Natija:")
    for layer, name, k, target, kind in METRIC_ROWS:
        log(f"  {mark(m['targets_met'].get(k))} {name}: {fmt(m.get(k), kind, m)} (maqsad {target})")
    log(f"Hisobot: {out / 'HISOBOT.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
