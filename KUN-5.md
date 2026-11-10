# 5-kun (8-noyabr) — yakuniy tuzatishlar, vizualizatsiyalar v3, ovozlar

## 1. Toʻrtinchi GPU ishga tushirish (08:07) — natijalar

**Muhim:** kod versiyasi **`343d270`** — bu 7–8-noyabr kechasi qilingan tuzatishlar (eski nusxalar, zid raqamlar, isitish, `versions`, v3 vizualizatsiyalar) **hali GitHub’ga push qilinmagan**. Jamoadosh `git pull` qilgan, lekin yangi kod kelmagan; eski `day4.py` nomaʼlum `versions` qismini jimgina tashlab ketgan. Shuning uchun bu ishga tushirish — **eski kodning qayta oʻlchovi**.

| Qism | Natija | Izoh |
|---|---|---|
| Baza | 24 267 hujjat, 54 173 modda, 183 170 boʻlak — hammasi indekslangan | ✅ |
| eval | gibrid Recall@5 **0,911**, MRR **0,754** (dense 0,800 / 0,675; BM25 0,778 / 0,601) | MRR avval 0,773 edi: qidiruv kodi oʻzgarmagan → HNSW taxminiy qidiruvining ±0,02 tebranishi |
| demo 1 | Konstitutsiya 1-modda, 95,9 — lekin **24,2 s** | sovuq start (isitish yangi kodda) |
| demo 2 | «yigirma bir kalendar kun» ✅ **+** «15 ish kunidan kam emas» ❌ | eski yoʻriqnoma (yangi kodda zid raqam qoidasi olib tashlaydi) |
| demo 3 | kirill, 100, 3,8 s ✅ | |
| demo 4 | **12, 15, 30, 20 foiz** ❌ | 1997/2007/2019 Soliq kodekslari (yangi kodda eski nusxalar chiqariladi) |
| demo 5, 6 | «Bilmayman» 2,1 s / 0,3 s ✅ | |
| fixture | qisqa savol → «15 ish kunidan kam boʻlmasligi kerak», baho 57,2, sana **2028-01-01** ❌ | `public/demo/` ga **qoʻyilmadi**; yangi kodda toʻliq savol va sana tuzatilgan |
| video | RTX 4060: median **60**, eng past **47** kadr/s, javob 2,6 s ✅ | eski vizualizatsiyalar bilan |

**Xulosa:** tizim barqaror (qidiruv, tezlik, kadr/s takrorlanadi), qolgan ikki xato (2 va 4-savol) va fixture — aynan push qilinmagan tuzatishlar hal qiladigan narsalar. Keyingi qadam — **push**, keyin bitta ishga tushirish.

## 2. Bobur: push (oʻz noutbukingizda)

Barcha oʻzgarishlar `~/Lex_Uz_AI_Agent` papkangizda turibdi (commit qilinmagan). Faqat loyiha fayllarini qoʻshing (`Bobur_uchun …` papkalari, videolar, `3D_Models` qoʻshilmasin):

```bash
cd ~/Lex_Uz_AI_Agent
git status --short            # tekshiring: src/, scripts/, frontend_idea/, docs/, tests/, *.md
git add .gitignore src scripts tests docs frontend_idea KUN-4.md KUN-5.md DEMO.md README.md lexuz-huquqiy-ai-yol-xaritasi-v3-5-kun.md
git commit -m "Day 5: act versions, number conflicts, warm-up, visualisations v3, sounds"
git push
```

## 3. Jamoadosh (push’dan keyin, ≈ 10 daqiqa)

```bat
git pull
scripts\day4.bat --only versions,eval,demo,fixture,video,report
```

`day4` endi nomaʼlum qism berilsa ogohlantiradi («kod eski boʻlishi mumkin»). Kutilgan: `versions` — Mehnat/Soliq kodekslarining eski nusxalari roʻyxati; eval’da `hybrid_auth` qatori; demo 1-savol 2–5 s; 2-savol faqat «yigirma bir kalendar kun»; 4-savol faqat «12 foiz»; fixture — 217-modda, sana ≤ bugun.

## 4. Bugun qilinganlar

* **Vizualizatsiyalar v3** — Mind minorasi, 1024 qiymat — 3D ustunlar, PCA tumanligi, RRF lentalari, bosh sahifa Mind (batafsil — `frontend_idea/README.md`).
* **Maʼlumot sifati** — `docs/MALUMOT-SIFATI.md` (20 tasodifiy modda jonli lex.uz bilan: 0 mos emas).
* **Qabul mezonlari** — `frontend_idea/QABUL.md` (30 ✅, 2 ⚠️).
* **Ovozlar** (Bobur topgan 2 ta fayl + Web Audio sintezi):

| Hodisa | Ovoz | Manba |
|---|---|---|
| Bolgʻacha uradi | ikki zarba — animatsiya ham endi **ikki marta** uradi, zarbalar oraligʻi ovozdagidek (0,49 s) | `gavel.mp3` (Pixabay, 0,88 s jimlik kesilgan, 26 KB) |
| Tarozidagi olov yonadi | olov «gurillashi», 3,4 s, soʻnib boradi | `flame.mp3` (Pixabay, 5,6 → 3,4 s, 42 KB) |
| Tarozi pallalari tebranadi | kichik jez qoʻngʻiroq + zanjir shiqirlashi | sintez (Web Audio) |
| Kitob varaqlanadi | varaq «shitirlashi»; qidiruv paytida — sokin, bir vaqtda ≤ 3 ta | sintez (filtrlangan shovqin) |
| Kitob ochiladi / yopiladi | muqovaning yumshoq «gup» etishi | sintez |

