"""Ollama HTTP client: embeddings and chat. Only `requests` is needed."""

from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass

import requests


class OllamaError(RuntimeError):
    pass


@dataclass
class Ollama:
    url: str = "http://localhost:11434"
    timeout: float = 600.0
    keep_alive: str = "30m"          # keep models in memory between batches (no reload every few minutes)

    def _post(self, path: str, payload: dict) -> dict:
        try:
            r = requests.post(f"{self.url}{path}", json=payload, timeout=self.timeout)
        except requests.Timeout as exc:
            raise OllamaError(f"Ollama {path} {self.timeout:.0f} s ichida javob bermadi (model yuklanyaptimi?)") from exc
        except requests.ConnectionError as exc:
            raise OllamaError(f"Ollama’ga ulanib boʻlmadi ({self.url}). `ollama serve` ishlayaptimi?") from exc
        if r.status_code != 200:
            raise OllamaError(f"Ollama {path} → HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def version(self) -> str:
        try:
            r = requests.get(f"{self.url}/api/version", timeout=10)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama’ga ulanib boʻlmadi ({self.url}).") from exc
        return r.json().get("version", "?")

    def models(self) -> list[str]:
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=10)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama’ga ulanib boʻlmadi ({self.url}).") from exc
        return [m["name"] for m in r.json().get("models", [])]

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        try:
            data = self._post("/api/embed", {"model": model, "input": texts, "truncate": True,
                                             "keep_alive": self.keep_alive})
        except OllamaError as exc:
            if "HTTP 404" in str(exc) and "not found" in str(exc).lower() and "model" in str(exc).lower():
                raise OllamaError(f"`{model}` modeli topilmadi. Ollama yangilangandan keyin: ollama pull {model}") from exc
            raise
        vecs = data.get("embeddings")
        if not vecs or len(vecs) != len(texts):
            raise OllamaError(f"Embedding javobi notoʻgʻri: {str(data)[:200]}")
        return vecs

    def chat(self, model: str, messages: list[dict], *, temperature: float = 0.0, num_ctx: int = 8192,
             json_mode: bool = False) -> tuple[str, float]:
        payload: dict = {
            "model": model, "messages": messages, "stream": False, "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        if model.startswith(("qwen3", "deepseek-r1", "gpt-oss")):
            payload["think"] = False             # reasoning models: no hidden chain, faster
        if json_mode:
            payload["format"] = "json"
        t0 = time.perf_counter()
        data = self._post("/api/chat", payload)
        dt = time.perf_counter() - t0
        text = data.get("message", {}).get("content", "")
        return strip_think(text), dt


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


class FakeEmbedder:
    """Deterministic hashing embedder for tests and offline runs (not for real search quality)."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        from .textnorm import tokenize
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in tokenize(t):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
