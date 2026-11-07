# 3-kun (7-noyabr) — GPU noutbukda: indeks, LLM tanlash, demo savollar

## 1. 11:16 dagi ishga tushirish — tahlil

Noutbukda **eski skript** (`setup_windows.bat`, 14 qadam) ishlagan — yangi `setup_server.bat` GitHub’ga 11:23 da chiqqan edi. Natija:

| Qadam | Holat | Izoh |
|---|---|---|
| system | ✅ | RTX 4060 Laptop 8 GB, driver 560.81, RAM 16,8 GB, disk 42 GB boʻsh, Python 3.10.9 |
| python | ✅ | `.[dev,api]` — FastAPI ham oʻrnatildi |
| ollama | ✅ | v0.40.15, `qwen3:8b` avvaldan bor |
| models | ⚠️ | bge-m3 yuklandi, lekin **GPU’da faqat 689 MB** (model ≈ 1,2 GB) — qolgani CPU’da |
| corpus, qdrant, env | ✅ | 54 173 qator (checksum), Qdrant v1.20.0, SQLite |
| ingest → chunk → numbers | ✅ | 54 173 modda → **183 170 boʻlak** → 1 540 ta 195¹ — Bobur’dagi bilan aynan bir xil |
| bench | ❌ | **2,6 boʻlak/s** — bu CPU tezligi. RTX 4060 da ≥ 25 (odatda 50–150) boʻlishi kerak |
| index | ⏸️ | sekinlik sabab ikki qatlamli indeks boshlandi: BM25 hammasi + bge-m3 faqat 39 701 ta (kodeks/qonun); ≈ 2 soat. **Bobur’dagi holat emas** (unda 183 170 tasi dense) |

**Sabab (ehtimol):** bge-m3 GPU’ga sigʻmadi — VRAM’ni boshqa narsa band qilgan (xotirada qolgan `qwen3:8b`, boshqa dastur — LM Studio, oʻyin, brauzer) yoki noutbuk batareyada ishlagan. `day3.bat` buni oʻzi tekshiradi va GPU’ni boʻshatadi.

**Yechim:** indeksni qayta yasamaymiz — Bobur’ning **snapshot**’ini yuklaymiz (≈ 1 daqiqa, Bobur’dagi bilan aynan bir xil).

## 2. Jamoadosh nima qiladi

1. Ishlab turgan oynada **Ctrl+C** (eski indekslash toʻxtaydi — zarari yoʻq, snapshot uni almashtiradi).
2. Zaryadlovchini ulang. Boshqa ogʻir dasturlarni yoping.
3. Bobur yuborgan 2 ta faylni **Downloads** papkasiga qoʻying:
   `modda-20261105-0637.snapshot` (≈ 2 GB) va `modda-20261105-0637.manifest.json.gz`
4. Loyiha papkasida terminal: `git pull`
5. **`scripts\day3.bat`** ni ikki marta bosing (Firewall uchun bir marta «Ha / Yes»). Taxminan 2–3 soat (asosan bakeoff modellarini yuklab olish, ≈ 10–15 GB).
6. Tugagach `data\reports\day3-<vaqt>.log` faylini Bobur’ga yuboring.

`day3.bat` nima qiladi:

| Qism | Nima | Vaqt |
|---|---|---|
| gpu | nvidia-smi, zaryadlovchi, VRAM’dagi dasturlar, Ollama sozlamalari; GPU’ni boʻshatib bge-m3 (boʻlak/s) va qwen3:8b (token/s) tezligi va GPU ulushi | 3–5 daq |
| setup | `setup_server.py`: Git, Node.js, sayt build, bakeoff modellari, **snapshot-import**, eval, Firewall, `start_modda.bat`, haqiqiy savol | 1–2 soat |
| bakeoff | qwen3:8b · gemma4:e4b · Llama-3.1-8B-Uz, 20 oltin savol | 20–40 daq |
| demo | 6 demo savol (aniq modda, mehnat, kirill, yangilangan hujjat, javobsiz, prompt-injection) — vaqt, javob, manba, baho | 3–5 daq |
| status | yakuniy holat | — |