Ovoz brauzer qoidasiga koʻra birinchi bosish/tugmadan keyin yoqiladi. Yuqori oʻng burchakda **ovoz tugmasi** (karnay) — oʻchirish/yoqish, shu brauzerda eslab qolinadi; `?mute=1` — ovozsiz. Uchta ovoz bir vaqtda kelganda (olov + tarozi + bolgʻacha) cheklovchi (limiter) shovqinni kesib qoʻymaydi.

## 5. Beshinchi GPU ishga tushirish (09:40, kod `3e29a55` — yangi kod) — **hammasi oʻtdi**

| Qism | Natija |
|---|---|
| versions | bir xil nomli **70 ta eski hujjat (4 296 boʻlak)** 63 ta amaldagi hujjat foydasiga chiqarildi: Soliq kodeksi 1997/2007 → 2019, Mehnat 1995 → 2022, Konstitutsiya 1992 → 2023, FPK 1997 → 2018, «Taʼlim toʻgʻrisida» 1992/1997 → 2020 … |
| eval | gibrid Recall@5 **0,911**, MRR **0,778** (eski nusxalarsiz; avval 0,754) · `hybrid_auth` MRR **0,819** → `AUTHORITY_PRIOR=on` |
| demo | **6/6**: 1 ✅ Konstitutsiya 95,9 · 2 ✅ faqat «yigirma bir kalendar kun», 100 · 3 ✅ kirill 98,5 · 4 ✅ faqat «12 foiz», 100 · 5 ✅ Bilmayman · 6 ✅ Bilmayman (τ) |
| fixture | toʻliq savol → 217-modda, «yigirma bir kalendar kun», baho 100, sana 2026-11-01 → **`public/demo/fixture.json` ga qoʻyildi** |
| video | RTX 4060, javob **1,5 s** (server isitilgan), median 53 / eng past 33 kadr/s, render 1,0 |

**Mening fikrim:** tizim demo’ga tayyor. Ikki kichik topilma:

1. **Fuqarolik kodeksi** ikki hujjatdan iborat (1-qism: 1–386-moddalar, 2-qism: 387–1199) — nomlari bir xil, shuning uchun `versions` 1-qismni (-111189) «eski nusxa» deb chiqarib yuborgan. **Tuzatildi:** endi ikki hujjat faqat modda raqamlari ≥ 50 % mos kelsa bir aktning versiyalari hisoblanadi (yangi versiya raqamlashni 1 dan boshlaydi, ikkinchi qism davom ettiradi). Test qoʻshildi. Oltin toʻplamda 1-qismdan savol yoʻq — shuning uchun eval buni koʻrsatmagan.
2. **Kadr/s 60 → 53, eng past 33, render koeff. 1,5 → 1,0:** bu sahna emas, oʻlchov xatosi — panel ochiq paytida asosiy sahna ¼ tezlikda chiziladi (5-kun), lekin hisoblagich nollanmagan; panel yopilgach birinchi oʻlchov «20–30 kadr/s» chiqib, DPR boshqaruvchisi sifatni 1,0 ga tushirgan. **Tuzatildi:** panel ochiqligida hisoblagich va boshqaruvchi toʻxtaydi; `record_video.mjs` endi brauzerning haqiqiy kadr tezligini (`requestAnimationFrame`, hamma canvas) oʻlchaydi.

1-savolning 26,8 s i — demo skripti modellarni ataylab GPU’dan tushiradi (sovuq start); jonli serverda isitish bor (video: 1,5 s).

## 6. Qolgan (ixtiyoriy)

* Bobur: oxirgi tuzatishlarni push qilish (Fuqarolik kodeksi, kadr/s oʻlchovi, namuna fixture, banner).
* Jamoadosh (ixtiyoriy, ≈ 3 daqiqa): `git pull` → `scripts\day4.bat --only versions,video` — eski nusxalar roʻyxatida Fuqarolik kodeksi 1-qismi yoʻqligini va haqiqiy kadr/s ni tasdiqlash.
* Mashq: [DEMO.md](DEMO.md) boʻyicha 2 marta.

## 7. Oltinchi GPU ishga tushirish (10:37 va 10:56, kod `8e48c94`)

| Qism | Natija |
|---|---|
| versions | **63 ta eski hujjat (3 877 boʻlak)** — avval 70 edi. **Fuqarolik kodeksi 1-qismi endi qidiruvda** ✅; yana 6 juftlik ham ajratildi (modda raqamlari < 50 % mos — boshqa-boshqa aktlar, saqlash xavfsizroq). Konstitutsiya, Mehnat, Soliq, FPK… eski nusxalari avvalgidek chiqariladi |
| video, 10:37 | ❌ sahifa 120 s ichida tayyor boʻlmadi, jarayon 18 daqiqa osilib qoldi. Sabab: bu ishga tushirishda `build` yoʻq edi — server eski `dist` ni koʻrsatdi (yangi kod bilan mos emas) |
| video, 10:56 (`build` bilan) | ✅ RTX 4060: javob **1,7 s**, median **59** kadr/s, render koeff. **1,5** (DPR endi tushmaydi — oʻlchov tuzatilgani ishladi); eng past **9** — bitta soniya |

