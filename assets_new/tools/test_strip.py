import glob,random,sys,os
import numpy as np
from PIL import Image
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..")
random.seed(3);rng=np.random.default_rng(3)
bl=[np.asarray(Image.open(f)) for f in sorted(glob.glob(A+"/grassBlades/*.png"))]
def paste(bg,s,x,y):
    h,w=s.shape[:2]
    x0,y0=max(x,0),max(y,0);x1,y1=min(x+w,bg.shape[1]),min(y+h,bg.shape[0])
    if x1<=x0 or y1<=y0:return
    sub=s[y0-y:y1-y,x0-x:x1-x];a=sub[...,3:4]/255.
    bg[y0:y1,x0:x1]=bg[y0:y1,x0:x1]*(1-a)+sub[...,:3]*a
rows=[]
for b in sys.argv[1:4]:
    im=np.asarray(Image.open(A+"/backgrounds/"+b).convert("RGB"),float)[:540,:960].copy()
    for _ in range(140):
        s=random.choice(bl);paste(im,s,rng.integers(-20,960),rng.integers(-20,540))
    rows.append(im)
Image.fromarray(np.vstack(rows).astype(np.uint8)).save(sys.argv[4],quality=92)
