// Unit tests (node --test): the state machine follows backend events exactly and never invents progress.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initial, reduce, activeStage, orderedSources, stageMeta } from '../src/core/research.js';
import { parseSSE } from '../src/api/stream.js';

const ev = (type, data = {}, ts = '2026-11-06T10:00:00.000Z', rid = 'r1') => ({ type, request_id: rid, ts, data });
const run = (events, q = 'Taʼtil?') => events.reduce(reduce, initial(q));

test('stages advance only when their event arrives', () => {
  let s = run([ev('query.received', { question: 'Taʼtil?' })]);
  assert.equal(s.stages.analyze.status, 'running');
  assert.equal(s.stages.embed.status, 'waiting');
  assert.equal(activeStage(s), 'analyze');
  s = reduce(s, ev('query.analyzed', { route: 'semantic', terms: ['taʼtil'], ms: 1.5 }));
  assert.equal(s.stages.analyze.status, 'done');
  assert.equal(s.stages.analyze.ms, 1.5);
  assert.equal(activeStage(s), 'embed');
});

test('full run, durations from backend data or real timestamps', () => {
  const s = run([
    ev('query.received', { question: 'q' }, '2026-11-06T10:00:00.000Z'),
    ev('query.analyzed', { ms: 1 }, '2026-11-06T10:00:00.010Z'),
    ev('embedding.completed', { model: 'bge-m3', dim: 1024, ms: 40 }, '2026-11-06T10:00:00.050Z'),
    ev('retrieval.started', {}, '2026-11-06T10:00:00.051Z'),
    ev('retrieval.completed', { candidates: [{ chunk_id: 'a' }, { chunk_id: 'b' }], dense_list: [{ chunk_id: 'a' }], sparse_list: [{ chunk_id: 'b' }], ms: 120 }, '2026-11-06T10:00:00.171Z'),
    ev('ranking.completed', { reranker: false, selected: ['a'], rejected: ['b'] }, '2026-11-06T10:00:00.181Z'),
    ev('context.completed', { chunk_ids: ['a'] }, '2026-11-06T10:00:00.191Z'),
    ev('generation.started', { model: 'qwen3:8b' }, '2026-11-06T10:00:00.200Z'),
    ev('generation.delta', { text: 'Javob ' }), ev('generation.delta', { text: '[1].' }),
    ev('generation.completed', { model: 'qwen3:8b', gen_ms: 900, output_tokens: 12 }, '2026-11-06T10:00:01.200Z'),
    ev('verification.completed', { verified: ['a'], failed: [] }, '2026-11-06T10:00:01.210Z'),
    ev('scoring.completed', { score: 80, total: 1, supported: 1 }),
    ev('answer.completed', { unknown: false, answer: [{ text: 'Javob [1].', chunk_ids: ['a'] }], sources: { a: { title: 'MK' } } }, '2026-11-06T10:00:01.220Z'),
  ]);
  assert.equal(s.phase, 'done');
  assert.deepEqual(Object.values(s.stages).map((x) => x.status), Array(8).fill('done'));
  assert.equal(s.stages.fuse.ms, 10);                        // from timestamps: 171 → 181 ms
  assert.equal(s.stages.generate.ms, 900);
  assert.equal(s.generation.text, 'Javob [1].');
  assert.equal(s.score.score, 80);
  assert.equal(stageMeta(s, 'embed'), '40 ms');
});

test('unknown answer before the LLM: remaining stages are skipped, never done', () => {
  const s = run([ev('query.received'), ev('query.analyzed'), ev('embedding.completed', { ms: 5 }), ev('retrieval.started'),
    ev('retrieval.completed', { candidates: [] }), ev('ranking.completed', { selected: [] }),
    ev('answer.completed', { unknown: true, answer: [], sources: {} })]);
  assert.equal(s.phase, 'unknown');
  assert.equal(s.stages.vector.status, 'warning');
  assert.equal(s.stages.generate.status, 'skipped');
  assert.equal(s.stages.verify.status, 'skipped');
});

test('failure marks the running stage failed and keeps the question', () => {
  const s = run([ev('query.received'), ev('query.analyzed'), ev('stage.failed', { stage: 'server', message: 'Ollama yoʻq' })], 'Savol');
  assert.equal(s.phase, 'error');
  assert.equal(s.stages.embed.status, 'failed');
  assert.equal(s.question, 'Savol');
  assert.equal(s.error.message, 'Ollama yoʻq');
});

test('events of another request and events after the end are ignored', () => {
  let s = run([ev('query.received')]);
  const before = s;
  s = reduce(s, ev('query.analyzed', {}, undefined, 'other'));
  assert.equal(s, before);
  s = run([ev('query.received'), ev('answer.completed', { unknown: true, answer: [], sources: {} })]);
  assert.equal(reduce(s, ev('generation.delta', { text: 'x' })), s);
});

test('plain /ask fallback: stages are "unobserved", not invented', () => {
  const s = reduce(initial('q'), { type: 'fallback.answer', data: { unknown: false, answer: [], sources: {}, request_id: 'z' } });
  assert.equal(s.phase, 'done');
  assert.ok(Object.values(s.stages).every((x) => x.status === 'unobserved'));
});

test('sources are numbered in citation order', () => {
  const srcs = orderedSources({ unknown: false, answer: [{ text: 'x', chunk_ids: ['b'] }, { text: 'y', chunk_ids: ['a', 'b'] }], sources: { a: { title: 'A' }, b: { title: 'B' } } });
  assert.deepEqual(srcs.map((s) => [s.n, s.chunk_id]), [[1, 'b'], [2, 'a']]);
  assert.deepEqual(orderedSources({ unknown: true }), []);
});

test('SSE parser: named events, split chunks, broken JSON skipped', () => {
  const got = [];
  let rest = parseSSE('event: query.received\ndata: {"type":"query.received","request_id":"r","data":{}}\n\nevent: x\ndata: {bro', (e) => got.push(e));
  assert.equal(got.length, 1);
  rest = parseSSE(`${rest}ken\n\nevent: answer.completed\ndata: {"type":"answer.completed","data":{"unknown":true}}\n\n`, (e) => got.push(e));
  assert.equal(rest, '');
  assert.deepEqual(got.map((e) => e.type), ['query.received', 'answer.completed']);
});
