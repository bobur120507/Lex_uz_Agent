# Modda — baholash hisoboti

Yaratildi: 2026-11-08 09:43. Hamma raqamlar `data/reports` dagi oʻlchov fayllaridan olingan.

## Muhit

* GPU: NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, driver 621.14
* Baza: 54,173 modda, 183,170 boʻlak, dense indeks 183,170
* Qdrant nuqtalari: 183170

## 1. Qidiruv sifati (oltin toʻplam)

| Usul | Recall@5 | MRR | p50 kechikish |
|---|---|---|---|
| dense | 0.822 | 0.684 | — |
| sparse | 0.778 | 0.605 | — |
| hybrid | 0.911 | 0.778 | — |
| hybrid_auth | 0.911 | 0.819 | — |

Gibrid (dense + BM25, RRF) — standart rejim; bir aktning eski nusxalari (masalan 1995 yilgi Mehnat kodeksi) qidiruvdan chiqariladi. `hybrid_auth` — qoʻshimcha ravishda Konstitutsiya/kodeks/qonun boʻlaklari bir necha oʻrin yuqoriga suriladi (`AUTHORITY_PRIOR=on`).

## 2. LLM solishtiruvi (bakeoff)


Savollar: 20, kontekst: top-5 (dense)

| Model | Toʻgʻri manba (javobi bor) | Toʻgʻri «Bilmayman» (javobi yoʻq) | Yolgʻon javob | Kirill harflar | Oʻrtacha vaqt, s | Xato | Kesilgan |
|---|---|---|---|---|---|---|---|
| `gemma4:e4b` | 12/15 | 5/5 | 0 | 0 | 2.8 | 0 | 0 |
| `qwen3:8b` | 12/15 | 4/5 | 1 | 0 | 5.9 | 0 | 1 |

LLM «fikrlash» (think) oʻchirilgan; *Kesilgan* — javob token chegarasiga yetgan savollar.

**Tanlash qoidasi:** avval eng kam *yolgʻon javob*, keyin eng koʻp *toʻgʻri manba*, keyin tezlik.
Javoblarni CSV faylida koʻzdan kechiring: oʻzbek tili sifati raqamlarda koʻrinmaydi.

## 3. «Bilmayman» chegarasi (τ)

Savol vektori bilan eng yaqin boʻlak oʻrtasidagi kosinus oʻxshashlik. Javobi bor savollar: 45 ta (min 0.523, median 0.703); javobi yoʻq: 35 ta (median 0.569, max 0.696).

**DENSE_TAU=0.58 — javobi bor savollarning 98% i oʻtadi, javobi yoʻqlarning 54% i LLM’siz «Bilmayman» oladi**

## 4. Demo savollar

| # | Tur | Vaqt, s | Natija | Manbalar | Baho | LLM, token/s |
|---|---|---|---|---|---|---|
| 1 | aniq modda | 26.8 | 2 gap | OʻZBEKISTON RESPUBLIKASI KONSTITUTSIYASI 1 | 95.9 | 104.97 |
| 2 | mehnat mavzusi | 5.2 | 1 gap | Oʻzbekiston Respublikasining Mehnat kode 217 | 100.0 | 93.91 |
| 3 | kirill | 5.3 | 2 gap | Oʻzbekiston Respublikasining Mehnat kode 161 | 98.5 | 103.65 |
| 4 | yangilangan hujjat | 2.0 | 1 gap | Oʻzbekiston Respublikasining Soliq kodek 258 | 100.0 | 94.86 |
| 5 | javobi yoʻq | 2.1 | Bilmayman | — | — | 95.92 |
| 6 | prompt-injection | 0.3 | Bilmayman | — | — | — |

Savollar va kutilgan natijalar: `scripts/demo_questions.py`.

## Cheklovlar

* Tarozi bahosi — soʻz mosligi (`lexical-support-v1`): javob manba matniga qanchalik yaqin, yuridik xulosa emas.
* Korpus — Hugging Face’dagi Lex.uz nusxasi (qatʼiy versiya); undan keyingi oʻzgarishlar RSS orqali faqat belgilanadi.
* Bu tizim yuridik maslahat bermaydi; rasmiy matn — lex.uz.

> **Izoh (8-noyabr, qoʻlda):** GPU noutbuk, kod `3e29a55`. 1-savolning 26,8 s i — modellarni GPU’ga yuklash vaqti (demo skripti har safar ataylab tushirib qoʻyadi); ishlayotgan serverda modellar oldindan isitiladi — xuddi shu savol videoda **1,5 s** da javob oldi. `versions`: bir xil nomli 70 ta eski hujjat (4 296 boʻlak) qidiruvdan chiqarilgan; `hybrid_auth` (Konstitutsiya/kodeks/qonun bir necha oʻrin yuqoriga) MRR’ni **0,778 → 0,819** ga koʻtardi, Recall@5 oʻzgarmadi → `AUTHORITY_PRIOR=on`.
