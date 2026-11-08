"""HTTP API for the website (FastAPI). The logic lives in `service.py`; this file only maps it to HTTP.

  GET  /health       database and index state, snapshot date, Ollama / Qdrant reachability
  POST /ask          {"question": "..."} → answer JSON (same shape the website's mock data uses)
  POST /ask/stream   the same, as Server-Sent Events: every stage of roadmap §12.4, then `answer.completed`

Inspector endpoints (frontend_idea/, read-only, real data only):
  GET  /ask/{request_id}/embedding   the query's exact bge-m3 vector, PCA projection, candidates' positions
  GET  /ask/{request_id}/trace       the request's recorded stages (no vector)
  GET  /model/info                   architecture of the embedding model and the LLM (Ollama /api/show)
  GET  /chunks/{chunk_id}/context    the found article among ±n neighbouring articles (book pages)
  GET  /articles/{article_id}/context  the same, starting from an article (documents page)
  GET  /documents?q=                 document list for «Hujjatlar»;  GET /documents/{doc_id}  its articles
Request traces live in memory for 30 minutes (last 50 requests); nothing is written to disk.

API /v1 («RAG API — test spetsifikatsiyasi», v1.py): POST /v1/rag/batch, GET /v1/rag/batch/{id}, POST /v1/rag/query,
GET /v1/meta, GET /v1/health — Bearer key from MODDA_API_KEY; batch results are saved in data/v1/batches/.

Run: python -m modda serve        (http://localhost:8080; the Vite dev servers proxy these paths)
Without FastAPI installed, `serve` falls back to `devserver.py` (standard library) with the same routes.
Optional reranker: RERANKER=on (needs `.[rerank]`; slow on CPU), RERANK_TAU=0.3 for «Bilmayman».
"""

from __future__ import annotations

import json
import queue
import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import service
from .service import NotFound

app = FastAPI(title="Modda", version="0.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


def _nf(fn, *args):
    try:
        return fn(*args)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@app.get("/health")
def health():
    return service.health()


@app.post("/ask")
def ask_plain(q: Question):
    try:
        return service.run(q.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/ask/stream")
def ask_stream(q: Question):
    events: queue.Queue = queue.Queue()

    def work():
        try:
            service.run(q.question, emit=events.put)
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


@app.get("/model/info")
def model_info():
    return service.model_info()


@app.get("/ask/{request_id}/trace")
def ask_trace(request_id: str):
    return _nf(service.trace, request_id)


@app.get("/ask/{request_id}/embedding")
def ask_embedding(request_id: str):
    return _nf(service.embedding, request_id)


@app.get("/chunks/{chunk_id}/context")
def chunk_context(chunk_id: str, n: int = Query(5, ge=0, le=10)):
    return _nf(service.chunk_context, chunk_id, n)


@app.get("/articles/{article_id}/context")
def article_context(article_id: str, n: int = Query(5, ge=0, le=10)):
    return _nf(service.article_context, article_id, n)


@app.get("/documents")
def documents(q: str = "", limit: int = Query(20, ge=1, le=100), doc_type: str | None = None):
    return service.documents(q, limit, doc_type)


@app.get("/documents/{doc_id}")
def document(doc_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return _nf(service.document, doc_id, offset, limit)


# --------------------------------------------------------------------------- API /v1 (test spetsifikatsiyasi)
# logic in v1.py; here only HTTP: auth → rate limit → JSON → work in a thread (the LLM blocks)

from fastapi import Request                                 # noqa: E402
from fastapi.responses import JSONResponse                  # noqa: E402
from starlette.concurrency import run_in_threadpool        # noqa: E402

from . import v1                                            # noqa: E402

UTF8 = "application/json; charset=utf-8"


def _v1_error(e: "v1.ApiError") -> JSONResponse:
    return JSONResponse(e.body(), status_code=e.status, headers=e.headers, media_type=UTF8)


async def _v1_json(request: Request):
    try:
        return json.loads((await request.body()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise v1.ApiError(400, "BAD_REQUEST", f"JSON oʻqilmadi: {exc}") from None


@app.post("/v1/rag/batch")
async def v1_batch(request: Request):
    auth = request.headers.get("authorization")
    try:
        v1.check_auth(auth)
        v1.rate_limit(auth)
        status, out = await run_in_threadpool(v1.submit_batch, await _v1_json(request))
        return JSONResponse(out, status_code=status, media_type=UTF8)
    except v1.ApiError as e:
        return _v1_error(e)


@app.get("/v1/rag/batch/{batch_id}")
async def v1_batch_get(batch_id: str, request: Request):
    try:
        v1.check_auth(request.headers.get("authorization"))
        status, out = await run_in_threadpool(v1.get_batch, batch_id)
        return JSONResponse(out, status_code=status, media_type=UTF8)
    except v1.ApiError as e:
        return _v1_error(e)


@app.post("/v1/rag/query")
async def v1_query(request: Request):
    try:
        v1.check_auth(request.headers.get("authorization"))
        return JSONResponse(await run_in_threadpool(v1.query, await _v1_json(request)), media_type=UTF8)
    except v1.ApiError as e:
        return _v1_error(e)


@app.get("/v1/meta")
async def v1_meta(request: Request):
    try:
        v1.check_auth(request.headers.get("authorization"))
        return JSONResponse(await run_in_threadpool(v1.meta), media_type=UTF8)
    except v1.ApiError as e:
        return _v1_error(e)


@app.get("/v1/health")
async def v1_health():
    out = await run_in_threadpool(v1.health)
    return JSONResponse(out, status_code=200 if out["status"] == "ok" else 503, media_type=UTF8)


_dist = service.web_dist()                             # MODDA_WEB_DIST=frontend_idea/dist for the new site
if _dist:
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
