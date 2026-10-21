# -*- coding: utf-8 -*-
"""本地精确地理数据服务

读取 backend/data/geo/ 下预生成的 GeoJSON（水系/路网），
按「本地精确数据优先 → OSM → 兜底近似」三级数据架构提供图层。

数据准备（用户本机执行一次）：
  1. 用 QGIS/GDAL/tippecanoe 或运行 backend/scripts/prepare_local_geo.py
     生成 wuhan_water.geojson / wuhan_roads.geojson（详见 docs/地理数据准备说明.md）；
  2. 放入 backend/data/geo/ 目录，系统自动优先使用。

GeoJSON 约定（WGS84 EPSG:4326，坐标 [lng, lat]）：
  - wuhan_water.geojson : FeatureCollection
      * LineString -> 河流（properties.name 可选）
      * Polygon/MultiPolygon -> 湖泊（properties.name 可选）
  - wuhan_roads.geojson : FeatureCollection
      * LineString -> 道路（properties.highway: motorway/trunk/primary/secondary/tertiary/residential）
"""
import json
import os
import copy
from typing import Dict, List
from shapely.ops import unary_union

from app.utils.helpers import generate_id
from app.utils.geometry import _convex_hull, _ring_area_km2

GEO_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "geo",
)

WATER_COLOR = "#1e90ff"
# 路网分级配色：高速/主干道用暖色加粗突出，次级/支路逐级变浅变细，
# 与行政区面/水系形成清晰层级
ROAD_COLOR = {
    "motorway": "#F97316", "trunk": "#EA580C", "primary": "#94A3B8",
    "secondary": "#B9C4D0", "tertiary": "#D3DBE3", "residential": "#E6EBF0",
    "service": "#EDF1F5", "living_street": "#EDF1F5",
    "unclassified": "#E9EEF3", "other": "#E9EEF3",
    "motorway_link": "#FDA75F", "trunk_link": "#F7A05C", "primary_link": "#C0CAD6",
    "secondary_link": "#CBD4DE", "tertiary_link": "#DDE3EA",
}
ROAD_WEIGHT = {
    "motorway": 4.0, "trunk": 3.2, "primary": 2.5,
    "secondary": 2.0, "tertiary": 1.5, "residential": 1.0,
    "service": 0.8, "living_street": 0.8,
    "unclassified": 0.8, "other": 0.8,
    "motorway_link": 2.2, "trunk_link": 2.0, "primary_link": 1.6,
    "secondary_link": 1.3, "tertiary_link": 1.1,
}


