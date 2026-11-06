// Lady Justice's scales: the answer's score against the Lex.uz text it cites (scoring.completed).
import { ICONS } from '../config.js';
import { openPanel } from './overlay.js';
import { h, card, tag, unavailable } from './dom.js';
import { scalesSVG } from '../viz/scalesviz.js';

export function openScales(ctx) {
  const state = ctx.state();
  const sc = state.score;
  const body = h('div', {});
  openPanel({ eyebrow: 'Adolat tarozisi', title: 'Javob va Lex.uz: moslik bahosi', icon: ICONS.scales, body, label: 'Adolat tarozisi' });
  if (!sc || sc.score == null) {
    body.append(h('div', { class: 'scales' }, scalesSVG({ score: null }),
      h('div', {}, unavailable(state.phase === 'idle' ? 'Hali javob yoʻq. Savol yuboring — javobning har bir gapi Lex.uz matni bilan solishtiriladi.'
        : state.phase === 'unknown' && !sc ? 'Javob yozilmadi (mos manba topilmadi) — baholanadigan gap yoʻq.' : 'Baho hali hisoblanmadi.'))));
    return;
  }
  body.append(
    h('div', { class: 'scales' }, scalesSVG(sc),
      h('div', {},
        h('div', { class: 'score' }, h('b', {}, String(sc.score)), h('span', {}, '/ 100 — manbaga moslik')),
        h('div', { class: 'chiprow', style: { margin: '10px 0' } }, tag(`${sc.supported} / ${sc.total} gap tasdiqlandi`, sc.supported === sc.total ? 'emerald' : 'amber'), tag(`soʻz mosligi ${sc.mean_overlap}%`), tag(sc.method)),
        h('p', { class: 'note' }, 'Qanday hisoblanadi: LLM yozgan har bir gap uchun — manbaga havola bormi, undagi raqamlar manbada bormi va gapning mazmunli soʻzlaridan qanchasi keltirilgan Lex.uz matnida uchraydi. Baho = tasdiqlangan gaplar soʻz mosligining oʻrtachasi (rad etilgan gap 0). Bu — matn mosligi oʻlchovi, yuridik xulosa emas.'))),
    card(['Gaplar', `${sc.total} ta`], h('div', {}, sc.sentences.map((s) => h('section', { class: `sentence ${s.supported ? 'is-ok' : 'is-bad'}` },
      h('p', {}, s.text),
      h('footer', {}, tag(s.supported ? '✓ tasdiqlandi' : `✗ ${s.why || 'tasdiqlanmadi'}`, s.supported ? 'emerald' : 'amber'), tag(`moslik ${Math.round(s.overlap * 100)}%`),
        s.numbers_ok === false ? tag('raqam mos emas', 'amber') : null,
        (s.chunk_ids || []).map((id) => h('button', { type: 'button', class: 'link', onclick: () => ctx.showSource(id) }, `manba: ${id}`))),
      s.matched_words?.length ? h('p', { class: 'note' }, `Manbada topilgan soʻzlar: ${s.matched_words.join(', ')}`) : null)))),
  );
}
