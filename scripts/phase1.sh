#!/usr/bin/env bash
# Phase 1 on the GPU workstation: embeddings for every ROI with two frozen models, then the
# logistic-regression baseline. Needs the ROI images synced (scripts/sync_from_bucket.sh).
#   scripts/phase1.sh            # run everything (~20-40 min on a T4)
#   UPLOAD=1 scripts/phase1.sh   # also copy embeddings + predictions to the bucket
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=configs/workstation.yaml
pip install -q -r requirements-gpu.txt
python -m cpics.embed --config $CFG --model dinov2
python -m cpics.embed --config $CFG --model bioclip
python -m cpics.baseline --config $CFG
echo "Report: reports/phase1_baseline.md  (commit and push it)"
if [ "${UPLOAD:-0}" = "1" ]; then
  gcloud storage rsync -r /home/user/data/cpics_ml "gs://nmfs-dev-uc1-landing-bucket/NEFSC/Plankton Optics/CPICS_ml"
fi
