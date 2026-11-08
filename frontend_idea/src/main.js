// Modda — Legal Intelligence Graph (frontend_idea.md §0). Wires the backend, the research state machine,
// the 3-D scene (book, process graph, Lady Justice) and the HTML interface together.
import * as THREE from 'three';
import { gsap } from 'gsap';
import { REDUCED, STAGES } from './config.js';
import { createStore } from './core/store.js';
import { initial, reduce, activeStage, orderedSources } from './core/research.js';
import { createBackend } from './api/backend.js';
import { drawBackdrop } from './scene/backdrop.js';
import { answerPage, sourcePage, foundPage, coverTexture, fontsReady, setPageQuality } from './scene/pages.js';
import { GraphNodes } from './ui/nodes.js';
import { openStage } from './ui/inspectors.js';
import { openMind } from './ui/mind.js';
import { openSentences, scoreSummary } from './ui/scales.js';
import { openReader } from './ui/reader.js';
import { openDocuments } from './ui/documents.js';
import { openHelp } from './ui/help.js';
import { openPanel, closePanel, isOpen } from './ui/overlay.js';
import { toast, say } from './ui/toast.js';
import { h, kv, unavailable } from './ui/dom.js';
import * as sfx from './audio/sfx.js';

gsap.ticker.lagSmoothing(0);                         // timelines follow real time even when frames are slow
const $ = (s) => document.querySelector(s);
const body = document.body;
const form = $('.ask'), textarea = $('#question'), send = $('.ask__send');
const bookUI = $('.book-ui'), where = $('.book-ui__where');
const store = createStore(initial());
const contexts = new Map();                           // chunk_id → Promise of /chunks/{id}/context

let backend, stage = null, book = null, graph = null, justice = null, gavel = null, nodes;
let ctl = null, runId = 0, bookQueue = Promise.resolve(), sourceIndex = 1, streamTimer = 0;

// ------------------------------------------------------------------ helpers
const queueBook = (fn) => (bookQueue = bookQueue.then(fn).catch((e) => console.warn('book:', e)));
const context = (cid) => {
  if (!contexts.has(cid)) contexts.set(cid, backend.api.chunkContext(cid, 5).catch((e) => { contexts.delete(cid); throw e; }));
  return contexts.get(cid);
};
const hash01 = (s) => { let x = 7; for (const ch of String(s)) x = (x * 31 + ch.charCodeAt(0)) >>> 0; return (x % 1000) / 1000; };
const setPhaseClass = (phase) => {
  body.classList.toggle('is-idle', phase === 'idle');
  body.classList.toggle('is-research', phase === 'running');
  body.classList.toggle('is-answer', ['done', 'unknown'].includes(phase));
  body.classList.toggle('is-error', phase === 'error');
  if (body.dataset.phase !== phase) { body.dataset.phase = phase; layoutGraph(); }
};
const ctx = {
  state: () => store.get(),
  subscribe: (fn) => store.subscribe(fn),
  get backend() { return backend; },
  context,
  openMind: (which) => openMind(ctx, which),
  openScales: () => focusJustice(),
  openStage: (id) => openStage(id, ctx),
  showSource: (cid) => showSource(cid),
  openArticleInBook: (aid) => openArticleInBook(aid),
  onReaderSource: (n) => { if (book && n !== sourceIndex) goToSource(n); },
};

// ------------------------------------------------------------------ the book pages for the current state
function answerData(st, { streaming = false } = {}) {
  const a = st.answer;
  const srcs = orderedSources(a);
  const num = new Map(srcs.map((s) => [s.chunk_id, s.n]));
  if (streaming) return { question: st.question, sentences: [{ text: st.generation.text, refs: [] }], sources: [], streaming: true };
  if (!a || a.unknown) return { question: st.question, unknown: true,          // reason: the τ gate (no LLM call)
    note: a?.reason ? 'Bu savol Lex.uz’dagi hech bir moddaga yetarlicha yaqin emas — qonunchilik savoliga oʻxshamaydi. Huquqiy savol boʻlsa, hujjat yoki modda nomini qoʻshing.' : undefined };
  return {
    question: st.question,
    sentences: a.answer.map((s) => ({ text: s.text, refs: [...new Set(s.chunk_ids.map((id) => num.get(id)).filter(Boolean))] })),
    sources: srcs.map((s) => ({ n: s.n, title: s.title, article_no: s.article_no })),
    score: st.score?.score ?? null, supported: st.score?.supported, total: st.score?.total,
  };
}

