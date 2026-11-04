"""Move a finished index from one computer to another (e.g. a teammate's GPU laptop → the server).

Export (GPU computer):  python -m modda snapshot-export
  → data/exports/modda-<date>.snapshot  (Qdrant snapshot: every vector)
  → data/exports/modda-<date>.manifest.json.gz  (which chunks are dense / BM25-only, checks)
Import (server):        python -m modda snapshot-import data/exports/modda-<date>.snapshot
  → the Qdrant collection is replaced by the snapshot, the database's `indexed` flags are set to match.

Both computers must have the same corpus and the same code (same chunk ids); the manifest carries a
fingerprint of the chunk ids and the import refuses a mismatch.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

from .config import ROOT
from .corpus import set_meta

DATASET_REVISION = "c69bbd5e1d645084194696d77f46607aa8d51a9f"     # sukhrobnurali/uzbek-legal-corpus


def _fingerprint(ids: list[str]) -> str:
    h = hashlib.sha256()
    for i in sorted(ids):
        h.update(i.encode())
        h.update(b"\n")
    return h.hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def export(con, store, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_ids = [r[0] for r in con.execute("SELECT chunk_id FROM chunks")]
    dense = [r[0] for r in con.execute("SELECT chunk_id FROM chunks WHERE indexed = 1")]
    sparse_only = [r[0] for r in con.execute("SELECT chunk_id FROM chunks WHERE indexed = 2")]
    avg = con.execute("SELECT value FROM meta WHERE key = 'bm25_avg_len'").fetchone()
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    base = out_dir / f"modda-{stamp}"

    t0 = time.time()
    print("Qdrant snapshot yaratilmoqda…", flush=True)
    r = requests.post(f"{store.url}/collections/{store.collection}/snapshots?wait=true", timeout=3600)
    r.raise_for_status()
    name = r.json()["result"]["name"]
    snap = base.with_suffix(".snapshot")
    with requests.get(f"{store.url}/collections/{store.collection}/snapshots/{name}", stream=True, timeout=3600) as g:
        g.raise_for_status()
        total = int(g.headers.get("content-length", 0))
        done = 0
        with open(snap, "wb") as fh:
            for part in g.iter_content(chunk_size=8 << 20):
                fh.write(part)
                done += len(part)
                if total:
                    print(f"\r  yuklab olinmoqda: {done / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", flush=True)
    print(f"\n  ✓ {snap} ({snap.stat().st_size / 1e6:,.0f} MB, {time.time() - t0:.0f} s)")
    requests.delete(f"{store.url}/collections/{store.collection}/snapshots/{name}", timeout=600)   # free Qdrant's copy

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"), "collection": store.collection,
        "points": store.count(), "chunks_total": len(all_ids), "chunks_fingerprint": _fingerprint(all_ids),
        "dense": dense, "sparse_only": sparse_only, "bm25_avg_len": float(avg[0]) if avg else None,
        "dataset_revision": DATASET_REVISION, "code_commit": _git_commit(), "snapshot": snap.name,
    }
    man = base.with_suffix(".manifest.json.gz")
    with gzip.open(man, "wt", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    print(f"  ✓ {man}: {len(dense):,} dense, {len(sparse_only):,} faqat BM25, jami nuqta {manifest['points']:,}")
    return snap, man


class _Multipart:
    """A multipart/form-data body read from disk piece by piece: a 2 GB snapshot is never held in memory."""

    def __init__(self, path: Path, field: str = "snapshot"):
        self.boundary = "modda" + hashlib.sha1(str(time.time()).encode()).hexdigest()
        head = (f"--{self.boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{path.name}\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n").encode()
        tail = f"\r\n--{self.boundary}--\r\n".encode()
        self.parts = [head, path, tail]
        self.len = len(head) + path.stat().st_size + len(tail)
        self.sent, self.t0, self._fh, self._i, self._shown = 0, time.time(), None, 0, 0.0

    @property
    def content_type(self) -> str:
        return f"multipart/form-data; boundary={self.boundary}"

    def read(self, n: int = 8 << 20) -> bytes:
        while self._i < len(self.parts):
            part = self.parts[self._i]
            if isinstance(part, bytes):
                self._i += 1
                out = part
            else:
                self._fh = self._fh or open(part, "rb")
                out = self._fh.read(n if n and n > 0 else 8 << 20)
                if not out:
                    self._fh.close()
                    self._i += 1
                    continue
            self.sent += len(out)
            mb = self.sent / 1e6
            if time.time() - self._shown < 0.5 and self.sent < self.len:
                return out
            self._shown = time.time()
            print(f"\r  yuborilmoqda: {mb:,.0f} / {self.len / 1e6:,.0f} MB "
                  f"({mb / max(time.time() - self.t0, 1e-6):.0f} MB/s)", end="", flush=True)
            return out
        return b""


def import_(con, store, snap: Path, manifest_path: Path | None = None, force: bool = False) -> dict:
    manifest_path = manifest_path or snap.with_name(snap.name.replace(".snapshot", ".manifest.json.gz"))
    with gzip.open(manifest_path, "rt", encoding="utf-8") as fh:
        man = json.load(fh)
    local = [r[0] for r in con.execute("SELECT chunk_id FROM chunks")]
    if _fingerprint(local) != man["chunks_fingerprint"] and not force:
        raise SystemExit(
            f"Boʻlaklar mos emas: bu yerda {len(local):,}, snapshot’da {man['chunks_total']:,}. "
            "Ikkala kompyuterda bir xil kod va korpus boʻlishi kerak (git pull; python -m modda ingest; "
            "python -m modda chunk --rebuild). Majburan: --force")
    t0 = time.time()
    print(f"Snapshot yuklanmoqda: {snap} ({snap.stat().st_size / 1e6:,.0f} MB)…", flush=True)
    body = _Multipart(snap)
    r = requests.post(f"{store.url}/collections/{store.collection}/snapshots/upload?priority=snapshot&wait=true",
                      data=body, headers={"Content-Type": body.content_type, "Content-Length": str(body.len)},
                      timeout=7200)
    print()
    requests.delete(f"{store.url}/collections/{store.collection}/snapshots/{snap.name}", timeout=600)  # Qdrant's copy
    if r.status_code >= 400:
        raise SystemExit(f"Qdrant snapshot’ni qabul qilmadi: HTTP {r.status_code} {r.text[:300]}")
    con.execute("UPDATE chunks SET indexed = 0")
    con.executemany("UPDATE chunks SET indexed = 1 WHERE chunk_id = ?", [(i,) for i in man["dense"]])
    con.executemany("UPDATE chunks SET indexed = 2 WHERE chunk_id = ?", [(i,) for i in man["sparse_only"]])
    if man.get("bm25_avg_len"):
        set_meta(con, "bm25_avg_len", str(man["bm25_avg_len"]))
    con.commit()
    res = {"points": store.count(), "dense": len(man["dense"]), "sparse_only": len(man["sparse_only"]),
           "seconds": round(time.time() - t0)}
    print(f"  ✓ {res}")
    return res
