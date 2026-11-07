// The sentence-by-sentence detail behind the statue's scales (opened from the scales caption, «Gaplar»).
// The scales themselves are the 3-D statue; there is no 2-D scale drawing any more.
import { ICONS } from '../config.js';
import { openPanel } from './overlay.js';
import { h, tag, unavailable } from './dom.js';

export function scoreSummary(state) {
  const sc = state.score;
  if (!sc || sc.score == null) {
    return { score: null, line: state.phase === 'idle' ? 'Hali javob yoʻq — savol bering.' : state.phase === 'running' ? 'Javob tayyorlanmoqda…' : 'Baholanadigan gap yoʻq.' };
  }
  return { score: sc.score, line: `${sc.supported} / ${sc.total} gap Lex.uz matni bilan tasdiqlandi · soʻz mosligi ${sc.mean_overlap}%` };
}

export function openSentences(ctx) {
  const sc = ctx.state().score;
  const body = h('div', {});
  openPanel({ eyebrow: 'Adolat tarozisi', title: 'Gaplar va Lex.uz manbalari', icon: ICONS.scales, body, narrow: true, label: 'Tarozi tafsiloti' });
  if (!sc || !sc.sentences?.length) { body.append(unavailable(scoreSummary(ctx.state()).line)); return; }
  body.append(
    h('p', { class: 'note' }, 'Har bir gap uchun: manbaga havola bormi, undagi raqamlar manbada bormi, gapning mazmunli soʻzlaridan qanchasi keltirilgan Lex.uz matnida uchraydi. Baho = tasdiqlangan gaplar moslik oʻrtachasi (rad etilgan gap 0). Bu — matn mosligi, yuridik xulosa emas.'),
    ...sc.sentences.map((s) => h('section', { class: `sentence ${s.supported ? 'is-ok' : 'is-bad'}` }, h('p', {}, s.text),
      h('footer', {}, tag(s.supported ? '✓ tasdiqlandi' : `✗ ${s.why || 'tasdiqlanmadi'}`, s.supported ? 'emerald' : 'amber'), tag(`moslik ${Math.round(s.overlap * 100)}%`),
        s.numbers_ok === false ? tag('raqam mos emas', 'amber') : null,
        (s.chunk_ids || []).map((id) => h('button', { type: 'button', class: 'link', onclick: () => ctx.showSource(id) }, `manba: ${id}`))),
      s.matched_words?.length ? h('p', { class: 'note' }, `Manbada topilgan soʻzlar: ${s.matched_words.join(', ')}`) : null)));
}
