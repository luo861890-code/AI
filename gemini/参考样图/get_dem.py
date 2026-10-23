# -*- coding: utf-8 -*-
"""Download the SRTM tiles covering Hubei (lon 108-116, lat 29-33) in parallel."""
import sys, os, glob, gzip, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
GEO = r"C:\Users\落落晨星\AppData\Local\Temp\opencode\geo"
DEM = os.path.join(GEO, "dem")
os.makedirs(DEM, exist_ok=True)

tiles = [f"N{lat}E{lon}" for lat in range(29, 34) for lon in range(108, 117)]

def get(t):
    gz = os.path.join(DEM, t + ".hgt.gz")
    hgt = os.path.join(DEM, t + ".hgt")
    if os.path.exists(hgt) and os.path.getsize(hgt) > 1000000:
        return (t, "cached")
    url = f"https://elevation-tiles-prod.s3.amazonaws.com/skadi/{t[:3]}/{t}.hgt.gz"
    r = subprocess.run(["curl.exe", "-s", "-L", "-m", "300", "-o", gz, url],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(gz) or os.path.getsize(gz) < 100000:
        return (t, "FAIL")
    try:
        with gzip.open(gz, "rb") as fi, open(hgt, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    except Exception as e:
        return (t, f"GZFAIL {e}")
    return (t, f"ok {os.path.getsize(hgt)//1024}KB")

with ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(get, tiles))
ok = [r for r in res if r[1].startswith("ok")]
cached = [r for r in res if r[1] == "cached"]
bad = [r for r in res if r[1] not in ("ok", "cached") and not r[1].startswith("ok")]
print(f"downloaded {len(ok)}, cached {len(cached)}, failed {len(bad)}")
for t, s in bad: print("  FAIL", t, s)
print("tiles present:", sorted(os.path.basename(p) for p in glob.glob(os.path.join(DEM, "*.hgt"))))
