// The scales: left pan «Javob» (claims written by the LLM), right pan «Lex.uz» (evidence found for them).
// The beam tilts by the real score (100 = balanced). Animated with CSS transitions.
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, text) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
};

export function scalesSVG({ score, total = 0, supported = 0 }) {
  const svg = el('svg', { viewBox: '0 0 420 300', class: 'beam', role: 'img', 'aria-label': score == null ? 'Tarozi: baho yoʻq' : `Tarozi: manbaga moslik ${score} / 100` });
  const gold = '#d6b66d', dim = '#9e8148';
  svg.append(el('path', { d: 'M150 288 h120 l-14 -14 h-92 z', fill: dim }));
  svg.append(el('rect', { x: 205, y: 70, width: 10, height: 206, rx: 3, fill: gold }));
  svg.append(el('circle', { cx: 210, cy: 66, r: 10, fill: gold }));
  const angle = score == null ? 0 : -((100 - Math.max(0, Math.min(100, score))) / 100) * 16;
  const beam = el('g', { style: 'transform-origin: 210px 70px; transition: transform 1.2s cubic-bezier(.2,1.4,.4,1); transform: rotate(0deg)' });
  beam.append(el('rect', { x: 40, y: 66, width: 340, height: 8, rx: 4, fill: gold }));
  const pan = (x, label, value, color) => {
    const g = el('g', { style: `transform-origin: ${x}px 70px; transition: transform 1.2s cubic-bezier(.2,1.4,.4,1);` });
    g.append(el('line', { x1: x, y1: 74, x2: x - 46, y2: 170, stroke: dim, 'stroke-width': 1.5 }));
    g.append(el('line', { x1: x, y1: 74, x2: x + 46, y2: 170, stroke: dim, 'stroke-width': 1.5 }));
    g.append(el('path', { d: `M${x - 58} 170 Q${x} 214 ${x + 58} 170 z`, fill: color, 'fill-opacity': 0.9 }));
    g.append(el('text', { x, y: 238, 'text-anchor': 'middle', fill: '#f0f2ed', 'font-size': 15, 'font-weight': 600 }, label));
    g.append(el('text', { x, y: 258, 'text-anchor': 'middle', fill: '#a1ada5', 'font-size': 12.5 }, value));
    beam.append(g); return g;
  };
  const left = pan(80, 'Javob', `${total} ta gap`, '#b98f42');
  const right = pan(340, 'Lex.uz', `${supported} ta tasdiq`, '#2fae84');
  svg.append(beam);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    beam.style.transform = `rotate(${angle}deg)`;
    left.style.transform = right.style.transform = `rotate(${-angle}deg)`;
  }));
  return svg;
}