async function spreadFor(st, n) {
  const left = answerPage(answerData(st));
  const srcs = orderedSources(st.answer);
  let right;
  const s = srcs[n - 1];
  const cid = s?.chunk_id ?? st.retrieval?.candidates?.[0]?.chunk_id;
  if (cid) {
    try {
      const quote = st.answer?.answer?.find((x) => x.chunk_ids.includes(cid))?.quote;
      right = sourcePage(await context(cid), { n: s ? n : null, quote, total: srcs.length, stale: s?.stale ? (s.stale_info || {}) : null });
    } catch { right = null; }
  }
  if (!right) right = sourcePage({ document: { title: s?.title || 'Manba' }, articles: s ? [{ label: s.article_no, title: s.article_title, text: s.text, is_target: true }] : [] }, { n, stale: s?.stale ? (s.stale_info || {}) : null });
  return { left: left.texture, right: right.texture, leftHits: left.hits, rightHits: right.hits };
}

function updateWhere() {
  const st = store.get();
  const total = orderedSources(st.answer).length;
  where.textContent = total ? `manba ${sourceIndex} / ${total}` : st.phase === 'unknown' ? 'javob topilmadi' : '';
  bookUI.querySelector('[data-action="page-prev"]').disabled = sourceIndex <= 1;
  bookUI.querySelector('[data-action="page-next"]').disabled = sourceIndex >= total;
}

function backToBook() {
  if (!body.classList.contains('show-graph')) return;
  body.classList.remove('show-graph');
  setNav('home');
  layoutGraph();
  stage?.setShot('answer');
}

function goToSource(n) {
  backToBook();
  const st = store.get();
  const total = orderedSources(st.answer).length;
  if (!total || n < 1 || n > total || n === sourceIndex) return;
  const dir = n > sourceIndex ? 1 : -1;
  sourceIndex = n;
  updateWhere();
  say(`Manba ${n}`);
  if (!book) return;
  queueBook(async () => book.turnTo(await spreadFor(store.get(), n), dir));
}

function showSource(cid) {
  closePanel();
  const st = store.get();
  const srcs = orderedSources(st.answer);
  const s = srcs.find((x) => x.chunk_id === cid);
  if (s) { goToSource(s.n); if (!book) openReader(ctx, s.n); return; }
  // a candidate that is not cited in the answer: show it on the right page, the answer stays on the left
  if (!book) { context(cid).then((d) => openArticlePanel(d)).catch((e) => toast(e.message, { tone: 'error' })); return; }
  queueBook(async () => {
    const d = await context(cid);
    const left = st.answer ? answerPage(answerData(st)) : foundPage({ documents: st.retrieval?.documents_found, chunks: st.retrieval?.chunks_retrieved });
    const right = sourcePage(d, {});
    await book.turnTo({ left: left.texture, right: right.texture, leftHits: left.hits, rightHits: right.hits }, 1);
    where.textContent = 'nomzod modda';
  });
}

async function openArticleInBook(aid) {
  closePanel();
  try {
    const d = await backend.api.articleContext(aid, 5);
    if (!book) { openArticlePanel(d); return; }
    const st = store.get();
    const left = st.answer ? answerPage(answerData(st)) : foundPage({ documents: 1, chunks: d.articles.length, first: d.document?.title });
    const right = sourcePage(d, {});
    queueBook(async () => {
      if (!book.isOpen) await book.landOn(hash01(aid), { left: left.texture, right: right.texture, leftHits: left.hits, rightHits: right.hits });
      else await book.turnTo({ left: left.texture, right: right.texture, leftHits: left.hits, rightHits: right.hits }, 1);
      bookUI.hidden = false; where.textContent = d.document?.title ? 'hujjat' : '';
      stage?.setShot('answer');
      body.classList.add('is-reading');
    });
  } catch (err) { toast(`Modda olinmadi: ${err.message}`, { tone: 'error' }); }
}

