"""Day-1 helper jobs: real articles for writing the golden set, and Lex.uz pages for the parser tests."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import requests

from .textnorm import normalize_uz

# The documents people ask about most. The biggest matching act is taken (the code itself, not a
# short law that amends it).
KEY_DOCUMENTS = [
    ("Konstitutsiya", ("constitution",)),
    ("Mehnat kodeksi", ("code",)),
    ("Fuqarolik kodeksi", ("code",)),
    ("Oila kodeksi", ("code",)),
    ("Jinoyat kodeksi", ("code",)),
    ("Soliq kodeksi", ("code",)),
    ("Maʼmuriy javobgarlik toʻgʻrisidagi kodeks", ("code",)),
    ("Uy-joy kodeksi", ("code",)),
    ("Yer kodeksi", ("code",)),
    ("Bojxona kodeksi", ("code",)),
    ("Taʼlim toʻgʻrisida", ("law",)),
    ("Isteʼmolchilarning huquqlarini himoya qilish", ("law",)),
    ("Shaxsga doir maʼlumotlar", ("law",)),
    ("Yoʻl harakati xavfsizligi", ("law",)),
]

UA = "Mozilla/5.0 (compatible; modda-research/0.1; educational student project)"
CRAWL_DELAY = 20          # lex.uz robots.txt: Crawl-delay: 20


def pick_documents(con) -> list[dict]:
    out = []
    for kw, types in KEY_DOCUMENTS:
        marks = ", ".join("?" for _ in types)
        rows = con.execute(
            "SELECT doc_id, doc_title, doc_type, MAX(source_url) AS source_url, COUNT(*) AS n FROM articles "
            f"WHERE LOWER(doc_title) LIKE LOWER(?) AND doc_type IN ({marks}) "
            "GROUP BY doc_id, doc_title, doc_type ORDER BY n DESC LIMIT 1",
            (f"%{normalize_uz(kw)}%", *types)).fetchall()
        if rows:
            out.append({"keyword": kw, **dict(rows[0])})
        else:
            out.append({"keyword": kw, "doc_id": None})
    return out


def export_golden(con, out_dir: Path, per_doc: int = 6, seed: int = 7) -> Path:
    """Real, clean, short-to-medium articles from the key documents → data/reports/golden-candidates.jsonl"""
    rnd = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "golden-candidates.jsonl"
    docs = pick_documents(con)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for d in docs:
            if not d.get("doc_id"):
                print(f"  ✗ topilmadi: {d['keyword']}")
                continue
            rows = con.execute(
                "SELECT id, doc_id, doc_title, doc_type, doc_date, chapter, article_number, article_title, article_text, "
                "source_url FROM articles WHERE doc_id = ? AND COALESCE(quality_flag, '') = '' "
                "AND length(article_text) BETWEEN 150 AND 1600", (d["doc_id"],)).fetchall()
            rows = [dict(r) for r in rows]
            rnd.shuffle(rows)
            for r in rows[:per_doc]:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                n += 1
            print(f"  ✓ {d['keyword']}: «{d['doc_title'][:70]}» ({d['n']} modda) → {min(per_doc, len(rows))} ta")
    # every document's list too, so questions can be checked against the right act
    (out_dir / "golden-documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{n} ta modda → {path}")
    return path


def fetch_fixtures(con, out_dir: Path, limit: int = 10) -> list[Path]:
    """Save a few real Lex.uz pages for the HTML parser tests (day 2). Waits 20 s between pages."""
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = []
    for d in pick_documents(con):
        if d.get("source_url"):
            urls.append((d["doc_id"], d["source_url"]))
    for t in ("decree", "resolution", "order"):
        r = con.execute("SELECT doc_id, MAX(source_url) AS u FROM articles WHERE doc_type = ? "
                        "GROUP BY doc_id ORDER BY doc_id LIMIT 1", (t,)).fetchone()
        if r:
            urls.append((r["doc_id"], r["u"]))
    seen, saved = set(), []
    session = requests.Session()
    session.headers["User-Agent"] = UA
    for doc_id, url in urls:
        if doc_id in seen or len(saved) >= limit:
            continue
        seen.add(doc_id)
        path = out_dir / f"{str(doc_id).lstrip('-')}.html"
        if path.exists():
            saved.append(path)
            continue
        if saved:
            time.sleep(CRAWL_DELAY)
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
        except requests.RequestException as exc:
            print(f"  ✗ {url}: {exc}")
            continue
        path.write_text(r.text, encoding="utf-8")
        saved.append(path)
        print(f"  ✓ {url} → {path.name} ({len(r.text) // 1024} KB)")
    return saved
