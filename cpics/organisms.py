"""Organism pool -> visual clusters + BioCLIP group suggestions -> data for the cluster labeler.

    python -m cpics.organisms embed    --config configs/workstation.yaml   # gather DINOv2 rows for the pool
    python -m cpics.organisms bioclip  --config configs/workstation.yaml   # zero-shot group suggestions (GPU)
    python -m cpics.organisms cluster  --config configs/workstation.yaml   # k-means on DINOv2, ~45 per cluster
    python -m cpics.organisms package  --config configs/workstation.yaml   # manifest.json + clusters/c####.json
    (scripts/organisms_workstation.sh runs all four)

Input: labels/organism_pool.csv (one row per likely organism: human-confirmed or model-predicted, May-June and
January 2026). Outputs in <work_dir>/organisms/: dinov2.npy, bioclip_zeroshot.csv, clusters.csv and
labeler_data/ (upload that folder to Google Drive for the Apps Script labeler, or serve it locally).

BioCLIP suggestions are a zero-shot guess (the image is compared with text such as "a photo of Copepoda"); they
only order and pre-fill clusters. Labels come from people.
"""
import argparse
import base64
import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from cpics import config

# Level 1 groups -> Level 2 -> text prompts for BioCLIP (taxonomic and common names; embeddings are averaged)
GROUPS = {
    "crustacean": {
        "copepod": ["Animalia Arthropoda Copepoda", "copepod"],
        "nauplius": ["nauplius larva", "copepod nauplius"],
        "cladoceran": ["Animalia Arthropoda Branchiopoda Cladocera", "water flea cladoceran"],
        "crustacean larva": ["decapod zoea larva", "barnacle cyprid larva"],
        "other crustacean": ["Animalia Arthropoda Malacostraca", "amphipod", "krill euphausiid"],
    },
    "gelatinous": {
        "appendicularian": ["Animalia Chordata Appendicularia", "larvacean Oikopleura"],
        "cnidarian": ["Animalia Cnidaria Hydrozoa", "hydromedusa jellyfish", "siphonophore"],
        "ctenophore": ["Animalia Ctenophora", "comb jelly"],
        "salp/doliolid": ["Animalia Chordata Thaliacea", "salp", "doliolid"],
    },
    "worm_like": {
        "chaetognath": ["Animalia Chaetognatha Sagittoidea", "arrow worm"],
        "polychaete": ["Animalia Annelida Polychaeta", "polychaete larva"],
        "other worm-like": ["planktonic worm"],
    },
    "fish_like": {
        "fish egg": ["fish egg"],
        "fish larva": ["Animalia Chordata Actinopteri larva", "larval fish"],
    },
    "protozoan": {
        "radiolarian/foraminiferan": ["Chromista Radiozoa", "radiolarian", "Chromista Foraminifera"],
        "ciliate": ["Chromista Ciliophora", "tintinnid ciliate"],
        "other protozoan": ["protozoan cell"],
    },
    "phyto_colonial": {
        "diatom chain": ["Chromista Ochrophyta Bacillariophyceae chain", "chain-forming diatom"],
        "single diatom": ["Chromista Ochrophyta Bacillariophyceae", "diatom cell"],
        "dinoflagellate": ["Chromista Myzozoa Dinophyceae", "dinoflagellate"],
        "other colony": ["Trichodesmium colony", "phytoplankton colony"],
    },
    "not_organism": {
        "marine snow": ["marine snow", "detritus aggregate"],
        "bubble or ring": ["air bubble", "optical ring halo"],
    },
}
L1_NAMES = {"crustacean": "Crustacean", "gelatinous": "Gelatinous", "worm_like": "Worm-like", "fish_like": "Fish-like",
            "protozoan": "Protozoan", "phyto_colonial": "Phytoplankton / colonial", "other_organism": "Other organism",
            "unsure_organism": "Unsure organism", "not_organism": "Not an organism"}
PER_CLUSTER = 45


def dirs(cfg):
    d = cfg["work_dir"] / "organisms"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_pool(cfg):
    return pd.read_csv(cfg["labels_dir"] / "organism_pool.csv", dtype=str, keep_default_na=False)


