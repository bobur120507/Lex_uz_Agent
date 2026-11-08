"""Ollama HTTP client: embeddings and chat. Only `requests` is needed."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field

import requests


class OllamaError(RuntimeError):
    pass


@dataclass
class Ollama:
    url: str = "http://localhost:11434"
    timeout: float = 600.0
    keep_alive: str = "30m"          # keep models in memory between batches (no reload every few minutes)
    last_embed: dict = field(default_factory=dict)   # Ollama's own counters for the latest call (shown on the site)
    last_chat: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)      # per-request generation options (API /v1: temperature, seed)

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
        self.last_embed = _stats(data)
        return vecs

    def show(self, model: str) -> dict:
        """Model card from Ollama (`/api/show`): architecture numbers such as layers, width and heads."""
        return self._post("/api/show", {"model": model})

    def chat(self, model: str, messages: list[dict], *, temperature: float = 0.0, num_ctx: int = 8192,
             json_mode: bool = False, on_token=None, num_predict: int = 900) -> tuple[str, float]:
        """Returns (text, seconds). With `on_token`, the answer is streamed and each piece is passed to it.

        `think: False` goes to every model: thinking models (qwen3, gemma4, deepseek-r1, gpt-oss…) otherwise
        spend the `num_predict` budget on a hidden chain and return an empty or cut answer (day-4 run: gemma4
        hit 700/700 tokens with no answer text). Ollama ignores it for models that do not think; an Ollama that
        refuses it gets the request again without it."""
        payload: dict = {
            "model": model, "messages": messages, "stream": on_token is not None, "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict, **self.options},
            "think": False,
        }
        if json_mode:
            payload["format"] = "json"
        t0 = time.perf_counter()
        try:
            text, thinking, data = self._chat_once(payload, on_token)
        except OllamaError as exc:
            if "HTTP 400" not in str(exc) or "think" not in str(exc).lower():
                raise
            payload.pop("think")
            text, thinking, data = self._chat_once(payload, on_token)
        dt = time.perf_counter() - t0
        self.last_chat = _stats(data)
        if data.get("done_reason"):
            self.last_chat["done_reason"] = data["done_reason"]       # "length" = cut at num_predict
        if data.get("done_reason") == "length" or (data.get("eval_count") or 0) >= num_predict:
            self.last_chat["truncated"] = True
        inline = sum(len(m.group(0)) for m in THINK_RE.finditer(text))
        if thinking or inline:
            self.last_chat["thinking_chars"] = len(thinking) + inline
        return strip_think(text), dt

    def _chat_once(self, payload: dict, on_token) -> tuple[str, str, dict]:
        if on_token is None:
            data = self._post("/api/chat", payload)
            msg = data.get("message", {})
            return msg.get("content", "") or "", msg.get("thinking", "") or "", data
        return self._stream_chat(payload, on_token)

    def _stream_chat(self, payload: dict, on_token) -> tuple[str, str, dict]:
        try:
            r = requests.post(f"{self.url}/api/chat", json=payload, timeout=self.timeout, stream=True)
        except requests.Timeout as exc:
            raise OllamaError(f"Ollama /api/chat {self.timeout:.0f} s ichida javob bermadi") from exc
        except requests.ConnectionError as exc:
            raise OllamaError(f"Ollama’ga ulanib boʻlmadi ({self.url}). `ollama serve` ishlayaptimi?") from exc
        if r.status_code != 200:
            raise OllamaError(f"Ollama /api/chat → HTTP {r.status_code}: {r.text[:300]}")
        parts, thought, last = [], [], {}
        for line in r.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            if ev.get("error"):
                raise OllamaError(f"Ollama: {ev['error']}")
            msg = ev.get("message", {})
            if msg.get("thinking"):
                thought.append(msg["thinking"])
            piece = msg.get("content", "")
            if piece:
                parts.append(piece)
                on_token(piece)
            if ev.get("done"):
                last = ev
        return "".join(parts), "".join(thought), last


def _stats(data: dict) -> dict:
    """Ollama's measured numbers (durations come in nanoseconds). Missing ones stay out — never guessed."""
    ms = lambda k: round(data[k] / 1e6, 1) if isinstance(data.get(k), (int, float)) else None
    out = {"prompt_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count"),
           "load_ms": ms("load_duration"), "prompt_ms": ms("prompt_eval_duration"),
           "gen_ms": ms("eval_duration"), "total_ms": ms("total_duration")}
    if out["output_tokens"] and out["gen_ms"]:
        out["tokens_per_s"] = round(out["output_tokens"] / (out["gen_ms"] / 1000), 2)
    return {k: v for k, v in out.items() if v is not None}


# a reasoning block written into the answer text: <think>…</think>, <thought>…, also one cut before its end tag
THINK_RE = re.compile(r"<(think|thinking|thought)>.*?(?:</\1>|\Z)", re.S | re.I)


def strip_think(text: str) -> str:
    return THINK_RE.sub("", text).strip()


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
