# Modda — Legal Intelligence Graph (yangi frontend)

Dizayn: [`../frontend_idea.md`](../frontend_idea.md) **§0 (v2)** — ustun turadi. Vizual namuna: `reference/`.

Savol yuborilganda: kitob ochilib «qidiradi» → markazdagi **Mind** atrofidagi 8 bosqich backend hodisalari bilan yonadi (markazda — ayni bajarilayotgan bosqich) → kitob topilgan moddaga ochiladi → **chap sahifada javob** [1] [2] havolalari bilan yoziladi (soʻzma-soʻz, LLM yozayotganda), **oʻng sahifada manba ±5 qoʻshni modda bilan**. Havolani bossangiz — kitob oʻsha manbaga varaqlanadi. **Adolat haykali**ni bossangiz — kamera haykalning yuqori qismiga yaqinlashadi; uning **oʻz 3D tarozisida** bir pallada javob bahosi, ikkinchisida **rasmiy Lex.uz logotipi (3D)** turadi; tarozi bahoga qarab ogʻadi, pallalar **olov kabi** yonadi (2D tarozi yoʻq). Esc — orqaga.

## Ishga tushirish

```bash
# 1-terminal: API (loyiha ildizida)
cd ~/Lex_Uz_AI_Agent && source .venv/bin/activate
python -m modda serve                 # :8080 — FastAPI yoʻq boʻlsa, oʻzi standart kutubxonadagi serverga oʻtadi

# 2-terminal: sayt
cd ~/Lex_Uz_AI_Agent/frontend_idea
npm install
npm run dev                           # http://localhost:5174  (API yoʻllari :8080 ga proksi)
```

* **Namuna rejimi** (backend’siz): http://localhost:5174/?demo — `public/demo/fixture.json` dagi yozuv; sahifada doim «Namuna rejimi» yozuvi turadi. Oʻz backend’ingizdan yangi yozuv: `python frontend_idea/scripts/record_demo.py "Savol"`.
* **WebGL’siz koʻrinish**: `?nowebgl` (avtomatik ham yoqiladi).
* **Build**: `npm run build` → `dist/`; API bilan bitta portda: `MODDA_WEB_DIST=frontend_idea/dist python -m modda serve` → http://localhost:8080
* Boshqa kompyuterdagi API: `MODDA_API_URL=http://192.168.1.61:8080 npm run dev` (yoki build uchun `.env.local` da `VITE_MODDA_API=`).

## Testlar

```bash
npm test                              # holat mashinasi, SSE parser (node --test, 8 ta)
npx playwright install chromium       # bir marta
npm run build && (cd .. && MODDA_WEB_DIST=frontend_idea/dist python -m modda serve) &
npm run test:e2e                      # butun yoʻl, 5 oʻlcham, WebGL’siz rejim → test-results/
cd .. && python -m pytest -q          # backend (yangi endpointlar bilan)
```

## Tuzilish

```text
index.html                 sahifa skeleti (semantik HTML: tugmalar, dialoglar, aria-live)
src/main.js                hammasini bogʻlaydi: savol → hodisalar → kitob / graf / haykal
src/config.js              8 bosqich (nom, rang, belgi), API manzili, demo / qisqartirilgan harakat
src/core/research.js       holat mashinasi: backend hodisalari → holat (sof funksiyalar, testlangan)
src/api/                   client.js (fetch + xatolar), stream.js (SSE + /ask zaxirasi), backend.js (haqiqiy / ?demo)
src/scene/                 stage.js (renderer, kamera, yorugʻlik), book.js, pages.js (sahifa tekstura + bosiladigan joylar),
                           graph.js (Mind + 8 tugun), justice.js (haykal .glb yoki oʻrinbosar), backdrop.js (kutubxona foni)
src/ui/                    nodes.js, inspectors.js (8 bosqich), mind.js, scales.js, reader.js, documents.js, help.js, overlay.js
src/viz/                   heatmap (1024 qiymat), cloud (PCA 3D), layers (qatlamlar 3D), rankflow (RRF)
src/styles/                tokens.css (frontend_idea.md §2.2), layout, components, inspector, responsive
src/assets/models/         lady-justice.glb (95 MB → 3.6 MB: scripts/optimize_model.py)
scripts/                   optimize_model.py, record_demo.py
tests/                     research.test.js (unit), e2e.mjs (Playwright)
```

