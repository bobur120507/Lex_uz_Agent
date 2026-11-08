// Reciprocal Rank Fusion, drawn (v3): the dense list (left) and the BM25 list (right), real ranks and scores from
// the backend, joined by gradient ribbons to the fused order (centre). Kept passages glow emerald and their
// ribbons carry moving light; rejected ones stay dim. Score bars are scaled within each column.
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, text) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
};
let uid = 0;

export function rankFlow({ dense = [], sparse = [], fused = [], selected = [], label = (id) => id }) {
  const N = 10, rowH = 34, top = 50, colW = 250, gapW = 130, W = colW * 3 + gapW * 2, H = top + N * rowH + 14;
  const id = `rf${++uid}`;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', class: 'rankflow', 'aria-label': 'Dense, BM25 va birlashtirilgan tartib' });
  const defs = el('defs');
  const grad = (name, a, b) => {
    const g = el('linearGradient', { id: `${id}-${name}`, x1: '0', x2: '1', y1: '0', y2: '0' });
    g.append(el('stop', { offset: '0', 'stop-color': a }), el('stop', { offset: '1', 'stop-color': b }));
    defs.append(g);
  };
  grad('dense', '#5fe1f5', '#e8c477'); grad('bm25', '#e8c477', '#78aef0'); grad('keep', '#39e0a6', '#9af5d2');
  grad('pill', 'rgba(255,255,255,0.055)', 'rgba(255,255,255,0.015)'); grad('pillOn', 'rgba(57,224,166,0.22)', 'rgba(57,224,166,0.05)');
  const glow = el('filter', { id: `${id}-glow`, x: '-20%', y: '-50%', width: '140%', height: '200%' });
  glow.append(el('feGaussianBlur', { stdDeviation: '3.2', result: 'b' }));
  const merge = el('feMerge'); merge.append(el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'SourceGraphic' })); glow.append(merge);
  defs.append(glow);
  svg.append(defs);

  const cols = [
    { x: 0, title: 'Vektor (dense)', items: dense.slice(0, N), color: '#5fe1f5' },
    { x: colW + gapW, title: 'RRF natijasi', items: fused.slice(0, N), color: '#e8c477' },
    { x: (colW + gapW) * 2, title: 'BM25 (Lex.uz indeksi)', items: sparse.slice(0, N), color: '#78aef0' },
  ];
  const fusedAt = new Map(fused.slice(0, N).map((c, i) => [c.chunk_id, i]));
  const sel = new Set(selected);
  const mid = cols[1];
  for (const col of [cols[0], cols[2]]) {
    const fromLeft = col === cols[0];
    col.items.forEach((it, i) => {
      const j = fusedAt.get(it.chunk_id);
      if (j == null) return;
      const x1 = fromLeft ? col.x + colW : col.x, y1 = top + i * rowH + rowH / 2;
      const x2 = fromLeft ? mid.x : mid.x + colW, y2 = top + j * rowH + rowH / 2;
      const c1 = fromLeft ? x1 + 70 : x1 - 70, c2 = fromLeft ? x2 - 70 : x2 + 70;
      const d = fromLeft ? `M${x1},${y1} C${c1},${y1} ${c2},${y2} ${x2},${y2}` : `M${x2},${y2} C${c2},${y2} ${c1},${y1} ${x1},${y1}`;
      const on = sel.has(it.chunk_id);
      svg.append(el('path', { d, fill: 'none', stroke: `url(#${id}-${on ? 'keep' : fromLeft ? 'dense' : 'bm25'})`,
        'stroke-opacity': on ? 0.9 : 0.32, 'stroke-width': on ? 2.6 : 1.4, 'stroke-linecap': 'round', filter: on ? `url(#${id}-glow)` : null }));
      if (on) svg.append(el('path', { d, fill: 'none', stroke: '#eafff6', 'stroke-width': 2, 'stroke-linecap': 'round', class: 'rankflow__spark' }));
    });
  }
  for (const col of cols) {
    const max = Math.max(...col.items.map((x) => Math.abs(x.score ?? 0)), 1e-9);
    svg.append(el('circle', { cx: col.x + 5, cy: 20, r: 4, fill: col.color, filter: `url(#${id}-glow)` }));
    svg.append(el('text', { x: col.x + 16, y: 24, fill: col.color, 'font-family': 'JetBrains Mono, monospace', 'font-size': 11.5, 'letter-spacing': 1.2 }, col.title.toUpperCase()));
    if (!col.items.length) svg.append(el('text', { x: col.x, y: top + 20, fill: '#728078', 'font-size': 12.5 }, 'maʼlumot yoʻq'));
    col.items.forEach((it, i) => {
      const y = top + i * rowH, on = sel.has(it.chunk_id);
      const g = el('g', { class: `rankflow__row${on ? ' is-on' : ''}` });
      g.append(el('rect', { x: col.x, y: y + 3, width: colW, height: rowH - 6, rx: (rowH - 6) / 2, fill: `url(#${id}-${on ? 'pillOn' : 'pill'})`,
        stroke: on ? 'rgba(57,224,166,0.7)' : 'rgba(80,110,100,0.35)', filter: on ? `url(#${id}-glow)` : null }));
      if (it.score != null) {
        const bw = Math.max(4, ((colW - 50) * Math.abs(it.score)) / max);
        g.append(el('rect', { x: col.x + 40, y: y + rowH - 9, width: bw, height: 2.2, rx: 1.1, fill: col.color, opacity: on ? 0.9 : 0.45 }));
      }
      g.append(el('circle', { cx: col.x + 17, cy: y + rowH / 2, r: 11, fill: on ? 'rgba(57,224,166,0.25)' : 'rgba(255,255,255,0.05)', stroke: on ? '#39e0a6' : col.color, 'stroke-opacity': on ? 1 : 0.5 }));
      g.append(el('text', { x: col.x + 17, y: y + rowH / 2 + 4, 'text-anchor': 'middle', fill: on ? '#d9fff0' : '#a1ada5', 'font-family': 'JetBrains Mono, monospace', 'font-size': 10.5 }, `${it.rank ?? i + 1}`));
      const txt = String(label(it.chunk_id, it)).replace(/Oʻzbekiston Respublikasining\s+/i, '');
      g.append(el('text', { x: col.x + 38, y: y + rowH / 2 + 2, fill: on ? '#f0f2ed' : '#a1ada5', 'font-size': 12.5 }, txt.length > 22 ? `${txt.slice(0, 21)}…` : txt));
      if (it.score != null) g.append(el('text', { x: col.x + colW - 12, y: y + rowH / 2 + 2, fill: on ? '#9af5d2' : '#728078', 'text-anchor': 'end', 'font-family': 'JetBrains Mono, monospace', 'font-size': 10.5 }, Number(it.score).toFixed(3)));
      svg.append(g);
    });
  }
  return svg;
}
