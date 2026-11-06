// The research state machine. Pure functions: backend events in → state out. No timers, no animation —
// the interface only *shows* this state, so a stage is "done" exactly when the backend said so (§13).
import { STAGES } from '../config.js';

const ORDER = STAGES.map((s) => s.id);

export function initial(question = '') {
  return {
    question, requestId: null, phase: 'idle',
    stages: Object.fromEntries(ORDER.map((id) => [id, { status: 'waiting', ms: null, start: null }])),
    analysis: null, embedding: null, retrieval: null, ranking: null, context: null,
    generation: { model: null, text: '', stats: null }, verification: null, score: null,
    answer: null, error: null, observed: true, startedAt: null, finishedAt: null,
  };
}

/** The stage the centre of the graph shows: the first one still running (or null). */
export function activeStage(state) {
  return ORDER.find((id) => state.stages[id].status === 'running') || null;
}

const t = (ts) => (ts ? Date.parse(ts) : NaN);

function set(state, id, patch) {
  return { ...state, stages: { ...state.stages, [id]: { ...state.stages[id], ...patch } } };
}
function run(state, ids, ts) {
  let s = state;
  for (const id of ids) if (s.stages[id].status === 'waiting') s = set(s, id, { status: 'running', start: ts });
  return s;
}
function finish(state, id, ts, { ms, status = 'done' } = {}) {
  const st = state.stages[id];
  const dur = Number.isFinite(ms) ? ms : (Number.isFinite(t(ts) - t(st.start)) ? t(ts) - t(st.start) : null);
  return set(state, id, { status, ms: dur, start: st.start ?? ts });
}

export function reduce(state, ev) {
  if (!ev || !ev.type) return state;
  const d = ev.data ?? {};
  const ts = ev.ts ?? null;
  // events of another (older) request are ignored once this request has an id
  if (state.requestId && ev.request_id && ev.request_id !== state.requestId) return state;
  if (['done', 'unknown', 'error'].includes(state.phase) && ev.type !== 'fallback.answer') return state;

  let s = state;
  switch (ev.type) {
    case 'query.received':
      s = { ...s, requestId: ev.request_id ?? s.requestId, phase: 'running', startedAt: ts,
            analysis: { ...(s.analysis || {}), normalized: d.question, original: d.original ?? s.question } };
      return run(s, ['analyze'], ts);
    case 'query.analyzed':
      s = { ...s, analysis: { ...(s.analysis || {}), ...d } };
      s = finish(run(s, ['analyze'], ts), 'analyze', ts, { ms: d.ms });
      return run(s, ['embed'], ts);
    case 'embedding.completed':
      s = { ...s, embedding: d };
      return finish(run(s, ['embed'], ts), 'embed', ts, { ms: d.ms });
    case 'retrieval.started':
      s = { ...s, retrieval: { ...(s.retrieval || {}), ...d } };
      return run(s, ['vector', 'bm25'], ts);
    case 'retrieval.completed': {
      s = { ...s, retrieval: { ...(s.retrieval || {}), ...d } };
      s = run(s, ['vector', 'bm25'], ts);
      const none = !(d.candidates || []).length;
      const dense = (d.dense_list || []).length, sparse = (d.sparse_list || []).length;
      s = finish(s, 'vector', ts, { ms: d.ms, status: none || (d.dense_list && !dense) ? 'warning' : 'done' });
      s = finish(s, 'bm25', ts, { ms: d.ms, status: none || (d.sparse_list && !sparse) ? 'warning' : 'done' });
      return run(s, ['fuse'], ts);
    }
    case 'ranking.completed':
      s = { ...s, ranking: d };
      s = finish(run(s, ['fuse'], ts), 'fuse', ts, { ms: d.ms, status: (d.selected || []).length ? 'done' : 'warning' });
      return run(s, ['read'], ts);
    case 'context.completed':
      s = { ...s, context: d };
      return finish(run(s, ['read'], ts), 'read', ts);
    case 'generation.started':
      s = { ...s, generation: { ...s.generation, model: d.model } };
      return run(s, ['generate'], ts);
    case 'generation.delta':
      return { ...s, generation: { ...s.generation, text: s.generation.text + (d.text || '') } };
    case 'generation.completed':
      s = { ...s, generation: { ...s.generation, stats: d, model: d.model ?? s.generation.model } };
      s = finish(run(s, ['generate'], ts), 'generate', ts, { ms: d.gen_ms ?? d.ms });
      return run(s, ['verify'], ts);
    case 'verification.completed':
      s = { ...s, verification: d };
      if (s.stages.generate.status === 'running') s = finish(s, 'generate', ts, { ms: d.llm_ms });
      return finish(run(s, ['verify'], ts), 'verify', ts, { status: (d.failed || []).length ? 'warning' : 'done' });
    case 'scoring.completed':
      return { ...s, score: d };
    case 'answer.completed':
    case 'fallback.answer': {
      const observed = ev.type === 'answer.completed';
      s = { ...s, answer: d, score: d.score ?? s.score, phase: d.unknown ? 'unknown' : 'done', finishedAt: ts, observed,
            requestId: s.requestId ?? d.request_id ?? null };
      for (const id of ORDER) {
        const st = s.stages[id].status;
        if (st === 'waiting' || st === 'running') s = set(s, id, { status: observed ? 'skipped' : 'unobserved' });
      }
      return s;
    }
    case 'stage.failed': {
      s = { ...s, error: { stage: d.stage, message: d.message || 'Server xatosi' }, phase: 'error', finishedAt: ts };
      let marked = false;
      for (const id of ORDER) if (s.stages[id].status === 'running') { s = set(s, id, { status: 'failed' }); marked = true; }
      if (!marked) {
        const next = ORDER.find((id) => s.stages[id].status === 'waiting');
        if (next) s = set(s, next, { status: 'failed' });
      }
      return s;
    }
    default:
      return s;                                          // unknown events are for future versions
  }
}

/** Short status text under a node: real elapsed time only. */
export function stageMeta(state, id) {
  const st = state.stages[id];
  const ms = st.ms;
  const time = Number.isFinite(ms) ? (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`) : '';
  switch (st.status) {
    case 'running': return 'bajarilmoqda…';
    case 'done': return time || 'bajarildi';
    case 'warning': return time ? `${time} · diqqat` : 'diqqat';
    case 'failed': return 'xato';
    case 'skipped': return 'oʻtkazildi';
    case 'unobserved': return 'kuzatilmadi';
    default: return '';
  }
}

/** Sources of the answer in reference order [1], [2]… (as the LLM cited them). */
export function orderedSources(answer) {
  if (!answer || answer.unknown) return [];
  const seen = [];
  for (const s of answer.answer || []) for (const id of s.chunk_ids || []) if (!seen.includes(id)) seen.push(id);
  for (const id of Object.keys(answer.sources || {})) if (!seen.includes(id)) seen.push(id);
  return seen.filter((id) => answer.sources?.[id]).map((id, i) => ({ n: i + 1, chunk_id: id, ...answer.sources[id] }));
}
