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


def test_two_tier_indexing(con):
    """BM25 for everything without Ollama, then dense for the dense tier; sparse-only points are upgraded."""
    from modda.indexing import run_index
    store, emb = MemoryStore(dim=64), FakeEmbedder(64)
    n_sparse = run_index(con, store, None, "fake", mode="sparse")
    total, mvp = stats(con)["chunks"], stats(con)["chunks_mvp"]
    assert n_sparse == total - mvp and stats(con)["chunks_sparse_only"] == n_sparse
    ctx = retrieve(con, store, emb, "fake", "Yer soligʻi qachon toʻlanadi?", k=2, mode="sparse")
    assert ctx and ctx[0].meta["article_number"] == "7"              # found by BM25 alone
    assert store.search_dense(emb.embed("fake", ["yer"])[0], 5) == []  # no dense vectors yet
    n_dense = run_index(con, store, emb, "fake", types=["code", "constitution", "law"])
    st = stats(con)
    laws = con.execute("SELECT COUNT(*) FROM chunks c JOIN articles a ON a.id = c.article_id WHERE a.doc_type = 'law'").fetchone()[0]
    assert laws > 0 and n_dense == mvp + laws and st["chunks_indexed"] == n_dense   # codes + laws get dense
    assert st["chunks_sparse_only"] == total - n_dense                 # resolutions stay BM25-only
    assert run_index(con, store, None, "fake", mode="sparse") == 0


# ----------------------------------------------------------------------------- Lex.uz pages, labels, router

LEXUZ = FIX / "lexuz"


@pytest.mark.skipif(not (LEXUZ / "97664.html").exists(), reason="Lex.uz sahifalari saqlanmagan (fetch-fixtures)")
def test_lexuz_parser_keeps_superscripts_and_skips_commentary():
    from modda.lexparse import label_display, parse
    d = parse((LEXUZ / "97664.html").read_text(encoding="utf-8"))
    assert "Maʼmuriy javobgarlik" in d.title and len(d.articles) > 600
    a = d.by_label()["195-1"]
    assert label_display(a.label) == "195¹" and a.chapter.startswith("XVI bob")
    assert a.amendment_notes and "tahririda" in a.amendment_notes[0]
    assert all("LexUZ sharhi" not in p for art in d.articles for p in art.paragraphs)
    k = parse((LEXUZ / "6445145.html").read_text(encoding="utf-8")).by_label()["27"]
    assert "qirq sakkiz soatdan" in k.text and k.chapter.startswith("VII bob")


@pytest.mark.skipif(not LEXUZ.exists() or not list(LEXUZ.glob("*.html")), reason="Lex.uz sahifalari yoʻq")
def test_superscript_repair_matches_lexuz_on_every_saved_page():
    from modda.lexparse import flat_number, parse, repair_labels
    for f in LEXUZ.glob("*.html"):
        labels = [a.label for a in parse(f.read_text(encoding="utf-8")).articles]
        assert repair_labels([flat_number(x) for x in labels]) == labels, f.name


def test_repair_labels_rules():
    from modda.lexparse import repair_labels
    assert repair_labels(["194", "195", "1951", "1952", "196"]) == ["194", "195", "195-1", "195-2", "196"]
    assert repair_labels(["182", "183", "1842", "1843", "185"]) == ["182", "183", "184-2", "184-3", "185"]
    assert repair_labels(["1006", "1007", "1008"]) == ["1006", "1007", "1008"]
    assert repair_labels(["9", "10", "101", "11"]) == ["9", "10", "10-1", "11"]


def test_fix_numbers_and_router(con):
    from modda.corpus import fix_numbers
    from modda.router import lookup, route
    con.execute("UPDATE articles SET article_number = '31', id = id WHERE id = '9001:4'")   # 3, then 3¹ as "31"
    con.commit()
    res = fix_numbers(con)
    assert res["superscript_restored"] >= 1
    assert con.execute("SELECT article_label FROM articles WHERE id = '9001:4'").fetchone()[0] == "3-1"
    r = route("Namuna mehnat kodeksining 3¹-moddasi nima deydi?")
    assert r.kind == "exact" and r.document == "Mehnat kodeksi" and r.label == "3-1"
    assert route("MK 195-1-modda").label == "195-1" and route("мк 131-модда").label == "131"
    assert route("Taʼtil qancha?").kind == "hybrid"
    # lookup needs a code whose title contains "Mehnat kodeksi": the fixture is "Namuna mehnat kodeksi"
    assert lookup(con, r) == ["9001:4"]


