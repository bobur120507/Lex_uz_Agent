"""BM25 sparse vectors for Qdrant.

Documents get BM25 term weights (tf saturation + length normalization); Qdrant's `modifier: idf`
multiplies them by IDF at query time. Queries are plain term sets (weight 1).
Token → index is a stable CRC32 hash, so no vocabulary file is needed.
"""

from __future__ import annotations

import zlib
from collections import Counter

from .textnorm import tokenize

K1 = 1.2
B = 0.75
AVG_LEN = 220.0          # average tokens per chunk; recomputed by `modda index` and stored in meta


def token_id(token: str) -> int:
    return zlib.crc32(token.encode("utf-8")) & 0x7FFFFFFF


def doc_vector(text: str, avg_len: float = AVG_LEN) -> dict:
    toks = tokenize(text)
    if not toks:
        return {"indices": [], "values": []}
    tf = Counter(toks)
    dl = len(toks)
    weights: dict[int, float] = {}
    for tok, f in tf.items():
        w = f * (K1 + 1) / (f + K1 * (1 - B + B * dl / avg_len))
        idx = token_id(tok)
        weights[idx] = weights.get(idx, 0.0) + w          # hash collisions just add up
    idx = sorted(weights)
    return {"indices": idx, "values": [round(weights[i], 5) for i in idx]}


def query_vector(text: str) -> dict:
    idx = sorted({token_id(t) for t in tokenize(text)})
    return {"indices": idx, "values": [1.0] * len(idx)}
