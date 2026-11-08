# Modda — API /v1 (testchi uchun)

«RAG API — test spetsifikatsiyasi (lex.uz)» (3-noyabr 2026) boʻyicha. Kod: `src/modda/v1.py` (mantiq), `src/modda/api.py`
(FastAPI) va `src/modda/devserver.py` (FastAPI’siz zaxira server — xuddi shu yoʻllar).

## Ulanish

| | |
|---|---|
| Base URL | `http://<GPU-noutbuk-IP>:8080` (bir tarmoqda; server `start_modda.bat` yoki `scripts\day6.bat --keep-server`) |
| Kalit | `Authorization: Bearer <MODDA_API_KEY>` — `.env` da; `scripts\day6.bat` yoʻq boʻlsa yaratadi va `TESTCHI-UCHUN.md` ga yozadi |
| Kodlash | `Content-Type: application/json; charset=utf-8` — lotin, kirill, rus; `oʻ`, `gʻ`, `ʼ` saqlanadi |

| Endpoint | | Izoh |
|---|---|---|
| `POST /v1/rag/batch` | 1–10 savol | sync; 110 s dan oshsa `202 {"batch_id","status":"processing"}` |
| `GET /v1/rag/batch/{batch_id}` | natija | `processing` → `completed` / `failed`; diskda saqlanadi (`data/v1/batches/`), oʻchirilmaydi |
| `POST /v1/rag/query` | 1 savol (debug) | `{"question": "...", "language"?: "...", "options"?: {...}}` → `{"system", "result"}` |
| `GET /v1/meta` | versiyalar | model, embedding, indeks versiyasi, Lex.uz snapshot sanasi, korpus soni, cheklovlar |
| `GET /v1/health` | holat | kalitsiz ham ochiq (monitoring) |

## Qoidalar (§2, §5)

| Talab | Qanday |
|---|---|
| Autentifikatsiya | kalitsiz → 401, notoʻgʻri kalit → 403 (`health` dan tashqari) |
| Batch hajmi | 1–10; 11 ta, boʻsh `question`, takroriy `id`, 2000+ belgi → 400 (butun batch) |
| Rate limit | kalit boʻyicha 1 batch/s → `429` + `Retry-After` |
| Idempotentlik | bir xil `batch_id` + bir xil mazmun → saqlangan natija (qayta hisoblanmaydi); boshqa mazmun → `409`. Saqlangan natijada `retryable: true` xatoli savol boʻlsa — faqat oʻsha savollar qayta hisoblanadi |
| Bitta savol xatosi | batch `200`; oʻsha savol `status: "error"` + `error {code, message, retryable}`. Kodlar: `RETRIEVAL_FAILED`, `INDEX_UNAVAILABLE`, `LLM_TIMEOUT`, `LLM_ERROR`, `CONTEXT_TOO_LONG`, `INVALID_LANGUAGE` |
| Takrorlanuvchanlik | `temperature`, `seed` → Ollama; qidiruv deterministik (bir xil savol → bir xil manbalar) |
| Versiyalash | har javobda `system` obyekti |

## Javob (§4) — qoʻshimcha maydonlar

Spetsifikatsiyadagi hamma maydonlar bor. Qoʻshimchalar (testchiga foydali, majburiy emas):

- `contexts[]`: `retrieval_score` — bge-m3 kosinus oʻxshashligi; `rrf_score`, `bm25_score` — gibrid qidiruvning ikki roʻyxati;
  `header` — model koʻrgan boʻlak sarlavhasi; `exact_reference` — savolda modda raqami aniq aytilgan; `rerank_score: null`
  (reranker oʻchiq — sekin, gibrid qidiruv Recall@5 allaqachon 0,91; yoʻl xaritasi 2-kun).
- `citations[]`: `stale` — Lex.uz RSS’ida hujjat snapshot’dan keyin oʻzgargan deb belgilangan; `part` — kodeksning boʻlim/bob/paragrafi.
- `confidence` — javob soʻzlarining manbaga mosligi (0–1, saytdagi «tarozi» bahosi); «javob yoʻq» da `null`.
- `debug`: `rewritten_query`, `retrieved_total`, `dense_top` va `gate` (τ = 0,58 darvozasi), `verification.failed` (tekshiruvchi
  olib tashlagan gaplar), `superseded_dropped` (qidiruvdan chiqarilgan eski nusxalar), `question_uz` / `answer_uz` (rus savollari).
- `timing.translate_ms` — rus savoli/javobi tarjimasi.

## Tillar

