// The exact embedding as a 32 × 32 grid (dimension i at row ⌊i/32⌋, column i mod 32).
// Colour: negative → cyan, positive → gold; brightness ∝ |value| / max|value|. Hover shows the exact float.
import { h } from '../ui/dom.js';

export function heatmap(vector, { onSelect } = {}) {
  const n = vector.length, cols = Math.ceil(Math.sqrt(n)), rows = Math.ceil(n / cols);
  const cell = 14, pad = 1;
  const c = h('canvas', { width: cols * cell, height: rows * cell, role: 'img', 'aria-label': `Embedding vektorining ${n} ta qiymati issiqlik xaritasi sifatida` });
  const tip = h('div', { class: 'viz__tip', hidden: true });
  const wrap = h('div', { class: 'viz', style: { aspectRatio: `${cols} / ${rows}`, maxWidth: '520px' } }, c, tip);
  const ctx = c.getContext('2d');
  const max = Math.max(...vector.map(Math.abs)) || 1;
  let selected = -1;
  const draw = () => {
    ctx.fillStyle = '#060b0a'; ctx.fillRect(0, 0, c.width, c.height);
    for (let i = 0; i < n; i++) {
      const v = vector[i], k = Math.min(1, Math.abs(v) / max);
      const [r, g, b] = v >= 0 ? [214, 182, 109] : [101, 216, 238];
      ctx.fillStyle = `rgba(${r},${g},${b},${0.08 + 0.92 * Math.pow(k, 0.7)})`;
      ctx.fillRect((i % cols) * cell + pad, Math.floor(i / cols) * cell + pad, cell - pad * 2, cell - pad * 2);
    }
    if (selected >= 0) {
      ctx.strokeStyle = '#f0f2ed'; ctx.lineWidth = 2;
      ctx.strokeRect((selected % cols) * cell + 0.5, Math.floor(selected / cols) * cell + 0.5, cell - 1, cell - 1);
    }
  };
  draw();
  const at = (e) => {
    const r = c.getBoundingClientRect();
    const x = Math.floor(((e.clientX - r.left) / r.width) * cols), y = Math.floor(((e.clientY - r.top) / r.height) * rows);
    const i = y * cols + x;
    return i >= 0 && i < n && x < cols ? i : -1;
  };
  c.addEventListener('mousemove', (e) => {
    const i = at(e);
    if (i < 0) { tip.hidden = true; return; }
    const r = wrap.getBoundingClientRect();
    tip.hidden = false; tip.textContent = `embedding[${i}] = ${vector[i].toFixed(6)}`;
    tip.style.left = `${e.clientX - r.left}px`; tip.style.top = `${e.clientY - r.top}px`;
  });
  c.addEventListener('mouseleave', () => { tip.hidden = true; });
  c.addEventListener('click', (e) => { const i = at(e); if (i >= 0) { selected = i; draw(); onSelect?.(i); } });
  return { el: wrap, select(i) { selected = i; draw(); } };
}
