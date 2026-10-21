# -*- coding: utf-8 -*-
"""从 OpenStreetMap 下载武汉市水系/路网，导出为系统本地优先使用的 GeoJSON

用法（用户本机执行一次，需联网）：
    python prepare_local_geo.py
输出：
    backend/data/geo/wuhan_water.geojson
    backend/data/geo/wuhan_roads.geojson
生成后重启后端，系统自动优先使用这些精确数据（不再用手绘兜底水系）。

实现：纯 requests 直连 Overpass API（bbox 查询），不依赖 osmnx/geopandas。
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
]


def overpass(query: str, timeout: int = 300) -> dict:
    """执行 Overpass 查询（多服务器 × 多轮重试，限流时耐心等待）"""
    last = None
    for round_no in range(4):
        for url in OVERPASS_URLS:
            try:
                r = requests.post(url, data={"data": query}, timeout=timeout,
                                  headers={"User-Agent": "CartoAgent/1.0 (data-prep)"})
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last = e
                print(f"  Overpass 服务器失败 ({url}): {str(e)[:120]}")
                time.sleep(5)
        print(f"  第 {round_no + 1} 轮全部失败，等待后重试...")
        time.sleep(20)
    raise SystemExit(f"所有 Overpass 服务器均不可用: {last}")


def _ring_contains(ring: list, pt: list) -> bool:
    """射线法：点([lng,lat])是否在环内"""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[(i + 1) % n]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
    return inside


def _relation_geojson(el: dict):
    """将 relation（out geom 输出）的成员几何组装为 GeoJSON 几何

    OSM 大水体（东湖/汤逊湖/汉江等）通常为 multipolygon relation：
    role=outer 为外环，role=inner 为内环（岛）。返回 Polygon/MultiPolygon。
    """
    outer_rings, inner_rings = [], []
    for m in el.get("members", []):
        geo = m.get("geometry") or []
        pts = [[p["lon"], p["lat"]] for p in geo if "lon" in p and "lat" in p]
        if len(pts) < 4:
            continue
        if m.get("role") == "inner":
            inner_rings.append(pts)
        else:
            outer_rings.append(pts)
    if not outer_rings:
        return None
    if len(outer_rings) == 1:
        return {"type": "Polygon", "coordinates": [outer_rings[0]] + inner_rings}
    polys = []
    for ring in outer_rings:
        holes = [h for h in inner_rings if _ring_contains(ring, h[0])]
        polys.append([ring] + holes)
    return {"type": "MultiPolygon", "coordinates": polys}


def _merge_same_name_polygons(features: list) -> list:
    """按名称合并同名水面（union），使汤逊湖/长江等碎片化大水体合并为完整单体。

    仅合并名称完全相同的面要素；不跨名称、不改变几何精度。
    无名面不做合并，避免把相邻水塘糊成一片。
    """
    from shapely.geometry import shape, mapping, MultiPolygon
    from shapely.ops import unary_union

    def _clean(g):
        """清洗无效几何（自交/环问题），失败返回 None"""
        try:
            if not g.is_valid:
                g = g.buffer(0)
            return g if g.is_valid else None
        except Exception:
            return None

    by_name = {}
    out_lines = []
    for f in features:
        gtype = f["geometry"].get("type")
        if gtype in ("Polygon", "MultiPolygon"):
            name = (f.get("properties") or {}).get("name", "")
            if name:
                g = _clean(shape(f["geometry"]))
                if g is not None:
                    by_name.setdefault(name, []).append(g)
                continue
        out_lines.append(f)

    merged = []
    for name, geoms in by_name.items():
        geoms = [g for g in geoms if g is not None]
        if not geoms:
            continue
        if len(geoms) == 1:
            merged.append({
                "type": "Feature",
                "properties": {"name": name, "source": "merged"},
                "geometry": mapping(_clean(geoms[0])),
            })
            continue
        try:
            u = unary_union(geoms)
            if u.is_empty:
                continue
            merged.append({
                "type": "Feature",
                "properties": {"name": name, "source": "merged"},
                "geometry": mapping(u),
            })
        except Exception:
            # 个别复杂水体合并失败时退回未合并（保留原片）
            for g in geoms:
                cg = _clean(g)
                if cg is not None:
                    merged.append({
                        "type": "Feature",
                        "properties": {"name": name, "source": "merged"},
                        "geometry": mapping(cg),
                    })
    print(f"  同名水面合并: {len(by_name)} 组名称, 输出 {len(merged)} 个合并面")
    return out_lines + merged


def main():
    sw, w, ne, e = BBOX
    bbox_str = f"({sw},{w},{ne},{e})"

    # ---- 水系：河流/溪流/运河 + 湖泊（含 multipolygon relation，如东湖/汤逊湖/汉江）----
    print("下载武汉水系（河流/湖泊/大水体关系）...")
    water_features = []
    n_line, n_poly = 0, 0
    # 查询1：way（河流线 + 湖泊面）
    water_q = f"""[out:json][timeout:180];