Korpus — oʻzbek lotin. Javob **har doim oʻzbek lotinida yoziladi va manba bilan tekshiriladi**, keyin:
`uz-Cyrl` — transliteratsiya (soʻzma-soʻz, maʼno oʻzgarmaydi); `ru` — rus savoli avval oʻzbekchaga tarjima qilinadi (qidiruv uchun,
`debug.question_uz`), tekshirilgan javob rus tiliga tarjima qilinadi (`debug.answer_uz` — tekshirilgan asli). `quote` har doim
Lex.uz matnidan aynan (oʻzbek lotin).

## `options.as_of_date`

Qabul qilinadi va javobda qaytariladi, lekin korpus bitta snapshot (`system.lex_snapshot_date`): tahrir sanasi boʻyicha tanlov
qilinmaydi. Buning oʻrniga bir aktning eski nusxalari (masalan, 1995 va 2022 yilgi Mehnat kodekslari) qidiruvdan chiqariladi
(`src/modda/versions.py`, `debug.superseded_dropped`), hujjatlar orasida raqam zid boʻlsa — yuqori akt qoladi.

## Spetsifikatsiyadagi «ochiq savollar»ga javob

1. **Lex.uz maʼlumoti qachon olingan, qanchalik yangilanadi?** Korpus — Lex.uz’ning Hugging Face’dagi nusxasi (24 267 hujjat,
   54 173 modda); sana — `system.lex_snapshot_date` (eng soʻnggi `version_date`). Avtomatik yangilanmaydi: Lex.uz RSS’i oʻqiladi va
   snapshot’dan keyin oʻzgargan hujjatlar `citations[].stale = true` bilan belgilanadi. Qayta indekslash — `scripts\day3.bat`.
2. **Chunking modda boʻyichami?** Ha: bitta boʻlak = bitta modda; uzun modda qismlarga boʻlinadi (bir xil `article`). Shuning uchun
   `article` maydoni aniq. Moddasiz hujjatlar (qarorlar, buyruqlar) — `article: null`, boʻlaklar uzunlik boʻyicha.
3. **Kuchini yoʻqotgan hujjatlar indeksdami?** Nusxada hamma hujjat «amalda» deb belgilangan, alohida status yoʻq. Bir aktning eski
   nusxalari nom va moddalar mosligi boʻyicha aniqlanadi va qidiruvdan chiqariladi; `GET /v1/meta` → `corpus.superseded_documents`.
   **Oʻzgartish va bekor qilish aktlari** («…ga oʻzgartish va qoʻshimchalar kiritish toʻgʻrisida») ham qidiruvdan chiqariladi —
   ularning matni yo asosiy aktga kiritilgan, yo almashtirilgan aktga tegishli; savol oʻzgartishlar haqida boʻlsa — qoladi.

## Ikki qismli savollar (`SPLIT_QUESTIONS`)

«…qancha va … necha kun?» kabi savollar butun holda va har bir qismi alohida qidiriladi (`rag.split_question`, `interleave`).
Yoqish/oʻchirishni `scripts\day6.bat` oʻzi hal qiladi: testdan oldin `scripts/retrieval_ab.py` (LLMsiz, ≈ 1 daqiqa) 100 savolda
ikki variantni solishtiradi va `.env` ga `SPLIT_QUESTIONS=on|off` yozadi (koʻp moddali savollar yaxshilansa va umumiy Hit@5
tushmasa — `on`). Natija: `data/reports/retrieval_ab.json`.

## 100 savollik test

- Test toʻplami: `data/testset/test100.csv` (spetsifikatsiya ustunlari + `language`, `key_facts`, `source`); qayta yaratish —
  `python scripts/build_testset.py`. Tarkib §6 dagidek: 35 faktik, 15 raqam, 15 koʻp modda/hujjat, 10 oʻzgargan norma, 10 rus va
  kirill, 10 javobsiz, 5 ogʻzaki; har batch’da 6–7 kategoriya.
- Ishga tushirish (GPU noutbukda): `scripts\day6.bat` — server + kalit + test + hisobot.
- Testchining oʻz kompyuterida: `python scripts/rag_api_test.py --base-url http://<IP>:8080 --api-key <KALIT> [--testset oʻz.csv] [--judge none]`
  (faqat standart kutubxona; Word hisobot uchun `python-docx`).
- Natija: `HISOBOT.html` / `.docx` / `.md` (metrikalar §6, checklist §7, kategoriyalar, xato sabablari, **100 savol va javob**
  manbalari bilan), `results.csv`, `metrics.json`, `checks.json`, `batches/b01…b10.json` (xom javoblar), `judge.jsonl`.
- Baholash usuli — hisobotning 7-boʻlimi. Answer correctness: LLM-hakam (oʻrnatilgan boʻlsa boshqa model, masalan qwen3:8b) +
  kalit faktlar; faithfulness va citation accuracy — deterministik (sonlar va soʻzlar kontekstda), hakam bahosi alohida.
