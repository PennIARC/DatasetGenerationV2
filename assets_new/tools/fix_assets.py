"""Audit remediation (run once): rejects, native-res rocks, defringed leaf clumps, grainy dust, extra real-grass bgs."""
import os,glob,json,shutil,random,sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
A=os.path.normpath(HERE+"/..")
rng=np.random.default_rng(2024)
def rej(cat,names):
    d=f"{A}/{cat}/_rejected";os.makedirs(d,exist_ok=True)
    for n in names:
        p=f"{A}/{cat}/{n}"
        if os.path.exists(p): shutil.move(p,d+"/"+n)
# ---------------- backgrounds
BG_REJECT=["bg_Ground092A","bg_Ground033","bg_Ground034","bg_Ground049A","bg_Ground027","bg_Ground022","bg_Ground023","bg_Ground019",
 "bg_Ground009","bg_Gravel020","bg_Gravel016","bg_Ground007","bg_Ground011",
 "bg_real_06_Grass007_grass_dry","bg_real_07_Grass007_grass_patchy","bg_real_10_Grass002_grass_olive","bg_real_11_Grass002_grass_dry"]
rej("backgrounds",[n+".jpg" for n in BG_REJECT])
import grass_backgrounds as G
newreal=[("Grass006","grass_patchy",1),("Grass004","grass_fresh",0),("Grass008","grass_dry",1),("Moss001","grass_olive",0),("Grass003","grass_olive",1),("Grass006","grass_fresh",0)]
gm=json.load(open(HERE+"/grass_bg_manifest.json"))
have={m[0] for m in gm}
for k,(src,kind,dap) in enumerate(newreal):
    i=20+k;fn=f"bg_real_{i:02d}_{src}_{kind}.jpg"
    if fn in have: continue
    G.treat(src,kind,300+i,dap).save(f"{A}/backgrounds/{fn}",quality=96,subsampling=0)
    gm.append([fn,kind,"real",src,bool(dap)])
json.dump(gm,open(HERE+"/grass_bg_manifest.json","w"))
# ---------------- rocks
def load(a): return Image.open(glob.glob(f"{A}/raw_downloads/ambientcg/{a}/*_Color.jpg")[0]).convert("RGB")
def blob(n,aspect,rough):
    y,x=np.mgrid[:n,:n].astype(float);c=(n-1)/2;ang=rng.uniform(0,np.pi)
    X=((x-c)*np.cos(ang)+(y-c)*np.sin(ang))/aspect**.5;Y=(-(x-c)*np.sin(ang)+(y-c)*np.cos(ang))*aspect**.5
    r=np.hypot(X,Y)/(n*.44);th=np.arctan2(Y,X)
    return r-(1+sum(rng.normal(0,rough/(k**.9))*np.cos(k*th+rng.uniform(0,6.28)) for k in range(2,6)))
def rock_native(src,s):
    im=load(src);w,h=im.size;l=int(rng.integers(0,w-s));t=int(rng.integers(0,h-s))
    arr=np.asarray(im.crop((l,t,l+s,t+s)),float)  # native pixels, no resampling
    d=blob(s,rng.uniform(1,1.5),rng.uniform(.05,.1))
    a=ndi.gaussian_filter(np.clip(-d*s*.44*.5+.5,0,1),.7)
    dist=ndi.distance_transform_edt(a>.5);rim=np.clip(dist/(s*.08),0,1)
    arr=arr*(0.68+0.32*rim**.8)[...,None]
    return Image.fromarray(np.dstack([arr.clip(0,255),a*255]).astype(np.uint8),"RGBA")
R=A+"/rocks"
rej("rocks",["rock_03_Rock004.png","rock_14_Gravel001.png","rock_15_Gravel002.png","rock_16_Gravel003.png","rock_17_Gravel004.png","rock_28_Rock009.png","rock_dark_Ground018.png"])
regen={"rock_04_Rock005":"Rock005","rock_06_Rock007":"Rock007","rock_07_Rock008":"Rock008","rock_10_Rock011":"Rock011","rock_24_Rock005":"Rock005","rock_25_Rock006":"Rock006","rock_18_Gravel005":"Gravel005","rock_19_Gravel006":"Gravel006"}
for k,src in regen.items():
    if os.path.exists(f"{R}/{k}.png"): shutil.copy(f"{R}/{k}.png",f"{R}/_rejected/{k}__old.png") if os.path.isdir(f"{R}/_rejected") else None
    rock_native(src,int(rng.choice([72,88,104,120,136]))).save(f"{R}/{k}.png",optimize=True)
for i,src in enumerate(["Rock001","Rock003","Rock009","Rock012","Rock013","Rock014"]):
    rock_native(src,int(rng.choice([80,96,112,128,144]))).save(f"{R}/rock_nat_{i:02d}_{src}.png",optimize=True)
