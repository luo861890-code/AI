# -*- coding: utf-8 -*-
"""
================================================================================
[分类五 - 子模块 5.1] 交通专题图渲染器 `traffic_map.py`
================================================================================
地图学设计要点：
1. **基底弱化 (Muted Basemap Ground)**：行政区底图采用极低饱和度的暖灰白 (`#F8FAFC`)，水系采用柔和浅蓝，
   通过强烈的明度与纯度对比使道路网与轨道交通跃升为第一视觉平面（Figure）。
2. **等级化双线道路符号 (Hierarchical Road Casings)**：
   高速公路（橙红双线 4.2pt） > 快速路/主干道（暖黄双线 3.2pt） > 次干道（白芯灰边 2.3pt） > 支路（细灰线 0.85pt）。
3. **铁路黑白相间轨枕线与地铁专色网络**：清晰区分国铁干线（京广高铁/武九铁路）与城市轨道交通干线。
4. **交通枢纽多级符号与八方位避让注记**：三大火车站、核心跨江大桥、换乘枢纽突出显示。
"""

from typing import Dict
import geopandas as gpd

from .base_renderer import BaseCartoRenderer
from ..symbology.color_schemes import CartoColorSchemes
from ..symbology.symbol_library import CartoSymbolLibrary
from ..layout_and_elements.layer_manager import LayerHierarchyManager
from ..layout_and_elements.label_engine import CartoLabelEngine
from ..calibration.generalization import CartoGeneralizer


class TrafficMapRenderer(BaseCartoRenderer):
    """交通专题图（多级道路网、国铁干线、地铁网络与综合交通枢纽）专业渲染器"""

    def render_on_axes(self, ax, raw_layers: Dict[str, gpd.GeoDataFrame], **kwargs):
        layers = self.calibrate_all_layers(raw_layers)
        extent = self.task_spec.bbox_wgs84
        ax.set_facecolor("#EEF2F6")
        label_engine = CartoLabelEngine(extent)
        self.legend_items = []

        # 1. 基底行政区（消色系暖灰白，突出交通网）
        admin_gdf = layers.get("admin_polygons")
        if admin_gdf is not None and not admin_gdf.empty:
            admin_gdf.plot(
                ax=ax,
                facecolor="#F8FAFC",
                edgecolor="#CBD5E1",
                linewidth=0.7,
                linestyle="--",
                zorder=LayerHierarchyManager.get_z_order("admin_base_polygon"),
            )

        # 2. 水系图层（长江、汉江、东湖，交代跨江交通背景）
        water_gdf = layers.get("water_polygons")
        if water_gdf is not None and not water_gdf.empty:
            water_gdf.plot(
                ax=ax,
                facecolor=CartoColorSchemes.WATER_FILL,
                edgecolor=CartoColorSchemes.WATER_STROKE,
                linewidth=0.8,
                zorder=LayerHierarchyManager.get_z_order("water_polygon"),
            )
            for _, row in water_gdf.iterrows():
                if row.get("name"):
                    label_engine.place_polygon_spaced_label(
                        ax, row.geometry, row["name"], self.font_family, font_size=8.0, is_water=True
                    )

        # 3. 多级道路与轨道网络（按低等级 -> 高等级顺序叠置，实现道路交叉口平滑融合）
        road_styles = CartoSymbolLibrary.get_traffic_road_styles()
        roads_gdf = layers.get("roads_lines")
        if roads_gdf is not None and not roads_gdf.empty:
            roads_gdf = CartoGeneralizer.smooth_lines(roads_gdf, simplify_tolerance=0.0002, chaikin_iterations=1)
            order_specs = [
                ("tertiary", "城市支路/次要通道", "road_tertiary"),
                ("secondary", "城市次干道", "road_secondary"),
                ("primary", "城市主干道/快速路", "road_primary"),
                ("motorway", "高速公路/环线高速", "road_motorway"),
                ("railway", "国铁/高铁干线", "railway_line"),
                ("subway_line2", "轨道交通2号线", "subway_line"),
                ("subway_line4", "轨道交通4号线", "subway_line"),
            ]
            for r_class, label_cn, z_key in order_specs:
                sub = roads_gdf[roads_gdf["feat_class"] == r_class]
                if not sub.empty and r_class in road_styles:
                    st = road_styles[r_class]
                    self.draw_composite_line(ax, sub, st, zorder=LayerHierarchyManager.get_z_order(z_key))
                    self.legend_items.append({
                        "label": label_cn,
                        "geom_type": "line",
                        "stroke_color": st.stroke_color,
                        "stroke_width": st.stroke_width,
                        "linestyle": "dashed" if st.railway_ticks else st.stroke_linestyle,
                    })

        # 4. 交通枢纽点状要素（火车站、跨江大桥、核心地铁换乘站）
        hub_styles = CartoSymbolLibrary.get_traffic_hub_styles()
        hubs_gdf = layers.get("traffic_hubs_points")
        if hubs_gdf is not None and not hubs_gdf.empty:
            hubs_gdf = CartoGeneralizer.thin_points_by_priority_and_distance(hubs_gdf, min_distance=0.015)
            hub_specs = [
                ("railway_station", "特等火车站/综合客运枢纽", True, 8.8),
                ("bridge_crossing", "长江/汉江跨江通道", False, 7.8),
                ("subway_transfer", "核心轨道换乘站", False, 7.5),
            ]
            for h_class, label_cn, force_lbl, fsize in hub_specs:
                sub = hubs_gdf[hubs_gdf["feat_class"] == h_class]
                if not sub.empty and h_class in hub_styles:
                    st = hub_styles[h_class]
                    self.draw_composite_points(ax, sub, st, label_engine=label_engine, zorder=84)
                    self.legend_items.append({
                        "label": label_cn,
                        "geom_type": "point",
                        "marker": st.marker_symbol,
                        "markersize": st.marker_size * 0.85,
                        "fill_color": st.fill_color,
                        "stroke_color": st.stroke_color,
                    })
                    for _, row in sub.iterrows():
                        pt = row.geometry.centroid
                        label_engine.place_point_label(
                            ax,
                            pt.x,
                            pt.y,
                            row["name"],
                            self.font_family,
                            font_size=fsize,
                            font_weight="bold" if force_lbl else "normal",
                            font_color="#7F1D1D" if h_class == "railway_station" else "#1E293B",
                            force_place=force_lbl,
                        )

        self.compose_map_elements(ax, extent)
