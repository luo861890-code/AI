# -*- coding: utf-8 -*-
"""本地地理数据优化：Douglas-Peucker 几何简化（视觉无损，减小数据体量）

对道路/水系/轨道交通坐标做轻量简化（容差约 20~30m），
大幅减小 maps.json 落盘体积与内存占用，地图视觉基本无差异。
"""
import json
import os

GEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geo")

# (文件名, 简化容差(度))  —— 0.0003度≈33m，0.0002≈22m，0.0001≈11m
PLANS = [
    ("wuhan_roads.geojson", 0.0002),
    # 水系用更小容差（≈11m）：保留自然河湖的微弯，避免出现"笔直长段"假象
    ("wuhan_water.geojson", 0.0001),
    ("wuhan_transit.geojson", 0.0002),
    ("hubei_cities.geojson", 0.0005),
    ("wuhan_districts.geojson", 0.0005),
]


def simplify_coords(coords, tol):
    """对坐标序列做 Douglas-Peucker 简化（支持 [lng,lat] 点序列）"""
    try:
        from shapely.geometry import LineString, Polygon, MultiPolygon
        from shapely.geometry import shape, mapping
    except ImportError:
        return coords  # 无 shapely 时原样保留

    g = shape({"type": "LineString", "coordinates": coords})
    sg = g.simplify(tol, preserve_topology=True)
    return list(sg.coords)


def simplify_geometry(geom, tol):
    from shapely.geometry import shape, mapping
    try:
        g = shape(geom)
    except Exception:
        return geom
    if g.is_empty:
        return geom
    sg = g.simplify(tol, preserve_topology=True)
    return mapping(sg)


def main():
    total_before = 0
    total_after = 0
    for fname, tol in PLANS:
        path = os.path.join(GEO, fname)
        if not os.path.exists(path):
            print(f"跳过（不存在）: {fname}")
            continue
        d = json.load(open(path, encoding="utf-8"))
        feats = d.get("features", [])
        before = os.path.getsize(path)
        for f in feats:
            g = f.get("geometry") or {}
            gtype = g.get("type", "")
            if gtype in ("LineString", "Polygon", "MultiPolygon"):
                f["geometry"] = simplify_geometry(g, tol)
        out = os.path.join(GEO, fname)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": feats}, fh, ensure_ascii=False)
        after = os.path.getsize(out)
        total_before += before
        total_after += after
        print(f"{fname}: {before/1e6:.1f}MB -> {after/1e6:.1f}MB ({100*(1-after/before):.0f}% 减小)")
    print(f"合计: {total_before/1e6:.1f}MB -> {total_after/1e6:.1f}MB")


if __name__ == "__main__":
    main()
