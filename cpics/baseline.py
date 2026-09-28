"""Phase 1 baseline: logistic regression on frozen embeddings, scored by survey day.

    python -m cpics.baseline --config configs/workstation.yaml --features dinov2 bioclip dinov2+bioclip size

Trains on labeled `train` ROIs (one per distinct object), picks C on `val`, and reports on
`val`, `test` and `eval_newdays`. Feature sets: an embedding name, two joined with '+', or `size`
(width, height, aspect only: a check on how much the model leans on ROI size).

Triage classes: organism, marine_snow, ring, blurry, artifact ('other' is folded into artifact,
too rare to learn). The organism threshold is set on val for 95% organism recall, then applied
unchanged to test and eval_newdays.

Writes reports/phase1_baseline.md and <work_dir>/predictions/baseline_<features>.csv
(class probabilities for every ROI).
NOTE: eval_newdays was labeled by a different annotator (Jeremy) than train/val/test
(collaborator); differences there mix model error with labeling-style differences.
"""
import argparse
import math
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler

from cpics import config

CLASSES = ["organism", "marine_snow", "ring", "blurry", "artifact"]
TARGET_RECALL = 0.95


def features(name, df, cfg):
    if name == "size":
        w, h = df.width.astype(float).to_numpy(), df.height.astype(float).to_numpy()
        return np.c_[np.log(w), np.log(h), np.log(w / h), np.log(w * h)]
    parts = []
    for m in name.split("+"):
        d = cfg["work_dir"] / "embeddings"
        ids = pd.read_csv(d / f"{m}_ids.csv", dtype=str).roi_id
        E = np.load(d / f"{m}.npy").astype(np.float32)
        pos = pd.Series(np.arange(len(ids)), index=ids)
        missing = set(df.roi_id) - set(ids)
        if missing:
            raise SystemExit(f"{m}: {len(missing)} ROIs have no embedding; re-run cpics.embed")
        parts.append(E[pos.loc[df.roi_id].to_numpy()])
    return np.hstack(parts)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def organism_stats(y, p_org, thr):
    pos, pred = y == "organism", p_org >= thr
    tp, fp = int((pos & pred).sum()), int((~pos & pred).sum())
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    rec = tp / n_pos if n_pos else float("nan")
    prec = tp / (tp + fp) if tp + fp else float("nan")
    removed = int((~pos & ~pred).sum()) / n_neg if n_neg else float("nan")
    return dict(n_org=n_pos, recall=rec, recall_ci=wilson(tp, n_pos), precision=prec, noise_removed=removed,
                flagged=int(pred.sum()), n=len(y))


def threshold_for_recall(y, p_org, target):
    s = np.sort(p_org[y == "organism"])
    if not len(s):
        return 0.5
    k = int(math.floor((1 - target) * len(s)))
    return float(s[k]) if k < len(s) else float(s[-1])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--features", nargs="+", default=["dinov2", "bioclip", "dinov2+bioclip", "size"])
    ap.add_argument("--report", default=str(config.REPO / "reports" / "phase1_baseline.md"))
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    df = pd.read_csv(cfg["labels_dir"] / "labels.csv", dtype=str, keep_default_na=False)
    df["y"] = df.triage.replace({"other": "artifact"})
    lab = df[df.y.isin(CLASSES)]
    train = lab[lab.split == "train"].drop_duplicates("dup_group")
    sets = {s: lab[lab.split == s].drop_duplicates("dup_group") for s in ["val", "test", "eval_newdays"]}

    L = ["# Phase 1 baseline: logistic regression on frozen embeddings", "",
         f"Run {time.strftime('%Y-%m-%d %H:%M')}. Train {len(train):,} objects "
         f"({', '.join(f'{c} {int((train.y == c).sum())}' for c in CLASSES)}). "
         f"Val {len(sets['val'])}, test {len(sets['test'])}, eval_newdays {len(sets['eval_newdays'])} objects.", "",
         "Organism threshold set on val for 95% organism recall, then applied unchanged. "
         "'Noise removed' = share of non-organisms below the threshold (what annotators no longer see). "
         "eval_newdays was labeled by a different annotator than the training data.", "",
         "| features | C | val macro-F1 | test macro-F1 | newdays macro-F1 | test org. recall | test org. precision "
         "| test noise removed | newdays org. recall (95% CI) | newdays org. precision | newdays noise removed |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    pred_dir = cfg["work_dir"] / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    for name in args.features:
        Xtr = features(name, train, cfg)
        sc = StandardScaler().fit(Xtr)
        best = None
        for C in [0.01, 0.1, 1.0]:
            clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(sc.transform(Xtr), train.y)
            f1 = f1_score(sets["val"].y, clf.predict(sc.transform(features(name, sets["val"], cfg))), average="macro")
            if best is None or f1 > best[0]:
                best = (f1, C, clf)
        f1v, C, clf = best
        org = list(clf.classes_).index("organism")
        pv = clf.predict_proba(sc.transform(features(name, sets["val"], cfg)))
        thr = threshold_for_recall(sets["val"].y.to_numpy(), pv[:, org], TARGET_RECALL)
        res = {}
        for s, d in sets.items():
            P = clf.predict_proba(sc.transform(features(name, d, cfg)))
            yhat = clf.classes_[P.argmax(1)]
            res[s] = dict(f1=f1_score(d.y, yhat, average="macro"),
                          org=organism_stats(d.y.to_numpy(), P[:, org], thr),
                          cm=pd.crosstab(d.y, pd.Series(yhat, index=d.index), rownames=["true"], colnames=["pred"])
                          .reindex(index=CLASSES, columns=CLASSES, fill_value=0))
        t, e = res["test"]["org"], res["eval_newdays"]["org"]
        L.append(f"| {name} | {C} | {f1v:.2f} | {res['test']['f1']:.2f} | {res['eval_newdays']['f1']:.2f} | "
                 f"{t['recall']:.2f} | {t['precision']:.2f} | {t['noise_removed']:.0%} | "
                 f"{e['recall']:.2f} ({e['recall_ci'][0]:.2f}-{e['recall_ci'][1]:.2f}, n={e['n_org']}) | "
                 f"{e['precision']:.2f} | {e['noise_removed']:.0%} |")
        detail += [f"## {name}", "", f"C = {C}; organism threshold {thr:.3f}.", ""]
        for s in ["test", "eval_newdays"]:
            cm = res[s]["cm"]
            detail += [f"{s} confusion (rows true, columns predicted):", "",
                       "| true \\ pred | " + " | ".join(CLASSES) + " |", "|---" * (len(CLASSES) + 1) + "|"]
            detail += [f"| {c} | " + " | ".join(str(v) for v in cm.loc[c]) + " |" for c in CLASSES]
            detail.append("")
        if name != "size":
            P = clf.predict_proba(sc.transform(features(name, df, cfg)))
            out = pd.DataFrame(P, columns=[f"p_{c}" for c in clf.classes_])
            out.insert(0, "roi_id", df.roi_id.to_numpy())
            out["organism_flag"] = (P[:, org] >= thr)
            out.to_csv(pred_dir / f"baseline_{name.replace('+', '_')}.csv", index=False, float_format="%.4f")
        print(L[-1], flush=True)

    from pathlib import Path
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(L + [""] + detail) + "\n")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
