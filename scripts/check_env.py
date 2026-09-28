"""Workstation sanity check: GPU, packages, labels, and that images resolve.

    python scripts/check_env.py --config configs/workstation.yaml
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from PIL import Image

from cpics import config

ap = argparse.ArgumentParser()
ap.add_argument("--config")
cfg = config.load(ap.parse_args().config)

try:
    import torch
    print(f"torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}",
          f"({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else "")
except ImportError:
    print("torch not installed (needed from Phase 1)")

df = pd.read_csv(cfg["labels_dir"] / "labels.csv", dtype=str, keep_default_na=False)
print(f"labels.csv: {len(df):,} rows, {(df.triage != '').sum():,} labeled")
missing = [p for p in df.path if not (cfg["rois_dir"] / p).exists()]
print(f"images resolved: {len(df) - len(missing):,} / {len(df):,}")
if missing:
    print("first missing:", missing[:3])
else:
    with Image.open(cfg["rois_dir"] / df.path.iloc[0]) as im:
        print("sample image:", im.size, im.mode)
