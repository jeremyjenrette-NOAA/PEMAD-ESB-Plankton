"""Run the current pipeline on a new, unlabeled cruise (first used for the January 2026 Chance USV data).

PRELIMINARY by design: the classifier is the Phase 1 DINOv2 + logistic-regression baseline trained on
the V3 (May-June 2026) labels. Nothing from the new cruise has been labeled, so class shares are
model estimates, not counts.

    # On the Mac (no torch or GPU needed)
    python -m cpics.cruise inventory --name jan2026 --src "/Volumes/PortableSSD/saltnoaa/CPICS/January_2026_usv"
    python -m cpics.cruise dedup     --name jan2026
    python -m cpics.cruise package   --name jan2026          # tar of the ROIs only (full frames left out)
    # On the GPU workstation (after copying and unpacking the tar: scripts/cruise_workstation.sh)
    python -m cpics.cruise embed     --name jan2026 --config configs/workstation.yaml
    python -m cpics.cruise classify  --name jan2026 --config configs/workstation.yaml
    python -m cpics.cruise map       --name jan2026 --config configs/workstation.yaml

Outputs: large files in <work_dir>/cruises/<name>/ (rois.csv, dedup.csv, embeddings/, predictions.csv,
objects.csv, map.csv); the small report and figures in reports/cruises/<name>/ (commit those).

What each step does
  inventory  lists every PNG under <src>/<day>/<hour>/ and sorts it into roi / full_frame / unreadable.
             Full frames (2736 x 2192, the whole camera image) are saved alongside ROIs on some cruises
             and are left out of everything downstream; so are thumbnail/ folders and macOS ._ files.
  dedup      groups repeat captures of one object. New cruises have no ROICoord (frame position), so
             two ROIs are joined when, on the same day and within GAP_S seconds of each other, they are
             byte-identical, or have about the same size (10 %), a near-identical 64-bit difference hash
             (<= HASH_BITS) and correlated 16x16 grey thumbnails (>= CORR). Approximate; see the
             validation note at GAP_S below.
  embed      DINOv2 embedding of every ROI (same preprocessing as cpics.embed).
  classify   re-fits the Phase 1 DINOv2 baseline exactly as cpics.baseline does (train split, C chosen on
             val), applies it to every ROI, averages probabilities over each object's captures and
             reports class shares by object and by ROI, overall, per day and per hour. Also gives shares
             corrected for the model's known confusions on the eval_newdays set (with a bootstrap range).
  map        2-D UMAP of one capture per object, k-means regions on the map, and slide figures: the map
             coloured by predicted class, and each region with its majority class and example images.
"""
import argparse
import hashlib
import json
import os
import re
import tarfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from cpics import config

CLASSES = ["organism", "marine_snow", "ring", "blurry", "artifact"]
LABEL = {"organism": "Organism", "marine_snow": "Marine snow", "ring": "Ring", "blurry": "Blurry",
         "artifact": "Artifact"}
COLOR = {"organism": "#009E73", "marine_snow": "#56B4E9", "ring": "#E69F00", "blurry": "#9A9A9A",
         "artifact": "#CC79A7"}  # Okabe-Ito, colour-blind safe
FRAME_SIZE = (2736, 2192)
# Repeat-capture rule without frame positions. Checked on the May-June set against the position-based
# groups (cpics.dedup): distinct-object count within 0.3 % (24,368 vs 24,315); it finds the long
# "resting object" bursts (pair precision 1.00, recall 0.88) but not most scattered repeats, which are
# rare (< 1 % of ROIs outside 20260521). Looser settings chained distinct look-alike particles (rings).
GAP_S, SIZE_TOL, HASH_BITS, CORR, PERSIST_S = 5, 0.10, 4, 0.95, 10
MAX_MISFIT = 0.10   # classify: largest L1 misfit at which the confusion correction is reported


# ---------------------------------------------------------------- helpers
def cruise_dirs(cfg, name):
    work = cfg["work_dir"] / "cruises" / name
    rep = config.REPO / "reports" / "cruises" / name
    work.mkdir(parents=True, exist_ok=True)
    rep.mkdir(parents=True, exist_ok=True)
    return work, rep


def src_dir(work, arg):
    """Where the ROI images are: --src, else the unpacked tar (<work>/rois), else what inventory recorded."""
    if arg:
        return Path(arg)
    if (work / "rois").is_dir():
        return work / "rois"
    meta = work / "cruise.json"
    if meta.exists():
        return Path(json.loads(meta.read_text())["src"])
    raise SystemExit("no image folder: pass --src")


def ts(roi_id):
    return datetime.strptime(roi_id[:19], "%Y%m%d_%H%M%S.%f").timestamp()


def read_rois(work):
    df = pd.read_csv(work / "rois.csv", dtype=str, keep_default_na=False)
    return df[df.kind == "roi"].reset_index(drop=True)


