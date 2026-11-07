// Canvas textures for the book: cover, cloth, paper edge, blank printed pages, and the two result pages —
// the answer (left) and the found modda among its ±5 neighbours (right). Each result page also returns
// "hit" rectangles (in canvas pixels) so clicks on [n] references and article lines can be handled.
import * as THREE from 'three';
import { BASE, DISCLAIMER, UNKNOWN_TEXT } from '../config.js';

export const PX = { w: 1024, h: 1376 };                     // page ratio 1.45 : 1.95
const SERIF = '"Literata", "Lora", Georgia, serif';
const SANS = '"Onest", "Inter", system-ui, sans-serif';
const MONO = '"JetBrains Mono", ui-monospace, monospace';
const INK = '#1c2621', INK_2 = '#5c645d', INK_3 = '#8a8f85', GOLD_INK = '#8a6a26', EMER = '#1d7a5a';

// Page quality: pages are drawn in the same 1024 × 1376 "page units" as before, on a canvas Q times larger
// (Q = 2 on desktop → 2048 × 2752 texture), so the text stays sharp when the book fills the screen.
let Q = 2, ANISO = 8;
export function setPageQuality({ scale, anisotropy } = {}) {
  if (scale) Q = scale;
  if (anisotropy) ANISO = anisotropy;
}
function canvas(w, h, q = Q) {
  const c = document.createElement('canvas');
  c.width = Math.round(w * q); c.height = Math.round(h * q);
  const ctx = c.getContext('2d');
  ctx.scale(q, q);
  ctx.imageSmoothingQuality = 'high';
  return [c, ctx];
}
// Result pages are made often (every page turn, every streaming update): they are tracked and freed on the GPU
// as soon as the book no longer shows them (Book.sweep → sweepPages).
const LIVE = new Set();
export function toTexture(c, { repeat = false, live = false } = {}) {
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = ANISO;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (live) { t.userData.live = true; LIVE.add(t); }
  return t;
}
/** A mirrored copy for the back of a turning sheet (same canvas, no redraw). */
export function mirrored(t) {
  const m = t.clone();
  m.wrapS = THREE.RepeatWrapping; m.repeat.x = -1; m.offset.x = 1;
  m.needsUpdate = true;
  if (t.userData.live) LIVE.add(m);
  return m;
}
export function sweepPages(inUse) {
  for (const t of LIVE) if (!inUse.has(t)) { t.dispose(); LIVE.delete(t); }
}
export const livePages = () => LIVE.size;
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

// ---------------------------------------------------------------- cover
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
  for (const [x, y, r] of [[96, 96, 6], [250, 82, 4], [64, 262, 4]]) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
}
function frame(ctx, w, h) {
  ctx.strokeStyle = GOLD; ctx.lineWidth = 5; ctx.strokeRect(40, 40, w - 80, h - 80);
  ctx.lineWidth = 2; ctx.strokeRect(56, 56, w - 112, h - 112);
  for (const [sx, sy] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) {
    ctx.save(); ctx.translate(sx > 0 ? 0 : w, sy > 0 ? 0 : h); ctx.scale(sx, sy); flourish(ctx); ctx.restore();
  }
  ctx.fillStyle = GOLD;
  ctx.fillRect(w / 2 - 150, 76, 300, 4); ctx.fillRect(w / 2 - 150, h - 80, 300, 4);
}
function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img); img.onerror = reject; img.src = src;
  });
}

/** Front cover: navy cloth, gold frame, MODDA, the State Emblem of Uzbekistan (public/gerb.png), subtitle. */
export function coverTexture(onReady) {
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
  loadImage(`${BASE}gerb.png`)
    .catch(() => import('./emblem.js').then(({ loadEmblem }) => loadEmblem()))
    .then((img) => { draw(img); t.needsUpdate = true; onReady?.(c); })
    .catch(() => {});
  return t;
}
export function clothTexture({ spine = false } = {}) {
  const w = spine ? 256 : 1024, h = 1376;
  const [c, ctx] = canvas(w, h, Math.min(Q, 1.5));
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
  for (let y = 0; y < 64; y += 2) { ctx.fillStyle = y % 4 ? '#e9e2d0' : '#f6f1e5'; ctx.fillRect(0, y, 64, 2); }
  return toTexture(c, { repeat: true });
}

