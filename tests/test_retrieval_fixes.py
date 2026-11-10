"""Fixes after the 100-question test (8-noyabr 20:14): old versions excluded inside the search, amending acts left
out, two-part questions searched by halves, future acts, a forgotten [n], the judge's checklist."""

import importlib.util
import json
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


def _runner():
    spec = importlib.util.spec_from_file_location("rag_api_test", ROOT / "scripts" / "rag_api_test.py")
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    return t


def test_judge_checks_the_references_facts_only():
    t = _runner()
    assert t.ref_facts("kamida 35 yosh, davlat tilini bilishi; yetti yil muddatga; oktabr oyi") == \
        ["kamida 35 yosh, davlat tilini bilishi", "yetti yil muddatga", "oktabr oyi"]
    assert len(t.ref_facts("yigirma bir kalendar kun (amaldagi Mehnat kodeksi; eski kodeksdagi «15 ish kuni» emas)")) == 1
    j, seen = t.Judge("http://x", "m"), []
    answers = iter([
        {"present": [True, False], "same_topic": True, "conflict": None, "faithful": True},
        {"present": [True, True], "same_topic": True, "conflict": None, "faithful": True},
        {"present": [True, True], "same_topic": False, "conflict": None, "faithful": True},
        {"present": [True], "same_topic": True, "faithful": True,                       # «qirq sakkiz» = 48: no conflict
         "conflict": {"answer_says": "qirq sakkiz soatdan ortiq ushlab turilishi mumkin emas", "fact": 1}},
        {"present": [True, True], "same_topic": True, "faithful": True,
         "conflict": {"answer_says": "boshqa manbada Prezident besh yil muddatga saylanadi", "fact": 2}},
    ])

    def ask(prompt):
        seen.append(prompt)
        return next(answers)
    j.ask = ask
    q2 = {"question": "q", "expected_answer": "kamida 35 yosh; yetti yil muddatga"}
    r = {"answer": "35 yosh. Prezident yetti yil muddatga saylanadi, ammo boshqa manbada Prezident besh yil muddatga saylanadi.",
         "contexts": [], "citations": []}
    assert [j.grade(q2, r)["correctness"] for _ in range(3)] == [1, 2, 0]
    q1 = {"question": "q", "expected_answer": "sud qarorisiz 48 soatdan ortiq ushlab turish mumkin emas"}
    assert j.grade(q1, {"answer": "Shaxs qirq sakkiz soatdan ortiq ushlab turilishi mumkin emas.", "contexts": [],
                        "citations": []})["correctness"] == 2
    g = j.grade(q2, r)
    assert g["correctness"] == 0 and "besh yil" in g["conflict"]
    assert "1. kamida 35 yosh" in seen[0] and "2. yetti yil muddatga" in seen[0]


class _Ctx:
    def __init__(self, cid, doc_id, doc_type, text, title="t"):
        self.chunk_id, self.text, self.n = cid, text, 0
        self.meta = {"doc_id": doc_id, "doc_type": doc_type, "doc_title": title}


def test_quantities():
    from modda.versions import quantities
    assert quantities("taʼtilining muddati 15 ish kunidan kam boʻlmasligi kerak") == {("kun", "15")}
    assert quantities("davomiyligi yigirma bir kalendar kunni tashkil etadi") == {("kun", "21")}
    assert quantities("Prezident yetti yil muddatga saylanadi") == {("yil", "7")}
    assert quantities("oktabr oyining birinchi yakshanbasi") == set()


def test_drop_outdated():
    from modda.versions import drop_outdated
    con = _con([("-142859", "OʻZBEKISTON RESPUBLIKASINING MEHNAT KODEKSI", "code", str(i)) for i in range(1, 120)] +
               [("-6257288", "Oʻzbekiston Respublikasining Mehnat kodeksi", "code", str(i)) for i in range(1, 120)])
    con.label = "t-outdated"
    ctx = [
        _Ctx("code", "-6257288", "code", "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi yigirma bir kalendar kunni tashkil etadi."),
        _Ctx("res", "-3590278", "resolution", "Mehnat kodeksining 134-moddasiga muvofiq yillik mehnat taʼtilining muddati 15 ish kunidan kam boʻlmasligi kerak."),
        _Ctx("new", "-7000001", "resolution", "Mehnat kodeksining 217-moddasiga muvofiq taʼtil beriladi."),
        _Ctx("sk", "-4386848", "code", "Oʻzbekiston Respublikasi Prezidenti yetti yil muddatga saylanadi."),
        _Ctx("old", "-111838", "law", "Oʻzbekiston Respublikasi Prezidenti besh yil muddatga saylanadi."),
        _Ctx("other", "-5", "law", "Xodimga yillik qoʻshimcha taʼtil uch kalendar kun beriladi."),
    ]
    kept, dropped = drop_outdated(con, ctx)
    assert {d["chunk_id"] for d in dropped} == {"res", "old"}
    assert [c.chunk_id for c in kept] == ["code", "new", "sk", "other"]
    assert drop_outdated(con, ctx, exact=("old",))[1][0]["chunk_id"] == "res"      # an explicit reference is kept


