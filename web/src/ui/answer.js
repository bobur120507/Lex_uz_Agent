// HTML answer panel: sentences with source numbers, source cards, "I don't know" and error views.

const MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr'];
export function uzDate(iso) {
  const [y, m, d] = (iso || '').split('-').map(Number);
  return y ? `${y}-yil ${d}-${MONTHS[m - 1]}` : '';
}

const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

function docLine(s) {
  const date = s.adoption_date ? s.adoption_date.split('-').reverse().join('.') : '';
  const type = s.title && s.doc_type && s.title.includes(s.doc_type) ? '' : s.doc_type;
  return [type, s.doc_number, date].filter(Boolean).join(', ');
}

const STALE = 'Bu hujjatga yaqinda oʻzgartirish kiritilgan boʻlishi mumkin — Lex.uz’da tekshiring.';

export function renderAnswer(panel, question, data, { onSource } = {}) {
  panel.replaceChildren();
  panel.append(el('p', 'panel-kicker', 'Savol'), el('h2', 'panel-q', question));

  const order = [];
  for (const s of data.answer) for (const id of s.chunk_ids) if (data.sources[id] && !order.includes(id)) order.push(id);
  const num = (id) => order.indexOf(id) + 1;

  const body = el('div', 'answer');
  data.answer.forEach((s, i) => {
    const p = el('p', 'sent');
    p.style.setProperty('--i', i);
    p.append(document.createTextNode(s.text + ' '));
    for (const id of s.chunk_ids) {
      if (!data.sources[id]) continue;
      const src = data.sources[id];
      const b = el('button', 'cite', String(num(id)));
      b.type = 'button';
      b.setAttribute('aria-label', `Manba ${num(id)}: ${src.article_no}-modda, ${src.article_title}`);
      b.addEventListener('click', () => focusSource(panel, id, onSource));
      p.append(b);
    }
    body.append(p);
  });
  panel.append(body);

  const verified = el('p', 'verified', `${data.answer.length} ta gapning har biri manba matni bilan solishtirildi`);
  panel.append(verified);
  if (order.some((id) => data.sources[id].stale)) panel.append(el('p', 'warn', STALE));

  panel.append(el('h3', 'panel-h', 'Manbalar'));
  const list = el('ol', 'sources');
  for (const id of order) {
    const s = data.sources[id];
    const quote = data.answer.find((a) => a.chunk_ids.includes(id))?.quote;
    const li = el('li', 'source');
    li.dataset.id = id;
    li.tabIndex = -1;
    const head = el('div', 'source-head');
    head.append(el('span', 'source-n', String(num(id))), el('span', 'source-title', `${s.article_no}-modda. ${s.article_title || ''}`));
    li.append(head, el('p', 'source-doc', `${s.title}${docLine(s) ? ', ' + docLine(s) : ''}`));
    if (quote) li.append(el('blockquote', 'source-quote', `«${quote}»`));
    if (s.amendment_note) li.append(el('p', 'source-doc', s.amendment_note));
    if (s.stale) li.append(el('p', 'warn', STALE));
    const a = el('a', 'source-link', 'Lex.uz’da ochish');
    a.href = s.url; a.target = '_blank'; a.rel = 'noopener';
    li.append(a);
    li.addEventListener('click', (e) => { if (e.target.tagName !== 'A') focusSource(panel, id, onSource); });
    list.append(li);
  }
  panel.append(list);
  if (data.checked_at) panel.append(el('p', 'fine', `Lex.uz bilan ${uzDate(data.checked_at)}da solishtirilgan. Rasmiy yuridik maslahat emas.`));
  panel.scrollTop = 0;
}

function focusSource(panel, id, onSource) {
  panel.querySelectorAll('.source').forEach((s) => s.classList.toggle('active', s.dataset.id === id));
  const card = panel.querySelector(`.source[data-id="${CSS.escape(id)}"]`);
  card?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  card?.focus({ preventScroll: true });
  onSource?.(id);
}

export function renderUnknown(panel, question) {
  panel.replaceChildren(
    el('p', 'panel-kicker', 'Savol'), el('h2', 'panel-q', question),
    el('p', 'unknown-title', 'Bu savolga Lex.uz maʼlumotlari asosida ishonchli javob topilmadi.'),
    el('p', 'muted', 'Taxminiy javob bermaslik uchun tizim toʻxtadi. Savolni aniqroq yozib koʻring: hujjat turini, sohani yoki kimga tegishli ekanini qoʻshing.'),
  );
  const a = el('a', 'source-link', 'Lex.uz’da qidirish');
  a.href = `https://lex.uz/search/all?query=${encodeURIComponent(question)}`;
  a.target = '_blank'; a.rel = 'noopener';
  panel.append(a);
}

export function renderError(panel, onRetry) {
  panel.replaceChildren(
    el('p', 'unknown-title', 'Javob olishning imkoni boʻlmadi'),
    el('p', 'muted', 'Server javob bermadi yoki aloqa uzildi. Savolingiz saqlangan — qayta urinib koʻring.'),
  );
  const b = el('button', 'btn', 'Qayta urinish');
  b.type = 'button';
  b.addEventListener('click', onRetry);
  panel.append(b);
  b.focus({ preventScroll: true });
}
