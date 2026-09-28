# PEMAD-ESB-Plankton

Automated triage, detection and classification of CPICS plankton ROI imagery
(USV mission ChanceMC40 26008, May 14 – Jun 17 2026).

Plan: see the "CPICS Plankton Classification — Execution Plan" doc in the Claude project.

## Layout

```
configs/default.yaml       paths on the Mac (data_root = the CPICS folder this repo sits in)
configs/workstation.yaml   paths on the GCP workstation
configs/splits.yaml        FROZEN split assignment (val/test days, eval sample) — commit it
cpics/ingest.py            V3 annotations + ROICoord + image headers -> labels/labels.csv
labels/corrections.csv     manual label fixes applied on top of V3 (roi_id, field, value, source)
cpics/splits.py            day-based splits + new-day eval sample
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
| split | train, val, test, eval_newdays, eval_reserved (see cpics/splits.py) |
