// One inspector per processing stage. Each shows only what the backend returned for this request;
// anything not available is said plainly («Mavjud emas»), never filled in.
import { STAGE, ICONS } from '../config.js';
import { stageMeta } from '../core/research.js';
import { openPanel } from './overlay.js';
import { h, kv, card, tag, unavailable, fmtMs, fmtNum, fmtBig, copyText } from './dom.js';
import { toast } from './toast.js';
import { heatmap } from '../viz/heatmap.js';
import { pcaCloud } from '../viz/cloud.js';
import { rankFlow } from '../viz/rankflow.js';

const TONE = { done: 'emerald', running: 'gold', warning: 'amber', failed: 'red', skipped: '', unobserved: '', waiting: '' };
const WORD = { done: 'bajarildi', running: 'bajarilmoqda', warning: 'ogohlantirish', failed: 'xato', skipped: 'oʻtkazildi', unobserved: 'kuzatilmadi', waiting: 'kutilmoqda' };

// embedding payloads are cached per request (they are large and do not change)
const cache = new Map();
export function embeddingFor(backend, rid) {
  if (!rid) return Promise.reject(new Error('Soʻrov yoʻq'));
  if (!cache.has(rid)) cache.set(rid, backend.api.embedding(rid).catch((e) => { cache.delete(rid); throw e; }));
  return cache.get(rid);
}
let modelCard = null;
export function modelInfo(backend) {
  if (!modelCard) modelCard = backend.api.modelInfo().catch((e) => { modelCard = null; throw e; });
  return modelCard;
}

function candidateLabel(state) {
  const by = new Map((state.retrieval?.candidates || []).map((c) => [c.chunk_id, c]));
  return (id) => {
    const c = by.get(id);
    if (c) return `${c.article_no ? `${c.article_no}-m. ` : ''}${c.doc_title || id}`;
    return id;
  };
}

function idleNote(state) {
  return state.phase === 'idle' ? unavailable('Hali savol berilmagan. Savol yuborilgach, bu yerda shu bosqichning haqiqiy maʼlumotlari koʻrinadi.') : null;
}

function loading(text = 'Yuklanmoqda…') { return h('p', { class: 'note', role: 'status' }, text); }

// ---------------------------------------------------------------- 01 analysis
function analyze(state) {
  const a = state.analysis;
  if (!a) return idleNote(state) || unavailable('Bu bosqich maʼlumoti hali kelmadi.');
  const ref = a.reference;
  return [
    h('div', { class: 'grid2' },
      card('Savol',
        h('p', { class: 'note' }, 'Foydalanuvchi yozgani'), h('p', { class: 'stream' }, a.original ?? state.question),
        a.normalized && a.normalized !== a.original ? [h('p', { class: 'note' }, 'Normallashtirilgan (kirill → lotin, belgilar)'), h('p', { class: 'stream' }, a.normalized)] : null,
        a.query_form ? [h('p', { class: 'note' }, 'Qidiruv uchun shakl'), h('p', { class: 'stream mono' }, a.query_form)] : null),
      card('Natija', kv([
        ['Yoʻnalish', a.route === 'exact' ? 'aniq havola' : a.route === 'semantic' ? 'maʼno boʻyicha' : (a.route ?? '—')],
        ref ? ['Havola', `${ref.document || ''} ${ref.article ? `${ref.article}-modda` : ''}`.trim()] : null,
        ['Vaqt', fmtMs(a.ms ?? state.stages.analyze.ms)],
      ]), a.route === 'exact' ? h('p', { class: 'note' }, 'Savolda aniq modda koʻrsatilgan: u qidiruvdan oldin toʻgʻridan-toʻgʻri olinadi.') : null)),
    card(['Qidiruv soʻzlari', `${(a.terms || []).length} ta`], (a.terms || []).length ? h('div', { class: 'chiprow' }, a.terms.map((t) => tag(t, 'gold'))) : unavailable('Soʻzlar qaytarilmadi.'),
      (a.concepts || []).length ? [h('p', { class: 'note' }, 'Aniqlangan tushunchalar'), h('div', { class: 'chiprow' }, a.concepts.map((t) => tag(t, 'cyan')))] : null),
  ];
}

