// Browser test of the whole journey against a running site + API (real backend, or ?demo).
//   npm run build && (cd .. && MODDA_WEB_DIST=frontend_idea/dist python -m modda serve)   # site + API on :8080
//   node tests/e2e.mjs http://localhost:8080 ./test-results            # needs: npm i -D playwright && npx playwright install chromium
// Checks every visible control, the eight inspectors, the Mind, the scales, the reader, documents,
// five screen sizes, the no-WebGL mode, and that the console stays free of errors.
import { createRequire } from 'node:module';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const BASE = (process.argv[2] || 'http://localhost:8080').replace(/\/$/, '');
const OUT = process.argv[3] || './test-results';
const Q = process.env.E2E_QUESTION || 'Har yilgi mehnat taʼtili necha kun?';
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const check = (name, ok, extra = '') => { results.push({ name, ok: !!ok, extra }); console.log(`${ok ? '✓' : '✗'} ${name}${extra ? ` — ${extra}` : ''}`); };
const IGNORE = /fonts\.googleapis|fonts\.gstatic|ERR_TUNNEL_CONNECTION_FAILED|ERR_NAME_NOT_RESOLVED|GPU stall|WebGL/;

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
async function page(viewport, query = '') {
  const p = await browser.newPage({ viewport });
  p.errors = [];
  p.on('console', (m) => { if (m.type() === 'error' && !IGNORE.test(m.text())) p.errors.push(m.text()); });
  p.on('pageerror', (e) => p.errors.push(`pageerror: ${e.message}`));
  p.on('requestfailed', (r) => { if (!IGNORE.test(r.url())) p.errors.push(`failed: ${r.url()}`); });
  await p.goto(`${BASE}/${query}`);
  await p.waitForFunction(() => document.body.classList.contains('is-ready'), null, { timeout: 60000 });
  return p;
}
const shot = async (p, name) => { await p.waitForTimeout(400); return p.screenshot({ path: `${OUT}/${name}.png`, timeout: 120000, animations: 'disabled' }); };
const closePanel = async (p) => { await p.keyboard.press('Escape'); await p.waitForTimeout(250); };
async function askAndWait(p, q = Q) {
  await p.fill('#question', q);
  await p.keyboard.press('Enter');
  await p.waitForFunction(() => ['done', 'unknown', 'error'].includes(window.__modda.state.phase), null, { timeout: 180000 });
}

