# -*- coding: utf-8 -*-
"""
================================================================================
[分类二 - 子模块 2.1] 坐标系识别、偏移纠偏与动态投影校准器 `crs_calibrator.py`
================================================================================
地图学问题诊断：
1. 原系统 `data_source_adapter.py` 将高德 API / DataV (GCJ-02 火星坐标) 与 OSM / SRTM DEM (WGS-84)
   直接叠加，在中国境内产生 300~500 米的非线性系统偏移，导致道路穿湖、行政边界与底图错位。
2. 原系统仅支持 Web Mercator (EPSG:3857) 渲染，中高纬度面积与长度变形显著，且缺失对中国标准
   CGCS2000 (EPSG:4490) 及高斯-克吕格 3° 分带平面坐标系的自动推算与重投影支持。
"""

import math
from typing import Tuple, Optional
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon
from shapely.ops import transform as shapely_transform
from ..models_and_specs import CoordSystemType

# 克拉索夫斯基椭球参数 (GCJ-02 加密算法基准)
_A = 6378245.0
_EE = 0.00669342162296594323
_X_PI = math.pi * 3000.0 / 180.0


def _out_of_china(lon: float, lat: float) -> bool:
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84_coord(lon: float, lat: float) -> Tuple[float, float]:
    """将单点 GCJ-02 (火星坐标) 精确逆向纠偏为 WGS-84 / CGCS2000 坐标"""
    if _out_of_china(lon, lat):
        return lon, lat
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    mglat = lat + dlat
    mglon = lon + dlon
    return lon * 2 - mglon, lat * 2 - mglat


def bd09_to_wgs84_coord(bd_lon: float, bd_lat: float) -> Tuple[float, float]:
    """将单点 BD-09 (百度坐标) 转换为 WGS-84 / CGCS2000 坐标"""
    x = bd_lon - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    gcj_lon = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)
    return gcj02_to_wgs84_coord(gcj_lon, gcj_lat)


class CRSCalibrator:
    """
    空间要素坐标系与地图投影校准器
    支持点、线、面 Shapefile (`.shp`) 或 GeoDataFrame 的坐标系统一校准与高斯-克吕格分带重投影。
    """

    @staticmethod
    def infer_cgcs2000_gauss_kruger_epsg(center_lon: float) -> int:
        """
        根据制图区域中心经度，自动推算中国国家标准 CGCS2000 3°分带高斯-克吕格投影 EPSG 编码。
        例如：武汉市中心经度约 114.3°E -> 3°带第 38 带 (中央经线 114°E) -> EPSG:4547。
        """
        zone_3deg = int(round(center_lon / 3.0))
        # CGCS2000 / 3-degree Gauss-Kruger CM 75E (zone 25) ~ CM 135E (zone 45) 对应 EPSG:4534 ~ 4554
        if 25 <= zone_3deg <= 45:
            return 4509 + zone_3deg  # zone 38 -> 4509 + 38 = 4547
        return 3857

    @classmethod
    def calibrate_geodataframe(
        cls,
        gdf: gpd.GeoDataFrame,
        source_coord_type: CoordSystemType = CoordSystemType.WGS84,
        target_epsg: Optional[int] = 4326,
    ) -> gpd.GeoDataFrame:
        """
        对输入的点/线/面 GeoDataFrame 进行坐标系缺失补全、GCJ02/BD09 非线性纠偏与目标投影转换。
        """
        if gdf is None or gdf.empty:
            return gdf

        calibrated = gdf.copy()

        # 1. 若 SHP 文件缺失 .prj 投影信息，根据坐标值范围智能判定是经纬度还是平面坐标
        if calibrated.crs is None:
            bounds = calibrated.total_bounds  # minx, miny, maxx, maxy
            if abs(bounds[0]) <= 180 and abs(bounds[2]) <= 180 and abs(bounds[1]) <= 90 and abs(bounds[3]) <= 90:
                calibrated = calibrated.set_crs(epsg=4326, allow_override=True)
            else:
                # 默认假定为武汉所在 CGCS2000 3度带 114E (EPSG:4547) 或 Web Mercator (EPSG:3857)
                if bounds[0] > 10000000:
                    calibrated = calibrated.set_crs(epsg=3857, allow_override=True)
                else:
                    calibrated = calibrated.set_crs(epsg=4547, allow_override=True)

        # 2. 若源数据为 GCJ-02 (高德/DataV) 或 BD-09 (百度)，先在经纬度空间执行非线性逆向纠偏
        if source_coord_type in (CoordSystemType.GCJ02, CoordSystemType.BD09):
            if calibrated.crs.to_epsg() != 4326:
                calibrated = calibrated.to_crs(epsg=4326)

            func = gcj02_to_wgs84_coord if source_coord_type == CoordSystemType.GCJ02 else bd09_to_wgs84_coord

            def _rectify_geom(geom):
                if geom is None or geom.is_empty:
                    return geom
                return shapely_transform(lambda x, y, z=None: func(x, y), geom)

            calibrated["geometry"] = calibrated["geometry"].apply(_rectify_geom)

        # 3. 转换至统一的目标坐标系（如 EPSG:4326 地理坐标或 EPSG:4547 高斯平面坐标）
        if target_epsg is not None and calibrated.crs.to_epsg() != target_epsg:
            calibrated = calibrated.to_crs(epsg=target_epsg)

        return calibrated