def test_colloquial_words_get_the_legal_term():
    from modda.textnorm import base_query, legal_terms, to_query_form
    assert to_query_form("Otpuskaga necha kun berishadi oʻzi?") == "Otpuskaga necha kun berishadi oʻzi? (mehnat taʼtili)"
    assert "ish beruvchining tashabbusi" in legal_terms("Ishdan haydashmoqchi, oldindan aytishlari kerakmi?")
    assert legal_terms("Yillik asosiy mehnat taʼtilining eng kam muddati qancha?") == ""
    assert base_query(to_query_form("Otpuskaga necha kun?")) == "Otpuskaga necha kun?"
    parts = split_question(to_query_form("Xodim oʻz xohishi bilan ishdan ketmoqchi boʻlsa necha kun oldin ogohlantiradi, "
                                         "ish beruvchi esa qanday asoslar bilan shartnomani bekor qila oladi?"))
    assert "xodimning tashabbusi" in parts[0] and "(" not in parts[1]               # the term stays with its half


def test_no_info_sentences_are_not_claims():
    from modda.rag import drop_no_info, parse_answer
    assert drop_no_info("Qoʻshilgan qiymat soligʻi stavkasi haqida berilgan maʼlumotlar mavjud emas . [1][2][3][4][5]") is None
    kept = drop_no_info("Nikoh yoshi haqida maʼlumot berilmagan, ammo nikoh yoshiga yetmagan shaxs bilan nikoh haqiqiy emas deb topilishi mumkin. [1]")
    assert kept.startswith("Nikoh yoshiga yetmagan")
    law = "Shaxsga doir maʼlumotlarni yoʻq qilish amalga oshirilishi natijasida ularni tiklash imkoni boʻlmay qoladi. [1]"
    assert drop_no_info(law) == law                                   # «yoʻq qilish» = to destroy, a real claim
    assert drop_no_info("Agar shaxs haqida maʼlumotlar mavjud emas boʻlsa, soʻrov yuboriladi. [1]")    # a condition, kept
    c = [ctx("a", "Daromadlarga 12 foizlik soliq stavkasi boʻyicha soliq solinadi.")]
    ans = parse_answer("q", "QQS stavkasi haqida berilgan maʼlumotlar mavjud emas [1][2]. Daromadlarga 12 foizlik stavka boʻyicha soliq solinadi [1].", c)
    assert [x["text"][:11] for x in ans.sentences] == ["Daromadlarg"]


def test_conflict_checks_every_reference_fact():
    t = _runner()
    facts = ["jazo va aliment qarzi boʻyicha ushlab qolish ish haqining yetmish foizidan oshmaydi (umumiy holda — ellik foiz)"]
    assert t.real_conflict({"answer_says": "koʻpi bilan ellik foizi"}, "… koʻpi bilan ellik foizi ushlab qolinadi", facts) is None
    facts = ["oʻn olti yoshdan", "oʻn besh yoshdan ota-onadan birining yozma roziligi bilan"]
    assert t.real_conflict({"answer_says": "oʻn besh yoshga toʻlishi bilan", "fact": 1}, "… oʻn besh yoshga toʻlishi bilan …", facts) is None
    facts = ["yigirma bir kalendar kun (amaldagi Mehnat kodeksi; eski kodeksdagi «15 ish kuni» emas)"]
    assert t.real_conflict({"answer_says": "15 ish kunidan kam boʻlmasligi"}, "muddati 15 ish kunidan kam boʻlmasligi kerak", facts)


def test_cached_judge_regrades_saved_verdicts(tmp_path):
    t = _runner()
    (tmp_path / "judge.jsonl").write_text(json.dumps({"id": "q062", "relevant": [1], "grade": {
        "facts": [{"fact": "yetmish foizidan oshmaydi (umumiy holda — ellik foiz)", "present": True}], "same_topic": True,
        "conflict": "koʻpi bilan ellik foizi", "correctness": 0}}, ensure_ascii=False) + "\n", encoding="utf-8")
    j = t.CachedJudge(tmp_path / "judge.jsonl")
    g = j.grade({"id": "q062"}, {"answer": "Ish haqining koʻpi bilan ellik foizi ushlab qolinadi."})
    assert g["correctness"] == 2 and g["conflict"] is None and j.relevance({"id": "q062"}, {}) == [1]