function openArticlePanel(d) {
  import('./ui/reader.js').then(({ sourcePageHTML }) => openPanel({ eyebrow: 'Modda', title: d.document?.title || 'Modda', body: h('div', { class: 'reader', style: { gridTemplateColumns: '1fr' } }, sourcePageHTML(d)) }));
}

// ------------------------------------------------------------------ asking
function setBusy(busy) {
  form.classList.toggle('is-busy', busy);
  send.disabled = busy;
  send.setAttribute('aria-label', busy ? 'Javob tayyorlanmoqda' : 'Savolni yuborish');
  document.querySelectorAll('.chip').forEach((c) => { c.disabled = busy; });
}

function onEvent(ev, id) {
  if (id !== runId) return;
  const before = store.get();
  store.set((s) => reduce(s, ev));
  const st = store.get();
  if (st === before) return;
  switch (ev.type) {
    case 'retrieval.completed': {
      const first = st.retrieval?.candidates?.[0];
      if (first && book) {
        context(first.chunk_id).catch(() => {});
        queueBook(async () => {
          let right;
          try { right = sourcePage(await context(first.chunk_id), {}); } catch { right = null; }
          const left = foundPage({ documents: st.retrieval.documents_found, chunks: st.retrieval.chunks_retrieved, first: `${first.doc_title}${first.article_no ? `, ${first.article_no}-modda` : ''}` });
          if (store.get().phase !== 'running' && id !== runId) return;
          await book.landOn(hash01(first.chunk_id), { left: left.texture, right: (right || left).texture, leftHits: [], rightHits: right?.hits || [] });
        });
      }
      say(`${st.retrieval?.chunks_retrieved ?? 0} ta modda topildi`);
      break;
    }
    case 'generation.delta':
      if (book && !streamTimer) {
        streamTimer = setTimeout(() => {
          streamTimer = 0;
          const cur = store.get();
          if (cur.phase !== 'running' || id !== runId) return;
          queueBook(() => { const p = answerPage(answerData(store.get(), { streaming: true })); book.replace('left', p.texture, []); });
        }, 260);
      }
      break;
    case 'answer.completed':
    case 'fallback.answer':
      finishAnswer(id);
      break;
    case 'stage.failed':
      failed(st.error?.message || 'Server xatosi', id);
      break;
    default:
  }
}

function finishAnswer(id) {
  const st = store.get();
  setBusy(false);
  sourceIndex = 1;
  if (st.score?.score != null && justice && justice.score == null) {   // the verdict: flames, scales, the gavel falls
    if (statueShown()) { sfx.flame(); sfx.scales(); }
    gavel?.strike();
  }
  justice?.setScore(st.score?.score ?? null);
  const tag = $('.justice-hit__tag');
  if (tag) tag.textContent = st.score?.score != null ? `⚖ ${Math.round(st.score.score)} / 100 · manbaga moslik` : 'Adolat tarozisi';
  updateHud();
  const srcs = orderedSources(st.answer);
  say(st.phase === 'unknown' ? 'Ishonchli javob topilmadi' : `Javob tayyor: ${srcs.length} ta manba. Javob kitobda.`);
  if (!book) { openReader(ctx, 1); return; }
  queueBook(async () => {
    if (id !== runId) return;
    const spread = await spreadFor(st, 1);
    if (!book.isOpen || book.nLeft < 3) await book.landOn(hash01(st.requestId || st.question), spread);
    else await book.turnTo(spread, 1);
    if (id !== runId) return;
    if (!body.classList.contains('show-graph')) stage.setShot('answer', 1.3);
    bookUI.hidden = false;
    updateWhere();
  });
}

function failed(message, id) {
  if (id !== runId) return;
  setBusy(false);
  book?.stopRiffle();
  stage?.setActivity(0);
  toast(`Xato: ${message}`, { tone: 'error', timeout: 0, actions: [['Qayta urinish', () => ask(store.get().question)], ['Yopish', () => {}]] });
  say(`Xato: ${message}`);
}

