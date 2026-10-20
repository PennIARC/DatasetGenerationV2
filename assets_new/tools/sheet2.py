import json,os,glob
import numpy as np
from PIL import Image,ImageDraw
A="/Users/pranavgupta/Desktop/PennAiR/IARCtesting/IARCdatasetGenerationV2/assets_new"
OUT="/Users/pranavgupta/Desktop/PennAiR/IARCtesting/IARCdatasetGenerationV2/docs/showcase/images/assets_contact_sheet.jpg"
M=json.load(open(os.path.dirname(os.path.abspath(__file__))+"/manifest.json"))
IDX=json.load(open(A+"/backgrounds_index.json"))
BM=json.load(open(A+"/tools/grassBlades_manifest.json"))
W=2400;pad=10
sheet=Image.new("RGB",(W,16000),(40,40,40));d=ImageDraw.Draw(sheet);y=10
def checker(w,h,c=10):
    yy,xx=np.mgrid[:h,:w];m=((xx//c+yy//c)%2)*18+118
    return Image.fromarray(np.dstack([m]*3).astype(np.uint8))
def flow(entries,th,header):
    global y
    d.text((10,y),header,fill=(255,255,0));y+=18
    x=pad;rowh=0
    for im,label in entries:
        tw,tt=im.size
        if x+tw>W-pad: x=pad;y+=rowh+14;rowh=0
        sheet.paste(im,(x,y));d.text((x+2,y+tt+1),label,fill=(255,255,255))
        x+=tw+pad;rowh=max(rowh,tt)
    y+=rowh+34
def rgbthumb(p,th,tag):
    t=Image.open(p).convert("RGB");t.thumbnail((th*16//9,th));return t
def cutthumb(p,th,up=2.5,bgc=None,zoom=None):
    im=Image.open(p).convert("RGBA");t=im.copy()
    if zoom: t=t.resize((int(t.width*zoom),int(t.height*zoom)),Image.LANCZOS)
    if max(t.size)>th:t.thumbnail((th,th),Image.LANCZOS)
    else:
        f=min(th/max(t.size),up);t=t.resize((max(1,int(t.width*f)),max(1,int(t.height*f))),Image.LANCZOS)
    bg=checker(th,th) if bgc is None else Image.new('RGB',(th,th),bgc);bg.paste(t,((th-t.width)//2,(th-t.height)//2),t);return bg
fw=IDX["family_weights"]
d.text((10,y),f"BACKGROUNDS: sampling family_weights grass={fw['grass']}, non_grass={fw['non_grass']} (pick family, then item by weight). v1 = original assets (read-only); '*' = down-weighted; items with weight 0 are dropped and not shown.",fill=(0,255,255));y+=24
cats=["grass_fresh","grass_olive","grass_dry","grass_patchy","moss_clover","soil","gravel","sand","mixed_ground"]
V1="/Users/pranavgupta/PycharmProjects/IARCdatasetGeneration/DatasetGenerator/assets/backgrounds/"
for c in cats:
    its=[i for i in IDX["backgrounds"] if i["category"]==c and i["weight"]>0]
    ents=[]
    for i in its:
        p=V1+i["path"] if i["source"]=="v1" else A+"/"+i["path"]
        lab=("v1:" if i["source"]=="v1" else "")+os.path.basename(i["path"]).replace("bg_","").replace(".jpg","").replace(".png","")[:28]+("*" if i["weight"]<1 else "")
        ents.append((rgbthumb(p,100,c),lab))
    fam="grass" if c.startswith(("grass","moss")) else "non_grass"
    flow(ents,100,f"[{fam}] {c} ({len(its)})")
flow([(cutthumb(f"{A}/rocks/{fn}",128),s+f" {sz[0]}x{sz[1]}") for fn,s,sz in M["rocks"]],128,f"rocks ({len(M['rocks'])})")
flow([(cutthumb(f"{A}/grassDebris/{fn}",150),s+f" {sz[0]}x{sz[1]}") for fn,s,sz in M["grassDebris"]],150,f"grassDebris ({len(M['grassDebris'])})")
for kind,th in (("blade",260),("tuft",200),("wisp",200)):
    es=[(cutthumb(f"{A}/grassBlades/{fn}",th,1.0),f"{fn[:-4]} {sz[0]}x{sz[1]}") for fn,s,sz in BM if fn.startswith(kind)]
    flow(es,th,f"grassBlades/ {kind} ({len(es)}), procedural, shown 1:1 (scaled down if >{th}px)")
DI=json.load(open(A+"/dirt/index.json"))["items"]
flow([(cutthumb(f"{A}/dirt/{e['file']}",150,2.0),f"{e['kind']} {e['source']} {e['size'][0]}x{e['size'][1]} op{e['opacity'][0]}-{e['opacity'][1]}") for e in DI],150,f"dirt on checkerboard ({len(DI)}): soft/dissolved edges; clod=raised lump (shadow), patch=flat overlay, dust=very soft low opacity")
flow([(cutthumb(f"{A}/dirt/{e['file']}",150,2.0,bgc=(70,120,50)),e['file'][5:30]) for e in DI],150,"dirt on green background (edge blend check)")
ws=[(fn,sz) for fn,s_,sz in BM if fn.startswith("wisp")]
flow([(cutthumb(f"{A}/grassBlades/{fn}",330,2.0,zoom=2.0),f"{fn[:-4]} 2x") for fn,sz in ws],330,f"ZOOM 2x: wisps ({len(ws)}) (thin strands, curved, tangles, stubble, hair-like)")
bs=[(fn,sz) for fn,s_,sz in BM if fn.startswith("blade")][:16]
flow([(cutthumb(f"{A}/grassBlades/{fn}",330,2.0,zoom=2.0),f"{fn[:-4]} 2x") for fn,sz in bs],330,"ZOOM 2x: blades (first 16)")
os.makedirs(os.path.dirname(OUT),exist_ok=True)
sheet.crop((0,0,W,y)).save(OUT,quality=88)
