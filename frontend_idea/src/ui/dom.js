// Tiny DOM helpers. Text always goes through textContent (never innerHTML) unless it is our own static SVG.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;                 // only for trusted, static markup (icons)
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
export const fmtMs = (ms) => (!Number.isFinite(ms) ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`);
export const fmtNum = (n, d = 0) => (Number.isFinite(n) ? n.toLocaleString('uz-UZ', { maximumFractionDigits: d, minimumFractionDigits: d }) : '—');
export const fmtBig = (n) => (!Number.isFinite(n) ? '—' : n >= 1e9 ? `${(n / 1e9).toFixed(2)} mlrd` : n >= 1e6 ? `${(n / 1e6).toFixed(1)} mln` : fmtNum(n));
export function kv(items) {
  return h('dl', { class: 'kv' }, items.filter(Boolean).map(([k, v, sub]) => h('div', {}, h('dt', {}, k), h('dd', {}, v ?? '—', sub ? h('small', {}, ` ${sub}`) : null))));
}
export const unavailable = (text) => h('div', { class: 'unavailable', role: 'note' }, text);
export const tag = (text, tone = '') => h('span', { class: `tag${tone ? ` tag--${tone}` : ''}` }, text);
export function card(title, ...body) {
  const [main, small] = Array.isArray(title) ? title : [title, null];
  return h('section', { class: 'card' }, h('h3', {}, main, small ? h('small', {}, small) : null), ...body);
}
export function copyText(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  const ta = h('textarea', { style: { position: 'fixed', opacity: '0' } }, text);
  document.body.append(ta); ta.select();
  try { document.execCommand('copy'); } finally { ta.remove(); }
  return Promise.resolve();
}
