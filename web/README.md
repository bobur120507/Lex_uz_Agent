# Modda — Three.js sayt («qidiruvchi kitob»)

Savol yuborilganda 3D kitob ochiladi, varaqlari tez aylanib qidiradi, topilgan moddalar xatchoʻp kabi chiqadi, eng yaxshisi yonadi va kitob aynan oʻsha moddaning sahifasida ochiladi. Yonidan HTML javob paneli chiqadi.

## Ishga tushirish

```bash
cd web
npm install
npm run dev          # http://localhost:5173
```

| Manzil | Nima |
|---|---|
| `http://localhost:5173` | Oddiy rejim (server boʻlmasa — namuna maʼlumotlar) |
| `?debug` | Burchakda kadr/s (1-kun sinovi uchun) |
| `?demo` | Serverni tekshirmasdan namuna rejimi |
| `?q=Taʼtil haqi qachon toʻlanadi?` | Savolni darhol yuborish |
| `?flat` | 3D’siz zaxira rejim |

Namuna savollar: «Oʻquv taʼtili necha kun beriladi?» (javob), «Taʼtil haqi qachon toʻlanadi?» (eskirgan manba ogohlantirishi), boshqa istalgan savol («Bilmayman»).

## 1-kun sinovi: qaror mezoni

`?debug` bilan oching, savol yuboring va varaqlash paytida kadr/s ni kuzating:

* **≥ 45** — reja boʻyicha davom etamiz.
* **< 45** — `src/scene/book.js` da `SEG` ni 28 → 14 ga, `POOL` ni 8 → 5 ga tushiring; `stage.js` da soyalarni oʻchiring (`shadowMap.enabled = false`).

## Tuzilma

| Fayl | Vazifasi |
|---|---|
| `src/main.js` | Holatlar: kutish → qidiruv → javob / Bilmayman / xato |
| `src/scene/stage.js` | Renderer, kamera kadrlari, chiroq yorugʻligi, stol, chang |
| `src/scene/book.js` | Kitob: muqovalar, sahifa toʻplamlari, egiladigan varaqlar, varaqlash, kerakli sahifaga ochilish |
| `src/scene/textures.js` | Toʻq koʻk muqova (oltin hoshiya, gerb), qogʻoz, modda matni yozilgan sahifa (iqtibos yashil) |
| `public/gerb.png` | Oʻzbekiston Respublikasi Davlat gerbi (muqova uchun) |
| `src/scene/emblem.js` | Gerbning oltin chiziqli varianti — `gerb.png` yuklanmasa ishlatiladi |
| `src/api.js` | `POST /ask/stream` (SSE) → `POST /ask` → namuna maʼlumot |
| `src/mock.js` | Namuna hodisalar oqimi (server bilan bir xil shakl) |
| `src/ui/answer.js` | Javob paneli, manba kartalari |

## Server bilan shartnoma

`POST /ask/stream`, javob `text/event-stream`:

```
event: stage       data: {"name": "retrieving"}
event: candidates  data: [{"chunk_id": "...", "title": "...", "article_no": "131", "article_title": "...", "score": 0.82}]
event: stage       data: {"name": "generating"}
event: reranked    data: {"order": ["chunk_id_1", "chunk_id_2"]}
event: stage       data: {"name": "verifying"}
event: answer      data: {"unknown": false, "checked_at": "2026-11-01", "answer": [...], "sources": {...}}
```

`answer` hodisasining shakli — `POST /ask` javobi bilan bir xil: `answer[]` ichida `{text, chunk_ids, quote}`, `sources` ichida `{title, doc_type, doc_number, adoption_date, url, article_no, article_title, text, amendment_note, stale}`. `src/mock.js` da toʻliq namuna bor.

Ishlab chiqishda Vite `/ask` va `/health` ni `http://localhost:8080` ga uzatadi (`vite.config.js`).
