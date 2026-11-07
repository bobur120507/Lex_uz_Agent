"""Modda — 3-kun, GPU noutbukda: bitta skript, bitta hisobot fayli.

    double-click scripts\\day3.bat        (or: .venv\\Scripts\\python.exe scripts\\day3.py)

  1 gpu      Is the RTX 4060 really doing the work? nvidia-smi, charger, other programs in VRAM, Ollama settings;
             frees the GPU, then measures bge-m3 (chunks/s) and qwen3:8b (tokens/s) and how much of each runs on the GPU
  2 setup    scripts\\setup_server.py — everything the laptop still lacks (finished steps are skipped):
             the index comes from Bobur's snapshot (modda-*.snapshot + .manifest.json.gz in Downloads)
  3 bakeoff  qwen3:8b vs gemma4:e4b vs Llama-3.1-8B-Uz on 20 golden questions → which LLM the demo uses
  4 demo     the six demo questions (exact article, labour topic, Cyrillic, updated document, no answer,
             prompt injection) through the real pipeline, with timings and the answer score
  5 status   final state

Everything printed is also written to data\\reports\\day3-<time>.log — send that one file to Bobur.

  --only gpu,demo   run only these parts           --build-index   no snapshot: build the full index on this GPU
  --n 20            bake-off questions             --models a,b    bake-off models (default: the three)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_windows as base                          # noqa: E402

_unused = base.LOG_PATH                                # setup_windows opened its own log on import: use ours instead
base._log.close()
if _unused.exists() and _unused.stat().st_size == 0:
    _unused.unlink()
base.LOG_PATH = base.REPORTS / f"day3-{datetime.now():%Y%m%d-%H%M%S}.log"   # this run's report (base.log writes here)
base._log = open(base.LOG_PATH, "a", encoding="utf-8")
import setup_server as srv                            # noqa: E402
from setup_windows import C, IS_WIN, OLLAMA, REPORTS, ROOT, VPY, StepFailed, bad, fmt_mb, http_json, ok, run, say, warn  # noqa: E402

PARTS = ["gpu", "setup", "bakeoff", "demo", "status"]
BAKEOFF = ["qwen3:8b", "gemma4:e4b", "hf.co/QuantFactory/Llama-3.1-8B-Instuct-Uz-GGUF:Q4_K_M"]
EMBED_OK, LLM_OK = 25.0, 20.0                          # chunks/s, tokens/s that an RTX 4060 easily beats


# --------------------------------------------------------------------------- 1. GPU

def nvidia_smi(*args: str) -> str:
    exe = shutil.which("nvidia-smi") or (r"C:\Windows\System32\nvidia-smi.exe" if IS_WIN else None)
    if not exe or not Path(exe).exists():
        return ""
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def on_charger() -> bool | None:
    if not IS_WIN:
        return None
    code, out = srv.ps("(Get-CimInstance Win32_Battery | Select-Object -First 1).BatteryStatus")
    v = out.strip().splitlines()[-1].strip() if out.strip() else ""
    return None if not v.isdigit() else int(v) != 1          # 1 = on battery; 2 = on AC; 3+ = charging / full


def gpu_report():
    q = nvidia_smi("--query-gpu=name,driver_version,memory.used,memory.total,pstate,power.draw,power.limit,clocks.sm,clocks.max.sm,temperature.gpu",
                   "--format=csv,noheader")
    if not q:
        warn("nvidia-smi ishlamadi — NVIDIA drayveri oʻrnatilmaganmi?")
    else:
        say(f"GPU: {q}")
    apps = nvidia_smi("--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader")
    say("GPU xotirasidagi dasturlar: " + ("; ".join(l.strip() for l in apps.splitlines()) if apps else "— (nvidia-smi koʻrsatmadi)"))
    ac = on_charger()
    if ac is False:
        warn("Noutbuk BATAREYADA — GPU quvvati cheklanadi. Zaryadlovchini ulang!")
    elif ac:
        ok("Zaryadlovchiga ulangan")
    if IS_WIN:
        plan = run(["powercfg", "/getactivescheme"], check=False, quiet=True)[1].strip()
        say(f"Quvvat rejimi: {plan.splitlines()[-1] if plan else '?'}")
    env = {k: v for k, v in os.environ.items() if k.startswith(("OLLAMA_", "CUDA_"))}
    say(f"Ollama sozlamalari: {env or 'standart'}  |  Ollama {base.ollama_version() or 'ishlamayapti'}")
    before = srv.loaded_models()
    if before:
        say("Ollama xotirasida turgan modellar: " + ", ".join(
            f"{m['name']} ({fmt_mb(m.get('size_vram', 0))} / {fmt_mb(m.get('size', 0))} GPU’da)" for m in before))


def bench_embed() -> float:
    code, out = base.modda("bench-embed", "--n", "192", "--batch", "32", check=False, timeout=3600)
    m = re.search(r'"chunks_per_s":\s*([\d.]+)', out)
    return float(m.group(1)) if m else 0.0


def bench_llm(model: str) -> tuple[float, float | None]:
    r = http_json(f"{OLLAMA}/api/generate", {"model": model, "stream": False, "think": False, "keep_alive": "10m",
                                              "prompt": "Mehnat shartnomasi nima? Oʻzbek tilida 6–8 gap bilan tushuntiring.",
                                              "options": {"num_predict": 200}}, timeout=900)
    tps = r.get("eval_count", 0) / max(1e-9, r.get("eval_duration", 1) / 1e9)
    sh = srv.gpu_share(model)
    return tps, (sh[0] if sh else None)


def part_gpu():
    if not base.ollama_version():
        exe = base.find_ollama()
        if not exe or not base.start_ollama(exe):
            raise StepFailed("Ollama ishga tushmadi")
    gpu_report()
    srv.unload_all()
    say("bge-m3 tezligi oʻlchanmoqda (192 ta haqiqiy boʻlak)…")
    rate = bench_embed()
    sh = srv.gpu_share(base.EMBED_MODEL)
    emb_gpu = sh[0] if sh else None
    (ok if rate >= EMBED_OK else warn)(f"bge-m3: {rate} boʻlak/s, {'?' if emb_gpu is None else f'{emb_gpu * 100:.0f} %'} GPU’da "
                                       f"(kutilgan ≥ {EMBED_OK:.0f} boʻlak/s; avvalgi oʻlchov 2,6 edi)")
    base.STATE["bench"] = {"done": datetime.now().isoformat(timespec="seconds"), "rate": rate}   # the index step uses it
    base.save_state(base.STATE)
    llm = base.LLM_MODEL
    if base.have_model(llm):
        say(f"{llm} tezligi oʻlchanmoqda…")
        try:
            tps, share = bench_llm(llm)
            (ok if tps >= LLM_OK else warn)(f"{llm}: {tps:.1f} token/s, {'?' if share is None else f'{share * 100:.0f} %'} GPU’da "
                                            f"(kutilgan ≥ {LLM_OK:.0f} token/s)")
        except Exception as exc:
            warn(f"{llm} sinovi oʻtmadi: {exc}")
            tps, share = 0.0, None
        http_json(f"{OLLAMA}/api/embed", {"model": base.EMBED_MODEL, "input": ["sinov"], "keep_alive": "10m"}, timeout=300)
        both = {m["name"]: (m.get("size_vram", 0), m.get("size", 0)) for m in srv.loaded_models()}
        say("Ikkalasi birga (sayt ishlaganda shunday): " + ", ".join(f"{k} {v[0] / max(1, v[1]) * 100:.0f} % GPU’da" for k, v in both.items()))
    else:
        tps, share = 0.0, None
    vram = nvidia_smi("--query-gpu=memory.used,memory.total", "--format=csv,noheader")
    say(f"GPU xotirasi hozir: {vram}")
    good = rate >= EMBED_OK and (emb_gpu or 0) > 0.97
    if not good:
        warn("GPU toʻliq ishlamayapti. Tekshiring: 1) zaryadlovchi ulanganmi; 2) yuqoridagi «GPU xotirasidagi dasturlar» "
             "roʻyxatida boshqa dastur (oʻyin, LM Studio, brauzer) bormi — yoping; 3) Ollama’ni qayta ishga tushiring "
             "(soat yonidagi lama belgisi → Quit Ollama, keyin Ollama’ni oching); 4) NVIDIA drayverini yangilang. "
             "Keyin: scripts\\day3.bat --only gpu")
    srv.unload_all(quiet=True)
    base.mark_done("day3_gpu", embed_rate=rate, embed_gpu=emb_gpu, llm_tps=round(tps, 1), llm_gpu=share, good=good)


# --------------------------------------------------------------------------- 2. setup

def part_setup(build_index: bool) -> bool:
    complete = srv.index_complete() if base.qdrant_version() or base.start_qdrant() else False
    snap = srv.find_snapshot(None)
    argv = ["setup_server.py"]
    if not complete and not snap and not build_index:
        bad("Indeks toʻliq emas va Bobur’ning snapshot’i topilmadi (Downloads papkasida modda-*.snapshot va "
            "modda-*.manifest.json.gz boʻlishi kerak). Indeksdan boshqa hamma narsa oʻrnatiladi.")
        say("Fayllarni olgach: scripts\\day3.bat ni qayta ishga tushiring (yoki snapshot’siz: scripts\\day3.bat --build-index).", "y")
        argv += ["--only", "git,python,ollama,models,node,frontend,lan,launchers"]
    elif snap and not complete:
        ok(f"Snapshot topildi: {snap[0]} — indeks undan yuklanadi (≈ 1 daqiqa)")
    old = sys.argv
    sys.argv = argv
    try:
        code = srv.main()
    finally:
        sys.argv = old
    if code:
        warn(f"setup_server {code} kodi bilan tugadi — yuqoridagi xatoni koʻring")
    return srv.index_complete()


# --------------------------------------------------------------------------- 3. bake-off

def part_bakeoff(models: list[str], n: int):
    have = [m for m in models if base.have_model(m)]
    missing = [m for m in models if m not in have]
    if missing:
        warn(f"Yuklanmagan modellar oʻtkazib yuboriladi: {', '.join(missing)}")
    if not have:
        return warn("Bakeoff uchun model yoʻq")
    srv.unload_all(quiet=True)
    say(f"Bakeoff: {', '.join(have)} — {n} ta oltin savol (har model navbat bilan GPU’ga yuklanadi)…")
    code, out = base.modda("bakeoff", "--models", ",".join(have), "--n", str(n), check=False, timeout=4 * 3600)
    if code != 0:
        warn("bakeoff xato bilan tugadi — yuqoridagi xabarni koʻring")
    srv.unload_all(quiet=True)
    base.mark_done("day3_bakeoff", models=have, ok=code == 0)


# --------------------------------------------------------------------------- 4. demo questions

def part_demo():
    srv.ensure_services()
    srv.unload_all(quiet=True)
    out = REPORTS / f"demo-{datetime.now():%Y%m%d-%H%M%S}.json"
    code, _ = run([VPY, ROOT / "scripts" / "demo_questions.py", out], check=False, timeout=3600)
    if code != 0:
        warn("Demo savollar skripti xato bilan tugadi")
    base.mark_done("day3_demo", report=str(out), ok=code == 0)


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Modda — 3-kun: GPU tekshiruvi, indeks, bakeoff, demo savollar")
    ap.add_argument("--only", help="vergul bilan: " + ",".join(PARTS))
    ap.add_argument("--build-index", action="store_true", help="snapshot boʻlmasa ham indeksni shu GPU’da yasash")
    ap.add_argument("--models", default=",".join(BAKEOFF))
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    parts = [p for p in PARTS if not a.only or p in a.only.split(",")]
    if IS_WIN:
        base.keep_awake()
    git = srv.find_git()
    code, head = run([git, "-C", ROOT, "log", "-1", "--format=%h %ad %s", "--date=short"], check=False, quiet=True) if git else (1, "")
    head = head.strip() if code == 0 else "? (git yoʻq)"
    print(f"{C['b']}{C['c']}Modda — 3-kun (GPU noutbuk){C['0']}   {ROOT}")
    say(f"Kod versiyasi: {head.splitlines()[-1] if head else '?'}  |  Python {sys.version.split()[0]}")
    say(f"Hisobot fayli: {base.LOG_PATH}")
    fns = {"gpu": part_gpu, "setup": lambda: part_setup(a.build_index), "bakeoff": lambda: part_bakeoff(a.models.split(","), a.n),
           "demo": part_demo, "status": srv.cmd_status}
    for i, name in enumerate(parts, 1):
        print()
        say(f"══ [{i}/{len(parts)}] {name} ══", "b")
        t0 = time.time()
        try:
            fns[name]()
            ok(f"{name} tugadi ({base.fmt_dur(time.time() - t0)})")
        except KeyboardInterrupt:
            warn("Toʻxtatildi")
            break
        except StepFailed as exc:
            bad(f"{name}: {exc}")
        except Exception as exc:
            import traceback
            base.log(traceback.format_exc())
            bad(f"{name}: kutilmagan xato: {exc!r}")
    print()
    say(f"Tamom. Bobur’ga shu faylni yuboring:  {base.LOG_PATH}", "b")
    return 0


if __name__ == "__main__":
    sys.exit(main())
