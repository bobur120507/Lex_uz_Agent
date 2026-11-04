// Canvas textures: navy cloth cover with the emblem, paper edges, generic pages and pages with a real article.
import * as THREE from 'three';

export const PAGE_PX = { w: 1024, h: 1376 };          // same ratio as the page (1.45 : 1.95)
const SERIF = '"Literata", "Lora", Georgia, serif';
const SANS = '"Onest", "Inter", system-ui, sans-serif';

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return [c, c.getContext('2d')];
}

function toTexture(c, { repeat = false } = {}) {
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// small deterministic random, so the same seed always draws the same page
function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function grain(ctx, w, h, amount, alpha, rand) {
  for (let i = 0; i < amount; i++) {
    const v = rand() > 0.5 ? 255 : 0;
    ctx.fillStyle = `rgba(${v},${v},${v},${alpha * rand()})`;
    ctx.fillRect(rand() * w, rand() * h, 1 + rand() * 2, 1 + rand() * 2);
  }
}

const NAVY_A = '#1b2a48', NAVY_B = '#0f1a30', GOLD = '#e0bd63', GOLD_D = '#a98637';

function clothBase(ctx, w, h, seed) {
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, NAVY_A); g.addColorStop(1, NAVY_B);
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  grain(ctx, w, h, 26000, 0.06, rng(seed));
  const shine = ctx.createRadialGradient(w * 0.75, h * 0.12, 20, w * 0.75, h * 0.12, w * 0.9);
  shine.addColorStop(0, 'rgba(255,255,255,0.08)'); shine.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = shine; ctx.fillRect(0, 0, w, h);
}