// ---------------------------------------------------------------- 02 embedding
function embed(state, ctx, panel) {
  const e = state.embedding;
  if (!e) return idleNote(state) || unavailable('Embedding hali tayyor emas.');
  const holder = h('div', {}, loading('Vektor yuklanmoqda…'));
  const archHolder = h('div', {}, loading('Model maʼlumoti…'));
  embeddingFor(ctx.backend, state.requestId).then((d) => {
    holder.replaceChildren(vectorView(d));
  }).catch((err) => holder.replaceChildren(unavailable(`Exact vector payload is not available. (${err.message})`)));
  modelInfo(ctx.backend).then((m) => archHolder.replaceChildren(archCard(m.embedding, () => ctx.openMind('embedding'))))
    .catch(() => archHolder.replaceChildren(unavailable('Model kartasi mavjud emas.')));
  return [
    kv([['Model', e.model], ['Oʻlcham', fmtNum(e.dim), 'float'], ['Tokenlar', e.tokens ?? '—'], ['Vaqt', fmtMs(e.ms)], ['Norma', e.norm ?? '—']]),
    holder, archHolder,
  ];
}

function vectorView(d) {
  const v = d.vector;
  const PAGE = 64;
  let page = 0, hit = -1;
  const vals = h('div', { class: 'vals', role: 'list' });
  const where = h('span');
  const render = () => {
    vals.replaceChildren(...v.slice(page * PAGE, page * PAGE + PAGE).map((x, k) => {
      const i = page * PAGE + k;
      return h('span', { role: 'listitem', class: i === hit ? 'is-hit' : '' }, h('b', {}, `[${i}]`), x.toFixed(6));
    }));
    where.textContent = `${page * PAGE}–${Math.min(v.length, page * PAGE + PAGE) - 1} / ${v.length}`;
  };
  const hm = heatmap(v, { onSelect: (i) => { hit = i; page = Math.floor(i / PAGE); render(); } });
  const find = h('input', { type: 'number', min: 0, max: v.length - 1, placeholder: 'oʻlcham №', 'aria-label': 'Oʻlcham raqami', style: { width: '120px' } });
  const go = () => { const i = Number(find.value); if (Number.isInteger(i) && i >= 0 && i < v.length) { hit = i; page = Math.floor(i / PAGE); hm.select(i); render(); } };
  find.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  render();
  return h('div', { class: 'grid2' },
    card(['Aniq vektor', `${d.dim} × ${d.dtype}`], hm.el,
      h('p', { class: 'note' }, 'Har bir katak — bitta oʻlcham: oltin — musbat, moviy — manfiy qiymat; yorqinlik — qiymat kattaligi. Katakni bosing.'),
      kv([['min', d.stats.min.toFixed(4)], ['max', d.stats.max.toFixed(4)], ['oʻrtacha', d.stats.mean.toFixed(5)], ['norma', d.norm.toFixed(4)]])),
    card('Qiymatlar',
      h('div', { class: 'field' }, find, h('button', { type: 'button', class: 'btn btn--sm', onclick: go }, 'Topish'),
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: () => copyText(JSON.stringify({ model: d.model, dim: d.dim, vector: v })).then(() => toast('Vektor JSON nusxalandi')) }, 'JSON nusxalash')),
      h('div', { class: 'pager' },
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Oldingi', onclick: () => { page = Math.max(0, page - 1); render(); } }, '‹'), where,
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Keyingi', onclick: () => { page = Math.min(Math.ceil(v.length / PAGE) - 1, page + 1); render(); } }, '›')),
      vals));
}

export function archCard(c, onOpen) {
  if (!c || c.error) return unavailable(`Model kartasi mavjud emas${c?.error ? ` (${c.error})` : ''}.`);
  return card([`${c.name} — arxitektura`, c.source],
    kv([['Arxitektura', c.architecture], ['Qatlamlar', c.layers], ['Kenglik', fmtNum(c.hidden_size), 'neyron'], ['Attention boshlari', c.attention_heads],
      c.kv_heads ? ['KV boshlar', c.kv_heads] : null, ['FFN', fmtNum(c.ffn_size)], ['Kontekst', fmtNum(c.context_length), 'token'],
      ['Parametrlar', c.parameter_size ?? fmtBig(c.parameter_count)], c.quantization ? ['Kvantlash', c.quantization] : null]),
    onOpen ? h('button', { type: 'button', class: 'btn btn--gold', onclick: onOpen }, 'Qatlamlarni 3D’da koʻrish') : null);
}