(way["waterway"~"river|stream|canal|ditch|drain"]{bbox_str};
 way["natural"="water"]{bbox_str};
);
out geom;"""
    water = overpass(water_q)
    for el in water.get("elements", []):
        geo = el.get("geometry") or []
        pts = [[p["lon"], p["lat"]] for p in geo if "lon" in p and "lat" in p]
        if len(pts) < 2:
            continue
        tags = el.get("tags", {})
        name = tags.get("name", "")
        closed = len(pts) >= 4 and pts[0] == pts[-1]
        if closed and (el.get("type") == "way" and tags.get("natural") == "water"):
            water_features.append({"type": "Feature", "properties": {"name": name},
                                   "geometry": {"type": "Polygon", "coordinates": [pts]}})
            n_poly += 1
        else:
            water_features.append({"type": "Feature", "properties": {"name": name},
                                   "geometry": {"type": "LineString", "coordinates": pts}})
            n_line += 1
    # 查询2：relation（大水体 multipolygon：湖泊面/河岸面）
    rel_q = f"""[out:json][timeout:240];
(relation["natural"="water"]{bbox_str};
 relation["waterway"~"riverbank|river"]{bbox_str};
);
out geom;"""
    rel = overpass(rel_q, timeout=300)
    for el in rel.get("elements", []):
        if el.get("type") != "relation":
            continue
        geom = _relation_geojson(el)
        if geom is None:
            continue
        tags = el.get("tags", {})
        name = tags.get("name", "")
        water_features.append({
            "type": "Feature",
            "properties": {"name": name, "source": "relation"},
            "geometry": geom,
        })
        n_poly += 1
    out_w = os.path.join(OUT, "wuhan_water.geojson")
    with open(out_w, "w", encoding="utf-8") as f:
        merged_features = _merge_same_name_polygons(water_features)
        json.dump({"type": "FeatureCollection", "features": merged_features}, f, ensure_ascii=False)
    print(f"  水系已导出: {n_line} 条河流线, {n_poly} 个水面(含关系大水体) -> {out_w}")
    # 自动清洗：消除重叠、规范化湖名、主湖优先
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from clean_water_data import clean as _clean_water
        _clean_water()
        print("  水系清洗完成（去重叠/规范化湖名）")
    except Exception as e:
        print(f"  水系清洗跳过: {e}")

    # ---- 路网：主要道路 ----
    print("下载武汉路网（主要道路）...")
    road_q = f"""[out:json][timeout:120];
(way["highway"~"motorway|trunk|primary|secondary|tertiary|residential"]{bbox_str};
);
out geom;"""
    roads = overpass(road_q)
    road_features = []
    for el in roads.get("elements", []):
        geo = el.get("geometry") or []
        pts = [[p["lon"], p["lat"]] for p in geo if "lon" in p and "lat" in p]
        if len(pts) < 2:
            continue
        tags = el.get("tags", {})
        road_features.append({
            "type": "Feature",
            "properties": {"name": tags.get("name", ""), "highway": tags.get("highway", "other")},
            "geometry": {"type": "LineString", "coordinates": pts},
        })
    out_r = os.path.join(OUT, "wuhan_roads.geojson")
    with open(out_r, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": road_features}, f, ensure_ascii=False)
    print(f"  路网已导出: {len(road_features)} 段 -> {out_r}")

    print("完成。请重启后端服务，系统将自动优先使用本地精确数据。")


if __name__ == "__main__":
    main()
