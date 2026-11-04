// A gold, single-colour drawing of the State Emblem of Uzbekistan for the book cover:
// rising sun over mountains and two rivers, the Humo bird with spread wings, a wreath of cotton (left)
// and wheat (right) tied with a ribbon, and the eight-pointed star with crescent and star on top.
// Generated as SVG so it stays sharp at any texture size.

const GOLD = '#e0bd63';
const GOLD_D = '#a98637';
const BG = '#13203a';

const f = (n) => n.toFixed(1);
const rad = (d) => (d * Math.PI) / 180;
const C = { x: 200, y: 212 };

function pt(r, deg) {
  return [C.x + r * Math.cos(rad(deg)), C.y + r * Math.sin(rad(deg))];
}

function leaf(x, y, len, wid, deg, fill = GOLD) {
  return `<ellipse cx="${f(x)}" cy="${f(y)}" rx="${f(len / 2)}" ry="${f(wid / 2)}" transform="rotate(${f(deg)} ${f(x)} ${f(y)})" fill="${fill}"/>`;
}

function octagram(cx, cy, r) {
  const sq = (rot) => {
    const p = [0, 1, 2, 3].map((i) => {
      const a = rad(rot + 45 + i * 90);
      return `${f(cx + r * Math.cos(a))},${f(cy + r * Math.sin(a))}`;
    });
    return `<polygon points="${p.join(' ')}"/>`;
  };
  const star = (sx, sy, sr) => {
    const p = [];
    for (let i = 0; i < 10; i++) {
      const a = rad(-90 + i * 36), rr = i % 2 ? sr * 0.42 : sr;
      p.push(`${f(sx + rr * Math.cos(a))},${f(sy + rr * Math.sin(a))}`);
    }
    return `<polygon points="${p.join(' ')}" fill="${GOLD}"/>`;
  };
  return `<g fill="${GOLD}">${sq(0)}${sq(45)}</g>
    <circle cx="${cx}" cy="${cy}" r="${f(r * 0.66)}" fill="${BG}"/>
    <circle cx="${f(cx - 3)}" cy="${cy}" r="11.5" fill="${GOLD}"/><circle cx="${f(cx + 1.5)}" cy="${f(cy - 1)}" r="9.5" fill="${BG}"/>
    ${star(cx + 5, cy - 1, 4.5)}`;
}

function cottonBranch() {
  const out = [];
  // stem along the left side of the wreath
  const pts = [];
  for (let d = 102; d <= 238; d += 4) pts.push(pt(142, d));
  out.push(`<polyline points="${pts.map((p) => p.map(f).join(',')).join(' ')}" fill="none" stroke="${GOLD}" stroke-width="5" stroke-linecap="round"/>`);
  // leaves on both sides of the stem
  for (let d = 108; d <= 232; d += 11) {
    const [x, y] = pt(142, d);
    const tang = d + 90;
    out.push(leaf(...pt(156, d - 2), 30, 11, tang - 35));
    out.push(leaf(...pt(128, d + 3), 26, 10, tang + 30, GOLD_D));
    void x; void y;
  }
  // cotton bolls: three soft lobes with a dark seam
  for (const d of [128, 168, 206, 236]) {
    const [x, y] = pt(150, d);
    out.push(`<g transform="translate(${f(x)} ${f(y)})">
      <circle cx="-6" cy="2" r="9" fill="#f1dc9e"/><circle cx="6" cy="2" r="9" fill="#f1dc9e"/><circle cx="0" cy="-7" r="9" fill="#f1dc9e"/>
      <path d="M0 -2 L0 -14 M0 -2 L-10 6 M0 -2 L10 6" stroke="${GOLD_D}" stroke-width="1.6"/>
      <path d="M-12 8 Q0 18 12 8" fill="none" stroke="${GOLD}" stroke-width="3"/></g>`);
  }
  return out.join('');
}

function wheatBranch() {
  const out = [];
  for (let k = 0; k < 2; k++) {
    const r0 = 136 + k * 14;
    const pts = [];
    for (let d = 78; d >= -58; d -= 4) pts.push(pt(r0, d));
    out.push(`<polyline points="${pts.map((p) => p.map(f).join(',')).join(' ')}" fill="none" stroke="${GOLD_D}" stroke-width="2.5"/>`);
    // grains in pairs, pointing up along the stalk
    for (let d = 70; d >= -54; d -= 5.5) {
      const tang = d - 90;
      out.push(leaf(...pt(r0 + 6, d), 15, 7, tang + 28));
      out.push(leaf(...pt(r0 - 6, d - 1.5), 15, 7, tang - 28));
    }
    // awns at the tip
    const [tx, ty] = pt(r0, -58);
    for (let i = -2; i <= 2; i++) {
      out.push(`<line x1="${f(tx)}" y1="${f(ty)}" x2="${f(tx + 6 + i * 4)}" y2="${f(ty - 24 + Math.abs(i) * 3)}" stroke="${GOLD}" stroke-width="1.4"/>`);
    }
  }
  return out.join('');
}

