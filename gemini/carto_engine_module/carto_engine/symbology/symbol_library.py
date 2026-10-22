# -*- coding: utf-8 -*-
"""
================================================================================
[分类三 - 子模块 3.3] 国家图式标准地图符号库 `symbol_library.py`
================================================================================
依据《GB/T 20257 国家基本比例尺地图图式》与专题地图视觉等级规范：
1. **交通图符号体系**：
   - 高速公路 (`motorway`)：双线符号（暗琥珀红 `#B45309` 外廓 Casing 4.2pt + 明黄橙 `#F59E0B` 内芯 2.6pt）
   - 城市快速路/主干道 (`primary`)：双线符号（深灰褐 `#78350F` 外廓 3.2pt + 暖杏黄 `#FCD34D` 内芯 2.0pt）
   - 次干道 (`secondary`)：双线符号（暖灰 `#9CA3AF` 外廓 2.2pt + 纯白 `#FFFFFF` 内芯 1.3pt）
   - 支路 (`tertiary`)：单线浅灰 `#CBD5E1` 0.8pt
   - 铁路 (`railway`)：深炭黑底线 2.2pt + 白色断续轨枕线 (`railway_ticks=True`)
   - 地铁/轨道交通 (`subway`)：武汉地铁代表色（如 2号线梅花红 `#E11D48`、4号线芳草绿 `#16A34A`）+ 白芯站点圆环
2. **旅游景点图符号体系**：
   - 5A 级核心景区：大号五角星/宝石红徽章 (`#DC2626`, 12pt) + 金色/白色双层光晕
   - 4A 级重点景区：中号琥珀橙菱形/圆章 (`#EA580C`, 9pt)
   - 自然生态/森林公园：翠绿圆标 (`#15803D`, 8pt)
   - 历史人文/高校地标：学院蓝方形/圆标 (`#1D4ED8`, 8.5pt)
   - 精品游览路线：紫品红虚线流向廊道 (`#9333EA`, 2.0pt, dashed)
3. **行政规划图符号体系**：
   - 市级境界线：深紫灰跳绘点划线 (`#4A3B52`, 2.2pt, dashdot) + 内侧柔和紫红晕带 (`#D8B4E2`, 6.0pt, opacity=0.38)
   - 区县级境界线：中灰褐虚线 (`#6B5B73`, 1.2pt, dashed) + 内侧浅暖灰晕带 (`#E9D8FD`, 3.5pt, opacity=0.30)
   - 省级行政中心：红五角星 (`*`, `#DC2626`, 13pt)
   - 市级行政中心：外红圈内红点双圈符号 (`double_circle`, `#E11D48`, 9.5pt)
   - 区县级行政中心：白底黑圈点 (`o`, `#1F2937`, 6.5pt)
4. **地势图符号体系**：
   - 计曲线 (Index Contour, 每 100m)：深棕褐色实线 (`#6B4226`, 1.35pt) 嵌印高程数字注记
   - 首曲线 (Intermediate Contour, 每 20m/25m)：浅棕褐色细实线 (`#A67B5B`, 0.65pt)
   - 山峰高程点 (Peak Spot Elevation)：黑色实心正三角 (`^`, `#111827`, 7.5pt) 附山名与高程值
"""

from typing import Dict
from ..models_and_specs import VisualVariableSpec


