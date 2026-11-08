"""API /v1 (test spetsifikatsiyasi) — validation, language, transliteration; and the tester's scoring helpers."""

import importlib.util
from pathlib import Path

import pytest

from modda import v1
from modda.textnorm import lat_to_cyr

ROOT = Path(__file__).resolve().parents[1]


def body(n=1, **kw):
    b = {"run_id": "r", "batch_id": "r-b01", "items": [{"id": f"q{i:03d}", "question": "Mehnat taʼtili necha kun?"} for i in range(n)]}
    b.update(kw)
    return b


@pytest.mark.parametrize("bad, why", [
    (body(11), "1–10"), (body(0), "1–10"), (body(1, items=[{"id": "a", "question": "  "}]), "boʻsh"),
    (body(1, items=[{"id": "a", "question": "x"}, {"id": "a", "question": "y"}]), "takroriy"),
    (body(1, items=[{"id": "a", "question": "x" * 2001}]), "2000"), (body(1, batch_id=""), "batch_id"),
    (body(1, options={"top_k": 0}), "top_k"), (body(1, options={"answer_language": "de"}), "answer_language"),
])
def test_validation_400(bad, why):
    with pytest.raises(v1.ApiError) as e:
        v1.validate_batch(bad)
    assert e.value.status == 400 and why in e.value.message


def test_valid_batch_and_hash():
    b = body(10, options={"top_k": 5, "temperature": 0, "seed": 42})
    assert v1.validate_batch(b) is b
    assert v1.request_hash(b) == v1.request_hash(dict(b))
    assert v1.request_hash(b) != v1.request_hash(body(9, options=b["options"]))


@pytest.mark.parametrize("text, lang", [
    ("Yillik mehnat taʼtili qancha?", "uz-Latn"), ("Шахс суднинг қарорисиз қанча ушлаб турилади?", "uz-Cyrl"),
    ("Каков брачный возраст в Узбекистане?", "ru"), ("На какой срок избирается Президент?", "ru"),
])
def test_detect_language(text, lang):
    assert v1.detect_language(text) == lang


def test_lat_to_cyr():
    assert lat_to_cyr("Oʻzbekiston Konstitutsiyasi, yer, ega, shaxs, gʻoya, taʼtil [1].") == \
        "Ўзбекистон Конституцияси, ер, эга, шахс, ғоя, таътил [1]."


def test_auth(monkeypatch):
    monkeypatch.setenv("MODDA_API_KEY", "k1")
    v1.check_auth("Bearer k1")
    for header, code in ((None, 401), ("Basic k1", 401), ("Bearer k2", 403)):
        with pytest.raises(v1.ApiError) as e:
            v1.check_auth(header)
        assert e.value.status == code


def test_rate_limit():
    v1._last_batch.clear()
    v1.rate_limit("Bearer x")
    with pytest.raises(v1.ApiError) as e:
        v1.rate_limit("Bearer x")
    assert e.value.status == 429 and e.value.headers["Retry-After"] == "1"


def _runner():
    spec = importlib.util.spec_from_file_location("rag_api_test", ROOT / "scripts" / "rag_api_test.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scoring_helpers():
    t = _runner()
    assert t.claims("Taʼtil yigirma bir kalendar kun [1]. Boshqa gap shu yerda keltirilgan [2][3]") == \
        [("Taʼtil yigirma bir kalendar kun", [1]), ("Boshqa gap shu yerda keltirilgan", [2, 3])]
    src = "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi yigirma bir kalendar kunni tashkil etadi."
    assert t.supported("Har yilgi eng kam mehnat taʼtili 21 kalendar kun", src)[0]          # «yigirma bir» = 21
    assert not t.supported("Har yilgi eng kam mehnat taʼtili 15 ish kuni", src)[0]
    assert t.docnum("lex:-6257288") == "6257288" and t.artnum("217-modda") == "217"


def test_testset_composition():
    t = _runner()
    rows = t.load_testset(ROOT / "data" / "testset" / "test100.csv")
    assert len(rows) == 100 and len({r["id"] for r in rows}) == 100
    cats = {c: sum(r["category"] == c for r in rows) for c in {r["category"] for r in rows}}
    assert cats == {"faktik": 35, "raqam": 15, "kop_modda": 15, "ozgargan": 10, "til": 10, "javobsiz": 10, "noaniq": 5}
    assert all(r["exp_pairs"] for r in rows if r["answerable"]) and not any(r["answerable"] for r in rows if r["category"] == "javobsiz")
    assert {r["batch"] for r in rows} == {f"b{i:02d}" for i in range(1, 11)}
