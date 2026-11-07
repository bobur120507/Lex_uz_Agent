"""Modda — 4-kun, GPU noutbukda: sozlash, toʻliq baholash, zaxira demo. Bitta skript, bitta hisobot.

    double-click scripts\\day4.bat            (Bobur tanlagan LLM bilan: scripts\\day4.bat --llm gemma4:e4b)
                                             (bakeoff’dan keyin oʻzi tanlasin: scripts\\day4.bat --llm auto)

  0 bakeoff    (--llm auto yoki --only bakeoff) qwen3:8b va gemma4:e4b — 20 oltin savol, «fikrlash»siz; qoida boʻyicha tanlaydi
  1 llm        --llm MODEL boʻlsa: .env dagi LLM_MODEL ni oʻzgartiradi (--llm auto: bakeoff gʻolibi)
  2 calibrate  «Bilmayman» chegarasi τ: savol ↔ eng yaqin modda oʻxshashligi; ajratish yaxshi boʻlsa DENSE_TAU .env ga yoziladi
  3 eval       qidiruv sifati, 45 oltin savol (dense, BM25, gibrid) → data\\reports\\eval.json
  4 demo       6 demo savol yangi sozlamalar bilan (τ, kuchaytirilgan iqtibos tekshiruvchi)
  5 build      sayt: npm run build (frontend_idea\\dist)
  6 fixture    zaxira «Namuna rejimi» uchun haqiqiy javobni yozib olish → data\\reports\\fixture.json (Bobur uni
               frontend_idea/public/demo/ ga qoʻyib push qiladi)
  7 video      zaxira demo video (1920×1080 .webm) + haqiqiy kadr/s — ekranda Chromium oynasi ochiladi, ≈ 2 daqiqa tegmang
  8 report     toʻliq baholash hisoboti → data\\reports\\BAHOLASH.md (logga ham yoziladi)

Oxirida shu ishga tushirishning hamma fayllari data\\reports\\Bobur_uchun-<vaqt>\\ ga yigʻiladi — shu papkani Bobur’ga yuboring.
  --only calibrate,eval,report     faqat shu qismlar        --question "..."   fixture/video savoli
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_windows as base                          # noqa: E402

_unused = base.LOG_PATH
base._log.close()
if _unused.exists() and _unused.stat().st_size == 0:
    _unused.unlink()
base.LOG_PATH = base.REPORTS / f"day4-{datetime.now():%Y%m%d-%H%M%S}.log"
base._log = open(base.LOG_PATH, "a", encoding="utf-8")
import setup_server as srv                            # noqa: E402
from setup_windows import C, IS_WIN, REPORTS, ROOT, VPY, StepFailed, bad, ok, run, say, warn  # noqa: E402

PARTS = ["llm", "calibrate", "eval", "demo", "build", "fixture", "video", "report"]
OPTIONAL = ["bakeoff", "browser"]
BAKEOFF = ["gemma4:e4b", "qwen3:8b"]
QUESTION = "Har yilgi mehnat taʼtili necha kun?"
FIXTURE = REPORTS / "fixture.json"             # not public/demo/ directly: a changed tracked file would block `git pull`


def set_env(key: str, value: str | None):
    p = ROOT / ".env"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    lines = [l for l in lines if not re.match(rf"\s*{re.escape(key)}\s*=", l)] + ([f"{key}={value}"] if value else [])
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def part_llm(model: str | None):
    if not model:
        cur = next((l.split("=", 1)[1] for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("LLM_MODEL=")), None) \
            if (ROOT / ".env").exists() else None
        return say(f"LLM oʻzgartirilmaydi: {cur or base.LLM_MODEL}")
    if not base.have_model(model):
        base.pull(model)
    set_env("LLM_MODEL", model)
    base.LLM_MODEL = model
    ok(f".env: LLM_MODEL={model}")
    srv.ensure_services()
    srv.unload_all(quiet=True)
    try:
        r = base.http_json(f"{base.OLLAMA}/api/generate", {"model": model, "stream": False, "think": False, "keep_alive": "10m",
                                                             "prompt": "Mehnat shartnomasi nima? 4 gap bilan tushuntiring.",
                                                             "options": {"num_predict": 160}}, timeout=900)
        tps = r.get("eval_count", 0) / max(1e-9, r.get("eval_duration", 1) / 1e9)
        base.http_json(f"{base.OLLAMA}/api/embed", {"model": base.EMBED_MODEL, "input": ["sinov"], "keep_alive": "10m"}, timeout=300)
        shares = ", ".join(f"{m['name']} {m.get('size_vram', 0) / max(1, m.get('size', 1)) * 100:.0f} % GPU’da ({base.fmt_mb(m.get('size', 0))})"
                           for m in srv.loaded_models())
        ok(f"{model}: {tps:.1f} token/s · birga: {shares}")
        if any(m.get("size_vram", 0) < 0.97 * m.get("size", 1) for m in srv.loaded_models()):
            warn("Model GPU’ga toʻliq sigʻmadi — javob sekinroq boʻladi (zaryadlovchi ulanganmi? boshqa dasturlar yopiqmi?)")
    except Exception as exc:
        warn(f"{model} sinovi oʻtmadi: {exc}")


def part_bakeoff(models: list[str]) -> str | None:
    """Same 20 golden questions and context for each model, thinking off (llm.chat) — the day-3 bakeoff measured
    gemma4 with its hidden reasoning on. Returns the model the bakeoff rule picks."""
    have = [m for m in models if base.have_model(m)]
    if not have:
        raise StepFailed(f"modellar yoʻq: {', '.join(models)}")
    srv.ensure_services()
    srv.unload_all(quiet=True)
    say(f"Bakeoff: {', '.join(have)} — 20 oltin savol, har biri ≈ 5 s…")
    code, out = base.modda("bakeoff", "--models", ",".join(have), "--n", "20", check=False, timeout=3 * 3600)
    srv.unload_all(quiet=True)
    m = re.search(r"Qoida boʻyicha gʻolib:\s*(\S+)", out)
    if code != 0 or not m:
        raise StepFailed("bakeoff xato bilan tugadi — yuqoridagi jadval/xabarga qarang")
    best = m.group(1)
    ok(f"Qoida boʻyicha gʻolib (eng kam yolgʻon → koʻp toʻgʻri manba → tezlik): {best}")
    return best


def part_calibrate():
    srv.ensure_services()
    code, out = base.modda("calibrate", "--write-env", check=False, timeout=1800)
    if code != 0:
        raise StepFailed("calibrate xato bilan tugadi")
    m = re.search(r'"advice":\s*"([^"]+)"', out)
    ok(m.group(1) if m else "τ hisoblandi")


def part_eval():
    srv.ensure_services()
    code, out = base.modda("eval", check=False, timeout=3600)
    if code != 0:
        raise StepFailed("eval xato bilan tugadi")
    rep = json.loads(out[out.find("{"):])
    (REPORTS / "eval.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    for mode, r in rep.items():
        rec = next((v for k, v in r.items() if k.lower().startswith("recall")), None)
        say(f"  {mode:8} Recall@5 {rec}   MRR {r.get('mrr')}")


def part_demo():
    srv.ensure_services()
    srv.unload_all(quiet=True)
    out = REPORTS / f"demo-{datetime.now():%Y%m%d-%H%M%S}.json"
    code, _ = run([VPY, ROOT / "scripts" / "demo_questions.py", out], check=False, timeout=3600)
    (ok if code == 0 else warn)("6 demo savol tugadi" if code == 0 else "demo savollarda xato bor — yuqoriga qarang")


def part_build():
    code, _ = srv.npm("run", "build", check=False, timeout=1800)
    if code != 0 or not (srv.DIST / "index.html").exists():
        raise StepFailed("npm run build oʻtmadi")
    ok(f"Sayt yigʻildi: {srv.DIST}")


class Server:
    """The site + API on 127.0.0.1:8080 for the fixture and the video (uses a running one if there is one)."""

    def __enter__(self):
        srv.ensure_services()
        self.proc = None
        if not srv.port_busy(srv.API_PORT):
            self.proc = base.start_detached([VPY, "-m", "modda", "serve", "--host", "127.0.0.1", "--port", srv.API_PORT],
                                            REPORTS / "day4-serve.log", env=srv.server_env())
        if not srv.wait_ready(180):
            raise StepFailed(f"server javob bermadi ({REPORTS / 'day4-serve.log'})")
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()


def part_fixture(question: str):
    with Server():
        code, out = run([VPY, ROOT / "frontend_idea" / "scripts" / "record_demo.py", question, "--api", f"http://127.0.0.1:{srv.API_PORT}",
                         "--note", f"GPU noutbuk, {datetime.now():%Y-%m-%d}", "--out", FIXTURE], check=False, timeout=1800)
    if code != 0 or not FIXTURE.exists():
        raise StepFailed("fixture yozilmadi")
    ok(f"Zaxira namuna: {FIXTURE} ({FIXTURE.stat().st_size / 1e6:.1f} MB) — Bobur’ga yuboring")


def part_video(question: str):
    node = srv.find_node()
    if not node:
        raise StepFailed("Node.js topilmadi (setup_server node qadami)")
    front = ROOT / "frontend_idea"
    say("Chromium (Playwright) tayyorlanmoqda — birinchi marta ≈ 150 MB yuklanadi…")
    run([node, front / "node_modules" / "playwright" / "cli.js", "install", "chromium"], check=False, timeout=1800)
    say("Video yozilmoqda: ekranda oyna ochiladi — ≈ 2 daqiqa sichqoncha va klaviaturaga tegmang.", "y")
    with Server():
        code, out = run([node, front / "scripts" / "record_video.mjs", f"http://127.0.0.1:{srv.API_PORT}/", REPORTS / "video", question],
                        cwd=front, check=False, timeout=1800)
    try:
        r = json.loads(out[out.find("{"):])
    except Exception:
        raise StepFailed("video yozilmadi — yuqoridagi xabarga qarang")
    (ok if (r.get("fps_median") or 0) >= 45 else warn)(
        f"Kadr/s: median {r.get('fps_median')}, eng past {r.get('fps_min')} (maqsad ≥ 45) · render koeff. {r.get('render_scale')} · GPU: {r.get('gpu')}")
    ok(f"Javob {r.get('answer_s')} s da keldi · video: {r.get('video')}")
    if r.get("errors"):
        warn(f"Sahifa xatolari: {r['errors'][:3]}")
    base.mark_done("day4_video", **{k: r.get(k) for k in ("fps_median", "fps_min", "answer_s", "video", "gpu")})


BROWSERS = [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"]


def part_browser():
    """Windows «Graphics settings → High performance» for Chrome / Edge / Playwright’s Chromium: on a laptop with
    two GPUs the browser otherwise draws the 3-D site on the integrated Intel GPU (day4: 27 kadr/s on Iris Xe)."""
    if not IS_WIN:
        return warn("Faqat Windows uchun")
    import glob
    import os
    exes = [os.path.expandvars(p) for p in BROWSERS]
    exes += glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win\chrome.exe"))
    exes = [e for e in exes if Path(e).exists()]
    if not exes:
        return warn("Chrome / Edge topilmadi")
    lines = "\n".join(f"Set-ItemProperty -Path $k -Name '{e}' -Value 'GpuPreference=2;'" for e in exes)
    code, out = srv.ps(rf"""$k = 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'
