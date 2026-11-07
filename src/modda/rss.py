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

from .textnorm import normalize_uz, tokenize

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


def stale_doc_ids(con, since: str | None) -> "StaleIndex":
    """Documents announced in the feed after the snapshot date (by id, and by title — see StaleIndex)."""
    con.script(SCHEMA)
    rows = con.execute("SELECT doc_id, title, link, published FROM rss_items WHERE published > ? ORDER BY published DESC",
                       (since or "",)).fetchall()
    return StaleIndex([{"doc_id": r[0], "title": r[1], "link": r[2], "published": r[3]} for r in rows])


# Words every act title has: they say nothing about WHICH act it is.
_GENERIC = {"oʻzbekiston", "respublika", "respublikas", "toʻgʻrisida", "qonun", "qaror", "farmon", "farmoyish",
            "prezident", "vazirlar", "mahkama", "mahkamas", "oliy", "majlis", "oʻzgartish", "oʻzgartirish",
            "qoʻshimcha", "qoʻshimchalar", "kiritish", "kiritilishi", "ayrim", "hujjat", "hujjatlar", "tasdiqlash",
            "yil", "sonli", "qarori", "qonuni", "farmoni", "chora", "tadbir", "tadbirlar", "toʻgʻrisidagi",
            "haqida", "yangi", "tahrir", "tahrirda", "boʻlgan", "oʻz", "kuchini", "yoʻqotgan", "deb", "topish",
            "son", "yildagi", "pq", "pf", "zru", "oʻrq", "vmq"}


def _key(title: str) -> list[str]:
    return [t for t in tokenize(title or "") if not t.isdigit() and len(t) >= 3 and not any(_same(t, g) for g in _GENERIC)]


def _same(a: str, b: str) -> bool:
    """Uzbek endings make «kodeksi» → «kodek» but «kodeksiga» → «kodeks»: compare by common prefix."""
    if len(a) < 4 or len(b) < 4:
        return a == b
    return a.startswith(b) or b.startswith(a)


class StaleIndex:
    """Which sources may have changed on Lex.uz since the snapshot.

    A source is stale when its document id was announced in the RSS feed, or when a feed item's title names
    it — amendments are published as a new act titled e.g. «Mehnat kodeksiga oʻzgartish kiritish toʻgʻrisida»,
    and a Latin document may be announced under its Cyrillic id. Name match: every distinctive word of the
    source's title (generic words such as «Oʻzbekiston», «qonun», «toʻgʻrisida» removed) occurs in the feed
    item's title; titles with more than 8 distinctive words need 80 %. A hint for the reader, not a verdict.
    """

    def __init__(self, items: list[dict]):
        self.items = items
        self.ids = {str(i["doc_id"]) for i in items}
        self._keys = [(set(_key(i.get("title") or "")), i) for i in items]

    def __contains__(self, doc_id) -> bool:          # old callers: `doc_id in stale_ids`
        return str(doc_id) in self.ids

    def __len__(self):
        return len(self.items)

    def lookup(self, doc_id, title: str | None) -> dict | None:
        for i in self.items:
            if str(i["doc_id"]) == str(doc_id):
                return {**i, "match": "id"}
        key = _key(title or "")
        if not key or (len(key) == 1 and len(key[0]) < 8):
            return None
        need = len(key) if len(key) <= 8 else int(len(key) * 0.8 + 0.999)
        for words, item in self._keys:
            if sum(1 for k in key if any(_same(k, w) for w in words)) >= need:
                return {**item, "match": "title"}
        return None
