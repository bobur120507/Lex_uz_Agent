# MODDA — LEGAL INTELLIGENCE GRAPH
## Complete Frontend Design & Engineering Specification

**Document type:** Product Design Specification + Frontend Implementation Brief
**Product:** Modda — Uzbek Legal AI Agent
**Primary data source:** Lex.uz
**Version:** v2 (2026-11-06) — see §0 first
**Frontend:** Vanilla JavaScript + Vite + Three.js
**Animation:** GSAP
**3D interaction:** Three.js OrbitControls (restricted camera movement)
**Backend:** FastAPI + Server-Sent Events (SSE)
**Architecture:** Event-driven, modular, backend-connected
**Design reference:** The attached final Modda visual concept. Recreate its visual language and composition using editable HTML/CSS and real 3D elements. Do not use the reference image as a flattened website background.

---

# 0. FINAL CONCEPT v2 — Bobur's decisions (2026-11-06)

**This section overrides everything below where they differ.** It was written after reviewing the reference image (`frontend_idea/reference/Modda_ Qonunchilikdan Aniq Javob.png`). The reference image is ≈ 70 % right; this section describes the remaining 30 %.

## 0.1 What changes compared with the reference image

| Reference image | v2 decision |
|---|---|
| Left panel «Tadqiqot jarayoni» with 7 stages | **Removed.** The research stages live in the central graph |
| Right panel «Javob tayyor! / Javob · Manbalar · Grafda ko‘rish» | **Removed.** The answer is written **inside the book** |
| Central circular graph: topic/document nodes around a «Soliq majburiyati» core | **Process graph:** the **Mind** (the LLM) in the centre, the real processing stages around it |
| Lady Justice statue: decoration | **Interactive:** clicking it brings the statue to the centre; its own 3-D scales compare the **answer score** with **Lex.uz** |
| Book: closed decoration | **The book is the result:** it searches, opens at the found modda, shows ±5 neighbouring moddas and the answer with references |

Everything else stays as in the image: header, headline, background, platform, query field, topic chips, bottom trust indicators, «Qanday ishlaydi?».

