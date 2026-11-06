import { STAGES, ICONS, DISCLAIMER } from '../config.js';
import { openPanel } from './overlay.js';
import { h } from './dom.js';

export function openHelp() {
  openPanel({
    eyebrow: 'Yordam', title: 'Modda qanday ishlaydi?', icon: ICONS.mind, narrow: true, label: 'Yordam',
    body: h('div', {},
      h('p', {}, 'Savolingiz sakkiz bosqichdan oʻtadi. Grafdagi har bir doira — shu bosqichlardan biri: ustiga bossangiz, aynan sizning soʻrovingizda nima boʻlganini koʻrasiz. Markazdagi «Mind» — til modeli (LLM): uni bossangiz, uning haqiqiy qatlamlari koʻrinadi.'),
      h('ol', { class: 'steps' }, STAGES.map((s) => h('li', {}, h('div', {}, h('b', {}, s.name), h('span', {}, s.what))))),
      h('p', {}, 'Javob kitob sahifasida yoziladi: chapda — javob [1], [2] havolalari bilan, oʻngda — topilgan modda va uning atrofidagi ±5 modda. Havolani bossangiz, kitob oʻsha manbaga varaqlanadi.'),
      h('p', {}, 'Chapdagi Adolat haykalini bossangiz, tarozi javob gaplari Lex.uz matniga qanchalik mos kelishini koʻrsatadi.'),
      h('p', { class: 'note' }, 'Sahifadagi barcha raqamlar backend’dan keladi. Backend bermagan maʼlumot «Mavjud emas» deb koʻrsatiladi — oʻylab topilmaydi.'),
      h('p', { class: 'note' }, DISCLAIMER)),
  });
}
