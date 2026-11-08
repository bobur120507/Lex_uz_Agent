// Backup demo video + real frame rate, on the machine that runs the site (scripts/day4.py calls it).
//   node frontend_idea/scripts/record_video.mjs http://localhost:8080/ <out-dir> ["question"]
// Opens a visible Chromium window (real GPU), asks one question, lets the answer land in the book, shows the
// statue's scales and the Mind window, and saves a 1920×1080 .webm. Prints the measured fps and the GPU.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const url = process.argv[2] || 'http://localhost:8080/';
const out = path.resolve(process.argv[3] || 'demo-video');
const question = process.argv[4] || 'Har yilgi mehnat taʼtili necha kun?';
fs.mkdirSync(out, { recursive: true });

const headless = process.env.HEADLESS === '1';                     // only for testing without a screen
const browser = await chromium.launch({ headless, args: headless ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
  : ['--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--force_high_performance_gpu', '--window-size=1920,1120'] });
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
const wait = (ms) => page.waitForTimeout(ms);
const fps = [];
// the browser's real frame rate (requestAnimationFrame over 1 s) — counts every canvas, also a panel's own 3-D view
const rafFps = () => page.evaluate(() => new Promise((res) => {
  let n = 0; const t0 = performance.now();
  const f = () => { n++; const dt = performance.now() - t0; if (dt < 1000) requestAnimationFrame(f); else res(Math.round((n * 1000) / dt)); };
  requestAnimationFrame(f);
}));
const sample = async (n) => { for (let i = 0; i < n; i++) fps.push(await rafFps()); };

await page.goto(url);
await page.waitForFunction(() => document.body.classList.contains('is-ready'), null, { timeout: 120000 });
const gpu = await page.evaluate(() => {
  const gl = document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl');
  const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
  return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl ? gl.getParameter(gl.RENDERER) : 'no WebGL';
});
await sample(4);                                                  // idle scene
await page.fill('#question', '');
await page.type('#question', question, { delay: 45 });
await wait(400);
await page.keyboard.press('Enter');
const t0 = Date.now();
await page.waitForFunction(() => ['done', 'unknown', 'error'].includes(window.__modda?.state?.phase), null, { timeout: 600000 });
const answerS = (Date.now() - t0) / 1000;
await sample(8);                                                  // the book lands, pages turn
await page.click('.justice-hit', { force: true }).catch(() => {});
await sample(6);                                                  // the statue's scales
await page.keyboard.press('Escape');
await wait(2500);
await page.click('.node[data-node="generate"]', { force: true }).catch(() => {});
await wait(2500);
await page.keyboard.press('Escape'); await wait(800);
await page.click('.mind[data-node="mind"]', { force: true, timeout: 3000 }).catch(() => {});
await sample(5);
await page.keyboard.press('Escape');
await wait(1500);
const dpr = await page.evaluate(() => window.__moddaDpr || window.devicePixelRatio);
const video = page.video();
await ctx.close();
const raw = video ? await video.path() : null;
let file = null;
if (raw) {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
  file = path.join(out, `modda-demo-${stamp}.webm`);
  fs.renameSync(raw, file);
}
await browser.close();
const s = [...fps].filter((x) => x > 0).sort((a, b) => a - b);
console.log(JSON.stringify({ gpu, answer_s: Math.round(answerS * 10) / 10, fps_median: s[Math.floor(s.length / 2)] ?? null,
  fps_min: s[0] ?? null, render_scale: dpr, video: file, errors }, null, 2));