def test_exact_reference_comes_first(indexed):
    from modda.corpus import fix_numbers
    con, store, emb = indexed
    fix_numbers(con)
    ctx = retrieve(con, store, emb, "fake", "MK 4-modda", k=2, mode="sparse")
    assert ctx[0].chunk_id == "9001:4"


# ----------------------------------------------------------------------------- full pipeline with events

def test_pipeline_emits_every_stage_and_api_shape(indexed):
    from modda.corpus import fix_numbers
    from modda.pipeline import ask
    from modda.rerank import OverlapReranker
    con, store, emb = indexed
    fix_numbers(con)
    events = []
    llm = FakeLLM("Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi [1].")
    out = ask(con, store, emb, llm, question="Taʼtil haqi qachon toʻlanadi?", embed_model="fake", llm_model="x",
              emit=events.append, k=2, reranker=OverlapReranker(), checked_at="2026-11-01")
    kinds = [e["type"] for e in events]
    assert kinds == ["query.received", "query.analyzed", "embedding.completed", "retrieval.started", "retrieval.completed",
                     "ranking.completed", "context.completed", "generation.started", "generation.completed",
                     "verification.completed", "scoring.completed", "answer.completed"]
    assert len({e["request_id"] for e in events}) == 1
    assert not out["unknown"] and out["checked_at"] == "2026-11-01"
    s = out["answer"][0]
    src = out["sources"][s["chunk_ids"][0]]
    assert src["article_no"] == "4" and s["quote"] and s["quote"].lower() in src["text"].lower()
    assert events[5]["data"]["reranker"] is True
    assert out["score"]["total"] == 1 and out["score"]["supported"] == 1 and out["score"]["score"] > 0
    assert out["sources"][s["chunk_ids"][0]]["chunk_id"] == s["chunk_ids"][0]


def test_pipeline_drops_unverified_numbers(indexed):
    from modda.pipeline import ask
    con, store, emb = indexed
    llm = FakeLLM("Taʼtil haqi 10 kun oldin toʻlanadi [1].")          # 10 is not in the source
    events = []
    out = ask(con, store, emb, llm, question="Taʼtil haqi qachon toʻlanadi?", embed_model="fake", llm_model="x",
              emit=events.append, k=2)
    assert out["unknown"] is True
    ver = next(e["data"] for e in events if e["type"] == "verification.completed")
    assert ver["failed"][0]["why"].startswith("manbada yoʻq son")
    assert out["score"]["supported"] == 0 and out["score"]["score"] == 0.0      # the scales show the rejection


def test_rss_parse():
    from modda.rss import parse_feed
    xml = """<rss><channel><item><title>Yangi qonun</title><link>/docs/-7000001</link>
      <pubDate>Mon, 02 Nov 2026 10:00:00 +0500</pubDate></item><item><title>x</title><link>https://lex.uz/uz</link></item></channel></rss>"""
    items = parse_feed(xml)
    assert items == [{"doc_id": "-7000001", "title": "Yangi qonun", "link": "https://lex.uz/docs/-7000001", "published": "2026-11-02"}]


# --------------------------------------------------------------------------- snapshot move (GPU computer → server)

def test_snapshot_fingerprint_and_mismatch(con, tmp_path):
    import gzip, json
    from modda import snapshot
    assert snapshot._fingerprint(["b", "a"]) == snapshot._fingerprint(["a", "b"])
    man = tmp_path / "x.manifest.json.gz"
    with gzip.open(man, "wt") as fh:
        json.dump({"chunks_fingerprint": "different", "chunks_total": 1, "dense": [], "sparse_only": []}, fh)
    (tmp_path / "x.snapshot").write_bytes(b"0")
    with pytest.raises(SystemExit, match="mos emas"):
        snapshot.import_(con, None, tmp_path / "x.snapshot", man)


def test_snapshot_multipart_streams_whole_file(tmp_path):
    from modda.snapshot import _Multipart
    f = tmp_path / "a.snapshot"
    f.write_bytes(b"x" * 100_000)
    body = _Multipart(f)
    out = b""
    while chunk := body.read(4096):
        out += chunk
    assert len(out) == body.len and out.count(b"x") == 100_000
    assert out.endswith(f"--{body.boundary}--\r\n".encode()) and b'filename="a.snapshot"' in out


