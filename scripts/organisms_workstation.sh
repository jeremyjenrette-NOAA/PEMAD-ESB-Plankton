#!/usr/bin/env bash
# Build the organism cluster-labeler data on the GPU workstation (~15-25 min on the T4).
# Needs: Phase 1 May-June DINOv2 embeddings, the jan2026 cruise run (embeddings + unpacked ROIs), labels/organism_pool.csv.
#   scripts/organisms_workstation.sh
#   UPLOAD=1 scripts/organisms_workstation.sh    # also copy labeler_data to the bucket
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=configs/workstation.yaml
pip install -q -r requirements-gpu.txt
python -m cpics.organisms embed   --config $CFG
python -m cpics.organisms bioclip --config $CFG
python -m cpics.organisms cluster --config $CFG
python -m cpics.organisms package --config $CFG
cp /home/user/data/cpics_ml/organisms/bioclip_zeroshot.csv /home/user/data/cpics_ml/organisms/clusters.csv reports/ 2>/dev/null || true
mkdir -p reports/organisms && mv reports/bioclip_zeroshot.csv reports/clusters.csv reports/organisms/
echo "Commit reports/organisms/ and push. Labeler data: /home/user/data/cpics_ml/organisms/labeler_data"
if [ "${UPLOAD:-0}" = "1" ]; then
  gcloud storage rsync -r /home/user/data/cpics_ml/organisms/labeler_data \
    "gs://nmfs-dev-uc1-landing-bucket/NEFSC/Plankton Optics/CPICS_ml/organisms/labeler_data"
fi
