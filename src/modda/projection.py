"""A fixed 3-D view of the 1024-dimensional bge-m3 space (PCA), for the website's vector inspector.

The transform is fitted once on a reproducible reference sample (the first N points of the collection in
id order), saved to data/projection/, and then applied unchanged to every query and candidate. Its
`version` is derived from the sample ids, so the same index always gives the same picture. The XYZ values
are a derived projection, not native embedding dimensions — the page says so.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SAMPLE = 2000
CLOUD = 600                                         # reference points sent to the page as background

_lock = threading.Lock()
_cache: dict[str, "Projection"] = {}


@dataclass
class Projection:
    version: str
    mean: np.ndarray
    components: np.ndarray                          # 3 × dim
    explained: list[float]                          # share of variance kept by each axis
    sample_size: int
    cloud: list[dict]                               # [{chunk_id, doc_type, xyz}]

    def apply(self, vectors) -> np.ndarray:
        v = np.asarray(vectors, dtype=np.float32)
        v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
        return (v - self.mean) @ self.components.T

    def info(self) -> dict:
        return {"method": "PCA", "transform_version": self.version, "fitted_on": self.sample_size,
                "explained_variance": [round(x, 4) for x in self.explained]}


def fit(sample: list[tuple[str, list[float], dict]]) -> Projection:
    if len(sample) < 10:
        raise ValueError("PCA uchun indeksda kamida 10 ta dense vektor kerak")
    ids = [s[0] for s in sample]
    x = np.asarray([s[1] for s in sample], dtype=np.float32)
    x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)
    mean = x.mean(axis=0)
    _, sing, vt = np.linalg.svd(x - mean, full_matrices=False)
    comps = vt[:3]
    var = sing ** 2
    explained = (var[:3] / var.sum()).tolist()
    version = "pca3-" + hashlib.sha1("\n".join(ids).encode()).hexdigest()[:10]
    xyz = (x - mean) @ comps.T
    step = max(1, len(sample) // CLOUD)
    cloud = [{"chunk_id": sample[i][0], "doc_type": sample[i][2].get("doc_type"), "xyz": [round(float(c), 4) for c in xyz[i]]}
             for i in range(0, len(sample), step)][:CLOUD]
    return Projection(version, mean, comps, explained, len(sample), cloud)


def get(store, cache_dir: Path) -> Projection:
    """The saved projection for this collection, fitted on first use."""
    key = f"{getattr(store, 'url', 'memory')}|{getattr(store, 'collection', '')}"
    with _lock:
        if key in _cache:
            return _cache[key]
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{getattr(store, 'collection', 'memory')}-pca3.npz"
        if path.exists():
            z = np.load(path, allow_pickle=False)
            p = Projection(str(z["version"]), z["mean"], z["components"], z["explained"].tolist(),
                           int(z["sample_size"]), json.loads(str(z["cloud"])))
        else:
            p = fit(store.sample_vectors(SAMPLE))
            np.savez(path, version=p.version, mean=p.mean, components=p.components, explained=np.asarray(p.explained),
                     sample_size=p.sample_size, cloud=json.dumps(p.cloud))
        _cache[key] = p
        return p
