"""HTTP API for the website.

  GET  /health       database and index state, snapshot date
  POST /ask          {"question": "..."} → answer JSON (same shape the website's mock data uses)
  POST /ask/stream   the same, as Server-Sent Events: every stage of roadmap §12.4, then `answer.completed`

Run: python -m modda serve        (http://localhost:8080; the Vite dev server proxies /ask and /health)
Optional reranker: RERANKER=on (needs `.[rerank]`; slow on CPU), RERANK_TAU=0.3 for «Bilmayman».
"""

from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import ROOT, get_settings
from .corpus import connect, stats
from .llm import Ollama
from .pipeline import ask, snapshot_date
from .store import QdrantStore

S = get_settings()
app = FastAPI(title="Modda", version="0.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

_reranker = None
_cache: dict = {}


def _con():
    return connect(S.db_path, url=S.database_url or None)


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


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


def _run(question: str, emit=None) -> dict:
    con = _con()
    try:
        llm = Ollama(S.ollama_url)
        tau = os.environ.get("RERANK_TAU")
        return ask(con, QdrantStore(S.qdrant_url, S.collection, S.embed_dim), llm, llm,
                   question=question, embed_model=S.embed_model, llm_model=S.llm_model, emit=emit, k=S.top_k,
                   reranker=_get_reranker(), tau=float(tau) if tau else None,
                   stale_ids=_stale(con), checked_at=_checked_at(con))
    finally:
        con.close()


@app.get("/health")
def health():
    con = _con()
    try:
        st = stats(con)
        return {"ok": True, "checked_at": _checked_at(con), "articles": st["articles"], "chunks": st["chunks"],
                "dense_indexed": st["chunks_indexed"], "sparse_only": st.get("chunks_sparse_only", 0),
                "llm": S.llm_model, "embed": S.embed_model, "reranker": _reranker is not None}
    finally:
        con.close()


@app.post("/ask")
def ask_plain(q: Question):
    try:
        return _run(q.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/ask/stream")
def ask_stream(q: Question):
    events: queue.Queue = queue.Queue()

    def work():
        try:
            _run(q.question, emit=events.put)
        except Exception as exc:                       # reported to the page instead of a broken stream
            events.put({"type": "stage.failed", "data": {"stage": "server", "message": str(exc)[:300]}})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def sse():
        while True:
            ev = events.get()
            if ev is None:
                break
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


_dist = ROOT / "web" / "dist"
if _dist.exists():                                     # `npm run build` output served at /
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=Path(_dist), html=True), name="web")