async function ask(question) {
  const q = String(question || '').trim();
  if (q.length < 2) { textarea.focus(); toast('Savol kamida 2 belgidan iborat boʻlsin.', { tone: 'warn' }); return; }
  if (form.classList.contains('is-busy')) return;
  unfocusJustice();
  ctl?.abort();
  ctl = new AbortController();
  const id = ++runId;
  closePanel();
  contexts.clear();
  body.classList.remove('show-graph');
  store.set(initial(q));
  store.set((s) => ({ ...s, phase: 'running' }));
  sourceIndex = 1;
  bookUI.hidden = true;
  body.classList.remove('is-reading');
  $('.query-title__text').textContent = q;
  $('.query-title').hidden = false;
  setBusy(true);
  justice?.setScore(null);
  { const tag = $('.justice-hit__tag'); if (tag) tag.textContent = 'Adolat tarozisi'; }
  if (book) {
    stage.setShot('research', 1.1);
    queueBook(async () => { if (book.isOpen && book.nLeft > 3) await book.close(); book.beginSearch(); });
  }
  say('Savol yuborildi. Tadqiqot boshlandi.');
  try {
    await backend.askStream(q, (ev) => onEvent(ev, id), ctl.signal);
    const st = store.get();
    if (id === runId && st.phase === 'running') failed('Javob kelmadi', id);
  } catch (err) {
    if (ctl.signal.aborted && id !== runId) return;
    if (err?.name === 'AbortError') return;
    store.set((s) => reduce(s, { type: 'stage.failed', ts: new Date().toISOString(), data: { stage: 'network', message: err.message } }));
    failed(err.message, id);
  }
}

// ------------------------------------------------------------------ Lady Justice in focus (her scales show the score)
const hud = $('.justice-hud');
let beforeFocus = null;
function updateHud() {
  const s = scoreSummary(store.get());
  hud.querySelector('.justice-hud__score b').textContent = s.score == null ? '—' : String(Math.round(s.score));
  hud.querySelector('.justice-hud__line').textContent = s.line;
  hud.querySelector('[data-action="sentences"]').disabled = s.score == null;
}
function focusJustice() {
  if (!stage || !justice) { openSentences(ctx); return; }          // no 3-D: the sentence list only
  closePanel();
  if (!body.classList.contains('is-justice')) beforeFocus = stage.shotName === 'custom' ? 'idle' : stage.shotName;
  body.classList.add('is-justice');
  justice.group.visible = true;
  justice.setFocus(true);
  sfx.flameLoop(true);                                              // the flames burn brightest here — and are heard
  graph.group.visible = false;                                      // nothing in front of / around her
  const s = justice.focusShot(stage.layoutKind);
  stage.flyTo(s.pos, s.look, 1.5);
  updateHud();
  hud.hidden = false;
  say(`Adolat tarozisi. ${hud.querySelector('.justice-hud__line').textContent}`);
  setTimeout(() => hud.querySelector('[data-action="unfocus"]').focus({ preventScroll: true }), 50);
}
function unfocusJustice() {
  if (!body.classList.contains('is-justice')) return;
  body.classList.remove('is-justice');
  hud.hidden = true;
  justice.setFocus(false);
  sfx.flameLoop(false);
  graph.group.visible = true;
  justice.group.visible = statueShown();
  stage.setShot(beforeFocus || 'idle', 1.3);
  $('.justice-hit').focus?.({ preventScroll: true });
}

function home() {
  unfocusJustice();
  ctl?.abort();
  runId++;
  closePanel();
  setBusy(false);
  body.classList.remove('show-graph');
  store.set(initial());
  $('.query-title').hidden = true;
  bookUI.hidden = true;
  body.classList.remove('is-reading');
  justice?.setScore(null);
  { const tag = $('.justice-hit__tag'); if (tag) tag.textContent = 'Adolat tarozisi'; }
  if (book) { stage.setShot('idle', 1.1); queueBook(() => book.close()); }
  textarea.value = ''; autosize();
  setNav('home');
}

