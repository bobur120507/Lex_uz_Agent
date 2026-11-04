# Lex.uz Huquqiy AI-agent — 5 kunlik reja (v3)

> **Vaziyat:** butun loyihani qurish uchun **5 kun** bor. Bu hujjat [v2 yoʻl xaritasini](lexuz-huquqiy-ai-yol-xaritasi-v2.md) shu muddatga moslaydi. v2 — toʻliq tizimning **uzoq muddatli rejasi** sifatida qoladi; bu fayl — **hozir nima va qaysi tartibda** qilinishini belgilaydi.
>
> **Asosiy tamoyil:** eng **sekin** va eng **katta** qadamlar birinchi boshlanadi. Kompyuter oʻzi ishlaydigan uzoq ishlar (yuklab olish, indekslash, modellarni sinash) — **1-kunning birinchi soatida**, odam vaqtini koʻp oladigan ishlar (test savollari) — **1-kundan**. Interfeysdagi eng katta va xavfli ish — **Three.js kitobi** — ham **1-kundan** boshlanadi; uni backend’ga ulash — 3-kunda.

Tushunchalar va vositalar jamoa uchun [I_EXPLAIN.md](I_EXPLAIN.md) da tushuntirilgan.

---

## 0. Holat: tekshiruv roʻyxati

> Har bir qadam tugaganda shu roʻyxat yangilanadi. Belgilar: ✅ bajarildi · 🔄 jarayonda · ⏸️ toʻxtatilgan · ↪️ boshqa yoʻl bilan · ❌ toʻsiq · ⬜ hali boshlanmagan. Batafsil buyruqlar — [KUN-1.md](KUN-1.md).
>
> **Oxirgi yangilanish:** 2026-11-04 18:35. 1-kun: MVP indeksi ishlayapti. 2-kun kodi tayyor (37 test). Toʻliq dense indeks — jamoadoshning GPU kompyuterida ([SETUP-WINDOWS.md](SETUP-WINDOWS.md)).

### 1-kun — uzoq ishlar va asos

| Holat | Qadam | Natija / izoh |
|---|---|---|
| ✅ | HF korpusi yuklandi | articles + documents (Parquet, 321 MB) |
| ✅ | Modellar: `bge-m3`, `qwen3:8b`, `gemma4:e4b`, Llama-3.1-8B-Uz | hammasi yuklangan |
| ✅ | Reranker fayllari (`bge-reranker-v2-m3`) | HF keshida; `sentence-transformers` — 2-kunda |
| ✅ | Qdrant v1.20.0 | ishlayapti, kolleksiya hali yoʻq |
| ✅ | PostgreSQL 17 (`modda-pg`, port **5434**) | 5433 band edi — 5434 ga oʻtkazildi |
| ✅ | Korpus → PostgreSQL (`ingest`, `chunk`) | **54 173** qator, **183 170** boʻlak, MVP: **12 269** boʻlak |
| ✅ | Loyiha kodi: normalizatsiya, chunker, BM25, Qdrant REST, oddiy RAG, baholash, solishtirish | 26 test (SQLite va PostgreSQL 16 da) |
| ✅ | **Oltin toʻplam: 60 savol** (45 ta javobi bor, 15 ta yoʻq) | `data/golden/golden.jsonl`; 14 hujjat, 6 toifa; har bir kutilgan modda korpusda tekshirildi |
| ✅ | 10 ta Lex.uz sahifasi | `tests/fixtures/lexuz/` (Crawl-delay 20 s) |
| ✅ | 3D kitob (`web/`): ochilish, varaqlash, sahifaga ochilish, javob paneli, gerbli muqova | brauzerda barcha holatlar tekshirildi |
| ✅ | Sayt: namuna savollar olib tashlandi, sarlavha qisqartirildi | «Qonunchilikdan aniq javob» |
| ✅ | Ollama qayta oʻrnatildi (v0.40.14), embedding ishlaydi | |
| ✅ | Qolgan qadamlar bitta skriptda: `bash scripts/finish_day1.sh --full` | qisman indeksda `eval`/`bakeoff` faqat indekslangan savollarni hisoblaydi (26 test) |
| ✅ | `bench-embed`: **0,22 boʻlak/s** (CPU) → MVP ≈ 15 soat (bench), amalda 0,5 boʻlak/s ≈ 4,5 soat; butun korpus ≈ 233 soat | rejani oʻzgartirdi (2-kun) |
| ⏸️ | MVP qismini indekslash (`index --mvp`, 12 269 boʻlak) | 14:14–17:10: **4 896 / 12 269** dense; toʻxtatildi — qolgani jamoadoshning GPU’sida (`setup_windows.bat`) |
| ⬜ | Birinchi savol (`ask`) | MVP indeksidan keyin |
| ⬜ | Modellarni solishtirish (`bakeoff`, 20 savol) → LLM tanlash | MVP indeksidan keyin |
| ⬜ | 3D kitob kadr/s — oʻz kompyuterda ≥ 45 | `cd web && npm run dev` → `?debug` |
| ↪️ | Tungi indekslash | oʻrniga: GPU kompyuterda toʻliq dense → `snapshot-import` |

### 2-kun — toʻliq qidiruv

> **Rejadagi oʻzgarish (1-kun, 14:14):** `bench-embed` — 0,22 boʻlak/s (GPU yoʻq, bge-m3 CPU’da). Butun korpus dense uchun ≈ 233 soat. Yechim — **ikki qatlamli indeks**: BM25 hamma 183 170 boʻlakka (daqiqalar), bge-m3 faqat kodeks, Konstitutsiya va qonunlarga (≈ 39 ming boʻlak). Batafsil: [KUN-2.md](KUN-2.md).

| Holat | Qadam | Izoh |
|---|---|---|
| ⏸️ | MVP dense indeks (12 269 boʻlak) | 4 896 tasi tayyor; qolgani GPU snapshot’da keladi |
| ✅ | Ikki qatlamli indeks: `index --sparse-only`, standart `index` = BM25 hammaga + dense qonunlarga | kod tayyor, test qilingan |
| ⬜ | BM25 — butun korpus (qolgan MVP boʻlaklari bilan) | `python -m modda index --sparse-only --include-mvp` |
| ⬜ | Qonunlar dense (≈ 27 ming boʻlak) — tunda | `finish_day1.sh --full` ning oxirgi qadami; GPU snapshot kelsa — shart emas |
| ✅ | **GPU kompyuter uchun bitta skript**: `scripts\setup_windows.bat` / `setup_windows.py` | Python, Ollama, HF CLI, Qdrant ni oʻzi oʻrnatadi; har bosqichda zaxira usul; vaqtlar va log; qolgan joydan davom etadi. Soxta Ollama + haqiqiy Qdrant 1.20 bilan boshidan oxirigacha sinaldi |
| ✅ | `snapshot-export` / `snapshot-import`: indeksni kompyuterdan kompyuterga koʻchirish | boʻlaklar roʻyxati tekshiriladi; 2 GB fayl xotiraga yuklanmaydi |
| ⬜ | **Toʻliq dense indeks (183 170 boʻlak) — jamoadoshning GPU’sida** → Bobur’da `snapshot-import` | jamoadosh: `git clone` + `setup_windows.bat` |
| ✅ | Gibrid qidiruv + RRF — `ask` da standart | |
| ⬜ | Gibrid / dense / BM25 ni oltin toʻplamda solishtirish (`eval`) | MVP indeksidan keyin |
| ✅ | Reranker moduli (CrossEncoder, ixtiyoriy) | CPU’da sekin — `eval` natijasiga qarab yoqiladi |
| ✅ | Savol marshrutizatori: «MK 131-modda», «195¹-modda», kirill | |
| ✅ | **Yuqori indeksli raqamlar** (1951 → 195¹): tiklash qoidasi | 10 sahifada 4 028/4 028 toʻgʻri; `ingest` + `fix-numbers` ni ishga tushirish kerak |
| ✅ | Lex.uz HTML parseri + testlar | bob/boʻlim, tahrir izohlari; «LexUZ sharhi» tashlanadi |
| ✅ | RSS oʻquvchi | `python -m modda rss` |
| ✅ | Oltin toʻplam → 60 savol | 1-kunda |
| ✅ | FastAPI: `/health`, `/ask`, `/ask/stream` (§12.4 hodisalari) | 3-kundan oldinga surildi |
| ✅ | 3D kitob yangi hodisalarni oʻqiydi (`api.js`) | |
| ✅ | Raqam tekshiruvchi (javobdagi har bir son manbada boʻlishi shart) | 3-kundagi toʻliq tekshiruvchining birinchi qismi |
| ⬜ | 3D: xatchoʻplar sahifa chetida (hozir HTML yorliqlar) | |

