// The HTML layer of the process graph: one button per stage plus the Mind button in the centre.
// Positions follow the 3D anchors every frame; without WebGL they form a ring laid out in CSS/JS.
import { STAGES, ICONS, STAGE } from '../config.js';
import { stageMeta, activeStage } from '../core/research.js';
import { h } from './dom.js';

const STATUS_WORD = { waiting: 'kutilmoqda', running: 'bajarilmoqda', done: 'bajarildi', warning: 'ogohlantirish', failed: 'xato', skipped: 'oʻtkazildi', unobserved: 'kuzatilmadi' };

export class GraphNodes {
  constructor(root, { onOpen }) {
    this.list = root.querySelector('.graph__nodes');
    this.mind = root.querySelector('.mind');
    this.mind.querySelector('.mind__icon').innerHTML = ICONS.mind;
    this.mind.addEventListener('click', () => onOpen('mind'));
    this.items = new Map();
    for (const s of STAGES) {
      const meta = h('span', { class: 'node__meta' });
      const btn = h('button', { type: 'button', class: 'node', 'data-node': s.id, 'data-kind': s.kind, 'data-status': 'waiting',
        'aria-label': `${s.no}. ${s.name}: kutilmoqda. ${s.what}`, onclick: () => onOpen(s.id) },
        h('span', { class: 'node__disc', 'aria-hidden': 'true' }, h('span', { class: 'node__no' }, s.no), h('span', { html: s.icon })),
        h('span', { class: 'node__name' }, s.name), meta);
      this.list.append(h('li', {}, btn));
      this.items.set(s.id, { btn, meta, x: NaN, y: NaN });
    }
    this.mindPos = { x: NaN, y: NaN };
  }

  update(state) {
    for (const s of STAGES) {
      const it = this.items.get(s.id);
      const st = state.stages[s.id].status;
      it.btn.dataset.status = st;
      it.meta.textContent = stageMeta(state, s.id);
      it.btn.setAttribute('aria-label', `${s.no}. ${s.name}: ${STATUS_WORD[st]}${it.meta.textContent ? ` (${it.meta.textContent})` : ''}. ${s.what}. Batafsil koʻrish.`);
    }
    // the centre shows the running stage; otherwise the Mind
    const act = activeStage(state);
    const icon = this.mind.querySelector('.mind__icon'), name = this.mind.querySelector('.mind__name'), sub = this.mind.querySelector('.mind__sub');
    if (act) {
      if (this.mind.dataset.stage !== act) {
        this.mind.dataset.stage = act;
        icon.innerHTML = STAGE[act].icon;
        name.textContent = STAGE[act].name;
        sub.textContent = 'bajarilmoqda…';
      }
    } else {
      if (this.mind.dataset.stage) delete this.mind.dataset.stage;
      icon.innerHTML = ICONS.mind;
      name.textContent = 'Mind';
      sub.textContent = state.phase === 'idle' ? 'LLM — bosing: neyron qatlamlari'
        : state.generation?.model ? `${state.generation.model} — qatlamlarni koʻrish` : 'LLM — qatlamlarni koʻrish';
    }
  }

  place(el, rec, x, y) {
    if (Math.abs(rec.x - x) < 0.4 && Math.abs(rec.y - y) < 0.4) return;
    rec.x = x; rec.y = y;
    el.style.setProperty('--x', `${x.toFixed(1)}px`);
    el.style.setProperty('--y', `${y.toFixed(1)}px`);
  }

  /** positions: {mind: {x, y}, [id]: {x, y}} in CSS pixels; label offset puts names under the discs. */
  position(positions) {
    if (positions.mind) this.place(this.mind, this.mindPos, positions.mind.x, positions.mind.y);
    for (const s of STAGES) {
      const p = positions[s.id];
      if (p) this.place(this.items.get(s.id).btn, this.items.get(s.id), p.x, p.y + 22);
    }
  }

  /** Ring layout without WebGL. */
  ring(rect) {
    const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    const rx = Math.min(rect.width * 0.42, 420), ry = Math.min(rect.height * 0.4, 190);
    const pos = { mind: { x: cx, y: cy } };
    [150, 110, 70, 30, -30, -70, -110, -150].forEach((d, i) => {
      const a = (d * Math.PI) / 180;
      pos[STAGES[i].id] = { x: cx + rx * Math.cos(a), y: cy - ry * Math.sin(a) - 22 };
    });
    this.position(pos);
  }
}
