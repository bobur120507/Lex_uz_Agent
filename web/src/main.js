// State machine: idle → search (book opens, pages riffle) → answer (book lands on the article) | unknown | error
import './styles.css';
import { Stage, hasWebGL } from './scene/stage.js';
import { Book } from './scene/book.js';
import { fontsReady } from './scene/textures.js';
import { ask, health, usingMock } from './api.js';
import { EXAMPLES } from './mock.js';
import { renderAnswer, renderError, renderUnknown, uzDate } from './ui/answer.js';

const $ = (s) => document.querySelector(s);
const params = new URLSearchParams(location.search);
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const MIN_SEARCH_MS = REDUCED ? 0 : 1200;

const body = document.body;
const form = $('#ask'), input = $('#q'), btn = $('#ask-btn');
const panel = $('#panel'), steps = $('#steps'), cands = $('#cands'), skip = $('#skip');
const statusText = $('#status-text');

let stage = null, book = null, controller = null, lastQ = '';

function setState(s) { body.dataset.state = s; }

// ------------------------------------------------------------------ 3D or fallback
if (hasWebGL() && !params.has('flat')) {
  stage = new Stage($('#scene'), { reducedMotion: REDUCED });
  book = new Book(stage.scene, { reducedMotion: REDUCED });
  stage.onFrame.push((dt) => book.update(dt));
  if (params.has('debug')) {
    window.__modda = { book, stage };
    const f = $('#fps'); f.hidden = false;
    stage.onFps = (n) => { f.textContent = `${n} kadr/s`; };
  }
} else {
  body.classList.add('flat');                       // 2D mode: same panel, no canvas
}

// ------------------------------------------------------------------ examples, input
for (const ex of EXAMPLES) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'example';
  b.innerHTML = '<span class="ex-q"></span><span class="ex-h"></span>';
  b.querySelector('.ex-q').textContent = ex.text;
  b.querySelector('.ex-h').textContent = ex.hint;
  b.addEventListener('click', () => { input.value = ex.text; submit(ex.text); });
  $('#examples').append(b);
}
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});
input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; });
form.addEventListener('submit', (e) => { e.preventDefault(); submit(input.value); });

// ------------------------------------------------------------------ steps text
const STEP_TEXT = { retrieving: 'Moddalar qidirilmoqda', generating: 'Javob yozilmoqda', verifying: 'Iqtiboslar tekshirilmoqda' };
function setStep(name) {
  steps.querySelectorAll('li').forEach((li) => {
    const order = Object.keys(STEP_TEXT);
    const i = order.indexOf(li.dataset.step), j = order.indexOf(name);
    li.classList.toggle('done', i < j);
    li.classList.toggle('on', i === j);
  });
}
function showCandidates(list) {
  cands.replaceChildren();
  list.slice(0, 5).forEach((c, i) => {
    const li = document.createElement('li');
    li.style.setProperty('--i', i);
    li.dataset.id = c.chunk_id;
    li.textContent = `${c.article_no}-modda. ${c.article_title || ''}`;
    cands.append(li);
  });
}
function markBest(order) {
  cands.querySelectorAll('li').forEach((li) => {
    li.classList.toggle('best', li.dataset.id === order[0]);
    li.classList.toggle('weak', li.dataset.id !== order[0]);
  });
}

// place in the book: stable per article, so the same article always opens at the same page
function positionOf(id) {
  let h = 2166136261;
  for (const ch of id) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}

// ------------------------------------------------------------------ flow
async function submit(question) {
  question = question.trim();
  if (!question) return;
  lastQ = question;
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  const t0 = performance.now();
  setState('search');
  btn.disabled = true;
  panel.hidden = true;
  cands.replaceChildren();
  setStep('retrieving');
  if (book) {
    book.speed = 1;
    stage.setShot('search');
    book.beginSearch();
  }

  let result = null;
  try {
    await ask(question, (ev, data) => {
      if (signal.aborted) return;
      if (ev === 'stage') setStep(data.name);
      if (ev === 'candidates') showCandidates(data);
      if (ev === 'reranked') markBest(data.order);
      if (ev === 'answer') result = data;
    }, signal);
    if (usingMock) statusText.textContent = 'Namuna rejimi';
    const wait = MIN_SEARCH_MS - (performance.now() - t0);
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    if (signal.aborted) return;
    if (!result || result.unknown || !result.answer?.length) await showUnknown(question);
    else await showAnswer(question, result);
  } catch (err) {
    if (err.name === 'AbortError') return;
    console.warn('Modda:', err);
    setState('error');
    if (book) { book.close(); stage.setShot('closed'); }
    panel.hidden = false;
    renderError(panel, () => submit(lastQ));
  } finally {
    btn.disabled = false;
  }
}

async function showAnswer(question, data) {
  const firstId = data.answer[0].chunk_ids.find((id) => data.sources[id]);
  const src = data.sources[firstId];
  if (book) {
    await book.landOn({
      position: positionOf(firstId),
      articleNo: src.article_no, articleTitle: src.article_title, text: src.text,
      quote: data.answer.find((a) => a.chunk_ids.includes(firstId))?.quote,
      docTitle: src.title, docLine: [src.doc_type, src.doc_number].filter(Boolean).join(', '),
      chapter: src.chapter,
    });
    stage.setShot('side', 0.9);
  }
  setState('answer');
  panel.hidden = false;
  renderAnswer(panel, question, data);
}

async function showUnknown(question) {
  if (book) { await book.close(); stage.setShot('closed'); }
  setState('unknown');
  panel.hidden = false;
  renderUnknown(panel, question);
}

skip.addEventListener('click', () => { if (book) { book.speed = 6; } });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && body.dataset.state === 'search' && book) book.speed = 6; });

// ------------------------------------------------------------------ start
setState('idle');
fontsReady().then(() => {});
health().then((h) => {
  statusText.textContent = h?.checked_at ? `Baza ${uzDate(h.checked_at)} holatida` : (usingMock ? 'Namuna rejimi' : 'Server ulangan');
  if (params.get('q')) { input.value = params.get('q'); submit(input.value); }
});