## Backend’dan nima olinadi (hammasi haqiqiy)

| Koʻrinish | Manba |
|---|---|
| 8 bosqich holati, vaqtlari | `POST /ask/stream` hodisalari (`query.*`, `embedding.completed`, `retrieval.*`, `ranking.completed`, `context.completed`, `generation.started/delta/completed`, `verification.completed`, `scoring.completed`, `answer.completed`, `stage.failed`) |
| Dense va BM25 roʻyxatlari, ballar | `retrieval.completed`: `candidates[].score / dense_rank / sparse_rank`, `dense_list`, `sparse_list` |
| Aniq 1024 qiymat, PCA 3D, nomzodlar kosinusi | `GET /ask/{request_id}/embedding` (30 daqiqa xotirada) |
| Mind: qatlamlar, kenglik, attention boshlari | `GET /model/info` (Ollama `/api/show`) |
| Kitobning oʻng sahifasi (±5 modda) | `GET /chunks/{id}/context?n=5`, `GET /articles/{id}/context` |
| Hujjatlar | `GET /documents?q=`, `GET /documents/{doc_id}` |
| «Onlayn» belgisi | `GET /health` → `services.ollama`, `services.qdrant`, `ready` |

**Mock yoʻq.** Faqat `?demo` — oldindan yozib olingan haqiqiy javob, banner bilan. Backend bermagan narsa «Mavjud emas» deb koʻrsatiladi.

## Cheklovlar (halol)

* **Neyron faollashuvlari va attention** koʻrsatilmaydi — Ollama ularni bermaydi. Mind inspektori modelning *haqiqiy tuzilishini* (qatlamlar soni, kengligi) chizadi; har plastinkadagi 48 nuqta — namuna, sahifada shunday yozilgan.
* **Tokenlar roʻyxati** yoʻq (faqat soni) — Ollama embedding uchun tokenizer bermaydi.
* **Tarozi bahosi** — soʻz mosligi oʻlchovi (`lexical-support-v1`), yuridik xulosa emas; usuli «Gaplar» oynasida yozilgan.
* **Lex.uz logotipi** — `src/assets/models/lex_uz.svg` (Bobur qoʻshgan rasmiy fayl). SVG boʻlsa 3D logotip yasaladi; `.png`/`.webp`/`.jpg` boʻlsa — medalda rasm. Fayl boʻlmasa — «LEX.UZ» yozuvli medal.
* **Sifat** — sahifalar 2× aniqlikda chiziladi va ekran 2× gacha piksel bilan render qilinadi; FPS 40 dan tushsa piksellar oʻzi kamayadi. Kuchsiz kompyuterda: `?quality=low`.
* **Kitob modeli**: `3D_Models/book-…` faqat `.blend` (Blender’siz `.glb` ga oʻtkazib boʻlmaydi) va «Shahnoma» bezakli. Sahifalarida haqiqiy matn va gerbli muqova kerakligi uchun kitob Three.js’da yasalgan (`scene/book.js`). Blender’da `.glb` eksport qilsangiz, muqova bezagi sifatida qoʻshish mumkin.
* **Haykal litsenziyasi**: Sketchfab muallifi va litsenziyasini `src/assets/models/ATTRIBUTION.txt` ga yozing.
* Shriftlar Google Fonts’dan yuklanadi (internet boʻlmasa — tizim shriftlari).
* Sinov shu kompyuterda: haqiqiy backend kodi + haqiqiy Qdrant 1.20 + 10 ta Lex.uz kodeksi (4 028 modda) + **sinov LLM’i** (GPU yoʻq). Haqiqiy `qwen3:8b` bilan Bobur’ning kompyuterida tekshiriladi.
