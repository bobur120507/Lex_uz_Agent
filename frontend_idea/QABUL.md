# Qabul mezonlari — `frontend_idea.md` §21 (8-noyabr)

Har bir mezon — holat va dalil. **v2 qarorlari** (Bobur, `frontend_idea.md` §0) ayrim mezonlarni oʻzgartirgan: 7 → **8 bosqich**, yon panellar → **inspektor oynalari va kitob**. Dalillar: `tests/e2e.mjs` (Playwright, ≈ 45 tekshiruv, sinov muhitida: haqiqiy backend kodi + Qdrant 1.20 + 10 kodeks + sinov LLM), skrinshotlar, GPU noutbukdagi oʻlchovlar (`KUN-4.md`).

Belgilar: ✅ bajarildi · ⚠️ izoh bilan · ❌ yoʻq.

## Vizual (9)

| Mezon | Holat | Dalil |
|---|---|---|
| Qorongʻi huquqiy kutubxona uslubi namunaga mos | ✅ | `reference/` bilan solishtirma skrinshotlar (F7, 2 aylana) |
| Modda brendingi izchil | ✅ | logotip, «Javob qonundan — isbot manbadan», oltin/zumrad palitra |
| Kitob — taniladigan jismoniy 3D | ✅ | muqova, gerb, sahifa qirralari, varaqlash; teksturalar 2048 px |
| Markaziy graf taassurotli | ✅ | v3: shader neyronlar, sinapslar, soʻrov vaqtida uchqunlar, oqimli boʻgʻinlar |
| Bosqichlar aniq koʻrinadi | ✅ | **8** bosqich (v2), har biri raqam, nom, vaqt bilan |
| Panellar ierarxiyasi | ✅ | v2: yon panellar yoʻq — inspektor oynalari (sarlavha → teglar → 3D → jadval) |
| Hamma matn oʻqiladi | ✅ | e2e: matnlar mavjud; kontrast tokenlari (WCAG AA) |
| 1600 × 900 da ustma-ust tushish yoʻq | ✅ | 8-noyabr: sarlavha ostidagi jumla «02/03» tugun belgilariga tegardi → sarlavha oʻlchami ekran balandligiga bogʻlandi (`--fs-hero`), qayta tekshirildi |
| 390 px da moslashuvchan | ✅ | e2e: 390×844, 360×780 — gorizontal aylantirish yoʻq, konsol toza |

## Funksional (13)

| Mezon | Holat | Dalil |
|---|---|---|
| Savol yuborish | ✅ | e2e: boʻsh savol yuborilmaydi, ishlayotganda tugma oʻchiq |
| Haqiqiy SSE hodisalari bosqichlarni yangilaydi | ✅ | e2e: «every stage has a final status» |
| Bosqich tugunlari bosiladi | ✅ | e2e: 8 inspektor ochiladi |
| Topilgan hujjatlar bosiladi | ✅ | v2: kitob manba sahifasi (±5 modda), inspektorlardagi havolalar → «Kitobda ochish»; «Hujjatlar» roʻyxati |
| Markaziy model tuguni model inspektorini ochadi | ✅ | e2e: Mind — haqiqiy qatlam soni; LLM ↔ Embedding |
| Embedding inspektori haqiqiy maʼlumotni koʻrsatadi | ✅ | 1024 qiymat (3D ustunlar + roʻyxat + JSON), PCA — haqiqiy proeksiya |
| Graf kamerasi boshqaruvi | ⚠️ | bosh sahifa kamerasi ataylab belgilangan (kitob/haykal kompozitsiyasi); aylantirish/zoom/«Kamera» qaytarish — inspektorlarning 3D koʻrinishlarida |
| Javob `/ask` natijasini koʻrsatadi | ✅ | kitob chap sahifasi, [n] havolalar, tasdiqlangan gaplargina |
| Manba havolalari haqiqiy lex.uz hujjatiga | ✅ | `source_url` = `https://lex.uz/docs/<id>`; 20 tasodifiy modda tekshirildi (`docs/MALUMOT-SIFATI.md`) |
| Inspektordan qaytish | ✅ | e2e: Esc, ✕ |
| Yangi savol eski maʼlumotni tozalaydi | ✅ | holat mashinasi (unit testlar), «logo returns home» |
| Xato va «Bilmayman» holatlari | ✅ | e2e + demo 5/6-savollar (GPU noutbuk) |
| SSE zaxirasi | ✅ | `/ask` zaxirasi (F3), unit test |

## Texnik (10)

| Mezon | Holat | Dalil |
|---|---|---|
| Texnik qiymatlar oʻylab topilmagan | ✅ | hamma raqam backend’dan; kelmagani — «Mavjud emas» |
| Huquqiy manbalar oʻylab topilmagan | ✅ | iqtibos tekshiruvchi; manbasiz gap koʻrsatilmaydi |
| Embedding aniq 1024 oʻlchamli | ✅ | inspektor: `1024 × float32` |
| 3D proeksiya haqiqiy embedding’lardan | ✅ | versiyali PCA (`pca3-…`), 2 000 nuqtali namuna, dispersiya koʻrsatiladi |
| Neyron faollashuvlari faqat instrumentatsiya bersa | ✅ | Ollama bermaydi → chizilmaydi; Mind impulslari — chiqish tokenlari (son, token/s oʻlchangan), oynada yozilgan |
| WebGL’siz rejim | ✅ | e2e: `no-webgl` — oddiy graf, 2D issiqlik xaritasi, toʻliq javob |
| Qisqartirilgan harakat | ✅ | `prefers-reduced-motion`: zarralar, bloom, avto-aylanish oʻchadi |
| Graf resurslari soʻrovlar orasida tozalanadi | ✅ | har `mini3d` koʻrinish panel yopilganda `dispose()`; panel ochiqligida asosiy sahna ¼ tezlikda |
| Konsolda jiddiy xato yoʻq | ✅ | e2e: desktop, 5 oʻlcham, WebGL’siz — konsol toza |
| Unumdorlik | ⚠️ | RTX 4060 (demo kompyuteri): median **60**, eng past **53** kadr/s ✅; Intel Iris Xe: 27 — shuning uchun demo GPU noutbukda |

**Natija:** 32 mezondan 30 tasi ✅, 2 tasi ⚠️ (izoh bilan), ❌ yoʻq.
