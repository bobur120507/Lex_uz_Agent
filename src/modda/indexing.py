"""Embedding benchmark and the resumable indexing job (SQLite chunks → Qdrant)."""

from __future__ import annotations

import statistics
import sys
import time

from . import sparse
from .chunking import embed_text
from .corpus import set_meta
from .textnorm import tokenize

BATCH = 32


def _where(mvp_only: bool) -> str:
    return " WHERE c.indexed = 0" + (" AND c.mvp = 1" if mvp_only else "")


def _next_batch(con, mvp_only: bool, n: int):
    """Pending chunks are read batch by batch; a batch disappears from the query once it is marked indexed."""
    return con.execute(
        "SELECT c.*, a.doc_id, a.doc_type, a.status, a.article_number FROM chunks c "
        f"JOIN articles a ON a.id = c.article_id{_where(mvp_only)} ORDER BY c.mvp DESC, c.chunk_id LIMIT ?", (n,)).fetchall()


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


def run_index(con, store, embedder, model: str, *, mvp_only: bool = False,
              limit: int | None = None, batch: int = BATCH, retries: int = 3) -> int:
    """Index every chunk with indexed=0. Safe to stop with Ctrl+C and run again: it continues."""
    store.ensure_collection()
    row = con.execute("SELECT value FROM meta WHERE key='bm25_avg_len'").fetchone()
    if row:
        avg_len = float(row[0])
    else:
        avg_len = average_length(con)
        set_meta(con, "bm25_avg_len", str(avg_len))
        con.commit()

    total = con.execute(f"SELECT COUNT(*) FROM chunks c{_where(mvp_only)}").fetchone()[0]
    if limit:
        total = min(total, limit)
    done, t0 = 0, time.perf_counter()
    if not total:
        print("Indekslanadigan boʻlak qolmadi.")
        return 0
    print(f"Indekslanadi: {total} boʻlak ({'faqat MVP' if mvp_only else 'hammasi'}), BM25 oʻrtacha uzunlik {avg_len:.0f}")
    while done < total:
        part = _next_batch(con, mvp_only, min(batch, total - done))
        if not part:
            break
        texts = [embed_text(dict(r)) for r in part]
        for attempt in range(1, retries + 1):
            try:
                dense = embedder.embed(model, texts)
                break
            except Exception as exc:                         # network hiccup, model reload…
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
        con.executemany("UPDATE chunks SET indexed=1 WHERE chunk_id=?", [(r["chunk_id"],) for r in part])
        con.commit()
        done += len(part)
        el = time.perf_counter() - t0
        eta = el / done * (total - done)
        print(f"\r  {done}/{total}  {done / el:.1f} boʻlak/s  qoldi ≈ {_fmt(eta)}   ", end="", flush=True)
    print()
    return done