// ---------------------------------------------------------------- 03 vector search
function vector(state, ctx, panel) {
  const r = state.retrieval;
  if (!r?.candidates) return idleNote(state) || unavailable('Qidiruv natijasi hali kelmadi.');
  const label = candidateLabel(state);
  const viz = h('div', { class: 'viz' });
  const info = h('div', {}, loading('Proeksiya hisoblanmoqda…'));
  const toggles = h('div', { class: 'viz__hud' });
  viz.append(toggles);
  embeddingFor(ctx.backend, state.requestId).then((d) => {
    if (!d.projection) { viz.replaceWith(unavailable(`3D proeksiya mavjud emas${d.projection_error ? `: ${d.projection_error}` : ''}.`)); info.replaceChildren(); return; }
    const cloud = pcaCloud(viz, d, { onPick: (c) => ctx.showSource(c.chunk_id) });
    panel.onCleanup(() => cloud.view.dispose());
    const tg = (name, fn) => { let on = true; const b = h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-pressed': 'true' }, name); b.onclick = () => { on = !on; b.setAttribute('aria-pressed', String(on)); fn(on); }; return b; };
    toggles.append(tg('Fon nuqtalari', cloud.toggleCloud), tg('Chiziqlar', cloud.toggleLines), tg('Savol', cloud.toggleQuery),
      h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: () => cloud.view.reset() }, 'Kamera'));
    const c = d.projection.coordinates;
    info.replaceChildren(kv([['Usul', d.projection.method], ['Versiya', d.projection.transform_version], ['Namuna', fmtNum(d.projection.fitted_on), 'nuqta'],
      ['Savol XYZ', `${c.x.toFixed(3)}, ${c.y.toFixed(3)}, ${c.z.toFixed(3)}`], ['Dispersiya', d.projection.explained_variance.map((x) => `${(x * 100).toFixed(1)}%`).join(' · ')]]),
    h('p', { class: 'note' }, '1024 oʻlchamni toʻgʻridan-toʻgʻri koʻrib boʻlmaydi: bu — oʻsha vektorlarning PCA orqali 3 oʻqqa tushirilgan, versiyali proeksiyasi. Masofalar taxminan saqlanadi, aniq qiymatlar «Embedding» bosqichida.'),
    h('div', { class: 'legend' }, h('span', {}, h('i', { style: { background: '#39d6a0' } }), 'savol'), h('span', {}, h('i', { style: { background: '#73afe0' } }), 'topilgan boʻlaklar'), h('span', {}, h('i', { style: { background: '#6f8279' } }), 'indeksdan namuna')));
  }).catch((err) => { viz.replaceWith(unavailable(`Vektor maʼlumoti mavjud emas (${err.message}).`)); info.replaceChildren(); });
  const dense = r.dense_list || [];
  return [
    h('div', { class: 'grid2' }, viz, info),
    card(['Vektor qidiruv tartibi', `${dense.length} ta`], dense.length ? table(['#', 'Boʻlak', 'kosinus'], dense.slice(0, 15).map((x) => [x.rank, link(label(x.chunk_id), () => ctx.showSource(x.chunk_id)), x.score?.toFixed(4)]))
      : unavailable('Alohida dense roʻyxat qaytarilmadi (faqat birlashtirilgan natija).')),
  ];
}

function link(text, fn) { return h('button', { type: 'button', class: 'link', onclick: fn }, text); }
function table(head, rows, rowClass = () => '') {
  return h('table', { class: 'table' }, h('thead', {}, h('tr', {}, head.map((x, i) => h('th', { class: i === head.length - 1 ? 'num' : '' }, x)))),
    h('tbody', {}, rows.map((r, i) => h('tr', { class: rowClass(i) }, r.map((c, j) => h('td', { class: j === r.length - 1 || typeof c === 'number' ? 'num' : '' }, c ?? '—'))))));
}

// ---------------------------------------------------------------- 04 BM25
function bm25(state, ctx) {
  const r = state.retrieval;
  if (!r) return idleNote(state) || unavailable('Qidiruv hali boshlanmadi.');
  const terms = r.bm25_terms || state.analysis?.terms || [];
  const sp = r.sparse_list || [];
  const max = Math.max(...sp.map((x) => x.score || 0), 1);
  const label = candidateLabel(state);
  return [
    card(['Soʻrov soʻzlari', `${terms.length} ta`], h('div', { class: 'chiprow' }, terms.map((t) => tag(t, 'gold'))),
      h('p', { class: 'note' }, `Indeks: ${r.collection || '—'} — Lex.uz hujjatlaridan yigʻilgan. Bu jonli lex.uz sayti emas: qidiruv shu kompyuterdagi indeksda bajariladi.`)),
    card(['BM25 tartibi', `${sp.length} ta`], sp.length
      ? table(['#', 'Boʻlak', '', 'BM25'], sp.slice(0, 15).map((x) => [x.rank, link(label(x.chunk_id), () => ctx.showSource(x.chunk_id)), h('div', { class: 'bar' }, h('i', { style: { width: `${(100 * (x.score || 0)) / max}%` } })), x.score?.toFixed(3)]))
      : unavailable(r.candidates ? 'Kalit soʻzlar boʻyicha hech narsa topilmadi yoki roʻyxat qaytarilmadi.' : 'Natija hali kelmadi.')),
  ];
}

