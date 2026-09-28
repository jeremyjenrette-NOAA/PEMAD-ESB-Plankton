"""Build the canonical label table (labels/labels.csv) from V3 annotations,
ROICoord files and image headers.

    python -m cpics.ingest [--config configs/default.yaml]

Outputs (in labels/):
    labels.csv        one row per ROI, schema in README
    conflicts.csv     annotation rows that could not be mapped unambiguously
    ingest_report.md  counts, fixes applied, missing files
Re-running on unchanged inputs produces byte-identical outputs.
"""
import argparse
import csv
import hashlib
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from PIL import Image

from cpics import config

# CTD string columns in ROICoord. Order inferred from values; unk4 unidentified (possibly a voltage).
CTD_COLS = ["ctd_cond", "ctd_pres", "ctd_temp", "ctd_unk4", "ctd_sal", "ctd_dens", "ctd_sspd"]

CLASS_FIXES = {"oganism": "organism"}
TRIAGE_CLASSES = ["organism", "marine_snow", "ring", "blurry", "artifact", "other"]
ARTIFACT_NOTE = re.compile(r"camera part", re.I)


def sha1(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:12]


def scan_images(rois_dir, cache_dir):
    """Walk rois/<day>/<hour>/*.png (skip thumbnails); cache width/height."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "image_sizes.csv"
    cache = {}
    if cache_file.exists():
        c = pd.read_csv(cache_file, dtype={"path": str})
        cache = {p: (w, h, s) for p, w, h, s in c[["path", "width", "height", "bytes"]].itertuples(index=False)}
    rows = []
    for day_dir in sorted(p for p in rois_dir.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}", p.name)):
        for hour_dir in sorted(p for p in day_dir.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}_\d{4}", p.name)):
            for f in sorted(hour_dir.glob("*.png")):
                rel = f"{day_dir.name}/{hour_dir.name}/{f.name}"
                size = f.stat().st_size
                hit = cache.get(rel)
                if hit and hit[2] == size:
                    w, h = hit[0], hit[1]
                else:
                    with Image.open(f) as im:
                        w, h = im.size
                rows.append((rel, day_dir.name, hour_dir.name, f.name, w, h, size))
    df = pd.DataFrame(rows, columns=["path", "day", "hour_dir", "ROI_file", "width", "height", "bytes"])
    df[["path", "width", "height", "bytes"]].to_csv(cache_file, index=False)
    return df


def _num(x):
    try:
        return float(x)
    except ValueError:
        return None


def read_roicoord(roicoord_dir):
    recs, dups, bad_ctd, no_ctd = {}, 0, 0, 0
    for f in sorted(roicoord_dir.glob("*.roicoords.txt")):
        with open(f, newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.reader(fh):
                if len(row) < 8 or row[0] != "ROI":
                    continue
                name = row[2].strip()
                if name in recs:
                    dups += 1
                    continue
                parts = row[7].split()
                # some lines carry binary junk before the date; start at the date token
                start = next((i for i, t in enumerate(parts) if re.search(r"\d{4}-\d{2}-\d{2}$", t)), None)
                if start is not None:
                    parts = parts[start:]
                if len(parts) == 0:
                    no_ctd += 1
                    vals = [None] * 7
                else:
                    vals = [_num(x) for x in parts[2:9]] if len(parts) >= 9 else [None] * 7
                    if None in vals:
                        bad_ctd += 1
                        vals = [None] * 7
                recs[name] = dict(
                    capture_time=row[1].strip(),
                    frame_x0=int(row[3]), frame_y0=int(row[4]), frame_x1=int(row[5]), frame_y1=int(row[6]),
                    ctd_time=" ".join(parts[:2]) if len(parts) >= 2 else "",
                    **dict(zip(CTD_COLS, vals)),
                )
    return pd.DataFrame.from_dict(recs, orient="index").rename_axis("ROI_file").reset_index(), dups, bad_ctd, no_ctd


def read_annotations(path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    rows = list(csv.reader(text.splitlines()))
    header = [h.strip() for h in rows[0]]
    keep = [i for i, h in enumerate(header) if h]
    df = pd.DataFrame([[r[i] if i < len(r) else "" for i in keep] for r in rows[1:]],
                      columns=[header[i] for i in keep]).fillna("")
    return df.apply(lambda s: s.str.strip())


def map_row(org, cls, note):
    """Return (triage, reason_if_conflict, fix_applied)."""
    fix = None
    c = cls.lower()
    if c in CLASS_FIXES:
        fix = f"{cls} -> {CLASS_FIXES[c]}"
        c = CLASS_FIXES[c]
    if org == "" and c == "":
        return "", None, fix
    if org != "1" and ARTIFACT_NOTE.search(note):
        return "artifact", None, fix
    if org == "1":
        if c in ("organism", "shape of interest", ""):
            return "organism", None, fix
        return "", f"Organism=1 but Classification={cls}", fix
    if org == "0":
        if c == "ring":
            return "ring", None, fix
        if c == "marine snow":
            return "marine_snow", None, fix
        if c == "unknown":
            return "other", None, fix
        return "", f"Organism=0 but Classification={cls}", fix
    if org == "2":
        if c == "blurry":
            return "blurry", None, fix
        return "", f"Organism=2 but Classification={cls}", fix
    return "", f"unexpected Organism value {org!r}", fix


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    out = cfg["labels_dir"]
    out.mkdir(parents=True, exist_ok=True)

    imgs = scan_images(cfg["rois_dir"], out / "_cache")
    coords, coord_dups, bad_ctd, no_ctd = read_roicoord(cfg["roicoord_dir"])
    ann = read_annotations(cfg["annotations"])
    ann_dups = int(ann.duplicated("ROI_file").sum())
    ann = ann.drop_duplicates("ROI_file", keep="first")

    triage, conflicts, fixes = [], [], Counter()
    for r in ann.itertuples(index=False):
        t, why, fix = map_row(r.Organism, r.Classification, r.Notes)
        triage.append(t)
        if fix:
            fixes[fix] += 1
        if why:
            conflicts.append(dict(ROI_file=r.ROI_file, day=r.directory, Organism=r.Organism,
                                  Classification=r.Classification, needs_box=r._5, Notes=r.Notes, reason=why))
    ann["triage"] = triage
    ann["needs_box"] = ann["Needs Boxing"].map({"1": "true", "0": "false"}).fillna("")
    ann["triage_source"] = ann["triage"].map(lambda t: "collab_v3" if t else "")

    df = imgs.merge(ann[["ROI_file", "triage", "needs_box", "triage_source", "Notes"]], on="ROI_file", how="left")
    df = df.merge(coords, on="ROI_file", how="left")
    df["roi_id"] = df["ROI_file"].str.replace(r"\.png$", "", regex=True)
    df = df.rename(columns={"Notes": "notes"})
    for col in ["boxes", "morphotype", "morph_source", "taxon", "taxon_rank", "split"]:
        df[col] = ""
    cols = ["roi_id", "day", "hour_dir", "path", "width", "height", "bytes", "capture_time",
            "frame_x0", "frame_y0", "frame_x1", "frame_y1", "ctd_time", *CTD_COLS,
            "triage", "needs_box", "triage_source", "boxes", "morphotype", "morph_source",
            "taxon", "taxon_rank", "notes", "split"]
    df = df[cols].fillna("").sort_values("roi_id").reset_index(drop=True)

    # Manual corrections (labels/corrections.csv) override V3; each records who made it.
    applied_corr = 0
    corr_path = out / "corrections.csv"
    if corr_path.exists():
        corr = pd.read_csv(corr_path, dtype=str, keep_default_na=False)
        idx = pd.Series(df.index, index=df.roi_id)
        for c in corr.itertuples(index=False):
            if c.roi_id not in idx.index:
                raise SystemExit(f"corrections.csv: unknown roi_id {c.roi_id}")
            if c.field == "triage" and c.value not in TRIAGE_CLASSES + [""]:
                raise SystemExit(f"corrections.csv: bad triage value {c.value!r}")
            i = idx[c.roi_id]
            df.at[i, c.field] = c.value
            if c.field == "triage":
                df.at[i, "triage_source"] = c.source
            elif c.field == "morphotype":
                df.at[i, "morph_source"] = c.source
            applied_corr += 1
        resolved = set(corr.roi_id + ".png")
        conflicts = [c for c in conflicts if c["ROI_file"] not in resolved]

    # Labels made in the new-day eval labeler (exported from its shared store).
    applied_eval = 0
    eval_path = out / "eval_newdays_labels.csv"
    if eval_path.exists():
        ev = pd.read_csv(eval_path, dtype=str, keep_default_na=False)
        idx = pd.Series(df.index, index=df.roi_id)
        for e in ev.itertuples(index=False):
            if e.roi_id not in idx.index or e.triage not in TRIAGE_CLASSES:
                continue
            i = idx[e.roi_id]
            df.at[i, "triage"] = e.triage
            df.at[i, "needs_box"] = e.needs_box
            df.at[i, "triage_source"] = "eval_labeler"
            if e.note:
                df.at[i, "notes"] = e.note
            applied_eval += 1
    for c in ["frame_x0", "frame_y0", "frame_x1", "frame_y1"]:
        df[c] = df[c].map(lambda v: "" if v == "" else str(int(v)))
    df.to_csv(out / "labels.csv", index=False)
    pd.DataFrame(conflicts).to_csv(out / "conflicts.csv", index=False)

    # ---- report ----
    ann_not_found = sorted(set(ann["ROI_file"]) - set(imgs["ROI_file"]))
    img_not_in_ann = sorted(set(imgs["ROI_file"]) - set(ann["ROI_file"]))
    no_coord = int((df["frame_x0"] == "").sum())
    lab = df[df["triage"] != ""]
    L = [f"# Ingest report", "",
         f"- Annotation file: `{cfg['annotations'].name}` (sha1 {sha1(cfg['annotations'])})",
         f"- ROI images found: {len(imgs):,} across {imgs['day'].nunique()} days",
         f"- Annotation rows: {len(ann):,} (duplicate filenames dropped: {ann_dups})",
         f"- Labeled ROIs (triage set): {len(lab):,} ({len(lab)/len(df):.1%})",
         f"- Manual corrections applied (`corrections.csv`): {applied_corr}",
         f"- Unresolved conflicts (`conflicts.csv`): {len(conflicts)}",
         f"- Eval-labeler labels applied (`eval_newdays_labels.csv`): {applied_eval}",
         f"- Annotation rows with no image on disk: {len(ann_not_found)}",
         f"- Images with no annotation row: {len(img_not_in_ann)}",
         f"- Images with no ROICoord entry: {no_coord} (duplicate ROICoord lines ignored: {coord_dups}; malformed CTD strings: {bad_ctd})",
         f"- ROICoord lines with an empty CTD string: {no_ctd:,} (CTD can be joined later from aux_00 by time)",
         "", "## Fixes applied", ""]
    L += [f"- `{k}`: {v}" for k, v in fixes.items()] or ["- none"]
    L += ["- Classification casing normalized (e.g. `Marine Snow` -> `marine_snow`)",
          "- Notes containing 'camera part' (with Organism != 1) -> `artifact`", "",
          "## Triage counts", "", "| class | ROIs | needs_box=true | median width x height (px) |", "|---|---|---|---|"]
    for c in TRIAGE_CLASSES:
        s = lab[lab["triage"] == c]
        if len(s):
            L.append(f"| {c} | {len(s):,} | {(s['needs_box'] == 'true').sum()} | "
                     f"{int(s['width'].median())} x {int(s['height'].median())} |")
    L += ["", "## Labeled ROIs by day", "", "| day | ROIs | labeled | organism | ring | marine_snow | blurry | artifact |",
          "|---|---|---|---|---|---|---|---|"]
    for d, g in df.groupby("day"):
        vc = g["triage"].value_counts()
        L.append(f"| {d} | {len(g):,} | {(g['triage'] != '').sum():,} | " +
                 " | ".join(str(vc.get(c, 0)) for c in ["organism", "ring", "marine_snow", "blurry", "artifact"]) + " |")
    if conflicts:
        L += ["", "## Conflicts", "", "| ROI | Organism | Classification | Notes | reason |", "|---|---|---|---|---|"]
        L += [f"| {c['ROI_file']} | {c['Organism']} | {c['Classification']} | {c['Notes']} | {c['reason']} |" for c in conflicts]
    if ann_not_found:
        L += ["", "## Annotation rows with no image (first 20)", ""] + [f"- {x}" for x in ann_not_found[:20]]
    L += ["", "## Notes", "",
          "- CTD column order in ROICoord is inferred from values: conductivity, pressure, temperature, "
          "**unknown (ctd_unk4, possibly a voltage)**, salinity, density, sound speed."]
    (out / "ingest_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
