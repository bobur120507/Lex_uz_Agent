// The Mind inspector: the real architecture of the LLM (or the embedding model) from Ollama's model card,
// drawn as a 3-D stack of transformer layers; per-request numbers from Ollama's counters.
import { ICONS } from '../config.js';
import { openPanel } from './overlay.js';
import { h, kv, card, tag, unavailable, fmtMs, fmtNum, fmtBig } from './dom.js';
import { layerStack } from '../viz/layers.js';
import { modelInfo } from './inspectors.js';

export function openMind(ctx, which = 'llm') {
  const body = h('div', {}, h('p', { class: 'note', role: 'status' }, 'Model kartasi yuklanmoqda…'));
  const seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Model' });
  const panel = openPanel({ eyebrow: 'Model inspektori', title: 'Mind — neyron tarmogʻi', icon: ICONS.mind, tools: [seg], body, label: 'Model inspektori' });
  let view = null;
  panel.onCleanup(() => view?.view.dispose());

  const show = async (kind) => {
    for (const b of seg.children) b.setAttribute('aria-pressed', String(b.dataset.kind === kind));
    view?.view.dispose(); view = null;
    let info;
    try { info = await modelInfo(ctx.backend); } catch (err) { body.replaceChildren(unavailable(`Model maʼlumoti olinmadi: ${err.message}`)); return; }
    const c = info[kind === 'llm' ? 'llm' : 'embedding'];
    if (!c || c.error || !c.layers) { body.replaceChildren(unavailable(`Bu model uchun qatlamlar soni mavjud emas${c?.error ? ` (${c.error})` : ''}.`)); return; }
    const state = ctx.state();
    const stats = kind === 'llm' ? state.generation?.stats : null;
    const tokens = kind === 'llm' ? stats?.prompt_tokens : state.embedding?.tokens;
    const viz = h('div', { class: 'viz' });
    const layerInfo = h('div', {});
    const select = h('select', { 'aria-label': 'Qatlam' }, Array.from({ length: c.layers }, (_, i) => h('option', { value: i }, `${i + 1}-qatlam`)));
    const onLayer = (i) => {
      select.value = String(i);
      layerInfo.replaceChildren(card([`${i + 1}-qatlam / ${c.layers}`, 'transformer bloki'],
        kv([['Kenglik', fmtNum(c.hidden_size), 'neyron'], ['Attention boshlari', c.attention_heads], c.kv_heads ? ['KV boshlar', c.kv_heads] : null,
          c.head_dim ? ['Bosh oʻlchami', c.head_dim, c.head_dim_derived ? '(hisoblangan)' : ''] : null, ['FFN kengligi', fmtNum(c.ffn_size)]]),
        h('p', { class: 'note' }, `Har bir plastinkada ${fmtNum(c.hidden_size)} ta neyrondan 48 tasi namuna sifatida chizilgan. Hamma qatlamlarning tuzilishi bir xil; ular ketma-ket ishlaydi.`),
        unavailable('Bu soʻrovdagi faollashuvlar (activations) va attention qiymatlari mavjud emas: Ollama ularni bermaydi, shuning uchun ular chizilmaydi.')));
    };
    body.replaceChildren(
      h('div', { class: 'grid2' }, viz, h('div', {},
        card([c.name, c.source], kv([['Arxitektura', c.architecture], ['Qatlamlar', c.layers], ['Parametrlar', c.parameter_size ?? fmtBig(c.parameter_count)],
          ['Kontekst', fmtNum(c.context_length), 'token'], c.quantization ? ['Kvantlash', c.quantization] : null, c.pooling != null ? ['Pooling', c.pooling] : null])),
        h('div', { class: 'field', style: { margin: '12px 0' } },
          h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Oldingi qatlam', onclick: () => view.select(view.selected - 1) }, '‹'),
          select, h('button', { type: 'button', class: 'btn btn--sm btn--ghost', 'aria-label': 'Keyingi qatlam', onclick: () => view.select(view.selected + 1) }, '›'),
          h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: () => view.view.reset() }, 'Kamera')),
        layerInfo)),
      card(['Shu soʻrov', kind === 'llm' ? 'Ollama hisoblagichlari' : 'embedding'], stats || tokens
        ? kv(kind === 'llm'
          ? [['Kirish tokenlari', stats?.prompt_tokens ?? '—'], ['Chiqish tokenlari', stats?.output_tokens ?? '—'], ['Tezlik', stats?.tokens_per_s ? `${stats.tokens_per_s} tok/s` : '—'],
            ['Kontekstni oʻqish', fmtMs(stats?.prompt_ms)], ['Yozish', fmtMs(stats?.gen_ms)]]
          : [['Tokenlar', tokens ?? '—'], ['Vektor', `${state.embedding?.dim ?? '—'}`], ['Vaqt', fmtMs(state.embedding?.ms)]])
        : unavailable(state.phase === 'idle' ? 'Hali savol berilmagan — model tuzilishi koʻrsatilgan, soʻrov raqamlari savoldan keyin chiqadi.' : 'Bu soʻrov uchun hisoblagichlar kelmadi.'),
        h('div', { class: 'legend' }, h('span', {}, h('i', { style: { background: '#d6b66d' } }), `kirish tokenlari${tokens ? ` (${tokens})` : ''}`),
          h('span', {}, h('i', { style: { background: '#65d8ee' } }), 'qatlamlar'), h('span', {}, h('i', { style: { background: '#39d6a0' } }), kind === 'llm' ? 'chiqish' : '1024 oʻlchamli vektor'))));
    view = layerStack(viz, c, { tokens, onLayer });
    select.onchange = () => view.select(Number(select.value));
    view.select(0);
  };
  for (const [kind, label] of [['llm', 'LLM'], ['embedding', 'Embedding']]) {
    seg.append(h('button', { type: 'button', 'data-kind': kind, 'aria-pressed': 'false', onclick: () => show(kind) }, label));
  }
  show(which);
  return panel;
}