// ---------------------------------------------------------------- 05 fusion / selection
function fuse(state, ctx) {
  const r = state.retrieval, k = state.ranking;
  if (!r?.candidates) return idleNote(state) || unavailable('Saralash uchun nomzodlar hali yoʻq.');
  const label = candidateLabel(state);
  const selected = k?.selected || [];
  const rows = r.candidates.map((c) => [c.rank, link(label(c.chunk_id), () => ctx.showSource(c.chunk_id)), c.exact ? tag('aniq havola', 'gold') : c.dense_rank ?? '—', c.sparse_rank ?? '—',
    selected.includes(c.chunk_id) ? tag('tanlandi', 'emerald') : k ? tag('chiqarildi') : '…', c.score != null ? c.score.toFixed(4) : '—']);
  return [
    h('div', { class: 'chiprow' }, tag(`birlashtirish: ${r.fusion || 'rrf'}`, 'gold'),
      k ? (k.reranker ? tag(`reranker: ${k.model || 'yoqilgan'}`, 'cyan') : tag('reranker: faol emas')) : tag('saralash kutilmoqda'),
      k?.tau != null ? tag(`τ = ${k.tau}`, 'amber') : null, k?.top_score != null ? tag(`eng yuqori ball ${k.top_score}`) : null),
    card('Ikki roʻyxat → bitta tartib', rankFlow({ dense: r.dense_list || [], sparse: r.sparse_list || [], fused: r.candidates, selected, label: (id) => label(id) }),
      h('p', { class: 'note' }, 'Reciprocal Rank Fusion: har bir boʻlakning ikkala roʻyxatdagi oʻrni hisobga olinadi; ikkalasida ham yuqori boʻlgani oldinga chiqadi.')),
    card(['Nomzodlar', `${r.candidates.length} ta`], table(['#', 'Boʻlak', 'dense #', 'BM25 #', 'holat', 'RRF ball'], rows, (i) => (selected.includes(r.candidates[i].chunk_id) ? 'is-selected' : k ? 'is-rejected' : ''))),
  ];
}

// ---------------------------------------------------------------- 06 reading (context)
function read(state, ctx) {
  const c = state.context;
  if (!c) return idleNote(state) || unavailable('Kontekst hali tuzilmadi.');
  const list = h('div', {});
  for (const p of c.passages || c.chunk_ids.map((id, i) => ({ chunk_id: id, n: i + 1 }))) {
    const body = h('div', {});
    const open = h('button', { type: 'button', class: 'btn btn--sm btn--ghost' }, 'Matnni koʻrsatish');
    open.onclick = async () => {
      open.disabled = true; body.replaceChildren(loading());
      try {
        const d = await ctx.backend.api.chunkContext(p.chunk_id, 0);
        const a = d.articles.find((x) => x.is_target) || d.articles[0];
        body.replaceChildren(h('p', { class: 'stream' }, a?.text || '—'));
      } catch (err) { body.replaceChildren(unavailable(`Matn olinmadi: ${err.message}`)); }
    };
    list.append(h('section', { class: 'sentence' }, h('p', {}, h('b', {}, `[${p.n}] `), p.header || p.chunk_id),
      h('footer', {}, p.words ? tag(`${p.words} soʻz`) : null, tag(p.chunk_id), open, h('button', { type: 'button', class: 'btn btn--sm', onclick: () => ctx.showSource(p.chunk_id) }, 'Kitobda ochish')), body));
  }
  return [kv([['Parchalar', c.chunk_ids.length], ['Kontekst hajmi', c.chars ? fmtNum(c.chars) : '—', 'belgi'], ['Vaqt', fmtMs(state.stages.read.ms)]]),
    h('p', { class: 'note' }, 'Shu parchalar — va faqat shular — LLM’ga beriladi. Model ularni [1], [2] … raqamlari bilan koʻrsatishi shart.'), list];
}

