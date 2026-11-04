"""Zip every ROI image of one predicted class from a cruise run, with its table.

    python scripts/export_class.py <cruise_src_dir> <table.csv> <out.zip>
    e.g. python scripts/export_class.py /Volumes/PortableSSD/saltnoaa/CPICS/January_2026_usv \
           reports/cruises/jan2026/predicted_organisms.csv \
           /Volumes/PortableSSD/saltnoaa/CPICS/cpics_ml/cruises/jan2026/jan2026_predicted_organisms.zip

The table needs `source_path` (relative to the folder above the cruise folder, or to <cruise_src_dir>'s
parent) and `image_file` (path inside the zip). The table itself goes into the zip as table.csv.
"""
import sys, zipfile
from pathlib import Path
import pandas as pd

src, table, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
t = pd.read_csv(table, dtype=str)
missing = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:   # PNGs are already compressed
    z.write(table, "table.csv")
    for sp, f in zip(t.source_path, t.image_file):
        p = src.parent / sp
        if p.exists():
            z.write(p, f)
        else:
            missing += 1
print(f"wrote {out}: {len(t) - missing:,} images" + (f", {missing} missing" if missing else ""))
