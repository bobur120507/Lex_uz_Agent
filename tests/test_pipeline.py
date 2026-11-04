"""Offline tests: no Ollama, no Qdrant. Real services are exercised by `python -m modda doctor`."""

import os
from pathlib import Path

import pytest

from modda import sparse
from modda.chunking import MAX_WORDS, build_chunks, chunks_for_article, split_text
from modda.corpus import connect, find_article_files, ingest, stats
from modda.evaluation import first_rank, matches
from modda.llm import FakeEmbedder, strip_think
from modda.rag import answer, parse_answer, retrieve
from modda.store import MemoryStore, QdrantStore, _qdrant_filter, point_id
from modda.indexing import run_index
from modda.textnorm import cyr_to_lat, normalize_uz, to_query_form, tokenize

FIX = Path(__file__).parent / "fixtures"


# ----------------------------------------------------------------------------- text

def test_normalize_apostrophes():
    assert normalize_uz("o'zbek g`alla ma'lumot") == "oʻzbek gʻalla maʼlumot"
    assert normalize_uz("ko‘ra bo`linishi") == "koʻra boʻlinishi"


def test_cyrillic_to_latin():
    assert cyr_to_lat("Меҳнат кодекси") == "Mehnat kodeksi"
    assert to_query_form("таътил қачон берилади?") == "taʼtil qachon beriladi?"


def test_tokenize_stems_and_keeps_okina():
    toks = tokenize("Taʼtilga, taʼtilning va taʼtili haqida 131-modda")
    assert toks.count("taʼtil") == 3
    assert "131" in toks and "va" not in toks
    assert "oʻquv" in tokenize("O'quv")


# ----------------------------------------------------------------------------- corpus

PG_URL = os.environ.get("MODDA_TEST_DATABASE_URL")       # run the same tests on PostgreSQL when set


def make_con(tmp_path, name="t"):
    if PG_URL:
        c = connect(url=PG_URL)
        c.execute("DROP TABLE IF EXISTS chunks"); c.execute("DROP TABLE IF EXISTS articles"); c.execute("DROP TABLE IF EXISTS meta")
        c.commit()
        return connect(url=PG_URL)
    return connect(tmp_path / f"{name}.sqlite")


@pytest.fixture()
def con(tmp_path):
    c = make_con(tmp_path)
    ingest(FIX, c)
    build_chunks(c)
    return c


def test_finds_only_article_files():
    files = find_article_files(FIX)
    assert [f.name for f in files] == ["articles-sample.jsonl"]


def test_ingest_normalizes(con):
    st = stats(con)
    assert st["articles"] == 6 and st["documents"] == 4
    text = con.execute("SELECT article_text FROM articles WHERE id='9001:3'").fetchone()[0]
    assert "toʻlanadigan taʼtil" in text and "koʻra" in text and "boʻlinishi" in text
    cyr = con.execute("SELECT doc_title, article_text FROM articles WHERE id='9003:1'").fetchone()
    assert cyr[0] == "Naʼmuna qarori" and "yer maydonlariga" in cyr[1]


def test_chunk_header_and_mvp(con):
    r = con.execute("SELECT header, mvp FROM chunks WHERE chunk_id='9001:3'").fetchone()
    assert r["header"] == "Namuna mehnat kodeksi › Birinchi qism › 2-bob. Taʼtillar › 3-modda. Yillik taʼtil"
    assert r["mvp"] == 1
    assert con.execute("SELECT mvp FROM chunks WHERE chunk_id='9002:7'").fetchone()[0] == 0


def test_long_article_split_with_overlap(con):
    parts = con.execute("SELECT text, n_words FROM chunks WHERE article_id='9002:8' ORDER BY part_no").fetchall()
    assert len(parts) >= 2
    assert all(p["n_words"] <= MAX_WORDS for p in parts)
    tail = parts[0]["text"].split()[-10:]
    assert " ".join(tail) in parts[1]["text"]                # overlap


def test_split_text_short_is_one():
    assert split_text("Qisqa matn.") == ["Qisqa matn."]


def test_chunking_is_resumable(con):
    assert build_chunks(con) == 0                             # nothing new the second time


# ----------------------------------------------------------------------------- sparse + store

