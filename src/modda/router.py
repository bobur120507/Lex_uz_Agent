"""Query router: an explicit reference ("MK 131-modda", "Mehnat kodeksining 195¹-moddasi",
"Konstitutsiyaning 27-moddasi") is looked up directly; everything else goes to hybrid search."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .textnorm import to_query_form, tokenize

# order matters: the procedural codes before the plain ones
CODES = [
    (r"jinoyat[- ]protsessual|\bjpk\b", "Jinoyat-protsessual kodeksi"),
    (r"fuqarolik protsessual|\bfpk\b", "Fuqarolik protsessual kodeksi"),
    (r"maʼmuriy javobgarlik|\bmjtk\b|\bmajk\b|\bmjk\b", "Maʼmuriy javobgarlik toʻgʻrisidagi kodeks"),
    (r"mehnat kodeks|\bmk\b", "Mehnat kodeksi"),
    (r"fuqarolik kodeks|\bfk\b", "Fuqarolik kodeksi"),
    (r"oila kodeks|\bok\b", "Oila kodeksi"),
    (r"jinoyat kodeks|\bjk\b", "Jinoyat kodeksi"),
    (r"soliq kodeks|\bsk\b", "Soliq kodeksi"),
    (r"uy-joy kodeks|\bujk\b", "Uy-joy kodeksi"),
    (r"yer kodeks|\byk\b", "Yer kodeksi"),
    (r"bojxona kodeks|\bbk\b", "Bojxona kodeksi"),
    (r"konstitutsiya", "Konstitutsiya"),
]
SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
ARTICLE_RE = re.compile(r"(\d+)(?:\s*[-‐]\s*(\d+)(?=\s*-?\s*modda)|([⁰¹²³⁴⁵⁶⁷⁸⁹]+)|\^(\d+))?\s*-?\s*modda", re.I)


@dataclass
class Route:
    kind: str                      # "exact" or "hybrid"
    normalized: str
    document: str | None = None    # title keyword of the code
    label: str | None = None       # "195-1"
    concepts: list[str] | None = None


def _label(m: re.Match) -> str:
    base, dash, sup, caret = m.group(1), m.group(2), m.group(3), m.group(4)
    if sup:
        return f"{base}-{''.join(str(SUPERSCRIPTS.index(c)) for c in sup)}"
    if dash or caret:
        return f"{base}-{dash or caret}"
    return base


def concepts(q: str, n: int = 5) -> list[str]:
    """The search terms shown to the user (stop words removed, longest first)."""
    seen, out = set(), []
    for t in sorted(tokenize(q), key=len, reverse=True):
        if t not in seen and not t.isdigit():
            seen.add(t)
            out.append(t)
    return out[:n]


def route(question: str) -> Route:
    q = to_query_form(question)
    low = q.lower()
    m = ARTICLE_RE.search(low)
    doc = next((title for pat, title in CODES if re.search(pat, low)), None)
    if m and doc:
        return Route("exact", q, doc, _label(m), concepts(q))
    return Route("hybrid", q, None, None, concepts(q))


def lookup(con, r: Route) -> list[str]:
    """chunk_ids of the referenced article (all its parts), or [] if not found."""
    if r.kind != "exact":
        return []
    kw = r.document
    types = ("constitution",) if kw == "Konstitutsiya" else ("code",)
    marks = ", ".join("?" for _ in types)
    doc = con.execute(
        "SELECT doc_id, COUNT(*) AS n FROM articles WHERE LOWER(doc_title) LIKE LOWER(?) "
        f"AND doc_type IN ({marks}) GROUP BY doc_id ORDER BY n DESC LIMIT 1", (f"%{kw}%", *types)).fetchone()
    if not doc:
        return []
    flat = r.label.replace("-", "")
    rows = con.execute(
        "SELECT c.chunk_id FROM chunks c JOIN articles a ON a.id = c.article_id WHERE a.doc_id = ? "
        "AND (a.article_label = ? OR (a.article_label IS NULL AND a.article_number = ?)) ORDER BY c.part_no",
        (doc["doc_id"], r.label, flat)).fetchall()
    if not rows:                     # the user typed the corpus form ("1951-modda")
        rows = con.execute(
            "SELECT c.chunk_id FROM chunks c JOIN articles a ON a.id = c.article_id WHERE a.doc_id = ? "
            "AND a.article_number = ? ORDER BY c.part_no", (doc["doc_id"], flat)).fetchall()
    return [x["chunk_id"] for x in rows]
