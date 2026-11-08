# Lex.uz maʼlumotlari: tozami, tuzilganmi? (8-noyabr)

**Qisqa javob:** ha, **tuzilgan** (har bir modda — alohida yozuv, 25 maydon) va **asosan toza** (HTML qoldigʻi, boʻsh matn, aralash yozuv yoʻq). Lekin 5 ta maʼlum kamchilik bor — hammasi kodda hisobga olingan (pastda).

Manba: Hugging Face’dagi Lex.uz nusxasi (qatʼiy versiya) — **24 267 hujjat, 54 173 modda → 183 170 boʻlak**. Tekshiruv: sinov bazasi (shu nusxadagi 10 kodeks, 4 028 modda) + jonli lex.uz bilan 20 ta tasodifiy modda solishtirildi.

## Bitta yozuv — misol (Mehnat kodeksi, 217-modda)

```json
{
  "id": "6257288:217",
  "doc_id": "6257288",
  "doc_title": "Oʻzbekiston Respublikasining Mehnat kodeksi",
  "doc_type": "code",
  "status": "in-force",
  "version_date": "15.10.2026",
  "part": "4-§. Har yilgi mehnat taʼtili",
  "article_number": "217",
  "article_label": "217",
  "article_title": "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi",
  "article_text": "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi yigirma bir kalendar kunni tashkil etadi.",
  "language": "uz",
  "script": "latin",
  "source_url": "https://lex.uz/docs/6257288",
  "seq": 2823
}
```

Qolgan maydonlar: `act_group_id`, `doc_number`, `doc_date`, `chapter`, `amendment_note` (tahrir izohi, moddalarning ≈ 51 % ida), `cross_references`, `okoz_codes`, `tsz_codes`, `n_tokens`, `quality_flag`.

## Nima toza (sinov bazasi, 4 028 modda)

| Tekshiruv | Natija |
|---|---|
| Boʻsh matn | 0 |
| HTML qoldigʻi (`<p>`, `&nbsp;`) | 0 |
| «LexUZ sharhi» kabi muharrir izohlari matnda | 0 (parser olib tashlagan) |
| Yozuv / til | 100 % lotin, `uz` |
| Nostandart apostrof (‘ ’ `) | 0 — hammasi `ʻ` / `ʼ` |
| Sarlavhasiz modda | 155 — **hammasi Konstitutsiya** (unda moddalar sarlavhasiz — toʻgʻri) |
| Juda qisqa (< 40 belgi) | 5 — haqiqiy qisqa moddalar («Kalendar yil soliq davridir.») |
| Matn uzunligi | 22 … 51 612 belgi, oʻrtacha 1 151 → boʻlaklarga boʻlinadi |

## Jonli lex.uz bilan solishtirish (20 ta tasodifiy modda, 10 kodeks)

| Natija | Soni | Misollar |
|---|---|---|
| Raqam va sarlavha **mos** | 17 | Mehnat 1, 2, 217 · Oila 22, 175 · Uy-joy 23, 41 · Yer 10, 58 · Bojxona 30, 136 · Soliq 50, 289³ · Jinoyat 229², 276⁷ · Fuqarolik 876, 968 · Konstitutsiya 28 |
| Tekshirib boʻlmadi | 3 | MJtK 293, 324¹⁸ (sahifa juda uzun — vosita oxirigacha oʻqiy olmadi), Konstitutsiya 45 (matn koʻrinmadi) |
| Mos emas | **0** | |

`version_date` — lex.uz sahifasidagi tahrirlar roʻyxatidagi sana bilan mos (Mehnat 15.10.2026, Soliq 12.12.2026, Konstitutsiya 25.07.2026…). Jinoyat kodeksida lex.uz’da undan **keyingi** tahrir ham bor (05.02.2027 — kelajakda kuchga kiradigan) → bunday oʻzgarishlarni RSS belgilaydi.

*Eslatma:* birinchi urinishda 2 ta «mos emas» chiqqan edi — lex.uz mundarijasi tekis matn boʻlgani uchun vosita raqamni qoʻshni sarlavha bilan juftlagan. Soʻzma-soʻz qayta oʻqilganda (955–968, 276–276⁹) ikkalasi ham mos chiqdi.

## Maʼlum kamchiliklar va nima qilingan

| # | Kamchilik | Taʼsiri | Yechim |
|---|---|---|---|
| 1 | Ustki raqamlar yoʻqolgan: 195¹ → «1951» | «MJtK 195¹-modda» topilmasdi; 16¹ va 161 bir xil raqam | `fix-numbers`: hujjat tartibidan **1 540** ta tiklandi (`article_label` = «195-1») |
| 2 | Hamma hujjat `status = in-force` | Eskirgan aktlar ham «amalda» | Nomi bir xil kodeks/qonunlarning **eski avlodlari** (1995 Mehnat, 1997/2007 Soliq kodekslari) qidiruvdan chiqariladi (`versions.py`); zid raqamlarda yuqori akt qoladi |
| 3 | `doc_date` boʻsh | Qabul sanasini koʻrsatib boʻlmaydi | `version_date` ishlatiladi; kelajakdagi sanalar (kuchga kirish sanasi) «tekshirilgan sana»ga olinmaydi |
| 4 | ≈ 1 300 takror id | Bir modda ikki marta | Ikkalasi saqlanadi (`id~1`), qidiruvda boʻlak id’si boʻyicha farqlanadi |
| 5 | Snapshot’dan keyingi tahrirlar | Matn biroz eski boʻlishi mumkin | Lex.uz RSS → «oʻzgargan boʻlishi mumkin» sariq lentasi; matn oʻzgartirilmaydi |

**Xulosa:** RAG uchun yetarli darajada toza va tuzilgan; asosiy xavf — bir aktning eski avlodlari va eskirgan qaror/yoʻriqnomalar (masalan eski kodeksdan iqtibos keltirgan 2018 yilgi yoʻriqnoma) — birinchisi kodda hal qilindi, ikkinchisi «Cheklovlar»da yozilgan.
