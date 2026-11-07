# Modda — Lex.uz qonunchiligidan aniq javob

Oʻzbek tilidagi huquqiy savolga **Lex.uz moddalariga tayangan**, har bir gapi manba bilan tekshirilgan qisqa javob beradigan lokal AI-agent. Ishonchli manba topilmasa — **«Bilmayman»**. Javob 3D kitob ichida (chapda javob, oʻngda manba moddasi ±5 qoʻshni modda bilan), javobning manbaga mosligi — Adolat haykali tarozisida.

> Yuridik maslahat emas. Rasmiy matn — [lex.uz](https://lex.uz).

## Qanday ishlaydi

```
savol → marshrut (aniq havola / qidiruv) → bge-m3 vektor + BM25 → Qdrant gibrid qidiruv (RRF)
      → τ: savol hech bir moddaga yaqin boʻlmasa «Bilmayman» (LLM chaqirilmaydi)
      → LLM (Ollama, qwen3:8b) faqat berilgan moddalar bilan, [n] havolalar bilan yozadi
      → iqtibos tekshiruvchi: havola · raqamlar manbada · soʻzlar manbada → oʻtmagan gap olib tashlanadi
      → tarozi bahosi «manbaga moslik» + RSS: «Lex.uz’da oʻzgargan boʻlishi mumkin» belgisi
```

Har bosqich saytda jonli koʻrinadi (SSE hodisalari): Mind atrofidagi graf tugunini bossangiz — oʻsha bosqichning haqiqiy maʼlumoti (vektor, PCA 3D, BM25 soʻzlari, RRF, LLM hisoblagichlari, tekshiruv).

| Qism | Texnologiya |
|---|---|
| Korpus | Hugging Face’dagi Lex.uz nusxasi (qatʼiy versiya): 24 267 hujjat, 54 173 modda → 183 170 boʻlak |
| Qidiruv | bge-m3 (1024 oʻlcham) + BM25, Qdrant 1.20, RRF |
| LLM | Ollama: `qwen3:8b` (bakeoff: `gemma4:e4b`, Llama-3.1-8B-Uz) |
| Baza | SQLite yoki PostgreSQL |
| API | FastAPI (yoki standart kutubxona serveri) — `src/modda/api.py`, `service.py` |
| Sayt | `frontend_idea/` — Vite, Three.js, GSAP |

**Sifat (45 oltin savol, toʻliq indeks):** gibrid Recall@5 **0,911**, MRR **0,766**, p50 0,28 s (dense 0,800 / BM25 0,778). Toʻliq hisobot: `python -m modda report`.

## Ishga tushirish

**Windows + NVIDIA noutbuk (hammasini oʻrnatadi):** `scripts\setup_server.bat` → keyin `start_modda.bat` → http://localhost:8080. Batafsil: [SERVER-NOUTBUK.md](SERVER-NOUTBUK.md).

**Qoʻlda:**

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev,api]"
ollama pull bge-m3 && ollama pull qwen3:8b
python -m modda ingest && python -m modda fix-numbers && python -m modda chunk
python -m modda snapshot-import modda-*.snapshot      # yoki: python -m modda index (GPU’da 1–3 soat)
python -m modda serve                                 # API :8080
cd frontend_idea && npm ci && npm run dev             # sayt :5174
```

| Buyruq | Nima |
|---|---|
| `python -m modda ask "savol"` | terminalda javob |
| `python -m modda eval` | Recall@5, MRR (dense / BM25 / gibrid) |
| `python -m modda bakeoff --models a,b` | LLM’larni bir xil kontekstda solishtirish |
| `python -m modda calibrate --write-env` | «Bilmayman» chegarasi τ → `.env` (`DENSE_TAU`) |
| `python -m modda rss` | Lex.uz RSS → «oʻzgargan boʻlishi mumkin» belgilari |
| `python -m modda report` | `data/reports/BAHOLASH.md` |
| `scripts\day3.bat`, `scripts\day4.bat` | GPU noutbukda: tekshiruv, bakeoff, demo savollar, τ, baholash, zaxira video |

Testlar: `pytest` (backend), `cd frontend_idea && npm test` (unit), `node tests/e2e.mjs http://localhost:8080 out/` (brauzer).

## Hujjatlar

* [lexuz-huquqiy-ai-yol-xaritasi-v3-5-kun.md](lexuz-huquqiy-ai-yol-xaritasi-v3-5-kun.md) — 5 kunlik reja va checklist
* [I_EXPLAIN.md](I_EXPLAIN.md) — loyihani noldan tushuntirish (§0.1 — rejadan amalga)
* [frontend_idea.md](frontend_idea.md) — sayt konsepsiyasi · [frontend_idea/README.md](frontend_idea/README.md)
* [KUN-1.md](KUN-1.md), [KUN-2.md](KUN-2.md), [KUN-3.md](KUN-3.md) — kunlik ishlar

## Cheklovlar

* Tarozi bahosi — soʻz mosligi oʻlchovi, yuridik xulosa emas.
* Korpus snapshot sanasidan keyingi oʻzgarishlar faqat RSS orqali **belgilanadi**, matn yangilanmaydi.
* Qidiruv va javob — lotin yozuvida; kirillcha savol avtomatik lotinchaga oʻgiriladi.
