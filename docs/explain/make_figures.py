#!/usr/bin/env python3
"""Draws the pictures for I_EXPLAIN.md (saved next to this file).

Text figures run the REAL prototype functions from prototypes.py on a small
TRAINING SAMPLE law ("O'quv namunasi" - not a real legal act) and render the
output as HTML -> PNG. Charts with "sxema" in the title use illustrative data.

    python docs/explain/make_figures.py     (needs matplotlib + playwright)
"""

import html
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import prototypes as P  # noqa: E402

OUT = Path(__file__).resolve().parent
BLUE, RED, GREEN, ORANGE, PURPLE, GREY = "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#6b7280"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

SAMPLE_TITLE = "«Oʻquv namunasi» toʻgʻrisidagi Qonun"
SAMPLE_LAW = """1-modda. Ushbu Qonunning maqsadi
Ushbu Qonunning maqsadi oʻquv taʼtillarini berish tartibini belgilashdan iborat.

2-modda. Asosiy tushunchalar
Ushbu Qonunda quyidagi asosiy tushunchalar qoʻllaniladi: oʻquv taʼtili — xodimga oʻqish uchun beriladigan taʼtil; ish beruvchi — xodim bilan mehnat shartnomasi tuzgan shaxs.

3-modda. Taʼtil muddati
Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi. (Namuna qonunining 2026-yil 1-martdagi tahririda)
Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin.

4-modda. Taʼtil haqi
Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi."""

CSS = """
body{margin:0;font-family:Inter,system-ui,sans-serif;background:#fff;color:#16181d;font-size:15px}
.wrap{padding:22px;width:1040px} h2{font-size:18px;margin:0 0 6px} .sub{color:#6b7280;font-size:13px;margin:0 0 14px}
h3{font-size:14px;margin:14px 0 8px;color:#374151}.row{display:flex;gap:16px}.col{flex:1}
.card{border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;margin-bottom:9px;line-height:1.5;background:#fafafa}
.lbl{font-size:12px;font-weight:700;color:#6b7280;margin-bottom:4px;display:flex;justify-content:space-between;gap:10px}
.bad{border-color:#fca5a5;background:#fef2f2}.good{border-color:#86efac;background:#f0fdf4}
.blk{display:grid;grid-template-columns:1fr 290px;gap:12px;align-items:center;margin-bottom:7px}
.blk .src{border-radius:8px;padding:8px 10px;font-size:13.5px;border-left:5px solid}
.blk .act{font-size:13px}.arrow{color:#6b7280}
.k-drop{background:#f3f4f6;border-color:#9ca3af;color:#6b7280}.k-meta{background:#eff6ff;border-color:#2563eb}
.k-chunk{background:#f0fdf4;border-color:#16a34a}.k-sep{background:#fff7ed;border-color:#d97706}
.k-hier{background:#f5f3ff;border-color:#7c3aed}
table{border-collapse:collapse;width:100%;font-size:13.5px}td,th{border:1px solid #e5e7eb;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f9fafb}.mono{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
.ok{color:#15803d;font-weight:700}.no{color:#b91c1c;font-weight:700}.hdr{color:#2563eb;font-family:ui-monospace,Menlo,monospace;font-size:12px}
.note{font-size:13px;color:#374151;margin-top:6px}.hl{background:#fde68a;border-radius:3px;padding:0 2px}
"""


def render(body, name):
    from playwright.sync_api import sync_playwright
    doc = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='wrap'>{body}</div></body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1084, "height": 400}, device_scale_factor=2)
        pg.set_content(doc)
        pg.locator(".wrap").screenshot(path=str(OUT / name))
        b.close()
    print("  saved", name)


e = html.escape


