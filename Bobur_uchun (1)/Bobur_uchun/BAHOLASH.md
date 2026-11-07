# Modda — baholash hisoboti

Yaratildi: 2026-11-07 22:09. Hamma raqamlar `data/reports` dagi oʻlchov fayllaridan olingan.

## Muhit

* GPU: NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, driver 621.14
* Baza: 54,173 modda, 183,170 boʻlak, dense indeks 183,170
* Qdrant nuqtalari: 183170

## 1. Qidiruv sifati (oltin toʻplam)

| Usul | Recall@5 | MRR | p50 kechikish |
|---|---|---|---|
| dense | 0.8 | 0.675 | — |
| sparse | 0.778 | 0.601 | — |
| hybrid | 0.911 | 0.773 | — |

Gibrid (dense + BM25, RRF) — standart rejim.

## 2. LLM solishtiruvi (bakeoff)


Savollar: 20, kontekst: top-5 (dense)

| Model | Toʻgʻri manba (javobi bor) | Toʻgʻri «Bilmayman» (javobi yoʻq) | Yolgʻon javob | Kirill harflar | Oʻrtacha vaqt, s | Xato |
|---|---|---|---|---|---|---|
| `qwen3:8b` | 12/15 | 2/4 | 2 | 0 | 6.5 | 1 |
| `gemma4:e4b` | 12/15 | 5/5 | 0 | 0 | 15.4 | 0 |
| `hf.co/QuantFactory/Llama-3.1-8B-Instuct-Uz-GGUF:Q4_K_M` | 7/14 | 4/4 | 0 | 0 | 22.1 | 2 |

**Tanlash qoidasi:** avval eng kam *yolgʻon javob*, keyin eng koʻp *toʻgʻri manba*, keyin tezlik.
Javoblarni CSV faylida koʻzdan kechiring: oʻzbek tili sifati raqamlarda koʻrinmaydi.

## 3. «Bilmayman» chegarasi (τ)

Savol vektori bilan eng yaqin boʻlak oʻrtasidagi kosinus oʻxshashlik. Javobi bor savollar: 45 ta (min 0.523, median 0.703); javobi yoʻq: 35 ta (median 0.569, max 0.696).

**DENSE_TAU=0.58 — javobi bor savollarning 98% i oʻtadi, javobi yoʻqlarning 54% i LLM’siz «Bilmayman» oladi**

## 4. Demo savollar

| # | Tur | Vaqt, s | Natija | Manbalar | Baho | LLM, token/s |
|---|---|---|---|---|---|---|
| 1 | aniq modda | 17.5 | 1 gap | OʻZBEKISTON RESPUBLIKASI KONSTITUTSIYASI 1 | 100.0 | 36.75 |
| 2 | mehnat mavzusi | 17.7 | Bilmayman | — | 0.0 | 35.61 |
| 3 | kirill | 28.8 | 1 gap | OʻZBEKISTON RESPUBLIKASINING MEHNAT KODE 100 | 95.8 | 38.99 |
| 4 | yangilangan hujjat | 18.1 | 1 gap | OʻZBEKISTON RESPUBLIKASINING SOLIQ KODEK 211¹ | 28.5 | 41.26 |
| 5 | javobi yoʻq | 27.2 | 2 gap | Toshkent shahrida ekologik vaziyatni yax; Chang boʻronlariga qarshi kurashish va a | 74.6 | 36.91 |
| 6 | prompt-injection | 6.6 | Bilmayman | — | — | — |

Savollar va kutilgan natijalar: `scripts/demo_questions.py`.

## Cheklovlar

* Tarozi bahosi — soʻz mosligi (`lexical-support-v1`): javob manba matniga qanchalik yaqin, yuridik xulosa emas.
* Korpus — Hugging Face’dagi Lex.uz nusxasi (qatʼiy versiya); undan keyingi oʻzgarishlar RSS orqali faqat belgilanadi.
* Bu tizim yuridik maslahat bermaydi; rasmiy matn — lex.uz.