# ---------------- leaf clumps (grassDebris)
GD=A+"/grassDebris"
rej("grassDebris",["grass_21_ScatteredLeaves004.png","grass_22_ScatteredLeaves005.png","grass_23_ScatteredLeaves006.png"])
def defringe(a):
    rgb=a[...,:3].astype(float);al=a[...,3].astype(float)/255
    lab,n=ndi.label(al>0.1,structure=np.ones((3,3)))
    sz=ndi.sum(np.ones_like(al),lab,range(1,n+1));small=np.isin(lab,[i+1 for i,v in enumerate(sz) if v<25])
    al=np.where(small,0,al)
    al=ndi.minimum_filter(al,3)             # erode ~1px
    al=ndi.gaussian_filter(al,0.6)
    core=al>0.97
    if core.sum()>20:
        idx=ndi.distance_transform_edt(~core,return_distances=False,return_indices=True)
        bled=rgb[idx[0],idx[1]]
        w=np.clip(1-al/0.97,0,1)[...,None]            # edge pixels take interior colour
        rgb=rgb*(1-w)+bled*w
    out=np.dstack([rgb.clip(0,255),al*255]).astype(np.uint8)
    bb=np.argwhere(out[...,3]>10);y0,x0=bb.min(0);y1,x1=bb.max(0)+1
    return out[y0:y1,x0:x1]
for f in glob.glob(GD+"/grass_*.png"):
    Image.fromarray(defringe(np.asarray(Image.open(f).convert("RGBA"))),"RGBA").save(f,optimize=True)
# ---------------- dirt
D=A+"/dirt"
rej("dirt",["dirt_clod_n00_Ground002.png","dirt_patch_01_Ground004.png","dirt_patch_n02_Ground002.png","dirt_patch_n03_Ground031.png"])
from soften_alpha import soften_alpha
def grain(a,seed):
    r=np.random.default_rng(seed);rgb=a[...,:3].astype(float);al=a[...,3].astype(float)
    lo=np.stack([ndi.gaussian_filter(rgb[...,c],2.0) for c in range(3)],-1)
    rgb=rgb+0.9*(rgb-lo)                                 # unsharp: bring back fine texture
    g=ndi.gaussian_filter(r.standard_normal(al.shape),0.7);g/=g.std()
    rgb=rgb+g[...,None]*9                                # fine grain
    al=al*(1+0.18*ndi.gaussian_filter(r.standard_normal(al.shape),0.8)/0.3*0.3)  # grainy alpha
    return np.dstack([rgb.clip(0,255),al.clip(0,255)]).astype(np.uint8)
for f in glob.glob(D+"/dirt_dust_*.png"):
    a=np.asarray(Image.open(f).convert("RGBA"));Image.fromarray(grain(a,hash(f)%10**6),"RGBA").save(f,optimize=True)
# fix possible fringe in patch_n01: re-soften with colour bleed
f=D+"/dirt_patch_n01_Ground029.png";a=np.asarray(Image.open(f).convert("RGBA"))
Image.fromarray(soften_alpha(defringe_pad:=np.pad(a,((6,6),(6,6),(0,0))),8,2.2,seed=5,dissolve=0.8) if False else defringe(a),"RGBA").save(f,optimize=True)
# new native-res clods/patches
SOIL=["Ground002","Ground031","Ground012","Ground008","Ground004"]
idx=json.load(open(D+"/index.json"))
items=[e for e in idx["items"] if os.path.exists(f"{D}/{e['file']}")]
def newdirt(kind,i,src,s,wd):
    im=load(src);w,h=im.size;l=int(rng.integers(0,w-s));t=int(rng.integers(0,h-s))
    c=np.asarray(im.crop((l,t,l+s,t+s)),float)
    d=blob(s,rng.uniform(1,1.5),rng.uniform(.1,.2));al=(-d*s*.44*.5+.5).clip(0,1)
    if kind=="clod":
        dist=ndi.distance_transform_edt(al>.5);c=c*(0.58+0.42*np.clip(dist/(s*.12),0,1)**.8)[...,None]
    pad=int(wd)+3
    arr=np.pad(np.dstack([c.clip(0,255),(al>.5)*255]).astype(np.uint8),((pad,pad),(pad,pad),(0,0)),mode="edge");arr[...,3][:pad]=0;arr[...,3][-pad:]=0;arr[...,3][:,:pad]=0;arr[...,3][:,-pad:]=0
    out=soften_alpha(arr,wd,2.0,seed=int(rng.integers(1e9)),dissolve=0.7 if kind=="clod" else 1.0)
    nm=f"dirt_{kind}_n{i:02d}_{src}.png";Image.fromarray(out,"RGBA").save(f"{D}/{nm}",optimize=True)
    op={"clod":(0.9,1.0),"patch":(0.6,0.95)}[kind]
    items.append(dict(file=nm,kind=kind,opacity=list(op),casts_shadow=kind=="clod",source=src,size=list(out.shape[1::-1]),soften_width=round(wd,1)))
for i,(src,s) in enumerate(zip(["Ground002","Ground031","Ground012"],[72,90,100])): newdirt("clod",7+i,src,s,4)
for i,(src,s) in enumerate(zip(["Ground008","Ground004"],[150,170])): newdirt("patch",6+i,src,s,9)
idx["items"]=items;json.dump(idx,open(D+"/index.json","w"),indent=1)
# ---------------- manifest rescan for contact sheet
M=json.load(open(HERE+"/manifest.json"))
for k,d in (("rocks","rocks"),("grassDebris","grassDebris")):
    M[k]=[[os.path.basename(p),os.path.basename(p)[:-4].split("_")[-1],list(Image.open(p).size)] for p in sorted(glob.glob(f"{A}/{d}/*.png"))]
M["dirt"]=[[e["file"],e["source"],e["size"]] for e in items]
json.dump(M,open(HERE+"/manifest.json","w"))
print({k:len(v) for k,v in M.items()})