function landscape() {
  const rays = [];
  for (let a = 188; a <= 352; a += 9) {
    const [x1, y1] = [200 + 46 * Math.cos(rad(a)), 196 + 46 * Math.sin(rad(a))];
    const [x2, y2] = [200 + 92 * Math.cos(rad(a)), 196 + 92 * Math.sin(rad(a))];
    rays.push(`<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="${GOLD}" stroke-width="${a % 18 ? 2 : 4}" stroke-linecap="round"/>`);
  }
  return `<clipPath id="inner"><circle cx="${C.x}" cy="${C.y}" r="104"/></clipPath>
  <g clip-path="url(#inner)">
    ${rays.join('')}
    <path d="M158 196 A42 42 0 0 1 242 196 Z" fill="${GOLD}"/>
    <path d="M92 204 L122 182 L140 194 L166 170 L188 192 L200 186 L214 194 L236 172 L258 192 L278 180 L310 204 Z" fill="${GOLD_D}"/>
    <rect x="90" y="203" width="220" height="5" fill="${GOLD}"/>
    <path d="M150 316 C 178 280, 160 250, 192 214" fill="none" stroke="${GOLD}" stroke-width="5"/>
    <path d="M250 316 C 222 280, 240 250, 208 214" fill="none" stroke="${GOLD}" stroke-width="5"/>
    ${[0, 1, 2, 3].map((i) => `<path d="M${120 + i * 4} ${240 + i * 18} q 10 -6 20 0 t 20 0" fill="none" stroke="${GOLD_D}" stroke-width="2"/>
      <path d="M${240 - i * 4} ${240 + i * 18} q 10 -6 20 0 t 20 0" fill="none" stroke="${GOLD_D}" stroke-width="2"/>`).join('')}
  </g>
  <circle cx="${C.x}" cy="${C.y}" r="104" fill="none" stroke="${GOLD}" stroke-width="3"/>`;
}

function humo() {
  // the Humo bird: wings spread wide and swept upwards, fan tail, head with a crest turned to the right
  const wing = (sd) => {
    const out = [];
    for (let i = 0; i < 7; i++) {
      const ang = -(10 + i * 9.5), len = 104 - i * 5;
      const x0 = 200 + sd * 10, y0 = 252 - i * 2;
      const x1 = x0 + sd * len * Math.cos(rad(ang)), y1 = y0 + len * Math.sin(rad(ang));
      const mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
      const nx = sd * Math.sin(rad(ang)) * 15, ny = Math.cos(rad(ang)) * 15;
      out.push(`<path d="M${f(x0)} ${f(y0)} Q ${f(mx - nx)} ${f(my - ny)} ${f(x1)} ${f(y1)} Q ${f(mx + nx * 1.4)} ${f(my + ny * 1.4)} ${f(x0)} ${f(y0 + 8)} Z"
        fill="${i % 2 ? GOLD_D : GOLD}" stroke="${BG}" stroke-width="1.3"/>`);
    }
    return out.reverse().join('');
  };
  const tail = [-16, 0, 16].map((dx, i) => `<path d="M200 296 Q ${200 + dx * 0.6} 316 ${200 + dx * 1.6} 330 L ${200 + dx * 0.4} 326 Z" fill="${i === 1 ? GOLD : GOLD_D}" stroke="${BG}" stroke-width="1.2"/>`).join('');
  return `<g>
    ${wing(-1)}${wing(1)}
    ${tail}
    <path d="M200 224 C 222 232, 222 278, 204 300 L 196 300 C 178 278, 178 232, 200 224 Z" fill="${GOLD}" stroke="${BG}" stroke-width="1.6"/>
    <path d="M190 252 Q 200 260 210 252 M188 266 Q 200 274 212 266 M191 280 Q 200 287 209 280" fill="none" stroke="${GOLD_D}" stroke-width="1.6"/>
    <path d="M194 230 C 192 214, 200 204, 210 204 C 218 204, 222 210, 230 213 L 220 216 C 216 222, 208 228, 204 234 Z" fill="${GOLD}" stroke="${BG}" stroke-width="1.6"/>
    <path d="M206 205 C 204 196, 210 188, 218 186 C 214 192, 214 196, 214 200 M210 204 C 212 196, 220 192, 226 194 C 220 198, 218 200, 216 204" fill="${GOLD}" stroke="${BG}" stroke-width="1"/>
    <circle cx="214" cy="210" r="2" fill="${BG}"/>
  </g>`;
}

function ribbon() {
  return `<path d="M108 330 C 140 350, 170 356, 200 356 C 230 356, 260 350, 292 330 L 300 352 C 266 372, 232 378, 200 378 C 168 378, 134 372, 100 352 Z"
      fill="${GOLD}" stroke="${BG}" stroke-width="1.5"/>
    <path d="M100 352 L 82 360 L 94 344 L 84 330 L 108 330 Z M300 352 L 318 360 L 306 344 L 316 330 L 292 330 Z" fill="${GOLD_D}"/>
    <path id="rib" d="M120 352 C 150 366, 176 368, 200 368 C 224 368, 250 366, 280 352" fill="none"/>
    <text font-family="Literata, Lora, Georgia, serif" font-size="15" font-weight="700" letter-spacing="2" fill="${BG}" text-anchor="middle">
      <textPath href="#rib" startOffset="50%">OʻZBEKISTON</textPath></text>`;
}

export function emblemSVG() {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
    ${landscape()}
    ${cottonBranch()}
    ${wheatBranch()}
    ${humo()}
    ${ribbon()}
    ${octagram(200, 64, 26)}
  </svg>`;
}

export function loadEmblem() {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(emblemSVG());
  });
}
