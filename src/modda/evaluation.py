"""Golden set, retrieval metrics (Recall@k, MRR) and the LLM bake-off.

Golden set line (data/golden/golden.jsonl):
{"id": "g001", "category": "aniq_modda", "question": "...", "answerable": true,
 "expected": [{"doc_id": "...", "article_number": "131"}], "answer_hint": "...", "notes": "..."}
`expected` may use "doc_title_contains" instead of "doc_id".
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

from .rag import answer as rag_answer, retrieve
from .textnorm import has_cyrillic


def load_golden(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Oltin toʻplam topilmadi: {path}")
    items = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{i}: JSON xatosi: {exc}") from exc
    return items


def only_indexed(con, items: list[dict]) -> tuple[list[dict], int]:
    """While only part of the corpus is indexed (e.g. `index --mvp`), score only the answerable questions
    whose expected article is already in the index; unanswerable questions are always kept."""
    total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    done = con.execute("SELECT COUNT(*) FROM chunks WHERE indexed = 1").fetchone()[0]
    if total and done >= total:
        return items, 0
    keep = []
    for it in items:
        if not it.get("answerable", True):
            keep.append(it)
            continue
        ok = any(con.execute(
            "SELECT 1 FROM chunks c JOIN articles a ON a.id = c.article_id WHERE c.indexed = 1 "
            "AND a.doc_id = ? AND a.article_number = ? LIMIT 1", (e["doc_id"], e["article_number"])).fetchone()
            for e in it.get("expected", []) if e.get("doc_id"))
        if ok:
            keep.append(it)
    return keep, len(items) - len(keep)


def spread(items: list[dict], n: int) -> list[dict]:
    """n questions spread over documents and categories (round-robin), ¼ of them unanswerable."""
    ans = [i for i in items if i.get("answerable", True)]
    no = [i for i in items if not i.get("answerable", True)]
    n_no = min(len(no), max(1, n // 4))
    groups: dict[str, list] = {}
    for it in ans:
        groups.setdefault(it["expected"][0].get("doc_id", "?") if it.get("expected") else "?", []).append(it)
    picked, queues = [], list(groups.values())
    while len(picked) < n - n_no and any(queues):
        for q in queues:
            if q and len(picked) < n - n_no:
                picked.append(q.pop(0))
    return picked + no[:n_no]


def matches(meta: dict, exp: dict) -> bool:
    if str(meta.get("article_number")) != str(exp.get("article_number")):
        return False
    if exp.get("doc_id"):
        return str(meta.get("doc_id")) == str(exp["doc_id"])
    if exp.get("doc_title_contains"):
        return exp["doc_title_contains"].lower() in (meta.get("doc_title") or "").lower()
    return False


def first_rank(contexts, expected: list[dict]) -> int | None:
    for c in contexts:
        if any(matches(c.meta, e) for e in expected):
            return c.n
    return None


def eval_retrieval(con, store, embedder, embed_model, items, k=5, modes=("dense",)) -> dict:
    report = {}
    for mode in modes:
        ranks, lat = [], []
        for it in items:
            if not it.get("answerable", True):
                continue
            t0 = time.perf_counter()
            ctx = retrieve(con, store, embedder, embed_model, it["question"], k, mode)
            lat.append(time.perf_counter() - t0)
            ranks.append(first_rank(ctx, it["expected"]))
        n = len(ranks) or 1
        lat.sort()
        report[mode] = {
            "questions": len(ranks),
            f"recall@{k}": round(sum(r is not None for r in ranks) / n, 3),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
            "p50_s": round(lat[len(lat) // 2], 3) if lat else None,
            "p95_s": round(lat[int(len(lat) * 0.95) - 1], 3) if lat else None,
        }
    return report


def bakeoff(con, store, embedder, llm, *, embed_model: str, models: list[str], items: list[dict],
            out_dir: Path, k: int = 5) -> Path:
    """Same retrieved context for every model, so only the LLM differs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M")
    rows = []
    prepared = [(it, retrieve(con, store, embedder, embed_model, it["question"], k)) for it in items]
    for model in models:
        print(f"\n== {model}")
        for it, ctx in prepared:
            try:
                ans = rag_answer(con, store, embedder, llm, embed_model=embed_model, llm_model=model,
                                 question=it["question"], contexts=ctx)
                err = ""
            except Exception as exc:
                ans, err = None, str(exc)[:200]
            answerable = it.get("answerable", True)
            if ans is None:
                rows.append({"model": model, "id": it["id"], "category": it.get("category"), "error": err})
                continue
            metas = {c.chunk_id: c.meta for c in ctx}
            cited_ok = any(matches(metas.get(cid, {}), e) for cid in ans.sources for e in it.get("expected", []))
            rows.append({
                "model": model, "id": it["id"], "category": it.get("category"), "answerable": answerable,
                "retrieved_ok": first_rank(ctx, it.get("expected", [])) is not None if answerable else "",
                "unknown": ans.unknown, "cited_expected": cited_ok if answerable else "",
                "false_answer": (not answerable and not ans.unknown),
                "cyrillic": has_cyrillic(ans.text), "seconds": round(ans.llm_seconds, 2),
                "answer": ans.text.replace("\n", " ")[:600], "error": "",
                "truncated": bool((getattr(llm, "last_chat", None) or {}).get("truncated")),
            })
            mark = "✓" if (cited_ok if answerable else ans.unknown) else "✗"
            print(f"  {mark} {it['id']} {ans.llm_seconds:5.1f}s  {ans.text[:80]!r}")

    csv_path = out_dir / f"bakeoff-{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader()
        w.writerows(rows)

    md = [f"# Modellar solishtiruvi — {stamp}", "", f"Savollar: {len(items)}, kontekst: top-{k} (dense)", "",
          "| Model | Toʻgʻri manba (javobi bor) | Toʻgʻri «Bilmayman» (javobi yoʻq) | Yolgʻon javob | Kirill harflar | Oʻrtacha vaqt, s | Xato | Kesilgan |",
          "|---|---|---|---|---|---|---|---|"]
    for model in models:
        rs = [r for r in rows if r["model"] == model and not r.get("error")]
        ans_rs = [r for r in rs if r["answerable"]]
        no_rs = [r for r in rs if not r["answerable"]]
        pct = lambda a, b: f"{a}/{b}" if b else "—"
        md.append(f"| `{model}` | {pct(sum(r['cited_expected'] for r in ans_rs), len(ans_rs))} | "
                  f"{pct(sum(r['unknown'] for r in no_rs), len(no_rs))} | {sum(r['false_answer'] for r in rs)} | "
                  f"{sum(r['cyrillic'] for r in rs)} | "
                  f"{(sum(r['seconds'] for r in rs) / len(rs)) if rs else 0:.1f} | "
                  f"{sum(1 for r in rows if r['model'] == model and r.get('error'))} | {sum(bool(r.get('truncated')) for r in rs)} |")
    md += ["", "LLM «fikrlash» (think) oʻchirilgan; *Kesilgan* — javob token chegarasiga yetgan savollar.",
           "", "**Tanlash qoidasi:** avval eng kam *yolgʻon javob*, keyin eng koʻp *toʻgʻri manba*, keyin tezlik.",
           "Javoblarni CSV faylida koʻzdan kechiring: oʻzbek tili sifati raqamlarda koʻrinmaydi.", ""]
    md_path = out_dir / f"bakeoff-{stamp}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    return md_path


def bakeoff_pick(md: str) -> tuple[str | None, list[dict]]:
    """Reads a bakeoff-*.md table and applies its rule: fewest false answers, then most correct sources,
    then fewest errors, then the fastest. Returns (model, parsed rows)."""
    rows = []
    for line in md.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|(.*)\|\s*$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 6:
            continue
        frac = lambda c: (int(c.split("/")[0]) / int(c.split("/")[1])) if "/" in c and c.split("/")[1] != "0" else 0.0
        try:
            rows.append({"model": m.group(1), "correct": frac(cells[0]), "unknown_ok": frac(cells[1]),
                         "false": int(cells[2]), "seconds": float(cells[4]), "errors": int(cells[5])})
        except ValueError:
            continue
    if not rows:
        return None, rows
    best = min(rows, key=lambda r: (r["false"], -r["correct"], r["errors"], r["seconds"]))
    return best["model"], rows
