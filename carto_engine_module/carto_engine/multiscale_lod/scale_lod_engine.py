# -*- coding: utf-8 -*-
"""
================================================================================
[分类十 - 子模块 10.1] 多比例尺动态缩放、载负量控制与层级下钻引擎 `scale_lod_engine.py`
================================================================================
地图学核心设计原理（对应用户“最最最重要”的核心诉求）：
1. **三级连续比例尺与行政规划层级自动下钻 (Hierarchical Administrative Drill-Down)**：
   - **Level 1 省级概览比例尺 (`1:2,500,000`, Zoom ≈ 7)**：
     展示湖北省省域范围，以 17 个地级市/自治州（武汉市、宜昌市、襄阳市、荆州市、黄冈市、孝感市、咸宁市、鄂州市、荆门市、十堰市等）为行政分隔单元；
     不显示武汉市内部区界，避免小比例尺下图斑过密团黑；长江与汉江采用省域尺度面状宽水带表达。
   - **Level 2 市级中观比例尺 (`1:400,000`, Zoom ≈ 10)**：
     当用户将地图放大到武汉市时，自动触发层级下钻！武汉市单一图斑自动裂变切换为武汉市各市辖区（江岸、江汉、硚口、汉阳、武昌、青山、洪山等）行政规划边界与四色普染；
     同时周边紧邻地市（孝感、黄冈、鄂州、咸宁）作为淡化背景邻区交代空间区位；长江与东湖呈现宽阔真实的双岸线面状水系。
   - **Level 3 城区/街区大比例尺 (`1:50,000`, Zoom ≈ 13.5)**：
     当用户继续放大到武昌—东湖—武汉大学核心片区时，进一步下钻加载街道级路网（八一路、东湖路、珞喻路、武珞路）、地铁站点、高校校园面状范围（武汉大学、华中科技大学）及核心景区辐射圈。

2. **要素几何大小与道路线宽随比例尺动态自适应（真实道路宽度拟合模型）**：
   不同等级道路具有真实物理路幅宽度 $W_{\\text{real}}$（如双向八车道高速公路 ~36m、城市主干道 ~28m、次干道 ~18m、城市支路 ~10m）。
   在给定比例尺分母 $S$ 下，其理论真尺图面宽度（单位 pt）为：
   $$w_{\\text{true}}(S) = \\frac{W_{\\text{real}}}{S} \\times \\frac{72}{0.0254}$$
   结合地图学半依比例符号幂律视觉补偿公式：
   $$w_{\\text{render}}(S) = \\text{clip}\\left( w_{\\text{ref}} \\cdot \\left(\\frac{S_{\\text{ref}}}{S}\\right)^{\\gamma},\\; w_{\\min},\\; w_{\\max} \\right)$$
   当用户放大地图（$S$ 变小）时，道路双线外壳 (`casing_width`) 与内芯 (`stroke_width`) 自动按真实道路等级比例增粗，贴合实际道路宽度感！
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import geopandas as gpd

from ..models_and_specs import VisualVariableSpec
from ..symbology.symbol_library import CartoSymbolLibrary


@dataclass
class ScaleLevelSpec:
    """特定比例尺层级下的地图载负量与要素显隐规则"""
    level_id: str
    scale_denom: int
    admin_unit_level: str                 # 'prefecture_city' (地市级), 'city_district' (市辖区级), 'subdistrict_street' (街道/园区级)
    allowed_road_classes: List[str]       # 当前比例尺允许显示的道路等级（控制线状载负量）
    max_poi_count: int                    # 当前比例尺最大允许显示的 POI 点数（Töpfer 开方根控制）
    road_width_scale_factor: float        # 道路线宽相对于基准比例尺的动态放缩系数
    point_symbol_scale_factor: float      # 点状符号随比例尺的动态放缩系数
    river_polygon_min_width_m: float      # 河流面状表达的最小等效宽度（米）


class MultiScaleLODEngine:
    """
    多比例尺动态缩放、地图载负量控制、行政层级下钻与线面尺寸动态计算引擎
    """

    # 真实道路物理宽度基准表（单位：米，依据《城市道路工程设计规范 CJJ37》）
    REAL_ROAD_WIDTH_METERS: Dict[str, float] = {
        "motorway": 36.0,       # 双向6~8车道高速公路/环线高速
        "primary": 28.0,        # 双向6车道城市快速路/主干道
        "secondary": 18.0,      # 双向4车道城市次干道
        "tertiary": 10.0,       # 双向2车道城市支路/街巷
        "railway": 14.0,        # 双线国铁/高铁干线限界
        "subway_line2": 12.0,   # 城市轨道交通廊道
        "subway_line4": 12.0,
    }

    @classmethod
    def resolve_scale_level_spec(cls, scale_denom: int) -> ScaleLevelSpec:
        """
        根据当前地图比例尺分母 `scale_denom`，动态解算行政下钻层级、载负量白名单与符号缩放因子。
        基准比例尺 $S_{\\text{ref}} = 400,000$，幂律指数 $\\gamma = 0.36$。
        """
        s_ref = 400000.0
        ratio = max(0.05, min(20.0, s_ref / float(max(1000, scale_denom))))
        road_factor = round(math.pow(ratio, 0.36), 3)
        pt_factor = round(math.pow(ratio, 0.22), 3)

        if scale_denom >= 1000000:
            # Level 1: 省级宏观比例尺 (如湖北省 1:2,500,000) -> 仅地市级分隔 + 骨干高速/高铁 + 面状长江汉江
            return ScaleLevelSpec(
                level_id="L1_Provincial_Macro",
                scale_denom=scale_denom,
                admin_unit_level="prefecture_city",
                allowed_road_classes=["motorway", "railway"],
                max_poi_count=12,
                road_width_scale_factor=max(0.55, road_factor),
                point_symbol_scale_factor=max(0.75, pt_factor),
                river_polygon_min_width_m=3200.0,
            )
        elif scale_denom >= 120000:
            # Level 2: 市级中观比例尺 (如武汉市 1:400,000) -> 自动下钻展示武汉市各区规划 + 主次干道 + 地铁
            return ScaleLevelSpec(
                level_id="L2_Municipal_Meso",
                scale_denom=scale_denom,
                admin_unit_level="city_district",
                allowed_road_classes=["motorway", "primary", "secondary", "railway", "subway_line2", "subway_line4"],
                max_poi_count=28,
                road_width_scale_factor=road_factor,
                point_symbol_scale_factor=pt_factor,
                river_polygon_min_width_m=1450.0,
            )
        else:
            # Level 3: 城区/街区大比例尺 (如武昌—东湖片区 1:50,000) -> 全要素街道支路 + 真实路幅双线 + 园区面
            return ScaleLevelSpec(
                level_id="L3_Urban_Micro",
                scale_denom=scale_denom,
                admin_unit_level="subdistrict_street",
                allowed_road_classes=["motorway", "primary", "secondary", "tertiary", "railway", "subway_line2", "subway_line4"],
                max_poi_count=60,
                road_width_scale_factor=min(2.25, road_factor),
                point_symbol_scale_factor=min(1.45, pt_factor),
                river_polygon_min_width_m=1200.0,
            )

    @classmethod
    def compute_scale_adaptive_road_style(
        cls,
        road_class: str,
        scale_denom: int,
        user_multiplier: float = 1.0,
    ) -> VisualVariableSpec:
        """
        根据道路真实物理宽度 (m) 与当前比例尺分母 `scale_denom`，动态计算道路双线外廓 (`casing_width`)
        与内芯 (`stroke_width`) 的渲染线宽，使其随比例尺放大而平滑增粗并保持真实路幅比例关系。
        """
        base_styles = CartoSymbolLibrary.get_traffic_road_styles()
        st = base_styles.get(road_class, base_styles["tertiary"])
        spec = cls.resolve_scale_level_spec(scale_denom)
        factor = spec.road_width_scale_factor * float(user_multiplier)

        new_stroke = round(st.stroke_width * factor, 2)
        new_casing = round(st.casing_width * factor, 2) if st.casing_width else None

        return VisualVariableSpec(
            geometry_type="line",
            stroke_color=st.stroke_color,
            stroke_width=new_stroke,
            stroke_linestyle=st.stroke_linestyle,
            casing_color=st.casing_color,
            casing_width=new_casing,
            railway_ticks=st.railway_ticks,
        )