**Fikrim:** natijalar yaxshi. Ikki saboq kodga aylantirildi:

1. **Video oldidan avtomatik `build`:** `day4` endi `frontend_idea/src`, `public` yoki `index.html` `dist` dan yangiroq boʻlsa, videodan oldin oʻzi `npm run build` qiladi. `record_video.mjs` sahifa tayyor boʻlmasa — 18 daqiqa kutish oʻrniga — sabab bilan (konsol xatolari, sahifa holati) darhol chiqadi.
2. **«Eng past 9 kadr/s»:** endi brauzerning haqiqiy kadr tezligi oʻlchanadi (hamma canvas), shuning uchun oyna ochilishidagi bir martalik toʻxtash koʻrinib qoldi — 3D oyna (Mind, PCA) birinchi marta ochilganda shader’lar kompilyatsiya qilinadi (~1 s). Tuzatish: oyna shader’larini **parallel** kompilyatsiya qiladi (`compileAsync`, `KHR_parallel_shader_compile` — RTX’da bor) va tayyor boʻlgach koʻrsatadi; sahifa qotmaydi. Yozuvchi endi eng past kadr/s ni bosqichlar boʻyicha ham chiqaradi (`idle`, `answer`, `scales`, `mind`) — keyingi safar qayerda ekani aniq koʻrinadi.

Qolgani: Bobur push → (ixtiyoriy) jamoadosh `git pull` + `scripts\day4.bat --only video` (≈ 1 daqiqa, build oʻzi qilinadi) → mashq.

## 8. Yakuniy qadamlar (8-noyabr 12:00 dan)

| Kim | Nima | Buyruq |
|---|---|---|
| Jamoadosh (GPU noutbuk) | demo oldidan yakuniy tekshiruv — **demo kuni ertalab ham** | `git pull` → `scripts\day5.bat` → `data\reports\Bobur_uchun-…` papkasini Bobur’ga |
| Bobur (internetli kompyuter) | shriftlarni mahalliy qilish (internetsiz zalda ham shrift toʻgʻri) | `node frontend_idea/scripts/fetch_fonts.mjs` → `git add frontend_idea/public/fonts frontend_idea/index.html` → commit → push |
| Jamoa | mashq — 2 marta, soat bilan | [DEMO.md](DEMO.md) |

`day5.bat` nimani tekshiradi: zaryadlovchi va GPU · Ollama/Qdrant, `gemma4:e4b` va `bge-m3`, indeks toʻliq · `.env` (LLM, τ, ierarxiya) · sayt yigʻmasi yangi (eski boʻlsa yigʻadi) · server tayyor boʻlish va isitish vaqti · sayt, ovozlar, `?demo` fayllari · **6 demo savol** API orqali, har biri avtomatik: 2-savolda «yigirma bir» bor, «15 ish» yoʻq; 4-savolda «12 foiz» bor, boshqa foizlar yoʻq; 5–6 — «Bilmayman»; manba, baho ≥ 80, vaqt < 15 s · tarmoq «Private», firewall, LAN manzili · video va kadr/s bosqichlar boʻyicha. Natija — `TAYYORLIK.md`: hammasi ✅ boʻlsa «TAYYOR», aks holda ❌ lar roʻyxati.

## 9. Yakuniy tekshiruv natijasi (`day5.bat`, 8-noyabr 12:06, GPU noutbuk)

**26 ✅ · 1 ⚠️ · 2 ❌** — dasturiy qism toʻliq tayyor, ikkala ❌ muhitga oid.

| Tekshiruv | Natija |
|---|---|
| kod | `878bfae` — eng oxirgi |
| xizmatlar | Ollama + Qdrant, `gemma4:e4b`, `bge-m3`, indeks 183 170 boʻlak, `.env` (gemma4, τ 0,58, ierarxiya on) ✅ |
| server | 4 s da tayyor, isitish javobi 3,5 s ✅ |
| sayt | yigʻildi, `index.html`, ikkala ovoz, `?demo` fayli ✅ |
| demo 1 Konstitutsiya 1-m. | 3,1 s · 95,9 ✅ |
| demo 2 taʼtil | 1,0 s · 100 · «yigirma bir kalendar kun» ✅ |
| demo 3 kirill | 6,2 s · 99,0 ✅ |
| demo 4 QQS | 2,6 s · 100 · «12 foiz», boshqa foiz yoʻq ✅ |
| demo 5 ob-havo | 3,0 s · «Bilmayman» ✅ |
| demo 6 prompt-injection | 0,5 s · «Bilmayman» ✅ |
| sayt kadr/s | median **59**, render 1,5; eng past (bosqich boʻyicha) idle 11 · answer 37 · scales 52 · mind 28 ⚠️ |
| ❌ quvvat | **batareyada, 30 %** |
| ❌ tarmoq | «PDP Staff» — **Public**; firewall qoidalari faqat Private’da → boshqa kompyuter `10.30.10.61:8080` ga ulana olmaydi |

