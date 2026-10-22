# -*- coding: utf-8 -*-
"""
================================================================================
[分类五 - 子模块 5.3] 行政规划专题图渲染器 `admin_map.py`
================================================================================
地图学设计要点（落实会议记录中“行政区划图必须具备严肃性与标准性”的要求）：
1. **拓扑邻接贪心四色/五色普染算法**：自动计算各区县多边形的空间邻接矩阵，确保相邻政区底色绝不相同，
   且严格采用国家标准政区图柔和雅致的高明度暖色系。
2. **境界线跳绘与内侧色带晕染 (Boundary Inner Glow / Tint Band)**：
   - 彻底剔除杂乱的 OSM 重复边界与普通道路干扰；
   - 区县界采用虚线跳绘 + 浅灰紫内侧色带；市界外轮廓采用粗点划线 + 紫红内侧色带晕染，立体感强烈。
3. **三级行政驻地符号**：省会驻地（红五角星 `*`）、市级政府驻地（红白双同心圆 `double_circle`）、区级驻地（白底黑圈 `o`）。
4. **政区字列注记与驻地名称双层表达**：政区名采用带字距的居中字列（如“武 昌 区”），驻地符号旁配置精确定位注记。
"""

from typing import Dict
import geopandas as gpd

from .base_renderer import BaseCartoRenderer
from ..symbology.color_schemes import CartoColorSchemes
from ..symbology.symbol_library import CartoSymbolLibrary
from ..layout_and_elements.layer_manager import LayerHierarchyManager
from ..layout_and_elements.label_engine import CartoLabelEngine


class AdministrativeMapRenderer(BaseCartoRenderer):
    """标准行政区划与空间规划专题图渲染器"""

    def render_on_axes(self, ax, raw_layers: Dict[str, gpd.GeoDataFrame], **kwargs):
        layers = self.calibrate_all_layers(raw_layers)
        extent = self.task_spec.bbox_wgs84
        ax.set_facecolor("#F1F5F9")
        label_engine = CartoLabelEngine(extent)
        self.legend_items = []

        admin_gdf = layers.get("admin_polygons")
        admin_styles = CartoSymbolLibrary.get_admin_styles()

        # 1. 行政区四色/五色拓扑邻接普染
        if admin_gdf is not None and not admin_gdf.empty:
            fill_colors = CartoColorSchemes.compute_greedy_polygon_coloring(admin_gdf)
            admin_gdf = admin_gdf.copy()
            admin_gdf["_fill_color"] = fill_colors
            admin_gdf.plot(
                ax=ax,
                color=admin_gdf["_fill_color"],
                edgecolor="none",
                alpha=0.92,
                zorder=LayerHierarchyManager.get_z_order("admin_base_polygon"),
            )

        # 2. 主要骨干水系（长江、汉江作为重要自然地理骨架线，置于政区底色之上、界线之下）
        water_gdf = layers.get("water_polygons")
        if water_gdf is not None and not water_gdf.empty:
            water_gdf.plot(
                ax=ax,
                facecolor=CartoColorSchemes.WATER_FILL,
                edgecolor=CartoColorSchemes.WATER_STROKE,
                linewidth=0.75,
                alpha=0.88,
                zorder=LayerHierarchyManager.get_z_order("water_polygon"),
            )

        # 3. 区县级境界线（内侧色带晕染 + 虚线跳绘）与外围市界（内侧紫红晕带 + 点划线）
        if admin_gdf is not None and not admin_gdf.empty:
            district_boundaries = gpd.GeoDataFrame(geometry=admin_gdf.geometry.boundary, crs=admin_gdf.crs)
            self.draw_composite_line(
                ax,
                district_boundaries,
                admin_styles["district_boundary"],
                zorder=LayerHierarchyManager.get_z_order("admin_district_boundary"),
            )

            city_outer_geom = admin_gdf.unary_union.boundary
            city_outer_gdf = gpd.GeoDataFrame(geometry=[city_outer_geom], crs=admin_gdf.crs)
            self.draw_composite_line(
                ax,
                city_outer_gdf,
                admin_styles["city_boundary"],
                zorder=LayerHierarchyManager.get_z_order("admin_city_boundary"),
            )

            self.legend_items.extend([
                {
                    "label": "市级行政区划界线（附色带）",
                    "geom_type": "line",
                    "stroke_color": admin_styles["city_boundary"].stroke_color,
                    "stroke_width": 2.2,
                    "linestyle": "dashdot",
                },
                {
                    "label": "区（县）级行政区划界线",
                    "geom_type": "line",
                    "stroke_color": admin_styles["district_boundary"].stroke_color,
                    "stroke_width": 1.2,
                    "linestyle": "dashed",
                },
            ])

        # 4. 省/市/区三级行政驻地符号
        seats_gdf = layers.get("admin_seats_points")
        if seats_gdf is not None and not seats_gdf.empty:
            seat_specs = [
                ("provincial_capital", "省会行政中心驻地", True, 9.5),
                ("municipal_seat", "市级人民政府驻地", True, 8.8),
                ("district_seat", "区（县）级政府驻地", False, 7.6),
            ]
            for s_class, label_cn, force_lbl, fsize in seat_specs:
                sub = seats_gdf[seats_gdf["feat_class"] == s_class]
                if not sub.empty and s_class in admin_styles:
                    st = admin_styles[s_class]
                    self.draw_composite_points(ax, sub, st, label_engine=label_engine, zorder=86)
                    self.legend_items.append({
                        "label": label_cn,
                        "geom_type": "point",
                        "marker": "o" if st.marker_symbol == "double_circle" else st.marker_symbol,
                        "markersize": st.marker_size * 0.85,
                        "fill_color": st.fill_color,
                        "stroke_color": st.stroke_color,
                    })
                    if s_class in ("provincial_capital", "municipal_seat"):
                        for _, row in sub.iterrows():
                            pt = row.geometry.centroid
                            label_engine.place_point_label(
                                ax,
                                pt.x,
                                pt.y,
                                row["name"],
                                self.font_family,
                                font_size=fsize,
                                font_weight="bold",
                                font_color="#991B1B",
                                force_place=True,
                            )

        # 5. 政区名称居中字列注记（如“武 昌 区”、“江 岸 区”）
        if admin_gdf is not None and not admin_gdf.empty:
            for _, row in admin_gdf.iterrows():
                if row.get("name"):
                    label_engine.place_polygon_spaced_label(
                        ax,
                        row.geometry,
                        row["name"],
                        self.font_family,
                        font_size=8.8,
                        font_color="#1E293B",
                        char_spacing=1,
                        is_water=False,
                    )

        self.compose_map_elements(ax, extent)
