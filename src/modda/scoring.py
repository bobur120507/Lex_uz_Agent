"""The score on Lady Justice's scales: how well the answer is backed by the Lex.uz text it cites.

Measured, not guessed. For every sentence the LLM wrote:
  * cited      — it points to at least one of the sources it was given;
  * numbers_ok — every number in it appears in the cited source (the verifier's rule);
  * overlap    — share of its content words (3+ letters) that also appear in the cited source text.
A sentence is *supported* when it is cited and its numbers check out.

  score = mean over all sentences of (overlap if supported else 0), as a percentage.

So a sentence the verifier rejected weighs fully on the "answer" pan, and a supported sentence weighs
on the "Lex.uz" pan as much as its wording really matches the source. It is a lexical match measure:
it shows how closely the answer follows the law's own words, not whether a lawyer would agree.
"""

from __future__ import annotations

from .textnorm import tokenize

METHOD = "lexical-support-v1"


def _content(text: str) -> set[str]:
    return {t for t in tokenize(text) if len(t) >= 3 and not t.isdigit()}


def score_answer(sentences: list[dict], by_id: dict) -> dict:
    """sentences: [{text, chunk_ids, ok, why}] — all sentences the LLM produced, kept and rejected."""
    rows = []
    for s in sentences:
        ids = [i for i in s.get("chunk_ids", []) if i in by_id]
        src = " ".join(f"{by_id[i].header} {by_id[i].text}" for i in ids)
        words = _content(s["text"])
        hit = words & _content(src) if src else set()
        overlap = len(hit) / len(words) if words else 0.0
        supported = bool(ids) and bool(s.get("ok"))
        rows.append({
            "text": s["text"], "chunk_ids": ids, "cited": bool(ids), "numbers_ok": bool(s.get("ok")) if ids else None,
            "supported": supported, "why": s.get("why", ""), "overlap": round(overlap, 3),
            "matched_words": sorted(hit)[:40], "words": len(words),
        })
    n = len(rows)
    if not n:
        return {"method": METHOD, "score": None, "sentences": [], "supported": 0, "total": 0}
    score = sum(r["overlap"] for r in rows if r["supported"]) / n
    return {
        "method": METHOD, "score": round(100 * score, 1),
        "supported": sum(r["supported"] for r in rows), "total": n,
        "mean_overlap": round(100 * sum(r["overlap"] for r in rows) / n, 1),
        "sentences": rows,
    }
