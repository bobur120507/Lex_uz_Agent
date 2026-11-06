// The book's pages as plain HTML (screen readers, copying, small screens, no-WebGL): the answer with its
// references on the left, the selected source among its ±5 neighbouring moddas on the right.
import { DISCLAIMER, UNKNOWN_TEXT, ICONS } from '../config.js';
import { orderedSources } from '../core/research.js';
import { stripRefs } from '../scene/pages.js';
import { openPanel } from './overlay.js';
import { h, unavailable, copyText } from './dom.js';
import { toast } from './toast.js';

function markQuote(text, quote) {
  const q = (quote || '').trim();
  const at = q.length > 8 ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return [text];
  return [text.slice(0, at), h('mark', {}, text.slice(at, at + q.length)), text.slice(at + q.length)];
}

export function articleBlock(a, quote) {
  const head = `${a.label ? `${a.label}-modda. ` : ''}${a.title || ''}`.trim();
  return h('article', { class: `reader__art${a.is_target ? ' is-target' : ''}`, 'aria-current': a.is_target ? 'true' : null },
    a.is_target ? [h('h4', {}, head), ...String(a.text || '').split('\n').filter(Boolean).map((p) => h('p', {}, ...markQuote(p, quote)))] : h('span', {}, head));
}

export function sourcePageHTML(ctxData, { n, total, quote } = {}) {
  const d = ctxData.document || {};
  return h('section', { class: 'reader__page', 'aria-label': 'Manba' },
    h('h3', {}, n ? `Manba [${n}]${total ? ` / ${total}` : ''}` : 'Modda'),
    h('h4', {}, d.title || ''),
    (ctxData.articles || []).map((a) => articleBlock(a, quote)),
    d.url ? h('p', { class: 'reader__disc' }, h('a', { href: d.url, target: '_blank', rel: 'noopener' }, 'Lex.uz’da ochish ↗'), d.version_date ? ` · tahrir: ${d.version_date}` : '') : null);
}

export function answerPageHTML(state, onRef) {
  const a = state.answer;
  const srcs = orderedSources(a);
  const num = new Map(srcs.map((s) => [s.chunk_id, s.n]));
  const page = h('section', { class: 'reader__page', 'aria-label': 'Javob' }, h('h3', {}, 'Javob'),
    h('p', { style: { fontStyle: 'italic', color: '#5c645d' } }, `«${state.question}»`));
  if (!a || a.unknown) {
    page.append(h('p', {}, h('b', {}, UNKNOWN_TEXT)), h('p', {}, 'Savolni aniqroq yozing: hujjat nomi yoki modda raqamini qoʻshing.'));
  } else {
    for (const s of a.answer) {
      page.append(h('p', {}, stripRefs(s.text), ' ', [...new Set(s.chunk_ids.map((id) => num.get(id)).filter(Boolean))].map((n) =>
        h('button', { type: 'button', class: 'ref', 'aria-label': `Manba ${n}`, onclick: () => onRef(n) }, `[${n}]`))));
    }
    page.append(h('h3', { style: { marginTop: '22px' } }, 'Manbalar'),
      h('ol', { class: 'reader__src' }, srcs.map((s) => h('li', {}, h('button', { type: 'button', class: 'ref', onclick: () => onRef(s.n) }, `[${s.n}]`), ' ',
        `${s.title}${s.article_no ? `, ${s.article_no}-modda` : ''}`, s.url ? [' · ', h('a', { href: s.url, target: '_blank', rel: 'noopener' }, 'Lex.uz ↗')] : null,
        s.stale ? h('span', { style: { color: '#a06a1e' } }, ' · oʻzgargan boʻlishi mumkin') : null))));
  }
  page.append(h('p', { class: 'reader__disc' }, DISCLAIMER));
  return page;
}

/** Opens the reader at source n (1-based). loadContext(chunk_id) → Promise of /chunks/{id}/context. */
export function openReader(ctx, n = 1) {
  const state = ctx.state();
  const srcs = orderedSources(state.answer);
  let cur = Math.min(Math.max(1, n), Math.max(1, srcs.length));
  const right = h('div', {});
  const where = h('span', { class: 'pager' });
  const spread = h('div', { class: 'reader' }, answerPageHTML(state, (k) => go(k)), right);
  const go = async (k) => {
    cur = k;
    where.textContent = srcs.length ? `manba ${cur} / ${srcs.length}` : '';
    const s = srcs[cur - 1];
    if (!s) { right.replaceChildren(h('section', { class: 'reader__page' }, h('h3', {}, 'Manba'), h('p', {}, 'Bu javobda manba yoʻq.'))); return; }
    right.replaceChildren(h('section', { class: 'reader__page' }, h('p', {}, 'Yuklanmoqda…')));
    try {
      const d = await ctx.context(s.chunk_id);
      const quote = state.answer.answer.find((x) => x.chunk_ids.includes(s.chunk_id))?.quote;
      right.replaceChildren(sourcePageHTML(d, { n: cur, total: srcs.length, quote }));
    } catch (err) {
      right.replaceChildren(h('section', { class: 'reader__page' }, h('h3', {}, `Manba [${cur}]`), h('h4', {}, s.title), h('p', {}, s.text || ''),
        unavailable(`Qoʻshni moddalar olinmadi: ${err.message}`)));
    }
    ctx.onReaderSource?.(cur);
  };
  const tools = [
    h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Oldingi manba', onclick: () => cur > 1 && go(cur - 1) }, '◀'), where,
    h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Keyingi manba', onclick: () => cur < srcs.length && go(cur + 1) }, '▶'),
    h('button', { type: 'button', class: 'btn btn--sm', onclick: () => copyText(citationText(state)).then(() => toast('Javob manbalari bilan nusxalandi')) }, 'Iqtibosni nusxalash'),
  ];
  openPanel({ eyebrow: 'Kitob', title: 'Javob va manbalar', icon: ICONS.read || '', tools, body: spread, label: 'Kitobni oʻqish' });
  go(cur);
}

export function citationText(state) {
  const a = state.answer;
  if (!a || a.unknown) return `${state.question}\n\n${UNKNOWN_TEXT}`;
  const srcs = orderedSources(a);
  const num = new Map(srcs.map((s) => [s.chunk_id, s.n]));
  const body = a.answer.map((s) => `${stripRefs(s.text)} ${[...new Set(s.chunk_ids.map((id) => num.get(id)).filter(Boolean))].map((n) => `[${n}]`).join('')}`).join(' ');
  const list = srcs.map((s) => `[${s.n}] ${s.title}${s.article_no ? `, ${s.article_no}-modda` : ''}${s.url ? ` — ${s.url}` : ''}`).join('\n');
  return `${state.question}\n\n${body}\n\nManbalar:\n${list}\n\n${DISCLAIMER}`;
}
