"""Compute an image embedding for every ROI with a frozen pretrained model (Phase 1).

    python -m cpics.embed --config configs/workstation.yaml --model dinov2
    python -m cpics.embed --config configs/workstation.yaml --model bioclip

Each ROI is padded to a square with black (the CPICS background) so its shape is kept, then
resized to 224 px. Output, in <work_dir>/embeddings/:
    <model>.npy        float16 array, one row per ROI, L2-normalised
    <model>_ids.csv    roi_id for each row (same order as labels.csv)
    <model>_meta.json  model name, date, image count, seconds
A T4 does all 31,532 ROIs in roughly 5-15 minutes per model. Re-running skips a model whose
output already matches labels.csv unless --force is given.
"""
import argparse
import json
import time

import numpy as np
import pandas as pd
from PIL import Image

from cpics import config

MODELS = {
    # timm DINOv2 ViT-B/14 (self-supervised on natural images); pos-embeddings resampled to 224 px
    "dinov2": dict(kind="timm", name="vit_base_patch14_dinov2.lvd142m",
                   mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    # BioCLIP ViT-B/16 (CLIP trained on the Tree of Life images)
    "bioclip": dict(kind="open_clip", name="hf-hub:imageomics/bioclip",
                    mean=(0.48145466, 0.4578275, 0.40821073), std=(0.26862954, 0.26130258, 0.27577711)),
}
SIZE = 224


def pad_square(im):
    w, h = im.size
    s = max(w, h)
    canvas = Image.new("RGB", (s, s), (0, 0, 0))
    canvas.paste(im, ((s - w) // 2, (s - h) // 2))
    return canvas


def to_tensor(path, mean, std):
    import torch
    with Image.open(path) as im:
        im = pad_square(im.convert("RGB")).resize((SIZE, SIZE), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32) / 255.0
    a = (a - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
    return torch.from_numpy(a.transpose(2, 0, 1).copy())


def load_model(spec, device):
    if spec["kind"] == "timm":
        import timm
        m = timm.create_model(spec["name"], pretrained=True, num_classes=0, img_size=SIZE)
        fwd = m
    else:
        import open_clip
        m, _, _ = open_clip.create_model_and_transforms(spec["name"])
        fwd = m.encode_image
    return m.eval().to(device), fwd


class ROIs:
    def __init__(self, paths, spec):
        self.paths, self.spec = paths, spec

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        return to_tensor(self.paths[i], self.spec["mean"], self.spec["std"])


def main(argv=None):
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--model", choices=list(MODELS), required=True)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, help="only the first N ROIs (for a quick test)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    out = cfg["work_dir"] / "embeddings"
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(cfg["labels_dir"] / "labels.csv", dtype=str, keep_default_na=False)
    if args.limit:
        df = df.head(args.limit)
    ids_file, npy_file = out / f"{args.model}_ids.csv", out / f"{args.model}.npy"
    if not args.force and ids_file.exists() and npy_file.exists():
        if pd.read_csv(ids_file, dtype=str).roi_id.tolist() == df.roi_id.tolist():
            print(f"{npy_file} is up to date; use --force to recompute")
            return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    spec = MODELS[args.model]
    model, fwd = load_model(spec, device)
    paths = [str(cfg["rois_dir"] / p) for p in df.path]
    dl = torch.utils.data.DataLoader(ROIs(paths, spec), batch_size=args.batch, num_workers=args.workers,
                                     pin_memory=device == "cuda")
    feats, t0 = [], time.time()
    with torch.no_grad(), torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
        for k, x in enumerate(dl):
            f = fwd(x.to(device, non_blocking=True)).float()
            feats.append(torch.nn.functional.normalize(f, dim=1).cpu().numpy().astype(np.float16))
            if k % 20 == 0:
                done = min((k + 1) * args.batch, len(paths))
                print(f"{done:,}/{len(paths):,} ROIs  {time.time() - t0:.0f}s", flush=True)
    E = np.concatenate(feats)
    np.save(npy_file, E)
    df[["roi_id"]].to_csv(ids_file, index=False)
    meta = dict(model=spec["name"], dim=int(E.shape[1]), n=int(E.shape[0]), seconds=round(time.time() - t0),
                device=torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
                date=time.strftime("%Y-%m-%d %H:%M"))
    (out / f"{args.model}_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {npy_file} {E.shape} in {meta['seconds']}s")


if __name__ == "__main__":
    main()
