// Settings and the eight processing stages (frontend_idea.md §0.3). Stage ids are used everywhere.
const env = (typeof import.meta !== 'undefined' && import.meta.env) || {};
const win = typeof window !== 'undefined' ? window : {};

export const API = String(env.VITE_MODDA_API || win.MODDA_API || '').replace(/\/$/, '');
export const DEMO = typeof location !== 'undefined' && new URLSearchParams(location.search).has('demo');
export const REDUCED = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
export const BASE = env.BASE_URL || '/';

const I = {
  analyze: '<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5.5 5.5"/></svg>',
  embed: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="2.6"/><path d="M5 6v6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V6M5 12v6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6v-6"/></svg>',
  vector: '<svg viewBox="0 0 24 24"><circle cx="6" cy="17" r="1.6"/><circle cx="17" cy="6" r="1.6"/><circle cx="12" cy="12" r="2.2"/><circle cx="18" cy="16" r="1.3"/><circle cx="7" cy="7" r="1.3"/><path d="M12 12 6 17M12 12l5-6M12 12l6 4"/></svg>',
  bm25: '<svg viewBox="0 0 24 24"><path d="M4 5h16M4 10h10M4 15h13M4 20h7"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>',
  fuse: '<svg viewBox="0 0 24 24"><path d="M4 6h5l6 12h5M4 18h5l6-12h5"/></svg>',
  read: '<svg viewBox="0 0 24 24"><path d="M3 5.5C5.5 4 9 4 12 6c3-2 6.5-2 9-.5V19c-2.5-1.5-6-1.5-9 .5-3-2-6.5-2-9-.5z"/><path d="M12 6v13.5"/></svg>',
  generate: '<svg viewBox="0 0 24 24"><path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/></svg>',
  verify: '<svg viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 4.4-3 7.7-7 9-4-1.3-7-4.6-7-9V6z"/><path d="m9 12 2 2 4-4"/></svg>',
  mind: '<svg viewBox="0 0 24 24"><path d="M9 4.5a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 4.5 3 3 0 0 0 3 2.5c1.2 0 2-.6 3-1.5V5.6C11.3 4.9 10.3 4.5 9 4.5z"/><path d="M15 4.5a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 4.5 3 3 0 0 1-3 2.5c-1.2 0-2-.6-3-1.5"/><path d="M8 9.5h2M14 9.5h2M8 14h2.5M13.5 14H16"/></svg>',
  scales: '<svg viewBox="0 0 24 24"><path d="M12 3v18M7 21h10M4 7h16M6.5 7 3.5 14a3 3 0 0 0 6 0zM17.5 7l-3 7a3 3 0 0 0 6 0z"/></svg>',
  doc: '<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></svg>',
};
export const ICONS = I;

/** kind: colour family (gold = legal/search activity, cyan = neural/vector, blue = retrieval) — §2.2 */
export const STAGES = [
  { id: 'analyze', no: '01', name: 'Savol tahlili', kind: 'gold', icon: I.analyze, what: 'Normallashtirish, kirill → lotin, aniq havola, qidiruv soʻzlari' },
  { id: 'embed', no: '02', name: 'Embedding', kind: 'cyan', icon: I.embed, what: 'bge-m3: savol → 1024 oʻlchamli vektor' },
  { id: 'vector', no: '03', name: 'Vektor qidiruv', kind: 'cyan', icon: I.vector, what: 'Qdrant: kosinus oʻxshashlik boʻyicha yaqin boʻlaklar' },
  { id: 'bm25', no: '04', name: 'Lex.uz indeksi', kind: 'blue', icon: I.bm25, what: 'BM25: Lex.uz’dan yigʻilgan indeksda kalit soʻzlar' },
  { id: 'fuse', no: '05', name: 'Saralash', kind: 'gold', icon: I.fuse, what: 'RRF: ikki roʻyxatni birlashtirish, tanlash' },
  { id: 'read', no: '06', name: 'Oʻqish', kind: 'gold', icon: I.read, what: 'Tanlangan moddalar LLM’ga beriladi' },
  { id: 'generate', no: '07', name: 'LLM javob', kind: 'cyan', icon: I.generate, what: 'Model manbalar asosida javob yozadi' },
  { id: 'verify', no: '08', name: 'Tekshiruv', kind: 'gold', icon: I.verify, what: 'Iqtibos va raqamlar manba bilan solishtiriladi' },
];
export const STAGE = Object.fromEntries(STAGES.map((s) => [s.id, s]));

export const DISCLAIMER = 'Modda rasmiy yuridik maslahat oʻrnini bosmaydi.';
export const UNKNOWN_TEXT = 'Lex.uz maʼlumotlari asosida ishonchli javob topilmadi.';
