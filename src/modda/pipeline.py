"""The whole question → answer path, reporting each real stage as an event (roadmap §12.4).

The same function serves `POST /ask` (events ignored) and `POST /ask/stream` (events sent as SSE),
so the website never has to guess which stage is running.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone

from . import sparse
from .lexparse import label_display
from .rag import Context, build_messages, fetch_contexts, parse_answer
from .router import lookup, route
from .store import Hit
from .textnorm import normalize_uz, to_query_form, tokenize

NUM_RE = re.compile(r"\d+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _iso(d: str | None) -> str | None:
    if not d:
        return None
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else d[:10]


def best_quote(sentence: str, source: str) -> str:
    """The source sentence that shares most words with the answer sentence (highlighted on the page)."""
    words = set(tokenize(sentence))
    cands = [s.strip() for s in re.split(r"(?<=[.;:])\s+|\n", source) if len(s.strip()) > 20]
    if not cands:
        return source[:200]
    best = max(cands, key=lambda c: len(words & set(tokenize(c))))
    return best.rstrip(".;:")


def verify(sentence: dict, ctx_by_id: dict[str, Context]) -> tuple[bool, str]:
    """Day-1 verifier: the sentence must cite a given source, and every number in it must occur there."""
    ids = [i for i in sentence["chunk_ids"] if i in ctx_by_id]
    if not ids:
        return False, "manba koʻrsatilmagan"
    src = " ".join(f"{ctx_by_id[i].header} {ctx_by_id[i].text}" for i in ids)
    missing = [n for n in NUM_RE.findall(sentence["text"]) if n not in NUM_RE.findall(src)]
    if missing:
        return False, f"manbada yoʻq son: {', '.join(missing)}"
    return True, "ok"


def source_payload(c: Context, stale_ids: set) -> dict:
    m = c.meta
    flat = m.get("quality_flag") == "no-articles"
    label = m.get("article_label") or m.get("article_number")
    return {
        "title": m.get("doc_title"), "doc_type": m.get("doc_type"), "doc_number": m.get("doc_number") or None,
        "adoption_date": _iso(m.get("doc_date")), "url": m.get("source_url"),
        "article_no": None if flat else label_display(label or ""), "article_title": m.get("article_title"),
        "chapter": m.get("chapter"), "text": c.text, "amendment_note": m.get("amendment_note"),
        "stale": str(m.get("doc_id")) in stale_ids,
    }


def ask(con, store, embedder, llm, *, question: str, embed_model: str, llm_model: str, emit=None,
        k: int = 5, candidates: int = 20, reranker=None, rerank_top: int = 10, tau: float | None = None,
        stale_ids: set | None = None, checked_at: str | None = None) -> dict:
    rid = uuid.uuid4().hex[:12]
    t_all = time.perf_counter()

    def ev(kind: str, data: dict):
        if emit:
            emit({"type": kind, "request_id": rid, "ts": _now(), "data": data})

    question = normalize_uz(question)[:1000]
    ev("query.received", {"question": question})

    # 01 understanding
    r = route(question)
    q = to_query_form(question)
    ev("query.analyzed", {"concepts": r.concepts or [], "route": r.kind,
                          "reference": {"document": r.document, "article": r.label} if r.kind == "exact" else None})

    # 02 embedding
    t = time.perf_counter()
    vec = embedder.embed(embed_model, [q])[0]
    ev("embedding.completed", {"model": embed_model, "dim": len(vec), "ms": round((time.perf_counter() - t) * 1000)})

    # 03 retrieval (exact reference first, then hybrid dense + BM25)
    ev("retrieval.started", {"mode": "hybrid", "exact": r.kind == "exact"})
    t = time.perf_counter()
    exact = lookup(con, r)
    n_cand = candidates if reranker else k
    hits = store.search_hybrid(vec, sparse.query_vector(q), n_cand)
    hits = [Hit(cid, 1.0, {}) for cid in exact] + [h for h in hits if h.chunk_id not in exact]
    ctx = fetch_contexts(con, hits[:max(n_cand, len(exact))])
    docs = {c.meta.get("doc_id") for c in ctx}
    ev("retrieval.completed", {
        "documents_found": len(docs), "chunks_retrieved": len(ctx), "ms": round((time.perf_counter() - t) * 1000),
        "candidates": [{"chunk_id": c.chunk_id, "doc_title": c.meta.get("doc_title"), "doc_type": c.meta.get("doc_type"),
                        "article_no": label_display(c.meta.get("article_label") or c.meta.get("article_number") or ""),
                        "article_title": c.meta.get("article_title"), "rank": c.n} for c in ctx],
    })

    def finish(answer: dict) -> dict:
        answer["checked_at"] = checked_at
        answer["request_id"] = rid
        answer["ms"] = round((time.perf_counter() - t_all) * 1000)
        ev("answer.completed", answer)
        return answer

    unknown = {"unknown": True, "answer": [], "sources": {}}
    if not ctx:
        ev("ranking.completed", {"reranker": False, "selected": [], "rejected": []})
        return finish(unknown)

    # 04 ranking
    if reranker:
        from .rerank import rerank
        pool = ctx[:rerank_top]
        exact_ctx = [c for c in pool if c.chunk_id in exact]
        ranked, scores, secs = rerank(reranker, q, pool, top_n=k)
        for c in exact_ctx:                                # an explicit reference is never dropped
            if c not in ranked:
                ranked = [c] + ranked[:k - 1]
        selected = ranked
        top = scores[0] if scores else 0.0
        ev("ranking.completed", {"reranker": True, "model": getattr(reranker, "name", "?"), "top_score": round(top, 4),
                                 "tau": tau, "ms": round(secs * 1000), "selected": [c.chunk_id for c in selected],
                                 "rejected": [c.chunk_id for c in ctx if c not in selected]})
        if tau is not None and top < tau and not exact:
            return finish(unknown)                         # nothing relevant enough: «Bilmayman», no LLM call
    else:
        selected = ctx[:max(k, len(exact))]
        ev("ranking.completed", {"reranker": False, "selected": [c.chunk_id for c in selected],
                                 "rejected": [c.chunk_id for c in ctx if c not in selected]})
    for n, c in enumerate(selected, start=1):
        c.n = n

    # 05 context
    ev("context.completed", {"chunk_ids": [c.chunk_id for c in selected]})

    # 06 generation
    ev("generation.started", {"model": llm_model})
    raw, secs = llm.chat(llm_model, build_messages(question, selected))
    ans = parse_answer(question, raw, selected)

    # 07 verification
    by_id = {c.chunk_id: c for c in selected}
    kept, failed = [], []
    for s in ans.sentences:
        ok, why = verify(s, by_id)
        (kept if ok else failed).append({**s, "why": why})
    ev("verification.completed", {"verified": [i for s in kept for i in s["chunk_ids"]],
                                  "failed": [{"text": s["text"][:80], "why": s["why"]} for s in failed],
                                  "llm_ms": round(secs * 1000)})
    if ans.unknown or not kept:
        return finish(unknown)
    used = {i for s in kept for i in s["chunk_ids"]}
    stale_ids = stale_ids or set()
    return finish({
        "unknown": False,
        "answer": [{"text": s["text"], "chunk_ids": [i for i in s["chunk_ids"] if i in by_id],
                    "quote": best_quote(s["text"], by_id[s["chunk_ids"][0]].text)} for s in kept],
        "sources": {cid: source_payload(by_id[cid], stale_ids) for cid in used},
        "model": llm_model,
    })


def snapshot_date(con) -> str | None:
    rows = con.execute("SELECT DISTINCT version_date FROM articles WHERE version_date IS NOT NULL").fetchall()
    dates = sorted(filter(None, (_iso(r[0]) for r in rows)))
    return dates[-1] if dates else None
