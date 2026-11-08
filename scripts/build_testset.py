"""Builds data/testset/test100.csv — the 100-question test set of «RAG API — test spetsifikatsiyasi (lex.uz)» §6.

Columns are the spec's (id,batch,category,question,expected_answer,expected_doc_id,expected_article,answerable)
plus three tester-side helpers: language (sent as items[].language), key_facts (facts the answer must contain:
«;» between facts, «|» between accepted spellings — used for the 0/1/2 correctness score next to the LLM judge)
and source (gold set id, or «new»). Several expected documents/articles: «;» in the same order.

Composition (spec §6): faktik 35 · raqam 15 · kop_modda 15 · ozgargan 10 · til 10 (5 ru + 5 uz-Cyrl) ·
javobsiz 10 · noaniq 5. Every batch b01…b10 gets a mix of categories.

Answers come from the article texts of the current Lex.uz corpus (the 45 answerable gold questions were checked
in KUN-3/4; the new ones against the article texts in the index, 8-noyabr). Document ids are Lex.uz ids
(https://lex.uz/docs/<id>). Run:  python scripts/build_testset.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "golden" / "golden.jsonl"
OUT = ROOT / "data" / "testset" / "test100.csv"

KON, MEH, FUQ, MAM, SOL = "-6445145", "-6257288", "-180552", "-97664", "-4674902"
BOJ, JIN, OIL, UY, YER = "-2876354", "-111453", "-104720", "-106136", "-152653"
ISTE, SHAXS, YOL, TAL = "-4704", "-4396419", "-2153411", "-5013007"

# gold id → (category, key_facts, language)
FROM_GOLD = {
    # faktik — bitta modda (34 from the gold set)
    "g001": ("faktik", "qirq sakkiz|48", "uz-Latn"), "g002": ("faktik", "oʻzbek;tarjimon", "uz-Latn"),
    "g003": ("faktik", "koʻrib chiq", "uz-Latn"), "g004": ("faktik", "sud", "uz-Latn"),
    "g005": ("faktik", "qirq sakkiz|48", "uz-Latn"), "g007": ("faktik", "toʻliq", "uz-Latn"),
    "g008": ("faktik", "taqiqlan", "uz-Latn"), "g009": ("faktik", "ish beruvchi", "uz-Latn"),
    "g010": ("faktik", "dam olish vaqti", "uz-Latn"), "g012": ("faktik", "tekshir|koʻzdan kechir", "uz-Latn"),
    "g013": ("faktik", "yozma", "uz-Latn"), "g014": ("faktik", "qaytar", "uz-Latn"),
    "g015": ("faktik", "xarajat", "uz-Latn"), "g016": ("faktik", "vasiylik", "uz-Latn"),
    "g017": ("faktik", "shart|majbur", "uz-Latn"), "g018": ("faktik", "ikkinchi", "uz-Latn"),
    "g019": ("faktik", "vasiylik", "uz-Latn"), "g020": ("faktik", "sud", "uz-Latn"),
    "g021": ("faktik", "tayyorgarlik;suiqasd", "uz-Latn"), "g023": ("faktik", "soliq toʻlovchi", "uz-Latn"),
    "g024": ("faktik", "shaxsiy", "uz-Latn"), "g027": ("faktik", "bekor qilish uchun asos boʻlmaydi|asos boʻlmaydi", "uz-Latn"),
    "g028": ("faktik", "kelishuv", "uz-Latn"), "g029": ("faktik", "yer uchastkasi", "uz-Latn"),
    "g030": ("faktik", "berilmagan|toifalariga kiritilmagan", "uz-Latn"), "g031": ("faktik", "yer soligʻi", "uz-Latn"),
    "g035": ("faktik", "xalqaro|yakka tartibda", "uz-Latn"), "g036": ("faktik", "vakolatli", "uz-Latn"),
    "g038": ("faktik", "taqiqlan", "uz-Latn"), "g039": ("faktik", "davlat boj", "uz-Latn"),
    "g040": ("faktik", "rozilik", "uz-Latn"), "g041": ("faktik", "rozilig", "uz-Latn"),
    "g043": ("faktik", "tibbiy|mahrum", "uz-Latn"), "g045": ("faktik", "yoʻl harakati xavfsizligi|vakolatli", "uz-Latn"),
    # raqam — 5 from the gold set
    "g022": ("raqam", "yuz|100;ikki yuz|200", "uz-Latn"), "g025": ("raqam", "besh|5", "uz-Latn"),
    "g026": ("raqam", "oʻn besh|15", "uz-Latn"), "g032": ("raqam", "toʻqson|90", "uz-Latn"),
    "g033": ("raqam", "olti|6", "uz-Latn"),
    # til — uzbek Cyrillic (5)
    "g006": ("til", "қирқ саккиз|qirq sakkiz|48", "uz-Cyrl"), "g011": ("til", "тақиқлан|taqiqlan", "uz-Cyrl"),
    "g034": ("til", "адвалор|advalor;аралаш|aralash", "uz-Cyrl"), "g037": ("til", "етти|yetti|7", "uz-Cyrl"),
    "g044": ("til", "ўнг|oʻng", "uz-Cyrl"),
    # javobsiz (10)
    "g046": ("javobsiz", "", "uz-Latn"), "g047": ("javobsiz", "", "uz-Latn"), "g048": ("javobsiz", "", "uz-Latn"),
    "g049": ("javobsiz", "", "uz-Latn"), "g050": ("javobsiz", "", "uz-Latn"), "g051": ("javobsiz", "", "uz-Latn"),
    "g053": ("javobsiz", "", "uz-Latn"), "g054": ("javobsiz", "", "uz-Latn"), "g056": ("javobsiz", "", "uz-Latn"),
    "g058": ("javobsiz", "", "uz-Cyrl"),
}

# new questions: (category, question, expected_answer, [(doc, article)], key_facts, language)
NEW = [
    # faktik (1)
    ("faktik", "Konstitutsiyaga koʻra qanday fuqarolar saylovda ishtirok eta olmaydi?",
     "sud tomonidan muomalaga layoqatsiz deb topilgan fuqarolar va sud hukmi bilan ozodlikdan mahrum qilish joylarida saqlanayotgan shaxslar",
     [(KON, "128")], "muomalaga layoqatsiz", "uz-Latn"),
    # raqam (10)
    ("raqam", "Dastlabki sinov muddati eng koʻpi bilan qancha boʻlishi mumkin?",
     "uch oydan, rahbarlar, ularning oʻrinbosarlari va bosh buxgalterlar uchun olti oydan oshmasligi kerak",
     [(MEH, "130")], "uch oy|3 oy", "uz-Latn"),
    ("raqam", "Haftalik normal ish vaqti necha soatdan oshmasligi kerak?",
     "besh yoki olti kunlik ish haftasida haftasiga qirq soatdan ortiq boʻlishi mumkin emas",
     [(MEH, "182")], "qirq|40", "uz-Latn"),
    ("raqam", "16 yoshdan 18 yoshgacha boʻlgan xodimlarning haftalik ish vaqti qancha?",
     "haftasiga oʻttiz olti soatdan oshmaydi (15–16 yoshlilar uchun yigirma toʻrt soat)",
     [(MEH, "415")], "oʻttiz olti|36", "uz-Latn"),
    ("raqam", "Bir ish yili uchun jamlangan mehnat taʼtillari eng koʻpi bilan necha kun boʻlishi mumkin?",
     "qonunchilik bilan belgilangan taʼtillar jamlanganda ellik olti kalendar kundan oshmaydi",
     [(MEH, "222")], "ellik olti|56", "uz-Latn"),
    ("raqam", "Aliment qarzi boʻyicha xodimning ish haqidan necha foizgacha ushlab qolish mumkin?",
     "jazo va aliment qarzi boʻyicha ushlab qolish hisoblangan ish haqining yetmish foizidan oshmaydi (umumiy holda — ellik foiz)",
     [(MEH, "270")], "yetmish|70", "uz-Latn"),
    ("raqam", "Noqulay mehnat sharoitida ishlovchi xodimni yiliga necha soatgacha ish vaqtidan tashqari ishga jalb qilish mumkin?",
     "kuniga ikki soatdan va yiliga bir yuz yigirma soatdan ortiq emas",
     [(MEH, "479")], "bir yuz yigirma|120", "uz-Latn"),
    ("raqam", "Oʻzbekistonda nikoh yoshi necha yosh?",
     "erkaklar va ayollar uchun oʻn sakkiz yosh; uzrli sabablar bilan hokim koʻpi bilan bir yilga kamaytirishi mumkin",
     [(OIL, "15")], "oʻn sakkiz|18", "uz-Latn"),
    ("raqam", "Bir bola uchun aliment ota-ona daromadining qancha qismi miqdorida undiriladi?",
     "har oydagi ish haqi va boshqa daromadning toʻrtdan bir qismi (ikki bola — uchdan bir, uch va undan ortiq — yarmi)",
     [(OIL, "99")], "toʻrtdan bir|1/4", "uz-Latn"),
    ("raqam", "Maʼmuriy jarima qaror topshirilgan kundan boshlab necha kun ichida toʻlanishi kerak?",
     "oʻttiz kundan kechiktirmay (yoʻl harakati qoidalarini buzganlik uchun — oltmish kun)",
     [(MAM, "332")], "oʻttiz|30", "uz-Latn"),
    ("raqam", "Jinoiy javobgarlik necha yoshdan boshlanadi?",
     "jinoyat sodir etgunga qadar oʻn olti yoshga toʻlgan aqli raso shaxslar; ayrim jinoyatlar uchun oʻn toʻrt yoshdan",
     [(JIN, "17")], "oʻn olti|16", "uz-Latn"),
    # kop_modda (15)
    ("kop_modda", "Xodim oʻz xohishi bilan ishdan ketmoqchi boʻlsa necha kun oldin ogohlantiradi, ish beruvchi esa qanday asoslar bilan shartnomani bekor qila oladi?",
     "xodim oʻn toʻrt kalendar kun oldin yozma ogohlantiradi; ish beruvchi faqat asoslangan sabab bilan (tashkilot tugatilishi, shtat qisqarishi, malaka yetarli emasligi, majburiyatlarni muntazam yoki qoʻpol buzish va h.k.)",
     [(MEH, "160"), (MEH, "161")], "oʻn toʻrt|14;tugatil|qisqar|malaka", "uz-Latn"),
    ("kop_modda", "Dastlabki sinov muddati qancha va sinov davrida shartnomani bekor qilish uchun necha kun oldin ogohlantirish kerak?",
     "sinov uch oydan (rahbarlar uchun olti oydan) oshmaydi; taraflar kamida uch kun oldin yozma ogohlantiradi",
     [(MEH, "130"), (MEH, "132")], "uch oy|3 oy;uch kun|3 kun", "uz-Latn"),
    ("kop_modda", "Voyaga yetmagan xodimning ish vaqti qancha va uni tungi ishga yoki xizmat safariga yuborish mumkinmi?",
     "16–18 yoshlilar uchun haftasiga 36 soat, 15–16 yoshlilar uchun 24 soat; tungi ish, ish vaqtidan tashqari ish va xizmat safari taqiqlanadi",
     [(MEH, "415"), (MEH, "417")], "oʻttiz olti|36;taqiqlan", "uz-Latn"),
    ("kop_modda", "Har yilgi asosiy mehnat taʼtili necha kun va qoʻshimcha taʼtillar bilan birga eng koʻpi necha kun boʻladi?",
     "asosiy eng kam taʼtil yigirma bir kalendar kun; jamlanganda ellik olti kalendar kundan oshmaydi",
     [(MEH, "217"), (MEH, "222")], "yigirma bir|21;ellik olti|56", "uz-Latn"),
    ("kop_modda", "Nikoh yoshi necha yosh va nikoh yoshiga yetmagan shaxs bilan tuzilgan nikoh haqiqiy emas deb topilishi mumkinmi?",
     "nikoh yoshi oʻn sakkiz; bunday nikoh voyaga yetmagan shaxsning manfaatlari talab qilsa haqiqiy emas deb topilishi mumkin",
     [(OIL, "15"), (OIL, "51")], "oʻn sakkiz|18;haqiqiy emas", "uz-Latn"),
    ("kop_modda", "Ota-ona voyaga yetgan mehnatga layoqatsiz bolasiga taʼminot berishi shartmi va bunday aliment miqdorini kim belgilaydi?",
     "shart; kelishuv boʻlmasa sud ota-onaning oilaviy va moddiy ahvolini hisobga olib har oyda qatʼiy summada belgilaydi",
     [(OIL, "100"), (OIL, "101")], "shart;qatʼiy summa|sud", "uz-Latn"),
    ("kop_modda", "Prezidentlikka nomzod qanday talablarga javob berishi kerak va Prezident necha yilga saylanadi, saylov qachon oʻtkaziladi?",
     "kamida 35 yosh, davlat tilini yaxshi bilishi, saylovgacha kamida 10 yil Oʻzbekistonda yashashi; yetti yil muddatga; vakolat tugaydigan yilning oktabr oyi uchinchi oʻn kunligining birinchi yakshanbasida",
     [(KON, "106"), (KON, "128")], "oʻttiz besh|35;yetti yil|7 yil", "uz-Latn"),
    ("kop_modda", "Qoʻshilgan qiymat soligʻi stavkasi va rezident jismoniy shaxslar daromad soligʻi stavkasi qancha?",
     "QQS — 12 foiz (36-bobdagi hollarda 0 foiz); jismoniy shaxslar daromadi — 12 foiz, dividend va foizlar — 5 foiz",
     [(SOL, "258"), (SOL, "381")], "12 foiz|oʻn ikki foiz;5 foiz|besh foiz", "uz-Latn"),
    ("kop_modda", "Chet elda roʻyxatdan oʻtgan avtomobilni vaqtincha olib kirsa qancha turishi mumkin, reeksport rejimidagi tovarni-chi?",
     "transport vositasi kalendar yil mobaynida jami toʻqson kundan oshmasligi kerak; reeksport tovari deklaratsiya qabul qilingan kundan olti oydan kechiktirmay olib chiqilishi kerak",
     [(BOJ, "159"), (BOJ, "32")], "toʻqson|90;olti oy|6 oy", "uz-Latn"),
    ("kop_modda", "Guruh boʻlib xavfli harakatlangan haydovchilarga qancha jarima solinadi va jarimani necha kun ichida toʻlash kerak?",
     "BHMning besh baravari miqdorida jarima; yoʻl harakati qoidalarini buzganlik uchun jarima oltmish kundan kechiktirmay toʻlanadi",
     [(MAM, "129"), (MAM, "332")], "besh|5;oltmish|60", "uz-Latn"),
    ("kop_modda", "Homilador ayolni tungi ishga jalb qilish mumkinmi va u toʻliqsiz ish vaqti soʻrasa ish beruvchi rozi boʻlishi shartmi?",
     "faqat yozma roziligi va xavf yoʻqligini tasdiqlovchi tibbiy xulosa bilan; ish beruvchi iltimosga koʻra toʻliqsiz ish vaqti belgilashi shart",
     [(MEH, "396"), (MEH, "398")], "rozilig;shart", "uz-Latn"),
    ("kop_modda", "Konstitutsiyaga koʻra shaxsni sud qarorisiz qancha ushlab turish mumkin va telefon soʻzlashuvlari siri qachon cheklanadi?",
     "qirq sakkiz soatdan ortiq emas; yozishma va telefon soʻzlashuvlari siri faqat qonunga muvofiq va sud qarori bilan cheklanadi",
     [(KON, "27"), (KON, "31")], "qirq sakkiz|48;sud", "uz-Latn"),
    ("kop_modda", "Ota-ona bola ismi boʻyicha kelisha olmasa nizoni kim hal qiladi va ota-ona qaramogʻisiz qolgan bolalar huquqini kim himoya qiladi?",
     "ikkala holda ham vasiylik va homiylik organi",
     [(OIL, "69"), (OIL, "148")], "vasiylik", "uz-Latn"),
    ("kop_modda", "Ish beruvchi shtat qisqarishi sababli ishdan boʻshatsa necha oy oldin ogohlantiradi va ish beruvchi qaysi asoslar bilan shartnomani bekor qila oladi?",
     "tugatish yoki shtat qisqarishida kamida ikki oy oldin (malaka yetarli boʻlmasa — ikki hafta, aybli harakatlarda — uch kun) yozma ogohlantiradi; asoslar 161-moddada",
     [(MEH, "165"), (MEH, "161")], "ikki oy|2 oy", "uz-Latn"),
    ("kop_modda", "Necha yoshdan ishga qabul qilish mumkin va 15 yoshli oʻquvchi bilan mehnat shartnomasi qanday tuziladi?",
     "oʻn olti yoshdan; oʻn besh yoshdan ota-onadan birining yozma roziligi bilan, oʻqishdan boʻsh vaqtda yengil mehnat uchun",
     [(MEH, "118"), (MEH, "31")], "oʻn olti|16;rozilig", "uz-Latn"),
    # ozgargan — amaldagi tahrir (10): codes that have older generations in the corpus (versions.py)
    ("ozgargan", "Yillik asosiy mehnat taʼtilining eng kam muddati qancha?",
     "yigirma bir kalendar kun (amaldagi Mehnat kodeksi; eski kodeksdagi «15 ish kuni» emas)",
     [(MEH, "217")], "yigirma bir|21", "uz-Latn"),
    ("ozgargan", "Soliq kodeksiga koʻra qoʻshilgan qiymat soligʻi stavkasi necha foiz?",
     "12 foiz (36-bobda nazarda tutilgan hollarda 0 foiz)", [(SOL, "258")], "12 foiz|oʻn ikki foiz", "uz-Latn"),
    ("ozgargan", "Rezident jismoniy shaxsning daromadiga qanday stavkada soliq solinadi?",
     "12 foiz; dividend va foizlar tarzidagi daromadlarga 5 foiz", [(SOL, "381")], "12|oʻn ikki", "uz-Latn"),
    ("ozgargan", "Oʻzbekiston Prezidenti necha yil muddatga saylanadi?",
     "yetti yil muddatga (amaldagi Konstitutsiya)", [(KON, "106")], "yetti|7", "uz-Latn"),
    ("ozgargan", "Konstitutsiyaviy sud sudyalari qancha muddatga saylanadi?",
     "qayta saylanish huquqisiz oʻn yillik muddatga", [(KON, "132")], "oʻn yil|10 yil", "uz-Latn"),
    ("ozgargan", "Xodim mehnat shartnomasini oʻz tashabbusi bilan bekor qilsa ish beruvchini necha kun oldin ogohlantirishi kerak?",
     "oʻn toʻrt kalendar kun oldin yozma shaklda", [(MEH, "160")], "oʻn toʻrt|14", "uz-Latn"),
    ("ozgargan", "Mehnat kodeksiga koʻra ishga qabul qilish necha yoshdan mumkin?",
     "oʻn olti yoshdan; oʻquvchilar yengil ish uchun oʻn besh yoshdan ota-onaning yozma roziligi bilan",
     [(MEH, "118")], "oʻn olti|16", "uz-Latn"),
    ("ozgargan", "Ish beruvchi mehnat shartlarini oʻzgartirishi haqida xodimni qancha oldin ogohlantirishi shart?",
     "kamida ikki oy oldin yozma shaklda, imzo qoʻydirib", [(MEH, "137")], "ikki oy|2 oy", "uz-Latn"),
    ("ozgargan", "Oʻzbekiston Respublikasi Oliy sudining raisi qancha muddatga saylanadi?",
     "Prezident taqdimiga binoan Senat tomonidan besh yillik muddatga; surunkasiga ikki muddatdan ortiq emas",
     [(KON, "134")], "besh yil|5 yil", "uz-Latn"),
    ("ozgargan", "Ish vaqtining normal davomiyligi haftasiga necha soat?",
     "qirq soatdan ortiq boʻlishi mumkin emas", [(MEH, "182")], "qirq|40", "uz-Latn"),
    # til — Russian (5)
    ("til", "Какова минимальная продолжительность ежегодного основного трудового отпуска?",
     "двадцать один календарный день (yigirma bir kalendar kun)", [(MEH, "217")], "21|двадцать один|yigirma bir", "ru"),
    ("til", "С какого возраста допускается приём на работу по Трудовому кодексу?",
     "с шестнадцати лет (oʻn olti yoshdan); учащиеся — с пятнадцати лет с письменного согласия родителя",
     [(MEH, "118")], "16|шестнадцат|oʻn olti", "ru"),
    ("til", "Какая ставка налога на добавленную стоимость установлена Налоговым кодексом?",
     "12 процентов (12 foiz)", [(SOL, "258")], "12", "ru"),
    ("til", "Каков брачный возраст в Узбекистане?",
     "восемнадцать лет для мужчин и женщин (oʻn sakkiz yosh)", [(OIL, "15")], "18|восемнадцат|oʻn sakkiz", "ru"),
    ("til", "На какой срок избирается Президент Республики Узбекистан?",
     "на семь лет (yetti yil)", [(KON, "106")], "7|сем|yetti", "ru"),
    # noaniq — ogʻzaki (5)
    ("noaniq", "Otpuskaga necha kun berishadi oʻzi?",
     "har yilgi asosiy eng kam mehnat taʼtili yigirma bir kalendar kun", [(MEH, "217")], "yigirma bir|21", "uz-Latn"),
    ("noaniq", "Bolam 15 da, yozda ishlasa boʻladimi?",
     "oʻn besh yoshdan ota-onaning yozma roziligi bilan, sogʻligʻiga zarar yetkazmaydigan yengil ishga, oʻqishdan boʻsh vaqtda mumkin; ish vaqti haftasiga 24 soatdan oshmaydi",
     [(MEH, "118"), (MEH, "415")], "rozilig", "uz-Latn"),
    ("noaniq", "Ajrashsam bitta bolaga qancha aliment toʻlanadi?",
     "kelishuv boʻlmasa ota-onaning oylik daromadining toʻrtdan bir qismi", [(OIL, "99")], "toʻrtdan bir|1/4", "uz-Latn"),
    ("noaniq", "Ishdan haydashmoqchi, oldindan aytishlari kerakmi?",
     "ha: tugatish yoki shtat qisqarishida kamida ikki oy, malaka yetarli boʻlmasa ikki hafta, aybli harakatlarda uch kun oldin yozma ogohlantiriladi",
     [(MEH, "165")], "ogohlantir", "uz-Latn"),
    ("noaniq", "Chet eldan mashina olib kelsam qancha vaqt haydasam boʻladi?",
     "vaqtincha olib kirilgan transport vositasi kalendar yil mobaynida jami toʻqson kundan oshmasligi kerak",
     [(BOJ, "159")], "toʻqson|90", "uz-Latn"),
]

ORDER = ["faktik", "raqam", "kop_modda", "ozgargan", "til", "javobsiz", "noaniq"]


def main():
    gold = {g["id"]: g for g in map(json.loads, GOLD.read_text(encoding="utf-8").splitlines())}
    rows = []
    for gid, (cat, facts, lang) in FROM_GOLD.items():
        g = gold[gid]
        exp = g.get("expected") or []
        rows.append({"category": cat, "question": g["question"],
                     "expected_answer": g.get("answer_hint", "") if g.get("answerable", True) else "",
                     "expected_doc_id": ";".join(f"lex:{e['doc_id']}" for e in exp),
                     "expected_article": ";".join(f"{e['article_number']}-modda" for e in exp),
                     "answerable": "true" if g.get("answerable", True) and exp else "false",
                     "language": lang, "key_facts": facts, "source": gid})
    for cat, q, ans, exp, facts, lang in NEW:
        rows.append({"category": cat, "question": q, "expected_answer": ans,
                     "expected_doc_id": ";".join(f"lex:{d}" for d, _ in exp),
                     "expected_article": ";".join(f"{a}-modda" for _, a in exp),
                     "answerable": "true", "language": lang, "key_facts": facts, "source": "new"})
    counts = {c: sum(r["category"] == c for r in rows) for c in ORDER}
    want = {"faktik": 35, "raqam": 15, "kop_modda": 15, "ozgargan": 10, "til": 10, "javobsiz": 10, "noaniq": 5}
    assert counts == want, counts
    assert len({r["question"] for r in rows}) == 100, "duplicate question"
    # interleave categories so that every batch is a small sample of the whole set (spec §6)
    # each category is spread evenly over the 100 places: item j of n sits at (j + ½) / n
    pos = []
    for c in ORDER:
        items = [r for r in rows if r["category"] == c]
        pos += [((j + 0.5) / len(items), ORDER.index(c), r) for j, r in enumerate(items)]
    mixed = [r for _, _, r in sorted(pos, key=lambda t: (t[0], t[1]))]
    for i, r in enumerate(mixed):
        r["id"], r["batch"] = f"q{i + 1:03d}", f"b{i // 10 + 1:02d}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "batch", "category", "question", "expected_answer", "expected_doc_id", "expected_article", "answerable",
            "language", "key_facts", "source"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows({k: r[k] for k in cols} for r in mixed)
    per_batch = {}
    for r in mixed:
        per_batch.setdefault(r["batch"], set()).add(r["category"])
    print(f"{OUT.relative_to(ROOT)}: {len(mixed)} savol · {counts} · har batch’da {min(map(len, per_batch.values()))}–"
          f"{max(map(len, per_batch.values()))} kategoriya")


if __name__ == "__main__":
    main()
