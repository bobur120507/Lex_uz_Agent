"""Everything the website's HTTP API does, without any web framework.

`api.py` (FastAPI) and `devserver.py` (standard library only, a fallback when FastAPI cannot be installed)
are thin wrappers around these functions, so both serve exactly the same data.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

from . import library, modelinfo, projection
from .config import ROOT, get_settings
from .corpus import connect
from .llm import Ollama
from .pipeline import ask, snapshot_date
from .store import QdrantStore

S = get_settings()
TRACE_TTL, TRACE_MAX = 30 * 60, 50


class NotFound(LookupError):
    pass


class BadRequest(ValueError):
    pass


_reranker = None
_cache: dict = {}
_traces: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_lock = threading.Lock()


def _con():
    return connect(S.db_path, url=S.database_url or None)


def _store(timeout: float = 120.0) -> QdrantStore:
    return QdrantStore(S.qdrant_url, S.collection, S.embed_dim, timeout=timeout)


def _get_reranker():
    global _reranker
    if os.environ.get("RERANKER", "off").lower() in ("on", "1", "true") and _reranker is None:
        from .rerank import CrossEncoderReranker
        _reranker = CrossEncoderReranker()
    return _reranker


def _checked_at(con) -> str | None:
    if "checked_at" not in _cache:
        _cache["checked_at"] = snapshot_date(con)
    return _cache["checked_at"]


def _stale(con) -> set:
    try:
        from .rss import stale_doc_ids
        return stale_doc_ids(con, _checked_at(con))
    except Exception:
        return set()


def _keep_trace(trace: dict) -> None:
    rid = trace.get("request_id")
    if not rid:
        return
    with _lock:
        _traces[rid] = (time.time(), trace)
        now = time.time()
        for k in [k for k, (t, _) in _traces.items() if now - t > TRACE_TTL]:
            _traces.pop(k, None)
        while len(_traces) > TRACE_MAX:
            _traces.popitem(last=False)


def _trace(rid: str) -> dict:
    with _lock:
        item = _traces.get(rid)
    if not item or time.time() - item[0] > TRACE_TTL:
        raise NotFound("Soʻrov topilmadi yoki 30 daqiqadan eski")
    return item[1]


def check_question(question) -> str:
    q = (question or "").strip() if isinstance(question, str) else ""
    if not 2 <= len(q) <= 1000:
        raise BadRequest("Savol 2–1000 belgi boʻlishi kerak")
    return q


# --------------------------------------------------------------------------- endpoints

def run(question: str, emit=None) -> dict:
    con = _con()
    trace: dict = {}
    try:
        llm = Ollama(S.ollama_url)
        tau = os.environ.get("RERANK_TAU")
        return ask(con, _store(), llm, llm,
                   question=question, embed_model=S.embed_model, llm_model=S.llm_model, emit=emit, k=S.top_k,
                   reranker=_get_reranker(), tau=float(tau) if tau else None,
                   stale_ids=_stale(con), checked_at=_checked_at(con), trace=trace, diagnostics=True)
    finally:
        _keep_trace(trace)
        con.close()


HEALTH_TTL = 120          # seconds: the page polls /health; counting 183 k rows every time is wasteful


def _counts() -> dict:
    hit = _cache.get("counts")
    if hit and time.time() - hit[0] < HEALTH_TTL:
        return hit[1]
    con = _con()
    try:
        one = lambda sql: con.execute(sql).fetchone()[0]
        c = {"articles": one("SELECT COUNT(*) FROM articles"), "chunks": one("SELECT COUNT(*) FROM chunks"),
             "dense_indexed": one("SELECT COUNT(*) FROM chunks WHERE indexed = 1"),
             "sparse_only": one("SELECT COUNT(*) FROM chunks WHERE indexed = 2"), "checked_at": _checked_at(con)}
    finally:
        con.close()
    _cache["counts"] = (time.time(), c)
    return c


def health() -> dict:
    out = {"ok": True, **_counts(), "llm": S.llm_model, "embed": S.embed_model, "reranker": _reranker is not None}
    services = {}
    try:
        services["ollama"] = {"ok": True, "version": Ollama(S.ollama_url, timeout=3).version()}
    except Exception as exc:
        services["ollama"] = {"ok": False, "error": str(exc)[:120]}
    try:
        st = _store(timeout=3)
        services["qdrant"] = {"ok": True, "version": st.ping(), "points": st.count() if st.exists() else 0}
    except Exception as exc:
        services["qdrant"] = {"ok": False, "error": str(exc)[:120]}
    out["services"] = services
    out["ready"] = all(v["ok"] for v in services.values())
    return out


def model_info() -> dict:
    llm = Ollama(S.ollama_url, timeout=15)
    out = {}
    for role, name in (("embedding", S.embed_model), ("llm", S.llm_model)):
        key = f"card:{name}"
        if key not in _cache:
            try:
                _cache[key] = modelinfo.card(llm.show(name), name)
            except Exception as exc:
                out[role] = {"name": name, "error": str(exc)[:200]}
                continue
        out[role] = _cache[key]
    return out


def trace(rid: str) -> dict:
    return {k: v for k, v in _trace(rid).items() if k != "vector"}


def embedding(rid: str) -> dict:
    import numpy as np
    t = _trace(rid)
    vec = t.get("vector")
    if not vec:
        raise NotFound("Bu soʻrovda vektor yoʻq")
    v = np.asarray(vec, dtype=np.float32)
    out = {"request_id": rid, "model": t.get("embed_model"), "dim": len(vec), "dtype": "float32",
           "vector": vec, "norm": round(float(np.linalg.norm(v)), 6),
           "stats": {"min": round(float(v.min()), 6), "max": round(float(v.max()), 6), "mean": round(float(v.mean()), 6),
                     "std": round(float(v.std()), 6)},
           "embed_stats": t.get("embed_stats") or {}, "query_form": t.get("query_form")}
    cands = t.get("candidates") or []
    try:
        store = _store()
        cvecs = store.vectors([c["chunk_id"] for c in cands])
        proj = projection.get(store, ROOT / "data" / "projection")
        ids = [c["chunk_id"] for c in cands if c["chunk_id"] in cvecs]
        xyz = proj.apply([vec] + [cvecs[i] for i in ids])
        qn = v / (np.linalg.norm(v) or 1.0)
        by = {c["chunk_id"]: c for c in cands}
        out["projection"] = proj.info() | {"coordinates": dict(zip("xyz", (round(float(f), 5) for f in xyz[0])))}
        out["candidates"] = [{**{k: by[i].get(k) for k in ("chunk_id", "rank", "doc_title", "article_no", "doc_type")},
                              "cosine": round(float(qn @ (np.asarray(cvecs[i]) / (np.linalg.norm(cvecs[i]) or 1.0))), 5),
                              "xyz": [round(float(f), 5) for f in xyz[n + 1]]} for n, i in enumerate(ids)]
        out["reference_cloud"] = proj.cloud
    except Exception as exc:                            # the vector is still shown; projection reported unavailable
        out["projection"] = None
        out["projection_error"] = str(exc)[:200]
    return out


def chunk_context(chunk_id: str, n: int = 5) -> dict:
    con = _con()
    try:
        res = library.chunk_context(con, chunk_id, n)
    finally:
        con.close()
    if res is None:
        raise NotFound("Boʻlak topilmadi")
    return res


def article_context(article_id: str, n: int = 5) -> dict:
    con = _con()
    try:
        return library.article_context(con, article_id, n)
    except KeyError:
        raise NotFound("Modda topilmadi") from None
    finally:
        con.close()


def documents(q: str = "", limit: int = 20, doc_type: str | None = None) -> dict:
    con = _con()
    try:
        return {"q": q, "documents": library.search_documents(con, q, limit, doc_type)}
    finally:
        con.close()


def document(doc_id: str, offset: int = 0, limit: int = 20) -> dict:
    con = _con()
    try:
        return library.document_articles(con, doc_id, offset, limit)
    except KeyError:
        raise NotFound("Hujjat topilmadi") from None
    finally:
        con.close()


def web_dist():
    d = ROOT / os.environ.get("MODDA_WEB_DIST", "web/dist")
    return d if d.exists() else None
