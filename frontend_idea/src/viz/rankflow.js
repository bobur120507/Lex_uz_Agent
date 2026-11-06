// Reciprocal Rank Fusion, drawn: the dense list (left) and the BM25 list (right), real ranks from the backend,
// joined by lines to the fused order (centre) the system kept. Selected passages are emerald, rejected ones grey.
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, text) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
};

export function rankFlow({ dense = [], sparse = [], fused = [], selected = [], label = (id) => id }) {
  const N = 10, rowH = 30, top = 44, colW = 250, gapW = 120, W = colW * 3 + gapW * 2, H = top + N * rowH + 16;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': 'Dense, BM25 va birlashtirilgan tartib' });
  const cols = [
    { x: 0, title: 'Vektor (dense)', items: dense.slice(0, N), color: '#65d8ee' },
    { x: colW + gapW, title: 'RRF natijasi', items: fused.slice(0, N), color: '#d6b66d' },
    { x: (colW + gapW) * 2, title: 'BM25 (Lex.uz indeksi)', items: sparse.slice(0, N), color: '#73afe0' },
  ];
  const fusedAt = new Map(fused.slice(0, N).map((c, i) => [c.chunk_id, i]));
  const sel = new Set(selected);
  const mid = cols[1];
  // lines first (behind the labels): dense → centre from the left, BM25 → centre from the right
  for (const col of [cols[0], cols[2]]) {
    const fromLeft = col === cols[0];
    col.items.forEach((it, i) => {
      const j = fusedAt.get(it.chunk_id);
      if (j == null) return;
      const x1 = fromLeft ? col.x + colW : col.x, y1 = top + i * rowH + rowH / 2;
      const x2 = fromLeft ? mid.x : mid.x + colW, y2 = top + j * rowH + rowH / 2;
      const c1 = fromLeft ? x1 + 60 : x1 - 60, c2 = fromLeft ? x2 - 60 : x2 + 60;
      svg.append(el('path', { d: `M${x1},${y1} C${c1},${y1} ${c2},${y2} ${x2},${y2}`, fill: 'none',
        stroke: sel.has(it.chunk_id) ? '#39d6a0' : col.color, 'stroke-opacity': sel.has(it.chunk_id) ? 0.75 : 0.3, 'stroke-width': 1.6 }));
    });
  }
  for (const col of cols) {
    svg.append(el('text', { x: col.x, y: 22, fill: col.color, 'font-family': 'JetBrains Mono, monospace', 'font-size': 12, 'letter-spacing': 1 }, col.title.toUpperCase()));
    if (!col.items.length) svg.append(el('text', { x: col.x, y: top + 18, fill: '#728078', 'font-size': 12.5 }, 'maʼlumot yoʻq'));
    col.items.forEach((it, i) => {
      const y = top + i * rowH;
      const on = sel.has(it.chunk_id);
      svg.append(el('rect', { x: col.x, y: y + 3, width: colW, height: rowH - 6, rx: 6, fill: on ? 'rgba(57,214,160,0.12)' : 'rgba(255,255,255,0.03)', stroke: on ? 'rgba(57,214,160,0.55)' : 'rgba(41,58,51,1)' }));
      svg.append(el('text', { x: col.x + 9, y: y + 20, fill: '#728078', 'font-family': 'JetBrains Mono, monospace', 'font-size': 11 }, `#${it.rank ?? i + 1}`));
      const txt = label(it.chunk_id, it);
      svg.append(el('text', { x: col.x + 42, y: y + 20, fill: on ? '#f0f2ed' : '#a1ada5', 'font-size': 12.5 }, txt.length > 30 ? `${txt.slice(0, 29)}…` : txt));
      if (it.score != null) svg.append(el('text', { x: col.x + colW - 8, y: y + 20, fill: '#728078', 'text-anchor': 'end', 'font-family': 'JetBrains Mono, monospace', 'font-size': 10.5 }, Number(it.score).toFixed(3)));
    });
  }
  return svg;
}
