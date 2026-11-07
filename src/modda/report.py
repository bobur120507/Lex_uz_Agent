"""The full evaluation report (roadmap: «Toʻliq baholash hisoboti») — built only from measured files in
data/reports, nothing typed by hand:

  setup-eval.json / eval.json   retrieval: Recall@5, MRR per mode (python -m modda eval)
  bakeoff-*.md                  LLM comparison (python -m modda bakeoff)
  calibration.json              τ for «Bilmayman» (python -m modda calibrate)
  demo-*.json                   the six demo questions (scripts/demo_questions.py)
  server-status.json            the machine and index it ran on (scripts/setup_server.py)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _latest(d: Path, pattern: str) -> Path | None:
    files = sorted(d.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _json(p: Path | None):
    if not p:
        return None
    try:
        text = p.read_text(encoding="utf-8")
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        return json.loads(text[min(starts):]) if starts else None
    except Exception:
        return None


def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f} %" if isinstance(x, (int, float)) and x <= 1 else str(x)


def build(reports: Path, golden_path: Path | None = None) -> tuple[Path, str]:
    md = [f"# Modda — baholash hisoboti", "", f"Yaratildi: {datetime.now():%Y-%m-%d %H:%M}. Hamma raqamlar `data/reports` dagi "
          "oʻlchov fayllaridan olingan.", ""]

    st = _json(reports / "server-status.json")
    if st:
        db = st.get("db") or {}
        md += ["## Muhit", "", f"* GPU: {st.get('gpu') or '—'}",
               f"* Baza: {db.get('articles', '—'):,} modda, {db.get('chunks', '—'):,} boʻlak, dense indeks {db.get('chunks_indexed', '—'):,}"
               if isinstance(db.get("articles"), int) else "* Baza: —",
               f"* Qdrant nuqtalari: {st.get('qdrant_points') or '—'}", ""]

    ev = _json(reports / "eval.json") or _json(reports / "setup-eval.json")
    if isinstance(ev, dict) and ev:
        md += ["## 1. Qidiruv sifati (oltin toʻplam)", "", "| Usul | Recall@5 | MRR | p50 kechikish |", "|---|---|---|---|"]
        for mode, r in ev.items():
            if not isinstance(r, dict):
                continue
            rec = next((v for k, v in r.items() if k.lower().startswith("recall")), None)
            md.append(f"| {mode} | {rec} | {r.get('mrr', r.get('MRR'))} | {r.get('p50_ms', r.get('p50', '—'))} |")
        md += ["", "Gibrid (dense + BM25, RRF) — standart rejim.", ""]

    bo = _latest(reports, "bakeoff-*.md")
    if bo:
        body = bo.read_text(encoding="utf-8").splitlines()
        md += ["## 2. LLM solishtiruvi (bakeoff)", "", *[l for l in body if not l.startswith("# ")], ""]

    cal = _json(reports / "calibration.json")
    if isinstance(cal, dict):
        p, n = cal.get("positives") or {}, cal.get("negatives") or {}
        md += ["## 3. «Bilmayman» chegarasi (τ)", "",
               f"Savol vektori bilan eng yaqin boʻlak oʻrtasidagi kosinus oʻxshashlik. Javobi bor savollar: {p.get('n')} ta "
               f"(min {p.get('min')}, median {p.get('median')}); javobi yoʻq: {n.get('n')} ta (median {n.get('median')}, max {n.get('max')}).",
               "", f"**{cal.get('advice', '—')}**", ""]

    demo = _json(_latest(reports, "demo-*.json")) if _latest(reports, "demo-*.json") else None
    if isinstance(demo, list) and demo:
        md += ["## 4. Demo savollar", "", "| # | Tur | Vaqt, s | Natija | Manbalar | Baho | LLM, token/s |", "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(demo, 1):
            res = "XATO" if r.get("error") else "Bilmayman" if r.get("unknown") else f"{len(r.get('answer') or [])} gap"
            if (r.get("llm") or {}).get("truncated"):
                res += " (LLM kesildi)"
            srcs = "; ".join(f"{(s.get('title') or '?')[:40]} {s.get('article') or ''}".strip() for s in (r.get("sources") or [])[:2]) or "—"
            md.append(f"| {i} | {r.get('kind')} | {r.get('seconds')} | {res} | {srcs} | {r.get('score') if r.get('score') is not None else '—'} "
                      f"| {(r.get('llm') or {}).get('tokens_per_s', '—')} |")
        md += ["", "Savollar va kutilgan natijalar: `scripts/demo_questions.py`.", ""]

    md += ["## Cheklovlar", "",
           "* Tarozi bahosi — soʻz mosligi (`lexical-support-v1`): javob manba matniga qanchalik yaqin, yuridik xulosa emas.",
           "* Korpus — Hugging Face’dagi Lex.uz nusxasi (qatʼiy versiya); undan keyingi oʻzgarishlar RSS orqali faqat belgilanadi.",
           "* Bu tizim yuridik maslahat bermaydi; rasmiy matn — lex.uz.", ""]
    text = "\n".join(md)
    out = reports / "BAHOLASH.md"
    out.write_text(text, encoding="utf-8")
    return out, text
