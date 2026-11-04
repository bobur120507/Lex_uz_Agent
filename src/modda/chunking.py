"""Structural chunking: one article = one chunk; long articles are split by paragraphs with overlap.

Every chunk carries a contextual header (document › chapter › article) that is embedded together
with the text, so "3-modda" from the Labour Code is not confused with "3-modda" of another law.
"""

from __future__ import annotations

import re

MAX_WORDS = 380          # ~600–700 bge-m3 tokens of Uzbek text
OVERLAP_WORDS = 60       # words repeated from the previous part

# MVP subset: the Constitution and the codes (HF `doc_type` values are English: code, constitution, law, …)
MVP_TYPES = {"code", "constitution"}
MVP_TITLE_RE = re.compile(r"konstitutsiya|kodeksi?\b", re.I)


def is_flat(art: dict) -> bool:
    """Acts without article structure (most decrees and resolutions) are one flat-text row."""
    return (art.get("quality_flag") == "no-articles" or not art.get("article_number")
            or str(art.get("id", "")).endswith("-full"))


def is_mvp(art: dict) -> bool:
    return (art.get("doc_type") or "").lower() in MVP_TYPES or bool(MVP_TITLE_RE.search(art.get("doc_title") or ""))


def header_for(art: dict) -> str:
    parts = [art.get("doc_title") or ""]
    for key in ("part", "chapter"):
        if art.get(key):
            parts.append(art[key])
    if not is_flat(art):
        title = art.get("article_title") or ""
        parts.append(f"{art['article_number']}-modda. {title}".strip())
    return " › ".join(p for p in parts if p)


def _words(s: str) -> int:
    return len(s.split())


def split_text(text: str, max_words: int = MAX_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Split by paragraphs (then sentences) into windows ≤ max_words; each window after the first
    starts with the last `overlap` words of the previous one."""
    if _words(text) <= max_words:
        return [text]
    units: list[str] = []
    for para in [p.strip() for p in text.split("\n") if p.strip()]:
        if _words(para) <= max_words:
            units.append(para)
        else:
            units.extend(s.strip() for s in re.split(r"(?<=[.;:])\s+", para) if s.strip())
    # a single sentence may still be too long: hard-cut it by words
    final: list[str] = []
    for u in units:
        w = u.split()
        if len(w) <= max_words:
            final.append(u)
        else:
            final.extend(" ".join(w[i:i + max_words]) for i in range(0, len(w), max_words))

    chunks, cur = [], []
    for u in final:
        if cur and _words("\n".join(cur + [u])) > max_words:
            chunks.append("\n".join(cur))
            tail = " ".join(" ".join(cur).split()[-overlap:]) if overlap else ""
            cur = [tail] if tail else []
            if _words("\n".join(cur + [u])) > max_words:
                cur = []
        cur.append(u)
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def chunks_for_article(art: dict) -> list[dict]:
    header = header_for(art)
    pieces = split_text(art["article_text"])
    mvp = 1 if is_mvp(art) else 0
    out = []
    for i, piece in enumerate(pieces, start=1):
        cid = art["id"] if len(pieces) == 1 else f"{art['id']}#p{i}"
        out.append({
            "chunk_id": cid, "article_id": art["id"], "part_no": i, "parts_total": len(pieces),
            "header": header, "text": piece, "n_words": _words(piece), "mvp": mvp,
        })
    return out


def build_chunks(con, rebuild: bool = False, page: int = 1000) -> int:
    """Chunk every article that has no chunks yet. Reads articles page by page (keyset), so memory stays
    small even with 47 M words of text."""
    if rebuild:
        con.execute("DELETE FROM chunks")
        con.commit()
    sql = ("INSERT INTO chunks (chunk_id, article_id, part_no, parts_total, header, text, n_words, mvp) "
           "VALUES (:chunk_id, :article_id, :part_no, :parts_total, :header, :text, :n_words, :mvp) "
           "ON CONFLICT (chunk_id) DO NOTHING")
    n, last = 0, ""
    while True:
        rows = con.execute(
            "SELECT a.* FROM articles a WHERE a.id > ? AND NOT EXISTS "
            "(SELECT 1 FROM chunks c WHERE c.article_id = a.id) ORDER BY a.id LIMIT ?", (last, page)).fetchall()
        if not rows:
            break
        buf = [ch for r in rows for ch in chunks_for_article(dict(r))]
        con.executemany(sql, buf)
        con.commit()
        n += len(buf)
        last = rows[-1]["id"]
    return n


def embed_text(chunk: dict) -> str:
    """What the embedding model and BM25 see: header + text."""
    return f"{chunk['header']}\n{chunk['text']}"