def test_sparse_only_include_mvp(con):
    store = MemoryStore()
    n_plain = run_index(con, store, None, "fake", mode="sparse")
    mvp_left = con.execute("SELECT COUNT(*) FROM chunks WHERE indexed = 0 AND mvp = 1").fetchone()[0]
    assert mvp_left > 0
    n_mvp = run_index(con, store, None, "fake", mode="sparse", include_mvp=True)
    assert n_mvp == mvp_left
    assert con.execute("SELECT COUNT(*) FROM chunks WHERE indexed = 0").fetchone()[0] == 0


# --------------------------------------------------------------------------- data for the new frontend (frontend_idea/)

def test_pipeline_trace_diagnostics_and_streaming(indexed):
    from modda.pipeline import ask
    con, store, emb = indexed

    class StreamLLM:
        last_chat = {"prompt_tokens": 120, "output_tokens": 9, "gen_ms": 300.0, "tokens_per_s": 30.0}

        def chat(self, model, messages, on_token=None, **kw):
            text = "Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi [1]."
            for w in text.split(" "):
                on_token(w + " ")
            return text, 0.3

    events, trace = [], {}
    out = ask(con, store, emb, StreamLLM(), question="Taʼtil haqi qachon toʻlanadi?", embed_model="fake", llm_model="x",
              emit=events.append, k=2, trace=trace, diagnostics=True)
    by = {e["type"]: e["data"] for e in events}
    assert "".join(e["data"]["text"] for e in events if e["type"] == "generation.delta").strip().endswith("[1].")
    assert by["generation.completed"]["output_tokens"] == 9            # Ollama's counters passed through, not invented
    c = by["retrieval.completed"]["candidates"][0]
    assert {"score", "dense_rank", "sparse_rank", "doc_id"} <= set(c)
    assert by["query.analyzed"]["terms"] and by["embedding.completed"]["dim"] == 64
    assert trace["request_id"] == out["request_id"] and len(trace["vector"]) == 64 and trace["candidates"]
    assert by["scoring.completed"]["method"] == "lexical-support-v1"


def test_scoring_counts_rejected_sentences():
    from modda.rag import Context
    from modda.scoring import score_answer
    ctx = {"a": Context(1, "a", 1.0, "1-modda", "Taʼtil haqi kamida uch kun oldin toʻlanadi.", {})}
    res = score_answer([{"text": "Taʼtil haqi uch kun oldin toʻlanadi [1].", "chunk_ids": ["a"], "ok": True, "why": "ok"},
                        {"text": "Jarima 10 foiz.", "chunk_ids": ["a"], "ok": False, "why": "manbada yoʻq son: 10"}], ctx)
    assert res["total"] == 2 and res["supported"] == 1
    assert res["sentences"][0]["overlap"] == 1.0 and res["sentences"][1]["supported"] is False
    assert res["score"] == 50.0                                         # one fully matched, one rejected
    assert score_answer([], ctx)["score"] is None


def test_book_context_neighbours(con):
    from modda import library
    res = library.chunk_context(con, "9001:4", n=5)
    labels = [a["label"] for a in res["articles"]]
    assert labels == ["3", "4"] and res["articles"][1]["is_target"] and res["document"]["doc_id"] == "9001"
    assert library.chunk_context(con, "nope") is None
    docs = library.search_documents(con, "soliq")
    assert [d["doc_id"] for d in docs] == ["9002"] and docs[0]["articles"] == 2
    assert [a["label"] for a in library.document_articles(con, "9002")["articles"]] == ["7", "8"]


def test_projection_is_reproducible(indexed, tmp_path):
    import numpy as np
    from modda import projection
    con, store, emb = indexed
    sample = store.sample_vectors(100) * 3                              # small index: repeat to reach 10 points
    sample = [(f"{c}#{i}", v, p) for i, (c, v, p) in enumerate(sample)]
    p1, p2 = projection.fit(sample), projection.fit(sample)
    assert p1.version == p2.version and p1.components.shape == (3, 64)
    q = emb.embed("fake", ["taʼtil haqi"])[0]
    assert np.allclose(p1.apply([q]), p2.apply([q]))
    assert 0 < sum(p1.explained) <= 1.0001


def test_model_card_reads_only_reported_fields():
    from modda.modelinfo import card
    show = {"details": {"family": "qwen3", "parameter_size": "8.2B", "quantization_level": "Q4_K_M"},
            "model_info": {"general.architecture": "qwen3", "qwen3.block_count": 36, "qwen3.embedding_length": 4096,
                           "qwen3.attention.head_count": 32, "qwen3.attention.head_count_kv": 8,
                           "qwen3.feed_forward_length": 12288, "qwen3.context_length": 40960}}
    c = card(show, "qwen3:8b")
    assert c["layers"] == 36 and c["kv_heads"] == 8 and c["head_dim"] == 128 and c["head_dim_derived"]
    assert "experts" not in c and card({}, "x") == {"name": "x", "source": "ollama /api/show"}


