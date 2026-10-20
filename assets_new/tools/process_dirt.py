import os,glob,json,shutil,re,random
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
import sys
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
from soften_alpha import soften_alpha
A=os.path.normpath(HERE+"/..");D=A+"/dirt";R=A+"/rocks"
rng=np.random.default_rng(11);random.seed(11)
OR=D+"/_orig_sharp"
if not os.path.isdir(OR):
    os.makedirs(OR)
    for f in glob.glob(D+"/*.png"): shutil.copy(f,OR)
orig=sorted(glob.glob(OR+"/*.png"))
KIND_OP={"clod":(0.9,1.0),"patch":(0.6,0.95),"dust":(0.15,0.5)}
move={"dirt_clod_00_Ground001":"mossy","dirt_clod_09_Ground032":"grey","dirt_clod_15_Ground018":"dark","dirt_clod_12_Ground005":"beige"}
drop={"dirt_clod_18_Ground027":"cream cartoon-like blob","dirt_patch_16_Ground021":"blue-grey gravel","dirt_patch_19_Ground030":"pale grey, not soil",
      "dirt_dust_20_Ground033":"cream sand blob","dirt_patch_07_Ground026":"peach/orange, unnatural","dirt_dust_05_Ground020":"gravel/debris flecks, not soil"}
for f in glob.glob(D+"/*.png"): os.remove(f)
def sz_width(im,lo,hi,rg):
    return float(np.clip(max(im.shape[:2])*rg.uniform(lo,hi),3,12))
