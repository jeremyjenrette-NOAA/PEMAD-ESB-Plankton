"""2-D similarity map of every distinct object, for the ROI atlas page.

    python -m cpics.roi_map --config configs/workstation.yaml

Takes the DINOv2 embedding of each object's representative ROI (one per dup_group, so the
thousands of repeat captures don't swamp the picture), runs UMAP (cosine, 30 neighbours), and
writes reports/roi_map.csv with the map position, label, who labeled it, and the Phase 1
baseline class probabilities. About a minute on the workstation. Commit and push the CSV.
"""
import argparse

import numpy as np
import pandas as pd

from cpics import config


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--model", default="dinov2")
    ap.add_argument("--neighbors", type=int, default=30)
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    import umap

    df = pd.read_csv(cfg["labels_dir"] / "labels.csv", dtype=str, keep_default_na=False)
    # One row per object: its labeled capture if any (so labels show on the map), else the earliest.
    df["_lab"] = (df.triage != "").astype(int)
    reps = df.sort_values(["dup_group", "_lab", "roi_id"], ascending=[True, False, True]) \
             .drop_duplicates("dup_group").sort_values("roi_id").copy()
    d = cfg["work_dir"] / "embeddings"
    ids = pd.read_csv(d / f"{args.model}_ids.csv", dtype=str).roi_id
    E = np.load(d / f"{args.model}.npy").astype(np.float32)
    pos = pd.Series(np.arange(len(ids)), index=ids)
    X = E[pos.loc[reps.roi_id].to_numpy()]
    xy = umap.UMAP(n_neighbors=args.neighbors, min_dist=0.1, metric="cosine", random_state=0).fit_transform(X)
    reps["x"], reps["y"] = np.round(xy[:, 0], 3), np.round(xy[:, 1], 3)
    reps["annotator"] = np.select([reps.triage_source == "eval_labeler", reps.triage != ""],
                                  ["jeremy", "jordan"], "none")
    pred = cfg["work_dir"] / "predictions" / f"baseline_{args.model}.csv"
    if pred.exists():
        p = pd.read_csv(pred, dtype={"roi_id": str})
        reps = reps.merge(p.drop(columns=["organism_flag"]), on="roi_id", how="left")
    cols = ["roi_id", "x", "y", "day", "dup_size", "persistent", "width", "height", "triage", "needs_box",
            "annotator", "split"] + [c for c in reps.columns if c.startswith("p_")]
    out = config.REPO / "reports" / "roi_map.csv"
    out.parent.mkdir(exist_ok=True)
    reps[cols].to_csv(out, index=False, float_format="%.3f")
    print(f"wrote {out}: {len(reps):,} objects")


if __name__ == "__main__":
    main()