Faqat bir qismini qayta ishga tushirish: `scripts\day3.bat --only gpu` (yoki `demo`, `bakeoff`). Snapshot boʻlmasa va GPU tez boʻlsa: `scripts\day3.bat --build-index`.

## 3. Shu kuni qilingan ishlar (Bobur tomoni)

* `scripts/day3.bat` + `day3.py` + `demo_questions.py` — yuqoridagi bitta-fayl hisobot.
* `setup_server.py`: modellarni sinashdan oldin GPU boʻshatiladi; bge-m3 ning necha foizi GPU’da ekani koʻrsatiladi.
* **RSS «oʻzgargan boʻlishi mumkin» belgisi:** manba hujjati Lex.uz RSS’da snapshot’dan keyin eʼlon qilingan boʻlsa (id boʻyicha yoki **nomi boʻyicha** — masalan «Mehnat kodeksiga oʻzgartish kiritish toʻgʻrisida» → Mehnat kodeksi), kitobning manba sahifasida sariq lenta: «Lex.uz’da 2026-11-03 da oʻzgargan boʻlishi mumkin — rasmiy matnni tekshiring»; «Kitobni oʻqish» oynasida havola bilan. Test: `test_stale_by_id_and_by_title`.

### 17:30 gacha qoʻshilgani

* **Tarozi hukmi javob bilan birga:** javob kelganda haykal joyida reaksiya qiladi (pallalar bahoga ogʻadi, medal va logotip chiqadi, olov kuchayadi), haykal ostida baho; kitobning javob sahifasida **oltin muhr** — bosilsa tarozi markazga keladi. Kitob — asosiy javob, tarozi — uning bahosi; ikkalasi bogʻlangan.
* **Iqtibos tekshiruvchi:** havola va raqamlardan tashqari, gapning mazmunli soʻzlaridan kamida 20 % i manbada boʻlishi kerak.
* **τ kalibrlash:** `python -m modda calibrate --write-env`; τ dan past (hech bir moddaga yaqin emas) savol — LLM’siz «Bilmayman», sababi sahifada.
* **Baholash hisoboti:** `python -m modda report` → `data/reports/BAHOLASH.md`.
* **README** (ildizda) va **I_EXPLAIN §0.1**.

## 4. Keyingi skript: `scripts\day4.bat` (day3 logini Bobur koʻrgandan keyin)

```bat
git pull
scripts\day4.bat                      :: yoki Bobur tanlagan LLM bilan:  scripts\day4.bat --llm gemma4:e4b
```

| Qism | Nima |
|---|---|
| llm | `--llm` boʻlsa `.env` dagi LLM_MODEL ni oʻzgartiradi |
| calibrate | τ → `.env` (`DENSE_TAU`) |
| eval | 45 oltin savol → `data\reports\eval.json` |
| demo | 6 demo savol yangi sozlamalar bilan |
| build | `npm run build` |
| fixture | haqiqiy javob yozuvi → `data\reports\fixture.json` (saytning «Namuna rejimi» uchun; Bobur `frontend_idea/public/demo/` ga qoʻyadi) |
| video | ekranda Chromium ochiladi, ≈ 2 daqiqa tegmang: 1920×1080 `.webm` + haqiqiy kadr/s (`data\reports\video\`) |
| report | `data\reports\BAHOLASH.md` (logga ham yoziladi) |

Bobur’ga yuboriladi: `data\reports\day4-<vaqt>.log`, `data\reports\fixture.json`, `data\reports\video\modda-demo-*.webm`. Video chiqmasa — **Win+Alt+R** (Windows’ning oʻz ekran yozuvi) bilan qoʻlda yozib oling.