index=[];notes={"moved_to_rocks":[],"dropped":[]}
# ---- rocks from stone-like "clods"
for f in orig:
    k=os.path.basename(f)[:-4]
    if k in move:
        a=np.asarray(Image.open(f).convert("RGBA"));al=a[...,3]>128
        dist=ndi.distance_transform_edt(al);rim=np.clip(dist/(max(a.shape[:2])*.07),0,1)
        arr=a[...,:3]*(0.66+0.34*rim**0.8)[...,None]
        out=np.dstack([arr,ndi.gaussian_filter((al).astype(float),0.9)*255]).clip(0,255).astype(np.uint8)
        im=Image.fromarray(out,"RGBA");bb=im.getchannel("A").point(lambda v:255 if v>8 else 0).getbbox();im=im.crop(bb)
        w,h=im.size;m=max(w,h);cv=Image.new("RGBA",(m,m),(0,0,0,0));cv.paste(im,((m-w)//2,(m-h)//2))
        s=int(min(m,rng.integers(96,150)));cv=cv.resize((s,s),Image.LANCZOS)
        nm=f"rock_{move[k]}_{k.split('_')[-1]}.png";cv.save(R+"/"+nm,optimize=True);notes["moved_to_rocks"].append(nm)
# ---- kept originals, softened
for f in orig:
    k=os.path.basename(f)[:-4]
    if k in move: continue
    if k in drop: notes["dropped"].append((k,drop[k]));continue
    kind=k.split("_")[1]
    a=np.asarray(Image.open(f).convert("RGBA"))
    wd=sz_width(a,.03,.06,rng) if kind=="clod" else sz_width(a,.05,.1,rng)
    out=soften_alpha(a,wd,2.5,seed=int(rng.integers(1e9)),dissolve=0.7 if kind=="clod" else 1.0)
    Image.fromarray(out,"RGBA").save(f"{D}/{k}.png",optimize=True)
    index.append(dict(file=k+".png",kind=kind,opacity=KIND_OP[kind],casts_shadow=kind=="clod",source=k.split("_")[-1],size=list(out.shape[1::-1]),soften_width=round(wd,1)))
# ---- new soil snippets
def load(a): return Image.open(glob.glob(f"{A}/raw_downloads/ambientcg/{a}/*_Color.jpg")[0]).convert("RGB")
def noise(n,sig):
    z=ndi.gaussian_filter(rng.standard_normal((n,n)),sig,mode="wrap");return z/z.std()
def blob(n,aspect,rough):
    y,x=np.mgrid[:n,:n].astype(float);c=(n-1)/2;ang=rng.uniform(0,np.pi)
    X=((x-c)*np.cos(ang)+(y-c)*np.sin(ang))/aspect**.5;Y=(-(x-c)*np.sin(ang)+(y-c)*np.cos(ang))*aspect**.5
    r=np.hypot(X,Y)/(n*.44);th=np.arctan2(Y,X)
    return r-(1+sum(rng.normal(0,rough/(k**.8))*np.cos(k*th+rng.uniform(0,6.28)) for k in range(2,8)))
SOIL=["Ground002","Ground009","Ground023","Ground031","Ground008","Ground004","Ground012","Ground029","Ground049A","Ground005"]
plan=[("clod",7),("patch",6),("dust",5)]
j=0
for kind,cnt in plan:
    for i in range(cnt):
        src=SOIL[(j*2+i)%len(SOIL)] if kind!="dust" else SOIL[(j+3)%len(SOIL)];j+=1
        im=load(src);w,h=im.size
        cs=int(rng.uniform(150,260)) if kind=="clod" else int(rng.uniform(.25,.5)*min(w,h))
        cs=min(cs,min(w,h)-1);l=int(rng.integers(0,w-cs));t=int(rng.integers(0,h-cs));S=256 if kind!="clod" else cs
        c=np.asarray(im.crop((l,t,l+cs,t+cs)).resize((S,S),Image.LANCZOS),float)
        if kind=="clod":
            d=blob(S,rng.uniform(1,1.5),rng.uniform(.1,.2))
            al=(d<0).astype(float)
            dist=ndi.distance_transform_edt(al>0.5)
            c=c*(0.55+0.45*np.clip(dist/ (S*.12),0,1)**.8)[...,None]      # lump shading: dark rim
            wd=float(rng.uniform(3,5));nz=2.0;ds=.6
        else:
            d=blob(S,rng.uniform(1,1.6),rng.uniform(.15,.25))
            al=(d<-0.0).astype(float)
            wd=float(rng.uniform(8,12));nz=2.5;ds=1.0
        rgba=np.dstack([np.clip(c,0,255),al*255]).astype(np.uint8)
        # crop to bbox, scale to target size
        bb=np.argwhere(al>0.5);y0,x0=bb.min(0);y1,x1=bb.max(0)+1
        rgba=rgba[y0:y1,x0:x1];tgt=int(rng.integers(40,110)) if kind=="clod" else int(rng.integers(100,230))
        sc=min(1.0,tgt/max(rgba.shape[:2]))
        pil=Image.fromarray(rgba,"RGBA").resize((max(8,int(rgba.shape[1]*sc)),max(8,int(rgba.shape[0]*sc))),Image.LANCZOS)
        padn=int(wd)+2;arr=np.pad(np.asarray(pil),((padn,padn),(padn,padn),(0,0)),mode="edge");arr[...,3][:padn]=0;arr[...,3][-padn:]=0;arr[...,3][:,:padn]=0;arr[...,3][:,-padn:]=0
        out=soften_alpha(arr,wd,nz,seed=int(rng.integers(1e9)),dissolve=ds)
        if kind=="dust":
            a=ndi.gaussian_filter(out[...,3].astype(float),3.5)*rng.uniform(.75,1.0);out[...,3]=np.clip(a,0,255).astype(np.uint8)
        name=f"dirt_{kind}_n{i:02d}_{src}.png";Image.fromarray(out,"RGBA").save(f"{D}/{name}",optimize=True)
        index.append(dict(file=name,kind=kind,opacity=KIND_OP[kind],casts_shadow=kind=="clod",source=src,size=list(out.shape[1::-1]),soften_width=round(wd,1)))
json.dump(dict(description="kind: clod = raised soil lump (draw a small soft shadow beside it, opacity 0.9-1.0), patch = flat soil/dust patch (alpha overlay only, no shadow, opacity 0.6-0.95), dust = very soft low-opacity (0.15-0.5). Soft edges already baked; re-soften at composite time with tools/soften_alpha.py. Originals with sharp alpha in _orig_sharp/ (not for generator use).",items=index),open(D+"/index.json","w"),indent=1)
json.dump(notes,open(HERE+"/dirt_notes.json","w"),indent=1)
M=json.load(open(HERE+"/manifest.json"))
M["dirt"]=[[e["file"],e["source"],e["size"]] for e in index]
M["rocks"]=[r for r in M["rocks"] if not r[0].startswith("rock_mossy")]  # idempotent
for nm in notes["moved_to_rocks"]:
    M["rocks"].append([nm,nm.split("_")[-1][:-4],list(Image.open(R+"/"+nm).size)])
json.dump(M,open(HERE+"/manifest.json","w"))
from collections import Counter
print(Counter(e["kind"] for e in index),len(index),notes)
