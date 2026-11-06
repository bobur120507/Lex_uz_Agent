"""Reading the corpus like a book: an article with its neighbours, documents and their articles.

Used by the website's book pages (the found modda among ±5 neighbouring moddas) and the «Hujjatlar» page.
All text comes straight from the database — the official wording, unchanged.
"""

from __future__ import annotations

from .lexparse import label_display


def _article(r, target_id: str | None = None) -> dict:
    flat = (r["quality_flag"] or "") == "no-articles"
    label = r["article_label"] or r["article_number"]
    return {
        "article_id": r["id"], "seq": r["seq"], "label": None if flat else label_display(label or ""),
        "title": r["article_title"], "chapter": r["chapter"], "part": r["part"], "text": r["article_text"],
        "amendment_note": r["amendment_note"], "is_target": r["id"] == target_id,
    }


def _doc(r) -> dict:
    return {"doc_id": r["doc_id"], "title": r["doc_title"], "doc_type": r["doc_type"], "doc_number": r["doc_number"],
            "doc_date": r["doc_date"], "version_date": r["version_date"], "status": r["status"], "url": r["source_url"]}


COLS = ("id, seq, doc_id, doc_title, doc_type, doc_number, doc_date, version_date, status, part, chapter, "
        "article_number, article_label, article_title, article_text, amendment_note, source_url, quality_flag")


def chunk_context(con, chunk_id: str, n: int = 5) -> dict | None:
    """The article holding this chunk, plus up to n articles before and after it in the same document."""
    row = con.execute(f"SELECT c.chunk_id, c.part_no, c.parts_total, a.id AS aid FROM chunks c "
                      f"JOIN articles a ON a.id = c.article_id WHERE c.chunk_id = ?", (chunk_id,)).fetchone()
    if not row:
        return None
    return article_context(con, row["aid"], n) | {"chunk_id": chunk_id, "part_no": row["part_no"],
                                                   "parts_total": row["parts_total"]}


def article_context(con, article_id: str, n: int = 5) -> dict:
    a = con.execute(f"SELECT {COLS} FROM articles WHERE id = ?", (article_id,)).fetchone()
    if a is None:
        raise KeyError(article_id)
    n = max(0, min(int(n), 10))
    if a["seq"] is None:                                # corpus ingested before `seq` existed: only the article itself
        return {"document": _doc(a), "articles": [_article(a, article_id)], "neighbours": 0}
    before = con.execute(f"SELECT {COLS} FROM articles WHERE doc_id = ? AND seq < ? ORDER BY seq DESC LIMIT ?",
                         (a["doc_id"], a["seq"], n)).fetchall()
    after = con.execute(f"SELECT {COLS} FROM articles WHERE doc_id = ? AND seq > ? ORDER BY seq LIMIT ?",
                        (a["doc_id"], a["seq"], n)).fetchall()
    rows = list(reversed(before)) + [a] + list(after)
    return {"document": _doc(a), "articles": [_article(r, article_id) for r in rows], "neighbours": n}


def search_documents(con, q: str = "", limit: int = 20, doc_type: str | None = None) -> list[dict]:
    q = (q or "").strip()
    where, args = [], []
    if q:
        where.append("LOWER(doc_title) LIKE ?")
        args.append(f"%{q.lower()}%")
    if doc_type:
        where.append("doc_type = ?")
        args.append(doc_type)
    sql = ("SELECT doc_id, MIN(doc_title) AS doc_title, MIN(doc_type) AS doc_type, MIN(doc_number) AS doc_number, "
           "MIN(doc_date) AS doc_date, MIN(source_url) AS source_url, COUNT(*) AS n FROM articles"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " GROUP BY doc_id ORDER BY COUNT(*) DESC, MIN(doc_title) LIMIT ?")
    rows = con.execute(sql, (*args, max(1, min(int(limit), 100)))).fetchall()
    return [{"doc_id": r["doc_id"], "title": r["doc_title"], "doc_type": r["doc_type"], "doc_number": r["doc_number"],
             "doc_date": r["doc_date"], "url": r["source_url"], "articles": r["n"]} for r in rows]


def document_articles(con, doc_id: str, offset: int = 0, limit: int = 20) -> dict:
    rows = con.execute(f"SELECT {COLS} FROM articles WHERE doc_id = ? ORDER BY seq, id LIMIT ? OFFSET ?",
                       (doc_id, max(1, min(int(limit), 100)), max(0, int(offset)))).fetchall()
    if not rows:
        raise KeyError(doc_id)
    total = con.execute("SELECT COUNT(*) FROM articles WHERE doc_id = ?", (doc_id,)).fetchone()[0]
    return {"document": _doc(rows[0]), "total": total, "offset": offset,
            "articles": [_article(r) for r in rows]}