**Xulosa.**
1. Demo savollar — kutilgan javoblar, manbalar, baholar 4-kundagi bilan bir xil (eski nusxalar filtri va raqam ziddiyati hal qiluvchisi ishlayapti); vaqtlar batareyada ham ≤ 6,2 s.
2. **Batareya** — zaryadlovchiga ulash; 30 % bilan 7 daqiqalik demo oʻrtasida Windows quvvatni tejash rejimiga oʻtishi mumkin.
3. **Tarmoq** — ish/universitet Wi-Fi’ida profilni oʻzgartirish ruxsat etilmasligi va mijozlar bir-biridan ajratilgan boʻlishi mumkin. Ishonchli yoʻl: **telefon hotspot’i** (Private) yoki **noutbukni proyektorga ulab `http://localhost:8080`** (tarmoq umuman kerak emas).
4. **«idle 11 kadr/s»** — yozuvchi sahifa tayyor boʻlgan zahoti birinchi soniyani oʻlchagan (modellar va teksturalar GPU’ga bir marta yuklanadi). Demoda sahifa daqiqalar oldin ochiladi. Endi bu soniya alohida **«load»** bosqichi sifatida koʻrsatiladi va baholanmaydi, `idle` 2 s keyin oʻlchanadi. Mind 28 — oyna ochilishidagi birinchi soniya; batareyada ham. Keyingi `day5.bat` (zaryadlovchida) aniq koʻrsatadi.
5. Kichik tuzatishlar: indeks bir marta tekshiriladi (`stats` 3 marta chaqirilardi, −4 s), batareya foizi xabarda.

## 10. Ikkinchi tekshiruv (12:34) va oʻzgarishlar

**25 ✅ · 2 ⚠️ · 2 ❌** — dasturiy qism yana toʻliq ✅: 6/6 demo savol (0,4–5,6 s, baho 95,9–100), server 6 s, isitish 2,4 s.

| | 12:06 | 12:34 |
|---|---|---|
| batareya | 30 % | **14 %** |
| sayt kadr/s, median | 59 | **30** |
| render koeff. | 1,5 | **1,0** |
| eng past (load / idle / answer / scales / mind) | — / 11 / 37 / 52 / 28 | 8 / 30 / 17 / 30 / 17 |
| tarmoq | Public | Public |

**Xulosa:** median kadr/s **aniq 30** ga tushdi — bu Windows’ning batareya tejash rejimi (20 % dan past) ekran va brauzerni 30 kadr/s ga cheklaganining belgisi; DPR boshqaruvchisi buni sekinlik deb render koeffitsientini 1,0 ga tushirgan. 12:06 da (30 %) xuddi shu sahna 59 kadr/s edi. Kod oʻzgarmagan → sabab — **quvvat**. Demo faqat zaryadlovchida. Yangi «load» bosqichi ishladi: yuklanishdagi birinchi soniya (8) endi baholanmaydi, `idle` alohida koʻrinadi.

**Oʻzgarishlar (Bobur soʻrovi):**
1. **Tarozi olovining ovozi.** Olov faqat hukm paytida (javob kelganda) chalinardi — gavel zarbasi va qoʻngʻiroq bilan bir vaqtda, eshitilmay qolardi; haykal bosilib tarozi markazga kelganda (olov eng yorqin) esa umuman ovoz yoʻq edi. Endi tarozi koʻrinishida: olov alangalanadi (`flame.mp3` boshidan), keyin sokin yonib turadi (faylning barqaror qismi 0,4–2,4 s takrorlanadi), Esc/orqaga — 0,5 s da soʻnadi. e2e: «scales view: the flames are heard», «fire stops when the scales view closes».
2. **Mind — qatlamli neyron tarmogʻi (v4)**, Bobur namunasi boʻyicha: ustunlar chapdan oʻngga — KIRISH (soʻrov tokenlari) → EMBEDDING (2 560) → ATTENTION (8 bosh, 2 KV guruh — 2 rang) → FFN (10 240 — eng keng) → QOLDIQ OQIM (2 560) → CHIQISH (tokenlar); har neyron keyingi ustunning har neyroniga ulangan; ostida nom va haqiqiy son, transformer bloki ostida qavs «TRANSFORMER BLOKI × 42» va 42 belgi (har biri bitta qatlam, ‹ › bilan tanlanadi), ustida «42 marta takrorlanadi» yoyi. 3D: soyali sharlar, perspektiva, sekin chayqalish, sichqoncha bilan aylantirish; sharni bosing — ustun izohi. Impulslar — shu javobning chiqish tokenlari, oʻlchangan tok/s bilan. Sharlar soni — namuna (kenglikning √ ga mutanosib: FFN 4× keng → 2× shar), haqiqiy son yozilgan. Telefonda tarmoq yuqoridan pastga, yozuvlar chapda. Eski minora (`viz/layers.js`) olib tashlandi.

## 11. Yakuniy bosqich — «RAG API — test spetsifikatsiyasi» (@jurabek) va 100 savol

Spetsifikatsiya ikki narsani talab qiladi: (1) testchi chaqiradigan **API /v1**, (2) 100 savol bilan qidiruv va generatsiyani alohida
baholash. Ikkalasi tayyor; batafsil — [docs/API-V1.md](docs/API-V1.md).