# ------------------------------------------------------------------ 1. page anatomy
def fig_page_anatomy():
    rows = [
        ("k-drop", "💬 Hujjatga taklif yuborish · 🔊 Audio · 🔗 Havola", "UI shovqini → <b>olib tashlanadi</b>"),
        ("k-meta", "Qonun · Oʻzbekiston Respublikasi Oliy Majlisi · 2026-01-15 · № OʻRQ-000", "Rekvizitlar → <b>metadata</b>: turi, organ, sana, raqam"),
        ("k-hier", "BIRINCHI BOʻLIM. UMUMIY QOIDALAR  ›  I bob. Taʼtil berish tartibi", "Tuzilma → <b>hierarchy_path</b>"),
        ("k-meta", "[OKOZ: &lt;tasnif kodi&gt;]", "Tasnif → <b>okoz_codes</b> (mavzu filtri)"),
        ("k-chunk", "<b>3-modda. Taʼtil muddati</b><br>Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.", "Modda matni → <b>chunk</b> (qidiriladi)"),
        ("k-sep", "(Namuna qonunining 2026-yil 1-martdagi tahririda)", "Tahrir izohi → <b>amendment_note</b><br>(embedding’ga kirmaydi, ko‘rsatiladi)"),
        ("k-sep", "LexUZ sharhi: bu masala boshqa qonunda ham tartibga solingan…", "Sharh → <b>chunk_type = commentary</b><br>(rasmiy matn emas, qidiruvdan tashqarida)"),
        ("k-meta", "Oldingi tahrirga ›   ·   Tahrir sanasi: 01.03.2026", "Tahrir sanasi → <b>revision_date</b> (arzon yangilik signali)"),
    ]
    body = ("<h2>Lex.uz hujjat sahifasining anatomiyasi va parser nima qiladi</h2>"
            "<p class='sub'>Tuzilma lex.uz/docs/6445145 (Konstitutsiya) sahifasi asosida; matn — oʻquv namunasi, haqiqiy hujjat emas.</p>"
            + "".join(f"<div class='blk'><div class='src {k}'>{t}</div><div class='act'><span class='arrow'>→</span> {a}</div></div>"
                      for k, t, a in rows))
    render(body, "fig_page_anatomy.png")


# ------------------------------------------------------------------ 2. normalization
def fig_normalize():
    apos = ["o'zbek", "o‘zbek", "o’zbek", "o`zbek", "oʻzbek", "ma'lumot", "ma’lumot"]
    rows1 = "".join(f"<tr><td class='mono'>{e(a)}</td><td class='mono'>{' '.join(f'U+{ord(c):04X}' for c in a if not (c.isascii() and c.isalpha()))}</td>"
                    f"<td class='mono'>{e(P.normalize_uz(a))}</td></tr>" for a in apos)
    qs = ["Меҳнат кодекси 131-модда нима дейди?", "ер ва мулк солиғи", "MK 131-modda", "Ishdan boʻshatish tartibi qanday?"]
    rows2 = ""
    for q in qs:
        r = P.route(q)
        dest = (f"<span class='ok'>aniq havola</span> → {e(r['document'])}, {r['article_no']}-modda"
                if r["route"] == "exact" else "<span style='color:#2563eb;font-weight:700'>gibrid qidiruv</span>")
        rows2 += f"<tr><td class='mono'>{e(q)}</td><td class='mono'>{e(r['normalized'])}</td><td>{dest}</td></tr>"
    body = ("<h2>Normalizatsiya va savol marshrutizatori (prototypes.py chiqishi)</h2>"
            "<p class='sub'>Bir xil koʻrinadigan soʻzlar kompyuter uchun har xil — ularni bitta shaklga keltiramiz.</p>"
            "<div class='row'><div class='col'><h3>1. Apostroflar → bitta shakl</h3><table><tr><th>Kirish</th><th>Belgi kodi</th><th>Natija</th></tr>"
            f"{rows1}</table></div><div class='col'><h3>2. Savol: kirill → lotin → marshrut</h3>"
            f"<table><tr><th>Savol</th><th>Normallashgan</th><th>Yoʻnalish</th></tr>{rows2}</table></div></div>")
    render(body, "fig_normalize.png")


