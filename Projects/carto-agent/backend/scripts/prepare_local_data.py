# -*- coding: utf-8 -*-
"""扩充本地地理数据库：湖北省市级边界 / 武汉市辖区 / 武汉旅游POI / 武汉轨道交通

数据来源：
  - 湖北省市级边界、武汉市辖区：DataV GeoAtlas 公开区划数据（无需Key）
  - 旅游POI、轨道交通：OpenStreetMap Overpass API

用法（需联网，本机执行一次）：
    python prepare_local_data.py

输出到 backend/data/geo/：
    hubei_cities.geojson   湖北省 13 个地级市 + 省直辖县级市/林区面（上一级行政边界）
    wuhan_districts.geojson 武汉市 13 个区县面（行政区划图底图）
    wuhan_tourism.geojson   武汉市旅游景点/博物馆/公园等 POI
    wuhan_transit.geojson   武汉市铁路/地铁/轻轨线网与站点
"""
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("缺少依赖，请先安装: pip install requests")
    sys.exit(1)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geo")
os.makedirs(OUT, exist_ok=True)

# 武汉市范围 bbox：南/西/北/东
BBOX = (30.05, 113.85, 31.20, 114.95)
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]
DATAV_URL = "https://geo.datav.aliyun.com/areas_v3/bound"


def overpass(query: str) -> dict:
    """执行 Overpass 查询（多服务器重试）"""
    last = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, timeout=240,
                              headers={"User-Agent": "CartoAgent/1.0 (data-prep)"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            print(f"  Overpass 服务器失败 ({url}): {e}")
            time.sleep(2)
    raise SystemExit(f"所有 Overpass 服务器均不可用: {last}")


def datav(adcode: str) -> dict:
    """获取 DataV GeoAtlas 区划 GeoJSON（重试3次）"""
    url = f"{DATAV_URL}/{adcode}_full.json"
    last = None
    for i in range(3):
        try:
            r = requests.get(url, timeout=60,
                             headers={"User-Agent": "CartoAgent/1.0 (data-prep)"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            print(f"  DataV 获取失败 {adcode} (第{i + 1}次): {e}")
            time.sleep(2)
    raise SystemExit(f"DataV 获取失败 {adcode}: {last}")


def save(fname: str, fc: dict) -> None:
    path = os.path.join(OUT, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    print(f"  已导出 {path} ({len(fc.get('features', []))} 要素, {os.path.getsize(path) / 1024:.0f} KB)")


def main():
    sw, w, ne, e = BBOX
    bbox_str = f"({sw},{w},{ne},{e})"

    # ---- 1. 湖北省市级边界（DataV 420000_full）----
    print("下载湖北省市级边界 (DataV 420000_full)...")
    hb = datav("420000")
    save("hubei_cities.geojson", {
        "type": "FeatureCollection",
        "features": hb.get("features", []),
    })

    # ---- 2. 武汉市辖区面（DataV 420100_full）----
    print("下载武汉市辖区面 (DataV 420100_full)...")
    wh = datav("420100")
    save("wuhan_districts.geojson", {
        "type": "FeatureCollection",
        "features": wh.get("features", []),
    })

    # ---- 3. 武汉旅游POI（OSM：tourism/historic/leisure=park/文化场馆）----
    print("下载武汉旅游POI (OSM Overpass)...")
    tourism_q = f"""[out:json][timeout:240];
(
  node["tourism"~"attraction|museum|zoo|theme_park|viewpoint|artwork|information|hotel|hostel|guest_house|picnic_site"]{bbox_str};
  way["tourism"~"attraction|museum|zoo|theme_park|viewpoint|artwork|picnic_site"]{bbox_str};
  node["historic"~"monument|memorial|castle|ruins|archaeological_site"]{bbox_str};
  way["historic"~"monument|memorial|castle|ruins|archaeological_site"]{bbox_str};
  node["leisure"="park"]{bbox_str};
  way["leisure"="park"]{bbox_str};
  node["amenity"~"arts_centre|theatre|cinema|library|place_of_worship"]{bbox_str};
);
out center;"""
    tr = overpass(tourism_q)
    tr_features = []
    for el in tr.get("elements", []):
        c = el.get("center") or ({"lon": el.get("lon"), "lat": el.get("lat")} if el.get("lat") is not None else None)
        if not c or c.get("lon") is None or c.get("lat") is None:
            continue
        tags = el.get("tags", {})
        name = tags.get("name", "")
        if not name:
            continue
        t = (tags.get("tourism") or tags.get("historic") or tags.get("leisure")
             or tags.get("amenity") or "poi")
        tr_features.append({
            "type": "Feature",
            "properties": {"name": name, "category": t, "tags": tags},
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
        })
    save("wuhan_tourism.geojson", {"type": "FeatureCollection", "features": tr_features})

    # ---- 4. 武汉轨道交通/铁路（OSM：线路 + 站点）----
    print("下载武汉轨道交通/铁路 (OSM Overpass)...")
    transit_q = f"""[out:json][timeout:240];
(
  way["railway"~"rail|subway|light_rail|monorail|tram"]["service"!~"yard|siding|spur|crossover|depot|industrial|workshop"]{bbox_str};
  node["railway"~"station|halt|subway_entrance"]{bbox_str};
);
out geom;"""
    rt = overpass(transit_q)
    rt_features = []
    for el in rt.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name", "")
        gtype = el.get("type")
        if gtype == "way":
            geo = el.get("geometry") or []
            pts = [[p["lon"], p["lat"]] for p in geo if "lon" in p and "lat" in p]
            if len(pts) < 2:
                continue
            rt_features.append({
                "type": "Feature",
                "properties": {"name": name, "railway": tags.get("railway", ""), "kind": "line"},
                "geometry": {"type": "LineString", "coordinates": pts},
            })
        elif gtype == "node":
            if el.get("lon") is None:
                continue
            rt_features.append({
                "type": "Feature",
                "properties": {"name": name, "railway": tags.get("railway", ""), "kind": "station"},
                "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
            })
    save("wuhan_transit.geojson", {"type": "FeatureCollection", "features": rt_features})

    print("全部完成。重启后端后自动加载扩充数据。")


if __name__ == "__main__":
    main()
