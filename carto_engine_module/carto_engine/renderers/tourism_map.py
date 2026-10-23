# -*- coding: utf-8 -*-
"""
================================================================================
[分类五 - 子模块 5.2] 旅游景点专题图渲染器 `tourism_map.py`
================================================================================
地图学设计要点：
1. **水绿生态基底烘托**：突出东湖生态旅游风景区、磨山、沙湖等城市蓝绿空间基底（暖米白陆地 + 翠绿景区生态面 + 清澈蓝水体）。
2. **多维属性组合符号**：
   - 形状与尺寸编码景区等级（5A 级大号红金五角星 > 4A 级橙钻徽章 > 生态公园绿三角 > 百年名校地标蓝圆章）。
   - 核心景区外围绘制 1.5km 游览辐射活力圈（半透明暖粉光环）。
3. **精品游览路线引导流向线**：采用品紫双层虚线连接“黄鹤楼—长江大桥—东湖绿道—武汉大学—湖北省博物馆”经典文旅走廊。
4. **基于优先级的 POI 抽稀与零压盖注记**：自动解决中期报告提到的“高密度景点 POI 重叠压盖”难题。
"""

from typing import Dict
import geopandas as gpd

from .base_renderer import BaseCartoRenderer
from ..symbology.color_schemes import CartoColorSchemes
from ..symbology.symbol_library import CartoSymbolLibrary
from ..layout_and_elements.layer_manager import LayerHierarchyManager
from ..layout_and_elements.label_engine import CartoLabelEngine
from ..calibration.generalization import CartoGeneralizer
from ..models_and_specs import VisualVariableSpec


class TourismMapRenderer(BaseCartoRenderer):
    """旅游景点与精品文旅路线专题图渲染器"""

    def render_on_axes(self, ax, raw_layers: Dict[str, gpd.GeoDataFrame], **kwargs):
        layers = self.calibrate_all_layers(raw_layers)
        extent = self.task_spec.bbox_wgs84
        ax.set_facecolor("#FBF9F5")
        label_engine = CartoLabelEngine(extent)
        self.legend_items = []

        # 1. 温暖人文米白底图
        admin_gdf = layers.get("admin_polygons")
        if admin_gdf is not None and not admin_gdf.empty:
            admin_gdf.plot(
                ax=ax,
                facecolor="#FDFBF7",
                edgecolor="#E2D9C8",
                linewidth=0.75,
                zorder=LayerHierarchyManager.get_z_order("admin_base_polygon"),
            )

        # 2. 生态绿地与风景名胜区范围面
        green_gdf = layers.get("greenspace_polygons")
        if green_gdf is not None and not green_gdf.empty:
            green_gdf.plot(
                ax=ax,
                facecolor=CartoColorSchemes.GREENSPACE_FILL,
                edgecolor=CartoColorSchemes.GREENSPACE_STROKE,
                linewidth=0.8,
                alpha=0.85,
                zorder=LayerHierarchyManager.get_z_order("greenspace_polygon"),
            )
            self.legend_items.append({
                "label": "生态绿地/风景名胜保育区",
                "geom_type": "polygon",
                "fill_color": CartoColorSchemes.GREENSPACE_FILL,
                "stroke_color": CartoColorSchemes.GREENSPACE_STROKE,
            })

        # 3. 江河湖泊水系
        water_gdf = layers.get("water_polygons")
        if water_gdf is not None and not water_gdf.empty:
            water_gdf.plot(
                ax=ax,
                facecolor=CartoColorSchemes.WATER_FILL,
                edgecolor=CartoColorSchemes.WATER_STROKE,
                linewidth=0.85,
                zorder=LayerHierarchyManager.get_z_order("water_polygon"),
            )
            for _, row in water_gdf.iterrows():
                if row.get("name"):
                    label_engine.place_polygon_spaced_label(
                        ax, row.geometry, row["name"], self.font_family, font_size=8.0, is_water=True
                    )

        # 4. 5A 景区游览辐射活力圈（缓冲区视觉引导）
        pois_gdf = layers.get("tourism_pois_points")
        if pois_gdf is not None and not pois_gdf.empty:
            scenic_5a = pois_gdf[pois_gdf["feat_class"] == "5A_scenic"].copy()
            if not scenic_5a.empty:
                buffers = scenic_5a.geometry.buffer(0.018)
                gpd.GeoSeries(buffers, crs="EPSG:4326").plot(
                    ax=ax,
                    facecolor="#FDA4AF",
                    edgecolor="#F43F5E",
                    linewidth=0.8,
                    linestyle=":",
                    alpha=0.25,
                    zorder=LayerHierarchyManager.get_z_order("tourism_buffer_zone"),
                )
                self.legend_items.append({
                    "label": "5A景区核心文旅辐射圈",
                    "geom_type": "polygon",
                    "fill_color": "#FDA4AF",
                    "stroke_color": "#F43F5E",
                    "alpha": 0.45,
                })

        # 5. 旅游精品游览路线廊道
        routes_gdf = layers.get("tourism_routes_lines")
        if routes_gdf is not None and not routes_gdf.empty:
            routes_gdf = CartoGeneralizer.smooth_lines(routes_gdf, simplify_tolerance=0.0002, chaikin_iterations=2)
            route_style = VisualVariableSpec(
                geometry_type="line",
                stroke_color="#9333EA",
                stroke_width=2.1,
                stroke_linestyle="dashed",
                casing_color="#F3E8FF",
                casing_width=4.0,
            )
            self.draw_composite_line(ax, routes_gdf, route_style, zorder=LayerHierarchyManager.get_z_order("tourism_route"))
            self.legend_items.append({
                "label": "精品山水人文游览专线",
                "geom_type": "line",
                "stroke_color": "#9333EA",
                "stroke_width": 2.1,
                "linestyle": "dashed",
            })

        # 6. 多级旅游景点符号与防碰撞注记
        poi_styles = CartoSymbolLibrary.get_tourism_poi_styles()
        if pois_gdf is not None and not pois_gdf.empty:
            pois_thinned = CartoGeneralizer.thin_points_by_priority_and_distance(pois_gdf, min_distance=0.014)
            poi_specs = [
                ("5A_scenic", "国家5A级旅游景区", True, 9.2, "#9F1239"),
                ("4A_cultural", "国家4A级人文历史名胜", True, 8.2, "#9A3412"),
                ("university_landmark", "百年学府/文化地标", False, 8.0, "#1E40AF"),
                ("eco_park", "滨水湿地/生态森林公园", False, 7.8, "#166534"),
            ]
            for p_class, label_cn, force_lbl, fsize, tcolor in poi_specs:
                sub = pois_thinned[pois_thinned["feat_class"] == p_class]
                if not sub.empty and p_class in poi_styles:
                    st = poi_styles[p_class]
                    self.draw_composite_points(ax, sub, st, label_engine=label_engine, zorder=85)
                    self.legend_items.append({
                        "label": label_cn,
                        "geom_type": "point",
                        "marker": st.marker_symbol,
                        "markersize": st.marker_size * 0.82,
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
                            font_color=tcolor,
                            force_place=force_lbl,
                        )

        self.compose_map_elements(ax, extent)