## 0.2 Screen composition (desktop 1600 × 900)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Modda | Qonunchilikdan aniq javob    Bosh sahifa  Graf  Hujjatlar  Yordam  ● Onlayn │
│                 Qonunchilikdan aniq javob —                              │
│                 har bir gapning manbasi bilan                            │
│   ⚖ Lady Justice      ╭──── process graph ────╮                          │
│   (clickable,         │  stages around MIND   │                          │
│    left side)         ╰───────────┬───────────╯                          │
│                          ┌────────┴────────┐                             │
│                          │   MODDA  BOOK   │  ← opens, pages = result     │
│                          └─────────────────┘                             │
│ [Rasmiy manbalar | Tez javob]  [ Savolingizni yozing…  ➤ ]  [Qanday ishlaydi?] │
│                  (Soliq stavkalari) (Mehnat ta’tili) (Fuqarolik huquqlari)    │
└──────────────────────────────────────────────────────────────────────────┘
```

When the answer is open, the book becomes the main reading area (it grows and the graph moves up and shrinks); the graph and the statue stay clickable.

## 0.3 The central process graph

**Centre — the Mind (LLM).** A glowing brain-like core. **Clicking it opens the LLM inspector:** the model's *real* architecture read from Ollama (`GET /model/info` → `/api/show`): number of transformer layers, hidden size, attention heads / KV heads, feed-forward size, context length, parameter count, quantisation; drawn as a 3-D stack of layers. Each layer shows a fixed sample of its neurons — the page states the real width («4096 ta neyron; 48 tasi ko‘rsatilgan»). Per-request numbers come from Ollama's counters: prompt tokens, output tokens, prompt/generation time, tokens per second. **Activations and attention values are not available from Ollama and are never drawn** (no flashing "thinking" neurons).

**While a question is processed, the centre switches to the stage that is running** (its icon, colour and name replace the Mind for the duration of that stage); when the pipeline finishes, the centre returns to the Mind with the completed state.

**Around the Mind — eight stage nodes, each different and clickable**, each opening its own visualisation built from that stage's real data:

| # | Node (uz) | Real operation | Its inspector shows |
|---|---|---|---|
| 1 | Savol tahlili | normalisation, Cyrillic → Latin, router (exact article reference), search terms | original vs. normalised question, route, recognised reference, terms (as chips) |
| 2 | Embedding | `bge-m3` → 1024-dim vector | the exact vector: 32 × 32 heat-map, dimension search, value list, copy JSON; norm/min/max/mean; token count and time; bge-m3 architecture (layers, width, heads) |
| 3 | Vektor qidiruv | Qdrant dense search (cosine) | 3-D PCA view (versioned transform, fitted on 2 000 reference points): reference cloud, query point, candidates with cosine similarity; dense ranking list |
| 4 | Lex.uz indeksi (BM25) | keyword search over the Lex.uz-derived index | query terms, BM25 ranking list with real scores. (It searches our index built from Lex.uz — not the live lex.uz site; the label says so) |
| 5 | Saralash (RRF) | Reciprocal Rank Fusion of 3 + 4, optional reranker, τ | two ranked columns joined by lines to the fused list; selected vs. rejected; reranker shown as «Faol emas» when off |
| 6 | O‘qish (kontekst) | selected passages given to the LLM | the passages, their headers, word counts, total context size |
| 7 | LLM javob | the model writes the answer | model, streamed text as it arrives, tokens in/out, speed, time |
| 8 | Tekshiruv | citation + number verifier | every sentence: cited source, verified / rejected and why |

Node states: waiting (grey), running (gold/cyan pulse), done (emerald), skipped (grey + «o‘tkazildi»), failed (red), warning (amber). Edges follow the pipeline order, particles move only along edges of stages that are actually running. Nodes before the first query are a quiet ambient graph with no data claims.

## 0.4 The book

1. **Idle:** closed, gently breathing, never rotating (as in the reference).
2. **Search:** on submit the cover opens and pages riffle — the book "searches" while the backend works (as in the current `web/` book). The animation never delays the answer.
3. **Found:** when `retrieval.completed` arrives the book settles on the page of the first candidate.
4. **Answer spread (final):**
   * **Left page — «Javob»:** the answer sentences with reference marks [1] [2]…, a short source list, the disclaimer «Modda rasmiy yuridik maslahat o‘rnini bosmaydi.»
   * **Right page — the source:** the document title and the found modda **among its ±5 neighbouring moddas** in document order (`GET /chunks/{id}/context?n=5`), the found one highlighted, others dimmed; the official wording unchanged; link «Lex.uz’da ochish».
   * Clicking a reference mark [n] **turns the pages** to source n's spread. Page controls ◀ ▶ (and keyboard arrows) move between source spreads.
5. **Unknown answer:** left page says «Lex.uz ma’lumotlari asosida ishonchli javob topilmadi.» with a next-step hint; no green state.
6. **Accessibility:** the same pages exist as real HTML (a reader overlay «Kitobni o‘qish») for screen readers, copying and the no-WebGL mode.

## 0.5 Lady Justice — the scales (v2.2, 2026-11-07)

A golden Lady Justice holding scales stands left of the graph, **1.21 ×** the first version (two 10 % steps). Model file: `frontend_idea/src/assets/models/lady-justice.glb` (from Bobur's `3D_Models/Lady Justice.glb`, decimated by `scripts/optimize_model.py`, which also **splits the two scale pans into separate meshes** `pan_0` / `pan_1` so the page can move them). Hover: soft gold rim light.

**When the answer is ready — the verdict, without leaving the book:** the camera stays on the book (the answer is what the person came for). In answer mode the statue stands whole beside the book (a little smaller), and when `scoring.completed` arrives her pans swing to the score, the score medallion and the Lex.uz logo pop onto the pans and the flames flare up for a moment; her label reads «⚖ 97 / 100 · manbaga moslik». The answer page carries a **gold seal** in its corner with the same score and «2/2 gap»; clicking the seal (or the statue) opens the focus mode below. The book is the answer, the scales are its grade — linked, not separate.

**Click (or «⚖ Tarozi» in the book bar) → focus mode — there is no 2-D scale:**

* The camera flies smoothly (GSAP) to her **upper body** — from just under the scale pans to the top of the scales — placed in the free part of the screen (between the header and the question field), slightly left so the caption fits on the right. The graph and book controls fade out. **Esc** or «Orqaga» flies back.
* The comparison is shown **on the statue's own scales:** on one pan a gold medallion with the **score** («97 · JAVOB /100»), on the other the **official Lex.uz logo in 3-D** (`src/assets/models/lex_uz.svg`, extruded with its own blue gradient; a PNG/JPG logo goes on a medallion; with no file a «LEX.UZ» medallion).
* The pans move by the real score: level at 100, the «Javob» pan drops when sentences are unsupported (elastic easing).
* **The scales burn:** each pan has a **flame-shaped glow exactly as wide as the pan** (noise-driven shader tongues rising from the dish, plus low flames in front), embers rising from the dish, an emissive dish and a flickering light — brighter in focus mode. No round halo.
* A small caption beside the statue: «97 / 100 manbaga moslik · 2 / 2 gap Lex.uz matni bilan tasdiqlandi · so‘z mosligi 97 %», with «Gaplar» (per-sentence window: source, ✓/✗, reason, matched words) and «Orqaga (Esc)».
* **Score = «Manbaga moslik»** (`scoring.completed`, method `lexical-support-v1`): for every sentence the LLM wrote — is it cited, do its numbers occur in the source, what share of its content words occur in the cited source; score = mean of (overlap if supported else 0) × 100. It is a wording-match measure, not a legal opinion — the «Gaplar» window says so.
* Before an answer exists the pans are empty and dark; the caption says «Hali javob yo‘q — savol bering.»

**Rendering quality.** Book pages are drawn at 2× (2048 × 2752 textures on desktop, 1.5× on tablets, 1.25× on phones) with the GPU's maximum anisotropic filtering; the canvas renders at up to 2× the screen's pixels and steps down by 0.25 when the frame rate stays under 40 fps; the answer camera looks down on the pages more steeply so the text is less foreshortened. `?quality=low` turns all of this off.

**Inspector windows.** Every graph opens in a window; the graph is the main element of the window. The Mind window is wide: the 3-D layer stack fills it, facts are one row of tags (model, layers, neurons, heads, parameters, quantisation), layer navigation ‹ › / «Butun model» sits on the graph, one footnote line below.

## 0.6 Navigation

* **Bosh sahifa** — new question, book closes. **Graf** — focuses the process graph (opens the last request's graph). **Hujjatlar** — searchable list of documents (`GET /documents?q=`) and reading a document's articles in the book. **Yordam** — how Modda works (the eight stages in plain words). **● Onlayn** — real `/health`: emerald only when Ollama and Qdrant both answer.

## 0.7 Backend data used (all added 2026-11-06; nothing existing removed)

| Need | Source |
|---|---|
| stage events + streaming text | `POST /ask/stream`: §13 events + `generation.delta`, `generation.completed`, `scoring.completed` |
| retrieval scores and both rankings | `retrieval.completed.candidates[]`: `score`, `dense_rank/score`, `sparse_rank/score`; `dense_list`, `sparse_list` |
| exact vector, PCA, candidate positions | `GET /ask/{request_id}/embedding` |
| model architecture | `GET /model/info` |
| book pages (±5 moddas) | `GET /chunks/{chunk_id}/context?n=5` |
| documents page | `GET /documents?q=`, `GET /documents/{doc_id}` |
| honest status badge | `GET /health` → `services.ollama`, `services.qdrant`, `ready` |

## 0.8 Technology (unchanged)

Vite + vanilla JavaScript + Three.js + GSAP, built in `frontend_idea/`; `web/` and the backend's existing behaviour stay as they are. §§ 2 (colours, fonts), 11–13, 16–19 below remain valid. §§ 3.1–3.5 (five regions), 5.2 (three-column layout), 7 (left progress panel) and 9 (right answer panel) are **replaced** by §0.

---

# 1. PRODUCT VISION

Build Modda as a premium Legal Intelligence Platform for Uzbekistan.

Modda is not a conventional chatbot. Its purpose is to answer users' legal questions using Lex.uz data, retrieve relevant legal documents, and provide answers with traceable official sources.

The most distinctive feature of Modda must be its **interactive 3D Legal Knowledge Graph**.

When the user submits a question, the website should visually transform into a live research environment. The user should be able to observe:

1. How the system analyzes their question.
2. How BGE-M3 converts the question into a semantic embedding.
3. How Lex.uz-related indexed documents are retrieved.
4. How candidate documents are ranked and filtered.
5. How selected passages are assembled into context.
6. How the LLM generates an answer.
7. How citations and supporting passages are verified.

The user must be able to click every major graph node and investigate its underlying information.

The experience should communicate intelligence, transparency, legal authority, and technological sophistication.

## Core design philosophy

**The 3D environment visualizes actual system operations. It must never invent technical information.**

Do not simulate fake embedding values, fabricated neural activations, fake retrieval results, artificial confidence percentages, or fictional legal documents.

When the backend does not expose a particular value, display an explicit unavailable state rather than inventing it.

The website must prioritize legal answers and evidence while making the AI research process visually understandable.

---

# 2. VISUAL IDENTITY

## 2.1 Overall aesthetic

Use the visual direction of the provided reference:

- Dark, premium legal-library environment.
- Cinematic 3D lighting.
- Deep charcoal and almost-black backgrounds.
- Emerald and cyan illumination.
- Restrained gold details.
- Glass-like interface panels.
- Three-dimensional neural networks.
- Floating legal document elements.
- Realistic physical legal book.
- Subtle particles and glowing connections.
- Sophisticated typography.

The result should feel like a combination of a high-end AI research laboratory and a premium legal intelligence platform.

Avoid:

- Generic AI chatbot design.
- Traditional government portal styling.
- Excessive neon.
- Purple-blue gradient backgrounds.
- Excessively rounded cards.
- Gaming-style animations.
- Unnecessary dashboard widgets.
- Excessive decorative particles.
- Constantly spinning objects.

The interface must look professional enough to be presented to government institutions, legal professionals, universities, and enterprises.

## 2.2 Color system

Use these design tokens consistently.

| Token | Hex | Purpose |
|---|---|---|
| Background | `#070D0C` | Main environment |
| Background secondary | `#0B1412` | Secondary environment |
| Glass panel | `#101A17` | Main panels |
| Elevated panel | `#14211C` | Cards and overlays |
| Panel hover | `#192A22` | Hover states |
| Primary text | `#F0F2ED` | Main typography |
| Secondary text | `#A1ADA5` | Supporting text |
| Muted text | `#728078` | Metadata |
| Gold | `#D6B66D` | Legal identity and active accents |
| Gold soft | `#9E8148` | Secondary gold details |
| Emerald | `#39D6A0` | Selected and verified elements |
| Cyan | `#65D8EE` | Neural and embedding visualization |
| Blue | `#73AFE0` | Retrieval and data connections |
| Amber | `#E5AD5C` | Warnings and incomplete verification |
| Red | `#E36F72` | Actual errors only |
| Border | `#293A33` | Panel outlines |
| Paper | `#EDE7D9` | Physical book pages |

