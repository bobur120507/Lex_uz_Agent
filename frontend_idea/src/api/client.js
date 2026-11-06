// The only place that talks to the backend. Every function returns real API data or throws ApiError.
import { API } from '../config.js';

export class ApiError extends Error {
  constructor(message, { status = 0, cause } = {}) { super(message); this.status = status; this.cause = cause; }
}

export async function request(path, { method = 'GET', body, signal, timeout = 20000, headers = {} } = {}) {
  const ctl = new AbortController();
  const timer = timeout ? setTimeout(() => ctl.abort(new DOMException('timeout', 'TimeoutError')), timeout) : null;
  const onAbort = () => ctl.abort(signal.reason);
  signal?.addEventListener('abort', onAbort, { once: true });
  try {
    const r = await fetch(`${API}${path}`, {
      method, signal: ctl.signal,
      headers: body ? { 'Content-Type': 'application/json', ...headers } : headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) {
      let detail = '';
      try { detail = (await r.json()).detail; } catch { /* not JSON */ }
      throw new ApiError(detail || `HTTP ${r.status}`, { status: r.status });
    }
    return r;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (signal?.aborted) throw err;
    const msg = err?.name === 'TimeoutError' || ctl.signal.reason?.name === 'TimeoutError'
      ? 'Server javob bermadi (vaqt tugadi)' : 'Serverga ulanib boʻlmadi';
    throw new ApiError(msg, { cause: err });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

export const getJSON = async (path, opts) => (await request(path, opts)).json();

export const api = {
  health: (opts) => getJSON('/health', { timeout: 8000, ...opts }),
  modelInfo: (opts) => getJSON('/model/info', opts),
  embedding: (rid, opts) => getJSON(`/ask/${encodeURIComponent(rid)}/embedding`, { timeout: 60000, ...opts }),
  trace: (rid, opts) => getJSON(`/ask/${encodeURIComponent(rid)}/trace`, opts),
  chunkContext: (cid, n = 5, opts) => getJSON(`/chunks/${encodeURIComponent(cid)}/context?n=${n}`, opts),
  articleContext: (aid, n = 5, opts) => getJSON(`/articles/${encodeURIComponent(aid)}/context?n=${n}`, opts),
  documents: (q = '', opts) => getJSON(`/documents?q=${encodeURIComponent(q)}&limit=30`, opts),
  document: (id, offset = 0, opts) => getJSON(`/documents/${encodeURIComponent(id)}?offset=${offset}&limit=20`, opts),
  askPlain: async (question, opts) => (await request('/ask', { method: 'POST', body: { question }, timeout: 0, ...opts })).json(),
};
