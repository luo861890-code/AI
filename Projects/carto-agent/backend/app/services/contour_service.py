# -*- coding: utf-8 -*-
"""等高线图层服务

读取 tools/generate_contours.py 生成的 wuhan_contours.geojson
（数据源：SRTM 30m DEM，已做舍谷/扩谷/鞍部保持等制图综合），
转换为系统图层：计曲线(每100m加粗) + 首曲线(每20m细线)。
"""
import copy
import json
import os

from app.utils.helpers import generate_id

GEO_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "geo",
)

# 等高线配色：棕褐色系，计曲线深/粗，首曲线浅/细（制图规范：计曲线0.25mm加粗）
STYLE_INDEX = {"color": "#7A5230", "weight": 1.5, "opacity": 0.8}
STYLE_MINOR = {"color": "#C8A268", "weight": 0.7, "opacity": 0.55}


class ContourService:
    """等高线图层（SRTM DEM 生成）"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or GEO_DATA_DIR
        self._cache = None

    def _load_data(self) -> dict:
        path = os.path.join(self.data_dir, "wuhan_contours.geojson")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Contour] 读取 wuhan_contours.geojson 失败: {e}")
            return {}

    def get_contour_layers(self) -> list:
        """返回 [计曲线, 首曲线] 两个 polyline 图层；无数据时返回空列表。"""
        if self._cache is not None:
            return copy.deepcopy(self._cache)
        data = self._load_data()
        if not data.get("features"):
            self._cache = []
            return []

        index_coords, index_props = [], []
        minor_coords, minor_props = [], []
        for f in data["features"]:
            geom = f.get("geometry") or {}
            if geom.get("type") != "LineString":
                continue
            # GeoJSON [lng, lat] -> 系统图层 [lat, lng]
            coords = [[round(p[1], 6), round(p[0], 6)] for p in geom.get("coordinates", [])]
            if len(coords) < 2:
                continue
            prop = {
                "ele": f.get("properties", {}).get("ele"),
                "index": bool(f.get("properties", {}).get("index")),
                "subtype": "contour",
            }
            if prop["index"]:
                index_coords.append(coords)
                index_props.append(prop)
            else:
                minor_coords.append(coords)
                minor_props.append(prop)

        layers = []
        if index_coords:
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": "等高线（计曲线）",
                "coordinates": index_coords,
                "properties": index_props,
                "style": dict(STYLE_INDEX),
                "metadata": {
                    "subtype": "contour",
                    "description": "计曲线（加粗，间隔100m）",
                    "legend_title": "等高线",
                    "feature_count": len(index_coords),
                },
            })
        if minor_coords:
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": "等高线（首曲线）",
                "coordinates": minor_coords,
                "properties": minor_props,
                "style": dict(STYLE_MINOR),
                "metadata": {
                    "subtype": "contour",
                    "description": "首曲线（细线，间隔20m）",
                    "legend_title": "等高线",
                    "feature_count": len(minor_coords),
                },
            })
        self._cache = layers
        return copy.deepcopy(layers)
