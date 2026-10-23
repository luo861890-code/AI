# -*- coding: utf-8 -*-
"""Fetch province-wide 长江/汉江/主要水系 from OSM Overpass for Hubei, and
gunzip the SRTM tiles so the DEM stage can run."""
import sys, os, json, subprocess, gzip, shutil, time
sys.stdout.reconfigure(encoding="utf-8")
GEO = r"C:\Users\落落晨星\AppData\Local\Temp\opencode\geo"

def overpass(q, tries=4, server="https://overpass.kumi.systems/api/interpreter"):
    for i in range(tries):
        r = subprocess.run(["curl.exe", "-s", "-m", "300", "-X", "POST", server,
                            "--data-urlencode", "data=" + q],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip()
        if out.startswith("{"):
            try:
                return json.loads(out)
            except Exception:
                pass
        time.sleep(4)
    return None

# ---- 1. major rivers in Hubei bbox ----
print("=== fetching major rivers in Hubei (OSM Overpass) ===")
Q = ('[out:json][timeout:300];'
     'way["waterway"="river"]["name"~"^(长江|汉江|汉水|清江|黄柏河|香溪河|沮河|漳河|滠水|府河|澴水|内荆河|东荆河|唐白河|汉北河)$"](29.0,108.2,33.4,116.2);'
     'out geom;')
d = overpass(Q)
print("  raw elements:", len(d["elements"]) if d else "FAILED")
if d:
    feats = []
    for e in d["elements"]:
        g = e.get("geometry") or []
        if len(g) < 2: continue
        coords = [(p["lon"], p["lat"]) for p in g if p]
        t = e.get("tags", {})
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": coords},
                      "properties": {"name": t.get("name", ""), "osm_id": e.get("id")}})
    p = os.path.join(GEO, "osm_hubei_rivers.geojson")
    json.dump({"type": "FeatureCollection", "features": feats}, open(p, "w", encoding="utf-8"),
              ensure_ascii=False)
    import collections
    c = collections.Counter(f["properties"]["name"] for f in feats)
    print("  saved", len(feats), "river lines ->", os.path.basename(p))
    print("  by name:", dict(c))

# ---- 2. gunzip DEM tiles ----
print("\n=== preparing SRTM DEM tiles ===")
n = 0
for gz in glob.glob(os.path.join(GEO, "*.hgt.gz")) if False else []:
    pass
import glob
for gz in glob.glob(os.path.join(GEO, "*.hgt.gz")):
    hgt = gz[:-3]
    if not os.path.exists(hgt):
        with gzip.open(gz, "rb") as fi, open(hgt, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        n += 1
print(f"  decompressed {n} tiles")
have = sorted(os.path.basename(x) for x in glob.glob(os.path.join(GEO, "*.hgt")))
print("  available:", have)