// ---------------------------------------------------------------- 07 LLM
function generate(state, ctx, panel) {
  const g = state.generation;
  if (!g?.model && state.stages.generate.status === 'waiting') return idleNote(state) || unavailable(state.phase === 'unknown' ? 'Javob yozilmadi: mos manba topilmadi.' : 'LLM hali ishga tushmadi.');
  const s = g.stats || {};
  const live = state.stages.generate.status === 'running';
  const stream = h('div', { class: `stream${live ? ' is-live' : ''}`, 'aria-live': 'off' }, g.text || (live ? '' : '— (matn oqimi kelmadi; yakuniy javob kitobda)'));
  panel.live = (st) => { stream.textContent = st.generation.text; stream.classList.toggle('is-live', st.stages.generate.status === 'running'); };
  return [
    kv([['Model', g.model], ['Kirish tokenlari', s.prompt_tokens ?? '—'], ['Chiqish tokenlari', s.output_tokens ?? '—'], ['Tezlik', s.tokens_per_s ? `${s.tokens_per_s} tok/s` : '—'],
      ['Kontekstni oʻqish', fmtMs(s.prompt_ms)], ['Yozish', fmtMs(s.gen_ms ?? s.ms)], ['Yuklash', fmtMs(s.load_ms)]]),
    card(['Model yozayotgan matn', live ? 'jonli' : 'tugadi'], stream,
      h('p', { class: 'note' }, 'Bu — modelning chiqishi (javob matni). Ichki “fikrlash” koʻrsatilmaydi va oʻylab topilmaydi; faqat oʻlchanadigan raqamlar: tokenlar, vaqt, tezlik.')),
    h('button', { type: 'button', class: 'btn btn--gold', onclick: () => ctx.openMind('llm') }, 'Neyron qatlamlarini koʻrish'),
  ];
}

// ---------------------------------------------------------------- 08 verification
function verify(state, ctx) {
  const v = state.verification;
  if (!v) return idleNote(state) || unavailable('Tekshiruv hali bajarilmadi.');
  const sents = v.sentences || [];
  return [
    h('div', { class: 'chiprow' }, tag(`${sents.filter((s) => s.ok).length} ta tasdiqlandi`, 'emerald'), tag(`${(v.failed || []).length} ta rad etildi`, (v.failed || []).length ? 'amber' : '')),
    h('p', { class: 'note' }, 'Qoida: har bir gap berilgan manbaga havola qilishi va undagi har bir raqam shu manbada boʻlishi shart. Rad etilgan gap javobga kirmaydi.'),
    sents.length ? h('div', {}, sents.map((s) => h('section', { class: `sentence ${s.ok ? 'is-ok' : 'is-bad'}` }, h('p', {}, s.text),
      h('footer', {}, tag(s.ok ? '✓ tasdiqlandi' : `✗ ${s.why}`, s.ok ? 'emerald' : 'amber'), (s.chunk_ids || []).map((id) => link(candidateLabel(state)(id), () => ctx.showSource(id)))))))
      : unavailable('Gaplar roʻyxati qaytarilmadi.'),
    h('button', { type: 'button', class: 'btn btn--gold', onclick: () => ctx.openScales() }, 'Adolat tarozisida koʻrish'),
  ];
}

const RENDER = { analyze, embed, vector, bm25, fuse, read, generate, verify };

export function openStage(id, ctx) {
  const s = STAGE[id];
  const state = ctx.state();
  const st = state.stages[id].status;
  const tools = [tag(WORD[st], TONE[st]), stageMeta(state, id) && st !== 'running' ? tag(stageMeta(state, id)) : null];
  const body = h('div', {});
  const panel = openPanel({ eyebrow: `${s.no} · bosqich`, title: s.name, icon: s.icon, tools, body, label: `${s.name} — inspektor` });
  const draw = (stt) => { panel.live = null; body.replaceChildren(h('p', { class: 'note' }, s.what), ...[].concat(RENDER[id](stt, ctx, panel) || []).filter(Boolean)); };
  draw(state);
  // stages that are still in progress refresh when their data arrives; the LLM text streams in place
  let lastKey = JSON.stringify(state.stages[id]);
  const off = ctx.subscribe((stt) => {
    const key = JSON.stringify(stt.stages[id]);
    if (key !== lastKey) { lastKey = key; draw(stt); return; }
    panel.live?.(stt);
  });
  panel.onCleanup(off);
  return panel;
}

export { ICONS };
