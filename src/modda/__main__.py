"""Command line: python -m modda <command>

  doctor       Barcha talablarni tekshirish: Python paketlari, korpus, Ollama modellari, Qdrant, PostgreSQL, Node
  ingest       HF korpusi → PostgreSQL (normalizatsiya bilan)
  chunk        Moddalardan boʻlaklar yasash
  stats        Baza statistikasi
  bench-embed  Embedding tezligini oʻlchash va indekslash vaqtini hisoblash
  index        Boʻlaklarni Qdrant’ga yozish (toʻxtatib, qayta davom ettirish mumkin)
  ask          Savol berish
  eval         Qidiruv sifati: Recall@k, MRR, kechikish
  bakeoff      LLM modellarini bir xil kontekstda solishtirish
  sample       Oltin toʻplam yozish uchun tasodifiy moddalar
  find         Hujjat nomi va modda raqami boʻyicha topish
  fix-numbers  Yuqori indeksli modda raqamlarini tiklash (1951 → 195¹)
  rss          Lex.uz RSS’dagi yangi hujjatlarni saqlash
  serve        Sayt uchun API: /health, /ask, /ask/stream
  export-golden   Oltin toʻplam yozish uchun asosiy hujjatlardan haqiqiy moddalar
  fetch-fixtures  Parser testlari uchun Lex.uz sahifalarini saqlash (Crawl-delay 20 s)
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import get_settings


def _con(s):
    from .corpus import connect
    return connect(s.db_path, url=s.database_url or None)


def _store(s):
    from .store import QdrantStore
    return QdrantStore(s.qdrant_url, s.collection, s.embed_dim)


def _llm(s):
    from .llm import Ollama
    return Ollama(s.ollama_url)


# models the 5-day plan uses (bake-off candidates); the first two are required
PLAN_MODELS = ["bge-m3", "qwen3:8b", "gemma4:e4b", "hf.co/QuantFactory/Llama-3.1-8B-Instuct-Uz-GGUF:Q4_K_M"]


def _has_model(models: list[str], m: str) -> bool:
    base = m.split(":")[0]
    return any(x == m or x == f"{m}:latest" or (":" not in m and x.split(":")[0] == base) for x in models)


def cmd_doctor(s, a):
    """Checks every requirement of the project and says what to do about each missing one."""
    import shutil
    import subprocess
    from pathlib import Path

    from .corpus import find_article_files

    required_ok = True

    def line(ok, name, detail="", fix="", required=True):
        nonlocal required_ok
        mark = "✓" if ok else ("✗" if required else "–")
        print(f"  {mark} {name}{(': ' + detail) if detail else ''}")
        if not ok and fix:
            print(f"      → {fix}")
        if required and not ok:
            required_ok = False

    print("Python")
    import platform
    line(True, "Python", platform.python_version())
    for mod, pkg, req in (("requests", "requests", True), ("numpy", "numpy", True), ("pyarrow", "pyarrow", True),
                          ("psycopg", '"psycopg[binary]"', bool(s.database_url)),
                          ("sentence_transformers", '".[rerank]"  (2-kun)', False)):
        try:
            m = __import__(mod)
            line(True, mod, getattr(m, "__version__", ""))
        except ImportError:
            line(False, mod, "oʻrnatilmagan", f"uv pip install {pkg}", required=req)

    print("Korpus")
    files = find_article_files(s.corpus_dir) if s.corpus_dir.exists() else []
    line(bool(files), "HF articles", f"{len(files)} fayl" if files else str(s.corpus_dir),
         "huggingface-cli download sukhrobnurali/uzbek-legal-corpus --repo-type dataset --local-dir data/raw/hf")

    print(f"Ollama ({s.ollama_url})")
    from .llm import Ollama
    llm = Ollama(s.ollama_url, timeout=120)          # a health check must not wait 10 minutes
    try:
        ver = llm.version()
        models = llm.models()
        line(True, "server", f"v{ver}, {len(models)} model")
        for i, m in enumerate(PLAN_MODELS):
            line(_has_model(models, m), m, "", f"ollama pull {m}", required=i < 2 or m == s.llm_model)
        try:
            v = llm.embed(s.embed_model, ["Mehnat kodeksi 131-modda"])[0]
            line(len(v) == s.embed_dim, f"embedding ({s.embed_model})", f"oʻlcham {len(v)}",
                 f".env da EMBED_DIM={len(v)} qiling yoki boshqa model tanlang")
        except Exception as exc:
            line(False, f"embedding ({s.embed_model})", str(exc)[:160],
                 "ollama ps  (Stopping… holatida qolgan boʻlsa) → sudo systemctl restart ollama; KUN-1.md, 1-boʻlim")
        if _has_model(models, s.llm_model):
            try:
                txt, dt = llm.chat(s.llm_model, [{"role": "user", "content": "Bitta soʻz bilan javob ber: salom"}], num_ctx=512)
                line(bool(txt), f"chat ({s.llm_model})", f"{dt:.1f} s, «{txt[:30]}»")
            except Exception as exc:
                line(False, f"chat ({s.llm_model})", str(exc)[:160])
    except Exception as exc:
        line(False, "server", str(exc), "ollama serve   (yoki: systemctl status ollama)")

    print(f"Qdrant ({s.qdrant_url})")
    try:
        st = _store(s)
        ver = st.ping()
        line(True, "server", f"v{ver}, kolleksiya `{s.collection}`: {st.count() if st.exists() else 'hali yoʻq'}")
    except Exception as exc:
        line(False, "server", str(exc), "docker start qdrant")

    print("Maʼlumotlar bazasi")
    try:
        con = _con(s)
        from .corpus import stats
        stt = stats(con)
        line(True, con.kind, f"{con.label} — {stt['articles']} modda, {stt['chunks']} boʻlak, {stt['chunks_indexed']} indekslangan")
        if not s.database_url:
            line(False, "DATABASE_URL", "boʻsh — SQLite ishlatilmoqda", ".env ga DATABASE_URL=postgresql://… yozing", required=False)
    except Exception as exc:
        line(False, "PostgreSQL" if s.database_url else "SQLite", str(exc)[:200],
             "KUN-1.md, 0-bo‘lim: PostgreSQL konteynerini ishga tushiring")

    print("Reranker (2-kun)")
    hub = Path.home() / ".cache" / "huggingface" / "hub" / "models--BAAI--bge-reranker-v2-m3"
    line(hub.exists(), "BAAI/bge-reranker-v2-m3", str(hub) if hub.exists() else "yuklanmagan",
         "huggingface-cli download BAAI/bge-reranker-v2-m3", required=False)

    print("Sayt va vositalar")
    for tool, fix in (("docker", "Docker (Linux server uchun; Windows’da shart emas)"), ("node", "Node.js 20+"), ("npm", "Node.js bilan keladi")):
        path = shutil.which(tool)
        ver = ""
        if path:
            try:                                       # the full path: on Windows npm is npm.cmd
                ver = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
            except Exception:
                pass
        line(bool(path), tool, ver, fix, required=False)
    from .config import ROOT
    nm = ROOT / "web" / "node_modules" / "three"
    line(nm.exists(), "web/node_modules (three, gsap, vite)", "", "cd web && npm install", required=False)

    print("\nMajburiy talablar bajarildi ✓" if required_ok else "\n✗ belgili qatorlarni tuzating (– — hozircha shart emas).")


def cmd_ingest(s, a):
    from .corpus import ingest
    n = ingest(s.corpus_dir, _con(s), limit=a.limit)
    print(f"Yozildi: {n} qator → {'PostgreSQL' if s.database_url else s.db_path}")


def cmd_chunk(s, a):
    from .chunking import build_chunks
    n = build_chunks(_con(s), rebuild=a.rebuild)
    print(f"Yangi boʻlaklar: {n}")
    cmd_stats(s, a)


def cmd_stats(s, a):
    from .corpus import stats
    print(json.dumps(stats(_con(s)), ensure_ascii=False, indent=2))


def cmd_bench(s, a):
    from .indexing import bench
    res = bench(_con(s), _llm(s), s.embed_model, n=a.n, batch=a.batch)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_index(s, a):
    from .indexing import run_index
    con, st = _con(s), _store(s)
    if a.recreate:
        st.ensure_collection(recreate=True)
        con.execute("UPDATE chunks SET indexed=0")
        con.commit()
    from .indexing import DENSE_TYPES
    types = a.types.split(",") if a.types else None
    try:
        if a.mvp:                                       # dense for the Constitution and codes
            n = run_index(con, st, _llm(s), s.embed_model, mvp_only=True, limit=a.limit, batch=a.batch)
        elif a.sparse_only:                             # BM25 only, no Ollama
            n = run_index(con, st, None, s.embed_model, mode="sparse", types=types, limit=a.limit,
                          include_mvp=a.include_mvp)
        elif a.all_dense:
            n = run_index(con, st, _llm(s), s.embed_model, types=types, limit=a.limit, batch=a.batch)
        else:                                           # default: BM25 for everything first, then dense tier
            n = run_index(con, st, None, s.embed_model, mode="sparse", limit=a.limit)
            n += run_index(con, st, _llm(s), s.embed_model, types=types or list(DENSE_TYPES), limit=a.limit, batch=a.batch)
    except KeyboardInterrupt:
        print("\nToʻxtatildi. Qayta ishga tushirsangiz, qolgan joydan davom etadi.")
        return
    print(f"Indekslandi: {n}. Qdrant’da jami: {st.count()}")


def cmd_ask(s, a):
    from .rag import answer
    ans = answer(_con(s), _store(s), _llm(s), _llm(s), embed_model=s.embed_model,
                 llm_model=a.model or s.llm_model, question=a.question, k=a.k, mode=a.mode)
    if a.show_context:
        for c in ans.contexts:
            print(f"--- [{c.n}] {c.score:.3f} {c.header}\n{c.text[:400]}\n")
    if ans.unknown:
        print("Bu savolga Lex.uz maʼlumotlari asosida ishonchli javob topilmadi.")
    else:
        print(ans.text)
        print()
        print(ans.source_block())
    print(f"\n({ans.model}, {ans.llm_seconds:.1f} s. Rasmiy yuridik maslahat emas.)")


def cmd_eval(s, a):
    from .evaluation import eval_retrieval, load_golden, only_indexed
    con = _con(s)
    items, skipped = only_indexed(con, load_golden(s.golden_path))
    if skipped:
        print(f"Indeks toʻliq emas: kutilgan moddasi hali indekslanmagan {skipped} ta savol hisobga olinmadi.")
    rep = eval_retrieval(con, _store(s), _llm(s), s.embed_model, items, k=a.k, modes=a.modes.split(","))
    print(json.dumps(rep, ensure_ascii=False, indent=2))


def cmd_calibrate(s, a):
    from .calibrate import calibrate, write_env
    from .config import ROOT
    from .evaluation import load_golden
    rep = calibrate(_store(s), _llm(s), s.embed_model, load_golden(s.golden_path), keep=a.keep)
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    (s.reports_dir / "calibration.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "rows"}, ensure_ascii=False, indent=2))
    for r in rep["rows"]:
        print(f"  {'+' if r['positive'] else '−'} {r['dense_top']:.3f}  {r['question'][:90]}")
    if a.write_env:
        p = write_env(ROOT, "DENSE_TAU", None if rep["tau"] is None else str(rep["tau"]))
        print(f"\n{p}: DENSE_TAU={rep['tau'] if rep['tau'] is not None else '(oʻchirildi)'}")


def cmd_report(s, a):
    from .report import build
    path, text = build(s.reports_dir, s.golden_path)
    print(text)
    print(f"\nHisobot: {path}")


def cmd_bakeoff(s, a):
    from .evaluation import bakeoff, load_golden, only_indexed, spread
    con = _con(s)
    items, skipped = only_indexed(con, load_golden(s.golden_path))
    if skipped:
        print(f"Indeks toʻliq emas: {skipped} ta savol hisobga olinmadi (kutilgan moddasi hali indekslanmagan).")
    chosen = spread(items, a.n)
    path = bakeoff(con, _store(s), _llm(s), _llm(s), embed_model=s.embed_model,
                   models=a.models.split(","), items=chosen, out_dir=s.reports_dir, k=a.k)
    print(f"\nHisobot: {path}")
    print(path.read_text(encoding="utf-8"))


def cmd_sample(s, a):
    con = _con(s)
    sql = ("SELECT a.* FROM chunks c JOIN articles a ON a.id = c.article_id WHERE c.part_no = 1 "
           "AND COALESCE(a.quality_flag, '') = '' AND length(a.article_text) BETWEEN 200 AND 2500")
    if a.mvp:
        sql += " AND c.mvp = 1"
    rows = con.execute(sql + " ORDER BY RANDOM() LIMIT ?", (a.n,)).fetchall()
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    out = s.reports_dir / "sample-articles.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({k: r[k] for k in ("id", "doc_id", "doc_title", "doc_type", "article_number",
                                                     "article_title", "article_text", "source_url", "status")},
                                ensure_ascii=False) + "\n")
    print(f"{len(rows)} ta modda → {out}")


def cmd_find(s, a):
    con = _con(s)
    sql, args = "SELECT id, doc_id, doc_title, article_number, article_title, source_url FROM articles WHERE 1=1", []
    if a.title:
        sql += " AND LOWER(doc_title) LIKE LOWER(?)"
        args.append(f"%{a.title}%")
    if a.article:
        sql += " AND article_number = ?"
        args.append(a.article)
    for r in con.execute(sql + " LIMIT 20", args):
        print(dict(r))


def cmd_snapshot_export(s, a):
    from .snapshot import export
    export(_con(s), _store(s), s.reports_dir.parent / "exports")


def cmd_snapshot_import(s, a):
    from pathlib import Path
    from .snapshot import import_
    import_(_con(s), _store(s), Path(a.file), Path(a.manifest) if a.manifest else None, force=a.force)


def cmd_fix_numbers(s, a):
    from .corpus import fix_numbers
    print(json.dumps(fix_numbers(_con(s)), ensure_ascii=False, indent=2))


def cmd_rss(s, a):
    from .rss import fetch, store
    items = fetch()
    n = store(_con(s), items)
    print(f"RSS: {n} ta yozuv saqlandi. Oxirgilari:")
    for i in items[:5]:
        print(f"  {i['published']}  {i['title'][:90]}  {i['link']}")


def cmd_serve(s, a):
    try:
        if a.stdlib:
            raise ImportError
        import fastapi  # noqa: F401
        import uvicorn
    except ImportError:
        if not a.stdlib:
            print('FastAPI oʻrnatilmagan — standart kutubxonadagi server ishlatiladi (xuddi shu API). '
                  'FastAPI uchun: uv pip install -e ".[api]"', flush=True)
        from .devserver import serve
        return serve(a.host, a.port)
    uvicorn.run("modda.api:app", host=a.host, port=a.port, reload=False)


def cmd_export_golden(s, a):
    from .tools import export_golden
    export_golden(_con(s), s.reports_dir, per_doc=a.per_doc)


def cmd_fetch_fixtures(s, a):
    from .config import ROOT
    from .tools import fetch_fixtures
    saved = fetch_fixtures(_con(s), ROOT / "tests" / "fixtures" / "lexuz", limit=a.n)
    print(f"{len(saved)} ta sahifa saqlandi → tests/fixtures/lexuz/")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):           # Windows consoles and pipes: print Uzbek letters, never crash
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="modda", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    x = sub.add_parser("ingest"); x.add_argument("--limit", type=int); x.set_defaults(fn=cmd_ingest)
    x = sub.add_parser("chunk"); x.add_argument("--rebuild", action="store_true"); x.set_defaults(fn=cmd_chunk)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    x = sub.add_parser("bench-embed"); x.add_argument("--n", type=int, default=256)
    x.add_argument("--batch", type=int, default=32); x.set_defaults(fn=cmd_bench)
    x = sub.add_parser("index"); x.add_argument("--mvp", action="store_true", help="faqat Konstitutsiya va kodekslar")
    x.add_argument("--limit", type=int); x.add_argument("--batch", type=int, default=32)
    x.add_argument("--recreate", action="store_true", help="kolleksiyani oʻchirib, boshidan")
    x.add_argument("--sparse-only", action="store_true", help="faqat BM25 (Ollama kerak emas, tez)")
    x.add_argument("--include-mvp", action="store_true",
                   help="--sparse-only bilan: dense boʻlmagan kodeks boʻlaklariga ham BM25 (index --mvp ishlamayotganda)")
    x.add_argument("--all-dense", action="store_true", help="hamma boʻlakka bge-m3 (CPU’da juda sekin)")
    x.add_argument("--types", help="doc_type roʻyxati, masalan: law,decree"); x.set_defaults(fn=cmd_index)
    x = sub.add_parser("ask"); x.add_argument("question"); x.add_argument("--model")
    x.add_argument("--k", type=int, default=5); x.add_argument("--mode", choices=["dense", "sparse", "hybrid"], default="hybrid")
    x.add_argument("--show-context", action="store_true"); x.set_defaults(fn=cmd_ask)
    x = sub.add_parser("eval"); x.add_argument("--k", type=int, default=5)
    x.add_argument("--modes", default="dense,sparse,hybrid"); x.set_defaults(fn=cmd_eval)
    x = sub.add_parser("bakeoff"); x.add_argument("--models", required=True, help="vergul bilan: qwen3:8b,gemma4:e4b")
    x.add_argument("--n", type=int, default=20); x.add_argument("--k", type=int, default=5); x.set_defaults(fn=cmd_bakeoff)
    x = sub.add_parser("calibrate", help="«Bilmayman» uchun τ (savol ↔ eng yaqin modda oʻxshashligi)")
    x.add_argument("--keep", type=float, default=0.97); x.add_argument("--write-env", action="store_true")
    x.set_defaults(fn=cmd_calibrate)
    sub.add_parser("report", help="toʻliq baholash hisoboti (data/reports → BAHOLASH.md)").set_defaults(fn=cmd_report)
    x = sub.add_parser("sample"); x.add_argument("--n", type=int, default=60); x.add_argument("--mvp", action="store_true")
    x.set_defaults(fn=cmd_sample)
    x = sub.add_parser("find"); x.add_argument("--title"); x.add_argument("--article"); x.set_defaults(fn=cmd_find)
    sub.add_parser("fix-numbers", help="yuqori indeksli modda raqamlarini tiklash (1951 → 195¹)").set_defaults(fn=cmd_fix_numbers)
    sub.add_parser("snapshot-export", help="tayyor indeksni boshqa kompyuterga koʻchirish uchun saqlash").set_defaults(fn=cmd_snapshot_export)
    x = sub.add_parser("snapshot-import", help="boshqa kompyuterda yasalgan indeksni yuklash")
    x.add_argument("file"); x.add_argument("--manifest"); x.add_argument("--force", action="store_true")
    x.set_defaults(fn=cmd_snapshot_import)
    sub.add_parser("rss", help="Lex.uz RSS’dagi yangi hujjatlarni saqlash").set_defaults(fn=cmd_rss)
    x = sub.add_parser("serve", help="FastAPI server: /health, /ask, /ask/stream")
    x.add_argument("--host", default="0.0.0.0"); x.add_argument("--port", type=int, default=8080)
    x.add_argument("--stdlib", action="store_true", help="FastAPI’siz server (xuddi shu API)"); x.set_defaults(fn=cmd_serve)
    x = sub.add_parser("export-golden", help="oltin toʻplam uchun asosiy hujjatlardan haqiqiy moddalar")
    x.add_argument("--per-doc", type=int, default=6); x.set_defaults(fn=cmd_export_golden)
    x = sub.add_parser("fetch-fixtures", help="parser testlari uchun 10 ta Lex.uz sahifasi (20 s oraliq bilan)")
    x.add_argument("--n", type=int, default=10); x.set_defaults(fn=cmd_fetch_fixtures)
    a = p.parse_args(argv)
    try:
        a.fn(get_settings(), a)
    except (RuntimeError, SystemExit) as exc:
        if isinstance(exc, SystemExit) and not isinstance(exc.code, str):
            raise
        print(f"Xato: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
