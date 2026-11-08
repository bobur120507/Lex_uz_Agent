"""Modda — yakuniy test: «RAG API — test spetsifikatsiyasi (lex.uz)» boʻyicha 100 savol. GPU noutbukda, bitta skript.

    double-click scripts\\day6.bat          (≈ 25–35 daqiqa; noutbuk zaryadlovchida boʻlsin)

  1 pull      git pull — eng oxirgi kod
  2 machine   zaryadlovchi, GPU
  3 services  Ollama + Qdrant, modellar, indeks toʻliq; python-docx (Word hisobot uchun)
  4 key       .env da MODDA_API_KEY (testchi uchun alohida kalit) — yoʻq boʻlsa yaratadi
  5 testset   data\\testset\\test100.csv (100 savol: 35 faktik, 15 raqam, 15 koʻp modda, 10 oʻzgargan norma,
              10 rus/kirill, 10 javobsiz, 5 ogʻzaki) — yoʻq boʻlsa yaratadi
  6 server    eski serverni toʻxtatib, yangisini ishga tushiradi (yangi kod + kalit, 0.0.0.0:8080 — tarmoqdan ham)
  7 test      scripts\\rag_api_test.py: API checklist (§7) → 10 batch × 10 savol → idempotentlik, 409, takrorlanuvchanlik
              → metrikalar (§6) → HISOBOT.html / .docx / .md (100 savol va javob), results.csv, metrics.json
  8 collect   hammasi data\\reports\\Bobur_uchun-<vaqt>\\ ga — shu papkani Bobur’ga yuboring

  --only test,collect     faqat shu qismlar      --keep-server   oxirida serverni toʻxtatmaydi (testchi ulanishi uchun)
  --judge none            LLM-hakamsiz (faqat kalit faktlar)      --skip-checks   API checklistsiz
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_windows as base                          # noqa: E402

_unused = base.LOG_PATH
base._log.close()
if _unused.exists() and _unused.stat().st_size == 0:
    _unused.unlink()
base.LOG_PATH = base.REPORTS / f"day6-{datetime.now():%Y%m%d-%H%M%S}.log"
base._log = open(base.LOG_PATH, "a", encoding="utf-8")
import setup_server as srv                            # noqa: E402
from setup_windows import C, IS_WIN, REPORTS, ROOT, StepFailed, VPY, bad, ok, run, say, warn  # noqa: E402

PARTS = ["pull", "machine", "services", "key", "testset", "server", "test", "collect"]
LLM, EMBED = "gemma4:e4b", "bge-m3"
TESTSET = ROOT / "data" / "testset" / "test100.csv"
STATE: dict = {"problems": []}


def problem(text: str):
    STATE["problems"].append(text)
    bad(text)


# ----------------------------------------------------------------------------------------------- .env

def env_get(key: str) -> str | None:
    p = ROOT / ".env"
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip("\"'") or None
    return None


def env_set(key: str, value: str):
    p = ROOT / ".env"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    lines = [l for l in lines if not l.strip().startswith(f"{key}=")] + [f"{key}={value}"]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------------------------- parts

def part_pull():
    git = srv.find_git()
    if not git:
        return warn("git topilmadi — kod yangilanmadi")
    _, out = run([git, "-C", ROOT, "status", "--porcelain", "--untracked-files=no"], check=False, quiet=True)
    changed = [l for l in out.splitlines() if l.strip()]
    if changed:
        return warn(f"git pull oʻtkazib yuborildi — oʻzgartirilgan fayllar: {', '.join(l[3:] for l in changed[:4])}")
    code, _ = run([git, "-C", ROOT, "pull", "--ff-only"], check=False, timeout=300)
    _, head = run([git, "-C", ROOT, "log", "-1", "--format=%h %ad %s", "--date=short"], check=False, quiet=True)
    (ok if code == 0 else warn)(f"Kod: {head.strip().splitlines()[-1] if head.strip() else '?'}")
    if not (ROOT / "src" / "modda" / "v1.py").exists():
        raise StepFailed("src/modda/v1.py yoʻq — Bobur yangi kodni push qilganmi?")


def part_machine():
    if IS_WIN:
        _, out = srv.ps("(Get-CimInstance Win32_Battery | Select-Object -First 1).BatteryStatus; "
                        "(Get-CimInstance Win32_Battery | Select-Object -First 1).EstimatedChargeRemaining")
        vals = [v.strip() for v in out.splitlines() if v.strip()]
        if vals and vals[0] != "2":
            warn(f"Noutbuk batareyada ({vals[1] if len(vals) > 1 else '?'} %) — zaryadlovchini ulang: batareyada javoblar sekinlashadi "
                 "va latency metrikasi notoʻgʻri chiqadi")
        elif vals:
            ok(f"Zaryadlovchi ulangan ({vals[1] if len(vals) > 1 else '?'} %)")
    code, out = run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"], check=False, quiet=True)
    (ok if code == 0 else warn)(f"GPU: {out.strip().splitlines()[0] if code == 0 and out.strip() else 'nvidia-smi ishlamadi'}")


def part_services():
    srv.ensure_services()
    for m in (LLM, EMBED):
        if not base.have_model(m):
            raise StepFailed(f"{m} modeli yoʻq — ollama pull {m}")
    if not srv.index_complete():
        raise StepFailed("Indeks toʻliq emas — scripts\\day3.bat")
    ok("Ollama, Qdrant, modellar, indeks — tayyor")
    code, _ = run([VPY, "-c", "import docx"], check=False, quiet=True)
    if code != 0:
        say("Word hisobot uchun python-docx oʻrnatilmoqda…")
        code, _ = run([VPY, "-m", "pip", "install", "python-docx"], check=False, timeout=600)
        (ok if code == 0 else warn)("python-docx " + ("oʻrnatildi" if code == 0 else "oʻrnatilmadi — hisobot .html va .md da boʻladi"))
    else:
        ok("python-docx bor")


def part_key():
    key = env_get("MODDA_API_KEY")
    if not key:
        key = "modda-test-" + secrets.token_urlsafe(24)
        env_set("MODDA_API_KEY", key)
        ok("MODDA_API_KEY yaratildi va .env ga yozildi (testchi uchun alohida kalit)")
    else:
        ok(f"MODDA_API_KEY bor (…{key[-4:]})")
    STATE["key"] = key


def part_testset():
    if not TESTSET.exists():
        run([VPY, ROOT / "scripts" / "build_testset.py"], check=True)
    n = sum(1 for _ in TESTSET.open(encoding="utf-8")) - 1
    (ok if n == 100 else warn)(f"Test toʻplami: {TESTSET.relative_to(ROOT)} — {n} savol")


class Server:
    proc = None

    @classmethod
    def stop_old(cls):
        """A server already on 8080 runs old code without the key — stop it (only if it is Python)."""
        if not srv.port_busy(srv.API_PORT):
            return
        if IS_WIN:
            srv.ps(f"Get-NetTCPConnection -LocalPort {srv.API_PORT} -State Listen -ErrorAction SilentlyContinue | "
                   "ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; "
                   "if ($p -and $p.ProcessName -like 'python*') { Stop-Process -Id $p.Id -Force } }")
        time.sleep(2)
        if srv.port_busy(srv.API_PORT):
            raise StepFailed(f"{srv.API_PORT}-port band (Python emas?) — start_modda oynasini yoping va qayta urinib koʻring")
        ok("Eski server toʻxtatildi (yangi kod va kalit bilan qayta ishga tushadi)")

    @classmethod
    def start(cls) -> float | None:
        cls.stop_old()
        t0 = time.time()
        env = srv.server_env()
        env["MODDA_API_KEY"] = STATE.get("key") or env_get("MODDA_API_KEY") or ""
        cls.proc = base.start_detached([VPY, "-m", "modda", "serve", "--host", "0.0.0.0", "--port", srv.API_PORT],
                                       REPORTS / "day6-serve.log", env=env)
        return (time.time() - t0) if srv.wait_ready(180) else None

    @classmethod
    def stop(cls):
        if cls.proc:
            cls.proc.terminate()
            cls.proc = None


def part_server():
    t = Server.start()
    if t is None:
        raise StepFailed(f"Server 3 daqiqada tayyor boʻlmadi — {REPORTS / 'day6-serve.log'}")
    ok(f"Server tayyor ({t:.0f} s): http://127.0.0.1:{srv.API_PORT}/v1/health")
    ip = srv.lan_ip()
    if ip:
        say(f"Tarmoqdan (testchi uchun): http://{ip}:{srv.API_PORT}/v1/…")
    STATE["lan"] = f"http://{ip}:{srv.API_PORT}" if ip else None


def part_test(judge: str, skip_checks: bool):
    run_id = f"eval-{datetime.now():%Y-%m-%d-%H%M}"
    out = REPORTS / "rag100" / run_id
    cmd = [VPY, ROOT / "scripts" / "rag_api_test.py", "--base-url", f"http://127.0.0.1:{srv.API_PORT}", "--run-id", run_id,
           "--out", out, "--judge", judge, "--testset", TESTSET]
    if skip_checks:
        cmd.append("--skip-checks")
    env = base.child_env()
    env["MODDA_API_KEY"] = STATE.get("key") or env_get("MODDA_API_KEY") or ""
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    say("100 savol yuborilmoqda — har batch ≈ 30–60 s, keyin baholash (LLM-hakam) ≈ 5–10 daqiqa. Kompyuterga tegmasa ham boʻladi.")
    t0 = time.time()
    p = subprocess.Popen([str(c) for c in cmd], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:                              # live progress on screen and in the log
        line = line.rstrip()
        print("    " + line, flush=True)
        base.log("    " + line)
    code = p.wait()
    STATE["out"] = out
    if code != 0 or not (out / "metrics.json").exists():
        raise StepFailed(f"rag_api_test.py chiqish kodi {code} — yuqoridagi xabarga qarang")
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    checks = json.loads((out / "checks.json").read_text(encoding="utf-8")) if (out / "checks.json").exists() else []
    met = sum(1 for v in m["targets_met"].values() if v)
    (ok if met == len(m["targets_met"]) else warn)(f"Metrikalar maqsadga: {met} / {len(m['targets_met'])} · "
                                                    f"API checklist: {sum(1 for c in checks if c['ok'])} / {len(checks)} · "
                                                    f"{base.fmt_dur(time.time() - t0)}")
    say(f"Hisobot: {out / 'HISOBOT.html'}")


def collect(started: float) -> Path:
    dest = REPORTS / f"Bobur_uchun-{datetime.fromtimestamp(started):%Y%m%d-%H%M}"
    dest.mkdir(parents=True, exist_ok=True)
    out: Path | None = STATE.get("out")
    if out and out.exists():
        for name in ("HISOBOT.html", "HISOBOT.docx", "HISOBOT.md", "metrics.json", "checks.json", "results.csv", "meta.json"):
            if (out / name).exists():
                shutil.copy2(out / name, dest / name)
        with zipfile.ZipFile(dest / f"{out.name}-xom.zip", "w", zipfile.ZIP_DEFLATED) as z:   # raw batches, requests, judge log
            for f in out.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(out.parent))
    for f in [REPORTS / "day6-serve.log"]:
        if f.exists() and f.stat().st_mtime >= started:
            shutil.copy2(f, dest / f.name)
    key, lan = STATE.get("key") or env_get("MODDA_API_KEY"), STATE.get("lan")
    if key:
        (dest / "TESTCHI-UCHUN.md").write_text(
            "# Testchi uchun (spetsifikatsiya §7: alohida API kalit va base URL)\n\n"
            f"- Base URL: `{lan or 'http://<noutbuk-IP>:8080'}` (bir tarmoqda; serverni `start_modda.bat` bilan yoqing)\n"
            f"- Kalit: `Authorization: Bearer {key}`\n"
            "- Endpointlar: `POST /v1/rag/batch`, `GET /v1/rag/batch/{batch_id}`, `POST /v1/rag/query`, `GET /v1/meta`, `GET /v1/health`\n"
            "- Testchining oʻz skripti: `python scripts/rag_api_test.py --base-url <URL> --api-key <KALIT> --testset <CSV>`\n\n"
            "Kalit maxfiy: faqat testchiga bering. Yangi kalit: `.env` dagi `MODDA_API_KEY` ni oʻchirib, `day6.bat --only key` ni qayta ishga tushiring.\n",
            encoding="utf-8")
    base._log.flush()
    shutil.copy2(base.LOG_PATH, dest / base.LOG_PATH.name)
    return dest


def main():
    started = time.time()
    ap = argparse.ArgumentParser(description="Modda — yakuniy test: 100 savol (RAG API spetsifikatsiyasi)")
    ap.add_argument("--only", help="vergul bilan: " + ",".join(PARTS))
    ap.add_argument("--judge", default="auto", help="auto | none | <ollama model>")
    ap.add_argument("--skip-checks", action="store_true")
    ap.add_argument("--keep-server", action="store_true")
    a = ap.parse_args()
    wanted = set(a.only.split(",")) if a.only else set(PARTS)
    if wanted - set(PARTS):
        warn(f"Nomaʼlum qism(lar): {', '.join(sorted(wanted - set(PARTS)))} — avval `git pull`?")
    if IS_WIN:
        base.keep_awake()
    print(f"{C['b']}{C['c']}Modda — yakuniy test: 100 savol (RAG API spetsifikatsiyasi){C['0']}   {ROOT}")
    say(f"Hisobot: {base.LOG_PATH}")
    if "test" in wanted and "key" not in wanted:
        STATE["key"] = env_get("MODDA_API_KEY")
    fns = {"pull": part_pull, "machine": part_machine, "services": part_services, "key": part_key, "testset": part_testset,
           "server": part_server, "test": lambda: part_test(a.judge, a.skip_checks), "collect": lambda: None}
    try:
        for i, name in enumerate([p for p in PARTS if p in wanted], 1):
            print()
            say(f"══ [{i}/{len(wanted)}] {name} ══", "b")
            t0 = time.time()
            try:
                fns[name]()
                say(f"{name} tugadi ({base.fmt_dur(time.time() - t0)})")
            except KeyboardInterrupt:
                warn("Toʻxtatildi")
                break
            except StepFailed as exc:
                problem(f"{name}: {exc}")
                if name in ("pull", "services", "server", "test"):
                    break
            except Exception as exc:
                import traceback
                base.log(traceback.format_exc())
                problem(f"{name}: kutilmagan xato {exc!r}"[:300])
                break
    finally:
        if not a.keep_server:
            Server.stop()
    print()
    dest = collect(started)
    if STATE["problems"]:
        say("Muammolar: " + "; ".join(STATE["problems"]), "r")
    say(f"Tamom. Bobur’ga shu papkani yuboring: {dest}", "b")
    return 1 if STATE["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