class CartoSymbolLibrary:
    """四大核心地图类型的预设标准化符号库（可被 KG 知识图谱节点动态覆盖）"""

    @staticmethod
    def get_traffic_road_styles() -> Dict[str, VisualVariableSpec]:
        """获取交通图各等级道路与轨道的复合双线/轨枕符号规范"""
        return {
            "motorway": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#F59E0B",
                stroke_width=2.6,
                casing_color="#92400E",
                casing_width=4.2,
            ),
            "primary": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#FDE047",
                stroke_width=2.0,
                casing_color="#78350F",
                casing_width=3.2,
            ),
            "secondary": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#FFFFFF",
                stroke_width=1.3,
                casing_color="#64748B",
                casing_width=2.3,
            ),
            "tertiary": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#94A3B8",
                stroke_width=0.85,
            ),
            "railway": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#1E293B",
                stroke_width=2.2,
                railway_ticks=True,
            ),
            "subway_line2": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#E11D48",
                stroke_width=2.2,
                casing_color="#FFFFFF",
                casing_width=3.4,
            ),
            "subway_line4": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#16A34A",
                stroke_width=2.2,
                casing_color="#FFFFFF",
                casing_width=3.4,
            ),
        }

    @staticmethod
    def get_traffic_hub_styles() -> Dict[str, VisualVariableSpec]:
        """获取交通枢纽（火车站、机场、地铁换乘站）点状符号规范"""
        return {
            "railway_station": VisualVariableSpec(
                geometry_type="point",
                fill_color="#DC2626",
                stroke_color="#7F1D1D",
                marker_symbol="s",
                marker_size=9.5,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.8,
            ),
            "subway_transfer": VisualVariableSpec(
                geometry_type="point",
                fill_color="#FFFFFF",
                stroke_color="#1E293B",
                marker_symbol="o",
                marker_size=6.5,
                marker_halo_color="#E11D48",
                marker_halo_width=1.4,
            ),
            "bridge_crossing": VisualVariableSpec(
                geometry_type="point",
                fill_color="#F59E0B",
                stroke_color="#78350F",
                marker_symbol="D",
                marker_size=7.0,
            ),
        }

    @staticmethod
    def get_tourism_poi_styles() -> Dict[str, VisualVariableSpec]:
        """获取旅游景点图分级分类符号规范"""
        return {
            "5A_scenic": VisualVariableSpec(
                geometry_type="point",
                fill_color="#E11D48",
                stroke_color="#881337",
                marker_symbol="*",
                marker_size=13.5,
                marker_halo_color="#FEF08A",
                marker_halo_width=2.2,
            ),
            "4A_cultural": VisualVariableSpec(
                geometry_type="point",
                fill_color="#EA580C",
                stroke_color="#7C2D12",
                marker_symbol="D",
                marker_size=8.5,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.5,
            ),
            "eco_park": VisualVariableSpec(
                geometry_type="point",
                fill_color="#16A34A",
                stroke_color="#14532D",
                marker_symbol="^",
                marker_size=8.5,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.5,
            ),
            "university_landmark": VisualVariableSpec(
                geometry_type="point",
                fill_color="#2563EB",
                stroke_color="#1E3A8A",
                marker_symbol="o",
                marker_size=8.0,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.5,
            ),
        }

    @staticmethod
    def get_admin_styles() -> Dict[str, VisualVariableSpec]:
        """获取行政规划图境界线跳绘与内侧色带、行政驻地符号规范"""
        return {
            "city_boundary": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#4C1D95",
                stroke_width=1.8,
                stroke_linestyle="dashdot",
                inner_glow_color="#C4B5FD",
                inner_glow_width=5.5,
            ),
            "district_boundary": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#64748B",
                stroke_width=1.0,
                stroke_linestyle="dashed",
                inner_glow_color="#E2E8F0",
                inner_glow_width=2.8,
            ),
            "provincial_capital": VisualVariableSpec(
                geometry_type="point",
                fill_color="#DC2626",
                stroke_color="#991B1B",
                marker_symbol="*",
                marker_size=14.0,
                marker_halo_color="#FFFFFF",
                marker_halo_width=2.0,
            ),
            "municipal_seat": VisualVariableSpec(
                geometry_type="point",
                fill_color="#E11D48",
                stroke_color="#881337",
                marker_symbol="double_circle",
                marker_size=9.0,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.6,
            ),
            "district_seat": VisualVariableSpec(
                geometry_type="point",
                fill_color="#FFFFFF",
                stroke_color="#1E293B",
                marker_symbol="o",
                marker_size=6.0,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.2,
            ),
        }

    @staticmethod
    def get_terrain_styles() -> Dict[str, VisualVariableSpec]:
        """获取地势图计曲线、首曲线与山峰高程点符号规范"""
        return {
            "index_contour": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#6B4226",
                stroke_width=1.35,
                stroke_linestyle="solid",
            ),
            "intermediate_contour": VisualVariableSpec(
                geometry_type="line",
                stroke_color="#A67B5B",
                stroke_width=0.65,
                stroke_linestyle="solid",
            ),
            "peak_point": VisualVariableSpec(
                geometry_type="point",
                fill_color="#111827",
                stroke_color="#FFFFFF",
                marker_symbol="^",
                marker_size=8.5,
                marker_halo_color="#FFFFFF",
                marker_halo_width=1.5,
            ),
        }
