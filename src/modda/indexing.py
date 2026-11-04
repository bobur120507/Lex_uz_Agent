"""Embedding benchmark and the resumable indexing job (database chunks → Qdrant).

Two tiers, because dense embedding on a CPU is slow (≈ 0.5 chunk/s for bge-m3):
  * sparse (BM25) for every chunk — pure Python, minutes for the whole corpus;
  * dense (bge-m3) for the acts people ask about most: codes, the Constitution, laws.
`chunks.indexed`: 0 = not in Qdrant, 1 = dense + sparse, 2 = sparse only (upgraded to 1 later).
"""

from __future__ import annotations

import statistics
import sys
import time

from . import sparse
from .chunking import embed_text
from .corpus import set_meta
from .textnorm import tokenize

import re

BATCH = 32
SPARSE_BATCH = 256
DENSE_TYPES = ("code", "constitution", "law")
NONE, FULL, SPARSE_ONLY = 0, 1, 2


def _where(mvp_only: bool, mode: str = "dense", types=None) -> str:
    if mode == "sparse":
        # mvp = 0 only: never races with an `index --mvp` job that may be running at the same time
        w = f" WHERE c.indexed = {NONE} AND c.mvp = 0"
    else:
        w = f" WHERE c.indexed IN ({NONE}, {SPARSE_ONLY})"
    if mvp_only:
        w += " AND c.mvp = 1"
    if types:
        safe = [t for t in types if re.fullmatch(r"[a-z_]+", t)]
        w += " AND a.doc_type IN (" + ", ".join(f"'{t}'" for t in safe) + ")"
    return w


def _next_batch(con, mvp_only: bool, n: int, mode: str = "dense", types=None):
    """Pending chunks are read batch by batch; a batch disappears from the query once it is marked indexed."""
    return con.execute(
        "SELECT c.*, a.doc_id, a.doc_type, a.status, a.article_number FROM chunks c "
        f"JOIN articles a ON a.id = c.article_id{_where(mvp_only, mode, types)} "
        "ORDER BY c.mvp DESC, c.chunk_id LIMIT ?", (n,)).fetchall()


def average_length(con, sample: int = 3000) -> float:
    rows = con.execute("SELECT header, text FROM chunks ORDER BY RANDOM() LIMIT ?", (sample,)).fetchall()
    if not rows:
        return sparse.AVG_LEN
    return statistics.mean(len(tokenize(f"{r['header']}\n{r['text']}")) for r in rows)


def _fmt(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600} soat {sec % 3600 // 60} daq" if sec >= 3600 else f"{sec // 60} daq {sec % 60} s"


def bench(con, embedder, model: str, n: int = 256, batch: int = BATCH) -> dict:
    """Embed n random chunks and extrapolate the time for the MVP subset and the whole corpus."""
    rows = con.execute("SELECT header, text FROM chunks ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
    if not rows:
        raise SystemExit("Boʻlaklar yoʻq. Avval: python -m modda ingest && python -m modda chunk")
    texts = [f"{r['header']}\n{r['text']}" for r in rows]
    print(f"Model yuklanmoqda ({model})…", flush=True)
    t_load = time.perf_counter()
    dim = len(embedder.embed(model, texts[:2])[0])                     # warm-up: loads the model
    print(f"  tayyor: {time.perf_counter() - t_load:.1f} s, vektor oʻlchami {dim}", flush=True)
    t0 = time.perf_counter()
    for i in range(0, len(texts), batch):
        embedder.embed(model, texts[i:i + batch])
        done = min(i + batch, len(texts))
        print(f"\r  {done}/{len(texts)} boʻlak, {done / (time.perf_counter() - t0):.1f} boʻlak/s   ", end="", flush=True)
    print()
    dt = time.perf_counter() - t0
    per_chunk = dt / len(texts)
    total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    mvp = con.execute("SELECT COUNT(*) FROM chunks WHERE mvp=1").fetchone()[0]
    return {
        "embedding_dim": dim,
        "chunks_measured": len(texts), "seconds": round(dt, 2), "chunks_per_s": round(len(texts) / dt, 2),
        "mvp_chunks": mvp, "mvp_eta": _fmt(per_chunk * mvp),
        "all_chunks": total, "all_eta": _fmt(per_chunk * total),
    }


def run_index(con, store, embedder, model: str, *, mvp_only: bool = False, mode: str = "dense", types=None,
              limit: int | None = None, batch: int | None = None, retries: int = 3) -> int:
    """mode="dense": bge-m3 + BM25 for pending chunks (also upgrades sparse-only ones).
    mode="sparse": BM25 only, no Ollama needed. Safe to stop with Ctrl+C and run again: it continues."""
    batch = batch or (SPARSE_BATCH if mode == "sparse" else BATCH)
    store.ensure_collection()
    row = con.execute("SELECT value FROM meta WHERE key='bm25_avg_len'").fetchone()
    if row:
        avg_len = float(row[0])
    else:
        avg_len = average_length(con)
        set_meta(con, "bm25_avg_len", str(avg_len))
        con.commit()

    total = con.execute("SELECT COUNT(*) FROM chunks c JOIN articles a ON a.id = c.article_id"
                        f"{_where(mvp_only, mode, types)}").fetchone()[0]
    if limit:
        total = min(total, limit)
    done, t0 = 0, time.perf_counter()
    if not total:
        print("Indekslanadigan boʻlak qolmadi.")
        return 0
    scope = "faqat MVP" if mvp_only else (", ".join(types) if types else "hammasi")
    kind = "faqat BM25" if mode == "sparse" else "dense + BM25"
    print(f"Indekslanadi: {total} boʻlak ({scope}; {kind}), BM25 oʻrtacha uzunlik {avg_len:.0f}")
    while done < total:
        part = _next_batch(con, mvp_only, min(batch, total - done), mode, types)
        if not part:
            break
        texts = [embed_text(dict(r)) for r in part]
        if mode == "sparse":
            dense = [None] * len(part)
        else:
            for attempt in range(1, retries + 1):
                try:
                    dense = embedder.embed(model, texts)
                    break
                except Exception as exc:                     # network hiccup, model reload…
                    if attempt == retries:
                        raise
                    print(f"  qayta urinish {attempt}: {exc}", file=sys.stderr)
                    time.sleep(3 * attempt)
        items = [{
            "chunk_id": r["chunk_id"], "dense": v, "sparse": sparse.doc_vector(t, avg_len),
            "payload": {"article_id": r["article_id"], "doc_id": r["doc_id"], "doc_type": r["doc_type"],
                        "status": r["status"], "article_number": r["article_number"], "mvp": r["mvp"]},
        } for r, v, t in zip(part, dense, texts)]
        store.upsert(items)
        flag = SPARSE_ONLY if mode == "sparse" else FULL
        con.executemany(f"UPDATE chunks SET indexed={flag} WHERE chunk_id=?", [(r["chunk_id"],) for r in part])
        con.commit()
        done += len(part)
        el = time.perf_counter() - t0
        eta = el / done * (total - done)
        print(f"\r  {done}/{total}  {done / el:.1f} boʻlak/s  qoldi ≈ {_fmt(eta)}   ", end="", flush=True)
    print()
    return done