# ------------------------------------------------------------------ 3. chunking
def fig_chunking():
    fixed = P.fixed_size_chunks(SAMPLE_LAW.replace("\n", " "), 170)[:4]
    arts = P.split_articles(SAMPLE_LAW, SAMPLE_TITLE, "I bob")
    left = "".join(f"<div class='card bad'><div class='lbl'><span>Boʻlak {i}</span><span>{len(c)} belgi</span></div>{e(c)}</div>"
                   for i, c in enumerate(fixed, 1))
    right = ""
    for c in arts:
        note = (f"<div class='note'>📝 amendment_note: <i>{e(c['amendment_note'])}</i></div>" if c["amendment_note"] else "")
        right += (f"<div class='card good'><div class='lbl'><span>{e(c['chunk_id'])}</span><span>{len(c['text'])} belgi</span></div>"
                  f"<div class='hdr'>{e(c['header'])}</div>{e(c['text']).replace(chr(10), '<br>')}{note}</div>")
    body = ("<h2>Huquqiy matnni boʻlaklash: «har 170 belgida kesish» va «modda = boʻlak»</h2>"
            "<p class='sub'>Bir xil oʻquv namunasi matni. Chapda — oddiy usul, oʻngda — prototypes.split_articles() chiqishi.</p>"
            f"<div class='row'><div class='col'><h3>❌ Belgilar soni boʻyicha</h3>{left}"
            "<div class='note'>Soʻz va modda oʻrtasidan kesiladi: «3-modda. Taʼtil mudda» | «ti Xodimga…», «…qismlarga» | «boʻlinishi mumkin». "
            "Qaysi moddaligi ham, qaysi qonunligi ham bilinmaydi.</div></div>"
            f"<div class='col'><h3>✅ Modda boʻyicha + kontekst sarlavhasi</h3>{right}"
            "<div class='note'>Har boʻlak — bitta toʻliq modda. Sarlavha qonun va modda raqamini beradi. "
            "Tahrir izohi matndan ajratilib, metadata’ga oʻtdi.</div></div></div>")
    render(body, "fig_chunking.png")


# ------------------------------------------------------------------ 4. RRF
def fig_rrf():
    dense = ["13-modda", "131-modda", "113-modda", "31-modda"]
    bm25 = ["131-modda", "31-modda", "13-modda", "1310-son qaror"]
    fused = P.rrf({"dense": dense, "bm25": bm25})
    def col(lst):
        return "".join(f"<tr><td>{i}</td><td>{'<b>' if d == '131-modda' else ''}{e(d)}</td></tr>" for i, d in enumerate(lst, 1))
    rows = ""
    for d, sc in fused:
        parts = [f"1/(60+{lst.index(d) + 1})" for lst in (dense, bm25) if d in lst]
        rows += (f"<tr><td>{'<b>' if d == '131-modda' else ''}{e(d)}</td><td class='mono'>{' + '.join(parts)}</td>"
                 f"<td class='mono'>{sc:.5f}</td></tr>")
    body = ("<h2>Gibrid qidiruv: dense va BM25 natijalarini RRF bilan birlashtirish</h2>"
            "<p class='sub'>Savol: «Mehnat kodeksining 131-moddasi». Roʻyxatlar — tushuntirish uchun namuna; RRF hisobi — prototypes.rrf() chiqishi.</p>"
            "<div class='row'>"
            f"<div class='col'><h3>Dense (maʼno boʻyicha)</h3><table><tr><th>#</th><th>Natija</th></tr>{col(dense)}</table>"
            "<div class='note'>Maʼnoni yaxshi ushlaydi, lekin 13, 131, 113 raqamlarini “oʻxshash” deb biladi.</div></div>"
            f"<div class='col'><h3>BM25 (soʻz/raqam boʻyicha)</h3><table><tr><th>#</th><th>Natija</th></tr>{col(bm25)}</table>"
            "<div class='note'>«131» tokenini aniq topadi, lekin sinonimlarni bilmaydi.</div></div>"
            f"<div class='col'><h3>RRF: score = Σ 1/(60 + oʻrin)</h3><table><tr><th>Natija</th><th>Hisob</th><th>Ball</th></tr>{rows}</table>"
            "<div class='note'>Ikkala roʻyxatda ham yuqori turgan <b>131-modda</b> birinchi chiqdi.</div></div></div>")
    render(body, "fig_rrf.png")