### Semantic color rules

**Gold:** legal identity, query analysis, search activity, important controls.

**Cyan:** embeddings, vector spaces, neural structures, data transformations.

**Blue:** database retrieval and information transfer.

**Emerald:** completed stages, selected passages, validated citations, successful results.

**Grey:** pending stages, inactive nodes, rejected candidates.

**Amber:** incomplete verification, outdated sources, warnings.

**Red:** genuine backend failures. Do not use red merely to indicate unselected documents.

Green must have a clear meaning: the corresponding data has actually been selected or verified.

## 2.3 Typography

Use three font families:

| Font | Usage |
|---|---|
| Onest | Interface, menus, buttons, cards |
| Literata | Large headlines and legal document text |
| JetBrains Mono | Technical metadata, vector dimensions, event names, model information |

Suggested typography:

- Main hero headline: 44–58px.
- Section headings: 20–28px.
- Panel headings: 14–18px.
- Body text: 13–16px.
- Supporting information: 10–12px.
- Technical metadata: 9–11px.

Provide appropriate fallbacks and ensure Uzbek characters render correctly, including `o‘`, `g‘`, `ʻ`, `ʼ`, and Cyrillic text where applicable.

---

# 3. GLOBAL PAGE STRUCTURE

> **v2:** regions 3 and 4 (left and right panels) are removed (§0.2).

Design the main desktop experience around a 1600 × 900 viewport.

The interface should also scale proportionally to the 1648 × 928 reference image.

The main experience consists of five visual regions:

1. Top navigation.
2. Central headline and 3D environment.
3. Left research-progress panel.
4. Right answer/evidence panel.
5. Bottom query input and suggested topics.

The central graph and book are the visual focus.

## 3.1 Top navigation

Position the navigation bar along the top edge.

### Left side

Modda logo:

- A thin gold outlined square/book symbol.
- Brand name: `Modda`.
- Vertical divider.
- Brand description: `Qonunchilikdan aniq javob`.

### Center navigation

Four navigation items:

- Bosh sahifa
- Graf
- Hujjatlar
- Yordam

Use minimal icons and subtle hover effects.

The active item receives a gold underline and a restrained glow.

### Right side

System status badge:

`● Onlayn`

Use emerald when the backend and relevant services are healthy.

Use amber or grey when services are degraded or disconnected. Never display Online merely because the frontend loaded.

### Interaction

- Clicking Bosh sahifa returns to the initial screen.
- Clicking Graf opens the current research graph when a query exists.
- Clicking Hujjatlar opens document exploration.
- Clicking Yordam displays product guidance.
- Status badge may show system health information.

Keep the header visible during major state transitions.

---

# 4. FRAME 01 — INITIAL HOMEPAGE

## Objective

Create the first impression of a premium legal intelligence platform.

The initial page should have a calm atmosphere. The user should immediately understand what Modda does.

## 4.1 Main headline

Position the headline near the upper-center region.

Exact Uzbek copy:

**Qonunchilikdan aniq javob —
har bir gapning manbasi bilan**

Use Literata, approximately 44–54px.

The first line should use an off-white color. The second line may use a restrained gold accent.

Supporting description:

`Lex.uz ma’lumotlari asosida ishlovchi zamonaviy AI-agent`

Use Onest, approximately 16px, in secondary text color.

## 4.2 Background environment

Create an atmospheric legal library.

Visual elements:

- Dark bookshelves in the background.
- Warm desk lighting.
- Blurred books.
- Subtle reflections.
- A sophisticated legal-research environment.
- Very subtle dust particles.

The environment should have depth but must not compete with the foreground.

Implementation options:

- A lightweight optimized background image for static scenery.
- CSS gradients and overlays.
- Three.js objects for the physical book, central platform, particles, and graph.

Do not model an unnecessarily complex library in real time.

The background should remain dark enough to preserve text contrast.

## 4.3 Central 3D Modda book

This is one of Modda's key identity elements.

Create a realistic hardcover legal book using Three.js.

### Book design

- Deep navy/black-blue cover.
- Gold embossed decorative borders.
- `MODDA` on the cover.
- Uzbekistan Republic's official emblem at the center, using the actual supplied `web/public/gerb.png` asset where available.
- Text: `O‘ZBEKISTON RESPUBLIKASI QONUNCHILIGI`.
- Cream-colored pages.
- Realistic spine and page edges.
- Subtle physical reflections.

Do not invent or approximate the official national emblem with arbitrary graphics.

### Book position

Place the book near the bottom-center area, slightly in front of the central graph.

The book should rest on a subtle circular platform with cyan and emerald illumination.

### Idle animation

When there is no query:

- Book remains closed.
- Very subtle floating or breathing motion.
- Slow light reflection across the cover.
- Fine dust particles.
- Extremely restrained platform illumination.

The book should never continuously rotate.

### Query animation

When a user submits a question:

1. Camera slowly approaches.
2. The book cover opens.
3. Pages become visible.
4. A gentle page movement begins.
5. The central knowledge graph activates.
6. The camera returns to the main research composition.

Animation must not delay backend processing.

If the response arrives earlier than the animation, finish the minimum visual transition and display the result.

If backend processing takes longer, keep the research environment active without repeating the same animation excessively.

## 4.4 Initial graph

Before a question is submitted, show a quiet ambient network around the book.

It is decorative until a real query exists.

Use:

- Thin curved connections.
- Small cyan nodes.
- Restrained gold particles.
- A central subtle brain/neural symbol.

Do not label decorative nodes as actual retrieved documents.

## 4.5 Search field

Position the main query field near the lower portion of the screen.

Suggested appearance:

- Width: approximately 820px on a 1600px viewport.
- Height: 54–62px.
- Glass-like dark panel.
- Thin emerald or gold border.
- Soft focus illumination.

Placeholder:

`Savolingizni yozing...`

Right-side action:

`↑` or a paper-plane icon.

Button label may be omitted in favor of a compact icon.

### Search behavior

- Enter submits.
- Shift + Enter creates a new line.
- Button submits.
- Empty questions cannot be submitted.
- Trim leading/trailing whitespace.
- Disable duplicate submissions while a request is active.
- Preserve the submitted question at the top of the research screen.

## 4.6 Suggested questions

Under the search field, display three compact interactive topic suggestions:

- Soliq stavkalari
- Mehnat ta’tili
- Fuqarolik huquqlari

