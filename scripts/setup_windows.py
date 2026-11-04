"""Modda — one-command setup for a Windows computer with an NVIDIA GPU.

    python scripts\\setup_windows.py            (or double-click scripts\\setup_windows.bat)

It does everything itself and checks the result of every command; when one way fails it tries the next:
  1. checks the computer (Windows, Python, disk, RAM, NVIDIA GPU and driver)
  2. .venv + project packages (pip → pip --no-cache-dir → plain install)
  3. Ollama (already running → found on disk → winget → official installer → portable zip) and starts it
  4. bge-m3 (+ qwen3:8b) models (Ollama API with progress → `ollama pull`), checks that the GPU is used
  5. corpus at a fixed revision (hf → huggingface-cli → huggingface_hub → direct HTTPS with resume), checksum
  6. Qdrant v1.20.0 (already running → Docker → portable Windows build) and starts it
  7. .env (SQLite, no passwords needed)
  8. ingest → chunk → fix-numbers → bench-embed → full bge-m3 index → eval
  9. snapshot of the finished index in data\\exports\\ — the two files to send to Bobur

Every step prints its time; everything also goes to data\\reports\\setup-<date>.log. Safe to stop (Ctrl+C) and
run again: finished steps are recognised and skipped, indexing continues from where it stopped.

Options:  --skip-llm  (no qwen3:8b)   --only STEP[,STEP]   --from STEP   --no-index   --no-export   --list
Standard library only: it runs before anything is installed.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- constants

ROOT = Path(__file__).resolve().parents[1]
IS_WIN = os.name == "nt"
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")
VBIN = VPY.parent
DATA = ROOT / "data"
REPORTS = DATA / "reports"
TOOLS = ROOT / "tools"
STATE_FILE = REPORTS / "setup-state.json"

DATASET = "sukhrobnurali/uzbek-legal-corpus"
REVISION = "c69bbd5e1d645084194696d77f46607aa8d51a9f"
CORPUS_DIR = DATA / "raw" / "hf"
CORPUS_FILES = ["articles/train-00000-of-00001.parquet"]

OLLAMA = "http://127.0.0.1:11434"
QDRANT = "http://127.0.0.1:6333"
QDRANT_VERSION = "1.20.0"
QDRANT_ZIP = f"https://github.com/qdrant/qdrant/releases/download/v{QDRANT_VERSION}/qdrant-x86_64-pc-windows-msvc.zip"
OLLAMA_SETUP = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_ZIP = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"

EMBED_MODEL = "bge-m3"
LLM_MODEL = "qwen3:8b"
UA = "modda-setup/1.0"
MIN_DENSE_RATE = 15.0          # chunks/s; below this a full bge-m3 index would take > ~3.5 h

STEPS = ["system", "python", "ollama", "models", "corpus", "qdrant", "env", "ingest", "chunk",
         "numbers", "bench", "index", "eval", "export"]

# --------------------------------------------------------------------------- console + log

if IS_WIN:
    os.system("")                                     # turns on ANSI colours in the Windows console
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

C = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "c": "\033[36m", "b": "\033[1m", "d": "\033[2m", "0": "\033[0m"}
REPORTS.mkdir(parents=True, exist_ok=True)
LOG_PATH = REPORTS / f"setup-{datetime.now():%Y%m%d-%H%M%S}.log"
_log = open(LOG_PATH, "a", encoding="utf-8")
T_START = time.time()
_ANSI = re.compile(r"\033\[[0-9;]*m")


def log(text: str) -> None:
    _log.write(f"{datetime.now():%H:%M:%S} {_ANSI.sub('', text)}\n")
    _log.flush()


def say(text: str = "", color: str = "") -> None:
    elapsed = time.time() - T_START
    stamp = f"{C['d']}[{datetime.now():%H:%M:%S} +{fmt_dur(elapsed)}]{C['0']} "
    print(stamp + (C[color] if color else "") + text + (C["0"] if color else ""), flush=True)
    log(text)


def ok(text):   say("✓ " + text, "g")
def warn(text): say("! " + text, "y")
def bad(text):  say("✗ " + text, "r")


def fmt_dur(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{s % 3600 // 60:02d}m"


def fmt_mb(n: float) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"


class StepFailed(Exception):
    pass


# --------------------------------------------------------------------------- state

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


STATE = load_state()


def mark_done(step: str, **info) -> None:
    STATE[step] = {"done": datetime.now().isoformat(timespec="seconds"), **info}
    save_state(STATE)


# --------------------------------------------------------------------------- running commands

def child_env() -> dict:
    env = dict(os.environ)
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
               PIP_DISABLE_PIP_VERSION_CHECK="1", HF_HUB_DISABLE_TELEMETRY="1")
    if IS_WIN:
        env["PATH"] = os.pathsep.join([str(VBIN), str(ollama_dirs()[0]), env.get("PATH", "")])
    return env


def run(cmd, *, check=True, timeout=None, quiet=False, cwd=ROOT, env=None) -> tuple[int, str]:
    """Runs a command, shows its output live (progress bars included) and returns (exit code, output)."""
    cmd = [str(c) for c in cmd]
    say(f"$ {' '.join(cmd)}", "d")
    t0 = time.time()
    try:
        p = subprocess.Popen(cmd, cwd=cwd, env=env or child_env(), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        if check:
            raise StepFailed(f"buyruq topilmadi: {cmd[0]}") from exc
        return 127, str(exc)
    out: list[str] = []

    def pump():
        buf = b""
        while True:
            ch = p.stdout.read1(4096) if hasattr(p.stdout, "read1") else p.stdout.read(1)
            if not ch:
                break
            buf += ch
            while True:
                m = re.search(rb"[\r\n]", buf)
                if not m:
                    break
                line, sep, buf = buf[:m.start()], buf[m.start():m.end()], buf[m.end():]
                text = line.decode("utf-8", errors="replace")
                if sep == b"\r":                     # progress line: overwrite in place, do not log every tick
                    if not quiet:
                        sys.stdout.write("\r    " + text[:150].ljust(80))
                        sys.stdout.flush()
                    out.append(text)
                else:
                    if not quiet:
                        sys.stdout.write("\r    " + text + "\n")
                        sys.stdout.flush()
                    log("    " + text)
                    out.append(text)
        if buf:
            text = buf.decode("utf-8", errors="replace")
            if not quiet:
                print("    " + text)
            log("    " + text)
            out.append(text)

    th = threading.Thread(target=pump, daemon=True)
    th.start()
    try:
        code = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        code = -9
        out.append(f"timeout after {timeout}s")
    except KeyboardInterrupt:
        p.terminate()
        raise
    th.join(5)
    say(f"  (chiqish kodi {code}, {fmt_dur(time.time() - t0)})", "d")
    text = "\n".join(out)
    if check and code != 0:
        raise StepFailed(f"`{' '.join(cmd[:4])}…` xato bilan tugadi (kod {code}). Oxirgi qatorlar:\n"
                         + "\n".join(out[-8:]))
    return code, text


def start_detached(cmd, log_file: Path, env=None) -> subprocess.Popen:
    """Starts a server that keeps running after this script ends."""
    say(f"$ {' '.join(map(str, cmd))}  (fon rejimida, log: {log_file})", "d")
    fh = open(log_file, "ab")
    flags = 0
    if IS_WIN:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008 | 0x08000000   # DETACHED | NO_WINDOW
    return subprocess.Popen([str(c) for c in cmd], cwd=ROOT, env=env or child_env(), stdout=fh, stderr=fh,
                            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)


# --------------------------------------------------------------------------- HTTP

def http_json(url: str, data=None, timeout=10, method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def alive(url: str, timeout=3) -> bool:
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()
        return True
    except Exception:
        return False


def wait_for(url: str, seconds: int, what: str) -> bool:
    t0 = time.time()
    while time.time() - t0 < seconds:
        if alive(url):
            ok(f"{what} javob beryapti ({fmt_dur(time.time() - t0)})")
            return True
        time.sleep(1.5)
    return False


class Progress:
    def __init__(self, label: str, total: int, start: int = 0):
        self.label, self.total, self.done, self.t0, self.start, self.last = label, total, start, time.time(), start, 0.0

    def update(self, done: int, force=False):
        self.done = done
        now = time.time()
        if not force and now - self.last < 0.5:
            return
        self.last = now
        dt = max(now - self.t0, 1e-6)
        speed = (done - self.start) / dt
        if self.total:
            eta = (self.total - done) / speed if speed > 0 else 0
            pct = 100 * done / self.total
            bar = "█" * int(pct / 4) + "░" * (25 - int(pct / 4))
            msg = f"{self.label} {bar} {pct:5.1f}%  {fmt_mb(done)}/{fmt_mb(self.total)}  {speed / 1e6:.1f} MB/s  ETA {fmt_dur(eta)}"
        else:
            msg = f"{self.label} {fmt_mb(done)}  {speed / 1e6:.1f} MB/s"
        sys.stdout.write("\r    " + msg.ljust(100))
        sys.stdout.flush()

    def finish(self):
        self.update(self.done, force=True)
        print()
        log(f"    {self.label}: {fmt_mb(self.done)} in {fmt_dur(time.time() - self.t0)}")


def download(url: str, dest: Path, *, sha256: str | None = None, tries: int = 4) -> Path:
    """Resumable download with progress, speed and ETA; checks the sha256 when it is known."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, tries + 1):
        have = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            say(f"Yuklab olinmoqda ({attempt}/{tries}): {url}" + (f"  [{fmt_mb(have)} dan davom]" if have else ""))
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                if have and r.status != 206:          # server ignored Range: start again
                    have = 0
                total = int(r.headers.get("Content-Length") or 0) + have
                bar = Progress(dest.name, total, have)
                with open(part, "ab" if have else "wb") as fh:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
                        bar.update(bar.done + len(chunk))
                bar.finish()
            if total and part.stat().st_size < total:
                raise IOError(f"toʻliq emas: {part.stat().st_size} / {total}")
            if sha256:
                got = file_sha256(part)
                if got != sha256:
                    part.unlink()
                    raise IOError(f"sha256 mos emas ({got[:12]}… ≠ {sha256[:12]}…), qaytadan")
                ok("sha256 toʻgʻri")
            part.replace(dest)
            return dest
        except urllib.error.HTTPError as exc:
            if exc.code == 416:                       # already complete
                part.replace(dest)
                return dest
            warn(f"HTTP {exc.code}: {exc.reason}")
        except Exception as exc:
            print()
            warn(f"yuklab olish uzildi: {exc}")
        time.sleep(min(30, 3 * attempt))
    raise StepFailed(f"{url} yuklab olinmadi ({tries} urinish)")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- 1. system

