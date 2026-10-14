"""Score a calibration round labeled under the CPICS Annotation Rules v1.0.

    python -m cpics.calibration labels/calibration/jeremy.csv labels/calibration/jordan.csv

Each CSV has one row per object: roi_id, class, focus, needs_box, multiple, count, expert_flag, note
(the labeler's "Copy labels as CSV" format, or an export of its shared store).
Writes labels/calibration/calibration_report.md and labels/calibration/adjudication.csv
(every object where the two disagree on class, focus or needs box, to settle together).
Target: class kappa >= 0.7.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from cpics import config

CLASSES = ["organism", "marine_snow", "ring", "artifact", "unidentifiable"]
TARGET = 0.7


def kappa(a, b, cats):
    t = pd.crosstab(a, b).reindex(index=cats, columns=cats, fill_value=0).to_numpy()
    n = t.sum()
    if n == 0:
        return float("nan"), float("nan")
    po = np.trace(t) / n
    pe = (t.sum(1) * t.sum(0)).sum() / n ** 2
    return ((po - pe) / (1 - pe) if pe < 1 else 1.0), po


def load(path):
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    d.columns = [c.strip().lower() for c in d.columns]
    if "cls" in d.columns and "class" not in d.columns:
        d = d.rename(columns={"cls": "class"})
    for c in ["needs_box", "multiple", "expert_flag"]:
        d[c] = d.get(c, "").astype(str).str.lower().isin(["true", "1", "yes"])
    d["focus"] = d.get("focus", "sharp").replace("", "sharp")
    return d.drop_duplicates("roi_id", keep="last").set_index("roi_id")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("first")
    ap.add_argument("second")
    ap.add_argument("--names", nargs=2, default=None)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = config.load(a.config)
    n1, n2 = a.names or [Path(a.first).stem, Path(a.second).stem]
    A, B = load(a.first), load(a.second)
    sample = pd.read_csv(cfg["labels_dir"] / "calibration" / "calibration_set.csv", dtype=str).set_index("roi_id")
    ids = sorted(set(A.index) & set(B.index) & set(sample.index))
    A, B = A.loc[ids], B.loc[ids]
    k_cls, p_cls = kappa(A["class"], B["class"], CLASSES)
    org = lambda s: s.eq("organism").map({True: "organism", False: "not"})
    k_org, p_org = kappa(org(A["class"]), org(B["class"]), ["organism", "not"])
    k_foc, p_foc = kappa(A.focus, B.focus, ["sharp", "blurry"])
    both_org = (A["class"] == "organism") & (B["class"] == "organism")
    k_box, p_box = kappa(A.needs_box[both_org], B.needs_box[both_org], [True, False])
    k_mul, p_mul = kappa(A.multiple, B.multiple, [True, False])
    ok = k_cls >= TARGET
    L = [f"# Calibration round: {n1} vs {n2}", "",
         f"{len(ids)} objects labeled by both. Target: class kappa ≥ {TARGET}. "
         f"**{'Target met.' if ok else 'Target not met.'}**", "",
         "| measure | agreement | kappa |", "|---|---|---|",
         f"| Class (5 classes) | {p_cls:.0%} | {k_cls:.2f} |",
         f"| Organism vs. not | {p_org:.0%} | {k_org:.2f} |",
         f"| Focus (sharp / blurry) | {p_foc:.0%} | {k_foc:.2f} |",
         f"| Needs box (objects both called organism, n={int(both_org.sum())}) | {p_box:.0%} | {k_box:.2f} |",
         f"| Multiple | {p_mul:.0%} | {k_mul:.2f} |", "",
         f"## Class confusion ({n1} rows, {n2} columns)", "",
         "| | " + " | ".join(CLASSES) + " |", "|---" * (len(CLASSES) + 1) + "|"]
    t = pd.crosstab(A["class"], B["class"]).reindex(index=CLASSES, columns=CLASSES, fill_value=0)
    L += [f"| {c} | " + " | ".join(str(v) for v in t.loc[c]) + " |" for c in CLASSES]
    L += ["", "## Agreement by sampling stratum", "", "| stratum | objects | class agreement |", "|---|---|---|"]
    st = sample.loc[ids, "stratum"]
    for s, g in st.groupby(st):
        L.append(f"| {s} | {len(g)} | {(A.loc[g.index, 'class'] == B.loc[g.index, 'class']).mean():.0%} |")
    dis = pd.DataFrame({"roi_id": ids, f"{n1}_class": A["class"].values, f"{n2}_class": B["class"].values,
                        f"{n1}_focus": A.focus.values, f"{n2}_focus": B.focus.values,
                        f"{n1}_needs_box": A.needs_box.values, f"{n2}_needs_box": B.needs_box.values,
                        f"{n1}_note": A.get("note", "").values, f"{n2}_note": B.get("note", "").values})
    m = (dis[f"{n1}_class"] != dis[f"{n2}_class"]) | (dis[f"{n1}_focus"] != dis[f"{n2}_focus"]) | \
        (both_org.values & (dis[f"{n1}_needs_box"] != dis[f"{n2}_needs_box"]))
    dis = dis[m].assign(agreed_class="", agreed_focus="", agreed_needs_box="", rule="", comment="")
    out = cfg["labels_dir"] / "calibration"
    dis.to_csv(out / "adjudication.csv", index=False)
    L += ["", f"{len(dis)} objects need adjudication: see adjudication.csv "
          "(fill agreed_class / agreed_focus / agreed_needs_box and the rule that settled it)."]
    (out / "calibration_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