// ---------------------------------------------------------------- paper
/** side: 'right' page (spine on the left edge) or 'left' page (spine on the right edge) */
function paperBase(ctx, w, h, seed, side = 'right') {
  ctx.fillStyle = '#f3efe4'; ctx.fillRect(0, 0, w, h);
  grain(ctx, w, h, 9000, 0.035, rng(seed));
  const x0 = side === 'left' ? w : 0, x1 = side === 'left' ? w * 0.88 : w * 0.12;
  const shade = ctx.createLinearGradient(x0, 0, x1, 0);
  shade.addColorStop(0, 'rgba(60,45,20,0.16)'); shade.addColorStop(1, 'rgba(60,45,20,0)');
  ctx.fillStyle = shade; ctx.fillRect(Math.min(x0, x1), 0, w * 0.12, h);
}
/** A printed-looking page without readable words (used while the pages riffle). */
export function blankPage(seed = 1, side = 'right') {
  const { w, h } = PX;
  const [c, ctx] = canvas(w, h, 1);                 // only seen while pages fly: 12 of them, keep them light
  paperBase(ctx, w, h, seed, side);
  const rand = rng(seed * 31);
  ctx.fillStyle = 'rgba(40,40,36,0.28)';
  ctx.fillRect(130, 120, 300 + rand() * 300, 26);
  let y = 200;
  while (y < h - 140) {
    const lines = 3 + Math.floor(rand() * 6);
    for (let i = 0; i < lines && y < h - 140; i++) {
      ctx.fillStyle = 'rgba(40,40,36,0.17)';
      ctx.fillRect(130, y, i === lines - 1 ? 200 + rand() * 450 : 764 - rand() * 30, 12);
      y += 30;
    }
    y += 28;
  }
  return toTexture(c);
}

// ---------------------------------------------------------------- text layout
function wrap(ctx, text, maxW) {
  const out = [];
  for (const para of String(text ?? '').split('\n')) {
    const words = para.split(/\s+/).filter(Boolean);
    let line = '';
    for (const wd of words) {
      const test = line ? `${line} ${wd}` : wd;
      if (line && ctx.measureText(test).width > maxW) { out.push(line); line = wd; } else line = test;
    }
    out.push(line);
  }
  return out;
}
function ellipsize(ctx, text, maxW) {
  if (ctx.measureText(text).width <= maxW) return text;
  let s = text;
  while (s.length > 1 && ctx.measureText(`${s}…`).width > maxW) s = s.slice(0, -1);
  return `${s.trimEnd()}…`;
}
export const stripRefs = (s) => String(s || '').replace(/\s*\[\d+(?:\s*[,;]\s*\d+)*\]/g, '').trim();

/** Words of the text, each flagged when it lies inside the quoted part. */
function markedWords(text, quote) {
  const lower = text.toLowerCase();
  const q = (quote || '').toLowerCase().trim();
  const at = q.length > 8 ? lower.indexOf(q) : -1;
  const end = at >= 0 ? at + q.length : -1;
  const out = [];
  for (const m of text.matchAll(/\S+|\n/g)) {
    out.push({ text: m[0], hl: at >= 0 && m.index < end && m.index + m[0].length > at });
  }
  return out;
}

// ---------------------------------------------------------------- the answer page (left)
/**
 * data: {question, sentences: [{text, refs: [n]}], sources: [{n, title, article_no}], unknown, streaming, note}
 * Returns {texture, hits: [{x, y, w, h, ref}]}.
 */
