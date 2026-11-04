# 2-kun: bajarish tartibi

Hamma buyruqlar: `cd ~/Lex_Uz_AI_Agent && source .venv/bin/activate`

> **Rejadagi oʻzgarish.** `bench-embed`: bu kompyuterda bge-m3 ≈ 0,2–0,5 boʻlak/s (CPU). Butun korpus dense uchun ≈ 233 soat — 5 kunga sigʻmaydi. Shuning uchun indeks **ikki qatlamli**:
> * **BM25 — hamma 183 170 boʻlak** (Ollama kerak emas, bir necha daqiqa);
> * **bge-m3 — kodekslar, Konstitutsiya, qonunlar** (≈ 39 ming boʻlak): MVP bugun, qonunlar tunda.
> Qaror va farmonlar kalit soʻzlar boʻyicha topiladi; gibrid qidiruv ikkalasini birlashtiradi.

## 1. BM25 — butun korpus (MVP indeksi ishlayotgan paytda ham boʻladi)

```bash
python -m modda index --sparse-only
```

## 2. Modda raqamlari: 1951 → 195¹

Korpus yuqori indekslarni yoʻqotgan (MJtK’da 337 ta, JK’da 114 ta shunday modda). Avval hujjat ichidagi tartib saqlanadi, keyin raqamlar tiklanadi (10 ta Lex.uz sahifasida 4 028 moddadan 4 028 tasi toʻgʻri):

```bash
python -m modda ingest          # tartib raqami (seq) qoʻshiladi, indeksga tegmaydi, ≈ 3–5 daqiqa
python -m modda fix-numbers
```

Shundan keyin «MK 131-modda», «MJtK 195¹-modda», «МК 131-модда» kabi savollar toʻgʻridan-toʻgʻri shu moddani topadi.

## 3. Lex.uz RSS

```bash
python -m modda rss
```

## 4. API va sayt — haqiqiy javoblar

```bash
uv pip install -e ".[api]"
python -m modda serve                        # http://localhost:8080  (/health, /ask, /ask/stream)
# ikkinchi terminalda:
cd web && npm run dev                        # http://localhost:5173 — endi namuna emas, haqiqiy javob
```

Sinash: `curl -s localhost:8080/health` va
`curl -N -X POST localhost:8080/ask/stream -H 'Content-Type: application/json' -d '{"question":"MK 417-modda nima deydi?"}'`

## 5. Reranker (ixtiyoriy — CPU’da sekin)

```bash
uv pip install -e ".[rerank]"
RERANKER=on RERANK_TAU=0.3 python -m modda serve
```

`bge-reranker-v2-m3` bge-m3 bilan bir xil oʻlchamda — bu kompyuterda bir savolga 10 ta boʻlak ≈ 10–30 soniya qoʻshishi mumkin. Avval reranker’siz `eval` natijasini koʻramiz.

## 6. Sifatni oʻlchash

```bash
python -m modda eval                         # dense / sparse / hybrid: Recall@5, MRR, kechikish
```

## Kod qayerda (2-kun)

| Fayl | Nima qiladi |
|---|---|
| `src/modda/lexparse.py` | Lex.uz sahifasi → moddalar (bob, boʻlim, tahrir izohlari; «LexUZ sharhi» tashlanadi); 195¹ ni tiklash |
| `src/modda/router.py` | «MK 131-modda», «Mehnat kodeksining 195¹-moddasi» → toʻgʻridan-toʻgʻri modda |
| `src/modda/rerank.py` | CrossEncoder reranker (ixtiyoriy) |
| `src/modda/pipeline.py` | Butun yoʻl + har bosqich hodisasi (roadmap §12.4), raqamlarni tekshiruvchi |
| `src/modda/api.py` | FastAPI: `/health`, `/ask`, `/ask/stream` (SSE) |
| `src/modda/rss.py` | Lex.uz RSS → `rss_items`, eskirgan manbalar |

## 7. Toʻliq dense indeks — jamoadoshning GPU kompyuterida

Jamoadosh (Windows + NVIDIA): `git clone https://github.com/bobur120507/lex_uz_agent` → `scripts\setup_windows.bat` ni ikki marta bosadi. Skript hammasini oʻrnatadi, 183 170 boʻlakning hammasiga bge-m3 yozadi va `data\exports\` ga ikki fayl qoʻyadi ([SETUP-WINDOWS.md](SETUP-WINDOWS.md)).

Fayllar kelgach, shu kompyuterda:

```bash
python -m modda snapshot-import ~/Downloads/modda-<sana>.snapshot    # .manifest.json.gz yonida boʻlsin
python -m modda eval
```