def test_ollama_stats_from_nanoseconds():
    from modda.llm import _stats
    s = _stats({"prompt_eval_count": 100, "eval_count": 50, "eval_duration": 2_000_000_000, "total_duration": 3_500_000_000})
    assert s == {"prompt_tokens": 100, "output_tokens": 50, "gen_ms": 2000.0, "total_ms": 3500.0, "tokens_per_s": 25.0}


def test_stale_by_id_and_by_title():
    from modda.pipeline import _stale_fields
    from modda.rss import StaleIndex
    ix = StaleIndex([
        {"doc_id": "7000001", "title": "Oʻzbekiston Respublikasining Mehnat kodeksiga oʻzgartish va qoʻshimchalar "
         "kiritish toʻgʻrisida", "link": "https://lex.uz/docs/7000001", "published": "2026-11-03"},
        {"doc_id": "7000002", "title": "Oʻzbekiston Respublikasi Prezidentining Qarori, 02.11.2026 yildagi PQ-412-son. "
         "Qishloq xoʻjaligini rivojlantirish chora-tadbirlari toʻgʻrisida", "link": "x", "published": "2026-11-02"}])
    assert ix.lookup("1", "Oʻzbekiston Respublikasining Mehnat kodeksi")["match"] == "title"
    assert ix.lookup("1", "Меҳнат кодекси")["match"] == "title"                  # Cyrillic title, same act
    assert ix.lookup("1", "Oʻzbekiston Respublikasining Soliq kodeksi") is None    # another code
    assert ix.lookup("1", "Oʻzbekiston Respublikasining Qonuni") is None           # only generic words
    assert ix.lookup("7000002", "")["match"] == "id" and "7000002" in ix
    f = _stale_fields(ix, {"doc_id": "5", "doc_title": "Oʻzbekiston Respublikasining Mehnat kodeksi"})
    assert f["stale"] and f["stale_info"]["published"] == "2026-11-03"
    assert _stale_fields(set(), {"doc_id": "5"}) == {"stale": False}
    assert _stale_fields({"5"}, {"doc_id": "5"})["stale"]                        # old set form still works


def test_verifier_rejects_cited_sentence_the_source_does_not_say():
    from modda.pipeline import verify
    from modda.rag import Context
    c = Context(chunk_id="c1", n=1, score=1.0, header="Mehnat kodeksi, 216-modda",
                text="Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi yigirma bir kalendar kunni tashkil etadi.", meta={})
    ok, _ = verify({"text": "Har yilgi asosiy mehnat taʼtili yigirma bir kalendar kun.", "chunk_ids": ["c1"]}, {"c1": c})
    assert ok
    ok, why = verify({"text": "Jinoyat kodeksida oʻgʻirlik uchun jazo umuman belgilanmagan va bu harakat ruxsat etiladi.",
                      "chunk_ids": ["c1"]}, {"c1": c})
    assert not ok and "mos emas" in why


def test_calibration_picks_tau_between_positives_and_negatives():
    from modda.calibrate import calibrate, write_env

    class E:
        def embed(self, model, texts):
            return [[1.0 if ("modda" in t.lower() or "kodeks" in t.lower()) else 0.2] for t in texts]

    class S:
        def search_dense(self, vec, limit):
            return [type("H", (), {"score": 0.62 if vec[0] == 1.0 else 0.41})()]

    golden = [{"question": f"Mehnat kodeksi {i}-modda?", "answerable": True} for i in range(30)]
    golden += [{"question": "Ob-havo qanday?", "answerable": False}]
    rep = calibrate(S(), E(), "bge-m3", golden)
    assert rep["tau"] == 0.62 and rep["negatives_blocked"] == 1.0 and rep["positives_kept"] == 1.0


def test_write_env_replaces_only_its_key(tmp_path):
    from modda.calibrate import write_env
    (tmp_path / ".env").write_text("LLM_MODEL=qwen3:8b\nDENSE_TAU=0.3\n", encoding="utf-8")
    write_env(tmp_path, "DENSE_TAU", "0.55")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "LLM_MODEL=qwen3:8b\nDENSE_TAU=0.55\n"
    write_env(tmp_path, "DENSE_TAU", None)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "LLM_MODEL=qwen3:8b\n"
