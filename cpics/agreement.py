"""Build and score the inter-annotator agreement check.

    python -m cpics.agreement sample            # write labels/agreement_sets.csv (frozen; commit it)
    python -m cpics.agreement score FILE.csv    # score blind relabels exported from the labeler

Set A: ~200 objects from the collaborator's fully labeled days, relabeled blind by Jeremy.
Set B: ~100 of Jeremy's new-day eval objects, relabeled blind by the collaborator.
Both are stratified by the original label (so rare classes get enough examples); the stored
stratum weights let prevalence be re-estimated without that distortion.
"""
import argparse
import random
import sys

import pandas as pd

from cpics import config

A_DAYS_MIN_LABELED = 0.95
A_QUOTA = {"organism": 50, "organism_box": 35, "marine_snow": 45, "ring": 30, "blurry": 30, "artifact": 10}
B_QUOTA = {"organism": 29, "organism_box": 1, "blurry": 25, "ring": 20, "marine_snow": 15, "artifact": 9, "other": 2}
CLASSES = ["organism", "organism_box", "marine_snow", "ring", "blurry", "artifact", "other"]


def cls(df):
    c = df.triage.copy()
    c[(df.triage == "organism") & (df.needs_box == "true")] = "organism_box"
    return c


def sample(cfg):
    df = pd.read_csv(cfg["labels_dir"] / "labels.csv", dtype=str, keep_default_na=False)
    df["cls"] = cls(df)
    rng = random.Random(cfg["seed"] + 1)
    frac = df.groupby("day").triage.apply(lambda s: (s != "").mean())
    full_days = sorted(frac[frac >= A_DAYS_MIN_LABELED].index)
    rows = []
    a = df[df.day.isin(full_days) & (df.triage_source.isin(["collab_v3", "jeremy"])) & (df.cls != "")]
    a = a.drop_duplicates("dup_group")
    for c, n in A_QUOTA.items():
        pool = sorted(a[a.cls == c].roi_id)
        take = rng.sample(pool, min(n, len(pool)))
        w = len(pool) / len(take) if take else 0
        rows += [dict(set="A", roi_id=r, orig_annotator="collaborator", orig_cls=c, stratum_n=len(pool),
                      weight=round(w, 4)) for r in take]
    b = df[(df.split == "eval_newdays") & (df.cls != "")]
    for c, n in B_QUOTA.items():
        pool = sorted(b[b.cls == c].roi_id)
        take = rng.sample(pool, min(n, len(pool)))
        w = len(pool) / len(take) if take else 0
        rows += [dict(set="B", roi_id=r, orig_annotator="jeremy", orig_cls=c, stratum_n=len(pool),
                      weight=round(w, 4)) for r in take]
    out = pd.DataFrame(rows).sort_values(["set", "roi_id"])
    out.to_csv(cfg["labels_dir"] / "agreement_sets.csv", index=False)
    print("A days:", ", ".join(full_days))
    print(out.groupby(["set", "orig_cls"]).size().to_string())


def kappa(t):
    n = t.values.sum()
    po = sum(t.at[c, c] for c in t.index if c in t.columns) / n
    pe = sum(t.loc[c].sum() * t[c].sum() for c in t.index if c in t.columns) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def score(cfg, path):
    sets = pd.read_csv(cfg["labels_dir"] / "agreement_sets.csv", dtype=str)
    new = pd.read_csv(path, dtype=str, keep_default_na=False)
    new["new_cls"] = cls(new)
    m = sets.merge(new[["roi_id", "new_cls", "note"]], on="roi_id", how="inner")
    m["weight"] = m.weight.astype(float)
    L = ["# Annotator agreement", ""]
    for s, g in m.groupby("set"):
        who = "collaborator (rows) vs Jeremy (columns)" if s == "A" else "Jeremy (rows) vs collaborator (columns)"
        t = pd.crosstab(g.orig_cls, g.new_cls).reindex(index=CLASSES, columns=CLASSES, fill_value=0)
        t = t.loc[t.sum(axis=1) > 0, t.sum(axis=0) > 0]
        k, po = kappa(t.reindex(columns=t.index.union(t.columns), index=t.index.union(t.columns), fill_value=0))
        L += [f"## Set {s}: {len(g)} objects, {who}", "",
              f"- Raw agreement {po:.0%}, Cohen's kappa {k:.2f} (on the stratified sample)", ""]
        L += ["| original \\ relabel | " + " | ".join(t.columns) + " | agree |", "|---" * (len(t.columns) + 2) + "|"]
        for c in t.index:
            L.append(f"| {c} | " + " | ".join(str(v) for v in t.loc[c]) + f" | {t.at[c, c] / t.loc[c].sum():.0%} |"
                     if c in t.columns else f"| {c} | " + " | ".join(str(v) for v in t.loc[c]) + " | 0% |")
        # prevalence re-estimated with stratum weights
        orig = g.groupby("orig_cls").weight.sum() / g.weight.sum()
        rel = g.groupby("new_cls").weight.sum() / g.weight.sum()
        p = pd.DataFrame({"original annotator": orig, "relabel": rel}).reindex(CLASSES).fillna(0)
        L += ["", "Class shares on this set's source pool (weighted back from the stratified sample):", "",
              "| class | original | relabel |", "|---|---|---|"]
        L += [f"| {c} | {p.at[c, 'original annotator']:.1%} | {p.at[c, 'relabel']:.1%} |" for c in CLASSES
              if p.loc[c].sum() > 0]
        dis = g[g.orig_cls != g.new_cls]
        L += ["", f"Disagreements ({len(dis)}):", ""] + [f"- {r.roi_id}: {r.orig_cls} -> {r.new_cls}"
                                                         + (f" ({r.note})" if r.note else "") for r in dis.itertuples()]
        L.append("")
    out = cfg["labels_dir"] / "agreement_report.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "score"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = config.load(a.config)
    sample(cfg) if a.cmd == "sample" else score(cfg, a.file)