def test_bm25_vectors():
    d = sparse.doc_vector("taʼtil taʼtil haqi")
    q = sparse.query_vector("Taʼtil haqi?")
    assert set(q["indices"]) <= set(d["indices"])
    assert d["indices"] == sorted(d["indices"])
    assert sparse.query_vector("") == {"indices": [], "values": []}


def test_qdrant_filter_and_ids():
    assert _qdrant_filter({"status": "active", "doc_type": ["Kodeks", "Qonun"]}) == {"must": [
        {"key": "status", "match": {"value": "active"}}, {"key": "doc_type", "match": {"any": ["Kodeks", "Qonun"]}}]}
    assert point_id("a") == point_id("a") != point_id("b")


@pytest.fixture()
def indexed(con):
    store, emb = MemoryStore(dim=64), FakeEmbedder(64)
    n = run_index(con, store, emb, "fake", batch=2)
    assert n == store.count() == stats(con)["chunks"]
    return con, store, emb


def test_index_resume(indexed):
    con, store, emb = indexed
    assert run_index(con, store, emb, "fake") == 0


@pytest.mark.parametrize("mode", ["dense", "sparse", "hybrid"])
def test_retrieve_finds_article(indexed, mode):
    con, store, emb = indexed
    ctx = retrieve(con, store, emb, "fake", "Taʼtil haqi qachon toʻlanadi?", k=3, mode=mode)
    assert first_rank(ctx, [{"doc_id": "9001", "article_number": "4"}]) is not None


def test_retrieve_cyrillic_question(indexed):
    con, store, emb = indexed
    ctx = retrieve(con, store, emb, "fake", "Ер солиғи қачон тўланади?", k=2, mode="sparse")
    assert ctx and ctx[0].meta["article_number"] == "7"


# ----------------------------------------------------------------------------- answer parsing

class FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, model, messages, **kw):
        assert "MANBALAR" in messages[1]["content"]
        return self.reply, 0.01


def test_answer_with_citations_builds_sources(indexed):
    con, store, emb = indexed
    llm = FakeLLM("Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi [1].")
    ans = answer(con, store, emb, llm, embed_model="fake", llm_model="x", question="Taʼtil haqi qachon toʻlanadi?",
                 k=1, mode="sparse")
    assert not ans.unknown
    src = next(iter(ans.sources.values()))
    assert src["article_no"] == "4" and src["url"].startswith("https://lex.uz")
    assert "Manba:" in ans.source_block() and "4-modda" in ans.source_block()
    assert ans.sentences[0]["cited"]


def test_unknown_and_uncited_are_not_trusted(indexed):
    con, store, emb = indexed
    ctx = retrieve(con, store, emb, "fake", "taʼtil", k=2, mode="sparse")
    assert parse_answer("q", "BILMAYMAN", ctx).unknown
    assert parse_answer("q", "Taʼtil 30 kun.", ctx).unknown          # no [n] → not trusted
    assert parse_answer("q", "Javob [9].", ctx).unknown              # cites a source that was not given


def test_strip_think():
    assert strip_think("<think>hmm</think>\nJavob [1].") == "Javob [1]."


def test_golden_match():
    assert matches({"doc_id": "1", "article_number": "131"}, {"doc_id": "1", "article_number": "131"})
    assert matches({"doc_title": "Mehnat kodeksi", "article_number": "5"},
                   {"doc_title_contains": "mehnat", "article_number": "5"})
    assert not matches({"doc_id": "1", "article_number": "13"}, {"doc_id": "1", "article_number": "131"})


# ----------------------------------------------------------------------------- Qdrant REST shapes

class _Resp:
    def __init__(self, data, code=200):
        import json as _j
        self.status_code, self._d, self.content, self.text = code, data, _j.dumps(data).encode(), _j.dumps(data)

    def json(self):
        return self._d


