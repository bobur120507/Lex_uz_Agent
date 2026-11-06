"""Real architecture numbers of the models in use, read from Ollama's model card (`/api/show`).

The website draws the "mind" (LLM) and the embedding model from these numbers: layer count, hidden width,
attention heads, feed-forward width, context length. Nothing here is assumed — a field Ollama does not
report is simply missing. Per-request activations are not available from Ollama and are never invented.
"""

from __future__ import annotations

FIELDS = {
    "block_count": "layers", "embedding_length": "hidden_size", "attention.head_count": "attention_heads",
    "attention.head_count_kv": "kv_heads", "feed_forward_length": "ffn_size", "context_length": "context_length",
    "attention.key_length": "head_dim", "expert_count": "experts", "expert_used_count": "experts_used",
    "pooling_type": "pooling", "vocab_size": "vocab_size", "rope.freq_base": "rope_base",
}


def card(show: dict, name: str) -> dict:
    info = show.get("model_info") or {}
    details = show.get("details") or {}
    arch = info.get("general.architecture") or details.get("family")
    out = {"name": name, "architecture": arch, "family": details.get("family"),
           "parameter_size": details.get("parameter_size"), "quantization": details.get("quantization_level"),
           "format": details.get("format"), "parameter_count": info.get("general.parameter_count")}
    for key, label in FIELDS.items():
        v = info.get(f"{arch}.{key}") if arch else None
        if v is not None:
            out[label] = v
    tokens = info.get("tokenizer.ggml.tokens")
    if isinstance(tokens, list) and tokens:
        out.setdefault("vocab_size", len(tokens))
    if "attention_heads" in out and "hidden_size" in out and "head_dim" not in out:
        hd = out["hidden_size"] / out["attention_heads"]
        if hd == int(hd):
            out["head_dim"] = int(hd)
            out["head_dim_derived"] = True              # hidden_size / attention_heads, not reported
    out["source"] = "ollama /api/show"
    return {k: v for k, v in out.items() if v is not None}
