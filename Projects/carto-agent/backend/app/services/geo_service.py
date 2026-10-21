# -*- coding: utf-8 -*-
"""标准行政区划地理数据服务 - 基于DataV GeoAtlas公开区划数据

提供省/市/县面状行政区划边界（GeoJSON），用于生成标准行政区划图的
面状底图、区县名称注记与行政中心符号。数据无需API Key。
"""
import json
import os
from typing import Dict, List

from app.core.constants import (
    CITY_ADCODES,
    DISTRICT_FILL_COLORS,
    LABEL_STYLES,
    WUHAN_DISTRICT_FILLS,
    WUHAN_DISTRICT_FALLBACK,
    WUHAN_DISTRICTS,
    BOUNDARY_STANDARD_STYLES,
    ADMIN_CENTER_STYLES,
    SURROUNDING_CITY_FILL,
    WUHAN_MAIN_BOUNDARY,
)
from app.utils.helpers import generate_id
from app.utils.geometry import (
    _convex_hull,
    _interior_point,
    _point_in_ring,
    _ring_area_km2,
)

# 本地精确区划数据（backend/data/geo/，prepare_local_data.py 生成）
GEO_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "geo",
)
LOCAL_ADCODE_FILES = {
    "420000": "hubei_province.geojson",        # 湖北省省界（外轮廓，DataV 抓取）
    "420000_full": "hubei_cities.geojson",   # 湖北省市级边界
    "420100_full": "wuhan_districts.geojson",  # 武汉市辖区面
}
# 地名纠错：数据源/OSM 可能出现的行政区名错字（按官方标准地名规范修正）
DISTRICT_NAME_FIX = {
    "斫口区": "硚口区",
}
# 小于该面积(km²)的环视为数据碎块噪音（4-5点的细碎飞地），不纳入边界；
# 大于等于该面积的真实部件（主面/岛屿/飞地）全部保留，保证边界划分完整精确
MIN_RING_AREA_KM2 = 0.1


def _significant_rings(rings: list) -> list:
    """按面积过滤碎块，保留全部真实部件（主面/岛屿/飞地）"""
    return [r for r in rings if _ring_area_km2(r) >= MIN_RING_AREA_KM2]