Clicking a suggestion inserts the text into the query field or submits the associated prepared question according to the chosen interaction pattern.

These are topic examples, not official legal answers.

## 4.7 Bottom trust indicators

At the bottom-left:

- Rasmiy manbalar
- Manbali javoblar

At the bottom-right:

`Qanday ishlaydi?`

Clicking it opens an explanation of the retrieval and answer process.

---

# 5. FRAME 02 — LIVE LEGAL INTELLIGENCE GRAPH

This is the central feature of Modda.

When a query is submitted, transition the interface from the initial homepage into a live research workspace.

The main graph should occupy approximately 60–70% of the available central workspace.

The left and right panels remain visible.

The physical book stays near the lower center and acts as the visual anchor of the research environment.

## 5.1 Example query

Use the following as demonstration content:

`Soliq majburiyati bo‘yicha tegishli huquqiy normalarni toping.`

Do not hardcode a legal conclusion for this demonstration. Actual answers must come from the backend.

## 5.2 Main layout

> **v2:** replaced — no side panels (§0.2).

Desktop composition:

| Region | Approximate width |
|---|---:|
| Left pipeline panel | 18% |
| Central graph | 55% |
| Right answer/source panel | 27% |

The exact proportions should adapt to the screen width.

### Left panel

Displays seven pipeline stages.

### Center

Displays the interactive 3D graph.

### Right panel

Initially shows retrieved document candidates and research information.

After answer completion, it transforms into the answer/evidence panel.

## 5.3 The seven clickable research stages

> **v2:** now eight stages around the Mind (§0.3); the per-stage rules below still apply.

The seven nodes surrounding the central intelligence core must represent the following actual backend stages.

They are not merely decorative nodes.

### Node 01 — Query analysis

Label:

`Savol tahlili`

Backend operation:

- Input normalization.
- Cyrillic-to-Latin normalization where applicable.
- Legal query routing.
- Search concept extraction.
- Query preparation.

Visual color: Gold.

3D representation:

- The question appears as the central input.
- Recognized search concepts emerge as smaller connected nodes.
- Connections illuminate as the backend reports the actual concepts.
- A small information panel shows the recognized terms.

Click behavior:

Open the query analysis inspector.

Show:

- Original user question.
- Normalized query.
- Extracted concepts.
- Routing result.
- Processing time.

Only display fields returned by the backend.

### Node 02 — Embedding

Label:

`Embedding`

Model:

`BGE-M3`

Expected output:

`1024-dimensional vector`

Visual color: Cyan.

3D representation:

- Input query becomes a sequence of token representations.
- Token representations pass through the encoder.
- A vector node is produced.
- A particle stream travels from the model toward the vector/index.

Show actual model name, vector dimensions, and elapsed time.

Click behavior:

Open the full Embedding Inspector described in Section 6.

### Node 03 — Lex.uz retrieval

Label:

`Qidiruv`

Actual pipeline:

- Qdrant dense retrieval.
- BM25 sparse retrieval.
- Reciprocal Rank Fusion (RRF).
- Metadata filtering.

Visual color: Blue/Cyan.

3D representation:

- The central graph connects to an index/database structure.
- Retrieved document nodes appear as actual candidates.
- Each document node contains a document identifier and actual title.
- Related chunks or articles appear as smaller child nodes.

Click behavior:

Open the retrieval inspector.

Display:

- Retrieval mode.
- Index/collection information.
- Dense candidate count.
- Sparse candidate count, if exposed.
- Fused candidates.
- Actual retrieved chunk IDs.
- Document titles.
- Article numbers.
- Retrieval rank and available scores.

Never invent retrieved documents or scores.

### Node 04 — Ranking and reranking

Label:

`Saralash`

Actual operation:

- Candidate ordering.
- Optional `bge-reranker-v2-m3` CrossEncoder.
- Threshold `τ`.
- Selected/rejected passage IDs.

Visual color: Gold.

3D representation:

- Candidate document nodes are arranged into an ordered structure.
- Selected nodes illuminate.
- Rejected nodes fade into grey.
- A visible path connects selected passages with the next stage.

Click behavior:

Show:

- Reranker enabled/disabled.
- Original candidate ordering.
- Updated ranking.
- Actual available scores.
- Threshold configuration.
- Selected chunk IDs.
- Rejected chunk IDs.

If reranking is disabled:

Show `O‘tkazib yuborildi` or `Faol emas`.

Do not animate a fake reranker process.

### Node 05 — Context assembly

Label:

`Kontekst`

Actual operation:

- Selected passage collection.
- Document metadata association.
- Context construction.
- Preparation of the LLM input.

Visual color: Gold with cyan details.

3D representation:

- Selected document nodes converge into a central context structure.
- Actual selected passages are represented as connected document blocks.
- A visible packet or information flow moves toward the generation stage.

Click behavior:

Show:

- Selected passage IDs.
- Document titles.
- Actual excerpts.
- Context length, if available.
- Metadata associated with each passage.

Never substitute generated summaries for original retrieved text without clearly labeling them.

### Node 06 — Answer generation

Label:

`Javob`

Actual operation:

- Selected LLM receives the assembled context.
- The LLM generates structured answer content.
- The system prepares source references.

Visual color: Cyan transitioning to Emerald when generation completes.

3D representation:

- The context structure connects to an answer node.
- The answer node gradually illuminates.
- A subtle particle flow connects supporting passages to the resulting answer.

Click behavior:

Show:

- Actual model name.
- Generation status.
- Available timing information.
- Answer structure.
- Whether the system returned `unknown = true`.

Do not visualize private chain-of-thought or claim to reveal the LLM's hidden reasoning.

Visualize observable system operations and outputs only.

### Node 07 — Citation verification

Label:

`Tekshiruv`

Actual operation:

- Verify source metadata.
- Verify citations and passage relationships.
- Check numerical claims where implemented.
- Check supporting document references.

Visual color: Emerald for verified, amber for incomplete or failed verification.

3D representation:

- Answer node connects back to its source documents.
- Verified connections become green.
- Incomplete or failed verification connections become amber.
- Source relationships become visible.

Click behavior:

Show:

- Verified chunk IDs.
- Failed chunk IDs.
- Citation verification results.
- Numerical verification result, if available.
- Relevant source metadata.
- Actual verification time.

Do not display successful verification unless the backend confirms it.

---

# 6. FRAME 03 — INTERACTIVE EMBEDDING & NEURAL NETWORK INSPECTOR

This is the most technically interesting feature of Modda.

When the user clicks the central model/brain node or the embedding stage, open a dedicated 3D inspection environment.

The user should be able to investigate how the submitted question is encoded.

## 6.1 Inspector structure

Use a large full-screen overlay or dedicated view.

Three main regions:

1. Left: model input and architecture.
2. Center: interactive 3D neural network.
3. Right: exact embedding/vector data.

The 3D visualization should be the largest region.

### Header

Show:

`MODEL INSPECTOR`

Model metadata:

- BGE-M3.
- 1024 dimensions.
- Actual model version/revision if available.
- Request ID.
- Query text.

Buttons:

- Back to graph.
- Reset camera.
- Toggle labels.
- Show vector.
- Show/hide connections.
- Close inspector.

## 6.2 Neural network visualization

Create a three-dimensional network consisting of:

