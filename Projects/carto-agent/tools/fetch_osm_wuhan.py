# -*- coding: utf-8 -*-
"""从 Overpass API 抓取武汉周边 OSM 数据（制图综合数据源）。

输出:
  backend/data/geo/wuhan_peaks.geojson     山峰点(natural=peak, 含ele) - 用于DEM校验
  backend/data/geo/wuhan_builtup.geojson   居民地街区(landuse=residential) - 街区形状概括
  backend/data/geo/wuhan_riverlines.geojson 河流中心线(waterway=river/canal/stream) - 双线河→单线河过渡
"""
import json
import os
import subprocess
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_DIR = os.path.join(ROOT, "backend", "data", "geo")

# 武汉行政边界略扩的 bbox (south, west, north, east)
BBOX = "29.93,113.66,31.40,115.12"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def query_overpass(q: str, timeout: int = 300) -> dict:
    last_err = None
    with tempfile.NamedTemporaryFile("w", suffix=".ql", delete=False, encoding="utf-8") as f:
        f.write(q)
        qpath = f.name
    try:
        for ep in ENDPOINTS:
            out = os.path.join(os.path.dirname(qpath), "ov_out.json")
            try:
                r = subprocess.run(
                    ["curl.exe", "-s", "--max-time", str(timeout),
                     "--data-binary", "@" + qpath, "-o", out, ep],
                    capture_output=True, timeout=timeout + 30,
                )
                if r.returncode == 0 and os.path.exists(out):
                    with open(out, "r", encoding="utf-8") as fo:
                        data = json.load(fo)
                    if "elements" in data or "error" not in data:
                        return data
                    last_err = f"{ep}: {data.get('remark', data)}"
                else:
                    last_err = f"{ep}: curl rc={r.returncode} {r.stderr.decode('utf-8', 'ignore')[:200]}"
            except Exception as e:
                last_err = f"{ep}: {e}"
            time.sleep(3)
    finally:
        if os.path.exists(qpath):
            os.remove(qpath)
    raise RuntimeError(f"Overpass 查询失败: {last_err}")


def save(name: str, features: list) -> None:
    path = os.path.join(GEO_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
    print(f"saved {path}: {len(features)} features")


def main():
    os.makedirs(GEO_DIR, exist_ok=True)

    # 1) 山峰点
    q_peak = f"""
    [out:json][timeout:300];
    node["natural"="peak"]({BBOX});
    out body;"""
    try:
        data = query_overpass(q_peak)
        feats = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
                "properties": {
                    "name": tags.get("name", ""),
                    "ele": tags.get("ele", ""),
                    "source": "osm",
                },
            })
        save("wuhan_peaks.geojson", feats)
    except Exception as e:
        print("[peaks]", e)

    # 2) 居民地街区面（landuse=residential）
    q_builtup = f"""
    [out:json][timeout:300];
    way["landuse"="residential"]({BBOX});
    out geom;"""
    try:
        data = query_overpass(q_builtup)
        feats = []
        for el in data.get("elements", []):
            g = el.get("geometry")
            if not g or len(g) < 3:
                continue
            ring = [[p["lon"], p["lat"]] for p in g]
            tags = el.get("tags", {})
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {"name": tags.get("name", ""), "source": "osm"},
            })
        save("wuhan_builtup.geojson", feats)
    except Exception as e:
        print("[builtup]", e)

    # 3) 河流中心线（双线河→单线河过渡用）
    q_rivers = f"""
    [out:json][timeout:300];
    way["waterway"~"^(river|canal|stream)$"]({BBOX});
    out geom;"""
    try:
        data = query_overpass(q_rivers)
        feats = []
        for el in data.get("elements", []):
            g = el.get("geometry")
            if not g or len(g) < 2:
                continue
            line = [[p["lon"], p["lat"]] for p in g]
            tags = el.get("tags", {})
            feats.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": line},
                "properties": {
                    "name": tags.get("name", ""),
                    "waterway": tags.get("waterway", ""),
                    "source": "osm",
                },
            })
        save("wuhan_riverlines.geojson", feats)
    except Exception as e:
        print("[rivers]", e)


if __name__ == "__main__":
    main()
