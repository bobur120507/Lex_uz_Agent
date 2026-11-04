// Talks to FastAPI: POST /ask/stream (Server-Sent Events) → falls back to POST /ask → falls back to sample data.
import { mockStream } from './mock.js';

const API = (window.MODDA_API ?? '').replace(/\/$/, '');
const EXPLICIT = window.MODDA_API !== undefined;
const FORCE_MOCK = new URLSearchParams(location.search).has('demo');

export let usingMock = FORCE_MOCK;

function parseSSE(buffer, onEvent) {
  const blocks = buffer.split('\n\n');
  const rest = blocks.pop();
  for (const block of blocks) {
    let event = 'message', data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
    }
    if (data) {
      try { onEvent(event, JSON.parse(data)); } catch { /* ignore a broken event */ }
    }
  }
  return rest;
}

async function streamAsk(question, onEvent, signal) {
  const r = await fetch(`${API}/ask/stream`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question }), signal,
  });
  if (r.status === 404 || r.status === 405) return plainAsk(question, onEvent, signal);
  if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '', gotAnswer = false;
  const wrapped = (ev, data) => { if (ev === 'answer') gotAnswer = true; onEvent(ev, data); };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf = parseSSE(buf + dec.decode(value, { stream: true }), wrapped);
  }
  parseSSE(buf + '\n\n', wrapped);
  if (!gotAnswer) throw new Error('Oqim javobsiz tugadi');
}

async function plainAsk(question, onEvent, signal) {
  onEvent('stage', { name: 'retrieving' });
  const r = await fetch(`${API}/ask`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  onEvent('answer', await r.json());
}

export async function ask(question, onEvent, signal) {
  if (usingMock) return mockStream(question, onEvent, signal);
  try {
    await streamAsk(question, onEvent, signal);
  } catch (err) {
    if (err.name === 'AbortError' || EXPLICIT) throw err;
    usingMock = true;                      // no server next to the page: sample data from now on
    return mockStream(question, onEvent, signal);
  }
}

export async function health() {
  if (FORCE_MOCK) return null;
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2500) });
    if (!r.ok) throw new Error();
    return await r.json();
  } catch {
    if (!EXPLICIT) usingMock = true;
    return null;
  }
}