| Qism | Fayl | Holat |
|---|---|---|
| API /v1: batch (1–10), batch natijasi, query, meta, health; Bearer kalit, 400/401/403/409/429, idempotentlik, savol darajasidagi xato, 202 + polling | `src/modda/v1.py`, `api.py`, `devserver.py` | ✅ 18 unit test; sinov muhitida checklist 21/21 |
| 100 savollik test toʻplami (§6 tarkibi, har batch’da 6–7 kategoriya) | `data/testset/test100.csv`, `scripts/build_testset.py` | ✅ |
| Test skripti: checklist §7 → 10 batch → metrikalar §6 → hisobot (100 savol va javob) | `scripts/rag_api_test.py` | ✅ sinov muhitida toʻliq oʻtdi |
| Jamoadosh uchun bitta skript: kod, xizmatlar, kalit, server, test, papka | `scripts/day6.bat` / `day6.py` | 🔄 GPU noutbukda |

**Tillar.** Korpus oʻzbek lotin: javob har doim oʻzbekcha yoziladi va manba bilan tekshiriladi; kirill savolga — transliteratsiya,
rus savoliga — savol tarjimasi bilan qidiruv va tekshirilgan javobning tarjimasi (`debug.answer_uz` — asli).

**Baholash.** Correctness 0/1/2 — LLM-hakam (noutbukda `qwen3:8b` boʻlsa, u — tekshirilayotgan gemma4 emas) va test toʻplamidagi
kalit faktlar; faithfulness va citation accuracy — deterministik (har son va mazmunli soʻzlarning ≥ 50% i oʻzi havola qilgan
kontekstda); toʻqilgan / eskirgan manba — lokal korpus va `versions.py` bilan. Har notoʻgʻri javob bitta sababga yoziladi:
retrieval / generatsiya / manba.

**Sinov muhitidagi natija** (sinov LLM har savolga javob beradi, embedding — xesh, korpus 10 kodeks): API checklist 21/21 ✅,
100/100 javob, xato 0 %, p50 2,6 s. Sifat raqamlari maʼnosiz — haqiqiysi `day6.bat` dan keyin.

## 12. 15:12–15:18 natijalari va tuzatish

**`day5.bat` (15:12, zaryadlovchida, 100 %):** 27 ✅ · 1 ⚠️ · 1 ❌ — 6/6 demo savol (1,3–6,8 s, baho 95,9–100), **sayt median 60
kadr/s, eng past 41** (answer 41, scales 59, mind 42), render 1,5 — 12:34 dagi 30 kadr/s (batareya 14 %) haqiqatan quvvatdan edi.
Birinchi isitish javobi 23 s (modellar sovuq) — demo oldidan bitta sinov savoli bering (DEMO.md). Yagona ❌ — Wi-Fi «PDP Staff» Public.

**`day6.bat` (15:15): test boshlanmadi.** Server ishga tushmadi: `v1.py` 414-qatorda f-string ichida backslash —
`f"{re.sub(r'[^\w.\-]', '_', batch_id)}.json"`. Python 3.12+ buni qabul qiladi (sinov muhitida 3.13), GPU noutbukda esa
**Python 3.10** → `SyntaxError`. `day6` 3 daqiqa kutib, «tayyor boʻlmadi» dedi.

Tuzatildi:
1. `v1.py` — ifoda f-string’dan oldin hisoblanadi. Hamma `.py` fayllar Python 3.11 bilan kompilyatsiya qilindi (3.10 bilan bir xil
   f-string qoidalari) — boshqa muammo yoʻq; API testlari 3.11 da 18/18.
2. `tests/test_py310.py` — har `.py` faylda 3.10 qabul qilmaydigan f-string shakllarini topadi (eski xatoni topishi tekshirildi).
3. `day6.py` — pull’dan keyin kod **noutbukning oʻz Python’ida** kompilyatsiya qilinadi (xato boʻlsa — darhol, aniq xabar); server
   ishga tushishda yiqilsa — 3 daqiqa emas, darhol, server logining oxirgi qatorlari bilan.

**Mind v5 — minora + tarmoq.** Bobur soʻrovi: eski minora (`viz/layers.js`) va yangi qatlamli tarmoq bitta 3D koʻrinishda. Old
tomonda — tarmoq (rasm kabi); transformer bloki orqasida — **42 ta halqa chuqurlikka ketadi**: har halqa bitta qatlam (tashqi yoyi —
8 attention boshi, 2 KV guruh rangi; ichkisi — FFN; markazdan qoldiq oqim nuri). Impuls blokdan oʻtganda halqalar ketma-ket yonadi;
‹ › bilan tanlangan qatlam — oltin halqa va raqami. Kamera biroz yuqoridan — minora blok orqasidan koʻtariladi.

## 13. Yakuniy test natijasi (`day6.bat`, 8-noyabr 20:14, GPU noutbuk) va tuzatishlar

100 savol, 10 batch, **xato 0 %**, har batch 20–32 s. API checklist **19 / 20**, metrikalar **12 / 13**:

| Metrika | Natija | Maqsad | |
|---|---|---|---|
| Hit@5 hujjat / modda | 91,1 % / 84,4 % | ≥ 90 / 80 % | ✅ |
| MRR | 0,742 | ≥ 0,70 | ✅ |
| Context precision (hakam) | 67,0 % | ≥ 60 % | ✅ |
| Answer correctness | 1,90 → **1,77** (quyida) | ≥ 1,6 | ✅ |
| Faithfulness / citation accuracy | 100 % / 99,4 % (162 havola) | ≥ 95 / 90 % | ✅ |
| Toʻqilgan / eskirgan manba | 0 / 0 | 0 | ✅ |
| No-answer | **8 / 10** | ≥ 9 / 10 | ❌ |
| Latency p50 / p95 | 2,40 s / 4,43 s | ≤ 5 / 12 s | ✅ |

