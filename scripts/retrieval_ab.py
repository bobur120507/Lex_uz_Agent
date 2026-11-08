"""Retrieval-only A/B: two-part questions searched whole (A) or also by halves (B) — on the real index, no LLM (≈ 1 min).

The sandbox cannot decide this (its embeddings are random hashes, so each half's «best hit» there is noise), so the GPU
laptop measures it on the 100-question test set before the final test (`scripts\\day6.bat`, part «ab») and sets
SPLIT_QUESTIONS in .env: on only when B finds all articles of multi-article questions at least as often as A and loses
nothing on the whole set (Hit@5 article −0.5 pp, MRR −0.01 at most). Russian questions are skipped (the API translates
them before searching; here both variants would search Russian text).

    python scripts/retrieval_ab.py [--testset data/testset/test100.csv] [--write-env]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from modda import service                          # noqa: E402  (loads .env)
from modda.config import get_settings               # noqa: E402
from modda.llm import Ollama                        # noqa: E402
from modda.rag import retrieve, split_question       # noqa: E402
from modda.textnorm import to_query_form             # noqa: E402

dig = lambda x: re.sub(r"\D", "", str(x or ""))
art = lambda x: (re.search(r"\d+(?:\^\d+)?", str(x or "")) or [""])[0]


def measure(rows, con, store, emb, S, split: bool, mode: str) -> dict:
    hit_doc, hit_art, rr, multi_all, per = [], [], [], [], {}
    for r in rows:
        ctx = retrieve(con, store, emb, S.embed_model, r["question"], 5, mode, split=split)
        top = [(dig(c.meta.get("doc_id")), art(c.meta.get("article_label") or c.meta.get("article_number"))) for c in ctx[:5]]
        exp = set(r["pairs"])
        ranks = [i for i, t in enumerate(top, 1) if t in exp]
        hit_doc.append(any(d in {e[0] for e in exp} for d, _ in top))
        hit_art.append(bool(ranks))
        rr.append(1 / ranks[0] if ranks else 0.0)
        if len(exp) > 1:
            multi_all.append(exp <= set(top))
        per[r["id"]] = ranks[0] if ranks else None
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    return {"hit5_doc": avg(hit_doc), "hit5_article": avg(hit_art), "mrr": avg(rr), "multi_all_found": avg(multi_all),
            "n": len(rows), "n_multi": len(multi_all), "rank": per}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default=str(ROOT / "data" / "testset" / "test100.csv"))
    ap.add_argument("--write-env", action="store_true")
    a = ap.parse_args()
    S = get_settings()
    rows = []
    for r in csv.DictReader(open(a.testset, encoding="utf-8")):
        if str(r["answerable"]).lower() != "true" or r.get("language") == "ru":
            continue
        docs = [d for d in r["expected_doc_id"].split(";") if d]
        arts = [x for x in r["expected_article"].split(";") if x]
        docs = docs * len(arts) if len(docs) == 1 else docs
        r["pairs"] = [(dig(d), art(x)) for d, x in zip(docs, arts)]
        rows.append(r)
    mode = "hybrid_auth" if os.environ.get("AUTHORITY_PRIOR", "off").lower() in ("on", "1", "true") else "hybrid"
    con, store, emb = service._con(), service._store(), Ollama(S.ollama_url)
    try:
        A = measure(rows, con, store, emb, S, False, mode)
        B = measure(rows, con, store, emb, S, True, mode)
    finally:
        con.close()
    n_split = sum(1 for r in rows if split_question(to_query_form(r["question"])))
    on = (B["multi_all_found"] or 0) >= (A["multi_all_found"] or 0) and B["hit5_article"] >= A["hit5_article"] - 0.005 \
        and B["mrr"] >= A["mrr"] - 0.01
    changed = {i: (A["rank"][i], B["rank"][i]) for i in A["rank"] if A["rank"][i] != B["rank"][i]}
    print(f"Retrieval A/B ({len(rows)} savol, {n_split} tasi ikki qismli; rejim {mode}):")
    for k in ("hit5_doc", "hit5_article", "mrr", "multi_all_found"):
        print(f"  {k:16} A (butun savol) {A[k]}   B (+ yarmlari) {B[k]}")
    print(f"  oʻzgargan savollar (toʻgʻri modda oʻrni A → B): {changed or 'yoʻq'}")
    print(f"  Qaror: SPLIT_QUESTIONS={'on' if on else 'off'}")
    out = {"mode": mode, "A_whole": {k: v for k, v in A.items() if k != "rank"}, "B_split": {k: v for k, v in B.items() if k != "rank"},
           "changed": changed, "decision": "on" if on else "off"}
    (ROOT / "data" / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "reports" / "retrieval_ab.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.write_env:
        env = ROOT / ".env"
        lines = [l for l in (env.read_text(encoding="utf-8").splitlines() if env.exists() else []) if not l.startswith("SPLIT_QUESTIONS=")]
        env.write_text("\n".join(lines + [f"SPLIT_QUESTIONS={'on' if on else 'off'}"]) + "\n", encoding="utf-8")
        print("  .env ga yozildi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