- Input token layer.
- Embedding representation.
- Transformer layers.
- Output representation.
- Final 1024-dimensional vector.

The actual number of layers must be obtained from the model configuration or runtime inspection. Never hardcode an assumed architecture depth.

### Visual architecture

Each layer should be a spatial plane containing nodes.

Connections between layers represent actual model computation relationships where available.

Use:

- Small glowing spheres for neurons/nodes.
- Thin lines for connections.
- Cyan for active representations.
- Gold for important input information.
- Emerald for successfully produced output.
- Grey for inactive or unavailable telemetry.

### Input tokens

Display the actual tokenization result when available.

For example, a sentence should be broken into the model's real token sequence.

Each token can be represented by a small sphere or connected group.

Hovering over a token displays its text and token ID.

Clicking a token highlights its connected representation in the following layer, but only when the backend exposes the relevant alignment/activation data.

### Layer transitions

When the user inspects a layer:

- Camera smoothly approaches the layer.
- The layer expands.
- Its node representations become more visible.
- Previous and next layer connections remain visible.
- A side panel displays the available tensor information.

The user should be able to move through layers using:

- Previous layer.
- Next layer.
- Layer dropdown.
- Direct clicking in the 3D scene.

### Important distinction: weights vs activations

Do not show an incorrect representation of model weights.

Model weights are parameters and do not change with each inference request.

Input-dependent activations are the values that change as the question passes through the network.

The visualization should distinguish:

**Model weights:**

Static learned parameters.

**Runtime activations:**

Input-dependent intermediate representations produced during inference.

**Attention scores:**

Actual attention tensors from the corresponding computation, when instrumented and available.

If the backend does not expose these tensors, show the model's architecture and explain that detailed activations are unavailable.

Do not fabricate changing neuron brightness or pretend to visualize exact activations using random values.

## 6.3 Exact embedding visualization

This is a strict requirement.

BGE-M3 produces a 1024-dimensional embedding in the planned architecture.

A 1024-dimensional vector cannot be directly displayed as three native XYZ coordinates.

Therefore, implement two separate visualizations.

### A. Actual 1024-dimensional vector

Show the exact vector values.

Example structure:

`embedding[0] = actual float value`

`embedding[1] = actual float value`

Continue through all 1024 dimensions.

Use:

- A paginated value inspector.
- A dimension-indexed table.
- A horizontal value chart or heatmap.
- A selected-dimension detail view.
- Copy JSON action.
- Search dimension action.

Never use placeholder floats.

If the backend only returns `{model, dim, ms}`, display a clear message:

`Exact vector payload is not available.`

Do not fabricate numeric values.

### B. 3D vector projection

Create a genuine three-dimensional visualization derived from the actual 1024-dimensional vector.

Use PCA or UMAP with a fixed, reproducible reference projection.

Important:

- Fit or load a projection transform using a reference embedding dataset.
- Apply the same transform to the current query vector.
- Preserve the transform version.
- Display the query point's resulting XYZ coordinates.
- Make it clear that these coordinates are a derived projection, not native embedding dimensions.

The displayed cloud may include actual candidate document embeddings, provided they use the same model/version and projection transform.

The user's query vector should be highlighted in emerald or cyan.

Clicking a projected document point should display its actual document metadata.

### 3D projection controls

- Rotate.
- Zoom.
- Pan.
- Reset.
- Toggle document points.
- Toggle query point.
- Toggle labels.
- Display XYZ projection coordinates.
- Display vector dimension count.

The user must be able to inspect both the visual projection and exact raw values.

## 6.4 Backend requirements for the inspector

The existing `embedding.completed` event in the roadmap provides:

- `model`
- `dim`
- `ms`

This is insufficient to display the exact vector.

Add a request-scoped, controlled vector inspection endpoint or an equivalent payload.

Suggested endpoint:

`GET /ask/{request_id}/embedding`

Example response:

```json
{
  "request_id": "query_123",
  "model": "bge-m3",
  "dim": 1024,
  "dtype": "float32",
  "vector": [0.0],
  "projection": {
    "method": "PCA",
    "transform_version": "pca_v1",
    "coordinates": {
      "x": 0.0,
      "y": 0.0,
      "z": 0.0
    }
  }
}
```

The sample values above are placeholders for the schema only, not valid embedding data.

The actual endpoint must return the complete real vector.

Avoid transmitting the full vector in every SSE event. Fetch it on demand when the user opens the inspector.

Protect request-scoped diagnostic data according to the application's access and retention policy.

---

# 7. FRAME 04 — LIVE RESEARCH PROGRESS PANEL

> **v2:** replaced — the stages are nodes of the central graph (§0.3).

The left panel must remain visible throughout the research process.

It displays seven vertical stages.

Each stage contains:

- Stage number.
- Icon.
- Uzbek label.
- Short technical description.
- Status indicator.
- Optional elapsed time.

## Stage status system

| State | Visual treatment |
|---|---|
| Waiting | Grey |
| Running | Gold/cyan glow |
| Completed | Emerald |
| Skipped | Neutral grey with skipped label |
| Failed | Red |
| Warning | Amber |

Use actual backend events to update the statuses.

Clicking a stage opens its corresponding inspector.

The currently active stage should have a subtle border glow and a small live indicator.

Do not use fabricated percentage bars.

Display actual elapsed time where available.

The status system should remain readable even if the backend is slow.

---

# 8. FRAME 05 — CENTRAL GRAPH AND DOCUMENT NETWORK

The central graph must be visually impressive but technically meaningful.

## 8.1 Core structure

At the center:

A glowing neural/brain-like intelligence core.

Around it:

Seven interactive pipeline nodes.

Connections:

- Curved lines.
- Thin, luminous edges.
- Animated particles traveling along active edges.
- Soft halo around active nodes.

The seven nodes must be connected according to the actual pipeline.

Do not draw random unrelated connections merely for decoration.

## 8.2 Document nodes

When retrieval completes, actual legal document nodes appear.

Each document node contains:

- Document name.
- Document type.
- Document ID.
- Relevant article number.
- Rank.
- Available retrieval score.

Each legal document may contain child nodes representing retrieved articles or chunks.

Example visual hierarchy:

```text
Lex.uz Index
    |
    ├── Document A
    |      ├── Article 1
    |      └── Article 2
    |
    ├── Document B
    |      ├── Article 4
    |      └── Article 7
    |
    └── Document C
           └── Article 12
```

This is an illustrative relationship structure. Production nodes must originate from real backend data.

## 8.3 Graph interaction

### Hover

- Increase node brightness.
- Highlight connected paths.
- Display a compact tooltip.
- Dim unrelated parts of the graph slightly.

### Click

- Select node.
- Camera moves smoothly toward it.
- Open its details panel.
- Highlight incoming and outgoing connections.

### Double-click

Expand or collapse a document's article/chunk nodes.

### Graph controls

- Zoom in.
- Zoom out.
- Reset camera.
- Center selected node.
- Toggle rejected candidates.
- Toggle document labels.
- Toggle particle effects.

Keep camera movement restricted and predictable.

---

# 9. FRAME 06 — ANSWER GENERATION AND RESULT PANEL

> **v2:** replaced — the answer is written inside the book (§0.4). The content rules below (disclaimer, real sources, no invented metadata) still apply.

After research finishes, the right-side panel transforms into the final answer panel.

