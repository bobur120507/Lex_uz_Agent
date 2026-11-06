import { h } from './dom.js';

export function toast(message, { tone = 'info', actions = [], timeout = 7000 } = {}) {
  const box = document.querySelector('.toasts');
  const el = h('div', { class: `toast toast--${tone}`, role: tone === 'error' ? 'alert' : 'status' }, message,
    actions.length ? h('div', { class: 'toast__actions' }, actions.map(([label, fn]) => h('button', { type: 'button', class: 'btn btn--sm', onclick: () => { el.remove(); fn(); } }, label))) : null);
  box.append(el);
  if (timeout) setTimeout(() => el.remove(), timeout);
  return el;
}
export const say = (text) => { const live = document.getElementById('live'); if (live) { live.textContent = ''; requestAnimationFrame(() => { live.textContent = text; }); } };
