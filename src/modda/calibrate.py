"""τ calibration for «Bilmayman» without a reranker (roadmap 3–4-kun).

Signal: the cosine similarity between the question's bge-m3 vector and the closest chunk in the index
(`dense_top`). Questions the law answers land close to some article; questions it does not answer
(weather, football, recipes…) land far from all of them.

Positives: the golden set's answerable questions. Negatives: its unanswerable ones plus NEGATIVES below.
τ is the largest threshold that still keeps ≥ `keep` (default 97 %) of the positives — questions below τ
get «Bilmayman» without an LLM call (explicit references such as «Mehnat kodeksi 131-modda» always pass).
If τ blocks less than half of the negatives the signal does not separate well enough and no τ is advised.
"""

from __future__ import annotations

import os
import re
import statistics
from pathlib import Path

from .textnorm import to_query_form

NEGATIVES = [
    "Ertaga Toshkentda ob-havo qanday boʻladi?",
    "Eng mazali osh retsepti qanday?",
    "Real Madrid kechagi oʻyinda kim bilan oʻynadi?",
    "Python’da roʻyxatni qanday saralash mumkin?",
    "Dollar kursi bugun qancha?",
    "Qaysi telefonni sotib olsam yaxshi?",
    "Menga sevgi haqida sheʼr yozib ber.",
    "Oyga birinchi boʻlib kim qadam qoʻygan?",
    "Samarqanddan Buxoroga poyezd qachon joʻnaydi?",
    "Bosh ogʻrigʻiga qaysi dori yaxshi?",
    "Ingliz tilini tez oʻrganish uchun nima qilish kerak?",
    "Eng yaxshi film qaysi?",
    "Mashinamning motori nega shovqin qilyapti?",
    "Kompyuterim sekin ishlayapti, nima qilay?",
    "Quyosh tizimida nechta sayyora bor?",
    "Bugun kechqurun nima pishirsam boʻladi?",
    "Toshkentda eng yaxshi kafe qaysi?",
    "Mushugim ovqat yemayapti, nima qilsam boʻladi?",
    "Dunyodagi eng baland togʻ qaysi?",
    "Futbol boʻyicha jahon chempionati qachon boʻladi?",
]


def _top(store, embedder, embed_model: str, q: str) -> float:
    vec = embedder.embed(embed_model, [to_query_form(q)])[0]
    hits = store.search_dense(vec, 1)
    return float(hits[0].score) if hits else 0.0


def calibrate(store, embedder, embed_model: str, golden: list[dict], keep: float = 0.97) -> dict:
    pos = [it["question"] for it in golden if it.get("answerable", True)]
    neg = [it["question"] for it in golden if not it.get("answerable", True)] + NEGATIVES
    rows = [{"question": q, "positive": True, "dense_top": _top(store, embedder, embed_model, q)} for q in pos]
    rows += [{"question": q, "positive": False, "dense_top": _top(store, embedder, embed_model, q)} for q in neg]
    ps = sorted(r["dense_top"] for r in rows if r["positive"])
    ns = sorted(r["dense_top"] for r in rows if not r["positive"])
    if not ps or not ns:
        return {"tau": None, "reason": "musbat yoki manfiy savollar yoʻq", "rows": rows}
    # τ = the score of the positive at the (1 − keep) quantile, rounded down: ≥ keep of positives stay above
    i = max(0, int(len(ps) * (1 - keep)))
    tau = int(ps[i] * 100) / 100
    kept = sum(1 for x in ps if x >= tau) / len(ps)
    blocked = sum(1 for x in ns if x < tau) / len(ns)
    good = blocked >= 0.5
    desc = lambda xs: {"min": round(xs[0], 3), "median": round(statistics.median(xs), 3), "max": round(xs[-1], 3)}
    return {
        "method": "dense-top-cosine", "keep": keep, "tau": tau if good else None, "tau_candidate": tau,
        "positives_kept": round(kept, 3), "negatives_blocked": round(blocked, 3),
        "positives": {"n": len(ps), **desc(ps)}, "negatives": {"n": len(ns), **desc(ns)},
        "advice": (f"DENSE_TAU={tau} — javobi bor savollarning {kept:.0%} i oʻtadi, javobi yoʻqlarning {blocked:.0%} i "
                   "LLM’siz «Bilmayman» oladi" if good else
                   f"Ajratish kuchsiz ({blocked:.0%} < 50 %): τ tavsiya etilmaydi, «Bilmayman» LLM va tekshiruvga qoladi"),
        "rows": sorted(rows, key=lambda r: -r["dense_top"]),
    }


def write_env(root: Path, key: str, value: str | None) -> Path:
    """Sets (or removes, with value None) KEY=value in the project's .env, keeping every other line."""
    p = root / ".env"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    lines = [l for l in lines if not re.match(rf"\s*{re.escape(key)}\s*=", l)]
    if value is not None:
        lines.append(f"{key}={value}")
        os.environ[key] = value
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