function setNav(name) {
  document.querySelectorAll('.nav__item').forEach((b) => {
    const on = b.dataset.action === name;
    b.classList.toggle('is-active', on);
    if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
}

// ------------------------------------------------------------------ status badge (real /health only)
async function refreshHealth() {
  const badge = $('.status'), text = $('.status__text');
  if (backend.demo) { badge.dataset.state = 'demo'; text.textContent = 'Namuna rejimi'; return; }
  try {
    const hh = await backend.api.health();
    ctx.health = hh;
    const ready = hh.ready ?? true;
    badge.dataset.state = ready ? 'ok' : 'degraded';
    text.textContent = ready ? 'Onlayn' : 'Qisman ishlaydi';
  } catch (err) {
    ctx.health = { error: err.message };
    badge.dataset.state = 'offline';
    text.textContent = 'Oflayn';
  }
}
function openStatus() {
  const hh = ctx.health || {};
  const svc = hh.services || {};
  const line = (name, s) => [name, s ? (s.ok ? `ishlayapti${s.version ? ` · v${s.version}` : ''}` : `ishlamayapti — ${s.error || ''}`) : 'nomaʼlum'];
  openPanel({ eyebrow: 'Tizim holati', title: hh.error ? 'Server bilan aloqa yoʻq' : 'Xizmatlar', narrow: true, label: 'Tizim holati',
    body: h('div', {}, hh.error ? unavailable(`${hh.error}. «python -m modda serve» ishlayaptimi?`) : kv([
      ['API', 'ishlayapti'], line('Ollama', svc.ollama), line('Qdrant', svc.qdrant),
      ['Indeks', hh.dense_indexed != null ? `${hh.dense_indexed.toLocaleString()} dense / ${hh.chunks?.toLocaleString()} boʻlak` : '—'],
      ['Model', hh.llm], ['Embedding', hh.embed], ['Maʼlumotlar sanasi', hh.checked_at]]),
    h('button', { type: 'button', class: 'btn', style: { marginTop: '14px' }, onclick: () => { refreshHealth().then(openStatus); } }, 'Qayta tekshirish')) });
}

// ------------------------------------------------------------------ input
function autosize() {
  textarea.style.height = 'auto';
  textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
}
textarea.addEventListener('input', autosize);
textarea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
});
form.addEventListener('submit', (e) => { e.preventDefault(); ask(textarea.value); });
document.querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { textarea.value = c.dataset.topic; autosize(); ask(c.dataset.topic); }));

document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-action]');
  if (!a) return;
  switch (a.dataset.action) {
    case 'home': home(); break;
    case 'graph': {
      setNav('graph');
      const st = store.get();
      body.classList.add('show-graph');
      layoutGraph();
      if (stage) stage.setShot(st.phase === 'idle' ? 'idle' : 'research', 1);
      body.classList.remove('is-reading');
      bookUI.hidden = !['done', 'unknown'].includes(st.phase);
      const act = activeStage(st) || (st.phase === 'idle' ? null : STAGES[0].id);
      (act ? document.querySelector(`.node[data-node="${act}"]`) : document.querySelector('.mind'))?.focus();
      if (st.phase === 'idle') toast('Graf hozir kutish holatida. Savol yuborsangiz, bosqichlar haqiqiy maʼlumot bilan yonadi.');
      break;
    }
    case 'documents': setNav('documents'); openDocuments(ctx); break;
    case 'help': openHelp(); break;
    case 'status': openStatus(); break;
    case 'sound': sfx.setMuted(!sfx.isMuted()); break;
    case 'scales': focusJustice(); break;
    case 'unfocus': unfocusJustice(); break;
    case 'sentences': openSentences(ctx); break;
    case 'page-prev': goToSource(sourceIndex - 1); break;
    case 'page-next': goToSource(sourceIndex + 1); break;
    case 'reader': backToBook(); openReader(ctx, sourceIndex); break;
    case 'new': textarea.focus(); textarea.select(); break;
    default:
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !isOpen() && body.classList.contains('is-justice')) { unfocusJustice(); return; }
  if (isOpen() || e.target.closest('textarea, input, select')) return;
  if (!['done', 'unknown'].includes(store.get().phase)) return;
  if (e.key === 'ArrowRight') goToSource(sourceIndex + 1);
  if (e.key === 'ArrowLeft') goToSource(sourceIndex - 1);
});

