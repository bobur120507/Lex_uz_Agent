"""Hugging Face corpus (sukhrobnurali/uzbek-legal-corpus) → normalized SQLite.

The `articles` config has one row per article with these fields:
id, act_group_id, doc_id, doc_title, doc_type, doc_number, doc_date, version_date, status, part,
chapter, article_number, article_title, article_text, amendment_note, cross_references, language,
script, okoz_codes, tsz_codes, source_url, n_tokens, quality_flag

Files may be Parquet or JSON Lines (optionally .gz); we detect the articles files by their columns.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Iterable, Iterator

from .db import Database
from .textnorm import cyr_to_lat, has_cyrillic, normalize_uz

ARTICLE_FIELDS = [
    "id", "act_group_id", "doc_id", "doc_title", "doc_type", "doc_number", "doc_date", "version_date",
    "status", "part", "chapter", "article_number", "article_title", "article_text", "amendment_note",
    "cross_references", "language", "script", "okoz_codes", "tsz_codes", "source_url", "n_tokens",
    "quality_flag",
]
REQUIRED = {"doc_id", "doc_title", "article_number", "article_text"}
TEXT_FIELDS = ("doc_title", "doc_type", "part", "chapter", "article_title", "article_text", "amendment_note")

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    act_group_id TEXT, doc_id TEXT, doc_title TEXT, doc_type TEXT, doc_number TEXT,
    doc_date TEXT, version_date TEXT, status TEXT, part TEXT, chapter TEXT,
    article_number TEXT, article_title TEXT, article_text TEXT, amendment_note TEXT,
    cross_references TEXT, language TEXT, script TEXT, okoz_codes TEXT, tsz_codes TEXT,
    source_url TEXT, n_tokens INTEGER, quality_flag TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_doc ON articles(doc_id, article_number);
CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(doc_title);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL REFERENCES articles(id),
    part_no INTEGER NOT NULL,
    parts_total INTEGER NOT NULL,
    header TEXT NOT NULL,
    text TEXT NOT NULL,
    n_words INTEGER NOT NULL,
    mvp INTEGER NOT NULL DEFAULT 0,
    indexed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_article ON chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_chunks_pending ON chunks(indexed, mvp);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def connect(db_path: Path | None = None, url: str | None = None) -> Database:
    """PostgreSQL when `url` (DATABASE_URL) is set, otherwise SQLite at `db_path` (used by the tests)."""
    db = Database(url=url, sqlite_path=db_path)
    db.script(SCHEMA)
    db.add_column("articles", "seq", "INTEGER")             # position in the corpus (document order)
    db.add_column("articles", "article_label", "TEXT")      # "195-1" for 195¹ (corpus stores "1951")
    db.script("CREATE INDEX IF NOT EXISTS idx_articles_label ON articles(doc_id, article_label)")
    return db


def set_meta(con: Database, key: str, value: str) -> None:
    con.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value))


# --------------------------------------------------------------------------- reading files

def _iter_jsonl(path: Path) -> Iterator[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _iter_parquet(path: Path, batch_size: int = 5000) -> Iterator[dict]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:          # pragma: no cover - depends on the machine
        raise SystemExit("Parquet oʻqish uchun: pip install pyarrow") from exc
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size):
        yield from batch.to_pylist()


def _columns(path: Path) -> set[str]:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        return set(pq.ParquetFile(path).schema_arrow.names)
    first = next(_iter_jsonl(path), {})
    return set(first)


def find_article_files(corpus_dir: Path) -> list[Path]:
    """All Parquet/JSONL files under corpus_dir whose columns look like the `articles` config."""
    candidates = sorted(
        p for p in corpus_dir.rglob("*")
        if p.is_file() and (p.suffix == ".parquet" or p.name.endswith((".jsonl", ".jsonl.gz", ".json.gz")))
        and "manifest" not in p.name and ".cache" not in p.parts
    )
    found = []
    for p in candidates:
        try:
            cols = _columns(p)
        except Exception:
            continue
        if REQUIRED <= cols and "full_text" not in cols:
            found.append(p)
    return found


def iter_articles(files: Iterable[Path]) -> Iterator[dict]:
    for p in files:
        yield from (_iter_parquet(p) if p.suffix == ".parquet" else _iter_jsonl(p))


# --------------------------------------------------------------------------- cleaning

def _as_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False)
    if hasattr(value, "tolist"):                     # numpy arrays from parquet
        return json.dumps(value.tolist(), ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def clean_article(row: dict) -> dict:
    out = {f: row.get(f) for f in ARTICLE_FIELDS}
    for f in TEXT_FIELDS:
        v = out.get(f)
        if isinstance(v, str):
            if has_cyrillic(v) and (out.get("script") or "").lower().startswith("cyr"):
                v = cyr_to_lat(v)
            out[f] = normalize_uz(v)
    for f in ("okoz_codes", "tsz_codes", "cross_references"):
        out[f] = _as_text(out.get(f))
    for f in ("id", "act_group_id", "doc_id", "article_number", "doc_number", "doc_date", "version_date",
              "status", "language", "script", "source_url", "quality_flag"):
        v = out.get(f)
        out[f] = None if v is None else str(v).strip()
    if not out["id"]:
        out["id"] = f"{out['doc_id']}:{out['article_number']}"
    try:
        out["n_tokens"] = int(out["n_tokens"]) if out.get("n_tokens") is not None else None
    except (TypeError, ValueError):
        out["n_tokens"] = None
    return out


def ingest(corpus_dir: Path, con: Database, limit: int | None = None, batch: int = 2000) -> int:
    files = find_article_files(corpus_dir)
    if not files:
        raise SystemExit(
            f"{corpus_dir} ichida `articles` fayllari topilmadi. Avval yuklab oling:\n"
            "  huggingface-cli download sukhrobnurali/uzbek-legal-corpus --repo-type dataset "
            f"--local-dir {corpus_dir}"
        )
    cols = ", ".join(ARTICLE_FIELDS)
    marks = ", ".join("?" for _ in ARTICLE_FIELDS)
    cols += ", seq"
    marks += ", ?"
    updates = ", ".join(f"{f} = excluded.{f}" for f in ARTICLE_FIELDS + ["seq"] if f != "id")
    sql = f"INSERT INTO articles ({cols}) VALUES ({marks}) ON CONFLICT (id) DO UPDATE SET {updates}"
    n, buf, seen = 0, [], {}
    for row in iter_articles(files):
        art = clean_article(row)
        if not art.get("article_text"):
            continue
        # ~1 300 rows share an id with another row (same article number twice in one act, mostly
        # `parse-uncertain`); keep every row and make the id unique: "…-a12", "…-a12~2"
        k = seen.get(art["id"], 0) + 1
        seen[art["id"]] = k
        if k > 1:
            art["id"] = f"{art['id']}~{k}"
        buf.append([art[f] for f in ARTICLE_FIELDS] + [n])
        n += 1
        if len(buf) >= batch:
            con.executemany(sql, buf)
            buf.clear()
        if limit and n >= limit:
            break
    if buf:
        con.executemany(sql, buf)
    set_meta(con, "source_files", json.dumps([str(f) for f in files]))
    con.commit()
    return n


def fix_numbers(con: Database) -> dict:
    """Restore superscript article numbers (corpus "1951" → label "195-1") from document order."""
    from .lexparse import repair_labels
    if con.execute("SELECT COUNT(*) FROM articles WHERE seq IS NULL").fetchone()[0]:
        raise SystemExit("Avval korpusni qayta yuklang (tartib raqami kerak): python -m modda ingest")
    rows = con.execute("SELECT id, doc_id, article_number FROM articles "
                       "WHERE COALESCE(quality_flag, '') <> 'no-articles' ORDER BY doc_id, seq").fetchall()
    updates, changed, docs = [], 0, 0
    i = 0
    while i < len(rows):
        j = i
        while j < len(rows) and rows[j]["doc_id"] == rows[i]["doc_id"]:
            j += 1
        group = rows[i:j]
        labels = repair_labels([r["article_number"] for r in group])
        for r, lab in zip(group, labels):
            updates.append((lab, r["id"]))
            changed += lab != (r["article_number"] or "")
        docs += 1
        i = j
    con.executemany("UPDATE articles SET article_label = ? WHERE id = ?", updates)
    con.commit()
    return {"documents": docs, "articles": len(updates), "superscript_restored": changed}


def stats(con: Database) -> dict:
    q = lambda sql: con.execute(sql).fetchall()
    return {
        "articles": q("SELECT COUNT(*) FROM articles")[0][0],
        "documents": q("SELECT COUNT(DISTINCT doc_id) FROM articles")[0][0],
        "chunks": q("SELECT COUNT(*) FROM chunks")[0][0],
        "chunks_mvp": q("SELECT COUNT(*) FROM chunks WHERE mvp=1")[0][0],
        "chunks_indexed": q("SELECT COUNT(*) FROM chunks WHERE indexed=1")[0][0],
        "chunks_sparse_only": q("SELECT COUNT(*) FROM chunks WHERE indexed=2")[0][0],
        "doc_types": [r.values_tuple() for r in q("SELECT doc_type, COUNT(*) AS c FROM articles GROUP BY 1 ORDER BY 2 DESC LIMIT 15")],
        "status": [r.values_tuple() for r in q("SELECT status, COUNT(*) AS c FROM articles GROUP BY 1 ORDER BY 2 DESC LIMIT 10")],
        "language": [r.values_tuple() for r in q("SELECT language, script, COUNT(*) AS c FROM articles GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10")],
        "quality": [r.values_tuple() for r in q("SELECT quality_flag, COUNT(*) AS c FROM articles GROUP BY 1 ORDER BY 2 DESC LIMIT 10")],
        "chunks_by_type": [r.values_tuple() for r in q("SELECT a.doc_type, COUNT(*) AS n FROM chunks c JOIN articles a ON a.id = c.article_id GROUP BY 1 ORDER BY 2 DESC")],
        "tokens_total": q("SELECT COALESCE(SUM(n_tokens), 0) FROM articles")[0][0],
    }
