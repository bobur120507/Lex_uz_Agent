"""Small, working prototypes of the key ideas in the roadmap.

They are used by make_figures.py to draw the I_EXPLAIN.md pictures, and the
team can use them as a starting point for src/lexai/. Run the self-test with:

    python docs/explain/prototypes.py
"""

import re
import unicodedata
from difflib import SequenceMatcher

# ------------------------------------------------------------------ 1. normalization

OKINA = "ʻ"        # ʻ  in oʻ, gʻ
TUTUQ = "ʼ"        # ʼ  in maʼlumot
APOSTROPHES = "'`‘’ʻʼ´ʹ"   # ' ` ‘ ’ ʻ ʼ ´ ʹ


def normalize_uz(text: str) -> str:
    """One canonical form for Uzbek Latin text: NFC, oʻ/gʻ with U+02BB, other apostrophes U+02BC."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(rf"([oOgG])[{APOSTROPHES}]", lambda m: m.group(1) + OKINA, text)
    other = APOSTROPHES.replace(OKINA, "")                 # keep the ʻ produced by the line above
    text = re.sub(rf"(?<=\w)[{other}](?=\w)", TUTUQ, text)
    return re.sub(r"[ \t ]+", " ", text).strip()


# ------------------------------------------------------------------ 2. Cyrillic -> Latin (Uzbek)

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "ъ": TUTUQ, "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o" + OKINA, "қ": "q", "ғ": "g" + OKINA, "ҳ": "h",
}
_VOWELS = set("аеёиоуэюяў")


def cyr_to_lat(text: str) -> str:
    """Uzbek Cyrillic -> Latin. 'е' is 'ye' at the start of a word or after a vowel."""
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


# ------------------------------------------------------------------ 3. article (modda) chunking

ARTICLE_RE = re.compile(r"^(\d+)-modda\.\s*(.*)$", re.M)


def split_articles(doc_text: str, doc_title: str, hierarchy: str = ""):
    """'1-modda. ...' lines start a new chunk. Returns dicts with a contextual header."""
    matches = list(ARTICLE_RE.finditer(doc_text))
    chunks = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc_text)
        body = doc_text[m.start():end].strip()
        num = m.group(1)
        note = re.findall(r"\(([^()]*tahririda[^()]*)\)", body)          # amendment note
        clean = re.sub(r"\s*\([^()]*tahririda[^()]*\)", "", body).strip()
        header = f"[{doc_title} | {hierarchy} › {num}-modda]"
        chunks.append({"chunk_id": f"doc#m{num}", "article_no": num, "header": header,
                       "text": clean, "amendment_note": note[0] if note else None})
    return chunks


def fixed_size_chunks(text: str, size: int):
    return [text[i:i + size] for i in range(0, len(text), size)]


# ------------------------------------------------------------------ 4. hybrid search: RRF

def rrf(rankings: dict[str, list[str]], k: int = 60):
    """Reciprocal Rank Fusion: score(d) = sum over lists of 1 / (k + rank)."""
    scores = {}
    for ranked in rankings.values():
        for rank, doc in enumerate(ranked, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


# ------------------------------------------------------------------ 5. query router

ABBREVIATIONS = {"mk": "Mehnat kodeksi", "jk": "Jinoyat kodeksi", "fk": "Fuqarolik kodeksi",
                 "ok": "Oila kodeksi", "sk": "Soliq kodeksi"}
REF_RE = re.compile(r"\b(?P<code>[a-zʻ]+(?:\s+kodeksi)?)\s+(?P<art>\d+)\s*-?\s*modda", re.I)


def route(question: str):
    """Exact reference ('MK 131-modda', 'Mehnat kodeksi 131-moddasi') -> direct lookup, else hybrid search."""
    q = normalize_uz(cyr_to_lat(question)) if re.search("[а-яёўқғҳ]", question.lower()) else normalize_uz(question)
    m = REF_RE.search(q)
    if m:
        code = m.group("code").lower()
        doc = ABBREVIATIONS.get(code, m.group("code").capitalize())
        return {"route": "exact", "normalized": q, "document": doc, "article_no": m.group("art")}
    return {"route": "hybrid", "normalized": q}


# ------------------------------------------------------------------ 6. citation verifier

def _norm_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", normalize_uz(s).lower()).strip(" .,;:")


def verify_sentence(sentence: dict, context: dict[str, str], min_ratio: float = 0.9):
    """sentence = {"text", "chunk_ids", "quote"}. Returns (ok, reason)."""
    ids = sentence.get("chunk_ids") or []
    if not ids or any(i not in context for i in ids):
        return False, "chunk_id kontekstda yoʻq"
    source = " ".join(_norm_for_match(context[i]) for i in ids)
    quote = _norm_for_match(sentence.get("quote", ""))
    if not quote:
        return False, "iqtibos yoʻq"
    if quote not in source:
        best = max((SequenceMatcher(None, quote, source[j:j + len(quote)]).ratio()
                    for j in range(0, max(1, len(source) - len(quote) + 1), 5)), default=0)
        if best < min_ratio:
            return False, f"iqtibos manbada topilmadi (oʻxshashlik {best:.2f})"
    for num in re.findall(r"\d+", sentence["text"]):
        if num not in source:
            return False, f"«{num}» soni manbada yoʻq"
    return True, "tasdiqlandi"


if __name__ == "__main__":
    assert normalize_uz("o'zbek g`alla ma'lumot") == "oʻzbek gʻalla maʼlumot"
    assert cyr_to_lat("Меҳнат кодекси") == "Mehnat kodeksi"
    assert cyr_to_lat("ер ва юрт") == "yer va yurt"
    assert route("MK 131-modda nima deydi?")["article_no"] == "131"
    assert route("меҳнат кодекси 131-модда")["document"] == "Mehnat kodeksi"
    assert route("Ishdan boʻshatish tartibi qanday?")["route"] == "hybrid"
    assert rrf({"a": ["x", "y"], "b": ["y", "z"]})[0][0] == "y"
    ctx = {"c1": "Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi."}
    assert verify_sentence({"text": "Taʼtil 21 kun.", "chunk_ids": ["c1"], "quote": "kamida 21 kalendar kun"}, ctx)[0]
    assert not verify_sentence({"text": "Taʼtil 30 kun.", "chunk_ids": ["c1"], "quote": "kamida 21 kalendar kun"}, ctx)[0]
    print("all prototype checks passed")