if (-not (Test-Path $k)) {{ New-Item -Path $k -Force | Out-Null }}
{lines}
Write-Output 'gpu-pref-ok'""")
    if "gpu-pref-ok" not in out:
        raise StepFailed("sozlama yozilmadi — qoʻlda: Sozlamalar → Tizim → Displey → Grafika → brauzer → «Yuqori unumdorlik»")
    for e in exes:
        ok(f"Yuqori unumdorlik GPU: {e}")
    warn("Brauzer ochiq boʻlsa — yopib, qayta oching (sozlama keyingi ishga tushirishda kuchga kiradi).")


def part_report():
    code, out = base.modda("report", check=False, timeout=600)
    if code != 0:
        raise StepFailed("report xato bilan tugadi")
    ok(f"Hisobot: {REPORTS / 'BAHOLASH.md'}")


def collect(started: float) -> Path:
    """Copies this run's own outputs into one folder for Bobur — files older than the run are left out, so an
    old BAHOLASH.md or fixture.json can no longer be sent by mistake."""
    dest = REPORTS / f"Bobur_uchun-{datetime.fromtimestamp(started):%Y%m%d-%H%M}"
    dest.mkdir(parents=True, exist_ok=True)
    pats = ["BAHOLASH.md", "fixture.json", "calibration.json", "eval.json", "demo-*.json", "bakeoff-*.md", "bakeoff-*.csv",
            "video/*.webm"]
    fresh = [f for pat in pats for f in REPORTS.glob(pat) if f.is_file() and f.stat().st_mtime >= started]
    for f in fresh:
        shutil.copy2(f, dest / f.name)
    base._log.flush()
    shutil.copy2(base.LOG_PATH, dest / base.LOG_PATH.name)
    say(f"  {len(fresh) + 1} fayl: {', '.join(sorted([base.LOG_PATH.name, *(f.name for f in fresh)]))}")
    return dest


def main():
    started = time.time()
    ap = argparse.ArgumentParser(description="Modda — 4-kun: τ, baholash, zaxira demo, hisobot")
    ap.add_argument("--only", help="vergul bilan: " + ",".join(PARTS + OPTIONAL))
    ap.add_argument("--llm", help="LLM_MODEL ni shu modelga oʻzgartirish (masalan qwen3:8b); auto = bakeoff gʻolibi")
    ap.add_argument("--models", default=",".join(BAKEOFF), help="bakeoff modellari")
    ap.add_argument("--question", default=QUESTION)
    a = ap.parse_args()
    order = ["bakeoff", "llm", "browser", *PARTS[1:]]                 # the GPU setting before the video
    wanted = set(a.only.split(",")) if a.only else set(PARTS)
    if a.llm == "auto":
        wanted |= {"bakeoff", "llm"}
    parts = [p for p in order if p in wanted]
    chosen = {"model": None if a.llm == "auto" else a.llm}
    if IS_WIN:
        base.keep_awake()
    git = srv.find_git()
    code, head = run([git, "-C", ROOT, "log", "-1", "--format=%h %ad %s", "--date=short"], check=False, quiet=True) if git else (1, "")
    print(f"{C['b']}{C['c']}Modda — 4-kun (GPU noutbuk){C['0']}   {ROOT}")
    say(f"Kod versiyasi: {head.strip().splitlines()[-1] if code == 0 and head.strip() else '?'}  |  Hisobot: {base.LOG_PATH}")
    try:
        srv.ensure_services()                       # Qdrant must be up, or the check below reports a false «incomplete»
    except Exception as exc:
        warn(f"Xizmatlar ishga tushmadi: {exc}")
    if not srv.index_complete():
        warn("Indeks toʻliq emas — natijalar Bobur’dagidan farq qiladi (avval scripts\\day3.bat)")
    def do_bakeoff():
        best = part_bakeoff(a.models.split(","))
        if a.llm == "auto":
            chosen["model"] = best

    fns = {"bakeoff": do_bakeoff,
           "llm": lambda: part_llm(chosen["model"]), "calibrate": part_calibrate, "eval": part_eval, "demo": part_demo,
           "build": part_build, "fixture": lambda: part_fixture(a.question), "video": lambda: part_video(a.question),
           "report": part_report, "browser": part_browser}
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
    out = collect(started)
    say(f"Tamom. Bobur’ga shu papkani toʻliq yuboring (faqat shu ishga tushirishdagi fayllar): {out}", "b")
    return 0


if __name__ == "__main__":
    sys.exit(main())
