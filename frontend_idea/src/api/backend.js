// Chooses the data source: the real API, or (only with ?demo in the URL) a recorded sample run.
// Demo data is never mixed with real data, and the page shows a banner while it is used.
import { DEMO, BASE } from '../config.js';
import { api } from './client.js';
import { askStream } from './stream.js';

export async function createBackend() {
  if (!DEMO) return { demo: false, api, askStream };
  const fixture = await (await fetch(`${BASE}demo/fixture.json`)).json();
  return { demo: true, ...demoBackend(fixture) };
}

const sleep = (ms, signal) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms);
  signal?.addEventListener('abort', () => { clearTimeout(t); reject(signal.reason ?? new DOMException('aborted', 'AbortError')); }, { once: true });
});

export function demoBackend(fx) {
  const miss = (what) => Promise.reject(Object.assign(new Error(`Namunada yoʻq: ${what}`), { status: 404 }));
  const demoApi = {
    health: async () => ({ ...fx.health, demo: true }),
    modelInfo: async () => fx.model,
    embedding: async (rid) => (rid === fx.request_id ? fx.embedding : miss('embedding')),
    trace: async () => miss('trace'),
    chunkContext: async (cid) => fx.contexts?.[cid] ?? miss(cid),
    articleContext: async (aid) => Object.values(fx.contexts || {}).find((c) => c.articles.some((a) => a.article_id === aid)) ?? miss(aid),
    documents: async (q = '') => ({ q, documents: (fx.documents || []).filter((d) => d.title.toLowerCase().includes(q.toLowerCase())) }),
    document: async (id) => fx.document_pages?.[id] ?? miss(id),
    askPlain: async () => fx.events.at(-1).ev.data,
  };
  async function demoStream(question, onEvent, signal) {
    for (const { dt, ev } of fx.events) {
      await sleep(Math.min(dt, 900), signal);
      onEvent(ev);
    }
  }
  return { api: demoApi, askStream: demoStream, fixture: fx };
}
