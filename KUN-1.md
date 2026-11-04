# 1-kun: bajarish tartibi

Hamma buyruqlar loyiha papkasida: `cd ~/Lex_Uz_AI_Agent`

## 0. Muhit (bir marta)

Loyihadagi `.venv` uv bilan yaratilgan (Python 3.14):

```bash
source .venv/bin/activate
uv pip install -e ".[dev]"     # psycopg ham oʻrnatiladi; uv yoʻq boʻlsa: pip install -e ".[dev]"
cp -n .env.example .env        # .env allaqachon boʻlsa, unga DATABASE_URL qatorini qoʻshing
python -m pytest -q            # 24 ta test, internet va server kerak emas
```

### PostgreSQL: yangi port, alohida baza

Mavjud PostgreSQL’ga tegmaslik uchun loyiha bazasi alohida konteynerda, **5433** portda ishlaydi:

```bash
docker run -d --name modda-pg --restart unless-stopped \
  -e POSTGRES_USER=modda -e POSTGRES_PASSWORD=modda -e POSTGRES_DB=modda \
  -p 5433:5432 -v ~/modda_pg:/var/lib/postgresql/data postgres:17
```

`.env` da:

```
DATABASE_URL=postgresql://modda:modda@localhost:5433/modda
```

Mavjud serverdan foydalanmoqchi boʻlsangiz (port oʻzgarmaydi), faqat yangi baza yarating:

```bash
sudo -u postgres createuser -P modda          # parol soʻraydi
sudo -u postgres createdb -O modda modda
# .env: DATABASE_URL=postgresql://modda:<parol>@localhost:5432/modda
```

Testlarni PostgreSQL’da ham ishlatish (ixtiyoriy, jadvallarni oʻchirib qayta yaratadi — **alohida** test bazasida):

```bash
MODDA_TEST_DATABASE_URL=postgresql://modda:modda@localhost:5433/modda_test python -m pytest -q
```

## 1-kunni bitta buyruq bilan yakunlash

Ollama ishlagach (pastdagi `curl … /api/embed` `"embeddings"` qaytarsa):

```bash
bash scripts/finish_day1.sh --full
```

Tartib bilan: Ollama tekshiruvi → `bench-embed` → `index --mvp` → 3 ta sinov savoli → `eval` → 3 ta modelni solishtirish → butun korpusni fonda indekslash. Hammasi `data/reports/day1-*.log` ga yoziladi — shu faylni menga yuboring. Indeks toʻliq boʻlmaguncha `eval` va `bakeoff` faqat indekslangan moddalardagi savollarni hisoblaydi.

## 1. Tekshirish — barcha talablar

```bash
python -m modda doctor
```

Tekshiradi: Python paketlari, korpus, Ollama versiyasi va rejadagi 4 ta model, **haqiqiy embedding** (oʻlcham 1024) va **haqiqiy chat** chaqiruvi, Qdrant, PostgreSQL, reranker fayllari, Docker, Node/npm va `web/node_modules`. `✗` — tuzatish shart, `–` — hozircha shart emas; har birining tagida nima qilish kerakligi yoziladi.

### `llama-server binary not found` (Ollama yangilangandan keyin)

Yangi Ollama modelni alohida `llama-server` dasturi orqali ishga tushiradi; u `ollama` bilan birga `/usr/local/lib/ollama/` papkasida boʻlishi kerak. Xato — yangilanishda faqat `ollama` fayli almashgan, kutubxonalar papkasi kelmagan degani.

```bash
which -a ollama                              # bittadan koʻp boʻlsa — ikki xil oʻrnatish aralashgan
ls /usr/local/lib/ollama | head              # llama-server shu yerda boʻlishi kerak
snap list 2>/dev/null | grep -i ollama       # snap orqali ham oʻrnatilganmi?
curl -fsSL https://ollama.com/install.sh | sh   # rasmiy oʻrnatuvchi: bin + lib/ollama ni birga qoʻyadi
sudo systemctl restart ollama
ls -la /usr/local/lib/ollama/llama-server
curl -s -m 60 http://localhost:11434/api/embed -d '{"model":"bge-m3","input":"salom"}' | head -c 120; echo
```

