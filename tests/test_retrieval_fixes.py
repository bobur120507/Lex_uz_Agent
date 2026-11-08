"""Fixes after the 100-question test (8-noyabr 20:14): old versions excluded inside the search, amending acts left
out, two-part questions searched by halves, future acts, a forgotten [n], the judge's checklist."""

import importlib.util
import sqlite3
from pathlib import Path

from modda.pipeline import attach_source, future_act
from modda.rag import Context, interleave, split_question
from modda.store import Hit, MemoryStore, _qdrant_filter
from modda.versions import amending, excluded

ROOT = Path(__file__).resolve().parents[1]


def test_filter_excludes_documents():
    assert _qdrant_filter({"!doc_id": ["-1", "-2"]}) == {"must_not": [{"key": "doc_id", "match": {"any": ["-1", "-2"]}}]}
    assert _qdrant_filter({"doc_type": "code", "!doc_id": ["-1"]}) == {
        "must": [{"key": "doc_type", "match": {"value": "code"}}], "must_not": [{"key": "doc_id", "match": {"any": ["-1"]}}]}
    st = MemoryStore(dim=2)
    st.upsert([{"chunk_id": c, "dense": [1.0, 0.0], "sparse": {"indices": [1], "values": [1.0]}, "payload": {"doc_id": d}}
               for c, d in (("a", "-1"), ("b", "-2"), ("c", "-3"))])
    ids = {h.chunk_id for h in st.search_hybrid([1.0, 0.0], {"indices": [1], "values": [1.0]}, 5, flt={"!doc_id": ["-1", "-2"]})}
    assert ids == {"c"}


def _con(rows):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE articles (doc_id TEXT, doc_title TEXT, doc_type TEXT, article_number TEXT)")
    con.executemany("INSERT INTO articles VALUES (?, ?, ?, ?)", rows)

    class Con:                                            # the project's connection carries a label (cache key)
        label = "t-amend"
        execute = con.execute
    return Con()


def test_amending_acts_left_out_unless_asked():
    con = _con([("-112443", "OʻZBEKISTON RESPUBLIKASINING MEHNAT QONUNLARI KODEKSIGA OʻZGARTIShLAR VA QOʻShIMChALAR KIRITISh TOʻGʻRISIDA", "code", None),
                ("-36558", "Oʻzbekiston Respublikasining ayrim qonun hujjatlariga oʻzgartish va qoʻshimchalar kiritish toʻgʻrisida", "law", None),
                ("-9", "Ayrim qarorlarni oʻz kuchini yoʻqotgan deb hisoblash toʻgʻrisida", "resolution", None),
                ("-6257288", "Oʻzbekiston Respublikasining Mehnat kodeksi", "code", "217"),
                ("-5", "Nizomni tasdiqlash toʻgʻrisida", "resolution", None)])
    assert set(amending(con)) == {"-112443", "-36558", "-9"}
    assert "-112443" in excluded(con, "Otpuskaga necha kun berishadi?")
    assert "-112443" not in excluded(con, "Mehnat kodeksiga qachon oʻzgartish kiritilgan?")
    assert "-6257288" not in excluded(con, "Otpuskaga necha kun berishadi?") and "-5" not in excluded(con, "x")


def test_split_question():
    assert split_question("Dastlabki sinov muddati qancha va sinov davrida shartnomani bekor qilish uchun necha kun oldin ogohlantirish kerak?") == \
        ["Dastlabki sinov muddati qancha", "sinov davrida shartnomani bekor qilish uchun necha kun oldin ogohlantirish kerak"]
    for single in ("Ota-ona va bola oʻrtasidagi aliment qancha?", "Fuqarolar va yuridik shaxslar qanday huquqlarga ega?",
                   "Yillik asosiy mehnat taʼtilining eng kam muddati qancha?", "Qanday hollarda va qancha muddatga ushlab turiladi?"):
        assert split_question(single) == [], single


def test_interleave():
    full = [Hit(c, 0) for c in "abcdef"]
    p1, p2 = [Hit("a", 0), Hit("x", 0)], [Hit("y", 0), Hit("z", 0)]
    # the whole question keeps 3 places, each half adds its best new hit, then the rest
    assert [h.chunk_id for h in interleave([full, p1, p2], k=5)][:5] == ["a", "b", "c", "x", "y"]
    assert len(interleave([full, p1, p2], k=5)) == 9


def test_future_act():
    assert "2030" in future_act("2030-yilda qabul qilinadigan yangi soliq kodeksi nima deydi?", "2026-11-01")
    assert future_act("Kelgusi yilda kuchga kiradigan qonun nima?", "2026-11-01")
    assert future_act("2019-yilda qabul qilingan soliq kodeksi nima deydi?", "2026-11-01") is None
    assert future_act("2030-yilgacha moʻljallangan strategiya nima?", "2026-11-01") is None


def ctx(cid, text, header="Mehnat kodeksi 217-modda"):
    return Context(1, cid, 0.0, header, text, {})


def test_attach_source():
    c = [ctx("a", "Yoʻl harakati oʻng tomonlama. Transport vositalari yoʻlning oʻng tomonida harakatlanadi."),
         ctx("b", "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi yigirma bir kalendar kunni tashkil etadi.")]
    s = attach_source({"text": "Transport vositalari yoʻlning oʻng tomonida harakatlanadi", "chunk_ids": []}, c)
    assert s["chunk_ids"] == ["a"] and s["attached"]
    s = attach_source({"text": "Taʼtil 30 kalendar kun boʻladi va har yili beriladi", "chunk_ids": []}, c)
    assert s["chunk_ids"] == []                               # 30 is in no source: stays uncited (and is dropped)
    s = attach_source({"text": "Taʼtil yigirma bir kalendar kun", "chunk_ids": ["b"]}, c)
    assert s["chunk_ids"] == ["b"] and "attached" not in s     # cited sentences are left alone


def test_judge_checklist_and_min():
    spec = importlib.util.spec_from_file_location("rag_api_test", ROOT / "scripts" / "rag_api_test.py")
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    j = t.Judge("http://x", "m")
    answers = iter([
        {"facts": [{"fact": "21 kalendar kun", "present": False}], "same_topic": False, "contradicts": False, "faithful": True},
        {"facts": [{"fact": "36 soat", "present": True}, {"fact": "24 soat", "present": False}], "same_topic": True,
         "contradicts": False, "faithful": True},
        {"facts": [{"fact": "18 yosh", "present": True}], "same_topic": True, "contradicts": False, "faithful": True},
    ])
    j.ask = lambda prompt: next(answers)
    q, r = {"question": "q", "expected_answer": "e"}, {"answer": "a", "contexts": [], "citations": []}
    assert [j.grade(q, r)["correctness"] for _ in range(3)] == [0, 1, 2]
