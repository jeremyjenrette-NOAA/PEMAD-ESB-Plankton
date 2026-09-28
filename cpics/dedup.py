"""Find repeat captures of the same object and add dup-group columns to labels/labels.csv.

    python -m cpics.dedup

CPICS often re-captures one object many times: a particle resting in the sampling volume or on the
window is saved as a new ROI every frame for minutes (20260521 has groups of >1,000 ROIs at one spot).
Two ROIs are joined into a group when, on the same day, they are
  - byte-identical, or
  - at nearly the same place in the full frame (centres within 30 px), about the same size
    (within 15 %) and look alike (64-bit difference hash within 8 bits).
Groups are closed transitively. Columns added:
  dup_group   roi_id of the group's earliest member (its representative); own id when unique
  dup_size    members in the group
  dup_span_s  seconds between the first and last member
  persistent  true when the group spans >= 10 s (an object sitting in view, not a passing one)
Hashes are cached in labels/_cache/hashes.csv (keyed by path + file size).
"""
import argparse
import hashlib
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from PIL import Image

from cpics import config

POS_PX, SIZE_TOL, HASH_BITS, PERSIST_S = 30, 0.15, 8, 10


def dhash(path):
    with Image.open(path) as im:
        g = np.asarray(im.convert("L").resize((9, 8), Image.BILINEAR), dtype=np.int16)
    bits = (g[:, 1:] < g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hashes(df, rois_dir, cache_file):
    cache = {}
    if cache_file.exists():
        c = pd.read_csv(cache_file, dtype=str)
        if {"path", "bytes"} <= set(c.columns):
            cache = {(p, b): (m, h) for p, b, m, h in c[["path", "bytes", "md5", "dhash"]].itertuples(index=False)}
    out = []
    for p, b in zip(df.path, df.bytes):
        hit = cache.get((p, b))
        if not hit:
            f = rois_dir / p
            hit = (hashlib.md5(f.read_bytes()).hexdigest(), f"{dhash(f):016x}")
        out.append(hit)
    h = pd.DataFrame(out, columns=["md5", "dhash"], index=df.index)
    pd.concat([df[["path", "bytes"]], h], axis=1).to_csv(cache_file, index=False)
    return h


def ts(roi_id):
    return datetime.strptime(roi_id[:19], "%Y%m%d_%H%M%S.%f").timestamp()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    cfg = config.load(ap.parse_args(argv).config)
    path = cfg["labels_dir"] / "labels.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.drop(columns=[c for c in ["dup_group", "dup_size", "dup_span_s", "persistent"] if c in df.columns])
    h = hashes(df, cfg["rois_dir"], cfg["labels_dir"] / "_cache" / "hashes.csv")

    n = len(df)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for idx in df.groupby([df.day, h.md5]).indices.values():
        for j in idx[1:]:
            union(idx[0], j)

    num = lambda c: pd.to_numeric(df[c], errors="coerce").to_numpy()
    cx, cy = (num("frame_x0") + num("frame_x1")) / 2, (num("frame_y0") + num("frame_y1")) / 2
    W, H = df.width.astype(int).to_numpy(), df.height.astype(int).to_numpy()
    dh = np.array([int(x, 16) for x in h.dhash], dtype=np.uint64)
    day = df.day.to_numpy()
    cell = defaultdict(list)
    for i in range(n):
        if not np.isnan(cx[i]):
            cell[(day[i], int(cx[i] // (2 * POS_PX)), int(cy[i] // (2 * POS_PX)))].append(i)
    for (d, gx, gy), members in cell.items():
        cand = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cell.get((d, gx + dx, gy + dy), [])]
        cand = np.array(sorted(cand))
        for i in members:
            c = cand[cand > i]
            if not len(c):
                continue
            ok = (np.abs(cx[c] - cx[i]) <= POS_PX) & (np.abs(cy[c] - cy[i]) <= POS_PX)
            ok &= np.abs(W[c] - W[i]) <= SIZE_TOL * np.maximum(W[c], W[i])
            ok &= np.abs(H[c] - H[i]) <= SIZE_TOL * np.maximum(H[c], H[i])
            c = c[ok]
            if not len(c):
                continue
            x = dh[c] ^ dh[i]
            bits = np.array([bin(int(v)).count("1") for v in x])
            for j in c[bits <= HASH_BITS]:
                union(i, int(j))

    root = np.array([find(i) for i in range(n)])
    t = np.array([ts(r) for r in df.roi_id])
    g = pd.DataFrame({"root": root, "t": t, "roi_id": df.roi_id})
    first = g.sort_values("roi_id").groupby("root").roi_id.first()
    agg = g.groupby("root").agg(size=("t", "size"), span=("t", lambda s: s.max() - s.min()))
    df["dup_group"] = first.reindex(root).to_numpy()
    df["dup_size"] = agg["size"].reindex(root).astype(int).astype(str).to_numpy()
    span = agg["span"].reindex(root).to_numpy()
    df["dup_span_s"] = [f"{s:.0f}" for s in span]
    df["persistent"] = np.where(span >= PERSIST_S, "true", "false")
    df.to_csv(path, index=False)

    grp = df.drop_duplicates("dup_group")
    multi = grp[grp.dup_size.astype(int) > 1]
    L = ["# Duplicate report", "",
         f"- ROIs: {n:,}; distinct objects (dup groups): {len(grp):,}",
         f"- Groups with repeats: {len(multi):,}, covering {multi.dup_size.astype(int).sum():,} ROIs",
         f"- Persistent groups (span >= {PERSIST_S} s): {(multi.persistent == 'true').sum():,}, covering "
         f"{multi[multi.persistent == 'true'].dup_size.astype(int).sum():,} ROIs", "",
         "| day | ROIs | distinct objects | ROIs in persistent groups |", "|---|---|---|---|"]
    for d, s in df.groupby("day"):
        L.append(f"| {d} | {len(s):,} | {s.dup_group.nunique():,} | {(s.persistent == 'true').sum():,} |")
    L += ["", "## Largest groups", "", "| representative | ROIs | span (s) |", "|---|---|---|"]
    for r in multi.assign(k=multi.dup_size.astype(int)).sort_values("k", ascending=False).head(15).itertuples():
        L.append(f"| {r.dup_group} | {r.dup_size} | {r.dup_span_s} |")
    lab = df[df.triage != ""]
    conflict = lab.groupby("dup_group").triage.nunique()
    L += ["", f"- Labeled groups whose members carry different triage labels: {(conflict > 1).sum()}"]
    (cfg["labels_dir"] / "dup_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:6]))


if __name__ == "__main__":
    main()
