# -*- coding: utf-8 -*-
"""
================================================================================
[分类二 - 子模块 2.2] 点线面 SHP 空间几何与拓扑校准器 `topology_calibrator.py`
================================================================================
地图学问题诊断（对应会议记录与中期报告指导老师意见）：
1. 会议记录指出：OSM 要素与官方行政区划叠加时，存在“边界失真、越界溢出、双重描边重影”。
2. 原始 SHP 文件常存在多边形自相交 (Self-intersection)、悬挂微短线、极小碎多边形 (Sliver Polygons)
   以及属性字段命名不规范（如 `NAME`, `name`, `政区名称`, `adname` 混杂）问题。
"""

from typing import List, Optional, Tuple
import geopandas as gpd
from shapely.geometry import box
from shapely.ops import snap
from shapely.validation import make_valid


class TopologyCalibrator:
    """
    点、线、面矢量要素几何修复、碎多边形剔除、边界对齐捕捉与属性标准化引擎
    """

    STANDARD_NAME_CANDIDATES = ["name", "NAME", "Name", "名称", "政区名称", "中文名称", "fullname", "adname"]
    STANDARD_CLASS_CANDIDATES = ["type", "TYPE", "fclass", "highway", "class", "level", "admin_level", "grade"]

    @classmethod
    def standardize_schema(cls, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """统一校准不同来源 SHP 文件的属性字段名（确保 `name` 与 `feat_class` 存在）"""
        if gdf is None or gdf.empty:
            return gdf
        out = gdf.copy()
        if "name" not in out.columns:
            for cand in cls.STANDARD_NAME_CANDIDATES:
                if cand in out.columns:
                    out["name"] = out[cand].fillna("").astype(str)
                    break
            else:
                out["name"] = ""

        if "feat_class" not in out.columns:
            for cand in cls.STANDARD_CLASS_CANDIDATES:
                if cand in out.columns:
                    out["feat_class"] = out[cand].fillna("default").astype(str)
                    break
            else:
                out["feat_class"] = "default"
        return out

    @classmethod
    def repair_geometries(
        cls,
        gdf: gpd.GeoDataFrame,
        expected_geom_type: str,
        min_polygon_area_deg2: float = 1e-7,
        min_line_length_deg: float = 1e-5,
    ) -> gpd.GeoDataFrame:
        """
        修复点、线、面几何拓扑缺陷：
        1. 剔除空几何 (None / Empty) 与重复几何要素；
        2. 利用 `shapely.validation.make_valid` 修复面要素蝴蝶结自相交、环方向错误；
        3. 剔除低于面积阈值的碎多边形（Sliver Polygons）与微短悬挂线。
        """
        if gdf is None or gdf.empty:
            return gdf

        out = gdf[gdf.geometry.notnull() & (~gdf.geometry.is_empty)].copy()
        if out.empty:
            return out

        # 修复自相交等非法几何
        out["geometry"] = out["geometry"].apply(lambda g: make_valid(g) if not g.is_valid else g)

        # 按预期几何类型过滤与清理
        if expected_geom_type == "polygon":
            out = out[out.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
            if not out.empty:
                out = out[out.geometry.area >= min_polygon_area_deg2].copy()
        elif expected_geom_type == "line":
            out = out[out.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
            if not out.empty:
                out = out[out.geometry.length >= min_line_length_deg].copy()
        elif expected_geom_type == "point":
            out = out[out.geometry.geom_type.isin(["Point", "MultiPoint"])].copy()

        out = out.drop_duplicates(subset=["geometry"]).reset_index(drop=True)
        return cls.standardize_schema(out)

    @staticmethod
    def snap_and_clip_to_boundary(
        target_gdf: gpd.GeoDataFrame,
        reference_boundary_gdf: gpd.GeoDataFrame,
        snap_tolerance: float = 0.0005,
        clip_strictly: bool = True,
    ) -> gpd.GeoDataFrame:
        """
        跨源空间要素边界对齐捕捉（Snap）与研究区裁剪（Clip）：
        解决 OSM 水系/道路与权威行政区划边界不套合、越界溢出的问题。
        """
        if target_gdf is None or target_gdf.empty or reference_boundary_gdf is None or reference_boundary_gdf.empty:
            return target_gdf

        out = target_gdf.copy()
        ref_union = reference_boundary_gdf.unary_union

        if snap_tolerance > 0:
            out["geometry"] = out["geometry"].apply(lambda g: snap(g, ref_union, snap_tolerance))

        if clip_strictly:
            try:
                out = gpd.clip(out, ref_union)
                out = out[~out.geometry.is_empty].reset_index(drop=True)
            except Exception:
                pass
        return out

    @staticmethod
    def clip_to_bbox(
        gdf: gpd.GeoDataFrame,
        bbox: Tuple[float, float, float, float],
    ) -> gpd.GeoDataFrame:
        """按图廓经纬度范围 (min_lon, min_lat, max_lon, max_lat) 精确裁剪要素"""
        if gdf is None or gdf.empty or bbox is None:
            return gdf
        clip_box = box(*bbox)
        try:
            clipped = gpd.clip(gdf, clip_box)
            return clipped[~clipped.geometry.is_empty].reset_index(drop=True)
        except Exception:
            return gdf
