# Modda’ni GPU noutbukka koʻchirish (RTX 4060, 16 GB RAM, Windows)

Maqsad: loyiha **jamoadoshning noutbukida ishlaydi** (Ollama + qwen3:8b GPU’da, Qdrant, server, sayt), Bobur esa uni **oʻz noutbukidan boshqaradi** (brauzer orqali saytni ochadi, kodni GitHub’ga yuboradi, kerak boʻlsa SSH bilan buyruq beradi). Natija — Bobur’ning kompyuteridagi holat bilan bir xil: 54 173 modda, 183 170 boʻlak, toʻliq dense indeks, gibrid Recall@5 ≈ 0,91.

Hamma ishni bitta skript qiladi: **`scripts\setup_server.bat`**. U Python, Git, Ollama, modellar, korpus, Qdrant, Node.js, sayt va Windows Firewall’ni oʻzi oʻrnatadi va sozlaydi.

---

## 1. Noutbukka nima olib boriladi

| Nima | Qayerdan | Qayerga |
|---|---|---|
| Loyiha | `git clone https://github.com/bobur120507/lex_uz_agent` (Git yoʻq boʻlsa — GitHub’da **Code → Download ZIP**) yoki fleshkada nusxa (`.venv`, `node_modules`, `data\qdrant_storage` papkalarisiz) | masalan `C:\Modda\lex_uz_agent` (yoʻlda boʻsh joy va kirillcha harf boʻlmagani yaxshi) |
| Indeks snapshot’i — **2 ta fayl**, 2 GB | Bobur’da: `~/Downloads/modda-20261105-0637.snapshot` va `modda-20261105-0637.manifest.json.gz` | noutbukdagi **Downloads** papkasiga (yoki loyihadagi `data\import\`) |

Snapshot boʻlsa indeks **≈ 1 daqiqada** yuklanadi. Boʻlmasa skript indeksni shu GPU’da qaytadan yasaydi (1–3 soat).

> Repozitoriy yopiq (private) boʻlsa: jamoadoshni GitHub’da **Settings → Collaborators** orqali qoʻshing yoki ZIP/fleshka yoʻlidan foydalaning.

## 2. Oʻrnatish (jamoadosh qiladi, ≈ 1–2 soat, asosan yuklab olish)

1. NVIDIA drayveri yangi boʻlsin (GeForce Experience yoki nvidia.com). Noutbuk zaryadlovchiga ulangan boʻlsin.
2. Loyiha papkasida **`scripts\setup_server.bat`** ni ikki marta bosing.
3. Ikki marta **«Ha / Yes»** soʻraladi (administrator): Windows Firewall’ga ruxsat (8080, 5174 portlar — faqat shaxsiy tarmoq) va (agar tanlangan boʻlsa) SSH.
4. Oxirida **TAYYOR!** va Bobur’dagi holat bilan solishtirish jadvali chiqadi. `data\reports\server-status.json` faylini Bobur’ga yuboring.

To‘xtab qolsa yoki internet uzilsa — xuddi shu faylni qayta ishga tushiring: tayyor qadamlar oʻtkazib yuboriladi, yuklab olish davom etadi. Har bir qadamning logi: `data\reports\setup-<sana>.log`.

| # | Qadam | Nima qiladi | Taxminiy vaqt |
|---|---|---|---|
| 1 | system | Windows, disk (≥ 40 GB boʻsh), RAM, GPU va drayver; ish davomida uyquga ketmaydi | soniyalar |
| 2 | git | Git for Windows (winget → portativ MinGit) | 1–3 daq |
| 3 | python | `.venv` + loyiha + FastAPI | 2–5 daq |
| 4 | ollama | Ollama (winget → rasmiy oʻrnatuvchi → zip) | 2–5 daq |
| 5 | models | `bge-m3`, `qwen3:8b` + bakeoff uchun `gemma4:e4b`, Llama-3.1-8B-Uz; GPU’da ishlashini tekshiradi | 20–60 daq |
| 6 | corpus | Lex.uz korpusi (HF, qatʼiy versiya, checksum) | 2–5 daq |
| 7 | qdrant | Qdrant v1.20.0 (portativ, Docker shart emas) | 1 daq |
| 8 | env | `.env` (SQLite, parol yoʻq) | — |
| 9–11 | ingest, numbers, chunk | 54 173 modda → 195¹ raqamlari → 183 170 boʻlak | 5–15 daq |
| 12 | rss | Lex.uz RSS (yangi hujjatlar) | soniyalar |
| 13 | index | **snapshot-import** (topsa) yoki GPU’da toʻliq indeks | 1 daq / 1–3 soat |
| 14 | eval | 45 oltin savol: Recall@5, MRR — Bobur’dagi 0,911 bilan solishtiradi | 1 daq |
| 15–16 | node, frontend | Node.js LTS, `npm ci`, unit testlar, `npm run build` | 3–5 daq |
| 17 | lan | Firewall: boshqa kompyuterdan saytni ochish uchun | soniyalar |
| 18 | launchers | `start_modda.bat`, `start_dev.bat`, `update_modda.bat`, `status_modda.bat` | — |
| 19 | verify | serverni ishga tushirib, qwen3:8b bilan haqiqiy savol beradi va saytni tekshiradi | 10–60 s |

Qoʻshimcha (faqat soʻralsa):

```bat
scripts\setup_server.bat --ssh --ssh-key bobur_id_ed25519.pub     :: Bobur SSH bilan boshqaradi (parolsiz)
scripts\setup_server.bat --autostart                               :: kompyuterga kirganda server oʻzi yonadi
scripts\setup_server.bat --reranker                                :: reranker uchun CUDA PyTorch (≈ 3 GB, 4-kun)
scripts\setup_server.bat --no-bakeoff-models                       :: faqat bge-m3 + qwen3:8b (≈ 7 GB kam yuklash)
```

## 3. Har kuni

| Fayl (loyiha papkasida) | Nima |
|---|---|
| `start_modda.bat` | Ollama + Qdrant + server. Sayt: **http://localhost:8080**, boshqa kompyuterdan **http://&lt;noutbuk-IP&gt;:8080** (IP oynada yoziladi). Oynani yopsangiz server toʻxtaydi |
| `start_dev.bat` | Xuddi shu + Vite dev server **:5174** (kod oʻzgarsa sahifa oʻzi yangilanadi) |
| `update_modda.bat` | `git pull` + Python paketlari + `npm ci` + sayt yigʻish |
| `status_modda.bat` | Nima ishlayapti, indeks, modellar, GPU’dagi modellar, manzillar |

## 4. Bobur noutbukni oʻz kompyuteridan qanday boshqaradi

1. **Saytni ochish:** ikkala kompyuter bir Wi-Fi’da → Bobur brauzerida `http://<noutbuk-IP>:8080`. Wi-Fi tarmogʻi noutbukda **Private** boʻlishi kerak (Sozlamalar → Tarmoq → Wi-Fi → Xususiyatlar → *Private network*). Universitet/umumiy Wi-Fi’da kompyuterlar bir-birini koʻrmasligi mumkin — unda telefon hotspot’i yordam beradi.
2. **Kodni yangilash:** Bobur oʻzida oʻzgartiradi → `git push` → noutbukda `update_modda.bat` (yoki SSH orqali, quyida) → `start_modda.bat` ni qayta ishga tushirish.
3. **SSH (ixtiyoriy, `--ssh` bilan yoqiladi):**
   ```bash
   # Bobur’ning Linux noutbukida, bir marta: kalit yaratib, .pub faylini jamoadoshga yuborish
   ssh-keygen -t ed25519 -f ~/.ssh/modda_server -C bobur
   # jamoadosh: scripts\setup_server.bat --ssh --ssh-key modda_server.pub
   ssh -i ~/.ssh/modda_server <foydalanuvchi>@<noutbuk-IP>
   cd C:\Modda\lex_uz_agent; .\update_modda.bat; .\status_modda.bat
   ```
   VS Code’dagi **Remote – SSH** kengaytmasi bilan noutbukdagi fayllarni bevosita tahrirlash ham mumkin.
4. **Bobur’ning backend’i jamoadoshning GPU’sidagi LLM bilan** (kerak boʻlsa): bu skript Ollama’ni tarmoqqa **ochmaydi** (xavfsizlik uchun). Kerak boʻlsa noutbukda `setx OLLAMA_HOST 0.0.0.0:11434`, Ollama’ni qayta ishga tushirish va 11434 portiga Firewall ruxsati; Bobur’da `OLLAMA_URL=http://<IP>:11434`.

## 5. 3-kun: `scripts\day3.bat`

GPU tekshiruvi → (snapshot bilan) oʻrnatish → bakeoff → 6 demo savol, hammasi bitta hisobotga: `data\reports\day3-<vaqt>.log`. Batafsil: [KUN-3.md](KUN-3.md).

## 6. Muammolar

| Belgi | Sabab va yechim |
|---|---|
| bge-m3 sekin (< 25 boʻlak/s) yoki «… % GPU’da» 100 dan kam | Zaryadlovchini ulang; VRAM’dagi boshqa dasturlarni yoping (roʻyxat `day3.bat --only gpu` da); Ollama’ni qayta ishga tushiring (lama belgisi → Quit, qayta oching) |
| `models`: «GPU ishlatilmayapti» | NVIDIA drayverini yangilang, kompyuterni qayta yoqing, `scripts\setup_server.bat --only models,verify` |
| `index`: snapshot import oʻtmadi | Skript oʻzi `chunk --rebuild` qilib qayta urinadi, boʻlmasa GPU’da yasaydi. Fayllar toʻliq koʻchirilganini tekshiring (`.snapshot` ≈ 1,98 GB) |
| Boshqa kompyuterdan sayt ochilmaydi | Tarmoq *Public* — *Private* qiling; `scripts\setup_server.bat --only lan`; ikkala kompyuter bir tarmoqdami |
| Port 8080 band | Server allaqachon boshqa oynada ishlayapti — `status_modda.bat` |
| Javob sekin (> 60 s) | `status_modda.bat` → «GPU’da hozir» qatorida qwen3:8b VRAM bilan koʻrinishi kerak |

Har qanday xatoda: `data\reports\setup-<sana>.log` faylini Bobur’ga yuboring.
