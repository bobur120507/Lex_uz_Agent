"""Uzbek text normalization, Cyrillic→Latin transliteration and tokenization for BM25."""

from __future__ import annotations

import re
import unicodedata

OKINA = "ʻ"   # ʻ  in oʻ, gʻ
TUTUQ = "ʼ"   # ʼ  in maʼlumot
APOSTROPHES = "'`‘’ʻʼ´ʹ"

_CYR_RE = re.compile("[а-яёўқғҳА-ЯЁЎҚҒҲ]")


def normalize_uz(text: str) -> str:
    """One canonical form: NFC; oʻ/gʻ with U+02BB; other in-word apostrophes U+02BC; single spaces."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(rf"([oOgG])[{APOSTROPHES}]", lambda m: m.group(1) + OKINA, text)
    other = APOSTROPHES.replace(OKINA, "")
    text = re.sub(rf"(?<=\w)[{other}](?=\w)", TUTUQ, text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "ъ": TUTUQ, "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o" + OKINA, "қ": "q", "ғ": "g" + OKINA, "ҳ": "h",
}
_VOWELS = set("аеёиоуэюяў")


def has_cyrillic(text: str) -> bool:
    return bool(_CYR_RE.search(text or ""))


def cyr_to_lat(text: str) -> str:
    """Uzbek Cyrillic → Latin. 'е' is 'ye' at the start of a word or after a vowel."""
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if low == "е":
            prev = text[i - 1].lower() if i else " "
            lat = "ye" if (not prev.isalpha() or prev in _VOWELS) else "e"
        else:
            lat = _CYR.get(low, ch)
        if ch.isupper() and lat:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            lat = lat.upper() if (nxt.isupper() and len(lat) > 1) else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def to_query_form(text: str) -> str:
    """Normalize a user's question: Cyrillic → Latin, then canonical apostrophes."""
    return normalize_uz(cyr_to_lat(text) if has_cyrillic(text) else text)


# --------------------------------------------------------------------------- tokens for BM25


# Very frequent function words; they only add noise to BM25.
STOPWORDS = {
    "va", "ham", "bilan", "uchun", "yoki", "bu", "shu", "u", "ular", "bir", "har", "deb", "esa",
    "agar", "lekin", "biroq", "hamda", "kabi", "boʻyicha", "oʻz", "mazkur", "ushbu", "qilib",
    "boʻlib", "boʻlsa", "emas", "edi", "ekan", "nima", "qanday", "qancha", "necha", "qachon",
    "kim", "qaysi", "mi", "mu", "da", "dan", "ga", "ni", "ning",
}

# Light suffix stripping. Uzbek is agglutinative; this is NOT a full stemmer, it only removes the
# most common case and possessive endings so "taʼtilga", "taʼtilning", "taʼtili" all match "taʼtil".
_SUFFIXES = sorted([
    "larning", "laridan", "lariga", "larini", "larida", "lardan", "larga", "larni", "larda", "lari",
    "ning", "dagi", "idan", "iga", "ini", "ida", "dan", "lar", "ga", "ka", "qa", "ni", "da", "ta",
    "si", "i",
], key=len, reverse=True)


def stem(token: str) -> str:
    if token.isdigit() or len(token) <= 4:
        return token
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


_UNITS = {"bir": 1, "ikki": 2, "uch": 3, "toʻrt": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "toʻqqiz": 9}
_TENS = {"oʻn": 10, "yigirma": 20, "oʻttiz": 30, "qirq": 40, "ellik": 50, "oltmish": 60, "yetmish": 70, "sakson": 80,
         "toʻqson": 90}
_NUMWORD = re.compile(r"[a-zʻ]+")
_ORDER = sorted([*_UNITS, *_TENS, "yuz", "ming"], key=len, reverse=True)
_SUFFIX = {"", "inchi", "nchi", "ta", "tasi", "dan", "ga", "da", "ni", "ning", "lik", "ta", "talik", "inchisi", "nchisi"}


def number_words(text: str) -> set[str]:
    """Numbers written as words in a legal text, as digits: «yigirma bir kalendar kun» → {"21"},
    «oʻn besh foiz» → {"15"}, «uch yuz» → {"300"}, «ikki ming» → {"2000"}. Laws write durations and rates in words;
    an answer that writes them in digits is still saying what the law says."""
    out: set[str] = set()
    words = _NUMWORD.findall(normalize_uz(text).lower().replace("'", "ʻ").replace("ʼ", "ʻ"))
    total = cur = 0
    seen = False

    def flush():
        nonlocal total, cur, seen
        if seen:
            out.add(str(total + cur))
        total = cur = 0
        seen = False

    for w in words:
        base = next((nw for nw in _ORDER if w.startswith(nw) and w[len(nw):] in _SUFFIX), w)
        if base in _UNITS:
            cur += _UNITS[base]; seen = True
        elif base in _TENS:
            cur += _TENS[base]; seen = True
        elif base == "yuz" and seen:
            cur = max(cur, 1) * 100
        elif base == "ming" and seen:
            total += max(cur, 1) * 1000; cur = 0
        else:
            flush()
    flush()
    return out


def tokenize(text: str) -> list[str]:
    """Lowercased, normalized, apostrophes kept inside words, stop words removed, light stemming."""
    text = to_query_form(text).lower()
    text = text.replace(OKINA, "\x01").replace(TUTUQ, "\x02")          # keep them inside \w-like runs
    tokens = []
    for raw in re.findall(r"[0-9]+(?:-[0-9]+)*|[^\W\d_\x01\x02]+(?:[\x01\x02][^\W\d_\x01\x02]+)*[\x01\x02]?", text):
        tok = raw.replace("\x01", OKINA).replace("\x02", TUTUQ)
        if tok in STOPWORDS or len(tok) < 2 and not tok.isdigit():
            continue
        tokens.append(stem(tok))
    return tokens
