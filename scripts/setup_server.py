"""Modda — make a Windows laptop with an NVIDIA GPU the project's server, in the same state as Bobur's computer.

    double-click scripts\\setup_server.bat        (or: python scripts\\setup_server.py)

What it does (every step checks its result; when one way fails it tries the next; finished steps are skipped
when you run it again, so it is safe to stop with Ctrl+C and start again):

   1 system     Windows, Python, disk, RAM, NVIDIA GPU + driver; the laptop does not sleep while this runs
   2 git        Git for Windows (winget → portable MinGit) — for `update_modda.bat`
   3 python     .venv + the project with FastAPI (pip, three fallbacks)
   4 ollama     Ollama (running → on disk → winget → official installer → portable zip), started
   5 models     bge-m3 + qwen3:8b (+ gemma4:e4b and Llama-3.1-8B-Uz for the LLM bake-off); checks they run on the GPU
   6 corpus     the Lex.uz corpus from Hugging Face at the fixed revision, checksum-verified
   7 qdrant     Qdrant v1.20.0 (portable, no Docker needed)
   8 env        .env (SQLite database in data\\ — no passwords)
   9 ingest     54 173 articles → database
  10 numbers    superscript article numbers (195¹)
  11 chunk      183 170 chunks
  12 rss        the Lex.uz RSS feed (new documents)
  13 index      the search index: imports Bobur's snapshot (modda-*.snapshot + .manifest.json.gz) if it finds
                one — in Downloads, on the Desktop, in the project folder or data\\import — otherwise builds the
                full bge-m3 + BM25 index on this GPU
  14 eval       retrieval quality on the 45 golden questions (compared with Bobur's numbers)
  15 node       Node.js LTS (winget → portable zip)
  16 frontend   frontend_idea: npm ci, unit tests, production build (frontend_idea\\dist)
  17 lan        Windows Firewall: lets other computers on the same Wi-Fi open the site (port 8080, and 5174 for
                the dev server) — private networks only; one administrator prompt
  18 launchers  start_modda.bat, start_dev.bat, update_modda.bat in the project folder
  19 verify     starts the server, asks a real question with qwen3:8b on the GPU, checks the site, stops it

Optional (off unless asked):
  --ssh [--ssh-key FILE]  OpenSSH server so Bobur can manage this laptop from his: `ssh <user>@<ip>`
                          (administrator prompt; private networks only; with a key no password is needed)
  --autostart             start the server when this user logs in (Startup folder shortcut)
  --reranker              sentence-transformers + CUDA PyTorch for the optional reranker (≈ 3 GB)
  --no-bakeoff-models     only bge-m3 + qwen3:8b
  --snapshot FILE         use this snapshot file
  --only STEP[,STEP] / --from STEP / --list / --fresh

Daily use after setup (also written as .bat files in the project folder):
  python scripts\\setup_server.py --start         services + server: http://localhost:8080 (and http://<ip>:8080)
  python scripts\\setup_server.py --start --dev   the same + Vite dev server with hot reload on :5174
  python scripts\\setup_server.py --update        git pull + packages + frontend build
  python scripts\\setup_server.py --status        what runs, index size, models, addresses

Standard library only (it runs before anything is installed). Shares helpers with scripts\\setup_windows.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_windows as base                          # noqa: E402  (same folder)
from setup_windows import (C, DATA, IS_WIN, OLLAMA, QDRANT, REPORTS, ROOT, STATE, TOOLS, VPY,  # noqa: E402
                           StepFailed, bad, fmt_dur, fmt_mb, http_json, mark_done, modda, ok, run, say, warn)

FRONT = ROOT / "frontend_idea"
DIST = FRONT / "dist"
API_PORT, DEV_PORT = 8080, 5174
BAKEOFF_MODELS = ["gemma4:e4b", "hf.co/QuantFactory/Llama-3.1-8B-Instuct-Uz-GGUF:Q4_K_M"]
COLLECTION = os.environ.get("COLLECTION", "modda_chunks")
REPO_URL = "https://github.com/bobur120507/lex_uz_agent"
# Bobur's computer on 2026-11-06 — the state this laptop should reach
REFERENCE = {"articles": 54_173, "chunks": 183_170, "superscript": 1_540, "hybrid_recall5": 0.911, "hybrid_mrr": 0.766}

STEPS = ["system", "git", "python", "ollama", "models", "corpus", "qdrant", "env", "ingest", "numbers", "chunk",
         "rss", "index", "eval", "node", "frontend", "lan", "launchers", "verify"]
OPTIONAL = ["reranker", "ssh", "autostart"]


# --------------------------------------------------------------------------- small helpers

def lan_ip() -> str | None:
    """The address other computers on the same network use (no packet is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def port_busy(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ps(script: str, *, admin=False, timeout=900) -> tuple[int, str]:
    """Runs a PowerShell script; with admin=True through one UAC prompt (output goes to a log file)."""
    if not IS_WIN:
        return 1, "not Windows"
    TOOLS.mkdir(parents=True, exist_ok=True)
    f = TOOLS / f"modda-{int(time.time() * 1000)}.ps1"
    out = f.with_suffix(".log")
    f.write_text(("$ErrorActionPreference = 'Continue'\n" + script), encoding="utf-8-sig")
    if not admin:
        code, text = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", f], check=False, quiet=True, timeout=timeout)
        f.unlink(missing_ok=True)
        return code, text
    fq, oq = (str(x).replace("'", "''") for x in (f, out))            # a ' in the path (e.g. Gʻayrat) must not break the script
    inner = f"-NoProfile -ExecutionPolicy Bypass -Command \"& '{fq}' *> '{oq}'; exit $LASTEXITCODE\""
    outer = (f"$p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList '{inner.replace(chr(39), chr(39) * 2)}'; "
             "exit $p.ExitCode")
    code, _ = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", outer], check=False, quiet=True, timeout=timeout)
    raw = out.read_bytes() if out.exists() else b""                    # Windows PowerShell 5 writes UTF-16 here
    text = raw.decode("utf-16", errors="replace") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", errors="replace")
    base.log(text)
    f.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    return code, text


def winget(pkg: str, *extra: str, timeout=1800) -> bool:
    if not (IS_WIN and shutil.which("winget")):
        return False
    say(f"{pkg} winget orqali oʻrnatilmoqda…")
    code, _ = run(["winget", "install", "--id", pkg, "-e", "--silent", "--accept-package-agreements",
                   "--accept-source-agreements", *extra], check=False, timeout=timeout)
    return code == 0


def find_exe(name: str, dirs: list[Path]) -> Path | None:
    hit = shutil.which(name)
    if hit:
        return Path(hit)
    for d in dirs:
        p = d / name
        if p.exists():
            return p
    return None


def add_path(d: Path):
    os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


def stats() -> dict:
    return base.db_stats()


def qdrant_points() -> int | None:
    try:
        return http_json(f"{QDRANT}/collections/{COLLECTION}", timeout=5)["result"]["points_count"]
    except Exception:
        return None


def step_system():
    base.step_system()
    free = shutil.disk_usage(ROOT).free
    need = 40e9
    (ok if free >= need else warn)(f"Server uchun joy: {fmt_mb(free)} boʻsh (kerak ≈ 40 GB: 4 ta LLM ≈ 21 GB, indeks ≈ 5 GB, "
                                   "snapshot 2 GB, korpus va baza ≈ 3 GB). Kam boʻlsa: --no-bakeoff-models")


# --------------------------------------------------------------------------- 2. git

GIT_DIRS = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "cmd", TOOLS / "git" / "cmd"]


def find_git() -> Path | None:
    return find_exe("git.exe" if IS_WIN else "git", GIT_DIRS)


def step_git():
    git = find_git()
    if not git and IS_WIN:
        winget("Git.Git")
        git = find_git()
    if not git and IS_WIN:
        say("Portativ MinGit yuklab olinmoqda…")
        try:
            rel = http_json("https://api.github.com/repos/git-for-windows/git/releases/latest", timeout=30)
            asset = next(a for a in rel["assets"] if re.fullmatch(r"MinGit-[\d.]+-64-bit\.zip", a["name"]))
            z = base.download(asset["browser_download_url"], TOOLS / "downloads" / asset["name"])
            base.extract(z, TOOLS / "git")
        except Exception as exc:
            warn(f"MinGit yuklanmadi: {exc}")
        git = find_git()
    if not git:
        warn("Git oʻrnatilmadi — loyiha ishlaydi, faqat update_modda.bat (git pull) ishlamaydi. https://git-scm.com/download/win")
        return mark_done("git", git=None)
    add_path(git.parent)
    v = run([git, "--version"], check=False, quiet=True)[1].strip()
    ok(f"{v} ({git})")
    if (ROOT / ".git").exists():
        known = run([git, "config", "--global", "--get-all", "safe.directory"], check=False, quiet=True)[1]
        if ROOT.as_posix() not in known.splitlines():
            run([git, "config", "--global", "--add", "safe.directory", ROOT.as_posix()], check=False, quiet=True)
        head = run([git, "-C", ROOT, "log", "-1", "--format=%h %ad %s", "--date=short"], check=False, quiet=True)[1].strip()
        remote = run([git, "-C", ROOT, "remote", "get-url", "origin"], check=False, quiet=True)[1].strip()
        ok(f"Repozitoriy: {remote or '—'}  |  oxirgi commit: {head.splitlines()[-1] if head else '—'}")
    else:
        warn(f"Bu papka git repozitoriysi emas (nusxa koʻchirilgan). Yangilanishlarni olish uchun keyinroq: "
             f"git clone {REPO_URL}")
    mark_done("git", git=str(git))


# --------------------------------------------------------------------------- 5. models

def loaded_models() -> list[dict]:
    try:
        return http_json(f"{OLLAMA}/api/ps", timeout=10).get("models", [])
    except Exception:
        return []


def unload_all(quiet=False) -> list[str]:
    """Frees the GPU: other models held in VRAM push bge-m3 / qwen3 partly onto the CPU (10–50× slower)."""
    names = [m["name"] for m in loaded_models()]
    for name in names:
        for ep, body in (("generate", {"model": name, "keep_alive": 0}), ("embed", {"model": name, "input": "x", "keep_alive": 0})):
            try:
                http_json(f"{OLLAMA}/api/{ep}", body, timeout=120)
                break
            except Exception:
                continue
    for _ in range(20):
        if not loaded_models():
            break
        time.sleep(0.5)
    if names and not quiet:
        say(f"GPU boʻshatildi: {', '.join(names)} xotiradan chiqarildi")
    return names


def gpu_share(model: str) -> tuple[float, int, int] | None:
    """(share on GPU 0…1, size, size_vram) of a loaded model."""
    for m in loaded_models():
        if m["name"] == model or m["name"].startswith(model.split(":")[0] + ":") or m["name"] == model + ":latest":
            size, vram = m.get("size") or 0, m.get("size_vram") or 0
            return (vram / size if size else 0.0), size, vram
    return None


def gpu_of(model: str) -> int:
    try:
        for m in http_json(f"{OLLAMA}/api/ps")["models"]:
            if m["name"].startswith(model.split(":")[0]):
                return m.get("size_vram", 0)
    except Exception:
        pass
    return 0


def step_models(bakeoff: bool):
    unload_all()                                       # a model left in VRAM would push bge-m3 partly onto the CPU
    base.step_models(skip_llm=False)                  # bge-m3 + qwen3:8b, embedding on the GPU checked
    sh = gpu_share(base.EMBED_MODEL)
    if sh:
        (ok if sh[0] > 0.97 else warn)(f"bge-m3: {sh[0] * 100:.0f} % GPU’da ({fmt_mb(sh[2])} / {fmt_mb(sh[1])})"
                                       + ("" if sh[0] > 0.97 else " — qolgani CPU’da, sekin! scripts\\day3.bat GPU tekshiruvini koʻring"))
    if not base.have_model(base.LLM_MODEL):
        raise StepFailed(f"{base.LLM_MODEL} yuklanmadi — javob yozish uchun kerak. Internetni tekshirib, qayta ishga tushiring.")
    say(f"{base.LLM_MODEL} sinab koʻrilmoqda (birinchi chaqiruv modelni GPU’ga yuklaydi)…")
    t0 = time.time()
    try:
        r = http_json(f"{OLLAMA}/api/generate", {"model": base.LLM_MODEL, "prompt": "Salom! Bir soʻz bilan javob bering.",
                                                   "stream": False, "think": False, "keep_alive": "10m",
                                                   "options": {"num_predict": 16}}, timeout=900)
        tps = r.get("eval_count", 0) / max(1e-9, r.get("eval_duration", 1) / 1e9)
        vram = gpu_of(base.LLM_MODEL)
        (ok if vram else warn)(f"{base.LLM_MODEL}: {tps:.0f} token/s, {fmt_mb(vram) + ' VRAM' if vram else 'GPU ishlatilmayapti!'} "
                               f"({fmt_dur(time.time() - t0)})")
    except Exception as exc:
        warn(f"{base.LLM_MODEL} sinovi oʻtmadi: {exc}")
        tps, vram = 0, 0
    extra = []
    if bakeoff:
        for m in BAKEOFF_MODELS:                      # for the LLM bake-off (roadmap, 3rd day) — not required to run
            try:
                base.pull(m)
                extra.append(m)
            except StepFailed as exc:
                warn(f"{exc} — bakeoff uchun, majburiy emas")
    mark_done("models", llm_tokens_per_s=round(tps), llm_vram=vram, bakeoff=extra)


def step_reranker():
    say("Reranker: CUDA bilan PyTorch va sentence-transformers (≈ 3 GB)…")
    for cmd in ([VPY, "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cu124"],
                [VPY, "-m", "pip", "install", "-e", ".[rerank]"]):
        run(cmd, timeout=7200)
    code, out = run([VPY, "-c", "import torch; print(torch.cuda.is_available())"], check=False, quiet=True)
    (ok if "True" in out else warn)(f"PyTorch CUDA: {out.strip().splitlines()[-1] if out.strip() else '?'}")
    mark_done("reranker")


# --------------------------------------------------------------------------- 12. rss

def step_ingest():
    st = stats()
    if STATE.get("ingest") and (st.get("articles") or 0) > 50_000:      # the full corpus has 54 173 articles
        return ok(f"Korpus bazada: {st['articles']:,} modda")
    base.step_ingest()


def step_rss():
    code, out = modda("rss", check=False, timeout=600)
    if code != 0:
        return warn("RSS oʻqilmadi (lex.uz javob bermadi?) — muhim emas, keyinroq: python -m modda rss")
    m = re.search(r"RSS: (\d+)", out)
    mark_done("rss", items=int(m.group(1)) if m else None)


# --------------------------------------------------------------------------- 13. index

def find_snapshot(explicit: str | None) -> tuple[Path, Path | None] | None:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise StepFailed(f"Snapshot topilmadi: {p}")
        cands = [p]
    else:
        home = Path.home()
        dirs = [home / "Downloads", home / "Downloads" / "Telegram Desktop", home / "Desktop", ROOT, DATA / "import",
                DATA / "exports", home / "Documents"]
        if os.environ.get("OneDrive"):
            dirs += [Path(os.environ["OneDrive"]) / "Desktop", Path(os.environ["OneDrive"]) / "Documents"]
        cands = [f for d in dirs if d.exists() for f in d.glob("modda-*.snapshot")]
        if not cands:
            return None
    snap = max(cands, key=lambda p: p.stat().st_mtime)
    man = snap.with_name(snap.name.replace(".snapshot", ".manifest.json.gz"))
    return snap, (man if man.exists() else None)


def index_complete() -> bool:
    st = stats()
    n, dense, pts = st.get("chunks") or 0, st.get("chunks_indexed") or 0, qdrant_points() or 0
    return n > 100_000 and dense >= n * 0.999 and pts >= dense * 0.999


def step_index(snapshot: str | None):
    ensure_services()                                                  # after a reboot with --from index
    if index_complete():
        st = stats()
        return ok(f"Indeks allaqachon toʻliq: {st.get('chunks_indexed'):,} boʻlak, Qdrant’da {qdrant_points():,} nuqta")
    found = find_snapshot(snapshot)
    if found:
        snap, man = found
        say(f"Bobur’ning snapshot’i topildi: {snap} ({fmt_mb(snap.stat().st_size)})"
            + (f" + {man.name}" if man else " — manifest yoʻq, boʻlaklar roʻyxati tekshirilmaydi"))
        args = ["snapshot-import", str(snap)] + (["--manifest", str(man)] if man else [])
        code, out = modda(*args, check=False, timeout=7200)
        if code != 0 and man and "Boʻlaklar mos emas" in out:
            warn("Import oʻtmadi — boʻlaklarni qaytadan yasab (chunk --rebuild) yana urinib koʻramiz")
            modda("chunk", "--rebuild", timeout=7200)
            code, out = modda(*args, check=False, timeout=7200)
        if code == 0 and index_complete():
            st = stats()
            ok(f"Snapshot yuklandi: {st.get('chunks_indexed'):,} boʻlak, Qdrant’da {qdrant_points():,} nuqta")
            return mark_done("index", source="snapshot", snapshot=str(snap), chunks_indexed=st.get("chunks_indexed"))
        warn("Snapshot’dan yuklab boʻlmadi — indeksni shu GPU’da yasaymiz (1–3 soat)")
    else:
        say("Snapshot topilmadi — butun indeks shu GPU’da yasaladi. (Tezroq: Bobur’dagi modda-*.snapshot va "
            ".manifest.json.gz fayllarini Downloads papkasiga qoʻyib, skriptni qayta ishga tushiring.)", "y")
    base.step_bench()
    base.step_index()
    if not index_complete():
        st = stats()
        warn(f"Indeks toʻliq emas: {st.get('chunks_indexed')} / {st.get('chunks')} (ikki qatlamli indeks — qidiruv ishlaydi)")
    mark_done("index", source="built", **{k: stats().get(k) for k in ("chunks", "chunks_indexed")})


def step_eval():
    ensure_services()
    base.step_eval()
    try:
        rep = json.loads((REPORTS / "setup-eval.json").read_text(encoding="utf-8"))
    except Exception:
        return
    rows = []
    for mode, r in (rep.items() if isinstance(rep, dict) else []):
        if isinstance(r, dict) and "recall" in json.dumps(r):
            rec = next((v for k, v in r.items() if k.lower().startswith("recall")), None)
            mrr = r.get("mrr", r.get("MRR"))
            rows.append((mode, rec, mrr))
    for mode, rec, mrr in rows:
        say(f"  {mode:8} Recall@5 {rec}   MRR {mrr}")
    hy = next((r for r in rows if r[0] == "hybrid"), None)
    if hy and isinstance(hy[1], (int, float)):
        same = abs(hy[1] - REFERENCE["hybrid_recall5"]) < 0.03
        (ok if same else warn)(f"Gibrid Recall@5 = {hy[1]} (Bobur’da {REFERENCE['hybrid_recall5']}) — "
                               + ("bir xil" if same else "farq bor, Bobur’ga log faylni yuboring"))
        mark_done("eval", hybrid_recall5=hy[1], hybrid_mrr=hy[2])


# --------------------------------------------------------------------------- 15–16. node + frontend

NODE_DIRS = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs", TOOLS / "node"]


def node_ok(exe: Path | None) -> bool:
    if not exe:
        return False
    out = run([exe, "--version"], check=False, quiet=True)[1].strip()
    m = re.search(r"v(\d+)", out)
    return bool(m and int(m.group(1)) >= 18)


def find_node() -> Path | None:
    exe = find_exe("node.exe" if IS_WIN else "node", NODE_DIRS)
    return exe if node_ok(exe) else None


def npm(*args, cwd=FRONT, **kw):
    node = Path(STATE.get("node", {}).get("exe") or find_node() or "node")
    if node.exists():
        add_path(node.parent)                                          # npm scripts (vite, node --test) call `node` by name
    cli = node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    cmd = [node, cli, *args] if cli.exists() else [shutil.which("npm") or "npm", *args]
    return run(cmd, cwd=cwd, **kw)


def step_node():
    exe = find_node()
    if not exe and IS_WIN:
        winget("OpenJS.NodeJS.LTS")
        exe = find_node()
    if not exe and IS_WIN:
        say("Portativ Node.js LTS yuklab olinmoqda…")
        try:
            rel = next(r for r in http_json("https://nodejs.org/dist/index.json", timeout=30) if r.get("lts"))
            v = rel["version"]
            z = base.download(f"https://nodejs.org/dist/{v}/node-{v}-win-x64.zip", TOOLS / "downloads" / f"node-{v}-win-x64.zip")
            base.extract(z, TOOLS / "node", "node.exe")
        except Exception as exc:
            warn(f"Node.js yuklanmadi: {exc}")
        exe = find_node()
    if not exe:
        raise StepFailed("Node.js oʻrnatilmadi: https://nodejs.org (LTS) dan oʻrnating va qayta ishga tushiring.")
    add_path(exe.parent)
    v = run([exe, "--version"], check=False, quiet=True)[1].strip()
    ok(f"Node.js {v} ({exe})")
    mark_done("node", exe=str(exe), version=v)


def step_frontend():
    if not (FRONT / "package.json").exists():
        raise StepFailed(f"{FRONT} topilmadi — loyiha toʻliq koʻchirilmagan")
    lock = FRONT / "package-lock.json"
    for attempt, args in enumerate((["ci"] if lock.exists() else []) + ["install"], 1):
        code, _ = npm(*(args if isinstance(args, list) else [args]), "--no-audit", "--no-fund", check=False, timeout=1800)
        if code == 0:
            break
        warn(f"npm {args} ishlamadi ({attempt})")
    else:
        raise StepFailed("npm paketlari oʻrnatilmadi (internet? antivirus?)")
    code, out = npm("test", check=False, timeout=600)
    (ok if code == 0 else warn)("Frontend unit testlari " + ("oʻtdi" if code == 0 else "oʻtmadi — logga qarang"))
    npm("run", "build", timeout=1800)
    if not (DIST / "index.html").exists():
        raise StepFailed("frontend_idea\\dist\\index.html yaratilmadi")
    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    ok(f"Sayt yigʻildi: {DIST} ({fmt_mb(size)})")
    mark_done("frontend", dist=str(DIST))


# --------------------------------------------------------------------------- 17. LAN + optional SSH / autostart

def step_lan():
    if not IS_WIN:
        return warn("Faqat Windows uchun")
    ip = lan_ip()
    code, prof = ps("Get-NetConnectionProfile | ForEach-Object { \"$($_.Name)|$($_.NetworkCategory)\" }")
    profiles = [l.rsplit("|", 1) for l in prof.splitlines() if "|" in l]
    for name, cat in profiles:
        (ok if cat.strip() in ("Private", "DomainAuthenticated") else warn)(
            f"Tarmoq «{name.strip()}»: {cat.strip()}" + ("" if cat.strip() != "Public" else
            " — boshqa kompyuterlar ulana olmaydi. Sozlamalar → Tarmoq → shu Wi-Fi → «Private network» ni tanlang."))
    have = ps("Get-NetFirewallRule -DisplayName 'Modda *' -ErrorAction SilentlyContinue | Measure-Object | % Count")[1].strip()
    if have.isdigit() and int(have) >= 2:
        ok("Firewall qoidalari allaqachon bor (Modda 8080, 5174)")
    else:
        say("Windows Firewall’ga ruxsat qoʻshilmoqda — «Ha / Yes» tugmasini bosing (administrator soʻrovi)…", "y")
        # port rules + program rules for python.exe / node.exe (a «Cancel» in Windows' own pop-up would add a Block
        # rule for the program that overrides the port rule)
        progs = [(Path(sys.base_prefix) / "python.exe", API_PORT)]
        node = STATE.get("node", {}).get("exe")
        if node:
            progs.append((Path(node), DEV_PORT))
        prog_ps = "\n".join(
            f"Remove-NetFirewallRule -DisplayName 'Modda {pth.stem} {port}' -ErrorAction SilentlyContinue\n"
            f"Get-NetFirewallApplicationFilter -Program '{str(pth).replace(chr(39), chr(39) * 2)}' -ErrorAction SilentlyContinue | Get-NetFirewallRule | "
            f"Where-Object {{ $_.Action -eq 'Block' -and $_.Direction -eq 'Inbound' }} | Remove-NetFirewallRule\n"
            f"New-NetFirewallRule -DisplayName 'Modda {pth.stem} {port}' -Direction Inbound -Program '{str(pth).replace(chr(39), chr(39) * 2)}' "
            f"-Protocol TCP -LocalPort {port} -Action Allow -Profile Private | Out-Null"
            for pth, port in progs if pth.exists())
        code, out = ps(f"""
foreach ($p in @({API_PORT}, {DEV_PORT})) {{
  Remove-NetFirewallRule -DisplayName "Modda $p" -ErrorAction SilentlyContinue
  New-NetFirewallRule -DisplayName "Modda $p" -Direction Inbound -Protocol TCP -LocalPort $p -Action Allow -Profile Private | Out-Null
}}
{prog_ps}
Write-Output 'rules-ok'""", admin=True)
        if "rules-ok" in out:
            ok("Firewall: 8080 va 5174 portlari faqat shaxsiy (Private) tarmoqda ochildi")
        else:
            warn("Firewall qoidasi qoʻshilmadi (soʻrov rad etildi?). Saytni boshqa kompyuterdan ochishda Windows "
                 "«Allow access» deb soʻrasa — «Private networks» belgisini qoʻyib ruxsat bering.")
    ok(f"Bu noutbukning manzili: {ip or 'aniqlanmadi'}  →  boshqa kompyuterdan: http://{ip or '<IP>'}:{API_PORT}")
    mark_done("lan", ip=ip)


def step_ssh(key: str | None):
    if not IS_WIN:
        return warn("Faqat Windows uchun")
    pub = ""
    if key:
        p = Path(key).expanduser()
        pub = (p.read_text(encoding="utf-8").strip() if p.exists() else key.strip())
        if not re.match(r"^(ssh-(ed25519|rsa)|ecdsa-sha2-\S+) [A-Za-z0-9+/=]+", pub):
            raise StepFailed("--ssh-key: ochiq kalit (id_ed25519.pub) fayli yoki matni kerak")
    user = os.environ.get("USERNAME", "")
    home = Path.home()
    say("OpenSSH server yoqilmoqda — «Ha / Yes» tugmasini bosing (administrator soʻrovi, 1–5 daqiqa)…", "y")
    key_ps = ""
    if pub:
        k_ps, ud_ps, user_ps = pub.replace("'", "''"), str(home / ".ssh").replace("'", "''"), user.replace("'", "''")
        key_ps = f"""
$k = '{k_ps}'
$ud = '{ud_ps}'
New-Item -ItemType Directory -Force -Path $ud | Out-Null
$uf = Join-Path $ud 'authorized_keys'
if (-not (Test-Path $uf) -or -not (Select-String -Path $uf -SimpleMatch $k -Quiet)) {{ Add-Content -Path $uf -Value $k }}
$isAdmin = ($env:USERNAME -eq '{user_ps}') -and ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {{
  $af = 'C:\\ProgramData\\ssh\\administrators_authorized_keys'
  if (-not (Test-Path $af) -or -not (Select-String -Path $af -SimpleMatch $k -Quiet)) {{ Add-Content -Path $af -Value $k }}
  icacls $af /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null
}}
Write-Output 'key-ok'"""
    code, out = ps(f"""
$cap = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($cap.State -ne 'Installed') {{ Add-WindowsCapability -Online -Name $cap.Name | Out-Null }}
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
New-ItemProperty -Path 'HKLM:\\SOFTWARE\\OpenSSH' -Name DefaultShell -Value 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe' -PropertyType String -Force | Out-Null
Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -Profile Private | Out-Null
{key_ps}
if ((Get-Service sshd).Status -eq 'Running') {{ Write-Output 'sshd-ok' }}""", admin=True, timeout=1800)
    if "sshd-ok" not in out:
        raise StepFailed("OpenSSH server yoqilmadi (administrator soʻrovi rad etildimi?). Log: " + str(base.LOG_PATH))
    ip = lan_ip()
    ok(f"SSH tayyor: Bobur’ning kompyuteridan  ssh {user}@{ip or '<IP>'}"
       + ("  (kalit bilan, parolsiz)" if "key-ok" in out else "  (Windows parolingiz bilan)"))
    ok(f"Loyiha papkasi: {ROOT}   —   masalan:  ssh {user}@{ip or '<IP>'} \"cd '{ROOT}'; .\\update_modda.bat\"")
    mark_done("ssh", user=user, ip=ip, key=bool(pub))


def step_autostart():
    if not IS_WIN:
        return warn("Faqat Windows uchun")
    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    target = startup / "Modda server.bat"
    target.write_text(f'@echo off\r\nchcp 65001 >nul\r\ncd /d "{ROOT}"\r\nstart "Modda" /min cmd /c start_modda.bat --no-browser\r\n', encoding="utf-8")
    ok(f"Kompyuter yoqilib, siz kirganingizda server oʻzi ishga tushadi ({target}). Oʻchirish: shu faylni oʻchiring.")
    mark_done("autostart", file=str(target))


# --------------------------------------------------------------------------- 18. launchers

def bat(name: str, args: str, comment: str, pause: str = "if errorlevel 1 pause"):
    body = (f"@echo off\r\nrem {comment}\r\nchcp 65001 >nul\r\ncd /d \"%~dp0\"\r\n"
            f"if not exist \".venv\\Scripts\\python.exe\" (echo .venv yoq - avval scripts\\setup_server.bat ni ishga tushiring & pause & exit /b 1)\r\n"
            f"\".venv\\Scripts\\python.exe\" scripts\\setup_server.py {args} %*\r\n"
            f"{pause}\r\n")
    (ROOT / name).write_text(body, encoding="utf-8")


def step_launchers():
    bat("start_modda.bat", "--start", "Modda: Ollama + Qdrant + server (sayt: http://localhost:8080). Oynani yopsangiz server toʻxtaydi.")
    bat("start_dev.bat", "--start --dev", "Modda: server + Vite dev server (http://localhost:5174, kod oʻzgarsa sahifa yangilanadi)")
    bat("update_modda.bat", "--update", "Modda: git pull + paketlar + sayt yigʻish", "if not defined SSH_CONNECTION pause")
    bat("status_modda.bat", "--status", "Modda: holat", "if not defined SSH_CONNECTION pause")
    ok("Yaratildi: start_modda.bat, start_dev.bat, update_modda.bat, status_modda.bat (loyiha papkasida)")
    mark_done("launchers")


# --------------------------------------------------------------------------- services (start / verify / status)

def ensure_services():
    if not base.ollama_version():
        exe = base.find_ollama()
        if not exe or not base.start_ollama(exe):
            raise StepFailed("Ollama ishga tushmadi")
    if not base.qdrant_version() and not base.start_qdrant():
        raise StepFailed("Qdrant ishga tushmadi")


def server_env() -> dict:
    env = base.child_env()
    if (DIST / "index.html").exists():
        env["MODDA_WEB_DIST"] = str(DIST)
    return env


def wait_ready(seconds=120) -> dict | None:
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            h = http_json(f"http://127.0.0.1:{API_PORT}/health", timeout=20)
            if h.get("ready") or (h.get("services", {}).get("ollama", {}).get("ok") and h.get("services", {}).get("qdrant", {}).get("ok")):
                return h
        except Exception:
            pass
        time.sleep(2)
    return None


def step_verify():
    ensure_services()
    if port_busy(API_PORT):
        warn(f"Port {API_PORT} band — server allaqachon ishlayaptimi? Oʻsha bilan tekshiramiz.")
        proc = None
    else:
        proc = base.start_detached([VPY, "-m", "modda", "serve", "--host", "127.0.0.1", "--port", API_PORT],
                                   REPORTS / "verify-serve.log", env=server_env())
    try:
        h = wait_ready()
        if not h:
            raise StepFailed(f"Server javob bermadi. Log: {REPORTS / 'verify-serve.log'}")
        ok(f"/health: {h.get('articles'):,} modda, {h.get('chunks'):,} boʻlak, dense {h.get('dense_indexed'):,}; "
           f"Ollama {'✓' if h['services']['ollama']['ok'] else '✗'}  Qdrant {'✓' if h['services']['qdrant']['ok'] else '✗'}")
        site = urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/", timeout=20).read(2000).decode("utf-8", "replace")
        (ok if "<html" in site.lower() else warn)("Sayt (frontend_idea/dist) server orqali ochiladi" if "<html" in site.lower()
                                                   else "Sayt topilmadi — frontend qadamini qayta ishga tushiring")
        q = "Har yilgi mehnat taʼtili necha kun?"
        say(f"Haqiqiy savol: «{q}» (qwen3:8b, GPU)…")
        t0 = time.time()
        a = http_json(f"http://127.0.0.1:{API_PORT}/ask", {"question": q}, timeout=900)
        dt = time.time() - t0
        first = (a.get("answer") or [{}])[0].get("text", "") if not a.get("unknown") else "(Bilmayman)"
        score = (a.get("score") or {}).get("score")
        ok(f"Javob {dt:.1f} s da: {first[:140]}")
        ok(f"Manbalar: {len(a.get('sources') or [])}, manbaga moslik bahosi: {score}")
        if dt > 60:
            warn("Javob sekin (> 60 s) — model GPU’da ishlamayotgan boʻlishi mumkin (status_modda.bat)")
        mark_done("verify", answer_s=round(dt, 1), score=score)
    finally:
        if proc:
            proc.terminate()


def cmd_status():
    st = stats()
    ip = lan_ip()
    rows = [("Ollama", base.ollama_version() or "ishlamayapti"), ("Qdrant", base.qdrant_version() or "ishlamayapti"),
            ("Server :8080", "ishlayapti" if port_busy(API_PORT) else "ishlamayapti"),
            ("Dev :5174", "ishlayapti" if port_busy(DEV_PORT) else "—"),
            ("Moddalar", f"{st.get('articles', '?'):,}" if isinstance(st.get("articles"), int) else "?"),
            ("Boʻlaklar / dense", f"{st.get('chunks', '?')} / {st.get('chunks_indexed', '?')}"),
            ("Qdrant nuqtalari", qdrant_points()), ("Sayt (dist)", "bor" if (DIST / "index.html").exists() else "yoʻq"),
            ("Manzil", f"http://localhost:{API_PORT}  |  http://{ip}:{API_PORT}" if ip else f"http://localhost:{API_PORT}")]
    try:
        rows.append(("Modellar", ", ".join(m["name"] for m in http_json(f"{OLLAMA}/api/tags")["models"])))
        rows.append(("GPU’da hozir", ", ".join(f"{m['name']} {fmt_mb(m.get('size_vram', 0))}" for m in http_json(f"{OLLAMA}/api/ps")["models"]) or "—"))
    except Exception:
        pass
    gpu = base.nvidia_info()
    rows.append(("GPU", gpu or "nvidia-smi yoʻq"))
    for k, v in rows:
        print(f"  {k:18} {v}")
    return 0


def cmd_start(dev: bool, browser: bool):
    ensure_services()
    ip = lan_ip()
    if port_busy(API_PORT):
        warn(f"Port {API_PORT} band — server allaqachon ishlayapti (boshqa oynada?).")
        return 1
    env = server_env()
    if "MODDA_WEB_DIST" not in env and not dev:
        warn("frontend_idea\\dist yoʻq — avval: update_modda.bat (yoki start_dev.bat)")
    cmd = [VPY, "-m", "modda", "serve", "--host", "0.0.0.0", "--port", str(API_PORT)]
    url = f"http://localhost:{DEV_PORT if dev else API_PORT}"
    print(f"\n{C['b']}{C['g']}Modda ishga tushmoqda{C['0']}\n  shu kompyuterda:   {url}")
    if ip:
        print(f"  boshqa kompyuterdan (bir xil Wi-Fi):   http://{ip}:{DEV_PORT if dev else API_PORT}")
    print(f"{C['d']}  Toʻxtatish: Ctrl+C yoki oynani yoping.{C['0']}\n")
    if dev:
        fh = open(REPORTS / "serve.log", "ab")                         # shares this console: closing the window stops it too
        server = subprocess.Popen([str(c) for c in cmd], cwd=ROOT, env=env, stdout=fh, stderr=fh, stdin=subprocess.DEVNULL)
        try:
            if browser:
                subprocess.Popen(["cmd", "/c", "start", "", url], shell=False) if IS_WIN else None
            return npm("run", "dev", check=False)[0]
        finally:
            server.terminate()
    if browser:
        def later():
            if wait_ready(90) and IS_WIN:
                subprocess.Popen(["cmd", "/c", "start", "", url])
        import threading
        threading.Thread(target=later, daemon=True).start()
    try:
        return subprocess.call([str(c) for c in cmd], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 0


def cmd_update():
    git = find_git()
    if git and (ROOT / ".git").exists():
        code, out = run([git, "-C", ROOT, "pull", "--ff-only"], check=False)
        if code != 0:
            bad("git pull oʻtmadi (shu kompyuterda oʻzgartirilgan fayllar bormi? `git status`)")
            return 1
    else:
        warn("git yoki .git yoʻq — kodni yangilamasdan davom etamiz")
    run([VPY, "-m", "pip", "install", "-e", ".[dev,api]"], check=False)
    lock = FRONT / "package-lock.json"
    if not lock.exists() or npm("ci", "--no-audit", "--no-fund", check=False, timeout=1800)[0] != 0:
        npm("install", "--no-audit", "--no-fund", check=False, timeout=1800)
    code, _ = npm("run", "build", check=False, timeout=1800)
    (ok if code == 0 else bad)("Sayt qayta yigʻildi" if code == 0 else "npm run build xato bilan tugadi")
    ok("Tayyor. Server ishlayotgan boʻlsa — oynasini yopib, start_modda.bat ni qayta ishga tushiring.")
    return 0 if code == 0 else 1


# --------------------------------------------------------------------------- main

def write_status():
    st = stats()
    data = {"updated": datetime.now().isoformat(timespec="seconds"), "root": str(ROOT), "ip": lan_ip(),
            "gpu": base.nvidia_info(), "db": st, "qdrant_points": qdrant_points(), "reference_bobur": REFERENCE,
            "steps": {k: v for k, v in STATE.items()}}
    (REPORTS / "server-status.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Modda: GPU noutbukni loyiha serveriga aylantirish (Bobur’dagi holat bilan bir xil)")
    ap.add_argument("--only", help="faqat shu qadamlar, vergul bilan: " + ",".join(STEPS + OPTIONAL))
    ap.add_argument("--from", dest="start_step", choices=STEPS, help="shu qadamdan boshlab")
    ap.add_argument("--snapshot", help="snapshot fayli (modda-*.snapshot)")
    ap.add_argument("--no-bakeoff-models", action="store_true", help="gemma4:e4b va Llama-3.1-8B-Uz ni yuklamaslik")
    ap.add_argument("--reranker", action="store_true", help="reranker uchun PyTorch (CUDA) + sentence-transformers")
    ap.add_argument("--ssh", action="store_true", help="OpenSSH server: Bobur shu noutbukni oʻz kompyuteridan boshqaradi")
    ap.add_argument("--ssh-key", help="Bobur’ning ochiq kaliti (id_ed25519.pub fayli yoki matni)")
    ap.add_argument("--autostart", action="store_true", help="kirganda serverni oʻzi ishga tushirish")
    ap.add_argument("--fresh", action="store_true", help="avvalgi holatni unutish (fayllar oʻchirilmaydi)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--start", action="store_true", help="xizmatlar + server")
    ap.add_argument("--dev", action="store_true", help="--start bilan: Vite dev server ham")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--update", action="store_true", help="git pull + paketlar + sayt")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status:
        return cmd_status()
    if a.start:
        try:
            return cmd_start(a.dev, not a.no_browser)
        except StepFailed as exc:
            bad(str(exc))
            return 1
    if a.update:
        return cmd_update()
    if a.list:
        for s in STEPS + OPTIONAL:
            print(f"  {s:10} {'✓ ' + STATE[s]['done'] if s in STATE else ''}")
        return 0
    if a.fresh:
        STATE.clear()
        base.save_state(STATE)

    steps = list(STEPS)
    if a.start_step:
        steps = steps[steps.index(a.start_step):]
    extra = [s for s, on in (("reranker", a.reranker), ("ssh", a.ssh or bool(a.ssh_key)), ("autostart", a.autostart)) if on]
    steps += extra                                                     # optional steps last: they never block verify
    if a.only:
        wanted = [s.strip() for s in a.only.split(",")]
        unknown = set(wanted) - set(STEPS + OPTIONAL)
        if unknown:
            ap.error(f"nomaʼlum qadam: {', '.join(unknown)}")
        steps = [s for s in STEPS + OPTIONAL if s in wanted]

    if IS_WIN:
        base.keep_awake()                                              # also with --from / --only (index can take hours)
    print(f"{C['b']}{C['c']}Modda — GPU noutbukni server qilish{C['0']}   loyiha: {ROOT}")
    print(f"{C['d']}Log: {base.LOG_PATH}{C['0']}\n")
    fns = {"system": step_system, "git": step_git, "python": base.step_python, "ollama": base.step_ollama,
           "models": lambda: step_models(not a.no_bakeoff_models), "corpus": base.step_corpus, "qdrant": base.step_qdrant,
           "env": base.step_env, "ingest": step_ingest, "numbers": base.step_numbers, "chunk": base.step_chunk,
           "rss": step_rss, "index": lambda: step_index(a.snapshot), "eval": step_eval, "node": step_node,
           "frontend": step_frontend, "lan": step_lan, "launchers": step_launchers, "verify": step_verify,
           "reranker": step_reranker, "ssh": lambda: step_ssh(a.ssh_key), "autostart": step_autostart}
    timings = []
    for i, name in enumerate(steps, 1):
        print()
        say(f"━━ [{i}/{len(steps)}] {name} ━━", "b")
        t0 = time.time()
        try:
            fns[name]()
            timings.append((name, time.time() - t0, "ok"))
            ok(f"{name} tugadi ({fmt_dur(time.time() - t0)})")
        except KeyboardInterrupt:
            print()
            warn("Toʻxtatildi. Qayta ishga tushiring — tayyor qadamlar oʻtkazib yuboriladi.")
            timings.append((name, time.time() - t0, "toʻxtatildi"))
            base.summary(timings)
            return 130
        except StepFailed as exc:
            if name in OPTIONAL:
                warn(f"{name} (ixtiyoriy) oʻtmadi: {exc}")
                timings.append((name, time.time() - t0, "oʻtmadi"))
                continue
            bad(f"{name}: {exc}")
            timings.append((name, time.time() - t0, "XATO"))
            base.summary(timings)
            write_status()
            print(f"\n{C['y']}Tuzatgandan keyin qayta ishga tushiring. Yordam kerak boʻlsa, Bobur’ga shu faylni yuboring:{C['0']}\n  {base.LOG_PATH}")
            return 1
        except Exception as exc:
            import traceback
            base.log(traceback.format_exc())
            bad(f"{name}: kutilmagan xato: {exc!r}")
            timings.append((name, time.time() - t0, "XATO"))
            base.summary(timings)
            write_status()
            print(f"\nBobur’ga shu faylni yuboring: {base.LOG_PATH}")
            return 1
    base.summary(timings)
    write_status()
    st = stats()
    ip = lan_ip()
    print(f"\n{C['b']}{C['g']}TAYYOR!{C['0']}  Bobur’dagi holat bilan solishtirish:")
    for label, have, want in (("moddalar", st.get("articles"), REFERENCE["articles"]), ("boʻlaklar", st.get("chunks"), REFERENCE["chunks"]),
                              ("dense indeks", st.get("chunks_indexed"), REFERENCE["chunks"])):
        same = isinstance(have, int) and have == want
        say(f"  {label:13} {have!s:>9}   Bobur’da {want:,}   {'✓' if same else '≠'}", "g" if same else "y")
    print(f"\nIshga tushirish:  {ROOT / 'start_modda.bat'}   →  http://localhost:{API_PORT}"
          + (f"   (boshqa kompyuterdan: http://{ip}:{API_PORT})" if ip else ""))
    print(f"Holat: {REPORTS / 'server-status.json'}  — shu faylni Bobur’ga yuboring.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