// ------------------------------------------------------------------ scene
// graph size/position per screen and mode: smaller and higher while the answer is read in the book
const GRAPH = {
  desktop: { shape: [1.85, 0.56], normal: { scale: 1, cy: 1.75 }, answer: { scale: 0.72, cy: 1.5 } },
  tablet: { shape: [1.85, 0.75], normal: { scale: 0.75, cy: 2.3 }, answer: { scale: 0.6, cy: 2.3 } },
  mobile: { shape: [1.85, 1.3], normal: { scale: 0.62, cy: 2.45 }, answer: { scale: 0.5, cy: 2.75 } },
};
const statueShown = () => stage.layoutKind === 'desktop' || (stage.layoutKind === 'tablet' && stage.width / stage.height > 1.2);
function layoutGraph(duration = 1.1) {
  if (!graph) return;
  const answer = body.classList.contains('is-answer') && !body.classList.contains('show-graph');
  const g = GRAPH[stage.layoutKind];
  graph.setShape(...g.shape);
  graph.setLayout({ ...g[answer ? 'answer' : 'normal'], duration });
  justice?.setMode(answer, duration);
  gavel?.setMode(answer, duration);
}

function setupScene({ Stage, Book, Graph, Justice, Gavel }) {
  const canvas = $('#scene');
  stage = new Stage(canvas, { reducedMotion: REDUCED });
  {                                                                   // page texture sharpness (before the book is made)
    const caps = stage.renderer.capabilities, w = window.innerWidth;
    const scale = /[?&]quality=low/.test(location.search) ? 1 : w < 768 ? 1.25 : w < 1100 ? 1.5 : caps.maxTextureSize >= 4096 ? 2 : 1.5;
    setPageQuality({ scale, anisotropy: Math.min(16, caps.getMaxAnisotropy()) });
  }
  book = new Book(stage.scene, { reducedMotion: REDUCED, envMap: stage.env });
  graph = new Graph(stage.scene, { reducedMotion: REDUCED });
  justice = new Justice(stage.scene, { envMap: stage.env, reducedMotion: REDUCED });
  justice.camera = stage.camera;
  gavel = new Gavel(stage.scene, { envMap: stage.env, reducedMotion: REDUCED });
  gavel.onImpact = (n) => { if (n === 1 && gavel.group.visible) sfx.gavel(); };   // the file holds both strikes
  book.onSound = (kind, o) => (kind === 'page' ? sfx.page(o) : sfx.book({ close: kind === 'close' }));
  const pos = {}, tmp = { x: 0, y: 0, visible: false };
  const hit = $('.justice-hit');
  const ids = ['mind', ...STAGES.map((s) => s.id)];
  stage.onResize = () => {
    layoutGraph(0);
    justice.group.visible = statueShown() || body.classList.contains('is-justice');
    gavel.group.visible = statueShown();
    body.classList.toggle('no-statue', !statueShown());
    if (body.classList.contains('is-justice')) { const s = justice.focusShot(stage.layoutKind); stage.flyTo(s.pos, s.look, 0.3); }
    drawBackdrop($('#backdrop'));
  };
  stage.onResize();
  stage.onFrame.push((dt, t) => {
    book.update(dt); graph.update(dt); justice.update(dt, t); gavel.update(dt, t);
    for (const id of ids) { const p = stage.project(graph.anchor(id), tmp); pos[id] = { x: p.x, y: p.y }; }
    nodes.position(pos);
    if (justice.group.visible && !body.classList.contains('is-justice')) {
      const b = justice.screenBox(stage);
      hit.style.width = `${b.w}px`; hit.style.height = `${b.h}px`;
      hit.style.setProperty('--x', `${(b.x - b.w / 2).toFixed(1)}px`); hit.style.setProperty('--y', `${b.y.toFixed(1)}px`);
      hit.hidden = false;
    } else hit.hidden = true;
  });
  // clicks on the open pages: [n] references turn to that source; article lines open that article
  const ray = new THREE.Raycaster(), m = new THREE.Vector2();
  const pickAt = (e) => {
    const r = canvas.getBoundingClientRect();
    m.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(m, stage.camera);
    return book.pick(ray);
  };
  canvas.addEventListener('pointermove', (e) => {
    const p = pickAt(e);
    canvas.style.cursor = p?.hit || gavel.pick(ray) ? 'pointer' : '';
  });
  canvas.addEventListener('click', (e) => {
    const p = pickAt(e);
    if (!p?.hit && gavel.pick(ray)) { gavel.strike(); return; }
    if (!p) return;
    if (p.hit?.scales) ctx.openScales();                               // the seal on the answer page → the statue
    else if (p.hit?.ref) goToSource(p.hit.ref);
    else if (p.hit?.target || (p.side === 'right' && !p.hit && orderedSources(store.get().answer).length)) openReader(ctx, sourceIndex);
    else if (p.hit?.article) openArticleInBook(p.hit.article);
    else if (p.side === 'left' && store.get().answer) openReader(ctx, sourceIndex);
  });
  store.subscribe((st) => {
    graph.setStatuses(Object.fromEntries(STAGES.map((s) => [s.id, st.stages[s.id].status])), activeStage(st));
    stage.setActivity(st.phase === 'running' ? 1 : 0);
  });
}