def step_system():
    say(f"OS: {platform.platform()}  |  Python {platform.python_version()} ({sys.executable})")
    if not IS_WIN:
        warn("Bu skript Windows uchun yozilgan; boshqa tizimda ham ishlaydi, lekin Ollama/Qdrant’ni oʻzingiz oʻrnating.")
    if sys.version_info < (3, 10):
        raise StepFailed("Python 3.10 yoki yangiroq kerak: https://www.python.org/downloads/ "
                         "(oʻrnatishda «Add python.exe to PATH» belgisini qoʻying) yoki scripts\\setup_windows.bat")
    free = shutil.disk_usage(ROOT).free
    (ok if free > 25e9 else warn)(f"Diskda boʻsh joy: {fmt_mb(free)} (kerak ≈ 15–20 GB: modellar, korpus, indeks)")
    if free < 12e9:
        raise StepFailed("Diskda joy yetmaydi (kamida 12 GB kerak). Joy boʻshatib, qayta ishga tushiring.")
    ram = total_ram()
    if ram:
        (ok if ram >= 15e9 else warn)(f"RAM: {fmt_mb(ram)}")
    gpu = nvidia_info()
    if gpu:
        ok(f"GPU: {gpu}")
        m = re.search(r"driver (\d+)\.(\d+)", gpu)
        if m and (int(m.group(1)), int(m.group(2))) < (551, 61):
            warn("NVIDIA drayveri eski (Ollama 551.61+ talab qiladi). Yangilang: https://www.nvidia.com/Download/index.aspx "
                 "— aks holda model CPU’da ishlaydi (juda sekin).")
    else:
        warn("nvidia-smi topilmadi: NVIDIA GPU yoki drayver yoʻq. Skript ishlaydi, lekin indeks CPU’da sekin boʻladi.")
    if IS_WIN:
        keep_awake()
    mark_done("system", gpu=gpu, ram=ram)


