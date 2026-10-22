# -*- coding: utf-8 -*-
"""
================================================================================
[分类五 - 子模块 5.4] 地势专题图渲染器 `terrain_map.py`
================================================================================
地图学设计要点（彻底解决会议记录指出的“等高线折线感过强、仅画单调线条无地势感”问题）：
1. **高程分层设色 (Hypsometric Tinting)**：根据 DEM 高程场生成平原柔和绿 -> 台地暖黄 -> 丘陵浅褐 -> 山脊深棕渐变色层。
2. **西北光源分析性山体阴影 (Analytical Hillshading, 方位角 315°, 高度角 45°)**：
   计算高程场梯度 $(\partial z / \partial x, \partial z / \partial y)$，生成三维立体明暗地貌晕渲并叠加于分层设色之上。
3. **Chaikin 曲线圆滑后的计曲线与首曲线**：
   - 首曲线 (Intermediate Contour, 25m 间隔)：细浅棕实线 (`#A67B5B`, 0.65pt)
   - 计曲线 (Index Contour, 100m 间隔)：加粗深棕实线 (`#6B4226`, 1.35pt)，并沿等高线切线方向嵌印高程注记（如 `100m`, `200m`）。
4. **高程点与山峰符号 (`▲`)**：标注区域制高点与名山高程（如磨山 `118m`、喻家山 `149m`、九峰山 `268m`、木兰山 `582m`）。
"""

from typing import Dict
import numpy as np
import geopandas as gpd
from matplotlib.colors import LightSource

from .base_renderer import BaseCartoRenderer
from ..symbology.color_schemes import CartoColorSchemes
from ..symbology.symbol_library import CartoSymbolLibrary
from ..layout_and_elements.layer_manager import LayerHierarchyManager
from ..layout_and_elements.label_engine import CartoLabelEngine
from ..calibration.generalization import CartoGeneralizer


class TerrainMapRenderer(BaseCartoRenderer):
    """分层设色 + 山体阴影晕渲 + 计首曲线地势专题图渲染器"""

    def render_on_axes(self, ax, raw_layers: Dict[str, gpd.GeoDataFrame], **kwargs):
        layers = self.calibrate_all_layers(raw_layers)
        extent = self.task_spec.bbox_wgs84
        x0, y0, x1, y1 = extent
        label_engine = CartoLabelEngine(extent)
        self.legend_items = []
        terrain_styles = CartoSymbolLibrary.get_terrain_styles()

        # 1. 渲染 DEM 高程分层设色 + 315° 西北光源山体阴影 (Hillshade)
        dem_grid = kwargs.get("dem_grid")
        if dem_grid is not None:
            xx, yy, zz = dem_grid
            cmap = CartoColorSchemes.get_terrain_colormap()
            ls = LightSource(azdeg=315, altdeg=45)
            rgb_shaded = ls.shade(
                zz,
                cmap=cmap,
                vert_exag=0.08,
                blend_mode="soft",
                vmin=0.0,
                vmax=float(np.max(zz)),
            )
            ax.imshow(
                rgb_shaded,
                extent=(x0, x1, y0, y1),
                origin="lower",
                aspect="auto",
                zorder=LayerHierarchyManager.get_z_order("terrain_hillshade"),
            )
            self.legend_items.extend([
                {"label": "平原低地 (<50m)", "geom_type": "polygon", "fill_color": "#B8DFB0", "stroke_color": "#86C780"},
                {"label": "岗地丘陵 (50~200m)", "geom_type": "polygon", "fill_color": "#EED294", "stroke_color": "#C8A268"},
                {"label": "低山山脊 (>200m)", "geom_type": "polygon", "fill_color": "#B07546", "stroke_color": "#7A5230"},
            ])

        # 2. 水系叠置（江河湖泊切割地貌）
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

        # 3. 计曲线与首曲线（先执行 Chaikin 曲线平滑消除折线感）
        contours_gdf = layers.get("contours_lines")
        if contours_gdf is not None and not contours_gdf.empty:
            smoothed_contours = CartoGeneralizer.smooth_lines(
                contours_gdf, simplify_tolerance=0.00025, chaikin_iterations=2
            )
            minor_sub = smoothed_contours[smoothed_contours["feat_class"] == "intermediate_contour"]
            index_sub = smoothed_contours[smoothed_contours["feat_class"] == "index_contour"]

            if not minor_sub.empty:
                self.draw_composite_line(
                    ax,
                    minor_sub,
                    terrain_styles["intermediate_contour"],
                    zorder=LayerHierarchyManager.get_z_order("contour_intermediate"),
                )
                self.legend_items.append({
                    "label": "首曲线（基本等高距 25m）",
                    "geom_type": "line",
                    "stroke_color": terrain_styles["intermediate_contour"].stroke_color,
                    "stroke_width": 0.9,
                })

            if not index_sub.empty:
                self.draw_composite_line(
                    ax,
                    index_sub,
                    terrain_styles["index_contour"],
                    zorder=LayerHierarchyManager.get_z_order("contour_index"),
                )
                self.legend_items.append({
                    "label": "计曲线（加粗 100m 附高程注记）",
                    "geom_type": "line",
                    "stroke_color": terrain_styles["index_contour"].stroke_color,
                    "stroke_width": 1.8,
                })
                for _, row in index_sub.iterrows():
                    elev = float(row.get("elevation", 100.0))
                    label_engine.place_contour_elevation_label(
                        ax, row.geometry, elev, self.font_family, font_size=6.8
                    )

        # 4. 山峰与控制高程点 (▲ 符号 + 山名与高程值注记)
        peaks_gdf = layers.get("peaks_points")
        if peaks_gdf is not None and not peaks_gdf.empty:
            st = terrain_styles["peak_point"]
            self.draw_composite_points(ax, peaks_gdf, st, label_engine=label_engine, zorder=89)
            self.legend_items.append({
                "label": "山峰高程点 (▲ m)",
                "geom_type": "point",
                "marker": "^",
                "markersize": 7.5,
                "fill_color": st.fill_color,
                "stroke_color": "#FFFFFF",
            })
            for _, row in peaks_gdf.iterrows():
                pt = row.geometry.centroid
                elev_str = f"{row['name']} ({int(row.get('elevation', 150))}m)"
                label_engine.place_point_label(
                    ax,
                    pt.x,
                    pt.y,
                    elev_str,
                    self.font_family,
                    font_size=8.2,
                    font_weight="bold",
                    font_color="#111827",
                    halo_color="#FAF6F0",
                    force_place=True,
                )

        self.compose_map_elements(ax, extent)
