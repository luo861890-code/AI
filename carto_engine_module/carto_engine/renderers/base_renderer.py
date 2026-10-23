# -*- coding: utf-8 -*-
"""
================================================================================
[分类五 - 子模块 5.0] 专题地图渲染抽象基类 `base_renderer.py`
================================================================================
统一串联：
1. 空间要素校准（CRS 校准、GCJ-02 纠偏、几何拓扑修复、边界捕捉与图廓裁剪）
2. 尺度驱动制图综合（Töpfer 开方根选取、等高线/水系 Chaikin 平滑、POI 优先级抽稀）
3. 复合地图符号绘制（双线道路 Casing、铁路轨枕符、政区境界内侧晕带、双圈驻地符号）
4. 八方位碰撞避让注记与五大地图整饰要素排版
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from ..models_and_specs import CartoTaskSpec, VisualVariableSpec, CoordSystemType
from ..calibration.crs_calibrator import CRSCalibrator
from ..calibration.topology_calibrator import TopologyCalibrator
from ..layout_and_elements.label_engine import CartoLabelEngine
from ..layout_and_elements.map_elements import MapElementsComposer


def detect_cjk_font() -> str:
    """自动检测系统可用的中文无损矢量字体"""
    preferred = ["Noto Sans CJK JP", "Noto Serif CJK JP", "WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font_name in preferred:
        if font_name in available:
            return font_name
    return "sans-serif"


class BaseCartoRenderer(ABC):
    """四大基础地图专题渲染器的公共抽象基类"""

    def __init__(self, task_spec: CartoTaskSpec):
        self.task_spec = task_spec
        self.font_family = detect_cjk_font()
        self.legend_items: List[Dict[str, Any]] = []

    def calibrate_all_layers(
        self,
        raw_layers: Dict[str, gpd.GeoDataFrame],
        source_crs_map: Optional[Dict[str, CoordSystemType]] = None,
    ) -> Dict[str, gpd.GeoDataFrame]:
        """对输入的点、线、面 SHP 图层字典执行统一坐标系校准、拓扑修复与图廓裁剪"""
        source_crs_map = source_crs_map or {}
        calibrated: Dict[str, gpd.GeoDataFrame] = {}

        # 确定研究区边界与图廓范围
        ref_admin = raw_layers.get("admin_polygons")
        if ref_admin is not None and not ref_admin.empty:
            ref_admin = CRSCalibrator.calibrate_geodataframe(
                ref_admin, source_crs_map.get("admin_polygons", CoordSystemType.WGS84), target_epsg=4326
            )
            ref_admin = TopologyCalibrator.repair_geometries(ref_admin, "polygon")
            calibrated["admin_polygons"] = ref_admin
            if self.task_spec.bbox_wgs84 is None:
                b = ref_admin.total_bounds
                dx, dy = (b[2] - b[0]) * 0.06, (b[3] - b[1]) * 0.08
                self.task_spec.bbox_wgs84 = (b[0] - dx, b[1] - dy, b[2] + dx, b[3] + dy)

        if self.task_spec.bbox_wgs84 is None:
            self.task_spec.bbox_wgs84 = (114.05, 30.38, 114.58, 30.76)

        for key, gdf in raw_layers.items():
            if key == "admin_polygons" or gdf is None or gdf.empty:
                continue
            c_type = source_crs_map.get(key, CoordSystemType.WGS84)
            cgdf = CRSCalibrator.calibrate_geodataframe(gdf, c_type, target_epsg=4326)
            gtype_sample = cgdf.geometry.iloc[0].geom_type
            expected = (
                "polygon" if "Polygon" in gtype_sample else ("line" if "Line" in gtype_sample else "point")
            )
            cgdf = TopologyCalibrator.repair_geometries(cgdf, expected)
            cgdf = TopologyCalibrator.clip_to_bbox(cgdf, self.task_spec.bbox_wgs84)
            calibrated[key] = cgdf

        return calibrated

    @staticmethod
    def draw_composite_line(
        ax,
        line_gdf: gpd.GeoDataFrame,
        style: VisualVariableSpec,
        zorder: int = 55,
    ):
        """
        绘制复合线状地图符号：
        1. 支持双线道路外廓 (Road Casing：底层粗暗线 + 顶层细亮芯线)
        2. 支持政区境界线内侧半透明色带晕染 (Boundary Inner Glow / Tint Band)
        3. 支持铁路黑白相间轨枕符号 (Railway Ticks)
        """
        if line_gdf is None or line_gdf.empty:
            return

        # (a) 政区境界内侧色带晕染
        if style.inner_glow_color and style.inner_glow_width:
            line_gdf.plot(
                ax=ax,
                color=style.inner_glow_color,
                linewidth=style.inner_glow_width,
                alpha=0.38,
                capstyle="round",
                joinstyle="round",
                zorder=zorder - 2,
            )

        # (b) 双线道路外廓线 (Road Casing)
        if style.casing_color and style.casing_width:
            line_gdf.plot(
                ax=ax,
                color=style.casing_color,
                linewidth=style.casing_width,
                linestyle=style.stroke_linestyle,
                capstyle="round",
                joinstyle="round",
                zorder=zorder - 1,
            )

        # (c) 主体线芯
        line_gdf.plot(
            ax=ax,
            color=style.stroke_color,
            linewidth=style.stroke_width,
            linestyle=style.stroke_linestyle,
            capstyle="round",
            joinstyle="round",
            zorder=zorder,
        )

        # (d) 铁路黑白相间轨枕线 (Railway Ticks)
        if style.railway_ticks:
            line_gdf.plot(
                ax=ax,
                color="#FFFFFF",
                linewidth=style.stroke_width * 0.58,
                linestyle=(0, (3.2, 3.2)),
                capstyle="butt",
                zorder=zorder + 1,
            )

    @staticmethod
    def draw_composite_points(
        ax,
        point_gdf: gpd.GeoDataFrame,
        style: VisualVariableSpec,
        label_engine: Optional[CartoLabelEngine] = None,
        zorder: int = 80,
    ):
        """
        绘制复合点状地图符号：
        支持五角星 (`*`)、市级双同心圆 (`double_circle`)、山峰正三角 (`^`)、方形枢纽 (`s`) 等，
        自动附加白色/金色光晕底衬并向注记避让引擎注册符号障碍物。
        """
        if point_gdf is None or point_gdf.empty:
            return

        xs = [g.centroid.x for g in point_gdf.geometry]
        ys = [g.centroid.y for g in point_gdf.geometry]

        if label_engine is not None:
            for x, y in zip(xs, ys):
                label_engine.register_symbol_obstacle(x, y, radius_ratio=0.012)

        if style.marker_symbol == "double_circle":
            # 市级驻地经典双同心圆符号：外白晕 -> 红圈白底 -> 中心红实点
            ax.scatter(
                xs, ys, s=(style.marker_size * 1.45) ** 2, marker="o",
                 c=style.marker_halo_color, edgecolors="none", zorder=zorder - 1
            )
            ax.scatter(
                xs, ys, s=(style.marker_size * 1.15) ** 2, marker="o",
                facecolors="#FFFFFF", edgecolors=style.fill_color, linewidths=1.6, zorder=zorder
            )
            ax.scatter(
                xs, ys, s=(style.marker_size * 0.45) ** 2, marker="o",
                c=style.fill_color, edgecolors="none", zorder=zorder + 1
            )
        else:
            # 外层 Halo 光晕垫底
            if style.marker_halo_width > 0:
                ax.scatter(
                    xs,
                    ys,
                    s=(style.marker_size + style.marker_halo_width * 2.0) ** 2,
                    marker=style.marker_symbol,
                    c=style.marker_halo_color,
                    edgecolors="none",
                    alpha=0.92,
                    zorder=zorder - 1,
                )
            ax.scatter(
                xs,
                ys,
                s=style.marker_size ** 2,
                marker=style.marker_symbol,
                c=style.fill_color,
                edgecolors=style.stroke_color,
                linewidths=1.0,
                zorder=zorder,
            )

    def compose_map_elements(self, ax, extent: Tuple[float, float, float, float]):
        """统一装配五大地图整饰要素"""
        if self.task_spec.show_graticule:
            MapElementsComposer.draw_zebra_neatline_and_graticule(ax, extent, self.font_family)
        MapElementsComposer.draw_title_banner(
            ax, self.task_spec.title, self.task_spec.subtitle, self.font_family
        )
        if self.task_spec.show_compass:
            MapElementsComposer.draw_compass_rose(ax, self.font_family)
        if self.task_spec.show_scale_bar:
            MapElementsComposer.draw_graphic_scale_bar(ax, extent, self.font_family)
        if self.task_spec.show_legend and self.legend_items:
            MapElementsComposer.draw_structured_legend(ax, self.legend_items, self.font_family)

    @abstractmethod
    def render_on_axes(self, ax, raw_layers: Dict[str, gpd.GeoDataFrame], **kwargs):
        """由四个具体专题地图子类实现的核心渲染逻辑"""
        raise NotImplementedError
