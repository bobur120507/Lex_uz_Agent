# 4-kun (7–8-noyabr) — GPU noutbuk natijalari va yakuniy sozlash

## 1. Natijalar (`day3`, `day4` loglari, `BAHOLASH.md`)

**Holat Bobur’dagi bilan aynan bir xil ✅** — 54 173 modda · 183 170 boʻlak · 183 170 dense (snapshot 1,5 daqiqada yuklandi) · gibrid **Recall@5 0,911**, MRR 0,767–0,773, dense 0,800, BM25 0,778. Sayt `http://10.50.3.9:8080` da ochildi, Firewall faqat Private tarmoqda.

**GPU:** bge-m3 100 % GPU’da. Birinchi oʻlchov **batareyada** boʻlgan (16,7 boʻlak/s, qwen3:8b 6,4 token/s); zaryadlovchida qwen3:8b **23–41 token/s**. bakeoff 6 soat davom etgan — 16:09 dan 21:48 gacha log jim: noutbuk uxlagan/qopqogʻi yopilgan (skript uyquni oʻchiradi, qopqoqni yopish esa baribir uxlatadi).

**LLM solishtiruvi (20 oltin savol, bir xil kontekst):**

| Model | Toʻgʻri manba | Toʻgʻri «Bilmayman» | Yolgʻon javob | Vaqt |
|---|---|---|---|---|
| qwen3:8b | 12/15 | 2/4 | **2** | 6,5 s |
| **gemma4:e4b** | 12/15 | **5/5** | **0** | 15,4 s |
| Llama-3.1-8B-Uz | 7/14 | 4/4 | 0 | 22,1 s |

Kelishilgan qoida (avval eng kam yolgʻon, keyin toʻgʻri manba, keyin tezlik) boʻyicha **gemma4:e4b** tanlanadi. Narxi: javob ≈ 2× sekinroq (15 s), lekin yolgʻon javob yoʻq.

**τ:** `DENSE_TAU=0.58` — javobi bor savollarning 98 % i oʻtadi, javobi yoʻqlarning 54 % i LLM’siz «Bilmayman» (`.env` ga yozildi).

**6 demo savol (qwen3:8b):**

| # | Savol turi | Natija | Tahlil |
|---|---|---|---|
| 1 | aniq modda | ✅ Konstitutsiya 1-modda, baho 100 | — |
| 2 | mehnat taʼtili | ❌ «Bilmayman» | LLM eski kodeksdagi «**15 ish kuni**» ni yozdi — tekshiruvchi toʻgʻri rad etdi (manbada yoʻq). Yangi kodeksda «**yigirma bir** kalendar kun» — soʻz bilan; LLM «21» yozsa ham avval rad etilardi → **tuzatildi** (pastda) |
| 3 | kirillcha | ✅ Mehnat kodeksi 100-modda, baho 95,8 | — |
| 4 | QQS stavkasi | ⚠️ Soliq kodeksi 211¹, baho 28,5 | QQS stavkasi moddasi (12 %) top-5 ga kirmagan |
| 5 | ob-havo (javobsiz) | ❌ ekologiya hujjatlaridan 2 gap | τ dan oʻtgan (Toshkent soʻzi), qwen3 «Bilmayman» demadi → gemma4 (5/5) + prompt qoidasi |
| 6 | prompt-injection | ✅ «Bilmayman», 6,6 s | koʻrsatmaga boʻysunmadi |

**Sayt kadr/s: 27 (eng past 21)** — chunki brauzer **Intel Iris Xe** da chizgan, RTX 4060 da emas (Windows ikki GPU’li noutbukda brauzerga standart holda integratsiyalangan GPU beradi). Javob video vaqtida 42,6 s (model qayta yuklangan + Iris).

**Log muammosi:** buyruqlar chiqishi logda boʻsh qatorlar boʻlib qolgan (Windows `\r\n` ni skript «progress» deb tushungan) — **tuzatildi**.