function setupFallback() {
  body.classList.add('no-webgl');
  const img = h('img', { class: 'fallback-book', alt: 'Modda kitobi: Oʻzbekiston Respublikasi qonunchiligi' });
  coverTexture((c) => { img.src = c.toDataURL('image/jpeg', 0.85); });
  body.append(img);
  const ring = () => nodes.ring($('.graph').getBoundingClientRect());
  window.addEventListener('resize', ring); ring();
  drawBackdrop($('#backdrop'));
  window.addEventListener('resize', () => drawBackdrop($('#backdrop')));
}

// ------------------------------------------------------------------ start
async function start() {
  backend = await createBackend();
  if (backend.demo) {
    body.classList.add('is-demo'); $('.demo-banner').hidden = false;
    const when = String(backend.recorded || '').slice(0, 16).replace('T', ' ');
    if (when) $('.demo-banner').textContent = `Namuna rejimi — jonli backend emas: ${when} da yozib olingan haqiqiy javob${backend.note ? ` (${backend.note.split(',')[0]})` : ''}. Savol: «${backend.question}».`;
  }
  nodes = new GraphNodes($('.graph'), { onOpen: (id) => (id === 'mind' ? openMind(ctx, 'llm') : openStage(id, ctx)) });
  store.subscribe((st) => { nodes.update(st); setPhaseClass(st.phase); });
  nodes.update(store.get());
  await fontsReady();
  const { hasWebGL, Stage } = await import('./scene/stage.js');
  if (hasWebGL() && !new URLSearchParams(location.search).has('nowebgl')) {
    const [{ Book }, { Graph }, { Justice }, { Gavel }] = await Promise.all([import('./scene/book.js'), import('./scene/graph.js'), import('./scene/justice.js'), import('./scene/gavel.js')]);
    try { setupScene({ Stage, Book, Graph, Justice, Gavel }); } catch (err) { console.warn('WebGL scene failed, using the plain layout', err); stage = book = graph = justice = gavel = null; setupFallback(); }
  } else setupFallback();
  refreshHealth();
  setInterval(refreshHealth, 60000);
  sfx.initSound();
  const soundBtn = $('.sound');
  const showSound = (m) => { if (!soundBtn) return; soundBtn.setAttribute('aria-pressed', String(!m)); soundBtn.setAttribute('aria-label', m ? 'Ovoz: oʻchirilgan' : 'Ovoz: yoqilgan'); };
  showSound(sfx.isMuted()); sfx.onMuteChange(showSound);
  window.__modda = { store, get state() { return store.get(); }, ask, goToSource, get sourceIndex() { return sourceIndex; }, get gavel() { return gavel; }, sfx };
  body.classList.add('is-ready');
}
start();
