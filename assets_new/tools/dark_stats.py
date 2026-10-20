import sys,glob,os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
def stats(p):
    g=np.asarray(Image.open(p).convert("L"),float)/255
    frac=(g<0.06).mean()
    thr=np.percentile(g,5);m=g<=thr
    hp=g-ndi.gaussian_filter(g,2);v=hp[m].std()
    return frac,thr,v,g.mean()
if __name__=="__main__":
    for p in sorted(sys.argv[1:]):
        f,t,v,m=stats(p);print(f"{os.path.basename(p)[:40]:40s} frac<0.06={f:.4f} p5={t:.3f} darkest5%_hp_std={v:.4f} mean={m:.3f}")
