"""Reranker: a cross-encoder reads (question, chunk) pairs and scores how well the chunk answers.

`bge-reranker-v2-m3` (multilingual) via sentence-transformers. It is about as heavy as bge-m3, so on a
CPU-only laptop keep `top_n` small (10) and `max_length` short (384 tokens).
Install: uv pip install -e ".[rerank]"
"""

from __future__ import annotations

import time


class CrossEncoderReranker:
    def __init__(self, model: str = "BAAI/bge-reranker-v2-m3", max_length: int = 384, device: str | None = None):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError('Reranker uchun: uv pip install -e ".[rerank]"') from exc
        self.name = model
        self.model = CrossEncoder(model, max_length=max_length, device=device)

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        scores = self.model.predict([(query, t) for t in texts], batch_size=8, show_progress_bar=False)
        return [float(s) for s in scores]


class OverlapReranker:
    """No-model fallback (and test double): share of question terms found in the chunk."""

    name = "overlap"

    def score(self, query: str, texts: list[str]) -> list[float]:
        from .textnorm import tokenize
        q = set(tokenize(query))
        return [len(q & set(tokenize(t))) / (len(q) or 1) for t in texts]


def rerank(reranker, query: str, contexts, top_n: int = 5):
    """Returns (sorted contexts, scores, seconds). Contexts keep their objects; `score` is replaced."""
    t0 = time.perf_counter()
    scores = reranker.score(query, [f"{c.header}\n{c.text}" for c in contexts])
    order = sorted(range(len(contexts)), key=lambda i: -scores[i])
    out = []
    for i in order[:top_n]:
        c = contexts[i]
        c.score = scores[i]
        out.append(c)
    for n, c in enumerate(out, start=1):
        c.n = n
    return out, [scores[i] for i in order], time.perf_counter() - t0