Modellar (`ollama list`) qayta yuklanmaydi — ular `~/.ollama` yoki `/usr/share/ollama` da saqlanadi.

**Oʻrnatuvchini oxirigacha kuting (Ctrl+C bosmang).** U yuklashdan *oldin* eski `/usr/local/lib/ollama` ni oʻchiradi — oʻrtada toʻxtatilsa, Ollama umuman ishlamaydi. Internet sekin boʻlsa, uzilsa ham davom etadigan qoʻlda yuklash:

```bash
sudo apt install -y zstd
cd ~/Downloads
curl -L -C - -o ollama-linux-amd64.tar.zst https://ollama.com/download/ollama-linux-amd64.tar.zst   # uzilsa — shu buyruqni qayta bering
sudo tar --zstd -C /usr/local -xf ollama-linux-amd64.tar.zst
sudo systemctl restart ollama
ls -la /usr/local/lib/ollama/llama-server
```

### Embedding javob bermasa (`/api/embed … javob bermadi`)

Server javob beradi, modellar roʻyxati bor, lekin embedding osilib qoladi — bu odatda model jarayoni (runner) osilib qolganini bildiradi. Tartib bilan:

```bash
ollama ps                                   # bge-m3 «Stopping…» holatida turibdimi?
ps aux | grep -c "[o]llama serve"           # 1 boʻlishi kerak; 2 boʻlsa — eski va yangi server birga ishlayapti
curl -s -m 60 http://localhost:11434/api/embed -d '{"model":"bge-m3","input":"salom"}' | head -c 120; echo
sudo systemctl restart ollama               # osilgan boʻlsa — qayta ishga tushirish
journalctl -u ollama -n 80 --no-pager       # hali ham ishlamasa — xato sababi shu yerda
ollama pull bge-m3                          # yangilanishdan keyin model faylini qayta yuklash
```

`curl` 1–2 soniyada `{"model":"bge-m3","embeddings":[[…` qaytarsa — hammasi joyida, `doctor` ni qayta ishga tushiring.

### PostgreSQL porti band boʻlsa (`port is already allocated`)

```bash
docker ps -a --filter publish=5433          # 5433 ni qaysi konteyner egallagan
sudo ss -ltnp 'sport = :5433'               # yoki qaysi dastur
docker rm modda-pg                          # yaratilib, ishga tushmay qolgan konteynerni oʻchirish
docker run -d --name modda-pg --restart unless-stopped \
  -e POSTGRES_USER=modda -e POSTGRES_PASSWORD=modda -e POSTGRES_DB=modda \
  -p 5434:5432 -v ~/modda_pg:/var/lib/postgresql/data postgres:17
sed -i 's#localhost:5433/modda#localhost:5434/modda#' .env
```

## 2. Korpus → PostgreSQL → boʻlaklar (≈ 3–8 daqiqa)

```bash
python -m modda ingest        # 54 173 qator (moddalar + 23 ming «moddasiz» qaror/farmon), normalizatsiya bilan → PostgreSQL
python -m modda chunk         # modda = boʻlak; uzun moddalar overlap bilan boʻlinadi
python -m modda stats         # hujjat turlari, status qiymatlari, tillar
```

Kutilgan natija: 54 173 qator (takror id’li ~1 300 qator ham saqlanadi), ≈ 181 ming boʻlak, MVP ≈ 11 800 boʻlak.

## 2a. Oltin toʻplam va parser uchun haqiqiy maʼlumot

```bash
python -m modda export-golden       # 14 ta asosiy hujjatdan 6 tadan haqiqiy modda → data/reports/golden-candidates.jsonl
python -m modda fetch-fixtures      # 10 ta Lex.uz sahifasi → tests/fixtures/lexuz/ (har biri orasida 20 s, ≈ 4 daqiqa)
```

