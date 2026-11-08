"""API /v1 — «RAG API — test spetsifikatsiyasi (lex.uz)» (3-noyabr 2026), without any web framework.

  POST /v1/rag/batch               1–10 questions → answers, citations, contexts (sync; > SYNC_S → 202 + polling)
  GET  /v1/rag/batch/{batch_id}    a stored batch (processing → completed / failed); kept on disk, never deleted
  POST /v1/rag/query               one question (debug)
  GET  /v1/meta                    system versions: model, embedding, index, Lex.uz snapshot date
  GET  /v1/health                  is the service working

`api.py` maps these to HTTP. Rules of the spec, and how they are met here:
  • auth — `Authorization: Bearer <MODDA_API_KEY>` (.env); 401 without it, 403 with a wrong one;
  • batch 1–10 items, unique ids, question 1–2000 chars → otherwise 400 (whole batch);
  • rate limit — 1 batch per second per key → 429 + Retry-After;
  • idempotency — the same batch_id with the same content returns the saved result (not recomputed); with other
    content → 409. Results are saved in data/v1/batches/<batch_id>.json;
  • an error in one question never breaks the batch: that item gets status "error" and an `error` object;
  • temperature/seed go to the LLM (Ollama options); retrieval is deterministic — same question, same sources;
  • every response carries the `system` object.
Answers are always produced and verified in Uzbek Latin (the corpus language). A Russian question is first
translated into Uzbek for retrieval (debug.rewritten_query); the verified answer is then translated back into
Russian (debug.answer_uz keeps the verified original). Uzbek Cyrillic answers are transliterated. Quotes stay
verbatim from the Lex.uz source.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone

from . import __version__, service
from .config import ROOT, get_settings
from .lexparse import label_display
from .llm import Ollama, OllamaError
from .pipeline import _iso, best_quote, snapshot_date
from .rag import fetch_contexts
from .store import Hit
from .textnorm import has_cyrillic, lat_to_cyr

S = get_settings()
TZ = timezone(timedelta(hours=5))                     # Asia/Tashkent, as in the spec's examples
MAX_ITEMS, MAX_CHARS = 10, 2000
SYNC_S = float(os.environ.get("MODDA_V1_SYNC_S", "110"))      # spec: a batch ≤ 120 s in sync mode, else 202
LLM_TIMEOUT_S = float(os.environ.get("MODDA_V1_LLM_TIMEOUT", "90"))
STORE = ROOT / "data" / "v1" / "batches"
LANGS = {"uz-Latn", "uz-Cyrl", "ru"}
DOC_TYPE = {"constitution": "konstitutsiya", "code": "kodeks", "law": "qonun", "decree": "farmon",
            "resolution": "qaror", "order": "buyruq", "other": "boshqa"}
NO_ANSWER_TEXT = {"uz-Latn": "Lex.uz maʼlumotlari asosida ishonchli javob topilmadi.",
                  "uz-Cyrl": "Lex.uz маълумотлари асосида ишончли жавоб топилмади.",
                  "ru": "Надёжный ответ на основе данных Lex.uz не найден."}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


# --------------------------------------------------------------------------- auth, rate limit

def api_key() -> str:
    return os.environ.get("MODDA_API_KEY", "").strip()


def check_auth(header: str | None) -> None:
    key = api_key()
    if not key:
        return                                        # no key configured: open (local development only)
    if not header or not header.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHORIZED", "Authorization: Bearer <API_KEY> sarlavhasi kerak")
    if not _same(header[7:].strip(), key):
        raise ApiError(403, "FORBIDDEN", "API kaliti notoʻgʻri")


def _same(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


_last_batch: dict[str, float] = {}
_rl_lock = threading.Lock()


def rate_limit(header: str | None) -> None:
    """At most one batch per second per key (spec §2)."""
    who = hashlib.sha256((header or "").encode()).hexdigest()[:16]
    with _rl_lock:
        now = time.monotonic()
        wait = 1.0 - (now - _last_batch.get(who, -10.0))
        if wait > 0:
            raise ApiError(429, "RATE_LIMITED", "Kamida 1 soniyada bitta batch", {"Retry-After": str(max(1, round(wait + 0.49)))})
        _last_batch[who] = now


# --------------------------------------------------------------------------- system / meta / health

_sys_cache: dict = {}


def _git() -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def system() -> dict:
    if "system" not in _sys_cache:
        con = service._con()
        try:
            snap = snapshot_date(con)
            chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        finally:
            con.close()
        git = _git()
        _sys_cache["system"] = {
            "pipeline_version": f"{__version__}+{git}" if git else __version__,
            "llm_model": S.llm_model,
            "embedding_model": S.embed_model,
            "reranker": "cross-encoder" if os.environ.get("RERANKER", "off").lower() in ("on", "1", "true") else None,
            "index_version": f"lex-idx-{snap or 'unknown'}-{S.collection}-{chunks}",
            "lex_snapshot_date": snap,
            "retrieval": "hybrid bge-m3 dense + BM25, RRF",
            "dense_tau": float(os.environ["DENSE_TAU"]) if os.environ.get("DENSE_TAU") else None,
            "authority_prior": os.environ.get("AUTHORITY_PRIOR", "off").lower() in ("on", "1", "true"),
        }
    return dict(_sys_cache["system"])


def meta() -> dict:
    out = {"system": system(), "api_version": "v1",
           "limits": {"items_per_batch": MAX_ITEMS, "question_chars": MAX_CHARS, "sync_seconds": SYNC_S,
                      "rate_limit": "1 batch/s", "result_retention_days": "≥ 30 (data/v1/batches, oʻchirilmaydi)"},
           "languages": sorted(LANGS), "auth": "Bearer" if api_key() else "oʻchiq (MODDA_API_KEY berilmagan)"}
    try:
        h = service.health()
        out["corpus"] = {k: h.get(k) for k in ("articles", "chunks", "dense_indexed", "sparse_only") if k in h}
        from .versions import superseded
        con = service._con()
        try:
            out["corpus"]["superseded_documents"] = len(superseded(con))
        finally:
            con.close()
    except Exception as exc:
        out["corpus"] = {"error": str(exc)[:200]}
    out["notes"] = ["Korpus bitta snapshot: options.as_of_date qabul qilinadi va javobda qaytariladi, lekin tahrir "
                    "sanasi boʻyicha tanlov qilinmaydi — bir aktning eski nusxalari qidiruvdan chiqariladi (versions.py).",
                    "Javob oʻzbek lotin tilida tekshiriladi; ru — tekshirilgan javobning tarjimasi, uz-Cyrl — transliteratsiya."]
    return out


def health() -> dict:
    h = service.health()
    return {"status": "ok" if h.get("ready") else "degraded", "time": _now(),
            "services": h.get("services"), "chunks": h.get("chunks"), "dense_indexed": h.get("dense_indexed")}


# --------------------------------------------------------------------------- validation

def validate_batch(body) -> dict:
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "JSON obyekt kerak")
    for f in ("run_id", "batch_id"):
        if not isinstance(body.get(f), str) or not body[f].strip():
            raise ApiError(400, "BAD_REQUEST", f"«{f}» majburiy (string)")
    if not re.fullmatch(r"[\w.:\-]{1,128}", body["batch_id"]):
        raise ApiError(400, "BAD_REQUEST", "batch_id: harf, raqam, «-», «_», «.», «:» (≤ 128 belgi)")
    items = body.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ApiError(400, "BAD_REQUEST", f"items: 1–{MAX_ITEMS} ta savol (keldi: {len(items) if isinstance(items, list) else '—'})")
    ids = []
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str) or not it["id"].strip():
            raise ApiError(400, "BAD_REQUEST", "har bir item’da «id» (string) boʻlishi kerak")
        q = it.get("question")
        if not isinstance(q, str) or not q.strip():
            raise ApiError(400, "BAD_REQUEST", f"{it['id']}: «question» boʻsh")
        if len(q) > MAX_CHARS:
            raise ApiError(400, "BAD_REQUEST", f"{it['id']}: savol {MAX_CHARS} belgidan uzun")
        ids.append(it["id"])
    if len(set(ids)) != len(ids):
        raise ApiError(400, "BAD_REQUEST", "takroriy id: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    options(body.get("options"))                      # raises 400 on bad options
    return body


def options(o) -> dict:
    o = o or {}
    if not isinstance(o, dict):
        raise ApiError(400, "BAD_REQUEST", "options — obyekt boʻlishi kerak")
    top_k = o.get("top_k", 5)
    if not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ApiError(400, "BAD_REQUEST", "options.top_k: 1–20")
    temp = o.get("temperature", 0)
    if not isinstance(temp, (int, float)) or not 0 <= temp <= 2:
        raise ApiError(400, "BAD_REQUEST", "options.temperature: 0–2")
    seed = o.get("seed")
    if seed is not None and not isinstance(seed, int):
        raise ApiError(400, "BAD_REQUEST", "options.seed: butun son")
    lang = o.get("answer_language", "auto")
    if lang != "auto" and lang not in LANGS:
        raise ApiError(400, "BAD_REQUEST", f"options.answer_language: auto, {', '.join(sorted(LANGS))}")
    return {"top_k": top_k, "temperature": float(temp), "seed": seed, "answer_language": lang,
            "return_contexts": o.get("return_contexts", True) is not False, "return_debug": bool(o.get("return_debug", False)),
            "as_of_date": o.get("as_of_date")}


def request_hash(body: dict) -> str:
    keep = {"run_id": body.get("run_id"), "options": body.get("options") or {},
            "items": [{k: it.get(k) for k in ("id", "question", "language")} for it in body["items"]]}
    return hashlib.sha256(json.dumps(keep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# --------------------------------------------------------------------------- language

_RU_WORDS = {"какой", "какая", "какое", "какие", "каков", "какова", "каково", "что", "как", "сколько", "ли", "для", "при",
             "на", "в", "и", "по", "с", "срок", "является", "можно", "кто", "где", "когда", "или", "если", "это", "закон",
             "кодекс", "кодексом", "статья", "статье", "права", "право", "лет", "года", "размер", "ставка"}


def detect_language(text: str) -> str:
    if not has_cyrillic(text):
        return "uz-Latn"
    low = text.lower()
    if re.search("[ўқғҳ]", low):
        return "uz-Cyrl"
    if re.search("[ыщ]", low) or set(re.findall(r"[а-яё]+", low)) & _RU_WORDS:
        return "ru"
    return "uz-Cyrl"


def _translate(llm: Ollama, text: str, to: str) -> str:
    if to == "uz":
        prompt = ("Quyidagi savolni oʻzbek tiliga, lotin yozuvida tarjima qil. Yuridik atamalarni Oʻzbekiston qonunchiligidagidek "
                  "ishlat (masalan: трудовой отпуск — mehnat taʼtili, НДС — qoʻshilgan qiymat soligʻi, брачный возраст — nikoh yoshi). "
                  "Faqat tarjimani yoz, boshqa hech narsa qoʻshma.\n\n")
    else:
        prompt = ("Переведи текст на русский язык. Сохрани ссылки в квадратных скобках вида [1] на тех же местах и все числа "
                  "без изменений. Ничего не добавляй и не объясняй — только перевод.\n\n")
    out, _ = llm.chat(S.llm_model, [{"role": "user", "content": prompt + text}], num_predict=600)
    return out.strip().strip("«»\"").strip()


# --------------------------------------------------------------------------- one question

def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _err(code: str, message: str, retryable: bool) -> dict:
    return {"code": code, "message": message[:300], "retryable": retryable}


def _classify(exc: Exception) -> dict:
    msg = str(exc)
    low = msg.lower()
    if isinstance(exc, OllamaError) or "ollama" in low:
        if "javob bermadi" in low or "timeout" in low or "timed out" in low:
            return _err("LLM_TIMEOUT", msg, True)
        return _err("LLM_ERROR", msg, True)
    if "qdrant" in low or "collection" in low or "connection" in low:
        return _err("INDEX_UNAVAILABLE", msg, True)
    if "context" in low and "long" in low:
        return _err("CONTEXT_TOO_LONG", msg, False)
    return _err("RETRIEVAL_FAILED", f"{type(exc).__name__}: {msg}", True)


def answer_item(item: dict, opts: dict) -> dict:
    """One question → one `results[]` element of spec §4. Never raises."""
    t0 = time.perf_counter()
    qid, question = item["id"], item["question"].strip()
    base = {"id": qid, "status": "error", "answer": None, "answer_language": None, "no_answer": False,
            "confidence": None, "citations": [], "contexts": [], "error": None}
    lang = item.get("language") or detect_language(question)
    if lang not in LANGS:
        return {**base, "error": _err("INVALID_LANGUAGE", f"language «{lang}»: faqat {', '.join(sorted(LANGS))}", False),
                "timing": {"total_ms": round((time.perf_counter() - t0) * 1000)}}
    out_lang = lang if opts["answer_language"] == "auto" else opts["answer_language"]
    gen_opts = {"temperature": opts["temperature"], **({"seed": opts["seed"]} if opts["seed"] is not None else {})}
    llm = Ollama(S.ollama_url, keep_alive=service.KEEP_ALIVE, timeout=LLM_TIMEOUT_S, options=gen_opts)
    debug: dict = {"language_detected": lang}
    translate_ms = 0.0
    try:
        q_uz = question
        if lang == "ru":                              # the corpus is Uzbek: retrieve with an Uzbek question
            t = time.perf_counter()
            q_uz = _translate(llm, question, "uz")
            translate_ms += (time.perf_counter() - t) * 1000
        events: list[dict] = []
        res = service.run(q_uz, emit=events.append, k=opts["top_k"], options=gen_opts, llm_timeout=LLM_TIMEOUT_S)
    except Exception as exc:                          # one question's failure stays in that question
        e = _classify(exc)
        return {**base, "status": "timeout" if e["code"] == "LLM_TIMEOUT" else "error", "error": e, "debug": debug,
                "timing": {"total_ms": round((time.perf_counter() - t0) * 1000)}}

    ev = {e["type"]: e.get("data") or {} for e in events}
    cands = (ev.get("retrieval.completed") or {}).get("candidates") or []
    gen = ev.get("generation.completed") or {}
    rq = ev.get("query.analyzed") or {}
    gate = (ev.get("ranking.completed") or {}).get("gate")

    # contexts: the top-k chunks the answer was written from (also for «no answer»: retrieval is still measured)
    contexts, by_id = [], {}
    if cands:
        con = service._con()
        try:
            ctxs = {c.chunk_id: c for c in fetch_contexts(con, [Hit(c["chunk_id"], 0.0, {}) for c in cands])}
        finally:
            con.close()
        used = set((res.get("sources") or {}).keys())
        for rank, c in enumerate(cands[:opts["top_k"]], start=1):
            ctx = ctxs.get(c["chunk_id"])
            if not ctx:
                continue
            by_id[c["chunk_id"]] = ctx
            m = ctx.meta
            contexts.append({
                "rank": rank, "chunk_id": c["chunk_id"], "doc_id": f"lex:{m.get('doc_id')}", "doc_title": m.get("doc_title"),
                "article": _article(m), "header": ctx.header, "text": ctx.text,
                "retrieval_score": c.get("dense_score") if c.get("dense_score") is not None else c.get("score"),
                "rrf_score": c.get("score"), "bm25_score": c.get("sparse_score"), "rerank_score": None,
                "exact_reference": bool(c.get("exact")), "used_in_answer": c["chunk_id"] in used,
            })

    timing = {"retrieval_ms": (ev.get("embedding.completed") or {}).get("ms", 0) + (ev.get("retrieval.completed") or {}).get("ms", 0),
              "rerank_ms": None, "generation_ms": gen.get("ms"), "translate_ms": round(translate_ms) or None}
    usage = {"input_tokens": gen.get("prompt_tokens"), "output_tokens": gen.get("output_tokens")}
    debug.update({"rewritten_query": rq.get("query_form"), "question_uz": q_uz if lang == "ru" else None,
                  "route": rq.get("route"), "retrieved_total": len(cands), "dense_top": (ev.get("retrieval.completed") or {}).get("dense_top"),
                  "gate": gate, "request_id": res.get("request_id"),
                  "verification": {"failed": (ev.get("verification.completed") or {}).get("failed", [])},
                  "superseded_dropped": len((ev.get("retrieval.completed") or {}).get("superseded") or [])})

    if res.get("unknown"):
        result = {**base, "status": "no_answer", "answer": NO_ANSWER_TEXT[out_lang], "answer_language": out_lang,
                  "no_answer": True, "reason": res.get("reason")}
    else:
        refs: dict[str, int] = {}
        parts, citations = [], []
        for s in res.get("answer") or []:
            marks = []
            for cid in s.get("chunk_ids") or []:
                if cid not in by_id:
                    continue
                if cid not in refs:
                    refs[cid] = len(refs) + 1
                    ctx = by_id[cid]
                    m = ctx.meta
                    src = (res.get("sources") or {}).get(cid) or {}
                    citations.append({
                        "ref": refs[cid], "doc_id": f"lex:{m.get('doc_id')}", "doc_title": m.get("doc_title"),
                        "doc_type": DOC_TYPE.get(m.get("doc_type"), m.get("doc_type")), "url": m.get("source_url"),
                        "article": _article(m), "part": _part(m), "edition_date": _iso(m.get("version_date")),
                        "doc_status": "amalda", "stale": bool(src.get("stale")), "chunk_id": cid,
                        "quote": best_quote(s["text"], ctx.text),
                    })
                marks.append(f"[{refs[cid]}]")
            parts.append(s["text"].rstrip() + (" " + "".join(marks) if marks else ""))
        answer_uz = " ".join(parts)
        answer, lang_out = answer_uz, "uz-Latn"
        if out_lang == "uz-Cyrl":
            answer, lang_out = lat_to_cyr(answer_uz), "uz-Cyrl"
        elif out_lang == "ru":
            try:
                t = time.perf_counter()
                answer, lang_out = _translate(llm, answer_uz, "ru"), "ru"
                translate_ms += (time.perf_counter() - t) * 1000
                timing["translate_ms"] = round(translate_ms)
            except Exception as exc:                  # the verified Uzbek answer is still a correct answer
                debug["translation_error"] = str(exc)[:200]
        if lang_out != "uz-Latn":
            debug["answer_uz"] = answer_uz
        score = (res.get("score") or {}).get("score")
        result = {**base, "status": "ok", "answer": answer, "answer_language": lang_out, "no_answer": False,
                  "confidence": round(score / 100, 3) if isinstance(score, (int, float)) else None, "citations": citations}
    result["contexts"] = contexts if opts["return_contexts"] else []
    if opts["return_debug"]:
        result["debug"] = debug
    timing["total_ms"] = round((time.perf_counter() - t0) * 1000)
    result.update(timing=timing, usage=usage, error=None)
    return result


def _article(m: dict) -> str | None:
    if m.get("quality_flag") == "no-articles":
        return None
    label = label_display(m.get("article_label") or m.get("article_number") or "")
    return f"{label}-modda" if label else None


def _part(m: dict) -> str | None:
    p = (m.get("part") or "").strip()
    return p or None


# --------------------------------------------------------------------------- batches

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v1-batch")   # one GPU: one batch at a time
_running: dict[str, object] = {}
_lock = threading.Lock()


def _path(batch_id: str):
    safe = re.sub(r"[^\w.\-]", "_", batch_id)      # (no backslash inside an f-string: Python 3.10 on the laptop)
    return STORE / f"{safe}.json"


def _load(batch_id: str) -> dict | None:
    p = _path(batch_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _save(batch_id: str, rec: dict) -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    tmp = _path(batch_id).with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_path(batch_id))


def _retryable(r: dict) -> bool:
    return r.get("status") in ("error", "timeout") and bool((r.get("error") or {}).get("retryable"))


def _process(body: dict, h: str, previous: dict | None = None) -> dict:
    """previous: a saved result of the same batch — only its items with a retryable error are answered again."""
    opts = options(body.get("options"))
    received = _now()
    t0 = time.perf_counter()
    old = {r["id"]: r for r in (previous or {}).get("results", [])}
    results = [old[it["id"]] if it["id"] in old and not _retryable(old[it["id"]]) else answer_item(it, opts)
               for it in body["items"]]
    summary = {"total": len(results), "ok": sum(r["status"] == "ok" for r in results),
               "no_answer": sum(r["status"] == "no_answer" for r in results),
               "error": sum(r["status"] in ("error", "timeout") for r in results)}
    resp = {"run_id": body["run_id"], "batch_id": body["batch_id"], "batch_index": body.get("batch_index"),
            "total_batches": body.get("total_batches"), "status": "completed", "system": system(),
            "options": {k: v for k, v in opts.items()},
            "timing": {"received_at": received, "completed_at": _now(), "total_ms": round((time.perf_counter() - t0) * 1000)},
            "summary": summary, "results": results}
    _save(body["batch_id"], {"hash": h, "status": "completed", "response": resp})
    return resp


def submit_batch(body: dict) -> tuple[int, dict]:
    """Returns (HTTP status, body). Validation and idempotency first; then the batch runs on the single worker."""
    validate_batch(body)
    bid, h = body["batch_id"], request_hash(body)
    with _lock:
        old = _load(bid)
        if old:
            if old.get("hash") != h:
                raise ApiError(409, "CONFLICT", f"«{bid}» boshqa mazmun bilan yuborilgan — yangi batch_id bering")
            previous = old.get("response") if old.get("status") == "completed" else None
            if previous and not any(_retryable(r) for r in previous.get("results", [])):
                return 200, previous                  # idempotent: the saved result, not recomputed
            if old.get("status") == "failed":
                pass                                  # retry a failed batch
            elif bid in _running:
                return 202, {"batch_id": bid, "status": "processing"}
        else:
            previous = None
        _save(bid, {"hash": h, "status": "processing", "received_at": _now(), "previous": previous})
        fut = _pool.submit(_safe_process, body, h, previous)
        _running[bid] = fut
    try:
        return 200, fut.result(timeout=SYNC_S)
    except FutureTimeout:
        return 202, {"batch_id": bid, "status": "processing"}


def _safe_process(body: dict, h: str, previous: dict | None = None) -> dict:
    try:
        return _process(body, h, previous)
    except Exception as exc:                          # the whole batch failed (should not happen: items catch their errors)
        _save(body["batch_id"], {"hash": h, "status": "failed", "error": _classify(exc)})
        raise
    finally:
        with _lock:
            _running.pop(body["batch_id"], None)


def get_batch(batch_id: str) -> tuple[int, dict]:
    rec = _load(batch_id)
    if not rec:
        raise ApiError(404, "NOT_FOUND", f"«{batch_id}» topilmadi")
    if rec.get("status") == "completed":
        return 200, rec["response"]
    if rec.get("status") == "failed":
        return 200, {"batch_id": batch_id, "status": "failed", "error": rec.get("error")}
    if batch_id not in _running:                      # the server restarted while it was running
        return 200, {"batch_id": batch_id, "status": "failed",
                     "error": _err("INTERRUPTED", "server qayta ishga tushdi — batch’ni qayta yuboring", True)}
    return 200, {"batch_id": batch_id, "status": "processing"}


def query(body) -> dict:
    if not isinstance(body, dict) or not isinstance(body.get("question"), str) or not body["question"].strip():
        raise ApiError(400, "BAD_REQUEST", "«question» majburiy")
    if len(body["question"]) > MAX_CHARS:
        raise ApiError(400, "BAD_REQUEST", f"savol {MAX_CHARS} belgidan uzun")
    opts = options({"return_debug": True, **(body.get("options") or {})})
    item = {"id": body.get("id") or "q", "question": body["question"], "language": body.get("language")}
    fut = _pool.submit(answer_item, item, opts)        # same single worker as batches
    return {"system": system(), "result": fut.result()}