export function answerPage(data) {
  const { w, h } = PX;
  const [c, ctx] = canvas(w, h);
  paperBase(ctx, w, h, 5, 'left');
  const L = 104, R = w - 120, maxW = R - L;
  const hits = [];
  ctx.textBaseline = 'alphabetic';

  ctx.fillStyle = GOLD_INK; ctx.font = `600 24px ${MONO}`;
  ctx.fillText('J A V O B', L, 118);
  ctx.fillStyle = 'rgba(138,106,38,0.5)'; ctx.fillRect(L, 134, 110, 3);

  let y = 196;
  if (data.question) {
    ctx.fillStyle = INK_2; ctx.font = `italic 400 30px ${SERIF}`;
    for (const ln of wrap(ctx, `«${data.question}»`, maxW).slice(0, 3)) { ctx.fillText(ln, L, y); y += 42; }
    y += 18;
  }

  if (data.unknown) {
    ctx.fillStyle = INK; ctx.font = `500 38px ${SERIF}`;
    for (const ln of wrap(ctx, UNKNOWN_TEXT, maxW)) { ctx.fillText(ln, L, y); y += 54; }
    y += 14;
    ctx.fillStyle = INK_2; ctx.font = `400 28px ${SANS}`;
    for (const ln of wrap(ctx, data.note || 'Savolni aniqroq yozing: hujjat nomi yoki modda raqamini qoʻshing (masalan, «Mehnat kodeksi 131-modda»).', maxW)) {
      ctx.fillText(ln, L, y); y += 40;
    }
  } else {
    // auto-fit: the largest font size that leaves room for the source list
    const reserve = 150 + Math.min(data.sources?.length || 0, 5) * 44;
    let size = 44, lines;
    const layout = (sz) => {
      ctx.font = `400 ${sz}px ${SERIF}`;
      const space = ctx.measureText(' ').width;
      const out = [];
      let cy = y;
      for (const s of data.sentences || []) {
        const tokens = stripRefs(s.text).split(/\s+/).filter(Boolean).map((t) => ({ t, w: ctx.measureText(t).width }));
        for (const n of s.refs || []) tokens.push({ ref: n, w: ctx.measureText(`[${n}]`).width * 0.82 + 8 });
        let x = L;
        for (const tk of tokens) {
          if (x > L && x + tk.w > R) { x = L; cy += sz * 1.5; }
          out.push({ ...tk, x, y: cy });
          x += tk.w + space;
        }
        cy += sz * 1.5 + sz * 0.45;
      }
      return { out, end: cy };
    };
    for (; size >= 26; size -= 2) {
      lines = layout(size);
      if (lines.end < h - reserve) break;
    }
    ctx.font = `400 ${size}px ${SERIF}`;
    for (const tk of lines.out) {
      if (tk.y > h - reserve + size) break;
      if (tk.ref) {
        ctx.save();
        ctx.font = `600 ${Math.round(size * 0.62)}px ${MONO}`;
        const tw = ctx.measureText(`[${tk.ref}]`).width;
        ctx.fillStyle = 'rgba(57,214,160,0.2)';
        ctx.fillRect(tk.x - 3, tk.y - size * 0.82, tw + 6, size * 0.72);
        ctx.fillStyle = EMER; ctx.fillText(`[${tk.ref}]`, tk.x, tk.y - size * 0.3);
        ctx.restore();
        hits.push({ x: tk.x - 8, y: tk.y - size, w: tw + 16, h: size * 1.1, ref: tk.ref });
      } else {
        ctx.fillStyle = INK; ctx.fillText(tk.t, tk.x, tk.y);
      }
    }
    if (data.streaming) {
      const last = lines.out.at(-1);
      ctx.fillStyle = 'rgba(29,122,90,0.8)';
      ctx.fillRect((last ? last.x + last.w + 8 : L), (last ? last.y : y) - size * 0.8, 4, size * 0.9);
    }
    y = Math.max(lines.end + 8, y);
  }

  // sources list and disclaimer at the bottom of the page
  const srcs = data.sources || [];
  let by = h - 118 - Math.min(srcs.length, 5) * 44;
  if (srcs.length) {
    ctx.fillStyle = 'rgba(60,45,20,0.25)'; ctx.fillRect(L, by - 34, maxW, 2);
    ctx.fillStyle = GOLD_INK; ctx.font = `600 22px ${MONO}`; ctx.fillText('MANBALAR', L, by);
    by += 42;
    ctx.font = `400 26px ${SANS}`;
    for (const s of srcs.slice(0, 5)) {
      const label = `[${s.n}]  ${s.title || 'Hujjat'}${s.article_no ? `, ${s.article_no}-modda` : ''}`;
      ctx.fillStyle = EMER; ctx.fillText(ellipsize(ctx, label, maxW), L, by);
      hits.push({ x: L - 6, y: by - 30, w: maxW + 12, h: 40, ref: s.n });
      by += 44;
    }
  }
  ctx.fillStyle = INK_3; ctx.font = `italic 400 22px ${SERIF}`;
  ctx.fillText(DISCLAIMER, L, h - 64);
  return { texture: toTexture(c, { live: true }), hits };
}

