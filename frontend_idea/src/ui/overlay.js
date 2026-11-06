// One dialog system for every inspector, the reader, documents and help: modal, focus-trapped, Esc closes,
// focus returns to the control that opened it. Only one panel is open at a time.
import { h } from './dom.js';

let current = null;

export function closePanel() {
  if (!current) return;
  const c = current; current = null;
  c.cleanup.forEach((fn) => { try { fn(); } catch { /* already gone */ } });
  c.root.remove();
  document.body.classList.remove('has-overlay');
  c.opener?.focus?.({ preventScroll: true });
  c.onClose?.();
}

export function openPanel({ eyebrow = '', title, icon = '', tools = [], body, narrow = false, label, onClose } = {}) {
  const opener = document.activeElement;
  closePanel();
  const cleanup = [];
  const closeBtn = h('button', { type: 'button', class: 'panel__close', 'aria-label': 'Yopish', onclick: () => closePanel() }, '✕');
  const titleId = `panel-${Math.random().toString(36).slice(2, 8)}`;
  const panel = h('div', { class: `panel${narrow ? ' panel--narrow' : ''}`, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': titleId, 'aria-label': label },
    h('header', { class: 'panel__head' },
      icon ? h('span', { class: 'panel__icon', 'aria-hidden': 'true', html: icon }) : null,
      h('div', { class: 'panel__title' }, eyebrow ? h('div', { class: 'panel__eyebrow' }, eyebrow) : null, h('h2', { id: titleId }, title)),
      h('div', { class: 'panel__tools' }, tools), closeBtn),
    h('div', { class: 'panel__body' }, body));
  const root = h('div', { class: 'overlay', onmousedown: (e) => { if (e.target === root) closePanel(); } }, panel);
  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); closePanel(); return; }
    if (e.key !== 'Tab') return;
    const f = [...panel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter((x) => !x.disabled && x.offsetParent !== null);
    if (!f.length) return;
    const first = f[0], last = f.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  document.addEventListener('keydown', onKey);
  cleanup.push(() => document.removeEventListener('keydown', onKey));
  document.getElementById('overlays').append(root);
  document.body.classList.add('has-overlay');
  current = { root, cleanup, opener, onClose };
  requestAnimationFrame(() => closeBtn.focus({ preventScroll: true }));
  return { root, panel, body: panel.querySelector('.panel__body'), onCleanup: (fn) => cleanup.push(fn), close: closePanel };
}

export const isOpen = () => !!current;
