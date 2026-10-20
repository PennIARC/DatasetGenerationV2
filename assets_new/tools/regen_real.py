"""Regenerate existing bg_real_* in place (same seeds/names) after changing treat(). Usage: python3 regen_real.py"""
import os,json,re,sys
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
import grass_backgrounds as G
A=G.A
for m in json.load(open(HERE+"/grass_bg_manifest.json")):
    fn,kind,how,src,dap=m
    if how!="real" or not os.path.exists(f"{A}/backgrounds/{fn}"): continue
    i=int(re.match(r"bg_real_(\d+)",fn).group(1));seed=(100 if i<20 else 300)+i
    G.treat(src,kind,seed,bool(dap)).save(f"{A}/backgrounds/{fn}",quality=96,subsampling=0);print(fn,flush=True)