// ---------------------------------------------------------------- the source page (right)
/**
 * ctx: response of GET /chunks/{id}/context — {document, articles: [{article_id, label, title, text, is_target}]}
 * opts: {n (reference number), quote, total}
 */
export function sourcePage(src, { n = null, quote = '', total = 0 } = {}) {
  const { w, h } = PX;
  const [c, ctx] = canvas(w, h);
  paperBase(ctx, w, h, 17 + (n || 0), 'right');
  const L = 132, R = w - 96, maxW = R - L;
  const hits = [];
  const doc = src.document || {};

  ctx.fillStyle = INK_3; ctx.font = `500 20px ${MONO}`;
  ctx.fillText(n ? `MANBA [${n}]${total ? ` / ${total}` : ''}` : 'TOPILGAN MODDA', L, 104);
  ctx.textAlign = 'right';
  ctx.fillText(doc.doc_type ? String(doc.doc_type).toUpperCase() : '', R, 104);
  ctx.textAlign = 'left';
  ctx.fillStyle = INK; ctx.font = `600 30px ${SERIF}`;
  let y = 150;
  for (const ln of wrap(ctx, doc.title || '', maxW).slice(0, 2)) { ctx.fillText(ln, L, y); y += 38; }
  ctx.fillStyle = 'rgba(60,45,20,0.22)'; ctx.fillRect(L, y - 8, maxW, 2);
  y += 30;

  const arts = src.articles || [];
  const ti = Math.max(0, arts.findIndex((a) => a.is_target));
  const before = arts.slice(0, ti), target = arts[ti], after = arts.slice(ti + 1);
  const headline = (a) => `${a.label ? `${a.label}-modda. ` : ''}${a.title || ''}`.trim() || '—';

  const line = (a, yy) => {
    ctx.fillStyle = INK_3; ctx.font = `400 24px ${SERIF}`;
    ctx.fillText(ellipsize(ctx, headline(a), maxW), L, yy);
    hits.push({ x: L - 6, y: yy - 26, w: maxW + 12, h: 34, article: a.article_id });
  };
  for (const a of before) { line(a, y); y += 36; }
  y += 10;

  if (target) {
    const top = y - 6;
    ctx.fillStyle = INK; ctx.font = `600 31px ${SERIF}`;
    const head = wrap(ctx, headline(target), maxW - 24);
    const room = h - 120 - after.length * 36 - (head.length * 40 + 30);
    let ty = y + 34;
    const bodyLines = [];
    ctx.font = `400 29px ${SERIF}`;
    const space = ctx.measureText(' ').width;
    let x = L + 22, ly = 0;
    let row = [];
    for (const wd of markedWords(target.text || '', quote)) {
      if (wd.text === '\n') { bodyLines.push(row); row = []; x = L + 22; ly++; continue; }
      const ww = ctx.measureText(wd.text).width;
      if (row.length && x + ww > R - 10) { bodyLines.push(row); row = []; x = L + 22; ly++; }
      row.push({ ...wd, x, w: ww });
      x += ww + space;
    }
    if (row.length) bodyLines.push(row);
    const maxLines = Math.max(3, Math.floor(room / 40));
    const shown = bodyLines.slice(0, maxLines);
    const bh = head.length * 40 + 20 + shown.length * 40 + 26;
    ctx.fillStyle = 'rgba(214,182,109,0.17)'; ctx.fillRect(L - 4, top, maxW + 8, bh);
    ctx.fillStyle = '#b8933f'; ctx.fillRect(L - 4, top, 5, bh);
    ctx.fillStyle = INK; ctx.font = `600 31px ${SERIF}`;
    for (const ln of head) { ctx.fillText(ln, L + 22, ty); ty += 40; }
    ty += 8;
    ctx.font = `400 29px ${SERIF}`;
    shown.forEach((r, i) => {
      const lastShown = i === shown.length - 1 && bodyLines.length > shown.length;
      for (const wd of r) {
        if (wd.hl) { ctx.fillStyle = 'rgba(57,214,160,0.34)'; ctx.fillRect(wd.x - 3, ty - 27, wd.w + space, 36); }
        ctx.fillStyle = INK; ctx.fillText(wd.text, wd.x, ty);
      }
      if (lastShown) { ctx.fillStyle = GOLD_INK; ctx.fillText(' …', r.at(-1).x + r.at(-1).w, ty); }
      ty += 40;
    });
    hits.push({ x: L - 4, y: top, w: maxW + 8, h: bh, article: target.article_id, target: true });
    y = top + bh + 34;
  }
  for (const a of after) { if (y > h - 110) break; line(a, y); y += 36; }

  ctx.fillStyle = INK_3; ctx.font = `400 20px ${MONO}`;
  const url = doc.url ? doc.url.replace(/^https?:\/\//, '') : 'lex.uz';
  ctx.fillText(ellipsize(ctx, `${url}${doc.version_date ? ` · ${doc.version_date}` : ''}`, maxW), L, h - 64);
  return { texture: toTexture(c, { live: true }), hits };
}

/** Interim left page while the book has found candidates but the answer is not written yet. */
export function foundPage({ documents = 0, chunks = 0, first = null }) {
  const { w, h } = PX;
  const [c, ctx] = canvas(w, h);
  paperBase(ctx, w, h, 9, 'left');
  const L = 104, maxW = w - 220;
  ctx.fillStyle = GOLD_INK; ctx.font = `600 24px ${MONO}`; ctx.fillText('T O P I L D I', L, 118);
  ctx.fillStyle = INK; ctx.font = `500 40px ${SERIF}`;
  ctx.fillText(`${chunks} ta boʻlak, ${documents} ta hujjat`, L, 210);
  if (first) {
    ctx.fillStyle = INK_2; ctx.font = `400 28px ${SANS}`;
    let y = 290;
    for (const ln of wrap(ctx, `Eng yaqini: ${first}`, maxW).slice(0, 4)) { ctx.fillText(ln, L, y); y += 40; }
  }
  ctx.fillStyle = INK_3; ctx.font = `italic 400 26px ${SERIF}`;
  ctx.fillText('Javob shu sahifada yoziladi…', L, h - 140);
  return { texture: toTexture(c, { live: true }), hits: [] };
}

export async function fontsReady(timeoutMs = 2500) {
  if (!document.fonts) return;
  const load = Promise.all([
    document.fonts.load(`400 36px "Literata"`, 'oʻgʻʼ'), document.fonts.load(`600 50px "Literata"`, 'oʻgʻʼ'),
    document.fonts.load(`400 30px "Onest"`, 'oʻgʻʼ'), document.fonts.load(`500 20px "JetBrains Mono"`, 'MODDA'),
  ]).catch(() => {});
  await Promise.race([load, new Promise((r) => setTimeout(r, timeoutMs))]);
}
