// Sample event stream in the exact shape of POST /ask/stream (see web/README.md).
// The law below is a TRAINING SAMPLE ("Oʻquv namunasi"), not a real legal act.

const DOC = {
  title: '«Oʻquv namunasi» toʻgʻrisidagi Qonun',
  doc_type: 'Qonun', doc_number: 'OʻRQ-000', adoption_date: '2026-01-15', url: 'https://lex.uz/',
  chapter: '2-bob. Taʼtillar',
};

const SOURCES = {
  'namuna#m3': {
    ...DOC, article_no: '3', article_title: 'Taʼtil muddati',
    text: 'Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.\nTaʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin. Bunda taʼtilning bir qismi 14 kalendar kundan kam boʻlmasligi kerak.\nTaʼtil ish yili davomida istalgan vaqtda, taʼtillar jadvaliga muvofiq beriladi.',
    amendment_note: 'Namuna qonunining 2026-yil 1-martdagi tahririda', stale: false,
  },
  'namuna#m4': {
    ...DOC, article_no: '4', article_title: 'Taʼtil haqi',
    text: 'Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi.\nTaʼtil haqi xodimning oʻrtacha ish haqidan kelib chiqib hisoblanadi.',
    amendment_note: null, stale: false,
  },
};

const CANDIDATES = [
  { chunk_id: 'namuna#m3', title: DOC.title, article_no: '3', article_title: 'Taʼtil muddati', score: 0.86 },
  { chunk_id: 'namuna#m4', title: DOC.title, article_no: '4', article_title: 'Taʼtil haqi', score: 0.71 },
  { chunk_id: 'namuna#m7', title: DOC.title, article_no: '7', article_title: 'Ish vaqti', score: 0.44 },
  { chunk_id: 'namuna#m9', title: DOC.title, article_no: '9', article_title: 'Dam olish kunlari', score: 0.39 },
  { chunk_id: 'namuna#m12', title: DOC.title, article_no: '12', article_title: 'Mehnat shartnomasi', score: 0.31 },
];

const SCENARIOS = {
  leave: {
    order: ['namuna#m3', 'namuna#m4', 'namuna#m7', 'namuna#m9', 'namuna#m12'],
    answer: {
      unknown: false, checked_at: '2026-11-01',
      answer: [
        { text: 'Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.', chunk_ids: ['namuna#m3'],
          quote: 'kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi' },
        { text: 'Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin.', chunk_ids: ['namuna#m3'],
          quote: 'Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin' },
        { text: 'Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi.', chunk_ids: ['namuna#m4'],
          quote: 'taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi' },
      ],
      sources: SOURCES,
    },
  },
  pay: {
    order: ['namuna#m4', 'namuna#m3', 'namuna#m12', 'namuna#m7', 'namuna#m9'],
    answer: {
      unknown: false, checked_at: '2026-11-01',
      answer: [
        { text: 'Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi.', chunk_ids: ['namuna#m4'],
          quote: 'Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi' },
        { text: 'Uning miqdori xodimning oʻrtacha ish haqidan kelib chiqib hisoblanadi.', chunk_ids: ['namuna#m4'],
          quote: 'xodimning oʻrtacha ish haqidan kelib chiqib hisoblanadi' },
      ],
      sources: { 'namuna#m4': { ...SOURCES['namuna#m4'], stale: true } },
    },
  },
  unknown: {
    order: ['namuna#m12', 'namuna#m9'],
    answer: { unknown: true, checked_at: '2026-11-01', answer: [], sources: {} },
  },
};

export const EXAMPLES = [
  { text: 'Oʻquv taʼtili necha kun beriladi?', hint: 'Javob va ikki manba' },
  { text: 'Taʼtil haqi qachon toʻlanadi?', hint: 'Yaqinda oʻzgargan boʻlishi mumkin' },
  { text: 'Kosmik turizm uchun soliq imtiyozi bormi?', hint: 'Bazada javob yoʻq' },
];

function pick(question) {
  const q = question.toLowerCase().replace(/[ʻʼ'’‘`ъ]/g, '');
  const leave = /tatil|таътил|татил|отпуск/.test(q);
  if (leave && /haqi|tolan|ҳақи|тўлан/.test(q)) return SCENARIOS.pay;
  if (leave) return SCENARIOS.leave;
  return SCENARIOS.unknown;
}

const wait = (ms, signal) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms);
  signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('aborted', 'AbortError')); });
});

/** Emits the same events the real server will: stage, candidates, reranked, answer. */
export async function mockStream(question, onEvent, signal) {
  const sc = pick(question);
  onEvent('stage', { name: 'retrieving' });
  await wait(900, signal);
  const cands = sc.order.map((id) => CANDIDATES.find((c) => c.chunk_id === id)).filter(Boolean);
  onEvent('candidates', cands);
  await wait(600, signal);
  onEvent('stage', { name: 'generating' });
  onEvent('reranked', { order: sc.order });
  await wait(900, signal);
  onEvent('stage', { name: 'verifying' });
  await wait(500, signal);
  onEvent('answer', structuredClone(sc.answer));
}
