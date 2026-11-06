"""Record one real run of the API into public/demo/fixture.json, for the clearly-labelled demo mode (?demo).

    python frontend_idea/scripts/record_demo.py "Har yilgi mehnat taʼtili necha kun?" --api http://localhost:8080

It saves the SSE events with their real time gaps, the embedding/projection payload, the model cards,
the ±5 article contexts of every candidate and a few documents — so the page can be shown offline.
The page always shows a «Namuna rejimi» banner while this file is used.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

OUT = Path(__file__).resolve().parents[1] / "public" / "demo" / "fixture.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--api", default="http://localhost:8080")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    api = a.api.rstrip("/")
    events, last = [], time.time()
    with requests.post(f"{api}/ask/stream", json={"question": a.question}, stream=True, timeout=900) as r:
        r.raise_for_status()
        buf = ""
        for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                data = "".join(line[5:].strip() for line in block.splitlines() if line.startswith("data:"))
                if data:
                    now = time.time()
                    events.append({"dt": round((now - last) * 1000), "ev": json.loads(data)})
                    last = now
    rid = events[0]["ev"].get("request_id")
    get = lambda p: requests.get(f"{api}{p}", timeout=120).json()
    cands = next((e["ev"]["data"]["candidates"] for e in events if e["ev"]["type"] == "retrieval.completed"), [])
    contexts = {c["chunk_id"]: get(f"/chunks/{quote(c['chunk_id'], safe='')}/context?n=5") for c in cands}
    docs = get("/documents?limit=8")["documents"]
    fx = {
        "recorded": datetime.now().isoformat(timespec="seconds"), "question": a.question, "request_id": rid,
        "note": a.note or "Bitta haqiqiy soʻrovning yozuvi (namuna rejimi).",
        "health": get("/health"), "model": get("/model/info"), "embedding": get(f"/ask/{rid}/embedding"),
        "events": events, "contexts": contexts, "documents": docs,
        "document_pages": {d["doc_id"]: get(f"/documents/{quote(d['doc_id'], safe='')}?limit=20") for d in docs[:3]},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    print(f"{len(events)} ta hodisa → {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
