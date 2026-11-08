# frontend_idea — qoidalar (Modda sayti)

Qisqa qoidalar: shu papkada ishlaydigan har kim (odam yoki AI) uchun. Batafsil konsepsiya — `../frontend_idea.md`, qarorlar — `README.md`.

## Rostgoʻylik (eng muhim)
- Sahifadagi **har bir raqam backend’dan** keladi (`/ask/stream` hodisalari, `/ask/{id}/embedding`, `/model/info`). Kelmagan maʼlumot — «Mavjud emas», oʻylab topilmaydi.
- Neyron **faollashuvlari, attention vaznlari chizilmaydi** — Ollama ularni bermaydi. Mind tarmogʻida (`viz/network.js` + orqasidagi qatlamlar minorasi `viz/layers.js`) faqat haqiqiy sanoqlar: qatlamlar, attention boshlari, KV guruhlari, FFN kengligi, kirish/chiqish tokenlari, token/s. Impulslar — chiqish tokenlarining *qayta oʻynalishi* (son va tezlik oʻlchangan), yorugʻlik — oʻlchov emas.
- PCA — «hosila proeksiya»: bitta tekis masshtab, buzish (fisheye va h.k.) yoʻq.
- `?demo` (namuna rejimi) haqiqiy rejimga hech qachon aralashmaydi va banner bilan koʻrinadi.

## Tuzilma
- `src/scene/` — bosh sahifa 3D sahnasi (kitob, haykal, bolgʻacha, graf). Haykal, kitob, bolgʻacha — Bobur tasdiqlagan, **ruxsatsiz oʻzgartirilmaydi**.
- `src/viz/` — inspektor oynalaridagi vizualizatsiyalar. Umumiy dvigatel `mini3d.js` (HDR, ACES, bloom, avto-aylanish), qurilish bloklari `fx.js` (yorqin nuqtalar, oqimli chiziqlar, matn yorliqlari).
- `src/audio/sfx.js` — ovozlar (birinchi bosishdan keyin; karnay tugmasi bilan oʻchadi). Sahnalar ovozni `onSound` / `onImpact` orqali soʻraydi, oʻzi chalmaydi.
- `src/ui/` — panellar, inspektorlar, Mind oynasi. `src/core/` — holat mashinasi (animatsiyadan mustaqil).
- `web/` (eski sayt) va backend’ning mavjud javoblari — **tegilmaydi**; backend’ga faqat yangi maydon/endpoint, Bobur ruxsati bilan.

## Sifat
- `?quality=low` yoki `prefers-reduced-motion`: bloom va avto-aylanish yoʻq, impulslar oʻchadi; funksiya qoladi.
- WebGL yoʻq boʻlsa — `body.no-webgl`: 2D issiqlik xaritasi, oddiy graf, toʻliq javob.
- Har bir `mini3d` koʻrinishi panel yopilganda `dispose()` qilinadi (`panel.onCleanup`).
- Global `svg { 1em }` qoidasi bor — diagramma SVG’lariga oʻz oʻlchamini bering (`svg.rankflow`).

## Tekshirish
- `npm test` (unit), `node tests/e2e.mjs http://localhost:8080 out/` (brauzer, ≈ 45 tekshiruv), `npm run build`.
- Vizual oʻzgarishdan keyin: skrinshot (1440×900 va 390×844), konsol toza.