### 3-kun — «Bilmayman» va integratsiya

| Holat | Qadam |
|---|---|
| ⬜ | JSON strukturali chiqish |
| 🔄 | Iqtibos tekshiruvchi (raqamlar qismi tayyor) |
| ⬜ | τ kalibrlash |
| ✅ | `POST /ask/stream` (SSE) — 12.4 dagi hodisalar shartnomasi (2-kunda) |
| 🔄 | Saytni haqiqiy API’ga ulash (`python -m modda serve` + `npm run dev`) |
| ⬜ | RSS delta + «oʻzgargan boʻlishi mumkin» belgisi |

### 4-kun — sozlash va sifat

| Holat | Qadam |
|---|---|
| ⬜ | top-k, τ, prompt sozlash; kechikish |
| ⬜ | Prompt-injection sinovlari |
| ⬜ | Toʻliq baholash hisoboti |
| ⬜ | 3D: unumdorlik, zaxira rejim, klaviatura |

### 5-kun — muzlatish va demo

| Holat | Qadam |
|---|---|
| ⬜ | Yakuniy baholash |
| ⬜ | README, I_EXPLAIN yangilanishi |
| ⬜ | Demo ssenariysi va mashq, zaxira video |

### Yakuniy bosqich — «Legal Intelligence Graph» interfeysi (12-boʻlim)

| Holat | Qadam |
|---|---|
| ✅ | Konsepsiya tahlili va interaktiv demo (`demo/graph/index.html`) |
| ⬜ | Backend: 12.4 dagi hodisalar (`query.received` … `answer.completed`) SSE orqali |
| ⬜ | Yangi dizayn tizimi va bosh sahifa |
| ⬜ | Graf: haqiqiy hodisalarga ulangan tugunlar va yoʻllar |
| ⬜ | Topilgan hujjatlar paneli, javob sahifasi (65/35), «Grafda koʻrish» |
| ⬜ | Telefon, unumdorlik, qisqartirilgan harakat |

---

## Mundarija

