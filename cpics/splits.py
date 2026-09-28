"""Assign every ROI to a split, by survey day (never by random image).

    python -m cpics.splits --init   # choose val/test days + new-day eval blocks, write configs/splits.yaml
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


def choose_eval_blocks(df, excluded_days, n_total, per_block, seed):
    rng = random.Random(seed)
    counts = df.groupby("day").triage.apply(lambda s: (s != "").sum())
    new_days = sorted(d for d in df.day.unique() if counts[d] == 0 and d not in excluded_days)
    vol = df[df.day.isin(new_days)].groupby("day").size()
    quota = {d: max(4, round(n_total * vol[d] / vol.sum())) for d in new_days}
    blocks, sample = [], []
    for d in new_days:
        g = df[df.day == d].copy()
        fine = g.roi_id.map(block_of).value_counts().median() > 20
        g["block"] = g.roi_id.map(lambda r: block_of(r, fine))
        order = sorted(g.block.unique())
        rng.shuffle(order)
        need = quota[d]
        for b in order:
            if need <= 0:
                break
            ids = sorted(g[g.block == b].roi_id)
            take = rng.sample(ids, min(per_block, len(ids), need))
            blocks.append(b)
            sample.extend(sorted(take))
            need -= len(take)
    return new_days, sorted(blocks), sorted(sample)


def apply(df, spec):
    split = pd.Series("train", index=df.index)
    split[df.day.isin(spec["val_days"])] = "val"
    split[df.day.isin(spec["test_days"])] = "test"
    blocks = set(spec["eval_blocks"])
    reserved = df.roi_id.str[:14].isin(blocks) | df.roi_id.str[:15].isin(blocks)
    split[reserved] = "eval_reserved"
    split[df.roi_id.isin(set(spec["eval_newdays"]))] = "eval_newdays"
    return split


def report(df, spec, out):
    L = ["# Split report", "",
         f"- val days: {', '.join(spec['val_days'])}",
         f"- test days: {', '.join(spec['test_days'])}",
         f"- eval_newdays: {len(spec['eval_newdays'])} ROIs from {len(spec['eval_blocks'])} short time blocks (10 s; 1 s on burst days) "
         f"on {len(spec['new_days'])} unlabeled days", "",
         "| split | ROIs | labeled | " + " | ".join(CLASSES) + " | needs_box |",
         "|---|---|---|" + "---|" * len(CLASSES) + "---|"]
    for s in ["train", "val", "test", "eval_newdays", "eval_reserved"]:
        g = df[df.split == s]
        vc = g.triage.value_counts()
        L.append(f"| {s} | {len(g):,} | {(g.triage != '').sum():,} | " +
                 " | ".join(str(vc.get(c, 0)) for c in CLASSES) + f" | {(g.needs_box == 'true').sum()} |")
    L += ["", "## eval_newdays sample by day", "", "| day | ROIs on day | sampled |", "|---|---|---|"]
    ev = df[df.split == "eval_newdays"].groupby("day").size()
    for d in spec["new_days"]:
        L.append(f"| {d} | {(df.day == d).sum():,} | {ev.get(d, 0)} |")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L[:14]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--n-eval", type=int, default=400)
    ap.add_argument("--per-block", type=int, default=3)
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    path = cfg["labels_dir"] / "labels.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    if args.init:
        val, test = choose_days(df)
        new_days, blocks, sample = choose_eval_blocks(df, set(val) | set(test), args.n_eval, args.per_block, cfg["seed"])
        spec = dict(seed=cfg["seed"], val_days=val, test_days=test, new_days=new_days,
                    eval_blocks=blocks, eval_newdays=sample)
        SPLITS_YAML.write_text("# Frozen split assignment. Generated by `python -m cpics.splits --init`.\n" +
                               yaml.safe_dump(spec, sort_keys=False))
    spec = yaml.safe_load(SPLITS_YAML.read_text())
    df["split"] = apply(df, spec)
    df.to_csv(path, index=False)
    ev = df[df.split == "eval_newdays"][["roi_id", "day", "path", "width", "height"]]
    ev.assign(triage="", needs_box="", notes="").to_csv(cfg["labels_dir"] / "eval_newdays_to_label.csv", index=False)
    report(df, spec, cfg["labels_dir"] / "splits_report.md")


if __name__ == "__main__":
    main()
