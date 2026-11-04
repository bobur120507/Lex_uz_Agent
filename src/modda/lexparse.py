"""Parser for Lex.uz document pages (https://lex.uz/uz/docs/{id}).

Page structure (checked on 10 saved pages, tests/fixtures/lexuz/):
  ACT_TITLE              title of the act
  TEXT_HEADER_DEFAULT    part / chapter headings ("BIRINCHI BOʻLIM", "I bob. …")
  CLAUSE_DEFAULT         article heading: "195<sup>1</sup>-modda. Title"
  ACT_TEXT               a paragraph of the article
  CHANGES_ORIGINS        amendment note "(… tahririda …)"
  COMMENT / COMMENTLEXUZ «LexUZ sharhi» — editorial commentary, NOT official text: skipped
  INDEXES_ON_REF         OKOZ classifier codes

Article numbers keep their superscript: "195<sup>1</sup>" → label "195-1" (shown as 195¹).
The HF corpus flattened these to "1951"; `flat_number` gives that form for matching.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from .textnorm import normalize_uz

BLOCK_RE = re.compile(r'<div class="([A-Z_]+) (?:lx_elem|lx_no_select)"')
INNER_RE = re.compile(r'<div name="[^"]*" id="(-?\d+)">(.*?)</div>\s*</div>', re.S)
HEADING_RE = re.compile(r"^\s*(\d+)(?:\^(\d+))?\s*-\s*modda\.?\s*(.*)$", re.S)
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _text(fragment: str) -> str:
    fragment = re.sub(r"<sup>\s*(\d+)\s*</sup>", r"^\1", fragment)          # keep superscripts as ^n
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return normalize_uz(html.unescape(fragment).replace("\xa0", " "))


def label_display(label: str) -> str:
    """'195-1' → '195¹'"""
    base, _, sup = label.partition("-")
    return base + sup.translate(SUPERSCRIPT) if sup else base


def flat_number(label: str) -> str:
    """'195-1' → '1951' (how the HF corpus stores it)"""
    return label.replace("-", "")


@dataclass
class Article:
    label: str                       # "195-1"
    title: str
    part: str = ""
    chapter: str = ""
    paragraphs: list[str] = field(default_factory=list)
    amendment_notes: list[str] = field(default_factory=list)
    element_id: str = ""

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


@dataclass
class LexDocument:
    title: str
    articles: list[Article]
    version_dates: list[str]
    okoz: list[str]

    def by_label(self) -> dict[str, Article]:
        return {a.label: a for a in self.articles}


def parse(page: str) -> LexDocument:
    starts = [(m.start(), m.group(1)) for m in BLOCK_RE.finditer(page)]
    title, part, chapter = "", "", ""
    articles: list[Article] = []
    okoz: list[str] = []
    for i, (pos, cls) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(page)
        block = page[pos:end]
        if cls in ("COMMENT",):                                             # LexUZ sharhi — not law
            continue
        if cls == "INDEXES_ON_REF":
            okoz += re.findall(r'class="iorVal">([^<]+)<', block)
            continue
        m = INNER_RE.search(block)
        if not m:
            continue
        el_id, inner = m.group(1), m.group(2)
        txt = _text(inner)
        if not txt:
            continue
        if cls == "ACT_TITLE":
            title = txt
        elif cls == "TEXT_HEADER_DEFAULT":
            line = txt.replace("\n", " ")
            if re.search(r"\bbob\b", line, re.I):
                chapter = line
            else:
                part, chapter = line, ""
        elif cls == "CLAUSE_DEFAULT":
            h = HEADING_RE.match(txt)
            if h:
                label = h.group(1) + (f"-{h.group(2)}" if h.group(2) else "")
                articles.append(Article(label, h.group(3).strip(), part, chapter, element_id=el_id))
        elif cls == "ACT_TEXT" and articles:
            articles[-1].paragraphs.append(txt)
        elif cls == "CHANGES_ORIGINS" and articles:
            articles[-1].amendment_notes.append(txt)
    versions = sorted(set(re.findall(r"ONDATE=(\d{2}\.\d{2}\.\d{4})", page)),
                      key=lambda d: d[6:] + d[3:5] + d[:2])
    return LexDocument(title, articles, versions, okoz)


# ------------------------------------------------------------------ superscript repair for the corpus

def repair_labels(numbers_in_order: list[str]) -> list[str]:
    """Corpus article numbers in document order → labels with the superscript restored.

    The corpus wrote 195¹ as "1951". In document order an inserted article comes right after its base
    article, so "1951" that follows "195" (and is not the next number, 196) is "195-1".
    Numbers that already contain a dash ("12-1") are kept.
    """
    out, base = [], None
    for raw in numbers_in_order:
        n = str(raw or "").strip()
        if not n.isdigit():
            out.append(n)
            continue
        label = n
        if base is not None:
            for cand in (base, base + 1):        # base + 1: the base article itself was repealed (183 → 184²)
                c = str(cand)
                if (n != str(base + 1) and n.startswith(c) and len(n) > len(c) and n[len(c)] != "0"
                        and int(n) > 10 * cand):
                    label = f"{c}-{n[len(c):]}"
                    base = cand
                    break
        out.append(label)
        if "-" not in label:
            base = int(n)
    return out