The main graph and progress timeline remain visible, but they become less dominant.

The result panel becomes the primary reading area.

## 9.1 Answer panel header

Display:

`Javob tayyor!`

Use an emerald success indicator only after `answer.completed`.

Show the actual completion timestamp if available.

## 9.2 Tabs

Three tabs:

1. Javob
2. Manbalar (N)
3. Grafda ko‘rish ↗

### Tab 1 — Javob

Display the actual answer returned by the API.

Structure:

- Short direct answer.
- Detailed explanation.
- Conditions.
- Exceptions.
- Supporting legal basis.
- Necessary warnings.
- Legal disclaimer.

Use clear readable typography.

Highlight important parts carefully.

Do not allow the LLM to invent or manufacture source metadata.

### Tab 2 — Manbalar

Display the actual sources returned by the backend.

Each source card includes:

- Official document title.
- Document type.
- Article number.
- Relevant excerpt.
- Document status, if returned.
- Last checked/updated date, if returned.
- Official Lex.uz link.

Clicking a source opens its full detail view.

### Tab 3 — Grafda ko‘rish

Expand the knowledge graph.

Show:

- Which documents were retrieved.
- Which passages were selected.
- Which sources were verified.
- How the final answer connects to those sources.

The selected sources should be highlighted in emerald.

## 9.3 Full-document button

Button:

`To‘liq moddani ochish`

Clicking it opens the document detail view or official Lex.uz URL.

## 9.4 Legal disclaimer

Always display:

`Modda rasmiy yuridik maslahat o‘rnini bosmaydi.`

Use a restrained muted style.

---

# 10. FRAME 07 — SOURCE AND DOCUMENT INSPECTOR

Clicking a document node or source card opens its details.

This may be implemented as a right-side drawer or dedicated page.

## Information hierarchy

1. Official document title.
2. Document type.
3. Article number.
4. Article heading.
5. Original legal text.
6. Relevant excerpt.
7. Citation verification status.
8. Document status.
9. Relevant dates.
10. Official Lex.uz URL.

The legal text must be obtained from the backend.

Preserve the original official wording.

Never rewrite official legal text and present the rewrite as a quotation.

## Graph integration

When the source inspector opens:

- Highlight the selected document node.
- Highlight connected article nodes.
- Highlight the relationship to the answer.
- Offer a `Grafda ko‘rish` button.

Clicking the button returns to the graph and focuses the selected document.

---

# 11. ANIMATION SYSTEM

Use GSAP to coordinate interface transitions and Three.js animations.

The visual timeline must be driven by real backend events.

## 11.1 Initial idle animation

- Book gently floats.
- Soft gold lighting moves subtly.
- Background particles move slowly.
- The graph has very subtle ambient movement.
- Search field has a restrained focus effect.

No aggressive continuous movement.

## 11.2 Query submission

Sequence:

1. Input button responds immediately.
2. Query field becomes a submitted-query display.
3. Camera approaches the book.
4. Book cover opens.
5. Central graph activates.
6. Seven pipeline nodes appear.
7. Left and right research panels become prominent.

Recommended visual transition: approximately 0.6–1.2 seconds.

This is a visual guideline, not a backend processing delay.

## 11.3 Query analysis animation

- Central query node illuminates.
- Search concepts appear.
- Connections form around the node.
- Analysis stage changes to completed only when the actual event arrives.

## 11.4 Embedding animation

- Tokens appear.
- Actual model flow is represented.
- Vector output node activates.
- Data particles travel toward the index.

Only show token-level transformations if the backend exposes them.

## 11.5 Retrieval animation

- Database structure illuminates.
- Actual retrieved nodes appear.
- Connections extend toward candidate nodes.
- Document panels populate.

The number of visualized documents must correspond to the actual returned candidates.

## 11.6 Ranking animation

- Candidate nodes arrange by actual rank.
- Selected nodes brighten.
- Rejected nodes fade.
- Connection paths update.

## 11.7 Context animation

- Selected passages converge.
- A context node appears.
- Actual selected source IDs appear in the node inspector.

## 11.8 Answer-generation animation

- Central answer node becomes active.
- A connection is established from the context.
- Answer card appears.
- The system transitions into the completed state.

## 11.9 Verification animation

- Source-to-answer connections become green only when verified.
- Unverified connections remain amber.
- The final graph settles into a stable composition.

## 11.10 Error and unknown states

When `unknown = true`:

Display:

`Lex.uz ma’lumotlari asosida ishonchli javob topilmadi.`

Do not show a successful green completion state.

Provide a useful next step.

When the backend reports an actual error:

- Stop the current stage.
- Display an error indicator.
- Preserve the submitted query.
- Show a retry button.

The visual experience should never hide or misrepresent backend errors.

---

# 12. BUTTONS AND INTERACTION REQUIREMENTS

Every visible control must work.

| Control | Action |
|---|---|
| Modda logo | Return to homepage |
| Bosh sahifa | Navigate to home |
| Graf | Open current graph |
| Hujjatlar | Open document exploration |
| Yordam | Open help information |
| Onlayn badge | Show service status |
| Query input | Accept legal question |
| Send button | Submit request |
| Suggested topics | Insert or submit suggested query |
| Seven graph nodes | Open corresponding inspector |
| Central brain node | Open model inspector |
| Document node | Open document details |
| Article node | Open article excerpt |
| Source card | Open official source details |
| Javob tab | Display answer |
| Manbalar tab | Display sources |
| Grafda ko‘rish | Expand graph |
| Full document button | Open official document |
| Copy citation | Copy actual citation text |
| Reset camera | Reset graph camera |
| Zoom controls | Change graph zoom |
| Close inspector | Return to previous state |
| Back button | Return to previous screen |
| New query | Start a fresh research request |
| Skip animation | Complete visual transition immediately |

Provide keyboard navigation and visible focus states.

---

# 13. BACKEND INTEGRATION — SSE EVENT CONTRACT

The frontend must integrate with the existing FastAPI backend.

Primary endpoint:

`POST /ask/stream`

Use Server-Sent Events.

Every event should contain:

```json
{
  "type": "embedding.completed",
  "request_id": "query_123",
  "ts": "2026-11-05T10:00:00+05:00",
  "data": {}
}
```

All stages must be driven by the backend.

## Supported event sequence

| Event | Frontend responsibility |
|---|---|
| `query.received` | Create query node |
| `query.analyzed` | Display query and concepts |
| `embedding.completed` | Complete embedding stage |
| `retrieval.started` | Activate index |
| `retrieval.completed` | Create actual document nodes |
| `ranking.completed` | Update selected/rejected nodes |
| `context.completed` | Display selected context |
| `generation.started` | Activate answer node |
| `verification.completed` | Update source verification states |
| `answer.completed` | Display final answer |
| `stage.failed` | Display actual error |

### Required event data

`query.analyzed`:

```json
{
  "concepts": [],
  "route": "semantic"
}
```

`embedding.completed`:

```json
{
  "model": "bge-m3",
  "dim": 1024,
  "ms": 0
}
```

`retrieval.completed`:

```json
{
  "documents_found": 0,
  "chunks_retrieved": 0,
  "candidates": [
    {
      "chunk_id": "actual_chunk_id",
      "doc_title": "Actual document title",
      "doc_type": "Actual document type",
      "article_no": "Actual article number",
      "article_title": "Actual article title",
      "rank": 1
    }
  ]
}
```