# ------------------------------------------------------------------ 5. verifier
def fig_verifier():
    arts = {c["chunk_id"]: c["text"] for c in P.split_articles(SAMPLE_LAW, SAMPLE_TITLE, "I bob")}
    answer = [
        {"text": "Xodimga har yili kamida 21 kalendar kunlik haq toʻlanadigan taʼtil beriladi.", "chunk_ids": ["doc#m3"],
         "quote": "kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi"},
        {"text": "Taʼtil haqi taʼtildan kamida 3 kun oldin toʻlanadi.", "chunk_ids": ["doc#m4"],
         "quote": "taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi"},
        {"text": "Taʼtil 30 kundan oshmasligi kerak.", "chunk_ids": ["doc#m3"], "quote": "Taʼtil 30 kundan oshmasligi kerak"},
        {"text": "Ish beruvchi taʼtilni rad eta olmaydi.", "chunk_ids": ["doc#m9"], "quote": "rad eta olmaydi"},
    ]
    rows = ""
    for s in answer:
        ok, why = P.verify_sentence(s, arts)
        rows += (f"<tr><td>{e(s['text'])}</td><td class='mono'>{e(', '.join(s['chunk_ids']))}</td><td class='mono'>«{e(s['quote'])}»</td>"
                 f"<td class='{'ok' if ok else 'no'}'>{'✓' if ok else '✗'} {e(why)}</td></tr>")
    body = ("<h2>Iqtibos tekshiruvchi: LLM javobining har bir gapi manba bilan solishtiriladi</h2>"
            "<p class='sub'>LLM JSON qaytaradi: gap + chunk_ids + soʻzma-soʻz iqtibos. Natija ustuni — prototypes.verify_sentence() chiqishi.</p>"
            f"<table><tr><th>LLM gapi</th><th>chunk_ids</th><th>Iqtibos</th><th>Tekshiruv</th></tr>{rows}</table>"
            "<div class='note'>✗ belgili gaplar javobdan <b>olib tashlanadi</b>. Birorta ham gap qolmasa — «Bilmayman». "
            "Manba bloki esa faqat ✓ gaplarning chunk_ids lari boʻyicha metadata’dan yasaladi.</div>")
    render(body, "fig_verifier.png")


# ------------------------------------------------------------------ 6. parent-child
def fig_parent_child():
    body = ("<h2>Ota-bola (parent-child) qidiruv</h2>"
            "<p class='sub'>Qidiruv kichik, aniq boʻlak bilan; LLM ga esa toʻliq modda beriladi.</p>"
            "<div class='row'><div class='col'><h3>1. Qidiruv topgan “bola” boʻlak</h3>"
            "<div class='card'><div class='lbl'><span>doc#m3#p2</span><span>band</span></div>"
            "<span class='hl'>Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin.</span></div></div>"
            "<div class='col' style='flex:0 0 40px;display:flex;align-items:center;justify-content:center;font-size:28px'>→</div>"
            "<div class='col'><h3>2. LLM ga boriladigan “ota” — butun modda</h3>"
            "<div class='card good'><div class='lbl'><span>doc#m3</span><span>modda</span></div>"
            "<div class='hdr'>[«Oʻquv namunasi» toʻgʻrisidagi Qonun | I bob › 3-modda]</div>"
            "<b>3-modda. Taʼtil muddati</b><br>Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.<br>"
            "<span class='hl'>Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin.</span></div></div></div>"
            "<div class='note'>Nega? Kichik boʻlak qidiruvda aniqroq topiladi, lekin javob uchun moddaning qolgan qismi "
            "(masalan, «kamida 21 kun» sharti) ham kerak.</div>")
    render(body, "fig_parent_child.png")


