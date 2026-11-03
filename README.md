# PEMAD-ESB-Plankton

Automated triage, detection and classification of CPICS plankton ROI imagery
(USV mission ChanceMC40 26008, May 14 – Jun 17 2026).

Plan: see the "CPICS Plankton Classification — Execution Plan" doc in the Claude project.

## Layout

```
configs/default.yaml       paths on the Mac (data on the portable SSD: /Volumes/PortableSSD/saltnoaa/CPICS)
configs/workstation.yaml   paths on the GCP workstation
configs/splits.yaml        FROZEN split assignment (val/test days, eval sample) — commit it
cpics/ingest.py            V3 annotations + ROICoord + image headers -> labels/labels.csv
labels/corrections.csv     manual label fixes applied on top of V3 (roi_id, field, value, source)
labels/eval_newdays_labels.csv  labels exported from the eval labeler page
cpics/dedup.py             groups repeat captures of the same object (dup_group columns)
cpics/splits.py            day-based splits + new-day eval sample (one ROI per object)
labels/                    canonical label table and reports (small; versioned in git)
scripts/                   workstation helpers
```

Large outputs (embeddings, models, predictions) go to
`gs://nmfs-dev-uc1-landing-bucket/NEFSC/Plankton Optics/CPICS_ml/`, not into git and not into the
Drive-mirrored `CPICS/` prefix.

## Rebuild the label table

```bash
pip install -r requirements.txt
python -m cpics.ingest            # writes labels/labels.csv, conflicts.csv, ingest_report.md
python -m cpics.dedup             # adds dup_group, dup_size, dup_span_s, persistent; writes dup_report.md (~2.5 min first run, cached after)
python -m cpics.splits            # applies configs/splits.yaml; writes splits_report.md
```

Both are deterministic: same inputs -> byte-identical outputs. When V3 changes, re-run both and
commit; tag frozen training snapshots, e.g. `git tag labels-v3.0`.
`python -m cpics.splits --init` re-chooses the splits — only do this deliberately.

## Workstation setup

```bash
git pull
scripts/sync_from_bucket.sh /home/user/data/CPICS
python -m cpics.ingest --config configs/workstation.yaml   # optional: should reproduce labels.csv exactly
python scripts/check_env.py --config configs/workstation.yaml
```

## labels.csv columns

| column | meaning |
|---|---|
| roi_id, day, hour_dir, path | identity; `path` is relative to `rois/` |
| width, height, bytes | image size |
| capture_time, frame_x0..y1 | from ROICoord: capture time and ROI box in the full frame |
| ctd_time, ctd_* | CTD string from ROICoord (column order inferred; `ctd_unk4` unidentified, possibly a voltage); blank for ~half the ROIs |
| triage | organism, marine_snow, ring, blurry, artifact, other; blank = unlabeled |
| needs_box | true/false from V3 "Needs Boxing" |
| triage_source | who set triage: collab_v3, jeremy, expert, model_verified |
| boxes, morphotype, morph_source, taxon, taxon_rank | filled in later phases |
| notes | V3 Notes, verbatim |
| dup_group, dup_size, dup_span_s, persistent | repeat captures of one object; dup_group = the earliest member's roi_id (see cpics/dedup.py) |
| split | train, val, test, eval_newdays, eval_reserved (see cpics/splits.py) |

**Repeat captures.** CPICS re-saves an object that stays in view as a new ROI every frame
(20260521: 7,125 ROIs but only 33 distinct objects). Training should sample by `dup_group`
(one draw per group per epoch, or weight 1/dup_size), and counts for ecology should count groups.

## Run a new, unlabeled cruise (e.g. January 2026 Chance USV)

Preliminary: applies the Phase 1 DINOv2 baseline (trained on May-June 2026 V3 labels) to a cruise
nobody has labeled. See the docstring of `cpics/cruise.py` for what each step does.

```bash
# Mac (no GPU needed): list ROIs (full frames are skipped), group repeat captures, pack ROIs only
python -m cpics.cruise inventory --name jan2026 --src "/Volumes/PortableSSD/saltnoaa/CPICS/January_2026_usv"
python -m cpics.cruise dedup     --name jan2026
python -m cpics.cruise package   --name jan2026      # -> <work_dir>/cruises/jan2026/jan2026_rois.tar
gcloud storage cp /Volumes/PortableSSD/saltnoaa/CPICS/cpics_ml/cruises/jan2026/jan2026_rois.tar \
  "gs://nmfs-dev-uc1-landing-bucket/NEFSC/Plankton Optics/CPICS_ml/cruises/jan2026/"

# GPU workstation: embed, classify, map (~5-10 min on the T4)
git pull && scripts/cruise_workstation.sh jan2026
git add reports/cruises/jan2026 && git commit -m "jan2026 preliminary run" && git push
```

Outputs in `reports/cruises/<name>/`: `summary.md` (class shares by object and ROI, corrected range,
per day, caveats), `class_shares.png`, `cluster_map.png`, `cluster_map_slide.png` (16:9, map + region
key with example images), `map_regions.csv`, `objects_by_day.csv`, `objects_by_hour.csv`.
