"""Lex.uz RSS (https://lex.uz/rss): newly published and amended acts.

Day 2: read the feed into `rss_items`. Day 3: a source whose document appears in the feed after the
corpus snapshot is marked `stale` («Lex.uz’da yaqinda oʻzgargan boʻlishi mumkin»).
The feed links to /docs/{id}; note that Lex.uz gives each language version its own id, so a Latin
document may be announced under its Cyrillic id — the title is stored too, to match by name later.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from .textnorm import normalize_uz

FEED = "https://lex.uz/rss"
UA = "Mozilla/5.0 (compatible; modda-research/0.1; educational student project)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rss_items (
    doc_id TEXT NOT NULL,
    title TEXT,
    link TEXT,
    published TEXT,
    seen_at TEXT,
    PRIMARY KEY (doc_id, published)
)
"""


def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        m = re.search(r"/docs/(-?\d+)", link)
        if not m:
            continue
        pub = it.findtext("pubDate")
        try:
            published = parsedate_to_datetime(pub).date().isoformat() if pub else None
        except (TypeError, ValueError):
            published = None
        items.append({"doc_id": m.group(1), "title": normalize_uz(it.findtext("title") or ""),
                      "link": link if link.startswith("http") else f"https://lex.uz{link}", "published": published})
    return items


def fetch(url: str = FEED, timeout: float = 30) -> list[dict]:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return parse_feed(r.text)


def store(con, items: list[dict]) -> int:
    from datetime import datetime, timezone
    con.script(SCHEMA)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.executemany(
        "INSERT INTO rss_items (doc_id, title, link, published, seen_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (doc_id, published) DO NOTHING",
        [(i["doc_id"], i["title"], i["link"], i["published"] or "", now) for i in items])
    con.commit()
    return len(items)


def stale_doc_ids(con, since: str | None) -> set[str]:
    """Documents announced in the feed after the snapshot date."""
    con.script(SCHEMA)
    rows = con.execute("SELECT doc_id FROM rss_items WHERE published > ?", (since or "",)).fetchall()
    return {r[0] for r in rows}
