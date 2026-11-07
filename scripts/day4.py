"""Modda — 4-kun, GPU noutbukda: sozlash, toʻliq baholash, zaxira demo. Bitta skript, bitta hisobot.

    double-click scripts\\day4.bat            (Bobur tanlagan LLM bilan: scripts\\day4.bat --llm gemma4:e4b)

  1 llm        --llm MODEL boʻlsa: .env dagi LLM_MODEL ni oʻzgartiradi (bakeoff natijasiga qarab Bobur aytadi)
  2 calibrate  «Bilmayman» chegarasi τ: savol ↔ eng yaqin modda oʻxshashligi; ajratish yaxshi boʻlsa DENSE_TAU .env ga yoziladi
  3 eval       qidiruv sifati, 45 oltin savol (dense, BM25, gibrid) → data\\reports\\eval.json
  4 demo       6 demo savol yangi sozlamalar bilan (τ, kuchaytirilgan iqtibos tekshiruvchi)
  5 build      sayt: npm run build (frontend_idea\\dist)
  6 fixture    zaxira «Namuna rejimi» uchun haqiqiy javobni yozib olish → data\\reports\\fixture.json (Bobur uni
               frontend_idea/public/demo/ ga qoʻyib push qiladi)
  7 video      zaxira demo video (1920×1080 .webm) + haqiqiy kadr/s — ekranda Chromium oynasi ochiladi, ≈ 2 daqiqa tegmang
  8 report     toʻliq baholash hisoboti → data\\reports\\BAHOLASH.md (logga ham yoziladi)

Hammasi data\\reports\\day4-<vaqt>.log ga ham yoziladi — shu faylni (va fixture.json, video’ni) Bobur’ga yuboring.
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


def part_report():
    code, out = base.modda("report", check=False, timeout=600)
    if code != 0:
        raise StepFailed("report xato bilan tugadi")
    ok(f"Hisobot: {REPORTS / 'BAHOLASH.md'}")


def main():
    ap = argparse.ArgumentParser(description="Modda — 4-kun: τ, baholash, zaxira demo, hisobot")
    ap.add_argument("--only", help="vergul bilan: " + ",".join(PARTS))
    ap.add_argument("--llm", help="LLM_MODEL ni shu modelga oʻzgartirish (masalan qwen3:8b)")
    ap.add_argument("--question", default=QUESTION)
    a = ap.parse_args()
    parts = [p for p in PARTS if not a.only or p in a.only.split(",")]
    if IS_WIN:
        base.keep_awake()
    git = srv.find_git()
    code, head = run([git, "-C", ROOT, "log", "-1", "--format=%h %ad %s", "--date=short"], check=False, quiet=True) if git else (1, "")
    print(f"{C['b']}{C['c']}Modda — 4-kun (GPU noutbuk){C['0']}   {ROOT}")
    say(f"Kod versiyasi: {head.strip().splitlines()[-1] if code == 0 and head.strip() else '?'}  |  Hisobot: {base.LOG_PATH}")
    if not srv.index_complete():
        warn("Indeks toʻliq emas — natijalar Bobur’dagidan farq qiladi (avval scripts\\day3.bat)")
    fns = {"llm": lambda: part_llm(a.llm), "calibrate": part_calibrate, "eval": part_eval, "demo": part_demo,
           "build": part_build, "fixture": lambda: part_fixture(a.question), "video": lambda: part_video(a.question),
           "report": part_report}
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
    say(f"Tamom. Bobur’ga yuboring: {base.LOG_PATH}" + (f", {FIXTURE}" if FIXTURE.exists() else ""), "b")
    return 0


if __name__ == "__main__":
    sys.exit(main())
