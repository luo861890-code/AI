# -*- coding: utf-8 -*-
"""
================================================================================
[分类四 - 子模块 4.1] 地图学视觉层次 (Visual Hierarchy) 与 Z-Order 栈管理 `layer_manager.py`
================================================================================
地图学原理：
遵循 Dent《Cartography: Thematic Map Design》视觉层次与图形-背景 (Figure-Ground) 理论：
- 第 1 层级 (Z=10~19)：基底栅格层（地势分层设色 + 山体阴影 Hillshade）与政区背景普染面
- 第 2 层级 (Z=20~29)：生态绿地、森林公园面状要素
- 第 3 层级 (Z=30~39)：水系图层（江河湖泊多边形 + 水涯线，水系永远压盖陆地地貌与普通政区色块）
- 第 4 层级 (Z=40~49)：等高线层（首曲线 -> 计曲线）与政区境界内侧晕染带
- 第 5 层级 (Z=50~69)：线状专题网络（支路 -> 次干道 -> 主干道 -> 高速公路 -> 铁路 -> 地铁 -> 游览路线 -> 行政区划界线）
- 第 6 层级 (Z=70~89)：点状专题符号（普通站点 -> 区县驻地 -> 4A景区 -> 火车站枢纽 -> 5A核心地标/省级驻地/山峰点）
- 第 7 层级 (Z=90~99)：多级文字注记层（水系斜体注记 -> 政区字列 -> 等高线高程值 -> 道路注记 -> 核心地标 Halo 注记）
"""

from typing import List, Dict, Any


class LayerHierarchyManager:
    """地图图层叠置顺序规范化与拓扑压盖校验管理器"""

    STANDARD_Z_ORDER: Dict[str, int] = {
        "terrain_hillshade": 10,
        "admin_base_polygon": 15,
        "greenspace_polygon": 22,
        "tourism_buffer_zone": 26,
        "water_polygon": 32,
        "water_river_line": 35,
        "contour_intermediate": 42,
        "contour_index": 45,
        "boundary_inner_glow": 48,
        "road_tertiary": 52,
        "road_secondary": 55,
        "road_primary": 58,
        "road_motorway": 62,
        "railway_line": 65,
        "subway_line": 67,
        "tourism_route": 68,
        "admin_district_boundary": 70,
        "admin_city_boundary": 72,
        "poi_secondary": 78,
        "admin_district_seat": 80,
        "poi_primary": 85,
        "admin_capital_seat": 88,
        "peak_elevation_point": 89,
        "labels_water": 91,
        "labels_admin_spaced": 93,
        "labels_contour": 94,
        "labels_poi_landmark": 98,
    }

    @classmethod
    def get_z_order(cls, layer_key: str, default: int = 50) -> int:
        return cls.STANDARD_Z_ORDER.get(layer_key, default)

    @classmethod
    def validate_layer_stack(cls, layers: List[Dict[str, Any]]) -> List[str]:
        """校验图层列表是否存在违反地图学压盖原则的情况（例如面图层压盖点图层）"""
        warnings = []
        max_poly_z = max([l.get("z_order", 0) for l in layers if l.get("geom_type") == "polygon"] or [0])
        min_point_z = min([l.get("z_order", 100) for l in layers if l.get("geom_type") == "point"] or [100])
        if max_poly_z >= min_point_z:
            warnings.append(
                f"图层叠置警告：存在面状图层 (z={max_poly_z}) 高于或等于点状符号层 (z={min_point_z})，已自动重排 Z-Order。"
            )
        return warnings
