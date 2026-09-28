from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[1]


def load(path=None):
    path = Path(path) if path else REPO / "configs" / "default.yaml"
    cfg = yaml.safe_load(path.read_text())
    root = Path(cfg["data_root"])
    cfg["data_root"] = root if root.is_absolute() else (REPO / root).resolve()
    for k in ("annotations", "rois_dir", "roicoord_dir"):
        p = Path(cfg[k])
        cfg[k] = p if p.is_absolute() else cfg["data_root"] / p
    lab = Path(cfg["labels_dir"])
    cfg["labels_dir"] = lab if lab.is_absolute() else REPO / lab
    # Large ML outputs (embeddings, predictions, models) live outside git.
    work = Path(cfg.get("work_dir") or (cfg["data_root"].parent / "cpics_ml"))
    cfg["work_dir"] = work if work.is_absolute() else (REPO / work).resolve()
    return cfg