class GeoService:
    """行政区划面数据服务"""

    BASE_URL = "https://geo.datav.aliyun.com/areas_v3/bound"

    def __init__(self):
        self._cache: Dict[str, list] = {}

    def fetch_district_features(self, region: str) -> list:
        """获取区域下辖区县面要素（GeoJSON Feature列表）"""
        adcode = CITY_ADCODES.get(region)
        if not adcode:
            print(f"[GeoService] 未知行政区划代码: {region}")
            return []
        if region in self._cache:
            return self._cache[region]
        features = self._fetch_by_adcode(adcode, full=True)
        if features:
            self._cache[region] = features
            print(f"[GeoService] 获取{region}区划面: {len(features)}个区县")
        return features

    def _fallback_district_features(self, region: str) -> list:
        """本地兜底13区简化面（GeoJSON Feature列表，椭圆近似）

        DataV geo.datav.aliyun.com 抓取失败（网络/证书）时保证行政区划图
        仍有四色区面、面内注记、区县界线与行政中心。
        """
        if region != "武汉市":
            return []
        import math
        feats = []
        for d in WUHAN_DISTRICT_FALLBACK:
            pts = []
            n = 28
            for i in range(n):
                t = 2 * math.pi * i / n
                pts.append([d["lng"] + d["rx"] * math.cos(t), d["lat"] + d["ry"] * math.sin(t)])
            pts.append(pts[0])
            feats.append({
                "type": "Feature",
                "properties": {"name": d["name"], "adcode": 420100},
                "geometry": {"type": "Polygon", "coordinates": [pts]},
            })
        print(f"[GeoService] 使用本地兜底区划面: {len(feats)}个区县")
        return feats

    def _fetch_by_adcode(self, adcode: str, full: bool = False) -> list:
        """按行政区划代码抓取 GeoJSON Feature 列表（带缓存）"""
        key = adcode + ("_full" if full else "")
        if key in self._cache:
            return self._cache[key]
        # 本地精确数据优先（prepare_local_data.py 生成）
        local = self._load_local(key)
        if not local and not full:
            # 非 full 调用也复用 full 的本地文件（如 420000 -> 420000_full）
            local = self._load_local(key + "_full")
        if local:
            self._cache[key] = local
            print(f"[GeoService] 使用本地区划数据: {LOCAL_ADCODE_FILES.get(key) or LOCAL_ADCODE_FILES.get(key + '_full')}")
            return local
        # 在线 DataV GeoAtlas
        url = f"{self.BASE_URL}/{key}.json"
        try:
            import requests
            sess = requests.Session()
            sess.trust_env = False   # 绕过本机失效代理，直连 DataV（避免 30s 挂起）
            resp = sess.get(
                url, timeout=8,
                headers={"User-Agent": "CartoAgent/1.0 (Map Cartography Agent)"},
            )
            resp.raise_for_status()
            features = resp.json().get("features", [])
            self._cache[key] = features
            return features
        except Exception as e:
            print(f"[GeoService] 区划数据获取失败 {key}: {e}")
            return []

    def _load_local(self, key: str) -> list:
        """读取本地 GeoJSON 区划面要素（无文件/解析失败返回空）"""
        fname = LOCAL_ADCODE_FILES.get(key)
        if not fname:
            return []
        path = os.path.join(GEO_DATA_DIR, fname)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("features", []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[GeoService] 本地区划数据读取失败 {fname}: {e}")
            return []

    def build_surrounding_layers(self, region: str) -> list:
        """构建周边地市底图与标准境界线图层（规范一/二-3）

        返回图层顺序：周边地市面(极浅米黄) → 省界(黑色细点线) → 地级市界(紫色粗实线)。
        区县界线由 build_district_layers 一并生成。
        """
        layers = []
        wuhan_adcode = CITY_ADCODES.get(region, "420100")
        prov_cities = self._fetch_by_adcode("420000", full=True)
        # 0) 区域底色区分：湖北省域浅米色底 + 武汉市域白色底（突出主体，外部留白）
        wuhan_face0 = [f for f in prov_cities
                       if str((f.get("properties") or {}).get("adcode", "")) == str(wuhan_adcode)]
        prov_face0 = self._fetch_by_adcode("420000", full=False)
        for feat in prov_face0:
            rings = self._geom_to_rings(feat.get("geometry", {}))
            if rings:
                main_ring = max(rings, key=_ring_area_km2)
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polygon",
                    "name": "湖北省域",
                    "coordinates": [main_ring],
                    "properties": [{"name": "湖北省域", "subtype": "province"}],
                    "style": {"fillColor": "#FBF7EF", "fillOpacity": 0.35,
                              "color": "#C9D4E0", "weight": 0.8, "opacity": 0.7},
                })
                break
        for feat in wuhan_face0:
            rings = self._geom_to_rings(feat.get("geometry", {}))
            if rings:
                sig_rings = _significant_rings(rings)
                if not sig_rings:
                    sig_rings = [max(rings, key=_ring_area_km2)]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polygon",
                    "name": "武汉市域底图",
                    "coordinates": sig_rings,
                    "properties": [{"name": "武汉市域底图", "subtype": "city"} for _ in sig_rings],
                    "style": {"fillColor": "#FFFFFF", "fillOpacity": 0.7,
                              "color": "#FFD6D6", "weight": 1, "opacity": 0.85},
                })
                break
        # 1) 周边地市面：湖北省地市面中剔除武汉，极浅米黄底图（突出武汉主体）
        surr_rings = []
        for feat in prov_cities:
            props = feat.get("properties", {})
            if str(props.get("adcode", "")) == str(wuhan_adcode):
                continue
            rings = self._geom_to_rings(feat.get("geometry", {}))
            if rings:
                sig_rings = _significant_rings(rings)
                if not sig_rings:
                    sig_rings = [max(rings, key=_ring_area_km2)]
                surr_rings.extend(sig_rings)
        if surr_rings:
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": "周边地市",
                "coordinates": surr_rings,
                # 湖北省周边地市（上一级行政模块）：米黄色面 + 浅色轮廓与武汉市白色主体区分
                "style": {"fillColor": SURROUNDING_CITY_FILL, "fillOpacity": 0.5,
                          "color": "#E3D5C0", "weight": 0.8, "opacity": 0.7},
            })
            # 湖北省市级边界线（上一级行政边界）：棕色实线，与武汉市红色市域界区分
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": "湖北周边城市边界",
                "coordinates": surr_rings,
                "properties": [{"name": "湖北省周边城市边界", "subtype": "boundary", "admin_level": 6} for _ in surr_rings],
                "style": {"color": "#B08968", "weight": 1.4, "opacity": 0.9},
            })
        # 1.5) 武汉市域主边界：红色粗实线 #FF0000 4px（GIS叠加风格，视觉突出主边界）
        wuhan_face = [f for f in prov_cities
                      if str((f.get("properties") or {}).get("adcode", "")) == str(wuhan_adcode)]
        if not wuhan_face:
            wuhan_face = self._fetch_by_adcode(wuhan_adcode, full=False)
        if not wuhan_face:
            # DataV不可用：用本地兜底13区面的凸包近似武汉市域边界（红色粗实线）
            fb = self._fallback_district_features(region)
            all_pts = []
            for f in fb:
                for r in self._geom_to_rings(f.get("geometry", {})):
                    all_pts.extend(r)
            if len(all_pts) >= 4:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "武汉市域边界",
                    "coordinates": [_convex_hull(all_pts)],
                    "properties": [{"name": "武汉市域边界", "subtype": "boundary"}],
                    "style": {"color": WUHAN_MAIN_BOUNDARY["color"],
                              "weight": WUHAN_MAIN_BOUNDARY["weight"],
                              "opacity": WUHAN_MAIN_BOUNDARY["opacity"]},
                })
        for feat in wuhan_face:
            rings = self._geom_to_rings(feat.get("geometry", {}))
            if rings:
                sig_rings = _significant_rings(rings)
                if not sig_rings:
                    sig_rings = [max(rings, key=_ring_area_km2)]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "武汉市域边界",
                    "coordinates": sig_rings,
                    "properties": [{"name": "武汉市域边界", "subtype": "boundary"} for _ in sig_rings],
                    "style": {"color": WUHAN_MAIN_BOUNDARY["color"],
                              "weight": WUHAN_MAIN_BOUNDARY["weight"],
                              "opacity": WUHAN_MAIN_BOUNDARY["opacity"]},
                })
                break
        # 2) 省界（周边外省）：湖北省轮廓外环，黑色细点线 0.25mm
        prov_face = self._fetch_by_adcode("420000", full=False)
        for feat in prov_face:
            rings = self._geom_to_rings(feat.get("geometry", {}))
            if rings:
                main_ring = max(rings, key=_ring_area_km2)
                cfg = BOUNDARY_STANDARD_STYLES["province"]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"],
                    "coordinates": [main_ring],
                    "style": {"color": cfg["color"], "weight": cfg["weight"],
                              "opacity": cfg["opacity"], "dashArray": cfg["dashArray"]},
                })
                break
        return layers

    def _geom_to_rings(self, geom: dict) -> list:
        """GeoJSON几何转 [lat,lng] 环列表（取各Polygon外环）"""
        gtype = geom.get("type", "")
        coords = geom.get("coordinates", [])
        polys = coords if gtype == "MultiPolygon" else ([coords] if gtype == "Polygon" else [])
        rings = []
        for poly in polys:
            if poly and isinstance(poly[0], list) and len(poly[0]) >= 3:
                ring = [[pt[1], pt[0]] for pt in poly[0] if len(pt) >= 2]
                if len(ring) >= 3:
                    rings.append(ring)
        return rings

    @staticmethod
    def _centroid(ring: list) -> list:
        n = len(ring)
        if n == 0:
            return [0.0, 0.0]
        return [sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n]

    def build_district_layers(self, region: str) -> list:
        """生成区县政区面 + 名称注记 + 行政中心 + 区县界线 图层

        标准政区图（规范二/三/四）：
        - 区县面：按区名四色普染色（低饱和柔和浅色，相邻区不重复），面本身不描边；
        - 区县界线：黑色点划线（· — · —）0.3mm，从区县面轮廓生成；
        - 行政中心：区县级红色实心圆●，市级红色五角星★（由map_service补充）；
        - 注记：区名宋体黑色，置于面几何内部，按面积分级字号。
        """
        features = self.fetch_district_features(region)
        if not features:
            # DataV区划面不可用：使用本地13区兜底简化面，保证四色政区图仍可出图
            features = self._fallback_district_features(region)
        if not features:
            return []

        polygons = []
        labels = []
        centers = []
        boundary_rings = []
        for idx, feat in enumerate(features):
            props = feat.get("properties", {})
            name = props.get("name", "")
            name = DISTRICT_NAME_FIX.get(name, name)
            rings = self._geom_to_rings(feat.get("geometry", {}))
            if not rings:
                continue
            # 保留全部真实部件（主面/岛屿/飞地），仅剔除碎块噪音，使区县边界划分完整精确
            sig_rings = _significant_rings(rings)
            if not sig_rings:
                sig_rings = [max(rings, key=_ring_area_km2)]
            # 主面（面积最大）用于注记与中心点计算
            main_ring = max(sig_rings, key=_ring_area_km2)
            boundary_rings.extend(sig_rings)
            # 四色普染色：按区名指定，未匹配时回退柔和色板
            fill = WUHAN_DISTRICT_FILLS.get(name, DISTRICT_FILL_COLORS[idx % len(DISTRICT_FILL_COLORS)])
            for _ring in sig_rings:
                polygons.append({
                    "type": "polygon",
                    "coordinates": _ring,
                    "properties": {"name": name, "adcode": props.get("adcode")},
                    "style": {"fillColor": fill, "fillOpacity": 0.2, "weight": 0},
                })
            # 面内注记点（强制在多边形内部，主面上计算）
            c = _interior_point(main_ring)
            area = _ring_area_km2(main_ring)
            # 区政府驻地/区中心红点：优先用本地区中心坐标（须在面内，避免飘出），否则面内点
            center_pt = c
            for _d in WUHAN_DISTRICTS:
                if _d.get("name") == name:
                    _cand = [_d["lat"], _d["lng"]]
                    if _point_in_ring(_cand, main_ring):
                        center_pt = _cand
                    break
            # 字号分级：远城区面积大字号大；中心城区（面积小、密集）字号调小防重叠
            if area >= 1500:
                font_size = 15
            elif area >= 900:
                font_size = 14
            elif area >= 500:
                font_size = 13
            elif area >= 250:
                font_size = 12
            else:
                font_size = 10
            # 区名标注放在区中心点（区政府驻地）附近：避免大区多边形内点远离驻地、
            # 文字飘出辖区的问题；在面内沿驻地方向微移，防止文字压盖红点
            label_pt = center_pt
            for _dl, _dn in ((0.006, 0), (-0.006, 0), (0, 0.006), (0, -0.006),
                             (0.004, 0.004), (-0.004, -0.004), (0.004, -0.004), (-0.004, 0.004)):
                _cand2 = [center_pt[0] + _dl, center_pt[1] + _dn]
                if _point_in_ring(_cand2, main_ring):
                    label_pt = _cand2
                    break
            labels.append({"coords": label_pt, "name": name, "fontSize": font_size})
            centers.append({"coords": center_pt, "name": name})

        layers = []
        if polygons:
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": "区县政区",
                "features": polygons,
                # fillColor 仅作图例代表色（四色普染面），实际各面颜色在 features 内
                "style": {"fillColor": "#D8ECCE", "fillOpacity": 0.2},
            })
        # 区县界线：黑色点划线，从区县面轮廓生成（规范一-1-2）
        if boundary_rings:
            cfg = BOUNDARY_STANDARD_STYLES["county"]
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": cfg["name"],
                "coordinates": boundary_rings,
                "properties": [{"name": "区县界", "subtype": "boundary"} for _ in boundary_rings],
                "style": {"color": cfg["color"], "weight": cfg["weight"],
                          "opacity": cfg["opacity"], "dashArray": cfg["dashArray"]},
            })
        if labels:
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": "区县名称标注",
                "coordinates": [lbl["coords"] for lbl in labels],
                "properties": [{"name": lbl["name"], "fontSize": lbl.get("fontSize")} for lbl in labels],
                "style": {"color": LABEL_STYLES["district"]["color"],
                          "fontSize": LABEL_STYLES["district"]["fontSize"],
                          "weight": LABEL_STYLES["district"]["weight"],
                          "font": LABEL_STYLES["district"]["font"],
                          "center": True},
            })
        if centers:
            cfg = ADMIN_CENTER_STYLES["district"]
            layers.append({
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": cfg["name"],
                "coordinates": [c["coords"] for c in centers],
                "properties": [{"name": c["name"]} for c in centers],
                "style": {"color": cfg["color"], "fillColor": cfg["fillColor"],
                          "fillOpacity": cfg["fillOpacity"], "weight": cfg["weight"],
                          "radius": cfg["radius"]},
            })
        return layers