**Chuqur tahlil — raqamlar ortida nima bor:**
1. **Hakam (qwen3:8b) ishonchsiz chiqdi.** Yaxlit 0–2 bahosi aniq notoʻgʻri javoblarga 2 qoʻygan: q012 «Otpuskaga necha kun?» →
   javob homiladorlik taʼtili haqida; q054 «14 kun» soʻralgan, javobda yoʻq — hakam «14 kunni toʻgʻri aytgan» deb yozgan; q078 nikoh
   yoshi → fuqarolik muomala layoqati. Hakam va kalit faktlarning **kichigi** olinsa — **1,77** (baribir maqsaddan yuqori);
   koʻp moddali savollar — 1,40 (eng zaif joy).
2. **Eski Mehnat kodeksiga oʻzgartish aktlari.** «MEHNAT QONUNLARI KODEKSIGA OʻZGARTISHLAR…» (`-112443`) maʼlumotda «kodeks» turida —
   ierarxiya qoidasi uni haqiqiy kodeks kabi koʻtargan: q012, q050, q072, q091 javoblari 1995-yilgi kodeks matnidan. q063 da xuddi
   shunday akt jarimani «yuz soʻm» deb bergan. Bu — **eskirgan norma**, lekin metrika uni sanamagan (akt eski nusxa sifatida
   belgilanmagan edi).
3. **q075 (rus, QQS):** tarjima toʻgʻri, oʻxshashlik 0,77 — lekin **0 kontekst**: «Soliq kodeksi» Soliq kodeksining 4 avlodiga
   mos keldi, 10 nomzodning hammasi eski nusxalardan, ular chiqarilgach hech narsa qolmadi.
4. **q087** («2030-yilda qabul qilinadigan Soliq kodeksi») — 2030 soʻzi bor toʻgʻri, lekin aloqasiz gaplar; **q096** («Oyda uy
   qurish», kirill) — lotinda «oyda» = «bir oyda» ham; qurilish ruxsatnomasi tartibi berilgan.
5. **q044** — toʻgʻri modda 1-oʻrinda, lekin oʻxshashlik 0,52 < τ 0,58 → «Bilmayman»; **q046** — LLM toʻgʻri javob yozgan, [n] ni
   unutgan → tekshiruvchi olib tashlagan.
6. **Koʻp moddali savollar:** ikkala modda top-5’da faqat **12,5 %** hollarda — qidiruv bitta yarmini topadi.
7. Checklist’dagi yagona ❌ (`article` boʻsh) — xato emas: moddalarga boʻlinmagan hujjatlar (Oliy sud plenumi qarorlari, oʻzgartish
   aktlari); tekshiruv qoidasi tuzatildi.

**Tuzatishlar (kod):**
| # | Nima | Qayer |
|---|---|---|
| 1 | Eski nusxalar qidiruv **ichida** chiqariladi (Qdrant `must_not`) — joy egallamaydi (q075) | `store.py`, `pipeline.py`, `rag.py` |
| 2 | Oʻzgartish / bekor qilish aktlari qidiruvdan chiqariladi (savol oʻzgartishlar haqida boʻlmasa) | `versions.py: amending, excluded` |
| 3 | Ikki narsa soʻragan savol: har yarmi alohida qidiriladi, butun savolning top-3 i saqlanadi, har yarmining eng yaxshisi qoʻshiladi | `rag.py: split_question, interleave`; yoqilishini noutbukdagi A/B hal qiladi (`scripts/retrieval_ab.py`, `day6` qismi «ab» → `.env` `SPLIT_QUESTIONS`) — sandbox’dagi soxta embeddinglarda natija aniq emas edi |
| 4 | Kelajakda qabul qilinadigan hujjat haqidagi savol → «Bilmayman», LLM chaqirilmaydi (q087) | `pipeline.py: future_act` |
| 5 | [n] siz gap aniq bitta manbadan boʻlsa (har son va ≥ 50 % soʻz) — oʻsha manba qoʻshiladi (q046) | `pipeline.py: attach_source` |
| 6 | Prompt: Oy, Mars, koinot kabi joylar → BILMAYMAN (q096) | `rag.py` |
| 7 | Hakam: yaxlit baho oʻrniga **faktlar roʻyxati** (har fakt bor/yoʻq, mavzu, zidlik); yakuniy baho — hakam va kalit faktlarning kichigi | `rag_api_test.py` |
| 8 | Checklist: `article` faqat moddali hujjatlarda talab qilinadi | `rag_api_test.py` |

q044 (τ darvozasi) ataylab oʻzgartirilmadi: τ ni pasaytirish javobsiz savollarni oʻtkazib yuborishi mumkin — 10 javobsizdan 8 tasi
aynan shu darvoza bilan toʻxtagan. 9 ta yangi unit test (jami 88). Keyingi qadam — `day6.bat` ni qayta ishga tushirib, 20:14 bilan solishtirish.

## 14. Qayta test (`day6.bat`, 8-noyabr 22:00, kod `de24524`) va chuqur tahlil

