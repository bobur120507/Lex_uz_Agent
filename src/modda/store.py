"""Vector store: Qdrant over its REST API (no client library), plus an in-memory twin for tests.

Collection layout (created once, used for the whole project):
  vectors:        "dense" — bge-m3, 1024, cosine
  sparse_vectors: "bm25"  — our BM25 weights, Qdrant applies IDF (modifier: idf)
  payload:        chunk_id, article_id, doc_id, doc_type, status, article_number, mvp
The texts themselves live in SQLite; Qdrant keeps only what is needed to search and filter.
Both vectors are written on day 1, so hybrid search on day 2 needs no re-indexing.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

import numpy as np
import requests

PAYLOAD_INDEXES = {
    "doc_id": "keyword", "doc_type": "keyword", "status": "keyword",
    "article_number": "keyword", "mvp": "integer",
}


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"modda:{chunk_id}"))


def _qdrant_filter(flt: dict | None) -> dict | None:
    if not flt:
        return None
    must = []
    for k, v in flt.items():
        if isinstance(v, (list, tuple, set)):
            must.append({"key": k, "match": {"any": list(v)}})
        else:
            must.append({"key": k, "match": {"value": v}})
    return {"must": must}


@dataclass
class Hit:
    chunk_id: str
    score: float
    payload: dict = field(default_factory=dict)


class QdrantError(RuntimeError):
    pass


class QdrantStore:
    def __init__(self, url: str, collection: str, dim: int = 1024, timeout: float = 120.0):
        self.url, self.collection, self.dim, self.timeout = url.rstrip("/"), collection, dim, timeout

    def _req(self, method: str, path: str, json: dict | None = None) -> dict:
        try:
            r = requests.request(method, f"{self.url}{path}", json=json, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise QdrantError(f"Qdrant’ga ulanib boʻlmadi ({self.url}). `docker start qdrant`?") from exc
        if r.status_code >= 400:
            raise QdrantError(f"Qdrant {method} {path} → HTTP {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def ping(self) -> str:
        """Qdrant version; raises QdrantError when the server is not reachable."""
        return str(self._req("GET", "/").get("version", "?"))

    def exists(self) -> bool:
        try:
            return bool(self._req("GET", f"/collections/{self.collection}/exists")["result"]["exists"])
        except QdrantError:
            return False

    def ensure_collection(self, recreate: bool = False) -> None:
        if recreate and self.exists():
            self._req("DELETE", f"/collections/{self.collection}")
        if not self.exists():
            self._req("PUT", f"/collections/{self.collection}", {
                "vectors": {"dense": {"size": self.dim, "distance": "Cosine", "on_disk": True}},
                "sparse_vectors": {"bm25": {"modifier": "idf"}},
                "on_disk_payload": True,
            })
            for name, schema in PAYLOAD_INDEXES.items():
                self._req("PUT", f"/collections/{self.collection}/index?wait=true",
                          {"field_name": name, "field_schema": schema})

    def upsert(self, items: list[dict]) -> None:
        """items: {chunk_id, dense, sparse, payload}"""
        # named vectors are optional in Qdrant: a sparse-only point simply has no "dense" vector
        points = [{
            "id": point_id(it["chunk_id"]),
            "vector": ({"dense": it["dense"]} if it.get("dense") is not None else {}) | {"bm25": it["sparse"]},
            "payload": {"chunk_id": it["chunk_id"], **it["payload"]},
        } for it in items]
        self._req("PUT", f"/collections/{self.collection}/points?wait=true", {"points": points})

    def count(self) -> int:
        return int(self._req("POST", f"/collections/{self.collection}/points/count", {"exact": True})["result"]["count"])

    def _points(self, body: dict) -> list[Hit]:
        res = self._req("POST", f"/collections/{self.collection}/points/query", body)["result"]
        pts = res.get("points", res) if isinstance(res, dict) else res
        return [Hit(p["payload"]["chunk_id"], float(p["score"]), p["payload"]) for p in pts]

    def search_dense(self, vector: list[float], limit: int = 5, flt: dict | None = None) -> list[Hit]:
        body = {"query": vector, "using": "dense", "limit": limit, "with_payload": True}
        if flt:
            body["filter"] = _qdrant_filter(flt)
        return self._points(body)

    def search_sparse(self, sparse: dict, limit: int = 5, flt: dict | None = None) -> list[Hit]:
        if not sparse["indices"]:
            return []
        body = {"query": sparse, "using": "bm25", "limit": limit, "with_payload": True}
        if flt:
            body["filter"] = _qdrant_filter(flt)
        return self._points(body)

    def search_hybrid(self, vector: list[float], sparse: dict, limit: int = 5, prefetch: int = 40,
                      flt: dict | None = None) -> list[Hit]:
        f = _qdrant_filter(flt)
        pre = [{"query": vector, "using": "dense", "limit": prefetch}]
        if sparse["indices"]:
            pre.append({"query": sparse, "using": "bm25", "limit": prefetch})
        if f:
            for p in pre:
                p["filter"] = f
        return self._points({"prefetch": pre, "query": {"fusion": "rrf"}, "limit": limit, "with_payload": True})

    def vectors(self, chunk_ids: list[str]) -> dict[str, list[float]]:
        """Stored bge-m3 vectors of these chunks (chunks without a dense vector are left out)."""
        if not chunk_ids:
            return {}
        res = self._req("POST", f"/collections/{self.collection}/points",
                        {"ids": [point_id(c) for c in chunk_ids], "with_vector": ["dense"], "with_payload": ["chunk_id"]})
        out = {}
        for p in res.get("result", []):
            v = (p.get("vector") or {}).get("dense")
            if v:
                out[p["payload"]["chunk_id"]] = v
        return out

    def sample_vectors(self, n: int = 2000) -> list[tuple[str, list[float], dict]]:
        """The first n points in id order — a fixed, reproducible sample (used for the PCA reference)."""
        out, offset = [], None
        while len(out) < n:
            body = {"limit": min(256, n - len(out)), "with_vector": ["dense"],
                    "with_payload": ["chunk_id", "doc_type"]}
            if offset is not None:
                body["offset"] = offset
            res = self._req("POST", f"/collections/{self.collection}/points/scroll", body)["result"]
            for p in res.get("points", []):
                v = (p.get("vector") or {}).get("dense")
                if v:
                    out.append((p["payload"]["chunk_id"], v, p["payload"]))
            offset = res.get("next_page_offset")
            if offset is None:
                break
        return out[:n]


class MemoryStore:
    """Same interface as QdrantStore, everything in RAM. Used by tests and `--store memory`."""

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.points: dict[str, tuple[np.ndarray, dict, dict]] = {}

    def exists(self) -> bool:
        return True

    def ensure_collection(self, recreate: bool = False) -> None:
        if recreate:
            self.points.clear()

    def upsert(self, items: list[dict]) -> None:
        for it in items:
            v = None
            if it.get("dense") is not None:
                v = np.asarray(it["dense"], dtype=np.float32)
                v /= (np.linalg.norm(v) or 1.0)
            self.points[it["chunk_id"]] = (v, it["sparse"], {"chunk_id": it["chunk_id"], **it["payload"]})

    def count(self) -> int:
        return len(self.points)

    def vectors(self, chunk_ids):
        return {c: self.points[c][0].tolist() for c in chunk_ids if c in self.points and self.points[c][0] is not None}

    def sample_vectors(self, n=2000):
        return [(c, v.tolist(), p) for c, (v, _, p) in sorted(self.points.items()) if v is not None][:n]

    def _match(self, payload: dict, flt: dict | None) -> bool:
        if not flt:
            return True
        for k, v in flt.items():
            if isinstance(v, (list, tuple, set)):
                if payload.get(k) not in v:
                    return False
            elif payload.get(k) != v:
                return False
        return True

    def search_dense(self, vector, limit=5, flt=None) -> list[Hit]:
        q = np.asarray(vector, dtype=np.float32)
        q /= (np.linalg.norm(q) or 1.0)
        scored = [(float(v @ q), cid, p) for cid, (v, _, p) in self.points.items() if v is not None and self._match(p, flt)]
        scored.sort(key=lambda x: -x[0])
        return [Hit(cid, s, p) for s, cid, p in scored[:limit]]

    def search_sparse(self, sparse, limit=5, flt=None) -> list[Hit]:
        if not sparse["indices"]:
            return []
        n = len(self.points) or 1
        df: dict[int, int] = {}
        for _, sp, _ in self.points.values():
            for i in sp["indices"]:
                df[i] = df.get(i, 0) + 1
        qset = set(sparse["indices"])
        scored = []
        for cid, (_, sp, p) in self.points.items():
            if not self._match(p, flt):
                continue
            s = sum(w * math.log(1 + (n - df[i] + 0.5) / (df[i] + 0.5))
                    for i, w in zip(sp["indices"], sp["values"]) if i in qset)
            if s > 0:
                scored.append((s, cid, p))
        scored.sort(key=lambda x: -x[0])
        return [Hit(cid, s, p) for s, cid, p in scored[:limit]]

    def search_hybrid(self, vector, sparse, limit=5, prefetch=40, flt=None) -> list[Hit]:
        lists = [self.search_dense(vector, prefetch, flt), self.search_sparse(sparse, prefetch, flt)]
        scores: dict[str, float] = {}
        payloads: dict[str, dict] = {}
        for hits in lists:
            for rank, h in enumerate(hits, start=1):
                scores[h.chunk_id] = scores.get(h.chunk_id, 0.0) + 1.0 / (60 + rank)   # RRF with k=60
                payloads[h.chunk_id] = h.payload
        best = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
        return [Hit(cid, s, payloads[cid]) for cid, s in best]
