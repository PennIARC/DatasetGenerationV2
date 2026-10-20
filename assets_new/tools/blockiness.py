import sys,glob,os
import numpy as np
from PIL import Image
def blockiness(p,thr=70):
    g=np.asarray(Image.open(p).convert("L"),float)
    h,w=g.shape;g=g[:h//8*8,:w//8*8]
    dx=np.abs(np.diff(g,axis=1));dy=np.abs(np.diff(g,axis=0))
    lum=(g[:,1:]+g[:,:-1])/2;lumy=(g[1:]+g[:-1])/2
    r=[]
    for d,l,ax in ((dx,lum,1),(dy,lumy,0)):
        idx=np.arange(d.shape[ax]);bord=(idx%8==7)
        m=l<thr
        if ax==1: b=d[:,bord][m[:,bord]].mean();i=d[:,~bord][m[:,~bord]].mean()
        else: b=d[bord][m[bord]].mean();i=d[~bord][m[~bord]].mean()
        r.append(b/i)
    return float(np.mean(r))
if __name__=="__main__":
    for p in sorted(sys.argv[1:]): print(os.path.basename(p),round(blockiness(p),3))