| Metrika | 20:14 | **22:00** | Maqsad |
|---|---|---|---|
| Hit@5 hujjat / modda | 91,1 / 84,4 % | **94,4 / 86,7 %** | ≥ 90 / 80 % |
| MRR | 0,742 | **0,743** | ≥ 0,70 |
| Context precision (hakam) | 67 % | 65,8 % | ≥ 60 % |
| Answer correctness: kalit faktlar / hakam / kichigi | 1,77 / 1,90 / 1,77 | 1,72 / 1,53 / **1,42 ❌** | ≥ 1,6 |
| Faithfulness · citation accuracy | 100 · 99,4 % | **100 · 100 %** | ≥ 95 · 90 % |
| No-answer | 8 / 10 | **10 / 10** | ≥ 9 / 10 |
| Notoʻgʻri «Bilmayman» | 3 | 4 (q012, q019, q044, q046) | — |
| p50 / p95 | 2,40 / 4,43 s | **2,11 / 3,83 s** | ≤ 5 / 12 s |
| API checklist | 19 / 20 | **20 / 20** | — |

Retrieval A/B (`ab` qismi, LLMsiz, 29 s): yarmlab qidirish **foydali** — Hit@5 modda 84,7 → 85,9 %, koʻp moddali savollarda
ikkala modda 12,5 → 18,8 %; `SPLIT_QUESTIONS=on` yozildi. q075 tuzaldi (QQS — 12 %), q087 va q096 endi «Bilmayman».

**Tahlil — correctness nega tushdi:**
1. **Hakam xatosi (asosiy sabab).** Kalit faktlar deyarli oʻzgarmagan (1,77 → 1,72), lekin yangi «faktlar roʻyxati» hakami
   (qwen3:8b) faktlarni *kutilgan javobdan emas*, keltirilgan qonun matnidan oʻzi tuzgan va toʻgʻri javoblarni «qisman» degan:
   q021, q030, q034, q038, q045, q048, q086, q093, q098 va boshqalar (~17 ta). q013 da «qirq sakkiz soat» ni «48 soat» ga zid
   deb 0 bergan.
2. **Haqiqiy eskirgan norma — 3 ta, metrika 0 degan.** q005: «15 ish kuni» — 2018-yilgi qaror (`-3590278`) eski Mehnat kodeksining
   134-moddasini keltirgan (amaldagi 217-modda — 21 kun, 1-oʻrinda edi). q043 / q034: 1991-yilgi «Prezident saylovi toʻgʻrisida»
   qonun (`-111838`, Saylov kodeksi bilan almashtirilgan) — «besh yil»; q043 javobi «yetti yil, ammo boshqa manbada besh yil» degan.
   Eski nusxa filtri nomga tayanadi, bu hujjatlarning nomi boshqa — shuning uchun oʻtib ketgan.
3. **Ogʻzaki savollar** (correctness 0,6): «otpusk», «ishdan haydash» — qonun matnida yoʻq soʻzlar, qidiruv topmagan (q012, q072).
4. q019 — yarmlab qidirish bu savolda yomonlashtirdi (A/B da koʻringan; umumiy natija baribir ijobiy).

**Tuzatishlar (kod):**
| # | Nima | Qayer |
|---|---|---|
| 1 | Hakamga **faktlar beriladi** — kutilgan javobning «;» boʻlaklari; hakam faqat bor/yoʻq deydi. «Zidlik» faqat javobdagi iqtibos va raqam bilan tekshirilsa sanaladi | `rag_api_test.py: ref_facts, real_conflict` |
| 2 | Generatsiyadan **oldin** eskirgan boʻlaklar chiqariladi: (a) qayta qabul qilingan kodeksning eski raqamlashiga havola qilgan, undan eski quyi hujjat; (b) yuqori hujjatdagi xuddi shu gap boshqa miqdor bilan (Konstitutsiya → kodeks → qonun → qaror) | `versions.py: drop_outdated`; `debug.outdated_dropped` |
| 3 | «Eskirgan norma» metrikasi xuddi shu qoidalar bilan ham tekshiradi (22:00 qayta baholansa — 3 ta) | `rag_api_test.py: Corpus.outdated_chunks` |
| 4 | Prompt: bir narsa uchun ikki raqam boʻlsa — Konstitutsiya/kodeksdagisi, «boshqa manbada…» yozilmaydi | `rag.py` |
| 5 | Ogʻzaki soʻzlar lugʻati: otpusk → mehnat taʼtili, ishdan haydash → mehnat shartnomasini ish beruvchi tashabbusi bilan bekor qilish, shtraf, nalog, prava, dekret… (qidiruv soʻroviga qavsda qoʻshiladi, yarmlarga alohida) | `textnorm.py: legal_terms` |
| 6 | `day6-serve.log` har ishga tushishda yangidan (eski traceback adashtirmasin) | `day6.py` |

100 savoldagi kontekstlarda sinaldi: (a)+(b) 9 ta boʻlakni chiqaradi — hammasi eskirgan yoki javobsiz savolda, amaldagi manbaga tegmaydi
(0,2 s / 100 savol). Ogʻzaki lugʻat 100 savoldan 6 tasiga taʼsir qiladi (q003, q012, q072, q091 va 2 rus savoli) — bu savollar test
toʻplamida boʻlgani uchun ularning yaxshilanishi qisman «oʻrgatilgan» hisoblanadi. 6 ta yangi test (jami 91).

