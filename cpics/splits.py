"""Assign every ROI to a split, by survey day (never by random image).

    python -m cpics.splits --init   # choose val/test days + new-day eval sample, write configs/splits.yaml
    python -m cpics.splits --resample-eval   # keep val/test days; redraw eval, keeping labeled ROIs
    python -m cpics.splits          # apply configs/splits.yaml to labels/labels.csv

Split values
    train          labeled rows here are training data; unlabeled rows are the pool for labeling queues
    val            whole days held out for model selection / thresholds
    test           whole days held out for the final number; never tuned on
    eval_newdays   ~400 ROIs sampled from days with no labels at all; label them, never train on them
    eval_reserved  the rest of the 10-second blocks the eval sample came from (kept out of training
                   so near-duplicate bursts can't leak into the eval set)

configs/splits.yaml is the frozen record; commit it. Re-running --init overwrites it.
"""
import argparse
import itertools
import random
from pathlib import Path

import pandas as pd
import yaml

from cpics import config

CLASSES = ["organism", "ring", "marine_snow", "blurry"]
SPLITS_YAML = config.REPO / "configs" / "splits.yaml"


def block_of(roi_id, fine=False):
    # roi_id = YYYYMMDD_HHMMSS.mmm.k  -> YYYYMMDD_HHMMS (10-second block).
    # Capture is very bursty (20260521 has 7,125 ROIs in 13 minutes), so blocks must be short
    # to keep the reserved area small while still separating near-duplicate bursts.
    # On burst days (median 10-s block > 20 ROIs) use 1-second blocks instead.
    return roi_id[:15] if fine else roi_id[:14]


def choose_days(df):
    lab = df[df.triage.isin(CLASSES)]
    per_day = lab.groupby("day").triage.value_counts().unstack(fill_value=0).reindex(columns=CLASSES, fill_value=0)
    per_day = per_day[per_day.sum(axis=1) >= 100]          # only days with a usable number of labels
    total = per_day.sum()
    share = total / total.sum()
    best = None
    days = sorted(per_day.index)
    for val in itertools.combinations(days, 2):
        rest = [d for d in days if d not in val]
        for test in itertools.combinations(rest, 2):
            score = 0.0
            ok = True
            for grp in (val, test):
                s = per_day.loc[list(grp)].sum()
                frac = s.sum() / total.sum()
                if s["organism"] < 80 or s["ring"] < 15 or s["marine_snow"] < 40:
                    ok = False
                    break
                score += abs(frac - 0.15) * 4 + (s / s.sum() - share).abs().sum()
            if ok and (best is None or score < best[0]):
                best = (score, list(val), list(test))
    return best[1], best[2]


def choose_eval(df, excluded_days, n_total, seed, keep_ids=()):
    """One ROI per distinct object (dup group) on days with no labels.

    Quota per day is proportional to the number of distinct objects that day, so burst days full of
    repeat captures (20260521: 7,125 ROIs, 33 objects) don't dominate. ROIs in `keep_ids` (already
    labeled) are kept first, at most one per object; the rest of the quota is sampled at random."""
    rng = random.Random(seed)
    counts = df.groupby("day").triage.apply(lambda s: ((s != "") & (df.loc[s.index, "split"] != "eval_newdays")).sum())
    new_days = sorted(d for d in df.day.unique() if counts[d] == 0 and d not in excluded_days)
    reps = df[df.day.isin(new_days)].drop_duplicates("dup_group")      # earliest member of each object
    objs = reps.groupby("day").size()
    quota = {d: max(4, round(n_total * objs[d] / objs.sum())) for d in new_days}
    by_id = df.set_index("roi_id")
    chosen, seen = [], set()
    for r in sorted(keep_ids):
        if r in by_id.index and by_id.at[r, "day"] in new_days and by_id.at[r, "dup_group"] not in seen:
            chosen.append(r)
            seen.add(by_id.at[r, "dup_group"])
    for d in new_days:
        have = sum(by_id.at[r, "day"] == d for r in chosen)
        pool = sorted(reps[(reps.day == d) & ~reps.dup_group.isin(seen)].roi_id)
        for r in rng.sample(pool, max(0, min(quota[d] - have, len(pool)))):
            chosen.append(r)
            seen.add(by_id.at[r, "dup_group"])
    chosen = sorted(chosen)
    blocks = sorted({block_of(r, fine=(by_id.at[r, "day"] in BURST_DAYS(df))) for r in chosen})
    return new_days, blocks, chosen


