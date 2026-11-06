// «Hujjatlar»: search the documents in the index and read their articles (GET /documents, /documents/{id}).
import { ICONS } from '../config.js';
import { openPanel } from './overlay.js';
import { h, unavailable, tag } from './dom.js';
import { articleBlock } from './reader.js';

export function openDocuments(ctx) {
  const input = h('input', { type: 'search', placeholder: 'Hujjat nomi: masalan, «Mehnat kodeksi»', 'aria-label': 'Hujjat qidirish', style: { flex: '1' } });
  const list = h('div', {});
  const body = h('div', {}, h('form', { class: 'field', role: 'search', onsubmit: (e) => { e.preventDefault(); search(); } }, input, h('button', { type: 'submit', class: 'btn' }, 'Qidirish')), list);
  openPanel({ eyebrow: 'Hujjatlar', title: 'Indeksdagi hujjatlar', icon: ICONS.doc, body, label: 'Hujjatlar' });
  let ctl = null;
  const search = async () => {
    ctl?.abort(); ctl = new AbortController();
    list.replaceChildren(h('p', { class: 'note', role: 'status' }, 'Qidirilmoqda…'));
    try {
      const r = await ctx.backend.api.documents(input.value.trim(), { signal: ctl.signal });
      if (!r.documents.length) { list.replaceChildren(unavailable('Hech narsa topilmadi.')); return; }
      list.replaceChildren(h('ul', { class: 'doclist' }, r.documents.map((d) => h('li', {}, h('button', { type: 'button', onclick: () => openDoc(d) },
        h('span', {}, d.title), h('small', {}, `${d.articles} ta modda`), h('small', {}, [d.doc_type, d.doc_number, d.doc_date].filter(Boolean).join(' · ')))))));
    } catch (err) { if (err.name !== 'AbortError') list.replaceChildren(unavailable(`Roʻyxat olinmadi: ${err.message}`)); }
  };
  const openDoc = async (d, offset = 0) => {
    list.replaceChildren(h('p', { class: 'note', role: 'status' }, 'Yuklanmoqda…'));
    try {
      const r = await ctx.backend.api.document(d.doc_id, offset);
      const pages = Math.ceil(r.total / 20), page = Math.floor(offset / 20) + 1;
      list.replaceChildren(
        h('div', { class: 'field', style: { justifyContent: 'space-between', flexWrap: 'wrap' } },
          h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: search }, '← Roʻyxatga'),
          h('div', { class: 'pager' },
            h('button', { type: 'button', class: 'btn btn--sm btn--ghost', disabled: offset <= 0, onclick: () => openDoc(d, offset - 20) }, '‹'), `${page} / ${pages}`,
            h('button', { type: 'button', class: 'btn btn--sm btn--ghost', disabled: offset + 20 >= r.total, onclick: () => openDoc(d, offset + 20) }, '›')),
          r.document.url ? h('a', { href: r.document.url, target: '_blank', rel: 'noopener' }, 'Lex.uz ↗') : null),
        h('h3', { style: { font: '500 20px/1.3 var(--font-serif)' } }, r.document.title),
        h('div', { class: 'reader', style: { gridTemplateColumns: '1fr' } }, h('section', { class: 'reader__page' },
          r.articles.map((a) => h('div', {}, articleBlock({ ...a, is_target: true }),
            h('button', { type: 'button', class: 'btn btn--sm btn--ghost', style: { margin: '0 0 12px' }, onclick: () => ctx.openArticleInBook(a.article_id) }, 'Kitobda ochish'))))));
    } catch (err) { list.replaceChildren(unavailable(`Hujjat olinmadi: ${err.message}`)); }
  };
  search();
  requestAnimationFrame(() => input.focus());
}