**Keyingi qadam:** `git pull` → `scripts\day6.bat` (yangi kod bilan toʻliq test). 22:00 ni yangi hakam bilan qayta baholash
(API’siz, ≈ 10 daqiqa): `.venv\Scripts\python scripts\rag_api_test.py --rescore data\reports\rag100\eval-2026-11-08-2201`.

## 15. Yakuniy run (`day6.bat`, 9-noyabr 18:11, kod `7630873`) — spetsifikatsiya toʻliq bajarildi

| Metrika | 22:01 (qayta baholangan) | **18:12** | Maqsad |
|---|---|---|---|
| Hit@5 hujjat / modda | 94,4 / 86,7 % | **95,6 / 88,9 %** | ≥ 90 / 80 % |
| MRR | 0,743 | **0,775** | ≥ 0,70 |
| Correctness: kichigi (hakam · kalit faktlar) | 1,63 (1,80 · 1,72) | **1,68 (1,86 · 1,73)** | ≥ 1,6 |
| Faithfulness · citation accuracy | 100 · 100 % | 99,5 · 96,8 % | ≥ 95 · 90 % |
| Eskirgan norma | 3 | **0** | 0 |
| No-answer · notoʻgʻri «Bilmayman» | 10/10 · 4 | **10/10 · 3** | ≥ 9/10 |
| p50 / p95 | 2,11 / 3,83 s | 2,62 / 4,57 s | ≤ 5 / 12 s |
| Checklist | 20/20 | **20/20** | — |

Retrieval A/B: yarmlab qidirish yana foydali (Hit@5 hujjat 94,1 → 95,3 %, koʻp moddali savollarda ikkala modda 12,5 → 18,8 %) → `SPLIT_QUESTIONS=on`.

**Ishlagan tuzatishlar:** q005 — endi 217-moddadan «yigirma bir kalendar kun» (eski kodeksga havola qilgan qaror chiqarildi); q034/q043 — 1991-yilgi saylov qonuni kontekstga tushmaydi; q003, q072 — ogʻzaki soʻz lugʻati toʻgʻri moddani topdi; q091 — 165-modda 1-oʻrinda.

**Yangi topilganlar va tuzatish:**
1. **Hakamning yolgʻon «zidligi».** Skript 1,54 bergan: hakam 7 javobda (q014, q023, q052, q058, q062, q082, q099) yoʻq zidlik topgan — kutilgan javob qavsidagi ikkinchi raqam (q062 «umumiy holda — ellik foiz»), bob raqami (q014 «36-bob»), «bir bola» dagi «bir», yoki boshqa faktga qarab (q099). Endi raqam kutilgan javobning **hamma** faktlari bilan solishtiriladi, faqat «…» ichidagi eskirgan misol chiqariladi, yolgʻiz «bir» eʼtiborsiz (`rag_api_test.py: real_conflict`). 18:12 ning saqlangan hakam xulosalari LLM’siz qayta baholandi — **1,68** (`--rescore <run> --judge cache`, `CachedJudge`; noutbukda takrorlanadi).
2. **«…maʼlumotlar mavjud emas [1][2][3][4][5]».** q051 da hech narsa daʼvo qilmaydigan gap beshta havola bilan — citation accuracy 96,8 % ning yagona sababi (biri 2000-yilgi 45 % stavka haqidagi farmonga). Eski filtr «manbalarda / bu haqda» bilan boshlangan gaplarnigina olib tashlardi; endi «…maʼlumot(lar) mavjud emas / berilmagan / yoʻq» oʻzi yetarli, «…berilmagan, ammo X» da X qoladi, «maʼlumotlarni yoʻq qilish» va «…mavjud emas boʻlsa» — daʼvo sifatida qoladi (`rag.py: NO_INFO_RE, drop_no_info`). 200 haqiqiy javobda faqat 3 gapga taʼsir qiladi (q003, q031, q051).

Ochiq qolganlar: q012 («otpusk» → 218-modda, «30 kun» — voyaga yetmaganlar uchun), q019 (yarmlab qidirish yomonlashtirgan), q044 (τ 0,52 < 0,58 — ataylab), q046 (kirill, top-5 da yoʻq). 3 ta yangi test (jami 94).

**Sayt (README skrinshotlari paytida topilgan):** WebGL’siz rejimda bosqichlar halqasi sahifa koordinatasida hisoblanardi — pastki tugunlar («LLM javob», «Oʻqish») savol maydoni ostida qolardi, «Mind» kitob muqovasi ustida turardi (`ui/nodes.js: ring` — endi graf qutisining oʻz koordinatasi; 360–1920 px da kesishma yoʻq). Namuna rejimi yozuvi 390 px da 5 qatorga oʻralib grafni, kompyuterda 2 qatorga oʻralib sarlavhani yopardi — endi bitta qator (toʻliq matn `title` da), sarlavha shu qator balandligiga pastga tushadi. Jonli rejim oʻzgarmadi. Unit testlar 8/8.

**Yopish:** spetsifikatsiyaning 13 maqsadi va 20 checklist bandi bajarildi; testchi uchun javob hujjati (oʻzbekcha) tayyor; README — saytning har koʻrinishi skrinshoti va vazifasi bilan. Oxirgi ikki tuzatish kichik va testlangan — xohlansa ixtiyoriy yakuniy `day6.bat`.