def total_ram() -> int | None:
    if IS_WIN:
        class MEMSTAT(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        st = MEMSTAT()
        st.len = ctypes.sizeof(MEMSTAT)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return st.total
        return None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def nvidia_info() -> str | None:
    exe = shutil.which("nvidia-smi") or (r"C:\Windows\System32\nvidia-smi.exe" if IS_WIN else None)
    if not exe or not Path(exe).exists():
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return None
    if not out:
        return None
    name, mem, drv = [x.strip() for x in out.splitlines()[0].split(",")]
    return f"{name}, {mem}, driver {drv}"


def keep_awake():
    """Stops Windows from sleeping while the script runs (the index can take an hour)."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # CONTINUOUS | SYSTEM_REQUIRED
        ok("Skript ishlayotganda kompyuter uyquga ketmaydi")
    except Exception:
        pass


# --------------------------------------------------------------------------- 2. python packages

def venv_ok() -> bool:
    if not VPY.exists():
        return False
    code, _ = run([VPY, "-c", "import modda, requests, numpy, pyarrow, huggingface_hub; print('ok')"],
                  check=False, quiet=True)
    return code == 0


def step_python():
    if venv_ok():
        ok("Virtual muhit va paketlar allaqachon tayyor (.venv)")
        return mark_done("python")
    if not VPY.exists():
        say("Virtual muhit yaratilmoqda (.venv)…")
        code, out = run([sys.executable, "-m", "venv", VENV], check=False)
        if code != 0 or not VPY.exists():
            warn("venv yaratilmadi, virtualenv bilan urinib koʻramiz")
            run([sys.executable, "-m", "pip", "install", "--user", "virtualenv"])
            run([sys.executable, "-m", "virtualenv", VENV])
    run([VPY, "-m", "ensurepip", "--upgrade"], check=False, quiet=True)
    run([VPY, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=False)
    attempts = [
        [VPY, "-m", "pip", "install", "-e", ".[dev,api]", "huggingface_hub[cli]"],
        [VPY, "-m", "pip", "install", "--no-cache-dir", "-e", ".[dev,api]", "huggingface_hub[cli]"],
        [VPY, "-m", "pip", "install", "--no-cache-dir", "-e", ".", "huggingface_hub"],
        [VPY, "-m", "pip", "install", "--no-build-isolation", "-e", ".", "huggingface_hub"],
        [VPY, "-m", "pip", "install", "--no-cache-dir", "requests", "numpy", "pyarrow", "psycopg[binary]",
         "huggingface_hub", "pytest", "fastapi", "uvicorn"],
    ]
    for i, cmd in enumerate(attempts, 1):
        say(f"Paketlar oʻrnatilmoqda (usul {i}/{len(attempts)})…")
        code, out = run(cmd, check=False)
        if code == 0:
            break
        warn(f"usul {i} ishlamadi")
    if not venv_ok() and VPY.exists():
        # last resort for the final variant: make `import modda` work without an editable install
        site = run([VPY, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], quiet=True)[1].strip()
        Path(site.splitlines()[-1], "modda-src.pth").write_text(str(ROOT / "src"), encoding="utf-8")
    if not venv_ok():
        raise StepFailed("Python paketlari oʻrnatilmadi — yuqoridagi xatoni koʻring (internet? antivirus?).")
    run([VPY, "-m", "modda", "--help"], quiet=True)
    ok("Paketlar oʻrnatildi va import qilindi")
    mark_done("python")


# --------------------------------------------------------------------------- 3. Ollama

def ollama_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return [local / "Programs" / "Ollama", TOOLS / "ollama", Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Ollama"]


def find_ollama() -> Path | None:
    exe = shutil.which("ollama")
    if exe:
        return Path(exe)
    for d in ollama_dirs():
        p = d / ("ollama.exe" if IS_WIN else "ollama")
        if p.exists():
            return p
    return None


def ollama_version() -> str | None:
    try:
        return http_json(f"{OLLAMA}/api/version", timeout=3)["version"]
    except Exception:
        return None


def start_ollama(exe: Path) -> bool:
    if ollama_version():
        return True
    env = child_env()
    env.setdefault("OLLAMA_HOST", "127.0.0.1:11434")
    start_detached([exe, "serve"], REPORTS / "ollama-serve.log", env=env)
    return wait_for(f"{OLLAMA}/api/version", 90, "Ollama")


def step_ollama():
    v = ollama_version()
    if v:
        ok(f"Ollama allaqachon ishlayapti: v{v}")
        return mark_done("ollama", version=v)
    exe = find_ollama()
    if exe:
        ok(f"Ollama topildi: {exe}")
    elif IS_WIN:
        exe = install_ollama()
    else:
        raise StepFailed("Ollama yoʻq: https://ollama.com/download")
    if not start_ollama(exe):
        warn("Ollama ishga tushmadi; portativ versiya bilan urinib koʻramiz")
        exe = install_ollama_zip()
        if not start_ollama(exe):
            raise StepFailed(f"Ollama ishga tushmadi. Logga qarang: {REPORTS / 'ollama-serve.log'}")
    v = ollama_version()
    ok(f"Ollama v{v} ishlayapti ({exe})")
    mark_done("ollama", version=v, exe=str(exe))


def install_ollama() -> Path:
    if shutil.which("winget"):
        say("Ollama winget orqali oʻrnatilmoqda…")
        code, out = run(["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent",
                         "--accept-package-agreements", "--accept-source-agreements"], check=False, timeout=1800)
        exe = find_ollama()
        if exe:
            return exe
        warn("winget orqali boʻlmadi")
    say("Rasmiy oʻrnatuvchi yuklab olinmoqda (administrator huquqi kerak emas)…")
    try:
        setup = download(OLLAMA_SETUP, TOOLS / "downloads" / "OllamaSetup.exe")
        run([setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], check=False, timeout=1800)
        for _ in range(30):                           # the installer may finish a little after it exits
            exe = find_ollama()
            if exe:
                return exe
            time.sleep(2)
        warn("Oʻrnatuvchidan keyin ollama.exe topilmadi")
    except StepFailed as exc:
        warn(str(exc))
    return install_ollama_zip()


def install_ollama_zip() -> Path:
    target = TOOLS / "ollama"
    exe = target / "ollama.exe"
    if exe.exists():
        return exe
    say("Portativ Ollama (zip, ≈ 1–2 GB, NVIDIA kutubxonalari bilan) yuklab olinmoqda…")
    z = download(OLLAMA_ZIP, TOOLS / "downloads" / "ollama-windows-amd64.zip")
    extract(z, target, exe.name)
    if not exe.exists():
        raise StepFailed("ollama.exe zip ichida topilmadi")
    return exe


def extract(z: Path, target: Path, exe_name: str | None = None):
    """Unzips; when the program sits in a sub-folder of the zip, moves that folder's content up."""
    say(f"Ochilmoqda: {z.name} → {target}")
    t0 = time.time()
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(z) as zf:
            zf.extractall(target)
    except zipfile.BadZipFile:
        z.unlink(missing_ok=True)
        raise StepFailed(f"{z.name} buzilgan (oʻchirildi) — skriptni qayta ishga tushiring")
    if exe_name and not (target / exe_name).exists():
        found = next(iter(target.rglob(exe_name)), None)
        if found:
            for item in found.parent.iterdir():
                shutil.move(str(item), str(target / item.name))
    ok(f"ochildi ({fmt_dur(time.time() - t0)})")


# --------------------------------------------------------------------------- 4. models

def have_model(name: str) -> bool:
    try:
        tags = http_json(f"{OLLAMA}/api/tags")["models"]
    except Exception:
        return False
    full = name if ":" in name else name + ":latest"
    return any(m["name"] in (name, full) for m in tags)


def pull(name: str):
    if have_model(name):
        return ok(f"{name} allaqachon yuklangan")
    say(f"{name} yuklab olinmoqda…")
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(f"{OLLAMA}/api/pull", data=json.dumps({"model": name, "stream": True}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": UA})
            bars: dict[str, Progress] = {}
            with urllib.request.urlopen(req, timeout=600) as r:
                for raw in r:
                    ev = json.loads(raw)
                    if ev.get("error"):
                        raise IOError(ev["error"])
                    dg = ev.get("digest")
                    if dg and ev.get("total"):
                        b = bars.get(dg) or bars.setdefault(dg, Progress(f"{name} {dg[7:19]}", ev["total"], ev.get("completed", 0)))
                        b.update(ev.get("completed", 0))
                        if ev.get("completed") == ev["total"] and not getattr(b, "closed", False):
                            b.finish()
                            b.closed = True
                    elif ev.get("status") and not dg:
                        log(f"    {ev['status']}")
            if have_model(name):
                return ok(f"{name} tayyor")
        except Exception as exc:
            print()
            warn(f"API orqali yuklash uzildi ({attempt}/3): {exc}")
            time.sleep(5 * attempt)
    exe = find_ollama()
    if exe:
        say("`ollama pull` buyrugʻi bilan urinib koʻramiz…")
        for attempt in range(1, 3):
            if run([exe, "pull", name], check=False, timeout=7200)[0] == 0 and have_model(name):
                return ok(f"{name} tayyor")
    raise StepFailed(f"{name} modeli yuklanmadi (internetni tekshiring va skriptni qayta ishga tushiring)")


def step_models(skip_llm: bool):
    if not ollama_version():
        step_ollama()
    pull(EMBED_MODEL)
    if not skip_llm:
        try:
            pull(LLM_MODEL)
        except StepFailed as exc:
            warn(f"{exc} — indeks uchun shart emas, davom etamiz")
    say("bge-m3 sinab koʻrilmoqda va GPU tekshirilmoqda…")
    t0 = time.time()
    res = http_json(f"{OLLAMA}/api/embed", {"model": EMBED_MODEL, "input": ["Mehnat kodeksi 131-modda"], "keep_alive": "30m"},
                    timeout=600)
    dim = len(res["embeddings"][0])
    if dim != 1024:
        raise StepFailed(f"bge-m3 vektor oʻlchami {dim} (1024 boʻlishi kerak)")
    ok(f"bge-m3 ishlayapti: oʻlcham {dim}, {time.time() - t0:.1f} s (birinchi chaqiruv modelni yuklaydi)")
    vram = 0
    try:
        for m in http_json(f"{OLLAMA}/api/ps")["models"]:
            if m["name"].startswith(EMBED_MODEL):
                vram = m.get("size_vram", 0)
    except Exception:
        pass
    if vram:
        ok(f"Model GPU’da: {fmt_mb(vram)} VRAM")
    else:
        warn("Model CPU’da ishlayapti (GPU ishlatilmayapti). NVIDIA drayverini yangilang va kompyuterni qayta yoqing, "
             "keyin skriptni qayta ishga tushiring. Hozircha davom etamiz.")
    mark_done("models", gpu_vram=vram)


# --------------------------------------------------------------------------- 5. corpus

def corpus_ok() -> bool:
    files = [CORPUS_DIR / f for f in CORPUS_FILES]
    if not all(f.exists() and f.stat().st_size > 1e6 for f in files):
        return False
    if not VPY.exists():                              # packages not installed yet: size check only
        return True
    code, out = run([VPY, "-c", "import sys, pyarrow.parquet as pq; "
                     "print(sum(pq.ParquetFile(p).metadata.num_rows for p in sys.argv[1:]))", *files],
                    check=False, quiet=True)
    if code == 0:
        ok(f"Korpus joyida: {out.strip().splitlines()[-1]} qator")
        return True
    warn("Korpus fayli buzilgan, qaytadan yuklanadi")
    for f in files:
        f.unlink(missing_ok=True)
    return False


def expected_sha256() -> dict[str, str]:
    found = {}
    for folder in sorted({f.split("/")[0] for f in CORPUS_FILES}):
        try:
            for item in http_json(f"https://huggingface.co/api/datasets/{DATASET}/tree/{REVISION}/{folder}", timeout=30):
                if item.get("lfs"):
                    found[item["path"]] = item["lfs"]["oid"]
        except Exception as exc:
            warn(f"Hugging Face’dan sha256 olinmadi ({exc}); fayl hajmi va ochilishi bilan tekshiramiz")
    return found


def step_corpus():
    if corpus_ok():
        return mark_done("corpus")
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    include = [x for f in CORPUS_FILES for x in ("--include", f)]
    hf_args = ["download", DATASET, "--repo-type", "dataset", "--revision", REVISION, *include, "--local-dir", CORPUS_DIR]
    ways = []
    for tool in ("hf", "huggingface-cli"):
        exe = VBIN / (tool + (".exe" if IS_WIN else ""))
        exe = exe if exe.exists() else shutil.which(tool)
        if exe:
            ways.append((tool, [exe, *hf_args]))
    ways.append(("huggingface_hub", [VPY, "-c",
                 "import sys; from huggingface_hub import hf_hub_download as d\n"
                 "for f in sys.argv[1:]: print(d(%r, f, repo_type='dataset', revision=%r, local_dir=%r))"
                 % (DATASET, REVISION, str(CORPUS_DIR)), *CORPUS_FILES]))
    for name, cmd in ways:
        say(f"Korpus {name} orqali yuklanmoqda…")
        code, _ = run(cmd, check=False, timeout=7200)
        if code == 0 and corpus_ok():
            return mark_done("corpus", via=name)
        warn(f"{name} orqali boʻlmadi, keyingi usul")
    say("Toʻgʻridan-toʻgʻri HTTPS orqali (uzilsa davom etadi)…")
    sums = expected_sha256()
    for f in CORPUS_FILES:
        url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{f}"
        download(url, CORPUS_DIR / f, sha256=sums.get(f))
    if not corpus_ok():
        raise StepFailed("Korpus yuklanmadi yoki ochilmadi")
    mark_done("corpus", via="https")


# --------------------------------------------------------------------------- 6. Qdrant

def qdrant_version() -> str | None:
    try:
        return http_json(f"{QDRANT}/", timeout=3).get("version")
    except Exception:
        return None


def step_qdrant():
    v = qdrant_version()
    if not v:
        v = start_qdrant()
    if not v:
        raise StepFailed("Qdrant ishga tushmadi")
    if not v.startswith(QDRANT_VERSION.rsplit(".", 1)[0]):
        warn(f"Qdrant v{v}; Bobur’dagi server v{QDRANT_VERSION}. Snapshot mos kelmasligi mumkin — "
             f"imkoni boʻlsa v{QDRANT_VERSION} ishlating.")
    ok(f"Qdrant v{v} ishlayapti: {QDRANT}")
    mark_done("qdrant", version=v)


def start_qdrant() -> str | None:
    storage = DATA / "qdrant_storage"
    storage.mkdir(parents=True, exist_ok=True)
    exe = TOOLS / "qdrant" / ("qdrant.exe" if IS_WIN else "qdrant")
    if exe.exists() or IS_WIN:
        if not exe.exists():
            z = download(QDRANT_ZIP, TOOLS / "downloads" / f"qdrant-{QDRANT_VERSION}-windows.zip")
            extract(z, exe.parent, exe.name)
        if exe.exists():
            env = child_env()
            env.update(QDRANT__STORAGE__STORAGE_PATH=str(storage),
                       QDRANT__STORAGE__SNAPSHOTS_PATH=str(DATA / "qdrant_snapshots"),
                       QDRANT__SERVICE__HOST="127.0.0.1", QDRANT__SERVICE__HTTP_PORT="6333",
                       QDRANT__SERVICE__GRPC_PORT="6334", QDRANT__TELEMETRY_DISABLED="true")
            for attempt in (1, 2):
                proc = start_detached([exe], REPORTS / "qdrant.log", env=env)
                if wait_for(f"{QDRANT}/healthz", 60, "Qdrant"):
                    return qdrant_version()
                code = proc.poll()
                if code is None:                      # still starting or stuck: stop it before retrying
                    proc.kill()
                warn(f"Portativ Qdrant ishga tushmadi (kod {code}, log: {REPORTS / 'qdrant.log'})")
                if attempt == 1 and IS_WIN and shutil.which("winget"):
                    say("Qdrant’ga kerak boʻlishi mumkin boʻlgan Microsoft Visual C++ Runtime oʻrnatilmoqda…")
                    run(["winget", "install", "--id", "Microsoft.VCRedist.2015+.x64", "-e", "--silent",
                         "--accept-package-agreements", "--accept-source-agreements"], check=False, timeout=1800)
                else:
                    break
            warn("Docker bilan urinib koʻramiz")
    if shutil.which("docker") and run(["docker", "info"], check=False, quiet=True, timeout=60)[0] == 0:
        run(["docker", "rm", "-f", "modda-qdrant"], check=False, quiet=True)
        run(["docker", "run", "-d", "--name", "modda-qdrant", "--restart", "unless-stopped", "-p", "127.0.0.1:6333:6333",
             "-v", f"{storage.resolve()}:/qdrant/storage", f"qdrant/qdrant:v{QDRANT_VERSION}"], timeout=1800)
        if wait_for(f"{QDRANT}/healthz", 90, "Qdrant (Docker)"):
            return qdrant_version()
    return None


# --------------------------------------------------------------------------- 7. .env

def step_env():
    env_file = ROOT / ".env"
    want = {"OLLAMA_URL": OLLAMA, "QDRANT_URL": QDRANT, "EMBED_MODEL": EMBED_MODEL, "LLM_MODEL": LLM_MODEL,
            "DATABASE_URL": "", "CORPUS_DIR": "data/raw/hf", "DB_PATH": "data/modda.sqlite", "COLLECTION": "modda_chunks"}
    if env_file.exists():
        current = dict(l.split("=", 1) for l in env_file.read_text(encoding="utf-8").splitlines()
                       if "=" in l and not l.lstrip().startswith("#"))
        if current.get("DATABASE_URL", "").strip():
            backup = env_file.with_name(".env.backup")
            shutil.copy(env_file, backup)
            warn(f".env’da PostgreSQL manzili bor edi — bu kompyuterda SQLite ishlatamiz (eski fayl: {backup})")
        else:
            want = {**want, **{k: v for k, v in current.items() if k in want and k != "DATABASE_URL"}}
    lines = ["# Generated by scripts/setup_windows.py — SQLite, no passwords needed"] + [f"{k}={v}" for k, v in want.items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok(f".env yozildi ({env_file})")
    mark_done("env")


# --------------------------------------------------------------------------- 8. pipeline

def modda(*args, **kw) -> tuple[int, str]:
    return run([VPY, "-m", "modda", *args], **kw)


def db_stats() -> dict:
    code, out = modda("stats", check=False, quiet=True)
    try:
        return json.loads(out[out.index("{"):])
    except Exception:
        return {}


def step_ingest():
    st = db_stats()
    if STATE.get("ingest") and st.get("articles", 0) > 100_000:
        return ok(f"Korpus bazada: {st['articles']:,} modda")
    modda("ingest", timeout=7200)
    st = db_stats()
    ok(f"Bazada {st['articles']:,} modda" if isinstance(st.get("articles"), int) else "ingest tugadi")
    mark_done("ingest", articles=st.get("articles"))


def step_chunk():
    st = db_stats()
    if STATE.get("chunk") and st.get("chunks", 0) > 100_000:
        return ok(f"Boʻlaklar tayyor: {st['chunks']:,}")
    modda("chunk", timeout=7200)
    st = db_stats()
    mark_done("chunk", chunks=st.get("chunks"))
    ok(f"Boʻlaklar: {st.get('chunks')}")


def step_numbers():
    if STATE.get("numbers"):
        return ok("Modda raqamlari allaqachon tiklangan")
    modda("fix-numbers", timeout=3600)
    mark_done("numbers")


def step_bench():
    if (STATE.get("bench") or {}).get("rate"):
        rate = STATE["bench"]["rate"]
        ok(f"Tezlik avval oʻlchangan: {rate} boʻlak/s (qayta oʻlchash: --fresh)")
        return rate
    if not ollama_version():
        step_ollama()
    code, out = modda("bench-embed", "--n", "512", "--batch", "64", timeout=3600)
    m = re.search(r'"chunks_per_s":\s*([\d.]+)', out)
    rate = float(m.group(1)) if m else 0.0
    eta = re.search(r'"all_eta":\s*"([^"]+)"', out)
    ok(f"Tezlik: {rate} boʻlak/s; butun korpus ≈ {eta.group(1) if eta else '?'}")
    mark_done("bench", rate=rate)
    return rate


def step_index():
    rate = (STATE.get("bench") or {}).get("rate") or step_bench()
    full = rate >= MIN_DENSE_RATE
    args = ["index", "--all-dense", "--batch", "64"] if full else ["index"]
    if full:
        say(f"GPU tez ({rate} boʻlak/s): HAMMA boʻlaklarga bge-m3 + BM25 yoziladi")
    else:
        warn(f"Tezlik past ({rate} boʻlak/s): ikki qatlamli indeks (BM25 hammasi + bge-m3 kodeks/qonunlar)")
    for attempt in range(1, 4):
        if not ollama_version():
            warn("Ollama javob bermayapti — qayta ishga tushirilmoqda")
            exe = find_ollama()
            if exe:
                start_ollama(exe)
        code, out = modda(*args, check=False)
        if code == 0 and "Indekslandi" in out:
            break
        warn(f"Indekslash toʻxtadi ({attempt}/3) — qolgan joydan davom etamiz")
        time.sleep(10)
    else:
        raise StepFailed("Indekslash 3 marta toʻxtadi. Skriptni qayta ishga tushiring — davom etadi.")
    st = db_stats()
    keep = {k: st.get(k) for k in ("chunks", "chunks_indexed", "chunks_sparse_only")}
    ok(f"Indeks: {keep.get('chunks_indexed')} ta bge-m3+BM25, {keep.get('chunks_sparse_only')} ta faqat BM25, "
       f"jami boʻlak {keep.get('chunks')}")
    mark_done("index", full=full, **keep)


def step_eval():
    code, out = modda("eval", check=False, timeout=3600)
    if code != 0:
        return warn("eval ishlamadi (indeks uchun muhim emas)")
    (REPORTS / "setup-eval.json").write_text(out[out.find("{"):], encoding="utf-8")
    mark_done("eval")


def step_export():
    modda("snapshot-export", timeout=7200)
    exports = sorted((DATA / "exports").glob("modda-*.snapshot"), key=lambda p: p.stat().st_mtime)
    if not exports:
        raise StepFailed("Snapshot fayli topilmadi")
    snap = exports[-1]
    man = snap.with_name(snap.name.replace(".snapshot", ".manifest.json.gz"))
    for old in exports[:-1]:                          # keep only the newest export: each one can be ~2 GB
        old.unlink(missing_ok=True)
        old.with_name(old.name.replace(".snapshot", ".manifest.json.gz")).unlink(missing_ok=True)
        say(f"eski eksport oʻchirildi: {old.name}", "d")
    mark_done("export", snapshot=str(snap), manifest=str(man))
    return snap, man


# --------------------------------------------------------------------------- main

def check_ports():
    for port, name in ((11434, "Ollama"), (6333, "Qdrant")):
        with socket.socket() as s:
            s.settimeout(1)
            busy = s.connect_ex(("127.0.0.1", port)) == 0
        log(f"port {port} ({name}): {'busy' if busy else 'free'}")


def main():
    ap = argparse.ArgumentParser(description="Modda: Windows + NVIDIA GPU uchun toʻliq oʻrnatish va indekslash")
    ap.add_argument("--skip-llm", action="store_true", help=f"{LLM_MODEL} modelini yuklamaslik")
    ap.add_argument("--only", help="faqat shu qadamlar, vergul bilan: " + ",".join(STEPS))
    ap.add_argument("--from", dest="start", choices=STEPS, help="shu qadamdan boshlab")
    ap.add_argument("--no-index", action="store_true", help="indekslash va eksportni qilmaslik")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="avvalgi holatni unutish (fayllar oʻchirilmaydi)")
    ap.add_argument("--list", action="store_true", help="qadamlar roʻyxati")
    a = ap.parse_args()
    if a.list:
        for s in STEPS:
            print(f"  {s:8} {'✓ ' + STATE[s]['done'] if s in STATE else ''}")
        return 0
    if a.fresh:
        STATE.clear()
        save_state(STATE)

    steps = list(STEPS)
    if a.start:
        steps = steps[steps.index(a.start):]
    if a.only:
        wanted = [s.strip() for s in a.only.split(",")]
        unknown = set(wanted) - set(STEPS)
        if unknown:
            ap.error(f"nomaʼlum qadam: {', '.join(unknown)}")
        steps = [s for s in STEPS if s in wanted]
    if a.no_index:
        steps = [s for s in steps if s not in ("index", "eval", "export")]
    if a.no_export:
        steps = [s for s in steps if s != "export"]

    print(f"{C['b']}{C['c']}Modda — Windows GPU oʻrnatuvchisi{C['0']}   loyiha: {ROOT}")
    print(f"{C['d']}Log: {LOG_PATH}{C['0']}\n")
    check_ports()
    fns = {"system": step_system, "python": step_python, "ollama": step_ollama,
           "models": lambda: step_models(a.skip_llm), "corpus": step_corpus, "qdrant": step_qdrant,
           "env": step_env, "ingest": step_ingest, "chunk": step_chunk, "numbers": step_numbers,
           "bench": step_bench, "index": step_index, "eval": step_eval, "export": step_export}
    timings: list[tuple[str, float, str]] = []
    result = None
    for i, name in enumerate(steps, 1):
        print()
        say(f"━━ [{i}/{len(steps)}] {name} ━━", "b")
        t0 = time.time()
        try:
            r = fns[name]()
            if name == "export":
                result = r
            timings.append((name, time.time() - t0, "ok"))
        except KeyboardInterrupt:
            print()
            warn("Toʻxtatildi. Qayta ishga tushiring: python scripts\\setup_windows.py  — qolgan joydan davom etadi.")
            timings.append((name, time.time() - t0, "toʻxtatildi"))
            summary(timings)
            return 130
        except StepFailed as exc:
            bad(f"{name}: {exc}")
            timings.append((name, time.time() - t0, "XATO"))
            summary(timings)
            print(f"\n{C['y']}Tuzatgandan keyin xuddi shu buyruqni qayta ishga tushiring — tayyor qadamlar oʻtkazib "
                  f"yuboriladi. Yordam kerak boʻlsa, Bobur’ga shu faylni yuboring:{C['0']}\n  {LOG_PATH}")
            return 1
        except Exception as exc:                      # unexpected: still leave a useful log
            import traceback
            log(traceback.format_exc())
            bad(f"{name}: kutilmagan xato: {exc!r}")
            timings.append((name, time.time() - t0, "XATO"))
            summary(timings)
            print(f"\nBobur’ga shu faylni yuboring: {LOG_PATH}")
            return 1
        ok(f"{name} tugadi ({fmt_dur(time.time() - t0)})")
    summary(timings)
    if result:
        snap, man = result
        print(f"\n{C['b']}{C['g']}TAYYOR!{C['0']} Bobur’ga shu ikki faylni yuboring (Google Drive / Telegram):")
        for p in (snap, man):
            print(f"  {p}   ({fmt_mb(p.stat().st_size)})")
        print("Bobur oʻz kompyuterida:  python -m modda snapshot-import data/exports/" + snap.name)
        if IS_WIN:
            subprocess.run(["explorer", str(snap.parent)], check=False)
    return 0


def summary(timings):
    print()
    say("━━ Natija ━━", "b")
    for name, dt, status in timings:
        color = "g" if status == "ok" else "r"
        say(f"  {name:9} {fmt_dur(dt):>8}   {status}", color)
    say(f"  {'jami':9} {fmt_dur(time.time() - T_START):>8}")
    (REPORTS / "setup-summary.json").write_text(json.dumps(
        {"finished": datetime.now().isoformat(timespec="seconds"), "log": str(LOG_PATH),
         "steps": [{"step": n, "seconds": round(d), "status": s} for n, d, s in timings], "state": STATE},
        indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
