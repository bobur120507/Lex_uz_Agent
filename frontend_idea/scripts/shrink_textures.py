"""Make a textured .glb light enough for the page: every embedded texture is resized to at most --max px and
re-encoded (JPEG when it has no transparency, PNG otherwise). Geometry, nodes and materials are left as they are.

    python3 -I frontend_idea/scripts/shrink_textures.py "3D_Models/judges_gavel.glb" \
        frontend_idea/src/assets/models/judges-gavel.glb --max 1024

Standard library + Pillow.
"""

from __future__ import annotations

import argparse
import io
import json
import struct
from pathlib import Path

from PIL import Image


def read_glb(path: Path) -> tuple[dict, bytes]:
    b = path.read_bytes()
    magic, _, _ = struct.unpack("<III", b[:12])
    if magic != 0x46546C67:
        raise SystemExit(f"{path}: not a .glb")
    off, js, binary = 12, None, b""
    while off < len(b):
        ln, kind = struct.unpack("<II", b[off:off + 8])
        chunk = b[off + 8:off + 8 + ln]
        if kind == 0x4E4F534A:
            js = json.loads(chunk)
        elif kind == 0x004E4942:
            binary = chunk
        off += 8 + ln
    return js, binary


def write_glb(path: Path, js: dict, binary: bytes):
    jb = json.dumps(js, separators=(",", ":")).encode()
    jb += b" " * (-len(jb) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(jb) + 8 + len(binary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(jb), 0x4E4F534A) + jb
                     + struct.pack("<II", len(binary), 0x004E4942) + binary)


def shrink(data: bytes, max_px: int, quality: int) -> tuple[bytes, str]:
    im = Image.open(io.BytesIO(data))
    im.load()
    if max(im.size) > max_px:
        k = max_px / max(im.size)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    alpha = im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 255
    out = io.BytesIO()
    if alpha:
        im.save(out, "PNG", optimize=True)
        return out.getvalue(), "image/png"
    im.convert("RGB").save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue(), "image/jpeg"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--max", type=int, default=1024)
    ap.add_argument("--quality", type=int, default=86)
    a = ap.parse_args()
    js, binary = read_glb(Path(a.src))
    views = js["bufferViews"]
    replaced = {}
    for img in js.get("images", []):
        if "bufferView" not in img:
            continue
        v = views[img["bufferView"]]
        raw = binary[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]
        new, mime = shrink(raw, a.max, a.quality)
        replaced[img["bufferView"]] = new
        img["mimeType"] = mime
    out = bytearray()
    for i, v in enumerate(views):                   # rebuild the buffer view by view, 4-byte aligned
        data = replaced.get(i) or binary[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]
        out += b"\0" * (-len(out) % 4)
        v["byteOffset"] = len(out)
        v["byteLength"] = len(data)
        out += data
    js["buffers"][0]["byteLength"] = len(out)
    write_glb(Path(a.dst), js, bytes(out))
    print(f"{a.src} ({Path(a.src).stat().st_size / 1e6:.2f} MB) → {a.dst} ({Path(a.dst).stat().st_size / 1e6:.2f} MB), "
          f"{len(replaced)} textures ≤ {a.max}px")


if __name__ == "__main__":
    main()