# ------------------------------------------------------------------ 7. crawl budget (real arithmetic)
def fig_crawl_budget():
    tasks = [("Kunlik yangiliklar\n(RSS, ~5 hujjat)", 5), ("MVP namunasi\n(500 hujjat)", 500),
             ("Barcha lotin\n(24 267)", 24267), ("Barcha kirill\n(~54 000)", 54000)]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = np.arange(len(tasks))
    for off, (delay, color, label) in zip((-0.2, 0.2), ((20, GREEN, "Crawl-delay 20 s (odobli)"),
                                                         (1, RED, "1 soʻrov/s (v1 rejasi — robots.txt dan 20× tez)"))):
        hours = [n * delay / 3600 for _, n in tasks]
        bars = ax.bar(x + off, hours, 0.38, color=color, label=label)
        for b, h in zip(bars, hours):
            txt = f"{h * 3600:.0f} s" if h < 1 / 60 else f"{h * 60:.0f} daq" if h < 1 else (f"{h:.1f} soat" if h < 48 else f"{h / 24:.1f} kun")
            ax.text(b.get_x() + b.get_width() / 2, h * 1.15, txt, ha="center", fontsize=8.5)
    ax.set_yscale("log")
    ax.set_xticks(x, [t for t, _ in tasks])
    ax.set_ylabel("Vaqt, soat (log shkala)")
    ax.set_title("Lex.uz dan yuklash vaqti: 20 s kechikish bilan 4 320 hujjat/kun", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_ylim(0.001, 2000)
    fig.tight_layout()
    fig.savefig(OUT / "fig_crawl_budget.png", dpi=150)
    print("  saved fig_crawl_budget.png")


# ------------------------------------------------------------------ 8. threshold (illustrative)
def fig_threshold():
    rng = np.random.default_rng(7)
    ans = np.clip(rng.normal(0.72, 0.12, 400), 0, 1)
    no = np.clip(rng.normal(0.32, 0.12, 400), 0, 1)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    ax = axes[0]
    bins = np.linspace(0, 1, 31)
    ax.hist(ans, bins, color=GREEN, alpha=.6, label="javobi BOR savollar")
    ax.hist(no, bins, color=RED, alpha=.6, label="javobi YOʻQ savollar")
    tau = 0.52
    ax.axvline(tau, color="black", ls="--")
    ax.text(tau + 0.01, ax.get_ylim()[1] * 0.9, f"τ = {tau}", fontsize=10)
    ax.text(0.05, ax.get_ylim()[1] * 0.55, "← «Bilmayman»", color=GREY)
    ax.text(0.78, ax.get_ylim()[1] * 0.55, "LLM →", color=GREY)
    ax.set(title="Eng yaxshi reranker bali taqsimoti (sxema)", xlabel="reranker bali", ylabel="savollar soni")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(0, 1))
    ax = axes[1]
    taus = np.linspace(0, 1, 101)
    false_ans = [(no >= t).mean() for t in taus]
    over_ref = [(ans < t).mean() for t in taus]
    ax.plot(taus, false_ans, color=RED, label="Yolgʻon javob (javobi yoʻqqa javob berdi)")
    ax.plot(taus, over_ref, color=ORANGE, label="Ortiqcha «Bilmayman» (javobi borga rad etdi)")
    ax.axvline(tau, color="black", ls="--")
    ax.axhline(0.02, color=RED, ls=":", lw=1)
    ax.text(0.02, 0.04, "maqsad ≤ 2 %", color=RED, fontsize=8.5)
    ax.set(title="τ ni tanlash: ikki xato oʻrtasidagi muvozanat (sxema)", xlabel="τ", ylabel="ulush")
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
    fig.tight_layout()
    fig.savefig(OUT / "fig_threshold.png", dpi=150)
    print("  saved fig_threshold.png")


# ------------------------------------------------------------------ 9. freshness timeline
def fig_freshness():
    fig, ax = plt.subplots(figsize=(11, 2.9))
    ax.set_xlim(0, 24)
    ax.set_ylim(-0.6, 2.6)
    for h in range(24):
        ax.plot(h + 0.05, 2, marker="v", color=BLUE, ms=7)
    ax.text(-0.2, 2, "A · RSS (har soat, 1 soʻrov)", ha="right", va="center", color=BLUE, fontsize=9)
    ax.add_patch(plt.Rectangle((1, 0.8), 3, 0.4, color=PURPLE, alpha=.35))
    ax.text(-0.2, 1, "B · aylanma tekshiruv (kechasi)", ha="right", va="center", color=PURPLE, fontsize=9)
    ax.text(4.3, 1, "≤ 500 hujjat × 20 s ≈ 2,8 soat (01:00–04:00)", ha="left", va="center", fontsize=8.5)
    qs = [8.3, 9.1, 10.7, 13.2, 14.5, 16.8, 19.4]
    ax.plot(qs, [0] * len(qs), "o", color=GREEN, ms=8)
    ax.text(-0.2, 0, "C · savol vaqtidagi belgi (keshdan, 0 soʻrov)", ha="right", va="center", color=GREEN, fontsize=9)
    ax.set_xticks(range(0, 25, 2), [f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_title("Bir sutka davomida yangilanish kuzatuvi: Lex.uz ga yuk kichik, foydalanuvchi kutmaydi", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig_freshness.png", dpi=150, bbox_inches="tight")
    print("  saved fig_freshness.png")


if __name__ == "__main__":
    fig_crawl_budget()
    fig_threshold()
    fig_freshness()
    fig_page_anatomy()
    fig_normalize()
    fig_chunking()
    fig_rrf()
    fig_verifier()
    fig_parent_child()