def image_path(cfg, row):
    """Pool paths are relative to the CPICS folder; on the workstation January ROIs sit in the unpacked cruise tar."""
    p = cfg["data_root"] / row.path
    if p.exists() or row.cruise != "jan2026":
        return p
    rel = Path(row.path).parts[1:]                       # drop 'January_2026_usv'
    return cfg["work_dir"] / "cruises" / "jan2026" / "rois" / Path(*rel)


def cmd_embed(args, cfg):
    out = dirs(cfg)
    pool = read_pool(cfg)
    rows = []
    srcs = {"mayjun2026": cfg["work_dir"] / "embeddings", "jan2026": cfg["work_dir"] / "cruises" / "jan2026" / "embeddings"}
    E = None
    for cruise, d in srcs.items():
        sel = pool.index[pool.cruise == cruise]
        ids = pd.read_csv(d / "dinov2_ids.csv", dtype=str).roi_id
        X = np.load(d / "dinov2.npy")
        pos = pd.Series(np.arange(len(ids)), index=ids)
        miss = set(pool.loc[sel, "roi_id"]) - set(ids)
        if miss:
            raise SystemExit(f"{cruise}: {len(miss)} pool ROIs have no DINOv2 embedding")
        if E is None:
            E = np.zeros((len(pool), X.shape[1]), np.float16)
        E[sel] = X[pos.loc[pool.loc[sel, "roi_id"]].to_numpy()]
    np.save(out / "dinov2.npy", E)
    pool[["object_id"]].to_csv(out / "dinov2_ids.csv", index=False)
    print(f"wrote {out / 'dinov2.npy'} {E.shape}")


def cmd_bioclip(args, cfg):
    import open_clip
    import torch
    from cpics.embed import MODELS, ROIs
    out = dirs(cfg)
    pool = read_pool(cfg)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, _ = open_clip.create_model_and_transforms(args.bioclip_model)
    tok = open_clip.get_tokenizer(args.bioclip_model)
    model = model.eval().to(device)
    spec = dict(MODELS["bioclip"])
    paths = [str(image_path(cfg, r)) for r in pool.itertuples()]
    dl = torch.utils.data.DataLoader(ROIs(paths, spec), batch_size=128, num_workers=args.workers)
    l2, l1, T = [], [], []
    with torch.no_grad():
        for g1, subs in GROUPS.items():
            for g2, names in subs.items():
                t = model.encode_text(tok([f"a photo of {n}." for n in names]).to(device)).float()
                t = torch.nn.functional.normalize(t, dim=1).mean(0)
                T.append(torch.nn.functional.normalize(t, dim=0))
                l2.append(g2)
                l1.append(g1)
        T = torch.stack(T)
        scale = model.logit_scale.exp().float()
        P, t0 = [], time.time()
        for k, x in enumerate(dl):
            f = torch.nn.functional.normalize(model.encode_image(x.to(device)).float(), dim=1)
            P.append((scale * f @ T.T).softmax(1).cpu().numpy())
            if k % 10 == 0:
                print(f"{min((k + 1) * 128, len(paths)):,}/{len(paths):,} {time.time() - t0:.0f}s", flush=True)
    P = np.concatenate(P)
    l1 = np.array(l1)
    res = pd.DataFrame({"object_id": pool.object_id})
    groups1 = list(GROUPS)
    for g in groups1:
        res[f"bc_{g}"] = P[:, l1 == g].sum(1).round(4)
    res["bc_l1"] = np.array(groups1)[res[[f"bc_{g}" for g in groups1]].to_numpy().argmax(1)]
    res["bc_l1_p"] = res[[f"bc_{g}" for g in groups1]].max(axis=1)
    res["bc_l2"] = np.array(l2)[P.argmax(1)]
    res["bc_l2_p"] = P.max(1).round(4)
    res.to_csv(out / "bioclip_zeroshot.csv", index=False)
    print(res.bc_l1.value_counts().to_string())


