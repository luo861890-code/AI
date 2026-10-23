# -*- coding: utf-8 -*-
"""
================================================================================
[分类二 - 子模块 2.3] 尺度驱动的自动制图综合引擎 `generalization.py`
================================================================================
地图学理论支撑：
1. **Töpfer 开方根定律 (Radical Law)**：
   $$n_F = n_A \cdot C_b \cdot C_z \cdot \sqrt{\frac{M_A}{M_F}}$$
   根据原始数据比例尺分母 $M_A$ 与目标成图比例尺分母 $M_F$ 自动计算目标保留要素数量 $n_F$。
2. **Chaikin 拐角切割平滑算法 (Corner-Cutting Smoothing)**：
   解决会议记录与中期报告中指出的“DEM提取的原始等高线折线感过强、缺少圆滑特征保持”问题。
3. **基于空间最小间距与等级优先级的点群抽稀 (Priority Spatial Thinning)**：
   解决高密度 POI 在中小比例尺下严重相互压盖的问题。
"""

import math
from typing import Optional
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon


class CartoGeneralizer:
    """地图学自动制图综合算子集合（选取 Selection、化简 Simplification、平滑 Smoothing、移位/抽稀 Displacement）"""

    @staticmethod
    def topfer_radical_law_count(
        n_source: int,
        source_scale_denom: int,
        target_scale_denom: int,
        symbol_factor_cb: float = 1.0,
        importance_factor_cz: float = 1.0,
    ) -> int:
        """
        基于 Töpfer 开方根定律计算目标比例尺下应当保留的要素数量上限。
        """
        if target_scale_denom <= source_scale_denom or n_source <= 0:
            return n_source
        ratio = math.sqrt(float(source_scale_denom) / float(target_scale_denom))
        n_target = int(round(n_source * symbol_factor_cb * importance_factor_cz * ratio))
        return max(3, min(n_source, n_target))

    @classmethod
    def thin_points_by_priority_and_distance(
        cls,
        point_gdf: gpd.GeoDataFrame,
        min_distance: float = 0.012,
        priority_col: Optional[str] = "priority",
        max_keep: Optional[int] = None,
    ) -> gpd.GeoDataFrame:
        """
        对点状要素（如旅游景点 POI、交通站点）按重要性等级排序后进行空间半径互斥抽稀。
        优先保留高等级地标（如 5A 景区、核心火车站），剔除距离过近的次要同质点。
        """
        if point_gdf is None or point_gdf.empty:
            return point_gdf

        df = point_gdf.copy()
        if priority_col and priority_col in df.columns:
            df = df.sort_values(by=priority_col, ascending=True).reset_index(drop=True)

        kept_indices = []
        kept_coords = []

        for idx, row in df.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            pt = geom.centroid
            x, y = pt.x, pt.y
            conflict = False
            for kx, ky in kept_coords:
                if math.hypot(x - kx, y - ky) < min_distance:
                    conflict = True
                    break
            if not conflict:
                kept_indices.append(idx)
                kept_coords.append((x, y))
                if max_keep is not None and len(kept_indices) >= max_keep:
                    break

        return df.loc[kept_indices].reset_index(drop=True)

    @staticmethod
    def _chaikin_smooth_coords(coords: list, iterations: int = 2) -> list:
        """
        Chaikin 曲线圆滑算法：将生硬折线转换为符合自然地貌/水系形态的光滑曲线。
        """
        if len(coords) < 3 or iterations <= 0:
            return coords
        pts = np.array(coords, dtype=float)
        is_closed = np.allclose(pts[0], pts[-1])
        for _ in range(iterations):
            new_pts = []
            if not is_closed:
                new_pts.append(pts[0])
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i + 1]
                q = 0.75 * p0 + 0.25 * p1
                r = 0.25 * p0 + 0.75 * p1
                new_pts.extend([q, r])
            if is_closed:
                new_pts.append(new_pts[0])
            else:
                new_pts.append(pts[-1])
            pts = np.array(new_pts)
        return [tuple(p) for p in pts]

    @classmethod
    def smooth_lines(
        cls,
        line_gdf: gpd.GeoDataFrame,
        simplify_tolerance: float = 0.0003,
        chaikin_iterations: int = 2,
    ) -> gpd.GeoDataFrame:
        """
        线状要素（等高线、河流、曲线道路）“先化简去毛刺、后平滑保弯曲”组合算子。
        """
        if line_gdf is None or line_gdf.empty:
            return line_gdf

        out = line_gdf.copy()

        def _process_geom(geom):
            if geom is None or geom.is_empty:
                return geom
            if simplify_tolerance > 0:
                geom = geom.simplify(simplify_tolerance, preserve_topology=True)
            if geom.geom_type == "LineString":
                smoothed = cls._chaikin_smooth_coords(list(geom.coords), chaikin_iterations)
                return LineString(smoothed) if len(smoothed) >= 2 else geom
            elif geom.geom_type == "MultiLineString":
                parts = []
                for part in geom.geoms:
                    smoothed = cls._chaikin_smooth_coords(list(part.coords), chaikin_iterations)
                    if len(smoothed) >= 2:
                        parts.append(LineString(smoothed))
                return MultiLineString(parts) if parts else geom
            return geom

        out["geometry"] = out["geometry"].apply(_process_geom)
        return out
