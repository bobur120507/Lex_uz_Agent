// Offline fonts (roadmap 13.5 F1): downloads Onest, Literata and JetBrains Mono (latin, latin-ext, cyrillic)
// from Google Fonts into public/fonts/ and points index.html at the local copy. Run once on a machine with
// internet, then commit public/fonts/ and index.html — the demo laptop then needs no internet for fonts.
//   node frontend_idea/scripts/fetch_fonts.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'public', 'fonts');
const html = path.join(root, 'index.html');
const CSS = 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,500;0,7..72,600;1,7..72,400&family=Onest:wght@400;500;600&display=swap';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';  // → woff2
const KEEP = /\/\* (latin|latin-ext|cyrillic|cyrillic-ext) \*\//;

fs.mkdirSync(out, { recursive: true });
const css = await (await fetch(CSS, { headers: { 'User-Agent': UA } })).text();
const blocks = css.split('@font-face').slice(1).map((b) => '@font-face' + b);
const comments = css.match(/\/\* [a-z-]+ \*\//g) || [];
let local = '', n = 0;
for (let i = 0; i < blocks.length; i++) {
  if (!KEEP.test(comments[i] || '')) continue;
  const url = blocks[i].match(/url\((https:[^)]+)\)/)?.[1];
  if (!url) continue;
  const name = `${String(++n).padStart(2, '0')}-${path.basename(new URL(url).pathname)}`;
  fs.writeFileSync(path.join(out, name), Buffer.from(await (await fetch(url)).arrayBuffer()));
  local += `${comments[i]}\n${blocks[i].replace(url, `./${name}`).trim()}\n`;
}
fs.writeFileSync(path.join(out, 'fonts.css'), local);
let page = fs.readFileSync(html, 'utf8');
page = page.replace(/\s*<link rel="preconnect" href="https:\/\/fonts\.g[^>]+>/g, '')
  .replace(/<link rel="stylesheet" href="https:\/\/fonts\.googleapis\.com[^>]+>/, '<link rel="stylesheet" href="/fonts/fonts.css" />');
fs.writeFileSync(html, page);
console.log(`${n} ta shrift fayli → ${out}; index.html mahalliy fonts.css ga oʻtkazildi. public/fonts va index.html ni commit qiling.`);