def BURST_DAYS(df, _cache={}):
    key = id(df)
    if key not in _cache:
        b = df.roi_id.map(block_of)
        med = b.groupby(df.day).apply(lambda s: s.value_counts().median())
        _cache[key] = set(med[med > 20].index)
    return _cache[key]


def apply(df, spec):
    split = pd.Series("train", index=df.index)
    split[df.day.isin(spec["val_days"])] = "val"
    split[df.day.isin(spec["test_days"])] = "test"
    blocks = set(spec["eval_blocks"])
    reserved = df.roi_id.str[:14].isin(blocks) | df.roi_id.str[:15].isin(blocks)
    eval_ids = set(spec["eval_newdays"])
    if "dup_group" in df.columns:   # every repeat capture of an eval object is held out too
        reserved |= df.dup_group.isin(set(df.loc[df.roi_id.isin(eval_ids), "dup_group"]))
    split[reserved] = "eval_reserved"
    split[df.roi_id.isin(eval_ids)] = "eval_newdays"
    return split


def report(df, spec, out):
    L = ["# Split report", "",
         f"- val days: {', '.join(spec['val_days'])}",
         f"- test days: {', '.join(spec['test_days'])}",
         f"- eval_newdays: {len(spec['eval_newdays'])} ROIs, one per distinct object, on {len(spec['new_days'])} unlabeled days. "
         f"Every repeat capture of those objects, and the 10 s (1 s on burst days) block around each, is eval_reserved.", "",
         "| split | ROIs | labeled | " + " | ".join(CLASSES) + " | needs_box |",
         "|---|---|---|" + "---|" * len(CLASSES) + "---|"]
    for s in ["train", "val", "test", "eval_newdays", "eval_reserved"]:
        g = df[df.split == s]
        vc = g.triage.value_counts()
        L.append(f"| {s} | {len(g):,} | {(g.triage != '').sum():,} | " +
                 " | ".join(str(vc.get(c, 0)) for c in CLASSES) + f" | {(g.needs_box == 'true').sum()} |")
    L += ["", "## eval_newdays sample by day", "", "| day | ROIs on day | distinct objects | sampled |", "|---|---|---|---|"]
    ev = df[df.split == "eval_newdays"].groupby("day").size()
    for d in spec["new_days"]:
        L.append(f"| {d} | {(df.day == d).sum():,} | {df[df.day == d].dup_group.nunique():,} | {ev.get(d, 0)} |")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L[:14]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--n-eval", type=int, default=400)
    ap.add_argument("--resample-eval", action="store_true",
                    help="keep val/test days, redraw the eval sample (one ROI per distinct object)")
    ap.add_argument("--keep", default=str(config.REPO / "labels" / "eval_newdays_labels.csv"),
                    help="ROIs to keep in the eval sample (already labeled)")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    path = cfg["labels_dir"] / "labels.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    if "dup_group" not in df.columns:
        raise SystemExit("labels.csv has no dup_group column: run `python -m cpics.dedup` first")
    if args.init or args.resample_eval:
        if args.init:
            val, test = choose_days(df)
        else:
            old = yaml.safe_load(SPLITS_YAML.read_text())
            val, test = old["val_days"], old["test_days"]
        keep = []
        if args.keep and Path(args.keep).exists():
            keep = pd.read_csv(args.keep, dtype=str, keep_default_na=False).roi_id.tolist()
        new_days, blocks, sample = choose_eval(df, set(val) | set(test), args.n_eval, cfg["seed"], keep)
        spec = dict(seed=cfg["seed"], val_days=val, test_days=test, new_days=new_days,
                    eval_blocks=blocks, eval_newdays=sample)
        SPLITS_YAML.write_text("# Frozen split assignment. Generated by `python -m cpics.splits --init`.\n" +
                               yaml.safe_dump(spec, sort_keys=False))
    spec = yaml.safe_load(SPLITS_YAML.read_text())
    df["split"] = apply(df, spec)
    df.to_csv(path, index=False)
    ev = df[df.split == "eval_newdays"][["roi_id", "day", "path", "width", "height", "dup_size", "dup_span_s"]]
    ev.assign(triage="", needs_box="", notes="").to_csv(cfg["labels_dir"] / "eval_newdays_to_label.csv", index=False)
    report(df, spec, cfg["labels_dir"] / "splits_report.md")


if __name__ == "__main__":
    main()