class LocalGeoService:
    """读取本地 GeoJSON 并转换为系统图层（本地精确数据优先）"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or GEO_DATA_DIR
        self._boundary_cache = None   # 武汉市域边界多边形缓存（路网裁剪用）
        self._layer_cache: Dict[str, List[dict]] = {}  # 已处理图层缓存（deepcopy返回，防共享污染）

    def _cached(self, key: str, builder) -> List[dict]:
        """缓存包装：命中直接返回深拷贝；未命中构建后缓存"""
        if key in self._layer_cache:
            return copy.deepcopy(self._layer_cache[key])
        layers = builder()
        self._layer_cache[key] = layers
        return copy.deepcopy(layers)

    def _load(self, fname: str) -> dict:
        path = os.path.join(self.data_dir, fname)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[LocalGeo] 读取 {fname} 失败: {e}")
            return {}

    def get_water_layers(self, region: str = "武汉市") -> List[dict]:
        return self._cached(("water", region), lambda: self._compute_water_layers(region))

    def _compute_water_layers(self, region: str = "武汉市") -> List[dict]:
        """读取本地水系 GeoJSON → [河流polyline, 湖泊polygon, 水系注记]"""
        data = self._load("wuhan_water.geojson")
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return []
        # 市域边界（裁剪蒙版）：水系严格裁剪到武汉边界内
        poly = self._boundary_polygon(region)
        if poly is not None:
            from shapely.geometry import LineString, Polygon
            from shapely.prepared import prep
            prep_poly = prep(poly)

        big_rivers, main_rivers, minor_rivers, labels = [], [], [], []
        river_bodies = []   # 河流水面(双线河)：长江/汉江等面状水体，与湖泊分开分级

        # 多比例尺湖泊档位（面状水体制图综合·多尺度表达）：
        # 以"图上最小面积 2mm²"为选取下限，按比例尺折算实地面积阈值：
        #   概览 1:243.4万 -> 实地 >=11.8km²
        #   市域 1:65.5万  -> 实地 >=0.86km²
        #   城区 1:29.6万  -> 实地 >=0.18km²
        #   详图 (z>=13)   -> 实地 >=0.02km²
        LAKE_BANDS = [
            ("湖泊（概览级）", 11.8, 0.0012, 0.0045, 45),
            ("湖泊（市域级）", 0.86, 0.0006, 0.0022, 140),
            ("湖泊（城区级）", 0.18, 0.00035, 0.0011, 400),
            ("湖泊（详图级）", 0.02, 0.0002, 0.0, 2000),
        ]

        def _is_river_body(name: str) -> bool:
            """按名称判断面状水体是否为河流（长江/汉江/府河等）。"""
            return bool(name) and (
                name.endswith("江") or name.endswith("河") or name.endswith("渠")
                or name.endswith("港")
            )

        def _chaikin(ring, iterations=2):
            """Chaikin 平滑：圆润低点数多边形的直线拐角（不改变面积/位置）"""
            if len(ring) < 4:
                return ring
            pts = [list(p) for p in ring]
            for _ in range(iterations):
                n = len(pts)
                out = []
                for i in range(n):
                    p0 = pts[i - 1]
                    p1 = pts[i]
                    p2 = pts[(i + 1) % n]
                    p3 = pts[(i + 2) % n]
                    out.append([0.75 * p1[0] + 0.25 * p2[0], 0.75 * p1[1] + 0.25 * p2[1]])
                    out.append([0.25 * p1[0] + 0.75 * p2[0], 0.25 * p1[1] + 0.75 * p2[1]])
                pts = out
            return pts

        def _append_river(pts, name):
            if len(pts) < 2:
                return
            if name and "江" in name and len(pts) >= 8:
                big_rivers.append({"coords": pts, "name": name})
                if len(pts) >= 4:
                    labels.append({"coords": pts[len(pts) // 2], "name": name})
            elif name and len(name) >= 2:
                main_rivers.append({"coords": pts, "name": name})
            else:
                minor_rivers.append({"coords": pts, "name": name})

        lake_parts = []   # (coords[lat,lng], name, total_area)

        for feat in features:
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            name = (props.get("name") or "").strip()
            gtype = geom.get("type", "")
            coords = geom.get("coordinates") or []
            if gtype == "LineString" and len(coords) >= 2:
                raw = [[c[0], c[1]] for c in coords if len(c) >= 2]   # [lng,lat]
                if len(raw) < 2:
                    continue
                line = LineString(raw)
                if poly is not None:
                    try:
                        if prep_poly.contains(line):
                            segs = [line]
                        elif prep_poly.intersects(line):
                            inter = poly.intersection(line)
                            if inter.is_empty or inter.geom_type == "Point":
                                continue
                            segs = list(inter.geoms) if inter.geom_type == "MultiLineString" else [inter]
                        else:
                            continue
                    except Exception:
                        continue
                    for ln in segs:
                        if ln.geom_type != "LineString" or ln.length < 1e-7:
                            continue
                        _append_river([[p[1], p[0]] for p in ln.coords], name)
                else:
                    _append_river([[c[1], c[0]] for c in coords], name)
            elif gtype in ("Polygon", "MultiPolygon"):
                polys = coords if gtype == "MultiPolygon" else [coords]
                is_river_body = _is_river_body(name)
                # 整个水体（含 MultiPolygon 全部部件）的总面积，用于分桶：
                # 保证同一湖泊/河流的所有裁剪块进同一桶，避免大/中/小三档视觉重复
                total_area = sum(
                    _ring_area_km2([[c[1], c[0]] for c in pge[0] if len(c) >= 2])
                    for pge in polys if pge and len(pge[0]) >= 3
                )
                for pge in polys:
                    if not pge or len(pge[0]) < 3:
                        continue
                    ring = [[c[1], c[0]] for c in pge[0] if len(c) >= 2]
                    if len(ring) < 3:
                        continue
                    area = _ring_area_km2(ring)
                    if area < 0.02:
                        continue   # 过滤过小水面（详图级阈值以下不上图）
                    shape = Polygon([[c[0], c[1]] for c in pge[0] if len(c) >= 2])
                    if poly is not None:
                        try:
                            inter = poly.intersection(shape)
                            if inter.is_empty:
                                continue
                            parts = list(inter.geoms) if inter.geom_type == "MultiPolygon" else [inter]
                        except Exception:
                            continue
                        for part in parts:
                            if part.geom_type != "Polygon" or part.area * 111 * 95 < 0.15:
                                continue
                            r2 = [[p[1], p[0]] for p in part.exterior.coords]
                            a2 = _ring_area_km2(r2)
                            if is_river_body:
                                river_bodies.append((r2, name))
                                continue
                            # 收集后再统一分桶（先做质量过滤）
                            lake_parts.append((r2, name, total_area))
                            if name and a2 >= 1.0:
                                c0 = sum(p[0] for p in r2) / len(r2)
                                c1 = sum(p[1] for p in r2) / len(r2)
                                labels.append({"coords": [c0, c1], "name": name})
                    else:
                        if is_river_body:
                            river_bodies.append((ring, name))
                            continue
                        lake_parts.append((ring, name, total_area))
                        if name and area >= 1.0:
                            c0 = sum(p[0] for p in ring) / len(ring)
                            c1 = sum(p[1] for p in ring) / len(ring)
                            labels.append({"coords": [c0, c1], "name": name})

        # 湖泊质量处理：
        # 1) 低点数(<=8)多边形做 Chaikin 平滑，消除"蓝色直线"角形观感；
        # 2) 无名碎片被命名水面(长江/大湖等)覆盖 >=60% 的剔除，消除视觉重复
        _filtered = [(_chaikin(r[0]) if len(r[0]) <= 8 else r[0], r[1], r[2])
                     for r in lake_parts]
        named_pts = [r for r in _filtered if r[1]]
        if named_pts:
            try:
                _named_union = unary_union([
                    Polygon([(p[1], p[0]) for p in r[0]]) for r in named_pts
                    if len(r[0]) >= 4
                ])
                _out = []
                for r in _filtered:
                    if not r[1]:
                        _pp = Polygon([(p[1], p[0]) for p in r[0]])
                        if not _pp.is_valid:
                            _pp = _pp.buffer(0)
                        if (not _pp.is_empty and _pp.area > 0
                                and not _named_union.is_empty):
                            try:
                                if _pp.intersection(_named_union).area / _pp.area >= 0.6:
                                    continue
                            except Exception:
                                pass
                    _out.append(r)
                _filtered = _out
            except Exception as e:
                print(f"[LocalGeo] 湖泊去重失败(保留原样): {e}")
        # ============ 多比例尺湖泊综合（选取/合并/化简/降维/载负量）============
        # 每个比例尺档位独立执行：
        #   选取  - 实地面积 >= 档位阈值（图上 >=2mm²）
        #   合并  - 图上间距 <0.3mm 的相邻湖面聚合，保持湖群外包络与分布格局
        #   化简  - DP 简化（拓扑保持），面积变化 >20% 自动退回原几何（图形相似性）
        #   降维  - 概览级命名小湖转点状水体符号
        #   载负量- 每档最多保留 max_count 个（超出按面积从大到小截取）
        lake_bands = {name: [] for name, *_ in LAKE_BANDS}
        lake_pts_overview = []   # 概览级点状水体符号（降维）

        # 同名字湖块合并为一个湖面（消除区界裁剪造成的同一湖泊重复/重叠显示）
        _by_name = {}
        for r in _filtered:
            g = Polygon([(p[1], p[0]) for p in r[0]])
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty or g.area <= 0:
                continue
            if r[1]:
                _by_name.setdefault(r[1], []).append(g)
        _pool = []
        for r in _filtered:
            if r[1]:
                continue
            g = Polygon([(p[1], p[0]) for p in r[0]])
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty or g.area <= 0:
                continue
            _pool.append({"geom": g, "name": "", "area": g.area * 9700})
        # 同名湖块 440m 缓冲合并：修复原始数据中同一湖泊被拆成大量碎块/重叠的问题
        # （如东湖在原始数据中散成 30+ 块，直接 union 无法拼合）
        _NAME_BUF = 0.005   # ~550m：同名湖块拼合，修复碎块/重叠（东湖实测可拼回整湖）
        for nm, gs in _by_name.items():
            try:
                u = unary_union([g.buffer(_NAME_BUF) for g in gs]).buffer(-_NAME_BUF)
                parts = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
                for part in parts:
                    if part.geom_type == "Polygon" and not part.is_empty:
                        _pool.append({"geom": part, "name": nm, "area": part.area * 9700})
            except Exception:
                for g in gs:
                    _pool.append({"geom": g, "name": nm, "area": g.area * 9700})

        for bname, min_area, tol, merge_dist, max_count in LAKE_BANDS:
            sel = [dict(p) for p in _pool if p["area"] >= min_area]
            if not sel:
                continue

            # 合并：仅无名湖按图上间距阈值聚合（保持湖群外包络与分布格局）；
            # 命名湖保持独立，避免合并后丢失水体名称
            final_polys = []
            named_geoms = [g for g in sel if g["name"]]
            unnamed_geoms = [g for g in sel if not g["name"]]
            final_polys = [dict(g) for g in named_geoms]
            if merge_dist > 0 and unnamed_geoms:
                try:
                    merged = unary_union([
                        g["geom"].buffer(merge_dist) for g in unnamed_geoms
                    ]).buffer(-merge_dist)
                    mparts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
                    for mp in mparts:
                        if mp.geom_type != "Polygon" or mp.is_empty or not mp.is_valid:
                            continue
                        final_polys.append({"geom": mp, "name": "", "area": mp.area * 9700})
                except Exception as e:
                    print(f"[LocalGeo] {bname} 湖群合并失败(保留原样): {e}")
                    final_polys.extend(dict(g) for g in unnamed_geoms)
            else:
                final_polys.extend(dict(g) for g in unnamed_geoms)

            # 化简：Bend Simplify 近似（DP + 拓扑保持 + 面积变化<=20% 保护）
            out = []
            for fp in final_polys:
                if fp["area"] < min_area:
                    continue
                g = fp["geom"]
                simp = g.simplify(tol, preserve_topology=True)
                if simp.geom_type != "Polygon" or simp.is_empty or len(simp.exterior.coords) < 4:
                    simp = g
                a0 = g.area * 9700
                a1 = simp.area * 9700
                if a0 > 1e-9 and abs(a1 - a0) / a0 > 0.20:
                    simp = g      # 面积变形超限，退回原几何（保持图形相似性）
                    a1 = a0
                ring = [[p[1], p[0]] for p in simp.exterior.coords]
                if len(ring) < 4:
                    continue
                if bname == "湖泊（详图级）" and len(ring) <= 12:
                    ring = _chaikin(ring, 1)   # 详图级小湖轻度圆润
                out.append({"coords": ring, "name": fp["name"], "area": a1})

            # 载负量上限：按面积从大到小保留 max_count 个完整要素
            out.sort(key=lambda x: -x["area"])
            out = out[:max_count]
            lake_bands[bname] = out

            # 降维：概览级把命名小湖(1~12km²)转点状水体符号，避免"面过小、点更清"
            if bname == "湖泊（概览级）":
                _polygon_names = {l["name"] for l in lake_bands[bname] if l["name"]}
                for p in _pool:
                    if (p["name"] and p["name"] not in _polygon_names
                            and 1.0 <= p["area"] < 11.8):
                        c = p["geom"].centroid
                        lake_pts_overview.append({"coords": [c.y, c.x], "name": p["name"]})

        layers = []
        if big_rivers:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "大江大河",
                "coordinates": [r["coords"] for r in big_rivers],
                "properties": [{"name": r["name"], "subtype": "river"} for r in big_rivers],
                # 长江等大江：深蓝加粗高亮，突出主干水系
                "style": {"color": "#1677d1", "weight": 4.5, "opacity": 1.0},
            })
        if main_rivers:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "主要河流",
                "coordinates": [r["coords"] for r in main_rivers],
                "properties": [{"name": r["name"], "subtype": "river"} for r in main_rivers],
                "style": {"color": "#4a90d9", "weight": 2.2, "opacity": 0.9},
            })
        if minor_rivers:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "支流溪流",
                "coordinates": [r["coords"] for r in minor_rivers],
                "properties": [{"name": r["name"], "subtype": "stream"} for r in minor_rivers],
                "style": {"color": "#8fbee8", "weight": 1.0, "opacity": 0.5},
            })
        if river_bodies:
            # 河流水面（双线河）：长江/汉江等面状水体，独立图层便于"双线河→单线河"比例尺过渡
            layers.append({
                "id": generate_id("layer"), "type": "polygon", "name": "河流水面",
                "coordinates": [r[0] for r in river_bodies],
                "properties": [{"name": r[1], "subtype": "riverbody"} for r in river_bodies],
                "style": {"fillColor": "#3b82c4", "fillOpacity": 0.6,
                          "color": "#1d5fa8", "weight": 1.2, "opacity": 0.9},
            })
        # 多比例尺湖泊图层（多尺度表达：前端按 zoom 切换档位）
        band_styles = {
            "湖泊（概览级）": {"fillColor": "#3f7fc4", "fillOpacity": 0.55,
                              "color": "#1d5fa8", "weight": 1.4, "opacity": 0.9},
            "湖泊（市域级）": {"fillColor": "#4a90d9", "fillOpacity": 0.62,
                              "color": "#2e6fb8", "weight": 1.2, "opacity": 0.9},
            "湖泊（城区级）": {"fillColor": "#6faee3", "fillOpacity": 0.55,
                              "color": "#3d82c4", "weight": 1.0, "opacity": 0.85},
            "湖泊（详图级）": {"fillColor": "#9bc6ec", "fillOpacity": 0.45,
                              "color": "#6fa3d6", "weight": 0.8, "opacity": 0.75},
        }
        for bname, *_ in LAKE_BANDS:
            items = lake_bands[bname]
            if items:
                layers.append({
                    "id": generate_id("layer"), "type": "polygon", "name": bname,
                    "coordinates": [l["coords"] for l in items],
                    "properties": [{"name": l["name"], "subtype": "lake",
                                    "area_km2": round(l["area"], 2)} for l in items],
                    "style": band_styles[bname],
                    "metadata": {"subtype": "lake", "scale_band": bname,
                                 "legend_title": "湖泊", "feature_count": len(items)},
                })
        if lake_pts_overview:
            layers.append({
                "id": generate_id("layer"), "type": "circleMarker", "name": "湖泊点符号（概览）",
                "coordinates": [p["coords"] for p in lake_pts_overview],
                "properties": [{"name": p["name"], "subtype": "lake_point"} for p in lake_pts_overview],
                "style": {"color": "#1d5fa8", "fillColor": "#4a90d9",
                          "fillOpacity": 0.9, "weight": 1.5, "radius": 5},
                "metadata": {"subtype": "lake_point", "legend_title": "湖泊（点状符号）",
                             "feature_count": len(lake_pts_overview)},
            })
        if labels:
            layers.append({
                "id": generate_id("layer"), "type": "textLabel", "name": "水系注记",
                "coordinates": [l["coords"] for l in labels],
                "properties": [{"name": l["name"], "rotation": 0} for l in labels],
                "style": {"color": "#1e3a8a", "fontSize": 12, "weight": 2, "font": "song"},
            })
        # 湖岸线（河湖连通性吸附用）：入湖河口/出湖河源端点吸附到最近湖岸
        try:
            lake_shores = unary_union([
                Polygon([(p[1], p[0]) for p in r[0]]).boundary
                for r in _filtered if r[2] >= 0.2 and len(r[0]) >= 4
            ])
        except Exception:
            lake_shores = None
        # 河流中心线（单线河）：小比例尺下双线河收缩为单线，保证水系连通性表达
        layers.extend(self._compute_riverline_layers(region, lake_shores=lake_shores))
        print(f"[LocalGeo] 使用本地水系数据: {len(big_rivers)}条大江, {len(main_rivers)}条主河, "
              f"{len(minor_rivers)}条支流, 河流水面 {len(river_bodies)}, "
              f"湖泊档位 " + "/".join(f"{name}:{len(lake_bands[name])}"
                                      for name, *_ in LAKE_BANDS) +
              f", 概览点符号 {len(lake_pts_overview)}, "
              f"{len(labels)}个注记")
        return layers

    # ------------------------------------------------------------ 河流中心线（单线河）
    MAJOR_RIVER_NAMES = {
        "长江", "汉江", "府河", "滠水", "举水", "倒水", "金水", "东荆河",
        "通顺河", "沙河", "巡司河", "马影河", "朱家河", "汤逊湖", "北湖闸河",
    }

    def _compute_riverline_layers(self, region: str = "武汉市", lake_shores=None) -> List[dict]:
        """OSM 河流中心线 → 单线河图层（双线河→单线河过渡的数据基础）。

        制图综合：小比例尺仅保留主干/命名河流（长度阈值+密度对比），
        大比例尺逐步加入支流；线形做简化，保持与面状水系的协调。
        """
        data = self._load("wuhan_riverlines.geojson")
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return []
        from shapely.geometry import LineString, Point
        from shapely.prepared import prep
        poly = self._boundary_polygon(region)
        prep_poly = prep(poly) if poly is not None else None

        def _snap_to_shore(pts):
            """把折线两端吸附到最近湖岸点（<=400m），保持河湖连通性。"""
            if lake_shores is None or lake_shores.is_empty or len(pts) < 2:
                return pts
            out = [list(p) for p in pts]
            for k in (0, -1):
                pt = Point(out[k][1], out[k][0])
                d = pt.distance(lake_shores)
                if d <= 0.0036:   # ~400m
                    proj = lake_shores.interpolate(lake_shores.project(pt))
                    out[k] = [proj.y, proj.x]
            return out

        major, minor = [], []

        def _classify(name: str, ln_len: float) -> bool:
            if name in self.MAJOR_RIVER_NAMES:
                return True
            if name and len(name) >= 2:
                return True
            return ln_len > 0.25   # 无名长河（>25km）也按主干保留

        for feat in features:
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            name = (props.get("name") or "").strip()
            if geom.get("type") != "LineString":
                continue
            line = LineString([[c[0], c[1]] for c in geom.get("coordinates", []) if len(c) >= 2])
            if line.is_empty or line.length < 1e-7:
                continue
            segs = [line]
            if prep_poly is not None:
                try:
                    if prep_poly.contains(line):
                        segs = [line]
                    elif prep_poly.intersects(line):
                        inter = poly.intersection(line)
                        if inter.is_empty or inter.geom_type == "Point":
                            continue
                        segs = list(inter.geoms) if inter.geom_type == "MultiLineString" else [inter]
                    else:
                        continue
                except Exception:
                    continue
            for ln in segs:
                if ln.geom_type != "LineString" or len(ln.coords) < 2:
                    continue
                sim = ln.simplify(0.00012, preserve_topology=True)   # ~13m 化简
                if len(sim.coords) < 2:
                    continue
                pts = [[p[1], p[0]] for p in sim.coords]             # [lat, lng]
                if _classify(name, sim.length):
                    major.append({"coords": _snap_to_shore(pts), "name": name})
                else:
                    minor.append({"coords": pts, "name": name})

        layers = []
        if major:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "河流中心线（主要）",
                "coordinates": [r["coords"] for r in major],
                "properties": [{"name": r["name"], "subtype": "riverline"} for r in major],
                "style": {"color": "#2f7fd0", "weight": 1.8, "opacity": 0.85,
                          "dashArray": "6,4"},
            })
        if minor:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "河流中心线（支流）",
                "coordinates": [r["coords"] for r in minor],
                "properties": [{"name": r["name"], "subtype": "riverline"} for r in minor],
                "style": {"color": "#7fb2e3", "weight": 0.9, "opacity": 0.5,
                          "dashArray": "3,4"},
            })
        return layers

    # ------------------------------------------------------------ 居民地街区（制图综合）
    def get_builtup_layers(self, region: str = "武汉市") -> List[dict]:
        return self._cached(("builtup", region), lambda: self._compute_builtup_layers(region))

    def _compute_builtup_layers(self, region: str = "武汉市") -> List[dict]:
        """OSM 居民地街区面 → 分级街区图层（街区形状概括）。

        制图综合操作：
          1) 选取    按面积分档（大/中/小），小比例尺只保留大型集中建成区；
          2) 形状概括 相邻街区(<110m)合并、轮廓 Douglas-Peucker 化简、Chaikin 平滑，
                     保持"中心密、外围疏"的整体形态；
          3) 密度对比 保留区域密度差异，不平均删减。
        """
        data = self._load("wuhan_builtup.geojson")
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return []
        from shapely.geometry import Polygon
        from shapely.prepared import prep
        poly = self._boundary_polygon(region)
        prep_poly = prep(poly) if poly is not None else None

        geoms = []
        for feat in features:
            geom = feat.get("geometry") or {}
            if geom.get("type") != "Polygon":
                continue
            ring = [[c[0], c[1]] for c in geom.get("coordinates", [[]])[0] if len(c) >= 2]
            if len(ring) < 4:
                continue
            g = Polygon(ring)
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty or g.area * 9700 < 0.1:   # 过滤 <0.1km² 碎块
                continue
            if prep_poly is not None:
                try:
                    if not prep_poly.intersects(g):
                        continue
                    inter = poly.intersection(g)
                    if inter.is_empty or inter.geom_type != "Polygon":
                        continue
                    g = inter
                except Exception:
                    continue
            geoms.append(g.simplify(0.00012, preserve_topology=True))
        if not geoms:
            return []

        # 相邻街区合并（间距<110m），消除细碎缝隙；保持街区群分布格局
        try:
            merged = unary_union([g.buffer(0.0005) for g in geoms]).buffer(-0.0005)
        except Exception:
            merged = unary_union(geoms)
        parts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]

        big, mid, small = [], [], []
        for part in parts:
            if part.geom_type != "Polygon" or not part.is_valid or part.is_empty:
                continue
            area = part.area * 9700   # km² 近似
            if area < 0.2:
                continue
            ring = [[pt[1], pt[0]] for pt in part.exterior.coords]
            if len(ring) < 4:
                continue
            ring = self._chaikin_local(ring) if len(ring) <= 60 else ring
            item = {"coords": ring}
            if area >= 5:
                big.append(item)
            elif area >= 1:
                mid.append(item)
            else:
                small.append(item)

        layers = []
        for key, name, style, min_area in (
            ("big", "集中居民地（大型）",
             {"fillColor": "#e8cfa6", "fillOpacity": 0.7, "color": "#c9a15f", "weight": 1.0, "opacity": 0.8}, 5),
            ("mid", "集中居民地（中型）",
             {"fillColor": "#eeddbc", "fillOpacity": 0.6, "color": "#d0b27a", "weight": 0.8, "opacity": 0.7}, 1),
            ("small", "集中居民地（小型）",
             {"fillColor": "#f4e7cf", "fillOpacity": 0.5, "color": "#dcc29a", "weight": 0.6, "opacity": 0.6}, 0.2),
        ):
            items = {"big": big, "mid": mid, "small": small}[key]
            if items:
                layers.append({
                    "id": generate_id("layer"), "type": "polygon", "name": name,
                    "coordinates": [r["coords"] for r in items],
                    "properties": [{"subtype": "builtup"} for _ in items],
                    "style": style,
                    "metadata": {"subtype": "builtup", "min_area_km2": min_area,
                                 "legend_title": "居民地", "feature_count": len(items)},
                })
        print(f"[LocalGeo] 居民地街区: 合并后 {len(big)}大/{len(mid)}中/{len(small)}小 (源 {len(features)} 块)")
        return layers

    @staticmethod
    def _chaikin_local(ring, iterations=1):
        """静态版 Chaikin 平滑（供街区轮廓使用）。"""
        if len(ring) < 4:
            return ring
        pts = [list(p) for p in ring]
        for _ in range(iterations):
            n = len(pts)
            out = []
            for i in range(n):
                p0 = pts[i - 1]
                p1 = pts[i]
                p2 = pts[(i + 1) % n]
                out.append([0.75 * p1[0] + 0.25 * p2[0], 0.75 * p1[1] + 0.25 * p2[1]])
                out.append([0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]])
            pts = out
        return pts

    def _boundary_polygon(self, region: str = "武汉市"):
        """武汉市域边界多边形（shapely Polygon，[lng,lat]），用于路网裁剪

        优先使用 DataV 官方市域面（420000_full 中的武汉市面）；
        DataV 不可用时用本地13区兜底面的凸包近似。
        """
        if self._boundary_cache is not None:
            return self._boundary_cache
        poly = None
        try:
            from shapely.geometry import Polygon
            from app.services.geo_service import GeoService
            gs = GeoService()
            prov = gs._fetch_by_adcode("420000", full=True)
            for f in prov:
                if str((f.get("properties") or {}).get("adcode", "")) == "420100":
                    rings = gs._geom_to_rings(f.get("geometry", {}))
                    if rings:
                        main = max(rings, key=_ring_area_km2)
                        poly = Polygon([[p[1], p[0]] for p in main])
                    break
            if poly is None:
                # 兜底：本地13区兜底面的凸包近似市域边界
                feats = gs._fallback_district_features(region)
                pts = []
                for f in feats:
                    for r in gs._geom_to_rings(f.get("geometry", {})):
                        pts.extend(r)
                if len(pts) >= 4:
                    poly = Polygon([[p[1], p[0]] for p in _convex_hull(pts)])
        except Exception as e:
            print(f"[LocalGeo] 市域边界获取失败: {e}")
        self._boundary_cache = poly
        return poly

    def get_roads_layers(self, region: str = "武汉市") -> List[dict]:
        return self._cached(("roads", region), lambda: self._compute_roads_layers(region))

    def _compute_roads_layers(self, region: str = "武汉市") -> List[dict]:
        """读取本地路网 GeoJSON → 道路分级图层

        道路严格裁剪到武汉市域边界内：边界外的道路（孝感/黄冈/鄂州等）不显示。
        制图规范：
          - 中文命名 + 子分组（高速路网/城市主干道/城区道路），便于图层管理；
          - 图层按"低等级在前、高等级在后"排列，高等级道路渲染在上层；
          - 道路统一不透明度 0.9（与 carto-agent-1 行政区划图完全一致）。
        """
        ROAD_CN = {
            "motorway": "高速公路主线", "motorway_link": "高速互通匝道",
            "trunk": "城市干线主干道", "trunk_link": "主干道连接匝道",
            "primary": "城市主干道", "primary_link": "主干道衔接匝道",
            "secondary": "城市次干道", "secondary_link": "次干道连接匝道",
            "tertiary": "三级道路（次要道路）", "tertiary_link": "三级道路连接线",
            "residential": "居民区街区道路", "living_street": "生活性街道",
            "service": "服务性道路", "unclassified": "未分级道路", "other": "其他道路",
        }
        ROAD_SUBGROUP = {
            "motorway": "高速路网", "motorway_link": "高速路网",
            "trunk": "城市主干道", "trunk_link": "城市主干道",
            "primary": "城市主干道", "primary_link": "城市主干道",
            "secondary": "城区道路", "secondary_link": "城区道路",
            "tertiary": "城区道路", "tertiary_link": "城区道路",
            "residential": "城区道路", "living_street": "城区道路",
            "service": "其他道路", "unclassified": "其他道路", "other": "其他道路",
        }
        # 低等级在前、高等级在后（高等级最后添加 -> 渲染在最上层）
        ROAD_ORDER = [
            "other", "unclassified", "service", "living_street", "residential",
            "tertiary", "tertiary_link", "secondary", "secondary_link",
            "primary_link", "primary", "trunk_link", "trunk", "motorway_link", "motorway",
        ]
        data = self._load("wuhan_roads.geojson")
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return []
        poly = self._boundary_polygon(region)
        by_level = {}
        clipped_total = 0
        if poly is not None:
            from shapely.geometry import LineString
            from shapely.prepared import prep
            prep_poly = prep(poly)
        for feat in features:
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            if geom.get("type") != "LineString":
                continue
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            hw = (props.get("highway") or "other").lower()
            name = (props.get("name") or "").strip()
            line = LineString([[c[0], c[1]] for c in coords if len(c) >= 2])
            if line.length < 1e-7:
                continue
            if poly is not None:
                try:
                    if prep_poly.contains(line):
                        segs = [line]
                    elif prep_poly.intersects(line):
                        inter = poly.intersection(line)
                        if inter.is_empty or inter.geom_type == "Point":
                            continue
                        segs = list(inter.geoms) if inter.geom_type == "MultiLineString" else [inter]
                    else:
                        continue
                except Exception:
                    continue
                for ln in segs:
                    if ln.geom_type != "LineString" or ln.length < 1e-7:
                        continue
                    pts = [[p[1], p[0]] for p in ln.coords]
                    if len(pts) >= 2:
                        by_level.setdefault(hw, []).append({"coords": pts, "name": name})
                        clipped_total += 1
            else:
                # 无市域边界（数据源不可用）：保留全部，避免误删
                pts = [[c[1], c[0]] for c in coords if len(c) >= 2]
                if len(pts) >= 2:
                    by_level.setdefault(hw, []).append({"coords": pts, "name": name})
                    clipped_total += 1
        layers = []
        for hw in ROAD_ORDER:
            items = by_level.get(hw)
            if not items:
                continue
            cn = ROAD_CN.get(hw, hw)
            layers.append({
                "id": generate_id("layer"), "type": "polyline",
                "name": f"道路-{cn}",
                "subgroup": ROAD_SUBGROUP.get(hw, "其他道路"),
                "coordinates": [it["coords"] for it in items],
                "properties": [{"name": it["name"], "subtype": hw} for it in items],
                "style": {"color": ROAD_COLOR.get(hw, "#E0E0E0"),
                          "weight": ROAD_WEIGHT.get(hw, 0.8),
                          "opacity": 0.9},
                "metadata": {"subtype": "road", "raw_class": hw,
                             "group": "道路", "subgroup": ROAD_SUBGROUP.get(hw, "其他道路"),
                             "description": ROAD_CN.get(hw, hw)},
            })
        print(f"[LocalGeo] 使用本地路网数据: {clipped_total}条道路(已裁剪到市域内), {len(layers)}个等级图层")
        return layers

    # ==================== 旅游POI（武汉旅游图） ====================
    TOURISM_ICONS = {
        "attraction": "🏯", "museum": "🏛️", "zoo": "🦁", "theme_park": "🎢",
        "viewpoint": "📷", "park": "🌳", "monument": "🗽", "memorial": "🪦",
        "castle": "🏰", "ruins": "🏚️", "archaeological_site": "⛏️",
        "arts_centre": "🎭", "theatre": "🎭", "cinema": "🎬", "library": "📚",
        "place_of_worship": "⛪", "hotel": "🏨", "hostel": "🏨", "guest_house": "🏠",
        "information": "ℹ️", "picnic_site": "🧺", "artwork": "🖼️",
    }

    def get_tourism_layers(self, region: str = "武汉市") -> List[dict]:
        return self._cached(("tourism", region), lambda: self._compute_tourism_layers(region))

    def _compute_tourism_layers(self, region: str = "武汉市") -> List[dict]:
        """读取本地旅游POI GeoJSON → 旅游景点图层（武汉旅游图）"""
        if region != "武汉市":
            return []
        data = self._load("wuhan_tourism.geojson")
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return []
        # 只保留真正的旅游景点类目，过滤酒店/招待所/信息点等噪音
        KEEP = {
            "attraction", "museum", "zoo", "theme_park", "viewpoint", "artwork",
            "monument", "memorial", "castle", "ruins", "archaeological_site",
            "park", "arts_centre", "theatre", "cinema", "library", "place_of_worship",
        }
        coords, props = [], []
        for feat in features:
            geom = feat.get("geometry") or {}
            if geom.get("type") != "Point":
                continue
            c = geom.get("coordinates") or []
            if len(c) < 2:
                continue
            p = feat.get("properties") or {}
            name = (p.get("name") or "").strip()
            if not name:
                continue
            cat = (p.get("category") or "poi").lower()
            if cat not in KEEP:
                continue
            coords.append([c[1], c[0]])  # [lat, lng]
            props.append({"name": name, "category": cat})
        if not coords:
            return []
        layers = [{
            "id": generate_id("layer"),
            "type": "circleMarker",
            "name": "旅游景点",
            "coordinates": coords,
            "properties": props,
            "style": {"color": "#d97706", "fillColor": "#ffffff", "fillOpacity": 0.95,
                      "weight": 2.2, "radius": 7, "icon": "🏯", "iconClass": "fa-location-dot",
                      "group": "旅游景点", "kind": "poi"},
        }]
        print(f"[LocalGeo] 使用本地旅游POI数据: {len(coords)}个景点")
        return layers

    # ==================== 轨道交通（武汉交通图） ====================
    def get_transit_layers(self, region: str = "武汉市") -> List[dict]:
        return self._cached(("transit", region), lambda: self._compute_transit_layers(region))

    def _compute_transit_layers(self, region: str = "武汉市") -> List[dict]:
        """读取本地轨道交通/铁路 GeoJSON → 线路 + 站点图层（武汉交通图）"""
        if region != "武汉市":
            return []
        data = self._load("wuhan_transit.geojson")
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return []
        line_coords, line_props = [], []
        station_coords, station_props = [], []
        for feat in features:
            geom = feat.get("geometry") or {}
            p = feat.get("properties") or {}
            name = (p.get("name") or "").strip()
            gtype = geom.get("type", "")
            coords = geom.get("coordinates") or []
            if gtype == "LineString" and len(coords) >= 2:
                pts = [[c[1], c[0]] for c in coords if len(c) >= 2]
                if len(pts) >= 2:
                    line_coords.append(pts)
                    line_props.append({"name": name, "subtype": p.get("railway", "rail")})
            elif gtype == "Point" and len(coords) >= 2:
                station_coords.append([coords[1], coords[0]])
                station_props.append({"name": name, "subtype": p.get("railway", "station")})
        layers = []
        if line_coords:
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": "轨道交通线路",
                "coordinates": line_coords,
                "properties": line_props,
                "style": {"color": "#4338ca", "weight": 2.4, "opacity": 0.9,
                          "dashArray": None, "group": "轨道交通"},
            })
        if station_coords:
            layers.append({
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": "轨道交通站点",
                "coordinates": station_coords,
                "properties": station_props,
                "style": {"color": "#4338ca", "fillColor": "#ffffff", "fillOpacity": 0.95,
                          "weight": 1.6, "radius": 4.5, "icon": "🚉", "iconClass": "fa-train-subway",
                          "group": "轨道交通", "kind": "station"},
            })
        print(f"[LocalGeo] 使用本地轨道交通数据: {len(line_coords)}条线路, {len(station_coords)}个站点")
        return layers
