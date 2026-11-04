"""Settings from environment variables and an optional .env file (no extra dependency)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://localhost:11434").rstrip("/"))
    qdrant_url: str = field(default_factory=lambda: _env("QDRANT_URL", "http://localhost:6333").rstrip("/"))
    embed_model: str = field(default_factory=lambda: _env("EMBED_MODEL", "bge-m3"))
    embed_dim: int = field(default_factory=lambda: int(_env("EMBED_DIM", "1024")))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "qwen3:8b"))
    corpus_dir: Path = field(default_factory=lambda: ROOT / _env("CORPUS_DIR", "data/raw/hf"))
    db_path: Path = field(default_factory=lambda: ROOT / _env("DB_PATH", "data/modda.sqlite"))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", ""))
    collection: str = field(default_factory=lambda: _env("COLLECTION", "modda_chunks"))
    top_k: int = field(default_factory=lambda: int(_env("TOP_K", "5")))
    reports_dir: Path = field(default_factory=lambda: ROOT / "data" / "reports")
    golden_path: Path = field(default_factory=lambda: ROOT / "data" / "golden" / "golden.jsonl")


def get_settings() -> Settings:
    return Settings()