## 2. Tuzatishlar (Bobur tomoni, 7-noyabr 23:00)

* **Raqam soʻz bilan:** tekshiruvchi manbadagi «yigirma bir», «oʻn besh foiz», «ikki ming yigirma oltinchi» ni raqam deb ham taniydi (`textnorm.number_words`). «21 kalendar kun» endi oʻtadi, «15 ish kuni» hali ham rad etiladi. Test qoʻshildi.
* **Prompt:** raqam/muddatni manbadagidek yozish, eski qonundan raqam olmaslik; savol qonunchilik haqida boʻlmasa (ob-havo, sport…) — faqat BILMAYMAN.
* **LLM javobi ≤ 700 token** (`num_predict`) — cheksiz generatsiya boʻlmaydi.
* **Log:** Windows qator oxiri toʻgʻri oʻqiladi.
* **day4:** `--llm` dan keyin model tezligi va GPU ulushi koʻrsatiladi; yangi qism **`browser`** — Chrome/Edge/Playwright Chromium uchun Windows «Grafika → Yuqori unumdorlik» (RTX 4060); video yozuvida ham shu bayroq.
* **Sayt:** kitobning oʻng tomonida **hakam bolgʻachasi** (3D, Bobur’ning modeli, 5,2 → 1,0 MB); javob tayyor boʻlganda tarozi bilan birga **bir marta uradi** (yorugʻlik halqasi), bosilsa yana uradi. Sarlavha: **«Javob qonundan — isbot manbadan»**.

## 3. Jamoadosh endi nima qiladi

```bat
git pull
scripts\day4.bat --llm gemma4:e4b --only llm,browser,demo,build,fixture,video,report
```

Brauzer oynalarini oldindan yoping. Zaryadlovchi ulangan, qopqoq ochiq boʻlsin. ≈ 10 daqiqa. Bobur’ga: `data\reports\day4-*.log`, `data\reports\fixture.json`, `data\reports\BAHOLASH.md` (video — ixtiyoriy).

Kutilgan: 2-savol endi «21 kalendar kun» bilan javob, 5-savol «Bilmayman», kadr/s ≥ 45 (RTX 4060).

## 4. Ikkinchi ishga tushirish (7-noyabr 23:44, kod `a0439e5`, gemma4:e4b)

| Qism | Natija |
|---|---|
| llm | gemma4:e4b **81,7 token/s**; bge-m3 va gemma4 ikkalasi **100 % GPU’da** birga sigʻdi |
| browser | Chrome, Edge, Playwright Chromium → «Yuqori unumdorlik» ✅ |
| video | **RTX 4060** (ANGLE D3D11) · kadr/s **median 60, eng past 53** (maqsad ≥ 45) · render koeff. 1,5 ✅ (avval Iris Xe’da 27) |
| build | Vite ✅ 4,7 s; bolgʻacha 1,03 MB, haykal 3,6 MB |
| report | qidiruv: gibrid Recall@5 **0,911**, MRR **0,773** (oʻzgarmadi) |
| **demo** | ❌ **1-savol ✅ (95,9), 2–4 — notoʻgʻri «Bilmayman», 5 ✅, 6 ✅** |

**Demo nega buzildi — tashxis.** 2- va 3-savolda LLM **aynan 700 token** yozgan (`num_predict` chegarasi), lekin javob matni **boʻsh** (0/0 gap); 4-savolda 2 gap chiqqan-u, ikkalasi ham kesilgan. gemma4 — «fikrlaydigan» model: Ollama’da `think` yuborilmasa, u avval yashirin mulohaza yozadi (u `message.thinking` maydoniga tushadi, bizning `content` ga emas). Kodda `think: false` faqat qwen3/deepseek-r1/gpt-oss uchun yuborilardi → gemma4 butun 700 tokenni yashirin mulohazaga sarflagan, javobga token qolmagan. Day-3 bakeoff’da chegara yoʻq edi — shuning uchun u yerda gemma4 yaxshi javob bergan, lekin **15,4 s** (vaqtining katta qismi — yashirin mulohaza). Sinov muhitida aynan shu holat qayta yaratildi: eski kod → 6/6 «700 token · 0/0 gap · Bilmayman»; yangi kod → hammasi javob beradi.

