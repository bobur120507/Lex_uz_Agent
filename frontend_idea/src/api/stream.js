// POST /ask/stream (Server-Sent Events). If the stream endpoint is missing or breaks before any event,
// falls back to POST /ask and reports the final answer as a `fallback.answer` event (stages unobserved).
import { request, api, ApiError } from './client.js';

export function parseSSE(buffer, onEvent) {
  const blocks = buffer.split(/\r?\n\r?\n/);
  const rest = blocks.pop();
  for (const block of blocks) {
    let type = 'message', data = '';
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) type = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).replace(/^ /, '');
    }
    if (!data) continue;
    let payload;
    try { payload = JSON.parse(data); } catch { continue; }
    onEvent(payload && payload.type ? payload : { type, data: payload });
  }
  return rest;
}

export async function askStream(question, onEvent, signal) {
  let got = 0, terminal = false;
  const emit = (ev) => { got++; if (['answer.completed', 'stage.failed'].includes(ev.type)) terminal = true; onEvent(ev); };
  let r;
  try {
    r = await request('/ask/stream', { method: 'POST', body: { question }, signal, timeout: 0, headers: { Accept: 'text/event-stream' } });
  } catch (err) {
    if (signal?.aborted) throw err;
    if (err instanceof ApiError && (err.status === 404 || err.status === 405)) return fallback(question, onEvent, signal);
    throw err;
  }
  if (!r.body) return fallback(question, onEvent, signal);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf = parseSSE(buf + dec.decode(value, { stream: true }), emit);
    }
    parseSSE(buf + '\n\n', emit);
  } catch (err) {
    if (signal?.aborted) throw err;
    if (!got) return fallback(question, onEvent, signal);
    throw new ApiError('Oqim uzildi — natija toʻliq emas', { cause: err });
  }
  if (!terminal) {
    if (!got) return fallback(question, onEvent, signal);
    throw new ApiError('Oqim javobsiz tugadi');
  }
}

async function fallback(question, onEvent, signal) {
  const answer = await api.askPlain(question, { signal });
  onEvent({ type: 'fallback.answer', request_id: answer.request_id, ts: new Date().toISOString(), data: answer });
}