Oltin toʻplam tayyor: `data/golden/golden.jsonl` — 60 savol (45 ta javobi bor, 15 ta yoʻq), 14 ta hujjat, 6 toifa.

## 3. Embedding tezligi (≈ 1–3 daqiqa) — eng muhim oʻlchov

```bash
python -m modda bench-embed
```

Natijada `mvp_eta` va `all_eta` — MVP qismi va butun korpus necha vaqtda indekslanishi. Shu raqam boʻyicha rejani aniqlashtiramiz.

## 4. MVP qismini indekslash (Konstitutsiya + kodekslar: `doc_type` = `constitution`, `code`)

```bash
python -m modda index --mvp
```

Ctrl+C bilan toʻxtatish mumkin — qayta ishga tushirsangiz, qolgan joydan davom etadi. Dense **va** BM25 vektorlar birga yoziladi, shuning uchun 2-kunda qayta indekslash kerak emas.

## 5. Birinchi savol

```bash
python -m modda ask "Yillik mehnat taʼtili necha kun?" --show-context
python -m modda ask "Yillik mehnat taʼtili necha kun?" --mode hybrid
python -m modda ask "Меҳнат таътили неча кун?"          # kirill savol
```

## 6. Modellarni solishtirish (oltin toʻplam tayyor boʻlgach)

```bash
python -m modda bakeoff --models qwen3:8b,gemma4:e4b,hf.co/QuantFactory/Llama-3.1-8B-Instuct-Uz-GGUF:Q4_K_M --n 20
```

Hisobot: `data/reports/bakeoff-*.md` va `.csv`. Avval eng kam **yolgʻon javob**, keyin eng koʻp **toʻgʻri manba**, keyin tezlik. Tanlangan modelni `.env` dagi `LLM_MODEL` ga yozing.

## 7. Kechqurun: butun korpus — tunga

```bash
nohup python -m modda index > data/index-full.log 2>&1 &
tail -f data/index-full.log
```

## 8. Qidiruv sifati (oltin toʻplam bilan)

```bash
python -m modda eval          # dense, sparse, hybrid: Recall@5, MRR, P50/P95
```

## 1-kun tayyorlik mezoni

- [ ] `doctor` — hammasi ✓
- [ ] MVP qismi boʻyicha `ask` manbali javob qaytaradi
- [ ] LLM tanlandi (`bakeoff` hisoboti)
- [ ] Oltin toʻplam ≥ 30 savol (`data/golden/golden.jsonl`)
- [ ] Toʻliq indekslash tunda ishlayapti
- [ ] 3D kitob: `cd web && npm run dev` → `http://localhost:5173/?debug`, varaqlash paytida ≥ 45 kadr/s

## Kod qayerda

| Fayl | Nima qiladi |
|---|---|
| `src/modda/textnorm.py` | Apostroflar, kirill → lotin, BM25 uchun tokenlar |
| `src/modda/db.py` | PostgreSQL / SQLite qatlami (bitta SQL ikkalasida ishlaydi) |
| `src/modda/corpus.py` | HF fayllarini topish, jadvallar sxemasi, import |
| `src/modda/chunking.py` | Modda → boʻlak, sarlavha (hujjat › bob › modda), overlap |
| `src/modda/llm.py` | Ollama: embedding va chat |
| `src/modda/sparse.py` | BM25 sparse vektorlar (Qdrant IDF bilan) |
| `src/modda/store.py` | Qdrant REST va xotiradagi nusxasi (testlar uchun) |
| `src/modda/indexing.py` | Tezlik oʻlchovi, davom etadigan indekslash |
| `src/modda/rag.py` | Qidiruv → prompt → [n] iqtiboslar → koddan Manba bloki |
| `src/modda/evaluation.py` | Oltin toʻplam, Recall@k, MRR, modellar solishtiruvi |
