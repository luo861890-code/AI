# -*- coding: utf-8 -*-
"""水系数据清洗：消除重叠 + 名称规范化 + 子湖并入主湖

核对结论：
  1. 重叠：长江河岸约 128km2 被重复绘制（relation 无名块 vs 长江合并块）；
     东湖与其子湖（郭郑湖/汤菱湖/后湖）、牛山湖与梁子湖存在重叠。
  2. 缺失感：繁体名（魯湖/嚴東湖/湯菱湖）导致简体检索不到；东湖碎片分散于子湖名。

方案（面积降序逐步保留）：
  - 湖名繁体→简体规范；同名水面先合并（每湖一块）。
  - 所有水面（含无名面）按面积从大到小排序；
  - 依次保留：当前面减去“已保留覆盖”，余量 >= 阈值才保留（重叠区并入先保留的大湖）。
  - 效果：长江河岸只渲染一次；东湖整体保留，郭郑湖/汤菱湖等子湖重叠部分并入东湖；
    完全被覆盖的无名碎片自动剔除。
"""
import json
import os
from collections import defaultdict

from shapely.geometry import shape, mapping
from shapely.ops import unary_union

GEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geo")
WATER = os.path.join(GEO, "wuhan_water.geojson")

SIMPLIFY = {
    "魯": "鲁", "嚴": "严", "湯": "汤", "長": "长", "漢": "汉", "東": "东",
    "陽": "阳", "縣": "县", "鎮": "镇", "灣": "湾", "澤": "泽",
    "塗": "涂", "瀏": "浏", "濱": "滨", "灘": "滩", "潁": "颍",
}

MIN_AREA_KM2 = 0.05   # 保留阈值（渲染过滤 0.2km2，这里更宽松防丢边界）

# 主湖优先级：重叠区优先归主湖（东湖含后湖/郭郑湖/汤菱湖等子湖）
PRIORITY = {"东湖": 5, "汤逊湖": 4, "梁子湖": 3}


def norm_name(name: str) -> str:
    return "".join(SIMPLIFY.get(ch, ch) for ch in name)


def _clean(g):
    try:
        if not g.is_valid:
            g = g.buffer(0)
        return g if g.is_valid and not g.is_empty else None
    except Exception:
        return None


def clean():
    feats = json.load(open(WATER, encoding="utf-8"))["features"]
    lines = []
    named = defaultdict(list)
    unnamed = []

    for f in feats:
        g = shape(f["geometry"])
        if g.geom_type in ("Polygon", "MultiPolygon"):
            g = _clean(g)
            if g is None:
                continue
            name = norm_name((f.get("properties") or {}).get("name", ""))
            if name:
                named[name].append(g)
            else:
                unnamed.append(g)
        else:
            lines.append(f)

    # 1) 同名湖先合并
    pool = []  # (area, name, geom)
    for name, gs in named.items():
        try:
            u = unary_union(gs)
            u = _clean(u)
            if u is not None:
                pool.append((u.area, name, u))
        except Exception:
            for g in gs:
                pool.append((g.area, name, g))
    for g in unnamed:
        pool.append((g.area, "", g))

    # 2) 主湖优先 + 面积降序，依次减去已保留覆盖
    pool.sort(key=lambda x: (-PRIORITY.get(x[1], 0), -x[0]))
    kept_union = None
    kept = []
    dropped_covered = 0
    for area, name, g in pool:
        if kept_union is not None:
            try:
                rem = g.difference(kept_union)
            except Exception:
                rem = g
        else:
            rem = g
        rem = _clean(rem)
        if rem is None or rem.area < MIN_AREA_KM2 / 9700:
            if area > MIN_AREA_KM2 / 9700:
                dropped_covered += 1
            continue
        kept_union = rem if kept_union is None else unary_union([kept_union, rem])
        kept.append({"name": name, "geom": rem})

    # 3) 输出
    out_polys = [{
        "type": "Feature",
        "properties": {"name": item["name"], "source": "cleaned"},
        "geometry": mapping(item["geom"]),
    } for item in kept]
    out = {"type": "FeatureCollection", "features": lines + out_polys}
    with open(WATER, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    total_kept = sum(item["geom"].area for item in kept) * 9700
    print(f"输入面 {len(pool)} -> 保留 {len(kept)} 个（剔除被完全覆盖 {dropped_covered} 个）")
    print(f"保留水面总面积 {total_kept:.1f}km2 -> {WATER} ({os.path.getsize(WATER)/1e6:.1f}MB)")


def remove_redundant():
    """删除冗余/重叠要素：
    1) 被水面(河岸/湖泊面)覆盖 >=95% 的河流线（线面双渲染，如长江/汉水/举水等）；
    2) 面积 <0.2km2 且无名的细小水塘。
    """
    from shapely.ops import unary_union

    feats = json.load(open(WATER, encoding="utf-8"))["features"]
    lines = [f for f in feats if shape(f["geometry"]).geom_type == "LineString"]
    polys = [f for f in feats if shape(f["geometry"]).geom_type in ("Polygon", "MultiPolygon")]

    poly_union = unary_union([shape(f["geometry"]) for f in polys])

    kept_lines = []
    removed_lines = []
    for f in lines:
        g = shape(f["geometry"])
        name = (f.get("properties") or {}).get("name", "")
        if g.length > 0 and not poly_union.is_empty:
            try:
                inter = g.intersection(poly_union).length
                if inter / g.length >= 0.95:
                    removed_lines.append(f)
                    continue
            except Exception:
                pass
        kept_lines.append(f)

    kept_polys = []
    removed_polys = 0
    for f in polys:
        g = shape(f["geometry"])
        name = (f.get("properties") or {}).get("name", "")
        # 无名且 <0.2km2 的细小水塘：渲染时本就过滤，直接剔除冗余
        if g.area < 0.2 / 9700 and not name:
            removed_polys += 1
            continue
        kept_polys.append(f)

    out = {"type": "FeatureCollection", "features": kept_lines + kept_polys}
    with open(WATER, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"冗余清理: 删除被覆盖河流线 {len(removed_lines)} 条（含 "
          f"{sum(1 for f in removed_lines if (f.get('properties') or {}).get('name'))} 条命名河）, "
          f"删除无名小水塘 {removed_polys} 个")
    print(f"剩余: 线 {len(kept_lines)} 条, 面 {len(kept_polys)} 个 -> {WATER} "
          f"({os.path.getsize(WATER)/1e6:.1f}MB)")


if __name__ == "__main__":
    clean()
    remove_redundant()
