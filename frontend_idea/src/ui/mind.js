// The Mind window: the 3-D stack of the model's real layers is the main element; around it only one line of
// facts (from Ollama's model card) and the request's counters. Activations are not available and not drawn.
import { ICONS } from '../config.js';
import { openPanel } from './overlay.js';
import { h, unavailable, fmtMs, fmtNum, fmtBig } from './dom.js';
import { layerStack } from '../viz/layers.js';
import { modelInfo } from './inspectors.js';

export function openMind(ctx, which = 'llm') {
  const body = h('div', { class: 'mind-view' }, h('p', { class: 'note', role: 'status' }, 'Model kartasi yuklanmoqda…'));
  const seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Model' });
  const panel = openPanel({ eyebrow: 'Mind', title: 'Neyron tarmogʻi', icon: ICONS.mind, tools: [seg], body, label: 'Model inspektori', wide: true });
  let view = null;
  panel.onCleanup(() => view?.view.dispose());

  const show = async (kind) => {
    for (const b of seg.children) b.setAttribute('aria-pressed', String(b.dataset.kind === kind));
    view?.view.dispose(); view = null;
    let info;
    try { info = await modelInfo(ctx.backend); } catch (err) { body.replaceChildren(unavailable(`Model maʼlumoti olinmadi: ${err.message}`)); return; }
    const c = info[kind === 'llm' ? 'llm' : 'embedding'];
    if (!c || c.error || !c.layers) { body.replaceChildren(unavailable(`Bu model uchun qatlamlar soni mavjud emas${c?.error ? ` (${c.error})` : ''}.`)); return; }
    const st = ctx.state();
    const stats = kind === 'llm' ? st.generation?.stats : null;
    const tokens = kind === 'llm' ? stats?.prompt_tokens : st.embedding?.tokens;

    const facts = [c.name, `${c.layers} qatlam`, `${fmtNum(c.hidden_size)} neyron`, c.attention_heads ? `${c.attention_heads} attention bosh` : null,
      c.parameter_size ?? (c.parameter_count ? fmtBig(c.parameter_count) : null), c.quantization].filter(Boolean);
    const run = kind === 'llm'
      ? (stats ? [`${stats.prompt_tokens ?? '—'} → ${stats.output_tokens ?? '—'} token`, stats.tokens_per_s ? `${stats.tokens_per_s} tok/s` : null, stats.gen_ms ? fmtMs(stats.gen_ms) : null] : [])
      : (st.embedding ? [`${st.embedding.tokens ?? '—'} token`, `${st.embedding.dim} oʻlcham`, fmtMs(st.embedding.ms)] : []);

    const where = h('span', { class: 'mind-view__layer', 'aria-live': 'polite' });
    const viz = h('div', { class: 'viz mind-view__viz' },
      h('div', { class: 'viz__hud' }, facts.map((f, i) => h('span', { class: `tag${i === 0 ? ' tag--gold' : ''}` }, f))),
      h('div', { class: 'mind-view__nav' },
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Oldingi qatlam', onclick: () => view.select(view.selected - 1) }, '‹'),
        where,
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Keyingi qatlam', onclick: () => view.select(view.selected + 1) }, '›'),
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: () => view.view.reset() }, 'Butun model')));
    body.replaceChildren(viz,
      h('p', { class: 'note mind-view__foot' },
        run.filter(Boolean).length ? `Shu soʻrov: ${run.filter(Boolean).join(' · ')}. ` : '',
        `Har qatlamda ${fmtNum(c.hidden_size)} neyrondan 48 tasi namuna sifatida chizilgan. Faollashuvlar chizilmaydi — Ollama ularni bermaydi.`));
    const height = Math.max(360, Math.min(window.innerHeight - 250, 720));
    view = layerStack(viz, c, { tokens, height, onLayer: (i) => { where.textContent = `${i + 1} / ${c.layers}-qatlam`; } });
    view.select(0, false);
  };
  for (const [kind, label] of [['llm', 'LLM'], ['embedding', 'Embedding']]) {
    seg.append(h('button', { type: 'button', 'data-kind': kind, 'aria-pressed': 'false', onclick: () => show(kind) }, label));
  }
  show(which);
  return panel;
}