def test_qdrant_rest_requests(monkeypatch):
    import requests
    calls = []
    state = {"exists": False}

    def fake(method, url, json=None, timeout=None):
        calls.append((method, url.split("6333")[1], json))
        if url.endswith("/exists"):
            return _Resp({"result": {"exists": state["exists"]}})
        if method == "PUT" and url.endswith("/collections/c"):
            state["exists"] = True
        if url.endswith("/points/query"):
            return _Resp({"result": {"points": [{"id": "x", "score": 0.5, "payload": {"chunk_id": "9001:4"}}]}})
        return _Resp({"result": True})

    monkeypatch.setattr(requests, "request", fake)
    st = QdrantStore("http://q:6333", "c", dim=3)
    st.ensure_collection()
    create = next(c for c in calls if c[0] == "PUT" and c[1] == "/collections/c")[2]
    assert create["vectors"]["dense"]["size"] == 3 and create["sparse_vectors"]["bm25"]["modifier"] == "idf"
    assert sum(1 for c in calls if c[1].startswith("/collections/c/index")) == 5
    st.upsert([{"chunk_id": "a", "dense": [1, 0, 0], "sparse": {"indices": [1], "values": [0.5]}, "payload": {"mvp": 1}}])
    pts = calls[-1][2]["points"][0]
    assert pts["vector"]["bm25"]["indices"] == [1] and pts["payload"]["chunk_id"] == "a"
    hits = st.search_hybrid([1, 0, 0], {"indices": [1], "values": [1.0]}, limit=3, flt={"status": "active"})
    body = calls[-1][2]
    assert body["query"] == {"fusion": "rrf"} and len(body["prefetch"]) == 2
    assert body["prefetch"][0]["filter"]["must"][0]["key"] == "status"
    assert hits[0].chunk_id == "9001:4"


def test_flat_act_has_no_article_number(con):
    r = con.execute("SELECT header, mvp FROM chunks WHERE article_id='-9004-full'").fetchone()
    assert r["header"] == "Namuna qarori toʻgʻrisida" and r["mvp"] == 0


# ----------------------------------------------------------------------------- database layer

def test_sql_translation_for_postgres():
    from modda.db import _to_pg
    assert _to_pg("SELECT * FROM a WHERE id > ? LIMIT ?") == "SELECT * FROM a WHERE id > %s LIMIT %s"
    assert _to_pg("VALUES (:chunk_id, :mvp)") == "VALUES (%(chunk_id)s, %(mvp)s)"
    assert _to_pg("SELECT x::text") == "SELECT x::text"


def test_duplicate_ids_are_kept(tmp_path):
    import json, shutil
    d = tmp_path / "corpus"; d.mkdir()
    rows = [json.loads(l) for l in (FIX / "articles-sample.jsonl").read_text(encoding="utf-8").splitlines()]
    dup = dict(rows[0]); dup["article_text"] = "Boshqa matn."
    (d / "a.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows + [dup]), encoding="utf-8")
    c = make_con(tmp_path, "d")
    assert ingest(d, c) == len(rows) + 1
    ids = [r[0] for r in c.execute("SELECT id FROM articles WHERE id LIKE '9001:3%' ORDER BY id")]
    assert ids == ["9001:3", "9001:3~2"]
    assert ingest(d, c) == len(rows) + 1                       # running twice changes nothing
    assert stats(c)["articles"] == len(rows) + 1


def test_export_golden_picks_real_articles(con, tmp_path):
    from modda.tools import KEY_DOCUMENTS, export_golden
    KEY_DOCUMENTS.append(("Namuna mehnat kodeksi", ("code",)))
    try:
        path = export_golden(con, tmp_path, per_doc=5)
    finally:
        KEY_DOCUMENTS.pop()
    import json
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [] or all(r["doc_id"] == "9001" for r in rows)


def test_only_indexed_and_spread(indexed):
    from modda.evaluation import only_indexed, spread
    con, store, emb = indexed
    items = [
        {"id": "a", "answerable": True, "expected": [{"doc_id": "9001", "article_number": "4"}]},
        {"id": "b", "answerable": True, "expected": [{"doc_id": "7777", "article_number": "1"}]},
        {"id": "c", "answerable": False, "expected": []},
    ]
    assert only_indexed(con, items)[1] == 0                       # everything indexed → nothing dropped
    con.execute("UPDATE chunks SET indexed = 0 WHERE article_id <> '9001:4'"); con.commit()
    kept, skipped = only_indexed(con, items)
    assert [k["id"] for k in kept] == ["a", "c"] and skipped == 1
    many = [{"id": f"x{i}", "answerable": True, "expected": [{"doc_id": str(i % 3), "article_number": "1"}]} for i in range(9)]
    many += [{"id": f"n{i}", "answerable": False} for i in range(4)]
    got = spread(many, 8)
    assert len(got) == 8 and sum(not g["answerable"] for g in got) == 2
    assert {g["expected"][0]["doc_id"] for g in got if g["answerable"]} == {"0", "1", "2"}
