#!/usr/bin/env bash
# Copy ROI PNGs, ROICoord files and annotation CSVs from the bucket to local disk on the workstation.
# Thumbnails and full frames are skipped. Safe to re-run; only changed files are copied.
set -euo pipefail
SRC="gs://nmfs-dev-uc1-landing-bucket/NEFSC/Plankton Optics/CPICS"
DST="${1:-/home/user/data/CPICS}"
mkdir -p "$DST/rois"
gcloud storage rsync -r --exclude='.*thumbnail.*|.*\.db$|.*\.DS_Store$' "$SRC/rois" "$DST/rois"
gcloud storage cp "$SRC/V3_Annotations_full_ROI_list_20260729.xlsb.csv" "$DST/"
echo "PNG count: $(find "$DST/rois" -name '*.png' | wc -l)   (expected 31,532)"