// ---------------------------------------------------------------- desktop journey
{
  const p = await page({ width: 1440, height: 900 });
  await p.waitForTimeout(1500);
  await shot(p, 'desktop-1-idle');
  const status = await p.locator('.status').getAttribute('data-state');
  check('status badge shows a real state', ['ok', 'degraded', 'offline', 'demo'].includes(status), status);
  check('empty question is not sent', await (async () => { await p.fill('#question', '   '); await p.keyboard.press('Enter'); await p.waitForTimeout(300); return (await p.evaluate(() => window.__modda.state.phase)) === 'idle'; })());
  await p.fill('#question', Q);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(900);
  check('send button disabled while working', await p.locator('.ask__send').isDisabled() || ['done', 'unknown'].includes(await p.evaluate(() => window.__modda.state.phase)));
  await shot(p, 'desktop-2-research');
  await p.waitForFunction(() => ['done', 'unknown', 'error'].includes(window.__modda.state.phase), null, { timeout: 180000 });
  await p.waitForTimeout(4500);
  const st = await p.evaluate(() => window.__modda.state);
  check('answer arrived', st.phase === 'done' || st.phase === 'unknown', st.phase);
  check('every stage has a final status', Object.values(st.stages).every((s) => ['done', 'warning', 'skipped', 'failed', 'unobserved'].includes(s.status)), JSON.stringify(Object.fromEntries(Object.entries(st.stages).map(([k, v]) => [k, v.status]))));
  check('book controls visible after answer', await p.locator('.book-ui').isVisible());
  await shot(p, 'desktop-3-answer');

  // the graph glides to its answer layout after the book has landed: wait until the nodes stop moving
  const nodePos = () => p.evaluate(() => [...document.querySelectorAll('.node')].map((n) => { const b = n.getBoundingClientRect(); return `${Math.round(b.x)},${Math.round(b.y)}`; }).join(' '));
  for (let i = 0, last = ''; i < 40; i++) { const now = await nodePos(); if (now === last) break; last = now; await p.waitForTimeout(700); }
  for (const id of ['analyze', 'embed', 'vector', 'bm25', 'fuse', 'read', 'generate', 'verify']) {
    await p.click(`.node[data-node="${id}"]`, { force: true });
    await p.waitForSelector('.panel', { timeout: 5000 });
    await p.waitForTimeout(id === 'vector' || id === 'embed' ? 3500 : 600);
    const txt = await p.locator('.panel').innerText();
    check(`inspector ${id} opens`, txt.length > 40, `${txt.length} chars`);
    if (['embed', 'vector', 'fuse', 'verify'].includes(id)) await shot(p, `desktop-insp-${id}`);
    await closePanel(p);
  }
  check('panel closes with Esc', (await p.locator('.panel').count()) === 0);

  await p.click('.mind', { force: true });
  await p.waitForSelector('.panel'); await p.waitForTimeout(3000);
  check('Mind shows real layer count', /qatlam/.test(await p.locator('.panel').innerText()));
  await shot(p, 'desktop-insp-mind');
  await p.click('.seg button[data-kind="embedding"]'); await p.waitForTimeout(2500);
  check('Mind switches to the embedding model', /bge-m3|bert/i.test(await p.locator('.panel').innerText()));
  await closePanel(p);

  if (await p.locator('.justice-hit').isVisible()) {
    await p.click('.justice-hit', { force: true });
    await p.waitForTimeout(3200);
    check('statue comes to the centre (focus mode)', await p.evaluate(() => document.body.classList.contains('is-justice')));
    check('no 2-D scale window opens', (await p.locator('.panel').count()) === 0);
    const hudText = await p.locator('.justice-hud').innerText();
    check('scales caption shows the real score', /\d+\s*\/\s*100|javob yoʻq|Baholanadigan/i.test(hudText), hudText.replace(/\s+/g, ' ').slice(0, 80));
    await shot(p, 'desktop-justice-focus');
    await p.click('[data-action="sentences"]'); await p.waitForSelector('.panel'); await p.waitForTimeout(400);
    check('sentence list opens from the scales', /moslik|tasdiq/i.test(await p.locator('.panel').innerText()));
    await closePanel(p);
    await p.keyboard.press('Escape'); await p.waitForTimeout(1600);
    check('Esc leaves focus mode', !(await p.evaluate(() => document.body.classList.contains('is-justice'))));
  } else check('statue visible', false);

  await p.click('[data-action="reader"]');
  await p.waitForSelector('.reader'); await p.waitForTimeout(1200);
  check('reader shows answer and neighbouring moddas', (await p.locator('.reader__art').count()) >= 1 || st.phase === 'unknown');
  await shot(p, 'desktop-reader');
  await closePanel(p);

  if ((await p.locator('[data-action="page-next"]').isEnabled())) {
    await p.click('[data-action="page-next"]'); await p.waitForTimeout(2200);
    check('next source turns the page', (await p.evaluate(() => window.__modda.sourceIndex)) === 2);
    await shot(p, 'desktop-4-source2');
  }
  await p.click('.nav__item[data-action="graph"]'); await p.waitForTimeout(1600);
  await shot(p, 'desktop-5-graph-after-answer');
  await p.click('.nav__item[data-action="documents"]');
  await p.waitForSelector('.doclist button', { timeout: 10000 });
  check('documents list loads', (await p.locator('.doclist button').count()) > 0);
  await p.locator('.doclist button').first().click(); await p.waitForTimeout(1200);
  check('a document opens', (await p.locator('.reader__art').count()) > 0);
  await shot(p, 'desktop-documents');
  await closePanel(p);
  await p.click('.nav__item[data-action="help"]'); await p.waitForSelector('.steps');
  check('help opens', true); await closePanel(p);
  await p.click('.status'); await p.waitForSelector('.panel'); check('status panel opens', true); await closePanel(p);
  await p.click('.brand'); await p.waitForTimeout(1800);
  check('logo returns home', (await p.evaluate(() => window.__modda.state.phase)) === 'idle');
  check('desktop console clean', p.errors.length === 0, p.errors.slice(0, 5).join(' | '));
  await p.close();
}

// ---------------------------------------------------------------- other screen sizes
for (const [name, vp] of [['laptop', { width: 1280, height: 800 }], ['tablet', { width: 768, height: 1024 }], ['mobile', { width: 390, height: 844 }], ['small', { width: 360, height: 780 }]]) {
  const p = await page(vp);
  await p.waitForTimeout(1200);
  await shot(p, `${name}-1-idle`);
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  check(`${name}: no horizontal overflow`, !overflow);
  await askAndWait(p);
  await p.waitForTimeout(4000);
  await shot(p, `${name}-2-answer`);
  await p.click('.node[data-node="embed"]', { force: true }); await p.waitForSelector('.panel'); await p.waitForTimeout(2500);
  await shot(p, `${name}-3-inspector`);
  await closePanel(p);
  check(`${name}: console clean`, p.errors.length === 0, p.errors.slice(0, 3).join(' | '));
  await p.close();
}

// ---------------------------------------------------------------- without WebGL
{
  const p = await page({ width: 1280, height: 800 }, '?nowebgl');
  check('no-WebGL: plain layout', await p.evaluate(() => document.body.classList.contains('no-webgl')));
  await askAndWait(p);
  await p.waitForTimeout(1500);
  check('no-WebGL: answer shown in the reader', (await p.locator('.reader').count()) === 1);
  await shot(p, 'nowebgl-answer');
  check('no-WebGL: console clean', p.errors.length === 0, p.errors.slice(0, 3).join(' | '));
  await p.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