0. [Holat: tekshiruv roʻyxati](#0-holat-tekshiruv-roʻyxati)
1. [12 haftadan 5 kunga: nima oʻzgardi](#1-12-haftadan-5-kunga-nima-oʻzgardi)
2. [MVP qamrovi: P0, P1, P2](#2-mvp-qamrovi-p0-p1-p2)
3. [Eng sekin qadamlar va kritik yoʻl](#3-eng-sekin-qadamlar-va-kritik-yoʻl)
4. [Jamoa va kompyuterlar](#4-jamoa-va-kompyuterlar)
5. [Kunma-kun reja](#5-kunma-kun-reja)
6. [Vaqt jadvali](#6-vaqt-jadvali)
7. [Orqada qolsak: kesish rejasi](#7-orqada-qolsak-kesish-rejasi)
8. [Interfeys: Three.js va «qidiruvchi kitob»](#8-interfeys-threejs-va-qidiruvchi-kitob)
9. [5 kunlik texnik soddalashtirishlar](#9-5-kunlik-texnik-soddalashtirishlar)
10. [Har kungi tartib va tayyorlik mezonlari](#10-har-kungi-tartib-va-tayyorlik-mezonlari)
11. [Xavflar (5 kun uchun)](#11-xavflar-5-kun-uchun)
12. [Yakuniy interfeys: Legal Intelligence Graph](#12-yakuniy-interfeys-legal-intelligence-graph)

---

## 1. 12 haftadan 5 kunga: nima oʻzgardi

| v2 (12 hafta) | v3 (5 kun) | Nega |
|---|---|---|
| Sprintlar ketma-ket, har biri 2 hafta | **Kunlar**, har kun oxirida ishlaydigan natija | Muddat 17 barobar qisqa |
| Ishlar mantiqiy tartibda (maʼlumot → qidiruv → himoya → UI) | Ishlar **davomiyligi** boʻyicha: uzoq fon ishlari birinchi | Indekslash va yuklab olish soatlab davom etadi — ularni kutib oʻtirmaslik kerak |
| Har kim oʻz kompyuterida hammasini ishga tushiradi | **Bitta “server” kompyuter** (eng kuchli GPU): Ollama + Qdrant; boshqalar unga tarmoq orqali ulanadi | Modellarni va indeksni har kim alohida yuklab, qayta hisoblamaydi |
| Toʻliq yangilanish tizimi (A + B + C qatlamlari, versiyalash, havolalar) | **A** (RSS) + **C** (javobdagi yangilik belgisi). B va versiyalash — v1.1 | Talab №6 bajariladi, lekin minimal kod bilan |
| Oltin toʻplam 50 → 200 savol | **60 savol** (shundan 15 tasi javobi yoʻq) | Odam vaqti eng tanqis resurs |
| docker-compose, CI, monitoring | Qdrant + Ollama — Docker’da; API — oddiy `uvicorn`; testlar — `pytest` qoʻlda | Infratuzilma 5 kunda sifat bermaydi |

**Oʻzgarmagan narsalar:** 10 ta talabning hammasi bajariladi — faqat soddalashtirilgan shaklda (2-boʻlim). Arxitektura, metadata sxemasi va «Bilmayman» mantigʻi — v2 dagidek.

---

## 2. MVP qamrovi: P0, P1, P2

* **P0** — boʻlmasa, loyiha topshirilmaydi.
* **P1** — sifat uchun muhim, 4-kun oxirigacha.
* **P2** — vaqt qolsa; aks holda v1.1.

| № | Talab | P0 (shart) | P1 | P2 / v1.1 |
|---|---|---|---|---|
| 1 | Lex.uz maʼlumotlarini oʻqish | HF snapshot (24 267 hujjat) | RSS + yangi hujjatlarni parse qilib indekslash | Kirill versiyalar, toʻliq crawler |
| 2 | Tuzilmali chunking | Modda = boʻlak, uzun modda → band + overlap | Ota-bola kontekst | Jadval/ilova turlari |
| 3 | Metadata | `doc_id`, `title`, `doc_type`, `article_no`, `url`, `status`, `chunk_type` | `amendment_note`, `okoz_codes`, `last_checked_at` | `valid_from/valid_to` versiyalash |
| 4 | Embedding + vektor baza | `bge-m3` dense → Qdrant | BM25 sparse + RRF | — |
| 5 | Faqat kontekstga tayangan javob | Qatʼiy prompt, ekstraktiv uslub | JSON chiqish | — |
| 6 | Savoldan oldin yangilik tekshiruvi | Javobda «Lex.uz bilan solishtirilgan sana» | RSS keshi → «oʻzgargan boʻlishi mumkin» ogohlantirishi | Aylanma tekshiruv (B qatlami) |
| 7 | Aniq manba | Manba bloki **koddan** (metadata) | Manba panelida modda matni + iqtibos belgilangan | — |
| 8 | «Bilmayman» | Reranker bali chegarasi τ | Iqtibos tekshiruvchi | Injection testlari toʻplami |
| 9 | Retriever | Dense qidiruv + filtr `status = active` | Reranker, savol marshrutizatori | Qisqartmalar lugʻatini kengaytirish |
| 10 | Bepul va lokal | Ollama + Qdrant | — | — |
| — | Interfeys | Savol → javob → manba (HTML panel) + 3D kitob: ochilish va ochiq turish + zaxira rejim | Varaqlab qidirish, haqiqiy nomzod xatchoʻplari, kerakli sahifaga ochilish (8-boʻlim) | Bloom, zarralar, ovoz; Telegram bot |
| — | Baholash | 60 savol, Recall@5, yolgʻon javob ulushi | MRR, P50/P95 kechikish | ragas |

---

## 3. Eng sekin qadamlar va kritik yoʻl

Quyidagi vaqtlar — **taxminiy**; har birini 1-kunda birinchi 1–2 soatda **oʻlchab**, keyin rejani aniqlashtiramiz.

| Qadam | Taxminiy vaqt | Kim/nima ishlaydi | Qachon boshlanadi | Qanday tezlashtiriladi |
|---|---|---|---|---|
| **Modellarni yuklab olish** — `qwen3:8b` (5,2 GB), `gemma4:e4b` (~6,6 GB), `bge-m3` (1,2 GB), reranker (~2,3 GB), Llama-3.1-8B-Uz GGUF (~5 GB) | 1–4 soat (internet tezligiga qarab) | Kompyuter, fonda | **1-kun, 0-soat** | Faqat server kompyuterga yuklash; boshqalar unga ulanadi |
| **HF korpusini yuklab olish** (321 MB) | 5–30 daqiqa | Kompyuter | **1-kun, 0-soat** | — |
| **Butun korpusni embedding qilish** — ~47 mln token, ~55–90 ming boʻlak | GPU’da **≈ 0,5–1,5 soat**, CPU’da **≈ 3–8 soat** | Server kompyuter, tunda | **1-kun kechqurun** (avval kichik qism kunduzi) | Avval **MVP qismi** (Konstitutsiya + asosiy kodekslar, ~5–8 ming boʻlak) → 1-kun tushgacha qidiruv ishlaydi; toʻliq korpus tunda. Ish **toʻxtab qolsa davom etadi** (bazada bor boʻlaklar oʻtkazib yuboriladi) |
| **Oltin toʻplam** — 60 savol + toʻgʻri modda + URL | **8–12 kishi-soat** | Odamlar | **1-kun, 1-soat** | Ikki kishiga boʻlish; savollarni HF korpusidagi moddalardan teskari yozish |
| **Modellarni solishtirish** — 3 LLM × 20 savol | 30–90 daqiqa (CPU’da sekin) | Kompyuter, fonda | **1-kun, modellar yuklangach** | Bitta skript, natija jadvalga |
| **Lex.uz HTML parseri** | 6–10 soat | Odam | **2-kun** | 10 ta sahifa 1-kunda **brauzerda qoʻlda** saqlanadi (crawl kerak emas) |
| **Reranker’ni ishlatish** | Har savolda 2–10 s (CPU) | Server | 2-kun | Top-30 emas, top-20; GPU boʻlsa fp16 |
| **τ ni kalibrlash** | 1–2 soat | Odam + skript | 3-kun | Oltin toʻplam tayyor boʻlishi shart |

### 3.1. Kritik yoʻl

Kritik yoʻl — kechiksa, butun loyiha kechikadigan zanjir:

```mermaid
flowchart LR
    D["Modellar va korpusni<br/>yuklab olish<br/>1-kun, 0-soat"] --> S["MVP qismi indekslandi<br/>1-kun tush"]
    S --> F["Toʻliq korpus indekslandi<br/>1-kun tunda"]
    F --> H["Gibrid qidiruv + reranker<br/>2-kun"]
    G["Oltin toʻplam 60 savol<br/>1–2-kun"] --> T["τ kalibrlash<br/>3-kun"]
    H --> T
    T --> I["UI bilan integratsiya<br/>3–4-kun"]
    K["Three.js kitob sinovi<br/>1-kun"] --> K2["Varaqlash + xatchoʻplar<br/>2-kun"]
    K2 --> I
    I --> R["Yakuniy baholash va demo<br/>5-kun"]
```

> **Qoida:** kritik yoʻldagi ishni bajarayotgan odamga boshqa vazifa berilmaydi. Fon ishi (indekslash) ishlayotganda o‘sha kompyuterda og‘ir boshqa ish ishga tushirilmaydi.

---

## 4. Jamoa va kompyuterlar

| Yoʻnalish | Masʼuliyat | 5 kun ichidagi asosiy natija |
|---|---|---|
| **A — Maʼlumot** | HF → PostgreSQL, normalizatsiya, chunking, indekslash ishi, RSS, Lex.uz parseri | Toʻliq indeks + yangi hujjatlar oqimi |
| **B — Qidiruv va AI** | Qdrant soʻrovlari, BM25 + RRF, reranker, marshrutizator, LLM, prompt, tekshiruvchi, τ | `/ask` uchidan-uchigacha ishlaydi va «Bilmayman» deya oladi |
| **C1 — Sifat** | Oltin toʻplam, baholash skripti, FastAPI, hujjatlar, demo | Baholash hisoboti |
| **C2 — 3D interfeys** | Three.js sahna, kitob, varaqlash, javob paneli, SSE ulash (8-boʻlim) | «Qidiruvchi kitob» ishlaydi |

C2 uchun alohida odam kerak: Three.js — interfeysdagi eng sekin ish. Jamoa 4 kishidan kam boʻlsa, **oltin toʻplam** (kritik yoʻlda) birinchi boʻlib hamma oʻrtasida taqsimlanadi, C2 esa toʻliq 3D bilan shugʻullanadi.

**Kompyuterlar:**

```mermaid
flowchart LR
    subgraph SRV["🖥️ Server kompyuter (eng kuchli GPU)"]
        OL["Ollama<br/>:11434"]
        QD["Qdrant<br/>:6333"]
        JOB["Indekslash ishi"]
    end
    A1["💻 A yoʻnalishi"] -- "LAN" --> SRV
    B1["💻 B yoʻnalishi"] -- "LAN" --> SRV
    C1["💻 C yoʻnalishi"] -- "LAN" --> SRV
```

* `.env` da `OLLAMA_URL=http://<server-IP>:11434`, `QDRANT_URL=http://<server-IP>:6333`.
* Kerak boʻlsa, tayyor indeks **Qdrant snapshot** sifatida boshqa kompyuterga koʻchiriladi — qayta embedding qilish shart emas: `python -m modda snapshot-export` → `snapshot-import`. GPU’li Windows kompyuter uchun hammasini bitta skript qiladi: [SETUP-WINDOWS.md](SETUP-WINDOWS.md).

---

## 5. Kunma-kun reja

Har kunning **birinchi soati** — eng uzoq davom etadigan ishlarni ishga tushirish. **Oxirgi soati** — natijani tekshirish va tungi fon ishini qoʻyish.

### 1-kun — Uzoq ishlarni ishga tushirish va asos

| Vaqt | A — Maʼlumot | B — Qidiruv va AI | C1 — Sifat |
|---|---|---|---|
| **0-soat** (hamma) | Server kompyuterda: `docker run qdrant`, `ollama pull bge-m3 qwen3:8b gemma4:e4b`, HF korpusini yuklashni boshlash | Reranker va Llama-3.1-8B-Uz GGUF ni yuklashni boshlash | Repozitoriy, `pyproject.toml`, papka tuzilmasi, `.env.example` |
| 1–4-soat | HF → PostgreSQL konvertori; normalizatsiya (`prototypes.py` dan); modda chunker + uzun moddalar boʻlinishi | Modellarni solishtirish skripti (3 LLM × 20 savol) → **fonda ishga tushirish** | **Oltin toʻplam:** savollarni yozish boshlanadi (6 toifa); brauzerda 10 ta Lex.uz sahifasini `tests/fixtures/` ga saqlash |
| 4–5-soat | **Tezlikni oʻlchash:** 1 000 boʻlak embedding → toʻliq korpus vaqtini hisoblash | Qdrant kolleksiya sxemasi: `dense` + `sparse`, payload indekslari | Oltin toʻplam davom etadi |
| 5–8-soat | **MVP qismini indekslash** (Konstitutsiya + asosiy kodekslar) | Birinchi oddiy RAG (faqat dense + LLM) MVP qismi ustida | Oltin toʻplam ≥ 30 savol |
| **Kun oxiri** | **Toʻliq korpusni indekslash — tunga** (davom etadigan rejimda) | Modellar solishtirish natijasi → **LLM tanlandi** | — |

**C2 — 3D interfeys, 1-kun (sinov):** `npm create vite` → `web/`; Three.js sahna, kamera, iliq yorugʻlik; kod bilan yasalgan kitob; muqova ochilishi; bitta varaqning egilishi (shader); jamoa noutbukida kadr/s oʻlchash. **Kun oxirida qaror:** ≥ 45 kadr/s boʻlsa — reja boʻyicha; boʻlmasa, varaq egilishi oddiy aylanishga almashtiriladi.

**1-kun tayyorlik mezoni:** MVP qismi boʻyicha birinchi savolga javob keladi; LLM tanlangan; oltin toʻplam ≥ 30; toʻliq indekslash tunda ishlayapti.

### 2-kun — Toʻliq qidiruv

| A — Maʼlumot | B — Qidiruv va AI | C1 — Sifat |
|---|---|---|
| Ertalab: tungi indekslash tugaganini tekshirish (boʻlaklar soni = kutilgan) | BM25 sparse + Qdrant prefetch + **RRF** | Oltin toʻplam → **60 savol** (15 tasi javobi yoʻq) |
| RSS oʻquvchi (`feedparser`), yangi ID lar navbati | **Reranker** (CrossEncoder, top-20 → top-5) | `scripts/run_eval.py`: Recall@5, MRR, yolgʻon javob ulushi |
| **Lex.uz HTML parseri** — `tests/fixtures/` dagi 10 sahifa boʻyicha testlar bilan | Savol marshrutizatori (aniq havola, kirill → lotin) | FastAPI skeleti: `/ask`, `/health`, `/docs/{id}` |

**C2 — 2-kun:** varaqlarning tez aylanishi (riffle); sahifa chetidan chiqadigan 5 ta xatchoʻp; kerakli sahifaga ochilish; GSAP bilan holatlar mashinasi — hammasi `mock.js` dagi **namuna hodisalar oqimi** bilan; `CanvasTexture` da modda matni (oʻ, gʻ, ʼ tekshiruvi).

**2-kun tayyorlik mezoni (Demo 1):** CLI’da gibrid qidiruv + reranker bilan toʻliq korpus boʻyicha javob; baholash skripti birinchi Recall@5 ni chiqaradi.

### 3-kun — «Bilmayman» va interfeys

| A — Maʼlumot | B — Qidiruv va AI | C1 — Sifat |
|---|---|---|
| RSS dagi yangi hujjatlarni parse qilib indekslash (delta) | JSON strukturali chiqish (`pydantic` sxema); **`POST /ask/stream` SSE hodisalari — 12.4 dagi nomlar bilan** | τ kalibrlash uchun oltin toʻplam natijalari |
| `last_checked_at`, RSS keshi → javobdagi yangilik belgisi | **Iqtibos tekshiruvchi** + Manba blokini koddan yasash | Baholash skriptini toʻliq korpusda ishga tushirish |
| APScheduler: RSS har soatda | **τ ni kalibrlash** oltin toʻplamda | Demo ssenariysi savollarini tanlash |

**C2 — 3-kun:** HTML javob paneli va toʻliq modda paneli; `api.js` — SSE oqimini kitob bosqichlariga ulash, `/ask` zaxirasi; holatlar: kutish, qidiruv, javob, eskirgan manba, «Bilmayman», xato.

**3-kun tayyorlik mezoni (Demo 2):** brauzerda savol → tekshirilgan javob + manba; javobi yoʻq savollarga «Bilmayman».

### 4-kun — Integratsiya va sifat

| A — Maʼlumot | B — Qidiruv va AI | C1 — Sifat |
|---|---|---|
| Xatoliklarni tuzatish; indeks yaxlitligi testlari | **Sozlash:** top-k, τ, prompt; kechikishni kamaytirish (kesh, kichikroq reranker oynasi) | Baholash hisobotining birinchi versiyasi |
| Snapshot sanasi va Lex.uz havolalarini tekshirish (20 ta tasodifiy) | Prompt-injection va chalgʻituvchi savollar sinovi | Demo ssenariysini haqiqiy tizimda sinash |
| — | Toʻliq baholash: Recall@5, yolgʻon javob, P50/P95 | Kod muzlatilishidan oldin barcha P1 vazifalar |

**C2 — 4-kun:** unumdorlik (kadr/s, `devicePixelRatio`, render toʻxtatish); telefon koʻrinishi; zaxira rejim (WebGL yoʻq / `prefers-reduced-motion`); klaviatura va «Oʻtkazib yuborish»; vaqt qolsa — P2 effektlar.

**4-kun tayyorlik mezoni:** barcha P0 va P1 bajarilgan; baholash hisobotining birinchi versiyasi.

### 5-kun — Muzlatish, hujjatlar, demo

| Vaqt | Hamma |
|---|---|
| Tushgacha | **Yangi funksiya yoʻq** — faqat xatoliklar. Yakuniy baholash; natijalar jadvali |
| Tushdan keyin | README (oʻrnatish, ishga tushirish), I_EXPLAIN yangilanishi, demo ssenariysi (6 ta savol: aniq modda, mavzuviy, kirill, yangi hujjat, javobi yoʻq, chalgʻituvchi) |
| Kechqurun | Demo mashqi; zaxira: indeks snapshot’i va ekran yozuvi (internet yoki kompyuter ishlamay qolsa) |

---

## 6. Vaqt jadvali

```mermaid
gantt
    title 5 kunlik reja — eng sekin ishlar birinchi
    dateFormat YYYY-MM-DD HH:mm
    axisFormat %d.%m %H:%M

    section Fon ishlari (kompyuter)
    Modellar va korpusni yuklab olish        :crit, dl, 2026-11-04 09:00, 4h
    MVP qismini indekslash                   :crit, mvp, after dl, 3h
    Modellarni solishtirish                  :bake, after dl, 2h
    Toʻliq korpus indekslash (tun)           :crit, full, 2026-11-04 19:00, 10h

    section A. Maʼlumot
    HF → PostgreSQL, normalizatsiya, chunker :a1, 2026-11-04 10:00, 5h
    RSS + Lex.uz parser                      :a2, 2026-11-05 09:00, 9h
    Delta indekslash, yangilik belgisi       :a3, 2026-11-06 09:00, 9h
    Xatolar, tekshiruvlar                    :a4, 2026-11-07 09:00, 9h

    section B. Qidiruv va AI
    Kolleksiya sxemasi, oddiy RAG            :b1, 2026-11-04 10:00, 8h
    BM25 + RRF, reranker, marshrut           :crit, b2, 2026-11-05 09:00, 9h
    JSON, tekshiruvchi, τ                    :crit, b3, 2026-11-06 09:00, 9h
    Sozlash, injection testlari              :b4, 2026-11-07 09:00, 9h

    section C1. Sifat
    Oltin toʻplam (60 savol)                 :crit, c1, 2026-11-04 10:00, 32h
    Baholash skripti, FastAPI                :c2, 2026-11-05 13:00, 5h

    section C2. 3D interfeys
    Three.js sinovi, kitob, varaq egilishi   :crit, d1, 2026-11-04 10:00, 8h
    Varaqlash, xatchoʻplar, sahifa matni     :d2, 2026-11-05 09:00, 9h
    Javob paneli, SSE ulash                  :crit, d3, 2026-11-06 09:00, 9h
    Unumdorlik, telefon, zaxira rejim        :d4, 2026-11-07 09:00, 9h

    section 5-kun
    Muzlatish, baholash, hujjatlar, demo     :crit, f1, 2026-11-08 09:00, 10h
```

*Sanalar 4-noyabrdan boshlanishni nazarda tutadi; boshqa kundan boshlasangiz, faqat sanalarni suring — tartib oʻzgarmaydi. Qizil boʻlaklar — kritik yoʻl.*

---

## 7. Orqada qolsak: kesish rejasi

Har kun oxirida tayyorlik mezoni bajarilmagan boʻlsa, quyidagilar **shu tartibda** kesiladi (avval eng oxirgisi):

| Tartib | Nima kesiladi | Oʻrniga | Taʼsir |
|---|---|---|---|
| 1 | Lex.uz HTML parseri va delta indekslash | RSS’dagi yangi hujjatlar faqat **roʻyxat** sifatida: «Lex.uz’da yangi: …» ogohlantirishi | Talab №6 belgi orqali saqlanadi |
| 2 | Iqtibos tekshiruvchining oʻxshashlik qismi | Faqat `chunk_ids` va raqamlar tekshiruvi | Himoya biroz zaiflashadi, τ saqlanadi |
| 3 | Savol marshrutizatori | Gibrid qidiruv (BM25 raqamlarni baribir topadi) | «MK 131-modda» savollari biroz sekinroq |
| 4 | Toʻliq korpus | Faqat MVP qismi (Konstitutsiya + asosiy kodekslar) | Qamrov kichrayadi, sifat saqlanadi |
| 5 | 3D effektlar (8.7 tartibida: P2 → xatchoʻplar → sahifa matni → varaqlash) | Kitob faqat ochiladi va ochiq turadi | Asosiy gʻoya soddalashadi, javob toʻliq saqlanadi |
| — | **Hech qachon kesilmaydi** | τ chegarasi, koddan yasalgan Manba bloki, «Bilmayman», «yuridik maslahat emas» ogohlantirishi | — |

---

## 8. Interfeys: Three.js va «qidiruvchi kitob»

> **Qaror:** sayt **Three.js** bilan noldan quriladi. Oldingi `frontend/` prototipidan faqat **API shartnomasi** va namuna maʼlumotlar (`mock-data.js`) olinadi; qolgani yangi.
>
> **Asosiy gʻoya (jamoadan):** foydalanuvchi savol yuborganda **3D kitob ochiladi, varaqlari tez aylanib qidiradi va kerakli sahifada toʻxtab, oʻsha moddani ochadi.**

### 8.1. Dribbble’dan tanlangan namunalar

Dribbble’da «3d book», «page flip», «threejs website», «legal ai», «ai search interface» boʻyicha qidirildi (4-noyabr 2026). Bitta tayyor dizayn bizning gʻoyani toʻliq bermaydi, shuning uchun har biridan **bitta narsa** olinadi:

| Namuna | Muallif | Undan nima olamiz |
|---|---|---|
| [Lexora — Legal AI SaaS Website Animation](https://dribbble.com/shots/27722017-Lexora-Landing-Page-Legal-AI-SaaS-Website-Animation) | Ilias Miah | **Asosiy yoʻnalish.** Qorongʻi, jiddiy huquqiy uslub; «tekshirib boʻladigan javob» gʻoyasi; *Reja → Javob → Manbalar* ketma-ketligi — bizning *Qidiruv → Javob → Tekshiruv* bosqichlarimizga mos |
| [3D Bookshelf Design](https://dribbble.com/shots/27310637-3D-Bookshelf-Design) | Firstborn | **Kitob sahnasi:** yumshoq kino yorugʻligi, haqiqiy material (charm, qogʻoz), yashil-kulrang tus |
| [3D Book Animation](https://dribbble.com/shots/27158802-3D-Book-Animation) | DeafBuild | Kitob ochilishi va muqova harakati |
| [AI Search 2026](https://dribbble.com/shots/27588775-AI-Search-2026) | Matthieu Martigny | **Savol maydoni:** qorongʻi «tabletka» shaklidagi maydon, ostida yumshoq nur |
| [Legal AI Chat Interface](https://dribbble.com/shots/26274650-Legal-AI-Chat-Interface) | Never Before Seen | Javob matni va manba kartalarining joylashuvi |

Bular — ilhom manbasi, nusxa emas: logotip, matn va rasmlar ishlatilmaydi.

**Natija — «Tungi kutubxona» yoʻnalishi:** qorongʻi sahna, stol chiroqidek iliq yorugʻlik ostida toʻq koʻk, oltin naqshli muqovali kitob; muqova markazida Oʻzbekiston gerbi. Yagona yorqin rang — yashil, u faqat **manba bilan tasdiqlangan** narsani bildiradi.

### 8.2. Kitob qanday qidiradi (asosiy ssenariy)

Animatsiya **haqiqiy** backend bosqichlariga bogʻlanadi — kitob «oʻynab» turmaydi, tizim nima qilayotganini koʻrsatadi. Buning uchun FastAPI’ga oqimli uch qoʻshiladi: `POST /ask/stream` (Server-Sent Events).

```mermaid
sequenceDiagram
    participant U as Foydalanuvchi
    participant K as 3D kitob
    participant API as FastAPI /ask/stream
    U->>K: Savol yuboradi
    K->>K: Kamera yaqinlashadi, muqova ochiladi
    K->>API: POST {question}
    API-->>K: stage: retrieving
    K->>K: Varaqlar tez aylanadi
    API-->>K: candidates: top-5 modda nomi
    K->>K: Sahifalar chetidan 5 ta xatchoʻp chiqadi
    API-->>K: reranked: eng yaxshisi
    K->>K: Kuchsizlari soʻnadi, eng yaxshisi yonadi
    API-->>K: answer: javob + manbalar
    K->>K: Shu sahifaga varaqlab ochiladi, iqtibos yashil
    K->>U: Yonidan javob paneli chiqadi
```

| № | Kitob holati | Backend hodisasi | Davomiyligi |
|---|---|---|---|
| 0 | **Kutish:** yopiq kitob stolda, sekin «nafas oladi», havoda chang zarralari | — | doimiy |
| 1 | **Ochilish:** kamera yaqinlashadi, muqova ilmoq atrofida aylanib ochiladi | soʻrov yuborildi | 0,8 s |
| 2 | **Qidiruv:** varaqlar tez aylanadi (riffle) | `stage: retrieving` | javob kelguncha, kamida 1,2 s |
| 3 | **Nomzodlar:** sahifalar chetidan **5 ta xatchoʻp** chiqadi, har birida haqiqiy modda nomi («MK 131-modda») | `candidates` | 0,6 s |
| 4 | **Tanlash:** kuchsiz xatchoʻplar soʻnadi, eng yaxshisi yashil yonadi | `reranked` | 0,5 s |
| 5 | **Ochilish:** kitob oʻsha sahifaga varaqlab boradi va toʻxtaydi; sahifada moddaning **haqiqiy matni**, iqtibos yashil belgilangan | `answer` | 1,0 s |
| 6 | **Javob:** kamera biroz chapga suriladi, oʻngdan javob paneli chiqadi (gaplar, manba raqamlari, «Toʻliq moddani koʻrish») | — | 0,5 s |
| 6a | **Bilmayman:** varaqlar oxirigacha aylanadi, xatchoʻplar tushib ketadi, kitob sekin yopiladi | `answer.unknown = true` | 1,0 s |
| 6b | **Xato:** kitob yopiladi, «Qayta urinish» tugmasi | tarmoq / HTTP xato | 0,6 s |

**Qoidalar:**

* Animatsiya javobni **kechiktirmaydi**: backend tez boʻlsa, 2-bosqich eng kami bilan tugaydi; sekin boʻlsa, varaqlash davom etadi. Jami qoʻshimcha vaqt ≤ 2,5 s.
* Xatchoʻplar va sahifa matni — **faqat haqiqiy** maʼlumot (`candidates`, `sources`). Toʻqima nomlar koʻrsatilmaydi.
* Javob matni, manbalar va tugmalar — oddiy **HTML** (3D ichida emas): oʻqiladi, nusxalanadi, ekran oʻquvchi va klaviatura bilan ishlaydi.
* Foydalanuvchi animatsiyani «Oʻtkazib yuborish» tugmasi yoki Esc bilan toʻxtatishi mumkin.

### 8.3. Texnik yechim

| Qism | Tanlov | Izoh |
|---|---|---|
| 3D | **Three.js** (aniq versiya `package.json` da qotiriladi) | WebGL, kutubxonaning oʻzi yetarli |
| Animatsiya vaqt chizigʻi | **GSAP** | Bosqichlarni ketma-ket va toʻxtatiladigan qilish uchun |
| Yigʻish | **Vite** (oddiy JS, freymvorksiz) | Tez ishga tushadi, oʻrganish oson |
| Kitob modeli | **Kod bilan yasaladi** (muqovalar — `BoxGeometry`, sahifalar — koʻp boʻlakli `PlaneGeometry`) | Blender va GLB fayl kerak emas; v1.1 da GLB model qoʻyish mumkin |
| Varaq egilishi | Vertex shader’da sahifani umurtqa atrofida egish (`curl`) | Bitta sahifa geometriyasi qayta ishlatiladi |
| Sahifadagi matn | `CanvasTexture`: modda matni canvas’ga Literata shriftida chiziladi | Shrift **yuklangandan keyin** chiziladi — `oʻ`, `gʻ`, `ʼ` toʻgʻri chiqishi tekshiriladi |
| Yorugʻlik | Bitta iliq `SpotLight` + yumshoq atrof yorugʻligi, soya | Firstborn namunasidagi kayfiyat |
| Effektlar (P2) | Yengil bloom, chang zarralari (`Points`) | Faqat kuchli qurilmada |
| API | `POST /ask/stream` (SSE) + zaxira `POST /ask` | Oqim boʻlmasa, 2–4-bosqichlar soddalashadi |

**Unumdorlik chegaralari:** oʻrtacha noutbukda 60 kadr/s, telefonda ≥ 30; `devicePixelRatio` ≤ 1,5; JS ≤ 300 KB (gzip); sahifa koʻrinmasa render toʻxtaydi.

**Zaxira rejim (doim ishlaydi):** WebGL yoʻq, `prefers-reduced-motion` yoqilgan yoki qurilma kuchsiz boʻlsa — 3D oʻrniga kitobning **statik rasmi** va oddiy bosqichlar roʻyxati; javob paneli aynan oʻsha.

**Papka tuzilmasi:**

```
web/
├── index.html
├── src/
│   ├── main.js            holatlar mashinasi (kutish → qidiruv → javob)
│   ├── api.js             SSE oqimi, /ask zaxirasi, namuna rejimi
│   ├── mock.js            namuna hodisalar oqimi (backend boʻlmasa)
│   ├── scene/
│   │   ├── stage.js       renderer, kamera, yorugʻlik
│   │   ├── book.js        muqova, sahifalar toʻplami, xatchoʻplar
│   │   ├── pageCurl.js    varaq egilishi (shader)
│   │   └── pageText.js    modda matnini CanvasTexture’ga chizish
│   └── ui/
│       ├── answer.js      javob paneli, manba raqamlari
│       └── drawer.js      toʻliq modda paneli
└── styles.css
```

### 8.4. SSE hodisalari (B yoʻnalishi qoʻshadi)

```
event: stage       data: {"name": "retrieving"}
event: candidates  data: [{"chunk_id": "...", "title": "Mehnat kodeksi", "article_no": "131", "score": 0.82}, ...]
event: reranked    data: {"order": ["chunk_id_1", "chunk_id_2", ...]}
event: answer      data: { ...oldingi /ask javobi bilan bir xil: unknown, checked_at, answer[], sources{} }
```

Bu B yoʻnalishi uchun kichik ish: mavjud quvurga 3 ta `yield` qoʻshiladi (qidiruvdan keyin, reranker’dan keyin, tekshiruvdan keyin).

### 8.5. Ranglar va shriftlar

| Nom | Qiymat | Vazifasi |
|---|---|---|
| Sahna | `#0B0F0D` | Fon |
| Sirt | `#141A17` (shaffof, blur bilan) | Javob paneli, savol maydoni |
| Matn | `#E6ECE8` | Asosiy matn |
| Kul matn | `#9AABA3` | Rekvizitlar |
| **Yashil** | `#6FD3A1` | Tasdiqlangan, faol xatchoʻp, asosiy tugma |
| Muqova | `#1B2A48` → `#0F1A30` (toʻq koʻk mato) | Kitob muqovasi; oltin hoshiya, «MODDA» yozuvi, markazda **Oʻzbekiston Respublikasi Davlat gerbi** (`web/public/gerb.png`) |
| Oltin | `#E0BD63` | Muqovadagi naqsh va yozuvlar |
| Qogʻoz | `#F3EFE4` | Sahifalar |
| Chiroq | `#FFD9A0` | Iliq yorugʻlik |
| Ogohlantirish | `#F0B45A` | «Oʻzgargan boʻlishi mumkin» |

Shriftlar: interfeys — **Onest**, savol, javob va sahifadagi modda matni — **Literata**.

### 8.6. Holatlar

| Holat | Nima koʻrinadi |
|---|---|
| Kutish | Yopiq kitob, sarlavha «Qonunchilikdan aniq javob — har bir gapning manbasi bilan», savol maydoni, 3 ta namunaviy savol |
| Qidiruv | 8.2 dagi 1–5-bosqichlar; pastda matnli bosqich: «Moddalar qidirilmoqda» → «Javob yozilmoqda» → «Iqtiboslar tekshirilmoqda» |
| Javob | Ochiq kitob + javob paneli; gapni bosganda kitob oʻsha manba sahifasiga oʻtadi |
| Eskirgan manba | Panelda va xatchoʻpda ogohlantirish rangi |
| Bilmayman | Yopilgan kitob + «Bu savolga Lex.uz maʼlumotlari asosida ishonchli javob topilmadi» + maslahat + Lex.uz qidiruviga havola |
| Xato | «Javob olishning imkoni boʻlmadi» + «Qayta urinish» |

### 8.7. Ustuvorlik (kesish tartibi bilan)

| Daraja | Nima |
|---|---|
| **P0** | HTML javob paneli toʻliq ishlaydi; 3D kitob: kutish, ochilish, javobda ochiq turish; zaxira rejim |
| **P1** | Varaqlash, haqiqiy nomzod xatchoʻplari, kerakli sahifaga ochilish, sahifadagi modda matni, SSE |
| **P2** | Bloom, chang zarralari, gapni bosganda sahifa almashishi, ovoz |

Vaqt yetmasa, **P2 → xatchoʻplar → sahifa matni → varaqlash** tartibida kesiladi. Javob paneli va zaxira rejim **hech qachon** kesilmaydi.

### 8.8. Tamoyillar

* Harakat tizim ishini tushuntiradi — bezak uchun emas.
* Bitta yorqin rang — yashil, faqat tasdiqlangan narsa uchun.
* «Bilmayman» xato emas: qizil emas, aniq keyingi qadam bilan.
* Klaviatura bilan toʻliq ishlaydi; fokus koʻrinadi; `prefers-reduced-motion` hurmat qilinadi.
* Telefonda: kitob yuqorida kichikroq, javob paneli pastdan chiqadi; 390 px kenglikda gorizontal aylantirish yoʻq.
* Manba bloki matnini model emas, **kod** metadata’dan yasaydi.

---

## 9. 5 kunlik texnik soddalashtirishlar

| v2 dagi reja | 5 kunda | Qachon qaytariladi |
|---|---|---|
| SQLite + Qdrant + versiyalash jadvallari | PostgreSQL: `articles`, `chunks`, `meta` (versiyalarsiz); testlar SQLite’da ham ishlaydi | v1.1 |
| Uch qatlamli yangilanish (A, B, C) | A (RSS har soatda) + C (javobdagi belgi) | B — v1.1 |
| Oʻzgartirish havolalari (`CROSS_REF`) | Yoʻq; RSS’dagi «oʻzgartirish kiritish» hujjatlari faqat ogohlantirish uchun | v1.1 |
| Lex.uz’da jonli qidiruv | Yoʻq; «Bilmayman» + Lex.uz qidiruv havolasi | v1.1 |
| docker-compose (API ham) | Qdrant + Ollama Docker’da, API — `uvicorn` | 5-kun, vaqt qolsa |
| CI (GitHub Actions) | `pytest` qoʻlda, har kuni kechqurun | v1.1 |
| Oltin toʻplam 150–200 | 60 | v1.1 |
| Telegram bot | Yoʻq | v1.1 |

---

## 10. Har kungi tartib va tayyorlik mezonlari

**Har kuni:**

* **09:00 — 15 daqiqalik qisqa yigʻilish:** kecha nima tugadi, bugun nima, nima toʻsib turibdi. Birinchi savol: **tungi fon ishi tugadimi?**
* **13:00 — tekshiruv nuqtasi:** kritik yoʻldagi ish rejadami? Orqada boʻlsa — 7-boʻlimdagi kesish rejasi.
* **18:00 — kun yakuni:** tayyorlik mezoni tekshiriladi; `pytest`; `run_eval.py`; **tungi fon ishi ishga tushiriladi**.

| Kun | Tayyorlik mezoni |
|---|---|
| 1 | MVP qismi boʻyicha birinchi javob; LLM tanlangan; oltin toʻplam ≥ 30; toʻliq indekslash tunda ishlayapti |
| 2 | Toʻliq korpus indekslangan; gibrid + reranker; Recall@5 oʻlchangan; oltin toʻplam = 60 |
| 3 | Brauzerda savol → tekshirilgan javob + manba; «Bilmayman» ishlaydi; τ kalibrlangan |
| 4 | Barcha P0 + P1; yolgʻon javob ulushi oʻlchangan; telefon ekranida ishlaydi |
| 5 | Yakuniy hisobot, README, demo mashqi, zaxira nusxa |

**MVP sifat maqsadlari (5 kun uchun):**

| Metrika | Maqsad |
|---|---|
| Recall@5 | ≥ 0,80 |
| Yolgʻon javob ulushi (javobi yoʻq 15 savol) | ≤ 1 ta savol |
| Ortiqcha «Bilmayman» | ≤ 15 % |
| P50 kechikish (server kompyuterda) | ≤ 15 s |

---

## 11. Xavflar (5 kun uchun)

| Xavf | Belgisi | Chora |
|---|---|---|
| Internet sekin — modellar 1-kun tushgacha yuklanmaydi | 0-soatdan keyin 2 soatda yuklash < 50 % | Eng kichik modellar bilan boshlash (`qwen3:4b`, faqat `bge-m3`); qolganini tunda |
| ⚠️ **Roʻy berdi:** GPU yoʻq — bge-m3 0,2–0,5 boʻlak/s, butun korpus ≈ 233 soat | 1-kun `bench-embed` | Ikki qatlamli indeks: BM25 hammaga, dense — kodeks, Konstitutsiya, qonunlarga (2-kun boʻlimi). Toʻliq dense — jamoadoshning GPU kompyuterida, snapshot bilan koʻchiriladi ([SETUP-WINDOWS.md](SETUP-WINDOWS.md)) |
| Oʻzbek tilida LLM javoblari sifatsiz | Modellar solishtirishida | Ekstraktiv uslubni kuchaytirish (iqtiboslardan javob); oʻzbekchaga moslangan modelni tanlash |
| Oltin toʻplam kechikadi | 2-kun tushda < 40 savol | Savollarni HF moddalaridan teskari yozish; ikki kishiga boʻlish |
| Lex.uz parseri murakkab chiqadi | 2-kun oxirida testlar oʻtmayapti | Kesish rejasi, 1-band |
| Integratsiya oxirgi kunga qolib ketadi | 3-kun oxirida brauzerda javob yoʻq | 4-kun ertalab yangi funksiyalar toʻxtatiladi, faqat integratsiya |
| Three.js kitobi kuchsiz kompyuterda sekin ishlaydi | 1-kun sinovida < 45 kadr/s | Varaq egilishini oddiy aylanishga almashtirish; `devicePixelRatio` ni 1 ga tushirish; zaxira rejim |
| Sahifadagi matnda oʻ, gʻ, ʼ notoʻgʻri chiqadi | 2-kun `CanvasTexture` sinovida | Shriftni `document.fonts.load()` bilan oldindan yuklash; kerak boʻlsa matnni HTML qatlamda koʻrsatish |
| Animatsiya javobni kechiktiradi | Qoʻshimcha vaqt > 2,5 s | Bosqichlar eng kam davomiylikka qisqartiriladi; «Oʻtkazib yuborish» |
| Demo kuni nimadir ishlamaydi | — | Indeks snapshot’i, oldindan yozilgan demo videosi, oflayn ishlaydigan server kompyuter |

---

## 12. Yakuniy interfeys: Legal Intelligence Graph

> **Holat:** konsepsiya qabul qilindi, **interaktiv demo tayyor** — `demo/graph/index.html` (brauzerda toʻgʻridan-toʻgʻri ochiladi). Asosiy ish yoʻl xaritasining **oxirida** qilinadi: 1–5-kunlarda 3D kitob ishlatiladi, chunki u yetarli. Bitta narsa hozirdan qilinadi: 3-kunda backend hodisalari 12.4 dagi shartnoma boʻyicha yoziladi, keyin yangi interfeysga oʻtish faqat frontend ishi boʻladi.

### 12.1. Gʻoya

Modda oddiy chatbot va aylanib turgan yuklanish belgisi oʻrniga savol yuborilganda **jonli huquqiy bilimlar grafiga** aylanadi. Foydalanuvchi tizim savolni qanday tahlil qilgani, Lex.uz bazasida nimani topgani, qaysi moddalarni tanlagani va javob qaysi manbalarga bogʻlanganini koʻradi.

**Asosiy tamoyil:** AI’ning *tadqiqot jarayoni* koʻrsatiladi, uning *ichki fikrlashi* emas. Grafdagi har bir tugun — backend’dan kelgan haqiqiy hodisa yoki haqiqiy topilgan modda.

Qoʻshimcha tamoyil: graf — Moddaning **oʻziga xos belgisi**, lekin odamlar saytga **manbali javob** uchun keladi. Tadqiqot tugagach, javob birinchi oʻringa chiqadi, graf ixcham kartaga aylanadi.

### 12.2. Toʻrtta holat

| Holat | Nima koʻrinadi |
|---|---|
| **01 — Kutish** | Tinch, qorongʻi «huquqiy olam»: sekin harakatlanuvchi 3D tarmoq. Sarlavha: «Qonunchilikni anglashning yangi usuli.» Savol maydoni pastda, namunaviy mavzular: Mehnat taʼtili, Soliq majburiyatlari, Taʼlim huquqlari |
| **02 — Tadqiqot** | Uch qism: chapda **bosqichlar** (kutilmoqda / bajarilmoqda / bajarildi / xato, haqiqiy vaqt bilan), markazda **3D graf** (60–70 %), oʻngda **topilgan hujjatlar** — topilishi bilan paydo boʻladi |
| **03 — Javob** | Chapda 65 %: savol → qisqa javob → batafsil → shartlar va istisnolar → huquqiy asos → ogohlantirish. Oʻngda 35 %: manba kartalari va ixcham graf; «Tadqiqot grafi ↗» uni kattalashtiradi |
| **04 — Manbani oʻrganish** | Tugun yoki kartani bosganda: tugun yonadi, kamera unga yumshoq yaqinlashadi, modda matni ochiladi. «Grafda koʻrish ↗» — javob manbasini grafda koʻrsatadi |

### 12.3. Tadqiqot bosqichlari va bizning quvurdagi oʻrni

| № | Bosqich | Modda’dagi haqiqiy qadam | Grafda |
|---|---|---|---|
| 01 | Savol tahlili | normalizatsiya, kirill → lotin, marshrutizator, qidiruv tushunchalari | markazda savol tuguni, atrofida tushuncha tugunlari |
| 02 | Embedding | `bge-m3`, 1024 oʻlchamli vektor | vektor tuguni, indeks tomon oqayotgan zarralar |
| 03 | Lex.uz qidiruvi | Qdrant gibrid qidiruv (dense + BM25, RRF) | indeks tuguni, hujjatlar boʻyicha guruhlangan **haqiqiy** nomzod moddalar |
| 04 | Saralash | reranker (`bge-reranker-v2-m3`) va τ chegarasi | tanlanganlar yashil yonadi, qolganlari kulrang soʻnadi |
| 05 | Kontekst | tanlangan boʻlaklar + metadata | tanlangan moddalar kontekst tuguniga birlashadi |
| 06 | Javob | LLM (`qwen3:8b` yoki tanlangan model) | javob tuguni yashil yonadi, undan manbalarga qaytuvchi yoʻl chiziladi |
| 07 | **Tekshiruv** *(bizning qoʻshimcha)* | iqtibos tekshiruvchi (3-kun) | tasdiqlangan manba yoʻllari yashil, tasdiqlanmagani amber |

**Qoida:** faqat backend haqiqatan bajargan bosqich koʻrsatiladi. Masalan, reranker oʻchiq boʻlsa, 04-bosqich «oʻtkazildi» deb koʻrsatiladi, «bajarildi» emas.

### 12.4. Hodisalar shartnomasi (SSE)

Har bir hodisada: `type`, `request_id`, `ts` (ISO vaqt), `data`. Frontend bosqich holatini **oʻzi taxmin qilmaydi** — faqat shu hodisalardan oladi.

| Hodisa | `data` | Grafda |
|---|---|---|
| `query.received` | `{question}` | savol tuguni |
| `query.analyzed` | `{concepts: [...], route}` | tushuncha tugunlari |
| `embedding.completed` | `{model, dim, ms}` | vektor animatsiyasi |
| `retrieval.started` | `{index, mode}` | indeks bilan aloqa yonadi |
| `retrieval.completed` | `{documents_found, chunks_retrieved, candidates: [{chunk_id, doc_title, doc_type, article_no, article_title, rank}]}` | hujjat va modda tugunlari |
| `ranking.completed` | `{reranker: true/false, selected: [chunk_id], rejected: [chunk_id], tau, top_score}` | tanlash effekti |
| `context.completed` | `{chunk_ids}` | kontekstga birlashish |
| `generation.started` | `{model}` | javob tuguni faollashadi |
| `verification.completed` | `{verified: [chunk_id], failed: [chunk_id]}` | yashil / amber yoʻllar |
| `answer.completed` | hozirgi `/ask` javobi (`unknown, checked_at, answer[], sources{}`) | graf joylashadi, javob chiqadi |
| `stage.failed` | `{stage, message}` | bosqich «xato», amber |

8.4 dagi hozirgi qisqa hodisalar (`stage`, `candidates`, `reranked`, `answer`) shu roʻyxatdan kelib chiqadi: 3D kitobning `api.js` i yangi nomlarni eski koʻrinishga oʻgiradi, shuning uchun backend bir marta yoziladi.

**Rostgoʻylik qoidalari:** soxta foiz-progress yoʻq; soxta «98 % ishonch» yoʻq (faqat tartib va tanlangan/chiqarilgan holati); faqat haqiqiy topilgan hujjatlar; bosqichlar haqiqiy oʻtgan vaqt bilan.

### 12.5. Grafning vizual tili

| Element | Koʻrinishi | Maʼnosi |
|---|---|---|
| Savol tuguni | katta markaziy shar | foydalanuvchi savoli |
| Tushuncha tugunlari | kichik oltin nuqtalar | aniqlangan qidiruv tushunchalari |
| Vektor tuguni | kichik nurli tugun, oqayotgan zarralar | semantik vektor |
| Indeks | katta setkali koʻp yoqli shakl | Lex.uz indeksi |
| Hujjat / modda tugunlari | yorliqli tugunlar, hujjat boʻyicha guruhlangan | topilgan moddalar |
| Oltin yoʻllar | harakatlanuvchi zarralar bilan | faol qidiruv va tanlash |
| Yashil yoʻllar | | javobga bogʻlangan, tasdiqlangan manbalar |
| Kulrang | soʻngan | chiqarilgan nomzodlar |
| Amber | | ogohlantirish, tasdiqlanmagan manba |

Ranglar: koʻmir-qora fon `#0E1011`, oltin `#C9A45C` (faol), zumrad `#3FBF8A` (tanlangan, bajarilgan), kulrang `#5B6166`, amber `#E0A440`. Shriftlar: Literata (sarlavha, huquqiy matn), Onest (interfeys), JetBrains Mono (hodisalar jurnali).

Harakat: zarralar yoʻl boʻylab, yumshoq yorugʻlik, sekin kamera, aloqalar ketma-ket paydo boʻladi. **Yoʻq:** portlashlar, doimiy aylanish, neon. Graf jiddiy tadqiqot asbobidek koʻrinishi kerak.

### 12.6. Texnik qaror

Konsepsiyada React + React Three Fiber + Drei + Motion + Tailwind + Zustand taklif qilingan — **frontend React’da** degan taxmin bilan. Bizning frontend — **oddiy Vite + Three.js** (React’siz). Shuning uchun:

* **Tanlov: React’siz Three.js** qoladi. Demo shuni koʻrsatdi: toʻrtta holat ham, graf ham, hodisa oqimi ham ≈ 700 qatorda, bitta kutubxona (`three` + `OrbitControls`) bilan ishlaydi.
* React’ga oʻtish 5 kunlik rejada qayta yozish demakdir va qoʻshimcha qiymat bermaydi. Jamoa keyin React’ga oʻtmoqchi boʻlsa, R3F mos keladi — graf mantigʻi (`Node`, `Edge`, hodisalar ishlovchisi) koʻchiriladi.
* Unumdorlik: koʻrinadigan tugunlar soni cheklangan (≤ 40); `devicePixelRatio` ≤ 1,75; sahifa yashirin boʻlsa render toʻxtaydi; telefonda kamroq zarralar; `prefers-reduced-motion` da harakat oʻchadi; ishlatilmagan geometriya va materiallar yangi savoldan oldin tozalanadi.

**3D kitob bilan bogʻlash (taklif):** gerbli kitob «Lex.uz indeksi» tugunining oʻrnida turishi mumkin — kitob grafning markaziy manbasi boʻladi, brend saqlanadi.

### 12.7. Indekslash — alohida koʻrinish

Ikki ish oqimi aralashtirilmaydi:

* **A. Oflayn indekslash** (Lex.uz → boʻlaklar → embedding → indeks) — foydalanuvchiga emas, **admin sahifasiga**: indeks yangiligi, RSS holati, oxirgi sinxronlash.
* **B. Jonli savol** (savol → embedding → qidiruv → saralash → javob) — foydalanuvchi grafi aynan shu.

### 12.8. Bajarish tartibi

| № | Ish | Taxminiy vaqt |
|---|---|---|
| 1 | Backend: 12.4 dagi hodisalar (`POST /ask/stream`) | 3-kun ichida, ≈ 2 soat |
| 2 | Dizayn tizimi va bosh sahifa (01-holat) | 0,5 kun |
| 3 | Graf: haqiqiy hodisalarga ulash (02-holat) | 1 kun |
| 4 | Hujjatlar paneli, javob sahifasi, «Grafda koʻrish» (03–04-holatlar) | 0,5 kun |
| 5 | Telefon, unumdorlik, klaviatura | 0,5 kun |

Jami ≈ 2,5 kun — shuning uchun asosiy 5 kundan **keyin** (yoki 5-kun tushdan keyin, vaqt qolsa — faqat 2–3-qadamlar).


---

*Hujjat versiyasi: 3.2 (5 kunlik reja, Three.js interfeysi, yakuniy graf interfeysi) · Sana: 2026-11-04 · Asos: v2 yoʻl xaritasi · Til: oʻzbek (lotin)*
