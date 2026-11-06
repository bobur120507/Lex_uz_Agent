"""Make a heavy sculpted .glb light enough for the browser (numpy only, no Blender needed).

    python frontend_idea/scripts/optimize_model.py "3D_Models/lady-justice/source/Lady Justice.glb" \
        frontend_idea/src/assets/models/lady-justice.glb --cells 260

What it does: applies the node transforms, merges every primitive into one mesh, simplifies it by vertex
clustering (vertices inside the same small grid cell become one; `--cells` = cells along the longest side,
higher = more detail), keeps the averaged vertex colours, recomputes smooth normals, puts the model upright
with its feet at y = 0, and writes a compact GLB (positions, normals, colours, 32-bit indices).
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np

COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path: Path):
    data = path.read_bytes()
    magic, _, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise SystemExit("GLB fayl emas")
    off, js, binary = 12, None, None
    while off < len(data):
        n, kind = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + n]
        if kind == 0x4E4F534A:
            js = json.loads(chunk)
        elif kind == 0x004E4942:
            binary = chunk
        off += 8 + n
    return js, binary


def accessor(js, binary, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    dt = np.dtype(COMP[a["componentType"]])
    nc = NCOMP[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or dt.itemsize * nc
    if stride == dt.itemsize * nc:
        arr = np.frombuffer(binary, dtype=dt, count=a["count"] * nc, offset=start).reshape(a["count"], nc)
    else:
        raw = np.frombuffer(binary, dtype=np.uint8, count=stride * a["count"], offset=start).reshape(a["count"], stride)
        arr = raw[:, : dt.itemsize * nc].copy().view(dt).reshape(a["count"], nc)
    if a.get("normalized"):
        arr = arr.astype(np.float32) / np.iinfo(dt).max
    return arr


def node_matrix(n):
    if "matrix" in n:
        return np.array(n["matrix"], dtype=np.float64).reshape(4, 4).T
    m = np.eye(4)
    if "scale" in n:
        m = np.diag([*n["scale"], 1.0]) @ m
    if "rotation" in n:
        x, y, z, w = n["rotation"]
        r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        rm = np.eye(4); rm[:3, :3] = r; m = rm @ m
    if "translation" in n:
        t = np.eye(4); t[:3, 3] = n["translation"]; m = t @ m
    return m


def world_meshes(js):
    parents = {c: i for i, n in enumerate(js["nodes"]) for c in n.get("children", [])}
    for i, n in enumerate(js["nodes"]):
        if "mesh" not in n:
            continue
        m, k = node_matrix(n), i
        while k in parents:
            k = parents[k]
            m = node_matrix(js["nodes"][k]) @ m
        yield n["mesh"], m


def simplify(pos, col, tris, cells):
    lo, hi = pos.min(0), pos.max(0)
    size = (hi - lo).max() / cells
    key = np.floor((pos - lo) / size).astype(np.int64)
    dims = key.max(0) + 1
    flat = (key[:, 0] * dims[1] + key[:, 1]) * dims[2] + key[:, 2]
    uniq, remap = np.unique(flat, return_inverse=True)
    n = len(uniq)
    cnt = np.bincount(remap, minlength=n).astype(np.float64)
    npos = np.stack([np.bincount(remap, pos[:, k], n) / cnt for k in range(3)], 1)
    ncol = None if col is None else np.stack([np.bincount(remap, col[:, k], n) / cnt for k in range(col.shape[1])], 1)
    t = remap[tris]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    _, keep = np.unique(np.sort(t, 1), axis=0, return_index=True)
    t = t[np.sort(keep)]
    used = np.unique(t)                                  # drop vertices no triangle uses
    new = -np.ones(n, dtype=np.int64); new[used] = np.arange(len(used))
    return npos[used], (None if ncol is None else ncol[used]), new[t]


def normals(pos, tris):
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    vn = np.zeros_like(pos)
    for k in range(3):
        np.add.at(vn, tris[:, k], fn)
    ln = np.linalg.norm(vn, axis=1, keepdims=True)
    return vn / np.maximum(ln, 1e-12)


def write_glb(path: Path, pos, nor, col, tris):
    pos, nor = pos.astype(np.float32), nor.astype(np.float32)
    idx = tris.astype(np.uint32).ravel()
    parts, views, accs = [], [], []

    def add(arr, target, comp, typ, normalized=False, minmax=False):
        off = sum(len(p) for p in parts)
        b = arr.tobytes()
        parts.append(b + b"\0" * (-len(b) % 4))
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b), **({"target": target} if target else {})})
        a = {"bufferView": len(views) - 1, "componentType": comp, "count": int(arr.shape[0] if arr.ndim > 1 else arr.size), "type": typ}
        if normalized:
            a["normalized"] = True
        if minmax:
            a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        accs.append(a)
        return len(accs) - 1

    attrs = {"POSITION": add(pos, 34962, 5126, "VEC3", minmax=True), "NORMAL": add(nor, 34962, 5126, "VEC3")}
    if col is not None:
        c8 = np.clip(np.round(col[:, :4] * 255), 0, 255).astype(np.uint8)
        if c8.shape[1] == 3:
            c8 = np.concatenate([c8, np.full((len(c8), 1), 255, np.uint8)], 1)
        attrs["COLOR_0"] = add(c8, 34962, 5121, "VEC4", normalized=True)
    ind = add(idx, 34963, 5125, "SCALAR")
    binary = b"".join(parts)
    js = {"asset": {"version": "2.0", "generator": "modda optimize_model.py"}, "scene": 0, "scenes": [{"nodes": [0]}],
          "nodes": [{"mesh": 0, "name": "lady_justice"}],
          "meshes": [{"name": "lady_justice", "primitives": [{"attributes": attrs, "indices": ind, "material": 0}]}],
          "materials": [{"name": "statue", "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.9, "roughnessFactor": 0.35}}],
          "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(binary)}]}
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(j) + 8 + len(binary))
    out += struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", len(binary), 0x004E4942) + binary
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--cells", type=int, default=260, help="grid cells along the longest side (detail)")
    a = ap.parse_args()
    js, binary = read_glb(Path(a.src))
    P, Cs, T, base = [], [], [], 0
    for mi, m in world_meshes(js):
        for prim in js["meshes"][mi]["primitives"]:
            if prim.get("mode", 4) != 4:
                continue
            pos = accessor(js, binary, prim["attributes"]["POSITION"]).astype(np.float64)
            pos = (np.c_[pos, np.ones(len(pos))] @ m.T)[:, :3]
            col = accessor(js, binary, prim["attributes"]["COLOR_0"]).astype(np.float64) if "COLOR_0" in prim["attributes"] else None
            tris = (accessor(js, binary, prim["indices"]).reshape(-1, 3).astype(np.int64) if "indices" in prim
                    else np.arange(len(pos)).reshape(-1, 3))
            P.append(pos); Cs.append(col); T.append(tris + base); base += len(pos)
    # primitives that share one vertex buffer would be repeated: de-duplicate identical buffers
    shared = len({json.dumps(p["attributes"], sort_keys=True) for mi, _ in world_meshes(js) for p in js["meshes"][mi]["primitives"]}) == 1
    if shared and len(P) > 1:
        n0 = len(P[0])
        T = [t - k * n0 for k, t in enumerate(T)]
        P, Cs = P[:1], Cs[:1]
    pos = np.concatenate(P); tris = np.concatenate(T)
    col = None if any(c is None for c in Cs) else np.concatenate(Cs)
    print(f"kirish: {len(pos):,} uch, {len(tris):,} uchburchak")
    pos, col, tris = simplify(pos, col, tris, a.cells)
    # upright, feet on y = 0, centred on x/z
    lo, hi = pos.min(0), pos.max(0)
    pos -= [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]
    nor = normals(pos, tris)
    write_glb(Path(a.dst), pos, nor, col, tris)
    print(f"chiqish: {len(pos):,} uch, {len(tris):,} uchburchak, oʻlcham {hi - lo}, fayl {Path(a.dst).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