def pad_square(im, fill=(0, 0, 0)):
    w, h = im.size
    s = max(w, h)
    c = Image.new("RGB", (s, s), fill)
    c.paste(im, ((s - w) // 2, (s - h) // 2))
    return c


# ---------------------------------------------------------------- inventory
def cmd_inventory(args, cfg):
    work, rep = cruise_dirs(cfg, args.name)
    src = Path(args.src)
    rows = []
    for day in sorted(p for p in src.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}", p.name)):
        for hour in sorted(p for p in day.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}_\d{4}", p.name)):
            for f in sorted(hour.glob("*.png")):
                if f.name.startswith("._"):
                    continue
                size = f.stat().st_size
                try:
                    with Image.open(f) as im:
                        w, h = im.size
                    kind = "full_frame" if (w, h) == FRAME_SIZE else "roi"
                except Exception:
                    w = h = 0
                    kind = "unreadable"
                rows.append((f.stem, day.name, hour.name, f"{day.name}/{hour.name}/{f.name}", w, h, size, kind))
    df = pd.DataFrame(rows, columns=["roi_id", "day", "hour_dir", "path", "width", "height", "bytes", "kind"])
    df.to_csv(work / "rois.csv", index=False)
    (work / "cruise.json").write_text(json.dumps({"name": args.name, "src": str(src),
                                                  "inventoried": time.strftime("%Y-%m-%d %H:%M")}, indent=2))
    by = df.pivot_table(index="hour_dir", columns="kind", values="roi_id", aggfunc="count", fill_value=0)
    for k in ["roi", "full_frame", "unreadable"]:
        if k not in by:
            by[k] = 0
    L = [f"# Inventory: {args.name}", "", f"Source: `{src}`", "",
         f"- PNG files: {len(df):,}; ROIs {int((df.kind == 'roi').sum()):,}; full frames "
         f"{int((df.kind == 'full_frame').sum()):,} ({df[df.kind == 'full_frame'].bytes.sum() / 1e9:.1f} GB); "
         f"unreadable {int((df.kind == 'unreadable').sum())}",
         f"- ROI images total {df[df.kind == 'roi'].bytes.sum() / 1e9:.2f} GB",
         "- Hour folders with no ROIs (full frames only): "
         + (", ".join(by.index[by.roi == 0]) or "none"), "",
         "| hour folder | ROIs | full frames | unreadable |", "|---|---|---|---|"]
    L += [f"| {h} | {r.roi:,} | {r.full_frame:,} | {r.unreadable} |" for h, r in by.iterrows()]
    (rep / "inventory.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:7]))


# ---------------------------------------------------------------- dedup
def fingerprints(df, src, cache, max_seconds=None):
    """md5, 64-bit dHash and a 16x16 grey thumbnail for every ROI (cached by path + bytes).
    With max_seconds, stops early, saves what it has and exits; re-run to continue."""
    old = {}
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        old = {(p, b): i for i, (p, b) in enumerate(zip(z["path"], z["bytes"]))}
        zm, zd, zt = z["md5"], z["dhash"], z["thumb"]
    md5, dh, th = [], np.zeros(len(df), np.uint64), np.zeros((len(df), 256), np.uint8)
    t0 = time.time()

    def save(k):
        np.savez(cache, path=df.path.to_numpy()[:k].astype(str), bytes=df.bytes.to_numpy()[:k].astype(str),
                 md5=np.array(md5[:k]), dhash=dh[:k], thumb=th[:k])

    for k, (p, b) in enumerate(zip(df.path, df.bytes)):
        i = old.get((p, b))
        if i is not None:
            md5.append(zm[i]); dh[k] = zd[i]; th[k] = zt[i]
            continue
        if max_seconds and time.time() - t0 > max_seconds:
            save(k)
            raise SystemExit(f"fingerprinted {k:,}/{len(df):,} ROIs; run the same command again to continue")
        raw = (src / p).read_bytes()
        md5.append(hashlib.md5(raw).hexdigest())
        with Image.open(src / p) as im:
            g = im.convert("L")
            a = np.asarray(g.resize((9, 8), Image.BILINEAR), dtype=np.int16)
            th[k] = np.asarray(g.resize((16, 16), Image.BILINEAR), dtype=np.uint8).ravel()
        bits = (a[:, 1:] < a[:, :-1]).ravel()
        dh[k] = np.uint64(int("".join("1" if x else "0" for x in bits), 2))
        if k % 5000 == 0 and k:
            print(f"  fingerprints {k:,}/{len(df):,} {time.time() - t0:.0f}s", flush=True)
    save(len(df))
    return np.array(md5), dh, th


def group_repeats(df, md5, dh, th, gap_s=GAP_S, size_tol=SIZE_TOL, hash_bits=HASH_BITS, corr=CORR):
    size_tol = float(size_tol)
    """Union-find over ROIs. Returns the root index of each ROI."""
    n = len(df)
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for idx in pd.DataFrame({"d": df.day.to_numpy(), "m": md5}).groupby(["d", "m"]).indices.values():
        for j in idx[1:]:
            union(idx[0], j)
    t = np.array([ts(r) for r in df.roi_id])
    W, H = df.width.astype(int).to_numpy(), df.height.astype(int).to_numpy()
    z = th.astype(np.float32)
    z = (z - z.mean(1, keepdims=True))
    z /= np.linalg.norm(z, axis=1, keepdims=True) + 1e-6
    day = df.day.to_numpy()
    order = np.lexsort((t, day))
    lo = 0
    for a in range(n):
        i = order[a]
        while day[order[lo]] != day[i] or t[i] - t[order[lo]] > gap_s:
            lo += 1
        if lo == a:
            continue
        c = order[lo:a]
        ok = (np.abs(W[c] - W[i]) <= size_tol * np.maximum(W[c], W[i])) & \
             (np.abs(H[c] - H[i]) <= size_tol * np.maximum(H[c], H[i]))
        c = c[ok]
        if not len(c):
            continue
        x = dh[c] ^ dh[i]
        bits = np.array([bin(int(v)).count("1") for v in x])
        c = c[bits <= hash_bits]
        if not len(c):
            continue
        c = c[z[c] @ z[i] >= corr]
        for j in c:
            union(i, int(j))
    return np.array([find(i) for i in range(n)]), t


def cmd_dedup(args, cfg):
    work, rep = cruise_dirs(cfg, args.name)
    df = read_rois(work)
    src = src_dir(work, args.src)
    md5, dh, th = fingerprints(df, src, work / "fingerprints.npz", args.max_seconds)
    root, t = group_repeats(df, md5, dh, th)
    g = pd.DataFrame({"root": root, "t": t, "roi_id": df.roi_id})
    first = g.sort_values("roi_id").groupby("root").roi_id.first()
    agg = g.groupby("root").agg(size=("t", "size"), span=("t", lambda s: s.max() - s.min()))
    out = pd.DataFrame({"roi_id": df.roi_id, "dup_group": first.reindex(root).to_numpy(),
                        "dup_size": agg["size"].reindex(root).to_numpy().astype(int)})
    span = agg["span"].reindex(root).to_numpy()
    out["dup_span_s"] = np.round(span).astype(int)
    out["persistent"] = span >= PERSIST_S
    out.to_csv(work / "dedup.csv", index=False)
    grp = out.drop_duplicates("dup_group")
    multi = grp[grp.dup_size > 1]
    L = [f"# Repeat captures: {args.name}", "",
         f"Rule (no frame positions on this cruise): same day, within {GAP_S} s, size within "
         f"{SIZE_TOL:.0%}, dHash within {HASH_BITS} bits and 16x16 thumbnail correlation >= {CORR}; "
         "or byte-identical. On the May-June set this rule gave a distinct-object count within 0.3 % of the "
         "position-based grouping; it catches long resting-object bursts but misses most scattered repeats.", "",
         f"- ROIs {len(out):,} -> distinct objects {len(grp):,}",
         f"- Objects captured more than once: {len(multi):,} (covering {multi.dup_size.sum():,} ROIs); "
         f"persistent (>= {PERSIST_S} s in view): {int(multi.persistent.sum()):,} "
         f"covering {int(multi[multi.persistent].dup_size.sum()):,} ROIs", "",
         "| day | ROIs | distinct objects |", "|---|---|---|"]
    out["day"] = df.day
    for d, s in out.groupby("day"):
        L.append(f"| {d} | {len(s):,} | {s.dup_group.nunique():,} |")
    L += ["", "| largest groups | ROIs | span (s) |", "|---|---|---|"]
    for r in multi.sort_values("dup_size", ascending=False).head(10).itertuples():
        L.append(f"| {r.dup_group} | {r.dup_size} | {r.dup_span_s} |")
    (rep / "dedup.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:6]))


# ---------------------------------------------------------------- package
def cmd_package(args, cfg):
    work, _ = cruise_dirs(cfg, args.name)
    df = read_rois(work)
    src = src_dir(work, args.src)
    out = Path(args.out) if args.out else work / f"{args.name}_rois.tar"
    with tarfile.open(out, "w") as tf:
        for f in ["rois.csv", "dedup.csv", "cruise.json"]:
            if (work / f).exists():
                tf.add(work / f, arcname=f)
        for k, p in enumerate(df.path):
            tf.add(src / p, arcname=f"rois/{p}")
    print(f"wrote {out} ({out.stat().st_size / 1e9:.2f} GB, {len(df):,} ROIs)")


# ---------------------------------------------------------------- embed
def cmd_embed(args, cfg):
    import torch
    from cpics.embed import MODELS, ROIs, load_model
    work, _ = cruise_dirs(cfg, args.name)
    df = read_rois(work)
    src = src_dir(work, args.src)
    out = work / "embeddings"
    out.mkdir(exist_ok=True)
    ids_file, npy_file = out / f"{args.model}_ids.csv", out / f"{args.model}.npy"
    if not args.force and ids_file.exists() and npy_file.exists() and \
            pd.read_csv(ids_file, dtype=str).roi_id.tolist() == df.roi_id.tolist():
        print(f"{npy_file} is up to date; use --force to recompute")
        return
    device = "cuda" if torch.cuda.is_available() else (
        "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")
    spec = MODELS[args.model]
    model, fwd = load_model(spec, device)
    paths = [str(src / p) for p in df.path]
    dl = torch.utils.data.DataLoader(ROIs(paths, spec), batch_size=args.batch, num_workers=args.workers)
    feats, t0 = [], time.time()
    with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
        for k, x in enumerate(dl):
            f = fwd(x.to(device)).float()
            feats.append(torch.nn.functional.normalize(f, dim=1).cpu().numpy().astype(np.float16))
            if k % 20 == 0:
                print(f"{min((k + 1) * args.batch, len(paths)):,}/{len(paths):,} ROIs {time.time() - t0:.0f}s",
                      flush=True)
    E = np.concatenate(feats)
    np.save(npy_file, E)
    df[["roi_id"]].to_csv(ids_file, index=False)
    (out / f"{args.model}_meta.json").write_text(json.dumps(dict(
        model=spec["name"], n=int(E.shape[0]), dim=int(E.shape[1]), device=device,
        seconds=round(time.time() - t0), date=time.strftime("%Y-%m-%d %H:%M")), indent=2))
    print(f"wrote {npy_file} {E.shape}")


# ---------------------------------------------------------------- classify
def load_embeddings(d, model, ids):
    E = np.load(d / f"{model}.npy").astype(np.float32)
    have = pd.read_csv(d / f"{model}_ids.csv", dtype=str).roi_id
    pos = pd.Series(np.arange(len(have)), index=have)
    missing = set(ids) - set(have)
    if missing:
        raise SystemExit(f"{len(missing)} ROIs have no {model} embedding; run the embed step")
    return E[pos.loc[list(ids)].to_numpy()]


def fit_baseline(cfg, model):
    """The Phase 1 baseline, refit exactly as cpics.baseline does; also its eval_newdays confusions."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.preprocessing import StandardScaler
    from cpics.baseline import TARGET_RECALL, features, threshold_for_recall
    df = pd.read_csv(cfg["labels_dir"] / "labels.csv", dtype=str, keep_default_na=False)
    df["y"] = df.triage.replace({"other": "artifact"})
    lab = df[df.y.isin(CLASSES)]
    train = lab[lab.split == "train"].drop_duplicates("dup_group")
    val = lab[lab.split == "val"].drop_duplicates("dup_group")
    ev = lab[lab.split == "eval_newdays"].drop_duplicates("dup_group")
    Xtr = features(model, train, cfg)
    sc = StandardScaler().fit(Xtr)
    Xv = sc.transform(features(model, val, cfg))
    best = None
    for C in [0.01, 0.1, 1.0]:
        clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(sc.transform(Xtr), train.y)
        f1 = f1_score(val.y, clf.predict(Xv), average="macro")
        if best is None or f1 > best[0]:
            best = (f1, C, clf)
    f1, C, clf = best
    org = list(clf.classes_).index("organism")
    thr = threshold_for_recall(val.y.to_numpy(), clf.predict_proba(Xv)[:, org], TARGET_RECALL)
    Pe = clf.predict_proba(sc.transform(features(model, ev, cfg)))
    ev_pred = clf.classes_[Pe.argmax(1)]
    return dict(clf=clf, scaler=sc, C=C, val_f1=f1, thr=thr, n_train=len(train),
                eval_true=ev.y.to_numpy(), eval_pred=ev_pred)


def adjusted_shares(true, pred, observed, classes, return_fit=False):
    """Correct observed predicted-class shares for the confusions seen on a labeled set.
    observed = M^T q, M[i, j] = P(pred j | true i); solve for q >= 0, sum 1 (least squares)."""
    from scipy.optimize import nnls
    k = len(classes)
    M = np.zeros((k, k))
    for i, c in enumerate(classes):
        sel = true == c
        if sel.sum() == 0:
            M[i, i] = 1.0
            continue
        for j, d in enumerate(classes):
            M[i, j] = (pred[sel] == d).mean()
    A = np.vstack([M.T, 10 * np.ones(k)])
    b = np.r_[observed, 10.0]
    q, _ = nnls(A, b)
    q = q / q.sum()
    if return_fit:
        return q, float(np.abs(M.T @ q - observed).sum())
    return q


def share_table(frame, col="pred"):
    s = frame[col].value_counts(normalize=True)
    return {c: float(s.get(c, 0.0)) for c in CLASSES}


def cmd_classify(args, cfg):
    import joblib
    work, rep = cruise_dirs(cfg, args.name)
    df = read_rois(work).merge(pd.read_csv(work / "dedup.csv", dtype={"roi_id": str, "dup_group": str}),
                               on="roi_id", how="left")
    df["dup_group"] = df.dup_group.fillna(df.roi_id)
    mfile = cfg["work_dir"] / "models" / f"{args.model}_logreg.joblib"
    lab_hash = hashlib.md5((cfg["labels_dir"] / "labels.csv").read_bytes()).hexdigest()
    m = joblib.load(mfile) if mfile.exists() else None
    if m is None or m.get("labels_md5") != lab_hash or args.refit:
        m = fit_baseline(cfg, args.model)
        m["labels_md5"] = lab_hash
        mfile.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(m, mfile)
    clf, sc = m["clf"], m["scaler"]
    X = load_embeddings(work / "embeddings", args.model, df.roi_id)
    P = clf.predict_proba(sc.transform(X))
    cls = list(clf.classes_)
    for c in CLASSES:
        df[f"p_{c}"] = P[:, cls.index(c)]
    pc = [f"p_{c}" for c in CLASSES]
    df["pred"] = np.array(CLASSES)[df[pc].to_numpy().argmax(1)]
    df["organism_flag"] = df.p_organism >= m["thr"]
    df[["roi_id", "dup_group", "day", "hour_dir", "width", "height", *pc, "pred", "organism_flag"]] \
        .to_csv(work / "predictions.csv", index=False, float_format="%.4f")

    # one row per object: mean probability over its captures
    obj = df.groupby("dup_group").agg(day=("day", "first"), hour_dir=("hour_dir", "first"),
                                      n_captures=("roi_id", "size"), width=("width", lambda s: s.astype(int).median()),
                                      height=("height", lambda s: s.astype(int).median()),
                                      **{c: (c, "mean") for c in pc}).reset_index()
    obj["pred"] = np.array(CLASSES)[obj[pc].to_numpy().argmax(1)]
    obj["confidence"] = obj[pc].max(axis=1)
    obj["organism_flag"] = obj.p_organism >= m["thr"]
    obj.to_csv(work / "objects.csv", index=False, float_format="%.4f")

    so, sr = share_table(obj), share_table(df)
    obs = np.array([so[c] for c in CLASSES])
    adj, misfit = adjusted_shares(m["eval_true"], m["eval_pred"], obs, CLASSES, return_fit=True)
    # misfit = L1 gap between the observed mix and the best mix the eval confusions can produce.
    # A large gap means the model behaves differently on this cruise than on the eval days, and the
    # correction is not meaningful.
    corr_ok = misfit <= MAX_MISFIT
    rng = np.random.default_rng(0)
    boot = []
    n = len(m["eval_true"])
    for _ in range(500):
        i = rng.integers(0, n, n)
        boot.append(adjusted_shares(m["eval_true"][i], m["eval_pred"][i], obs, CLASSES))
    lo, hi = np.percentile(np.array(boot), [5, 95], axis=0)
    ev_counts = pd.Series(m["eval_true"]).value_counts()

    by_day = obj.groupby("day").pred.value_counts().unstack(fill_value=0).reindex(columns=CLASSES, fill_value=0)
    by_hour = obj.groupby("hour_dir").pred.value_counts().unstack(fill_value=0).reindex(columns=CLASSES, fill_value=0)
    by_hour.to_csv(rep / "objects_by_hour.csv")
    by_day.to_csv(rep / "objects_by_day.csv")

    ms, og = so["marine_snow"], so["organism"]
    L = [f"# Preliminary class shares: {args.name}", "",
         f"Run {time.strftime('%Y-%m-%d %H:%M')}. Model: {args.model} embeddings + logistic regression "
         f"(Phase 1 baseline, C={m['C']}, trained on {m['n_train']:,} labeled May-June 2026 objects; "
         "no January images were labeled). **Preliminary.**", "",
         f"- ROIs classified: {len(df):,}; distinct objects: {len(obj):,} (repeat captures averaged)",
         f"- Marine snow : organism (objects) = {ms:.0%} : {og:.0%} "
         f"(about {ms / og:.1f} marine-snow particles per organism)" if og > 0 else "- no organisms predicted",
         f"- Objects above the high-recall organism threshold (an upper bound on organisms): "
         f"{int(obj.organism_flag.sum()):,} ({obj.organism_flag.mean():.0%})", "",
         "| class | share of objects (model) | share of ROIs (model) | objects, corrected for known model "
         "confusions (90% range) |", "|---|---|---|---|"]
    for i, c in enumerate(CLASSES):
        cc = f"{adj[i]:.1%} ({lo[i]:.0%}-{hi[i]:.0%})" if corr_ok else "n/a"
        L.append(f"| {LABEL[c]} | {so[c]:.1%} | {sr[c]:.1%} | {cc} |")
    ev_txt = (f"{n} objects from unlabeled May-June days, labeled by Jeremy: "
              + ", ".join(f"{LABEL[c].lower()} {int(ev_counts.get(c, 0))}" for c in CLASSES))
    if corr_ok:
        L += ["", f"The corrected column inverts the confusion matrix the model showed on the eval_newdays set "
              f"({ev_txt}). It assumes this cruise confuses classes the way those days did, which is untested; "
              "read the two columns as a range, not a precise value.", ""]
    else:
        L += ["", f"**Correction not applicable** (misfit {misfit:.2f} > {MAX_MISFIT}). No mix of true classes, "
              f"confused the way the model confused them on the eval_newdays set ({ev_txt}), can produce the "
              "predicted mix seen on this cruise. The model is behaving differently here than on May-June days "
              "(a domain shift), so the class shares above should be treated as rough and checked by eye.", ""]
    L += [
          "## By day (objects)", "", "| day | objects | " + " | ".join(LABEL[c] for c in CLASSES) + " |",
          "|---" * (len(CLASSES) + 2) + "|"]
    for d, r in by_day.iterrows():
        t = r.sum()
        L.append(f"| {d} | {t:,} | " + " | ".join(f"{r[c] / t:.0%}" for c in CLASSES) + " |")
    L += ["", "## Median ROI size by predicted class (pixels, objects)", "",
          "| class | objects | median width | median height |", "|---|---|---|---|"]
    for c in CLASSES:
        s = obj[obj.pred == c]
        if len(s):
            L.append(f"| {LABEL[c]} | {len(s):,} | {s.width.median():.0f} | {s.height.median():.0f} |")
    L += ["", "## Caveats for presenting", "",
          "- Trained on late-spring (May-June) imagery; January water, particle types and organisms differ. "
          "No January ROI has been checked by a person yet.",
          "- On new May-June days the baseline found 93% of organisms but only ~1 in 7 of its organism calls "
          "were organisms, so the raw organism share is likely an overestimate.",
          "- The training labels pre-date the v1.0 annotation rules (annotator agreement was moderate, "
          "kappa 0.34-0.57), and the 'blurry' class is now a focus flag rather than a class.",
          "- Repeat captures are grouped approximately (no frame positions on this cruise)."]
    (rep / "summary.md").write_text("\n".join(L) + "\n")
    (rep / "summary.json").write_text(json.dumps(dict(
        n_rois=len(df), n_objects=len(obj), share_objects=so, share_rois=sr,
        correction_misfit=misfit, correction_applicable=bool(corr_ok),
        share_objects_corrected={c: float(adj[i]) for i, c in enumerate(CLASSES)},
        corrected_lo={c: float(lo[i]) for i, c in enumerate(CLASSES)},
        corrected_hi={c: float(hi[i]) for i, c in enumerate(CLASSES)},
        organism_flag_share=float(obj.organism_flag.mean())), indent=2))
    plot_shares(by_day, so, adj if corr_ok else None, rep / "class_shares.png", args.title or args.name)
    print("\n".join(L[:16]))


def plot_shares(by_day, so, adj, out, name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = [("All objects (model)", np.array([so[c] for c in CLASSES]))]
    if adj is not None:
        rows.append(("All objects (corrected)", np.asarray(adj)))
    n_top = len(rows)
    for d, r in by_day.iterrows():
        rows.append((f"{d[:4]}-{d[4:6]}-{d[6:]}  (n={int(r.sum()):,})", (r / r.sum()).to_numpy()))
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(rows) + 1.4), dpi=200)
    for k, (lab, v) in enumerate(rows):
        left = 0
        for c, x in zip(CLASSES, v):
            ax.barh(k, x, left=left, color=COLOR[c], edgecolor="white", linewidth=0.8)
            if x >= 0.06:
                ax.text(left + x / 2, k, f"{x:.0%}", ha="center", va="center", fontsize=8, color="black")
            left += x
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.axhline(n_top - 0.5, color="#444", lw=0.6)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.legend(handles=[matplotlib.patches.Patch(color=COLOR[c], label=LABEL[c]) for c in CLASSES],
              ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, fontsize=9)
    ax.set_title(f"CPICS {name}: predicted class of each distinct particle (preliminary)", fontsize=10, pad=26)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ---------------------------------------------------------------- map
MAP_COLS = ["dup_group", "day", "hour_dir", "n_captures", "width", "height"] + [f"p_{c}" for c in CLASSES] + \
           ["pred", "confidence", "organism_flag", "x", "y", "region"]


def thumb(path, px=96):
    with Image.open(path) as im:
        return pad_square(im.convert("RGB")).resize((px, px), Image.BICUBIC)


def cmd_map(args, cfg):
    work, rep = cruise_dirs(cfg, args.name)
    obj = pd.read_csv(work / "objects.csv", dtype={"dup_group": str, "day": str, "hour_dir": str})
    X = load_embeddings(work / "embeddings", args.model, obj.dup_group)
    if args.method == "umap":
        import umap
        xy = umap.UMAP(n_neighbors=args.neighbors, min_dist=0.1, metric="cosine", random_state=0).fit_transform(X)
    else:
        from sklearn.manifold import TSNE
        xy = TSNE(metric="cosine", init="pca", random_state=0).fit_transform(X)
    from sklearn.cluster import KMeans
    obj["x"], obj["y"] = xy[:, 0], xy[:, 1]
    km = KMeans(n_clusters=args.regions, n_init=10, random_state=0).fit(xy)
    # number regions left-to-right, top-to-bottom so the figure reads in order
    cen = pd.DataFrame(km.cluster_centers_, columns=["x", "y"])
    order = cen.assign(r=np.round(-cen.y / (np.ptp(xy[:, 1]) / 3))).sort_values(["r", "x"]).index
    remap = {old: new + 1 for new, old in enumerate(order)}
    obj["region"] = pd.Series(km.labels_).map(remap).to_numpy()
    obj.to_csv(work / "map.csv", index=False, float_format="%.4f")
    # compact copy in reports/ so figures and atlases can be rebuilt on the Mac without the workstation
    obj[MAP_COLS].to_csv(rep / "map.csv.gz", index=False, float_format="%.3f", compression="gzip")
    cmd_figures(args, cfg, obj=obj)
    if args.atlas_sample:
        atlas_json(obj, read_rois(work).set_index("roi_id"), src_dir(work, args.src), work, args.atlas_sample)


def summarise_regions(obj, n_ex, seed=0):
    """Majority class per region, its share, a short label, and example objects of the region's main classes,
    drawn at random (seeded) from the region's members of those classes."""
    cen = obj.groupby("region")[["x", "y"]].mean()
    regs = []
    for r, s in obj.groupby("region"):
        vc = s.pred.value_counts(normalize=True)
        top, share = vc.index[0], float(vc.iloc[0])
        sec, sec_share = (vc.index[1], float(vc.iloc[1])) if len(vc) > 1 else ("", 0.0)
        mixed = share < 0.6
        text = (f"Mixed: {LABEL[top].lower()} {share:.0%}, {LABEL[sec].lower()} {sec_share:.0%}" if mixed
                else f"Mostly {LABEL[top].lower()} ({share:.0%})")
        want = [(top, n_ex - n_ex // 2), (sec, n_ex // 2)] if mixed and sec else [(top, n_ex)]
        ex = []
        for c, k in want:
            pool = s[s.pred == c]
            ex += pool.sample(min(k, len(pool)), random_state=seed * 1000 + int(r)).dup_group.tolist()
        regs.append(dict(region=int(r), n=len(s), share_all=len(s) / len(obj), majority=top, majority_share=share,
                         second=sec, second_share=sec_share, text=text, examples=" ".join(ex)))
    return pd.DataFrame(regs), cen


def organism_examples(obj, n, seed=0, min_conf=0.0):
    """A seeded random draw of predicted organisms (optionally only those the model is at least min_conf sure of)."""
    pool = obj[(obj.pred == "organism") & (obj.confidence >= min_conf)]
    return pool.sample(min(n, len(pool)), random_state=seed).dup_group.tolist(), len(pool)


def cmd_figures(args, cfg, obj=None):
    """Region summary + figures from the map. Re-runnable on the Mac from reports/cruises/<name>/map.csv.gz
    (no embeddings or GPU needed; needs the ROI images for the example strips: --src)."""
    work, rep = cruise_dirs(cfg, args.name)
    if obj is None:
        f = work / "map.csv" if (work / "map.csv").exists() else rep / "map.csv.gz"
        obj = pd.read_csv(f, dtype={"dup_group": str, "day": str, "hour_dir": str})
    rois = read_rois(work).set_index("roi_id")
    regs, cen = summarise_regions(obj, args.examples, args.seed)
    org_ids, org_pool = organism_examples(obj, args.organisms, args.seed, args.organism_min_conf)
    regs.drop(columns=["examples"]).to_csv(rep / "map_regions.csv", index=False, float_format="%.3f")
    ex = regs[["region", "examples"]].copy()
    ex.loc[len(ex)] = ["organisms", " ".join(org_ids)]
    ex.assign(seed=args.seed).to_csv(rep / "map_region_examples.csv", index=False)
    figures(obj, regs, cen, rois, src_dir(work, args.src), rep, args.title or args.name,
            org_ids, org_pool, args.organism_min_conf)
    print(regs[["region", "n", "text"]].to_string(index=False))
    print(f"figures in {rep}")


def figures(obj, regs, cen, rois, src, rep, name, org_ids=(), org_pool=0, org_min_conf=0.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.offsetbox import AnnotationBbox, OffsetImage
    handles = [matplotlib.lines.Line2D([], [], ls="", marker="o", ms=7, color=COLOR[c],
                                       label=f"{LABEL[c]} ({(obj.pred == c).mean():.0%})") for c in CLASSES]
    by_id = obj.set_index("dup_group")

    def scatter(ax, mark=()):
        o = obj.iloc[np.random.default_rng(0).permutation(len(obj))]
        ax.scatter(o.x, o.y, s=2.5 if len(o) > 5000 else 6, c=o.pred.map(COLOR), alpha=0.6, linewidths=0,
                   rasterized=True)
        if len(mark):
            m = by_id.loc[list(mark)]
            ax.scatter(m.x, m.y, s=26, facecolors="none", edgecolors="black", linewidths=0.9, zorder=3)
        for r, p in cen.iterrows():
            ax.text(p.x, p.y, str(r), ha="center", va="center", fontsize=12, weight="bold", color="black",
                    bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec="black", lw=0.8, alpha=0.9), zorder=4)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)

    def tile(ax, rid, xy, zoom, lw=1.5):
        try:
            im = thumb(src / rois.loc[rid, "path"], 96)
        except Exception:
            return
        ax.add_artist(AnnotationBbox(OffsetImage(np.asarray(im), zoom=zoom), xy, frameon=True, pad=0.04,
                                     bboxprops=dict(ec=COLOR[by_id.loc[rid, "pred"]], lw=lw)))

    # 1. the map alone
    fig, ax = plt.subplots(figsize=(9, 7.5), dpi=200)
    scatter(ax)
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=5, frameon=False,
              fontsize=9, title="Predicted class (share of particles)", title_fontsize=9)
    ax.set_title(f"CPICS, {name}: {len(obj):,} particles arranged by image similarity (DINOv2 + UMAP)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(rep / "cluster_map.png")
    plt.close(fig)

    # 2. slide (16:9): map, a strip of predicted organisms under it, and the region key with examples
    k, dpi = len(regs), 150
    W, H = 16, 9
    fig = plt.figure(figsize=(W, H), dpi=dpi)
    fig.text(0.012, 0.955, f"CPICS, {name}: {len(obj):,} particles arranged by image similarity",
             fontsize=16, weight="bold")
    fig.text(0.012, 0.918, "Each dot is one particle, coloured by the model's predicted class; similar-looking "
             "particles sit together. “Blurry” = too out of focus to classify. "
             "Preliminary: model trained on May–June 2026 labels.", fontsize=10.5, color="#333")
    has_org = len(org_ids) > 0
    map_box = [0.01, 0.33, 0.50, 0.56] if has_org else [0.01, 0.09, 0.50, 0.80]
    ax = fig.add_axes(map_box)
    scatter(ax, mark=org_ids)
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=5, frameon=False,
              fontsize=10.5, handletextpad=0.2, columnspacing=1.2)
    if has_org:
        cols = int(np.ceil(len(org_ids) / 2))
        strip = fig.add_axes([0.012, 0.015, 0.50, 0.215])
        strip.set_xlim(0, cols); strip.set_ylim(2, 0); strip.axis("off")
        cell_in = min(W * 0.50 / cols, H * 0.215 / 2)
        z = 0.86 * cell_in * 72 / 96
        for j, rid in enumerate(org_ids):
            tile(strip, rid, (j % cols + 0.5, j // cols + 0.5), z)
        how = f"model confidence ≥ {org_min_conf:.0%}, " if org_min_conf > 0 else ""
        fig.text(0.012, 0.245, f"Predicted organisms: {len(org_ids)} drawn at random ({how}from {org_pool:,}); "
                 "circled on the map", fontsize=11, weight="bold")
    key_h = 0.84
    key = fig.add_axes([0.53, 0.04, 0.46, key_h])
    key.set_xlim(0, 1); key.set_ylim(k, 0); key.axis("off")
    zoom = 0.80 * (H * key_h / k) * 72 / 96
    n_ex = max([len(r.split()) for r in regs.examples] + [1])
    x0, dx = 1.0 - n_ex * 0.112 + 0.056, 0.112
    for i, r in enumerate(regs.itertuples()):
        y = i + 0.5
        key.text(0.02, y, str(r.region), ha="center", va="center", fontsize=12, weight="bold",
                 bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec="black", lw=0.8))
        key.add_patch(matplotlib.patches.Rectangle((0.055, y - 0.3), 0.012, 0.6, color=COLOR[r.majority]))
        key.text(0.08, y - 0.13, r.text, va="center", fontsize=11, weight="bold")
        key.text(0.08, y + 0.2, f"{r.n:,} particles ({r.share_all:.0%} of all)", va="center", fontsize=9.5,
                 color="#444")
        for j, rid in enumerate(r.examples.split()):
            tile(key, rid, (x0 + j * dx, y), zoom)
    fig.savefig(rep / "cluster_map_slide.png")
    plt.close(fig)


def atlas_json(obj, rois, src, work, n):
    """Small thumbnails for an interactive atlas page: a stratified sample of up to n objects."""
    import base64
    import io
    s = pd.concat([g.sample(min(len(g), max(1, int(n * len(g) / len(obj)))), random_state=0)
                   for _, g in obj.groupby("region")])
    out = []
    for r in s.itertuples():
        try:
            im = thumb(src / rois.loc[r.dup_group, "path"], 64)
        except Exception:
            continue
        b = io.BytesIO()
        im.save(b, "WEBP", quality=70)
        out.append(dict(id=r.dup_group, x=round(r.x, 3), y=round(r.y, 3), region=int(r.region), pred=r.pred,
                        conf=round(r.confidence, 3), n=int(r.n_captures), w=int(r.width), h=int(r.height),
                        day=r.day, img=base64.b64encode(b.getvalue()).decode()))
    (work / "atlas_sample.json").write_text(json.dumps(out))
    print(f"atlas sample: {len(out)} objects")


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["inventory", "dedup", "package", "embed", "classify", "map", "figures"])
    ap.add_argument("--name", required=True, help="short cruise name, e.g. jan2026")
    ap.add_argument("--src", help="cruise image folder (<src>/<day>/<hour>/*.png)")
    ap.add_argument("--config")
    ap.add_argument("--model", default="dinov2")
    ap.add_argument("--out", help="package: tar path")
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--refit", action="store_true", help="classify: refit the baseline even if cached")
    ap.add_argument("--method", choices=["umap", "tsne"], default="umap")
    ap.add_argument("--neighbors", type=int, default=30)
    ap.add_argument("--regions", type=int, default=8)
    ap.add_argument("--examples", type=int, default=4, help="map/figures: example images per region")
    ap.add_argument("--seed", type=int, default=0, help="map/figures: seed for the random example draws")
    ap.add_argument("--organisms", type=int, default=18, help="map/figures: predicted organisms in the slide strip")
    ap.add_argument("--organism-min-conf", type=float, default=0.0,
                    help="map/figures: draw strip organisms only from those with model confidence >= this")
    ap.add_argument("--title", help="cruise name for figure titles, e.g. 'January 2026 Chance USV cruise'")
    ap.add_argument("--atlas-sample", type=int, default=4000)
    ap.add_argument("--max-seconds", type=float, help="dedup: stop fingerprinting after this long (re-run continues)")
    args = ap.parse_args(argv)
    if args.step == "inventory" and not args.src:
        ap.error("inventory needs --src")
    cfg = config.load(args.config)
    {"inventory": cmd_inventory, "dedup": cmd_dedup, "package": cmd_package, "embed": cmd_embed,
     "classify": cmd_classify, "map": cmd_map, "figures": cmd_figures}[args.step](args, cfg)


if __name__ == "__main__":
    main()
