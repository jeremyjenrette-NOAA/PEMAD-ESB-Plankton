#!/usr/bin/env bash
# Run a new, unlabeled cruise through the current model on the GPU workstation.
#   scripts/cruise_workstation.sh jan2026            # tar already copied from the bucket (see below)
#   UPLOAD=1 scripts/cruise_workstation.sh jan2026   # also copy results back to the bucket
# The tar comes from `python -m cpics.cruise package --name <name>` on the Mac (ROIs only, ~0.9 GB for jan2026).
# Needs the Phase 1 May-June DINOv2 embeddings in /home/user/data/cpics_ml/embeddings (from scripts/phase1.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
# NAME=${1:?cruise name, e.g. jan2026}
NAME=jan2026
CFG=configs/workstation.yaml
WORK=/home/user/data/cpics_ml/cruises/$NAME
BUCKET="gs://nmfs-dev-uc1-landing-bucket/NEFSC/Plankton Optics/CPICS/cruises/$NAME"
mkdir -p "$WORK"
if [ ! -d "$WORK/rois" ]; then
  [ -f "$WORK/${NAME}_rois.tar" ] || gcloud storage cp "$BUCKET/${NAME}_rois.tar" "$WORK/"
  tar -xf "$WORK/${NAME}_rois.tar" -C "$WORK"
fi
pip install -q -r requirements-gpu.txt
python -m cpics.cruise embed    --name "$NAME" --config $CFG
python -m cpics.cruise classify --name "$NAME" --config $CFG
python -m cpics.cruise map      --name "$NAME" --config $CFG
echo "Report and figures: reports/cruises/$NAME/  (git add reports/cruises/$NAME && commit && push)"
if [ "${UPLOAD:-0}" = "1" ]; then
  gcloud storage rsync -r -x '.*\.tar$|^rois/.*' "$WORK" "$BUCKET"
fi