def cmd_cluster(args, cfg):
    from sklearn.cluster import KMeans
    out = dirs(cfg)
    pool = read_pool(cfg)
    E = np.load(out / "dinov2.npy").astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-6
    k = args.clusters or max(1, round(len(pool) / PER_CLUSTER))
    km = KMeans(n_clusters=k, n_init=4, random_state=0).fit(E)
    d = np.linalg.norm(E - km.cluster_centers_[km.labels_], axis=1)
    c = pd.DataFrame({"object_id": pool.object_id, "cluster_raw": km.labels_, "dist": d.round(4),
                      "human": (pool.basis == "human").to_numpy(), "p_organism": pool.p_organism.astype(float)})
    stats = c.groupby("cluster_raw").agg(n=("object_id", "size"), human=("human", "mean"), p=("p_organism", "mean"))
    # most organism-like clusters first: share already confirmed by people, then model confidence
    order = stats.assign(score=stats.human + stats.p).sort_values("score", ascending=False).index
    rank = {raw: i + 1 for i, raw in enumerate(order)}
    c["cluster"] = c.cluster_raw.map(rank)
    c = c.sort_values(["cluster", "dist"]).drop(columns=["cluster_raw"])
    c.to_csv(out / "clusters.csv", index=False)
    print(f"{k} clusters; sizes {stats.n.min()}-{stats.n.max()} (median {int(stats.n.median())})")


def webp(path, px):
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        if max(w, h) > px:
            im.thumbnail((px, px))
        b = io.BytesIO()
        im.save(b, "WEBP", quality=85)
    return w, h, "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()


def cmd_package(args, cfg):
    out = dirs(cfg)
    pool = read_pool(cfg).set_index("object_id")
    c = pd.read_csv(out / "clusters.csv", dtype={"object_id": str})
    bc_file = out / "bioclip_zeroshot.csv"
    bc = pd.read_csv(bc_file, dtype={"object_id": str}).set_index("object_id") if bc_file.exists() else None
    dest = Path(args.out) if args.out else out / "labeler_data"
    (dest / "clusters").mkdir(parents=True, exist_ok=True)
    manifest = dict(created=time.strftime("%Y-%m-%d %H:%M"), n_objects=len(c), groups=L1_NAMES, clusters=[])
    for cl, g in c.groupby("cluster", sort=True):
        items = []
        for r in g.itertuples():
            row = pool.loc[r.object_id]
            w, h, img = webp(image_path(cfg, row), args.px)
            it = dict(id=r.object_id, roi=row.roi_id, cruise=row.cruise, day=row.day, w=w, h=h,
                      p=round(float(row.p_organism), 3), basis=row.basis, img=img)
            if bc is not None and r.object_id in bc.index:
                it["sug"] = bc.at[r.object_id, "bc_l1"]
                it["sug2"] = bc.at[r.object_id, "bc_l2"]
            items.append(it)
        sug = pd.Series([i.get("sug", "") for i in items]).value_counts(normalize=True)
        sug = sug[sug.index != ""]
        name = f"c{int(cl):04d}.json"
        (dest / "clusters" / name).write_text(json.dumps(dict(cluster=int(cl), items=items)))
        manifest["clusters"].append(dict(
            id=int(cl), file=name, n=len(items), human=int(sum(i["basis"] == "human" for i in items)),
            p=round(float(np.mean([i["p"] for i in items])), 3),
            cruises=sorted({i["cruise"] for i in items}),
            suggestion=(sug.index[0] if len(sug) else ""), suggestion_share=(round(float(sug.iloc[0]), 2) if len(sug) else 0)))
        if int(cl) % 20 == 0:
            print(f"cluster {cl}", flush=True)
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=1))
    size = sum(f.stat().st_size for f in (dest / "clusters").glob("*.json")) / 1e6
    print(f"wrote {dest}: {len(manifest['clusters'])} clusters, {len(c):,} objects, {size:.0f} MB")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["embed", "bioclip", "cluster", "package"])
    ap.add_argument("--config")
    ap.add_argument("--bioclip-model", default="hf-hub:imageomics/bioclip",
                    help="open_clip model name; try hf-hub:imageomics/bioclip-2 if available")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--clusters", type=int, help="number of clusters (default: pool size / 45)")
    ap.add_argument("--px", type=int, default=320, help="package: longest image side")
    ap.add_argument("--out", help="package: output folder (default <work_dir>/organisms/labeler_data)")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    {"embed": cmd_embed, "bioclip": cmd_bioclip, "cluster": cmd_cluster, "package": cmd_package}[args.step](args, cfg)


if __name__ == "__main__":
    main()