`ranking.completed`:

```json
{
  "reranker": true,
  "selected": [],
  "rejected": [],
  "tau": null,
  "top_score": null
}
```

`context.completed`:

```json
{
  "chunk_ids": []
}
```

`generation.started`:

```json
{
  "model": "actual_selected_model"
}
```

`verification.completed`:

```json
{
  "verified": [],
  "failed": []
}
```

`answer.completed`:

Return the existing `/ask` response structure:

- `unknown`
- `checked_at`
- `answer`
- `sources`

Keep this contract backward-compatible with the existing API wherever possible.

## Event handling requirements

- Process events in their received order.
- Match events to `request_id`.
- Ignore or safely handle duplicated events.
- Handle disconnected streams.
- Handle reconnections without duplicate document nodes.
- Preserve current research state during temporary disconnection.
- Handle cancellation when the user starts a new query.
- Provide a normal `/ask` fallback if SSE fails.
- Show accurate timestamps.
- Never fabricate a completed stage.

The frontend state machine must be independent of animation timelines.

Backend completion must never depend on animation completion.

---

# 14. TECHNICAL STACK

The existing frontend roadmap uses Vite and vanilla JavaScript.

Keep this architecture.

Do not migrate to React simply to adopt React Three Fiber.

## Core stack

| Technology | Responsibility |
|---|---|
| Vite | Build and development |
| Three.js | 3D book and knowledge graph |
| GSAP | Animation orchestration |
| OrbitControls | Restricted 3D interaction |
| HTML | Accessible interface |
| CSS | Visual system and responsive layout |
| Vanilla JavaScript | Application logic |
| FastAPI SSE | Live backend communication |

Use the official Three.js documentation:

https://threejs.org/docs/

GSAP:

https://gsap.com/docs/

Vite:

https://vite.dev/

Use current stable compatible package versions and lock them through the package manager.

## Architecture decision

Use Three.js directly.

Do not introduce React Three Fiber or Zustand unless the project is deliberately migrated to React in a future version.

Use modular JavaScript and a lightweight central event/state manager.

---

# 15. RECOMMENDED PROJECT STRUCTURE

Build the frontend from scratch while preserving the existing backend API contract and reusable assets.

Suggested structure:

```text
web/
│
├── index.html
├── package.json
├── vite.config.js
│
├── public/
│   ├── gerb.png
│   ├── textures/
│   │   ├── book-cover/
│   │   └── paper/
│   └── fonts/
│
├── src/
│   ├── main.js
│   ├── config.js
│   │
│   ├── core/
│   │   ├── appState.js
│   │   ├── stateMachine.js
│   │   ├── eventBus.js
│   │   ├── eventStore.js
│   │   └── requestManager.js
│   │
│   ├── api/
│   │   ├── api.js
│   │   ├── sse.js
│   │   ├── normalAsk.js
│   │   └── embeddingInspector.js
│   │
│   ├── scene/
│   │   ├── renderer.js
│   │   ├── camera.js
│   │   ├── lighting.js
│   │   ├── environment.js
│   │   ├── book.js
│   │   ├── bookMaterials.js
│   │   ├── bookAnimation.js
│   │   ├── graph.js
│   │   ├── graphNodes.js
│   │   ├── graphEdges.js
│   │   ├── graphParticles.js
│   │   ├── graphCamera.js
│   │   ├── neuralNetwork.js
│   │   ├── embeddingProjection.js
│   │   └── cleanup.js
│   │
│   ├── models/
│   │   ├── queryModel.js
│   │   ├── pipelineModel.js
│   │   ├── documentModel.js
│   │   └── embeddingModel.js
│   │
│   ├── ui/
│   │   ├── header.js
│   │   ├── searchBar.js
│   │   ├── suggestedTopics.js
│   │   ├── progressPanel.js
│   │   ├── stageInspector.js
│   │   ├── sourcePanel.js
│   │   ├── answerPanel.js
│   │   ├── embeddingInspector.js
│   │   ├── documentInspector.js
│   │   ├── notification.js
│   │   └── controls.js
│   │
│   ├── animations/
│   │   ├── transitions.js
│   │   ├── researchTimeline.js
│   │   ├── graphTimeline.js
│   │   ├── bookTimeline.js
│   │   └── reducedMotion.js
│   │
│   └── styles/
│       ├── tokens.css
│       ├── global.css
│       ├── layout.css
│       ├── components.css
│       ├── panels.css
│       ├── inspector.css
│       ├── responsive.css
│       └── animations.css
│
└── tests/
    ├── stateMachine.test.js
    ├── eventHandling.test.js
    └── dataIntegrity.test.js
```

Keep modules focused and avoid creating one enormous `main.js`.

---

# 16. PERFORMANCE REQUIREMENTS

The 3D environment must not make Modda unusable on ordinary laptops or mobile devices.

## Desktop targets

- Target 60 FPS.
- Minimum acceptable average around 45 FPS on the agreed test laptop.
- Device pixel ratio capped around 1.5–1.75.
- Limit visible graph nodes to approximately 40 in the initial MVP.
- Reuse geometry and materials.
- Use instancing when useful.
- Avoid unnecessary draw calls.
- Avoid excessive transparent overlapping effects.
- Stop rendering when the tab is hidden.
- Avoid continuous rendering when the scene is idle.

## Mobile targets

- Target 30 FPS or better.
- Reduce particles and visible node counts.
- Disable expensive shadows when necessary.
- Use smaller rendering resolution.
- Provide a simplified graph layout.

## Memory management

When beginning a new request:

- Remove old request-specific graph nodes.
- Dispose of unused geometries.
- Dispose of unused materials.
- Dispose of unnecessary textures.
- Kill obsolete GSAP timelines.
- Remove abandoned event listeners.

Do not recreate the entire WebGL renderer for every user query.

## Rendering strategy

Use a demand-based rendering approach where possible.

Render on:

- User interaction.
- Node position change.
- Animation updates.
- Incoming graph events.
- Camera movement.

Suspend rendering when the browser tab is hidden.

---

# 17. RESPONSIVE DESIGN

## Desktop: 1440px and above

Show:

- Header.
- Left research panel.
- Full central knowledge graph.
- Right answer/source panel.
- Bottom search field.
- Full 3D book.

## Tablet: 768–1199px

- Reduce the graph's size.
- Collapse the left pipeline into a compact timeline.
- Keep the answer panel accessible.
- Move sources into a slide-out drawer where necessary.
- Reduce decorative details.

## Mobile: 390px–767px

The experience must remain functional.

Layout:

1. Compact header.
2. Query title.
3. Smaller graph/book visualization.
4. Horizontally scrollable or vertically stacked stage list.
5. Answer panel below graph.
6. Fixed or easily accessible query input at the bottom.

The user must not need horizontal scrolling.

Use simplified 3D visuals for mobile.

All buttons must remain touch-friendly.

---

# 18. ACCESSIBILITY AND FALLBACKS

Provide a complete non-WebGL experience.

If WebGL is unavailable or the device is too weak:

- Display a static book illustration.
- Display an ordinary graph representation.
- Keep all seven progress stages.
- Keep document cards.
- Keep the complete answer.
- Preserve all source links.

