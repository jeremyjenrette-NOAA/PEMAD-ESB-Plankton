"""Exploratory focus/sharpness score per ROI (Nov 2026).

    python scripts/sharpness.py <image_root> <list_of_relative_paths.txt> <out.csv>   # resumable, ~150 s per call

Columns: path, edge (90th-pct gradient on the object outline / contrast), lapv (Laplacian variance / contrast^2),
con (99th pct - background), fill (share of ROI above half contrast).
Validation: edge vs Jeremy blurry labels AUC 0.77 (eval_newdays), 0.89 on calibration objects with agreed focus
(only 8 sharp); vs Jordan V3 blurry 0.54. lapv is noise-dominated. Fooled by small sharp specks on large
out-of-focus glows (common in Jan 2026), so not yet a replacement for a learned focus flag.
Results: <work_dir>/sharpness/{may,jan}_sharp.csv
"""
import sys, os, time, csv, numpy as np
from PIL import Image
root, listfile, out = sys.argv[1], sys.argv[2], sys.argv[3]
paths=[l.strip() for l in open(listfile) if l.strip()]
done=set()
if os.path.exists(out): done={r[0] for r in csv.reader(open(out))}
f=open(out,'a',newline=''); w=csv.writer(f); t0=time.time(); n=0
def measure(p):
    with Image.open(p) as im: g=np.asarray(im.convert('L'),dtype=np.float32)
    if min(g.shape)<5: return None
    border=np.concatenate([g[0],g[-1],g[:,0],g[:,-1]]); bg=np.median(border)
    p99=np.percentile(g,99); con=max(p99-bg,1.0)
    gx=np.zeros_like(g); gy=np.zeros_like(g); gx[:,1:-1]=(g[:,2:]-g[:,:-2])/2; gy[1:-1]=(g[2:]-g[:-2])/2
    gm=np.hypot(gx,gy)
    mask=g>bg+0.5*con
    edge=mask ^ (np.roll(mask,1,0)&np.roll(mask,-1,0)&np.roll(mask,1,1)&np.roll(mask,-1,1))
    edge_s=float(np.percentile(gm[edge],90)/con) if edge.sum()>=4 else float('nan')
    lap=(g[1:-1,2:]+g[1:-1,:-2]+g[2:,1:-1]+g[:-2,1:-1]-4*g[1:-1,1:-1])
    lapv=float(lap.var()/con**2)
    return edge_s, lapv, float(con), float(mask.mean())
for p in paths:
    if p in done: continue
    try: r=measure(os.path.join(root,p))
    except Exception: r=None
    w.writerow([p]+(list(r) if r else ['','','','']))
    n+=1
    if time.time()-t0>150: break
f.close(); print('wrote',n,'remaining',len(paths)-len(done)-n)