// one corner flourish, drawn for the top-left corner; the others are mirrored copies
function flourish(ctx) {
  ctx.save();
  ctx.strokeStyle = GOLD; ctx.lineWidth = 4; ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(70, 190); ctx.bezierCurveTo(70, 120, 110, 80, 180, 74);
  ctx.moveTo(100, 160); ctx.bezierCurveTo(96, 120, 120, 100, 150, 104); ctx.bezierCurveTo(176, 108, 176, 140, 152, 142);
  ctx.bezierCurveTo(136, 143, 132, 126, 144, 122);
  ctx.moveTo(180, 74); ctx.bezierCurveTo(230, 70, 250, 100, 232, 116); ctx.bezierCurveTo(218, 128, 200, 112, 212, 102);
  ctx.moveTo(70, 190); ctx.bezierCurveTo(66, 240, 96, 258, 112, 242); ctx.bezierCurveTo(124, 228, 108, 212, 98, 222);
  ctx.stroke();
  ctx.fillStyle = GOLD;
  for (const [x, y, r] of [[150, 104, 0], [96, 96, 6], [250, 82, 4], [64, 262, 4]]) {
    if (!r) continue;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

function frame(ctx, w, h) {
  ctx.strokeStyle = GOLD; ctx.lineWidth = 5; ctx.strokeRect(40, 40, w - 80, h - 80);
  ctx.lineWidth = 2; ctx.strokeRect(56, 56, w - 112, h - 112);
  for (const [sx, sy] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) {
    ctx.save();
    ctx.translate(sx > 0 ? 0 : w, sy > 0 ? 0 : h); ctx.scale(sx, sy);
    flourish(ctx);
    ctx.restore();
  }
  // short rules at the middle of the top and bottom edges
  ctx.fillStyle = GOLD;
  ctx.fillRect(w / 2 - 150, 76, 300, 4); ctx.fillRect(w / 2 - 150, h - 80, 300, 4);
}

/** Front cover: navy cloth, gold frame, title, the State Emblem of Uzbekistan, subtitle. */
export function coverTexture() {
  const w = 1024, h = 1376;
  const [c, ctx] = canvas(w, h);
  const draw = (emblem) => {
    clothBase(ctx, w, h, 7);
    frame(ctx, w, h);
    ctx.textAlign = 'center'; ctx.fillStyle = GOLD;
    ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowOffsetY = 3; ctx.shadowBlur = 3;
    ctx.font = `600 150px ${SERIF}`; ctx.fillText('MODDA', w / 2, 270);
    ctx.shadowColor = 'transparent';
    ctx.fillRect(w / 2 - 190, 312, 380, 3);
    if (emblem) {
      // keep the image's own proportions inside a 640 × 660 box
      const k = Math.min(640 / emblem.width, 660 / emblem.height);
      const ew = emblem.width * k, eh = emblem.height * k;
      ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 6;
      ctx.drawImage(emblem, w / 2 - ew / 2, 360 + (660 - eh) / 2, ew, eh);
      ctx.shadowColor = 'transparent';
    }
    ctx.fillStyle = GOLD;
    ctx.font = `italic 400 40px ${SERIF}`; ctx.fillText('Oʻzbekiston Respublikasi', w / 2, 1110);
    ctx.font = `600 58px ${SERIF}`; ctx.fillText('QONUNCHILIGI', w / 2, 1180);
    ctx.font = `400 30px ${SANS}`; ctx.fillStyle = GOLD_D; ctx.fillText('Lex.uz maʼlumotlari asosida', w / 2, 1236);
  };
  draw(null);
  const t = toTexture(c);
  // the State Emblem of Uzbekistan (web/public/gerb.png); if it cannot load, a drawn gold version is used
  loadImage(`${import.meta.env?.BASE_URL ?? './'}gerb.png`)
    .catch(() => import('./emblem.js').then(({ loadEmblem }) => loadEmblem()))
    .then((img) => { draw(img); t.needsUpdate = true; })
    .catch(() => {});
  return t;
}

/** Plain navy cloth for the back cover; `spine` adds gold bands and the title running down. */
export function clothTexture({ spine = false } = {}) {
  const w = spine ? 256 : 1024, h = 1376;
  const [c, ctx] = canvas(w, h);
  clothBase(ctx, w, h, spine ? 11 : 3);
  if (spine) {
    ctx.fillStyle = GOLD;
    for (const y of [90, 110, h - 120, h - 100]) ctx.fillRect(20, y, w - 40, 5);
    ctx.save(); ctx.translate(w / 2, h / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center'; ctx.font = `600 84px ${SERIF}`; ctx.fillText('MODDA', 0, 28);
    ctx.restore();
  } else {
    ctx.strokeStyle = GOLD_D; ctx.lineWidth = 3; ctx.strokeRect(56, 56, w - 112, h - 112);
  }
  return toTexture(c);
}

export function paperEdge() {
  const [c, ctx] = canvas(64, 64);
  for (let y = 0; y < 64; y += 2) {
    ctx.fillStyle = y % 4 ? '#e9e2d0' : '#f6f1e5';
    ctx.fillRect(0, y, 64, 2);
  }
  return toTexture(c, { repeat: true });
}

// spineRight: the page lies on the left half of the book, so its spine edge is the canvas's right edge
function paperBase(ctx, w, h, seed, spineRight = false) {
  ctx.fillStyle = '#f3efe4'; ctx.fillRect(0, 0, w, h);
  grain(ctx, w, h, 9000, 0.035, rng(seed));
  const x0 = spineRight ? w : 0, x1 = spineRight ? w * 0.88 : w * 0.12;
  const shade = ctx.createLinearGradient(x0, 0, x1, 0);              // darker near the spine
  shade.addColorStop(0, 'rgba(60,45,20,0.16)'); shade.addColorStop(1, 'rgba(60,45,20,0)');
  ctx.fillStyle = shade; ctx.fillRect(Math.min(x0, x1), 0, w * 0.12, h);
}

/** A page that looks printed but carries no readable words (used while flipping). */
export function genericPage(seed = 1, mirrored = false) {
  const { w, h } = PAGE_PX;
  const [c, ctx] = canvas(w, h);
  paperBase(ctx, w, h, seed, mirrored);
  const rand = rng(seed * 31);
  ctx.fillStyle = 'rgba(40,40,36,0.28)';
  ctx.fillRect(130, 120, 300 + rand() * 300, 26);                   // heading
  let y = 200;
  while (y < h - 140) {
    const lines = 3 + Math.floor(rand() * 6);
    for (let i = 0; i < lines && y < h - 140; i++) {
      const last = i === lines - 1;
      ctx.fillStyle = 'rgba(40,40,36,0.17)';
      ctx.fillRect(130, y, last ? 200 + rand() * 450 : 764 - rand() * 30, 12);
      y += 30;
    }
    y += 28;
  }
  ctx.fillStyle = 'rgba(40,40,36,0.3)';
  ctx.font = `400 26px ${SERIF}`; ctx.textAlign = 'center';
  ctx.fillText(String(10 + Math.floor(rand() * 600)), w / 2, h - 70);
  const t = toTexture(c);
  if (mirrored) mirror(t);
  return t;
}

export function mirror(t) {
  t.wrapS = THREE.RepeatWrapping; t.repeat.x = -1; t.offset.x = 1;
  return t;
}

function wrapWords(ctx, words, maxW) {
  const lines = [];
  let line = [], width = 0;
  const space = ctx.measureText(' ').width;
  for (const wd of words) {
    const ww = ctx.measureText(wd.text).width;
    if (line.length && width + space + ww > maxW) { lines.push(line); line = []; width = 0; }
    wd.w = ww;
    width += (line.length ? space : 0) + ww;
    line.push(wd);
  }
  if (line.length) lines.push(line);
  return lines;
}

/** Right-hand page: the article itself, with the quoted words highlighted. */
export function articlePage({ articleNo, articleTitle, text, quote }) {
  const { w, h } = PAGE_PX;
  const [c, ctx] = canvas(w, h);
  paperBase(ctx, w, h, 99);
  const left = 120, maxW = w - 120 - 110;
  ctx.fillStyle = '#16221c';
  ctx.font = `600 50px ${SERIF}`;
  const head = `${articleNo}-modda. ${articleTitle || ''}`.trim();
  const headLines = wrapWords(ctx, head.split(' ').map((t) => ({ text: t })), maxW);
  let y = 170;
  for (const ln of headLines) { ctx.fillText(ln.map((x) => x.text).join(' '), left, y); y += 64; }
  y += 26;

  const lower = text.toLowerCase();
  const qAt = quote ? lower.indexOf(quote.toLowerCase()) : -1;
  const qEnd = qAt >= 0 ? qAt + quote.length : -1;
  ctx.font = `400 36px ${SERIF}`;
  const lineH = 58;
  const space = ctx.measureText(' ').width;
  let offset = 0;
  for (const para of text.split('\n')) {
    const words = [];
    for (const m of para.matchAll(/\S+/g)) {
      const s = offset + m.index, e = s + m[0].length;
      words.push({ text: m[0], hl: qAt >= 0 && s < qEnd && e > qAt });
    }
    offset += para.length + 1;
    for (const ln of wrapWords(ctx, words, maxW)) {
      if (y > h - 120) break;
      let x = left;
      ln.forEach((wd, i) => {
        if (wd.hl) {
          const next = ln[i + 1];
          ctx.fillStyle = 'rgba(111, 211, 161, 0.42)';
          ctx.fillRect(x - 4, y - 38, wd.w + (next && next.hl ? space : 0) + 8, 52);
        }
        ctx.fillStyle = '#1b2620';
        ctx.fillText(wd.text, x, y);
        x += wd.w + space;
      });
      y += lineH;
    }
    y += 18;
  }
  return toTexture(c);
}

/** Left-hand page: where we are in the book (document and chapter). */
export function headerPage({ docTitle, docLine, chapter }) {
  const { w, h } = PAGE_PX;
  const [c, ctx] = canvas(w, h);
  paperBase(ctx, w, h, 42, true);
  const maxW = w - 240;
  ctx.textAlign = 'center';
  ctx.fillStyle = '#55645d'; ctx.font = `400 30px ${SANS}`;
  ctx.fillText(docLine || '', w / 2, 300);
  ctx.fillStyle = '#16221c'; ctx.font = `600 58px ${SERIF}`;
  let y = 420;
  for (const ln of wrapWords(ctx, (docTitle || '').split(' ').map((t) => ({ text: t })), maxW)) {
    ctx.fillText(ln.map((x) => x.text).join(' '), w / 2, y); y += 74;
  }
  ctx.fillStyle = 'rgba(29,90,66,0.6)'; ctx.fillRect(w / 2 - 60, y + 10, 120, 3);
  if (chapter) {
    ctx.fillStyle = '#3b4a43'; ctx.font = `italic 400 36px ${SERIF}`;
    y += 90;
    for (const ln of wrapWords(ctx, chapter.split(' ').map((t) => ({ text: t })), maxW)) {
      ctx.fillText(ln.map((x) => x.text).join(' '), w / 2, y); y += 50;
    }
  }
  return mirror(toTexture(c));
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export async function fontsReady(timeoutMs = 2500) {
  if (!document.fonts) return;
  const load = Promise.all([
    document.fonts.load(`400 36px "Literata"`, 'oʻgʻʼ'),
    document.fonts.load(`600 50px "Literata"`, 'oʻgʻʼ'),
    document.fonts.load(`400 30px "Onest"`, 'oʻgʻʼ'),
  ]).catch(() => {});
  await Promise.race([load, new Promise((r) => setTimeout(r, timeoutMs))]);
}
