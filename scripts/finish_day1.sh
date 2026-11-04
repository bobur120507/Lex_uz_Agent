#!/usr/bin/env bash
# 1-kunning qolgan qadamlari bitta buyruqda. Natija ekranga va data/reports/day1-*.log ga yoziladi.
#   bash scripts/finish_day1.sh          # oʻlchov, MVP indeks, savollar, baholash, modellar solishtiruvi
#   bash scripts/finish_day1.sh --full   # oxirida butun korpusni tungi indekslashni ham boshlaydi
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && source .venv/bin/activate
mkdir -p data/reports
LOG="data/reports/day1-$(date +%Y%m%d-%H%M).log"
exec > >(tee -a "$LOG") 2>&1

OLLAMA_URL=$(grep -E '^OLLAMA_URL=' .env 2>/dev/null | cut -d= -f2-); OLLAMA_URL=${OLLAMA_URL:-http://localhost:11434}
MODELS="qwen3:8b,gemma4:e4b,hf.co/QuantFactory/Llama-3.1-8B-Instuct-Uz-GGUF:Q4_K_M"
step() { echo; echo "==================== $* ($(date +%H:%M:%S))"; }

step "0. Ollama tekshiruvi"
curl -s -m 10 "$OLLAMA_URL/api/version"; echo
OUT=$(curl -s -m 120 "$OLLAMA_URL/api/embed" -d '{"model":"bge-m3","input":"salom"}' | head -c 200)
echo "$OUT"
if [[ "$OUT" != *'"embeddings"'* ]]; then
  echo "✗ Ollama embedding qaytarmadi. KUN-1.md, 1-boʻlim: Ollama’ni qayta oʻrnating, keyin shu skriptni qayta ishga tushiring."
  exit 1
fi
echo "✓ embedding ishlayapti"

step "1. Embedding tezligi"
python -m modda bench-embed || exit 1

step "2. MVP indeks (Konstitutsiya + kodekslar; toʻxtatsangiz, qayta ishga tushirganda davom etadi)"
python -m modda index --mvp || exit 1

step "3. Birinchi savollar"
python -m modda ask "17 yoshli xodimni tungi smenaga yoki xizmat safariga yuborish mumkinmi?" --show-context
python -m modda ask "Шахс суднинг қарорисиз қанча муддат ушлаб турилиши мумкин?" --mode hybrid
python -m modda ask "Marsda yer uchastkasi olish tartibi qanday?"

step "4. Qidiruv sifati (oltin toʻplam, faqat indekslangan moddalar)"
python -m modda eval

step "5. Modellar solishtiruvi (20 savol, bir xil kontekst)"
python -m modda bakeoff --models "$MODELS" --n 20

if [[ "${1:-}" == "--full" ]]; then
  step "6. Butun korpus — fonda (tunga)"
  nohup python -m modda index > data/index-full.log 2>&1 &
  echo "Boshlandi, PID $!. Kuzatish: tail -f data/index-full.log"
fi

step "Tayyor. Toʻliq jurnal: $LOG"