Respect:

`prefers-reduced-motion`

When reduced motion is enabled:

- Disable unnecessary particles.
- Remove camera parallax.
- Reduce page-turn movement.
- Replace long transitions with simple fades.
- Keep all actual functionality.

Additional requirements:

- Keyboard navigation.
- Visible focus indicators.
- Semantic HTML.
- Accessible button names.
- Screen-reader-friendly status updates.
- Proper text contrast.
- No information conveyed by color alone.

---

# 19. IMPORTANT PRODUCT AND DATA INTEGRITY RULES

These are non-negotiable requirements.

1. All document nodes must originate from actual backend results.
2. Article numbers must originate from actual metadata.
3. Search scores must only be displayed when the backend supplies them.
4. No fake confidence percentages.
5. No fake progress percentages.
6. No fabricated vector values.
7. No invented neural activations.
8. No invented attention scores.
9. No fake source verification.
10. No legal statements presented as official quotations unless taken from the official source.
11. Do not show a reranker as completed when it is disabled.
12. Do not confuse offline indexing with live user-query processing.
13. Do not delay real answers for animations.
14. Never expose private LLM chain-of-thought.
15. Keep generated explanations distinct from original legal text.

The frontend is a visualization layer, not the authority on legal truth.

The backend remains the source of actual processing states and legal evidence.

---

# 20. DEVELOPMENT ROADMAP

Prioritize a working implementation over decorative perfection.

## Phase 1 — Foundation

- Set up Vite.
- Configure Three.js.
- Establish the CSS design system.
- Build the header.
- Build the main layout.
- Implement the initial homepage.
- Create the central book scene.

**Deliverable:** A functional, visually polished Modda homepage.

## Phase 2 — Knowledge graph

- Create the central intelligence node.
- Build seven stage nodes.
- Create graph connections.
- Implement node selection.
- Add the left progress panel.
- Add source cards.
- Implement graph camera controls.

**Deliverable:** Interactive legal knowledge graph using clearly separated mock and production data sources.

## Phase 3 — Event-driven integration

- Integrate `/ask/stream`.
- Implement the event manager.
- Connect actual SSE events to graph states.
- Populate retrieved documents.
- Update seven progress stages.
- Handle errors and unknown results.
- Add normal `/ask` fallback.

**Deliverable:** Real user query displayed through the live research graph.

## Phase 4 — Embedding inspector

- Build model architecture view.
- Inspect actual BGE-M3 configuration.
- Implement vector payload retrieval.
- Display all 1024 actual dimensions.
- Implement genuine 3D PCA/UMAP projection.
- Implement layer inspection where instrumentation permits.
- Distinguish exact tensors from explanatory architecture diagrams.

**Deliverable:** Technically honest, interactive embedding inspector.

## Phase 5 — Answer and documents

- Build answer panel.
- Build source cards.
- Implement document inspector.
- Connect answer citations to graph nodes.
- Implement source navigation.
- Implement copy-citation interaction.

**Deliverable:** Full question-to-evidence workflow.

## Phase 6 — Optimization and final polish

- Desktop testing.
- Mobile testing.
- WebGL fallback.
- Reduced-motion mode.
- Keyboard controls.
- Memory cleanup.
- FPS measurements.
- SSE failure testing.
- Golden-set demo questions.

**Deliverable:** Stable, presentation-ready Modda frontend.

---

# 21. ACCEPTANCE CRITERIA

The MVP must not be considered complete merely because the homepage looks attractive.

It must pass these checks.

### Visual acceptance

- [ ] The dark legal-library aesthetic matches the supplied reference.
- [ ] Modda branding is consistent.
- [ ] Book has a recognizable physical 3D appearance.
- [ ] The central graph is visually impressive.
- [ ] Seven stages are clearly visible.
- [ ] Left and right panels have appropriate hierarchy.
- [ ] All text is readable.
- [ ] No visual overlap at 1600 × 900.
- [ ] Responsive layout works at 390px.

### Functional acceptance

- [ ] User can submit a question.
- [ ] Real SSE events update the pipeline.
- [ ] Seven stage nodes are clickable.
- [ ] Retrieved document nodes are clickable.
- [ ] Central model node opens model inspection.
- [ ] Embedding inspector displays actual data when available.
- [ ] Graph camera controls work.
- [ ] Answer panel displays actual `/ask` output.
- [ ] Source links navigate to real Lex.uz documents.
- [ ] User can return from inspectors.
- [ ] New queries clear old request-specific data.
- [ ] Error and unknown states work.
- [ ] SSE fallback works.

### Technical acceptance

- [ ] No fabricated technical values.
- [ ] No fabricated legal sources.
- [ ] Embedding is exactly 1024-dimensional when the model returns that dimension.
- [ ] 3D projection is derived from actual embeddings.
- [ ] Neural activations are shown only when instrumentation supplies them.
- [ ] WebGL fallback works.
- [ ] Reduced-motion mode works.
- [ ] Graph resources are cleaned up between requests.
- [ ] Browser console contains no critical errors.
- [ ] Performance meets the agreed desktop and mobile targets.

---

# 22. DEMONSTRATION SCENARIO

Use these six types of questions when testing the finished product:

1. A question containing an exact legal article reference.
2. A thematic question about employment legislation.
3. A question written in Cyrillic.
4. A question involving a potentially updated document.
5. A question for which the indexed knowledge base has no reliable answer.
6. A misleading or prompt-injection-style question.

For each demonstration:

- Submit the query.
- Show the actual seven-stage pipeline.
- Inspect the embedding.
- Observe real retrieved document nodes.
- Inspect ranking and selected passages.
- Open the final answer.
- Follow an answer citation back to its source node.
- Open the official Lex.uz document.

Never hardcode the demonstration answers as if they came from the live system.

A clearly identified demo/mock mode can be used when the backend is unavailable.

---

# 23. FINAL INSTRUCTIONS TO THE IMPLEMENTATION AGENT

Build the entire frontend from scratch using the specifications above and the attached final visual reference.

The reference image is the visual direction, not a flattened asset to embed as the whole webpage.

Preserve the existing backend architecture and API compatibility.

Keep Vite + vanilla JavaScript + Three.js. Use GSAP for coordinated animation timelines.

Do not migrate to React.

Start with architecture inspection and the actual backend API contract. Identify available assets, particularly the official emblem image, existing `/ask`, `/ask/stream`, and the current response format.

Implement the interface modularly.

Use actual backend data for production graph nodes and process states.

Use mock data only in a clearly identified demonstration mode.

Do not compromise data accuracy for visual effects.

Do not spend all development time polishing the initial landing screen while leaving the research experience unfinished.

The central experience is the seven-stage Legal Intelligence Graph, and the most technically distinctive interaction is the real embedding/model inspector.

**The final result should make users feel that they are exploring a sophisticated legal intelligence system—not simply chatting with an AI.**

### Definition of success

A user submits a legal question.

The Modda book opens.

The seven research stages activate.

The graph reveals the actual retrieval process.

The user can inspect the embedding, documents, ranking, and source relationships.

The LLM generates its answer.

The answer appears with verifiable Lex.uz references.

The user can navigate from any answer citation back to the exact document and graph node that supports it.

That is the complete Modda experience.