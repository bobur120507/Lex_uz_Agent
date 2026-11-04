# Windows + NVIDIA GPU: toʻliq indeksni yasash

Bu sahifa — kuchli GPU’li Windows kompyuter uchun. Skript hamma narsani oʻzi oʻrnatadi, butun korpusni **bge-m3** bilan indekslaydi va natijani Bobur’ga yuboriladigan **ikki faylga** joylaydi. Parol, token yoki akkaunt kerak emas.

## Nima kerak

* Windows 10/11, NVIDIA GPU (drayver **551.61** yoki yangiroq), diskda **≈ 20 GB** boʻsh joy, internet.
* Loyiha: `git clone https://github.com/bobur120507/lex_uz_agent` — yoki GitHub’dan **Code → Download ZIP** va oching.
* Python, Ollama, Hugging Face CLI, Qdrant **shart emas** — skript oʻzi oʻrnatadi.

## Ishga tushirish

`scripts\setup_windows.bat` faylini **ikki marta bosing**. Python yoʻq boʻlsa, avval Python 3.12 ni oʻrnatadi.

Python allaqachon bor boʻlsa, terminalda ham boʻladi:

```bat
cd lex_uz_agent
python scripts\setup_windows.py
```

Keyin kompyuterni yoqiq qoldiring: skript ishlayotgan paytda Windows uyquga ketmaydi. Taxminiy vaqt: yuklab olish 10–30 daqiqa (internetga bogʻliq), indeks GPU’da 30–90 daqiqa.

## Skript nima qiladi

| # | Qadam | Bitta usul ishlamasa |
|---|---|---|
| 1 | Kompyuterni tekshiradi: Python, disk, RAM, GPU va drayver | eski drayver — ogohlantiradi va havolani koʻrsatadi |
| 2 | `.venv` va paketlar | `pip` → `--no-cache-dir` → qisqa roʻyxat → oddiy oʻrnatish |
| 3 | Ollama | ishlayapti? → diskda bormi? → `winget` → rasmiy oʻrnatuvchi → portativ zip |
| 4 | `bge-m3` (+ `qwen3:8b`) modellari, GPU ishlatilayotganini tekshiradi | Ollama API → `ollama pull` (3 marta urinadi) |
| 5 | Korpus (bir xil versiya — `c69bbd5`) | `hf` → `huggingface-cli` → `huggingface_hub` → toʻgʻridan-toʻgʻri HTTPS (uzilsa davom etadi, sha256 tekshiriladi) |
| 6 | Qdrant v1.20.0 (Bobur’dagi bilan bir xil) | ishlayapti? → portativ Windows versiyasi → Visual C++ Runtime → Docker |
| 7 | `.env` — SQLite, parolsiz | eski `.env` saqlanadi (`.env.backup`) |
| 8 | `ingest → chunk → fix-numbers → bench-embed` | |
| 9 | Indeks: GPU tez boʻlsa **hamma 183 170 boʻlakka** bge-m3 + BM25, sekin boʻlsa ikki qatlamli | toʻxtasa — Ollama’ni qayta ishga tushirib, qolgan joydan davom etadi |
| 10 | `eval` — sifat oʻlchovi | muhim emas, xato boʻlsa oʻtkazib yuboriladi |
| 11 | `snapshot-export` → `data\exports\` | |

Har qadamning vaqti ekranda va logda: `data\reports\setup-<sana>.log`. Oxirida jadval: qaysi qadam qancha vaqt oldi.

## Toʻxtab qolsa

* **Qayta ishga tushiring** — xuddi shu buyruq. Tayyor qadamlar oʻtkazib yuboriladi, indeks qolgan joydan davom etadi. Ctrl+C bilan toʻxtatish ham xavfsiz.
* Xato tushunarsiz boʻlsa — `data\reports\` dagi oxirgi `setup-*.log` faylini Bobur’ga yuboring.
* Foydali parametrlar:

```bat
python scripts\setup_windows.py --list            :: qaysi qadamlar tayyor
python scripts\setup_windows.py --from index      :: shu qadamdan boshlab
python scripts\setup_windows.py --only corpus     :: faqat bitta qadam
python scripts\setup_windows.py --skip-llm        :: qwen3:8b (5 GB) ni yuklamaslik
python scripts\setup_windows.py --fresh           :: holatni unutib, hammasini qayta tekshirish
```

## Natija: Bobur’ga nima yuboriladi

Skript oxirida `data\exports\` papkasini ochadi. U yerda ikki fayl:

* `modda-<sana>.snapshot` — butun indeks (≈ 1–2 GB);
* `modda-<sana>.manifest.json.gz` — qaysi boʻlak qanday indekslangani va tekshiruv summasi.

Ikkalasini Google Drive yoki Telegram orqali Bobur’ga yuboring — u ikkalasini **bitta papkaga** saqlaydi.

## Bobur’ning kompyuterida (Linux)

```bash
cd ~/Lex_Uz_AI_Agent && source .venv/bin/activate
git pull                                       # kod bir xil boʻlishi kerak
python -m modda snapshot-import ~/Downloads/modda-<sana>.snapshot
python -m modda stats                          # chunks_indexed ≈ 183 170
python -m modda eval
```

Import boʻlaklar roʻyxati mosligini tekshiradi (kod va korpus bir xil boʻlishi shart). Mos kelmasa, tushunarli xato chiqaradi va hech narsani oʻzgartirmaydi.