**Yana ikki topilma.**
* Yuborilgan `BAHOLASH.md` va `fixture.json` — **eski nusxalar** (22:09 dagi; md5 bir xil). Yangilari noutbukda `data\reports\` da qolgan. Yangi hisobotning matni logda bor — demo jadvalidan boshqa hamma joyi eskisi bilan bir xil.
* «Indeks toʻliq emas» ogohlantirishi **yolgʻon** edi: tekshiruv Qdrant ishga tushishidan oldin boʻlgan (keyingi qismlar 183 170 nuqtani koʻrgan).
* fixture va video ham shu buzilgan gemma4 bilan yozilgan (javob 9,5 s, 12 hodisa — katta ehtimol bilan «Bilmayman») → qayta yoziladi.

## 5. Tuzatishlar (8-noyabr 00:05)

* **`think: false` hamma modelga** (`llm.chat`): Ollama fikrlamaydigan modelda buni eʼtiborsiz qoldiradi; rad etsa — soʻrov `think` siz qayta yuboriladi. `<think>`, `<thought>` bloklari (yopilmagani ham) matndan olib tashlanadi.
* Javob chegarasi **700 → 900 token**; chegaraga yetsa `truncated`, yashirin mulohaza boʻlsa `thinking_chars` — `generation.completed` hodisasida, demo chiqishida «⚠ LLM token chegarasiga yetdi», bakeoff jadvalida **«Kesilgan»** ustuni, hisobotda «(LLM kesildi)».
* Demo: «Bilmayman» boʻlsa LLM’ning **xom matni** ham chiqadi — keyingi safar sabab logdan darhol koʻrinadi.
* **`day4 --llm auto`**: yangi `bakeoff` qismi (gemma4:e4b va qwen3:8b, 20 oltin savol, fikrlashsiz) → qoida (eng kam yolgʻon → koʻp toʻgʻri manba → kam xato → tezlik) gʻolibni `.env` ga yozadi → demo shu model bilan. Day-3 bakeoff gemma4’ni fikrlash bilan oʻlchagan edi, endi ikkalasi teng sharoitda.
* `day4`: indeks tekshiruvidan **oldin** Qdrant ishga tushiriladi (yolgʻon ogohlantirish yoʻq).
* `day4` oxirida **shu ishga tushirishning oʻz fayllari** `data\reports\Bobur_uchun-<vaqt>\` papkasiga yigʻiladi (log, BAHOLASH, fixture, demo/bakeoff JSON/CSV, video). Eski fayl yuborilib qolmaydi.
* Testlar: **53** (fikrlash, chegarada kesilish, `think` rad etilganda qayta urinish, bakeoff tanlash qoidasi).

## 6. Jamoadosh endi nima qiladi (≈ 15 daqiqa)

```bat
git pull
scripts\day4.bat --llm auto --only demo,fixture,video,report
```

`--llm auto` bakeoff va llm qismlarini oʻzi qoʻshadi. Zaryadlovchi ulangan, qopqoq ochiq, brauzer oynalari yopiq; video vaqtida (≈ 1 daqiqa) sichqonchaga tegmang. Oxirida ekranda koʻrsatilgan **`data\reports\Bobur_uchun-…` papkasini toʻliq** yuboring.

Kutilgan: bakeoff’da gemma4 vaqti 15 s dan ≈ 3–5 s ga tushadi, «Kesilgan» = 0; demo 2-savol «yigirma bir kalendar kun», 5-savol «Bilmayman»; fixture — haqiqiy javob.
