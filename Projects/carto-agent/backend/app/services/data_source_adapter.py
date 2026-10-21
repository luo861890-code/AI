"""多源数据融合适配器 - DataSourceAdapter 统一接口

实现"知识-数据-工具"三元体系中"数据层"的多源接入能力。
支持 OSM、高德地图、天地图等多种数据源，通过统一适配器接口调用。

核心设计理念：
    1. 统一接口：所有数据源通过 DataSourceAdapter 抽象基类接入，
       对外暴露一致的 fetch(query) -> DataResult 接口。
    2. 智能路由：DataSourceRegistry 根据查询类型自动选择最优数据源，
       支持指定优先源和多源融合。
    3. 质量评分：每个数据源返回 DataResult 时附带 quality_score，
       用于多源融合时的优先级和可信度判断。
    4. 优雅降级：任意数据源不可用时自动跳过，返回空结果 + warning，
       不影响其他数据源的正常工作。

架构示意：
    MapService / Agent
         |
    DataSourceRegistry  (智能路由 + 多源融合)
         |
    +----+----+----+----+
    |    |    |    |    |
   OSM  Amap TDT  LocalFile ...
"""

import json
import os
import time
import warnings
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

import requests

from app.core.config import settings
from app.core.constants import CITY_BBOX

# ============================================================================
# 统一数据对象
# ============================================================================


@dataclass
class DataQuery:
    """统一数据查询对象

    表示一次跨数据源的通用地理数据查询，与具体数据源解耦。

    Attributes:
        data_type: OSM tag 或自定义类型标识，如 "highway"、"amenity"、"poi"
        bbox: 边界框 [min_lng, min_lat, max_lng, max_lat]（注意经纬度顺序与 OSM 不同）
        limit: 返回数据量上限，默认 1000
        filters: 额外筛选条件，如 {"amenity": "restaurant"}、{"highway": "primary"}
        region: 预定义区域名称（如"武汉市"），优先级低于 bbox
        zoom: 缩放级别，用于制图综合（影响要素等级选取）
    """
    data_type: str
    bbox: List[float] = field(default_factory=list)   # [min_lng, min_lat, max_lng, max_lat]
    limit: int = 1000
    filters: Optional[Dict[str, Any]] = None
    region: Optional[str] = None
    zoom: int = 12

    def __post_init__(self):
        if self.filters is None:
            self.filters = {}

    @property
    def bbox_osm(self) -> Dict[str, float]:
        """转换为 OSM 使用的 bbox 格式 {min_lat, min_lon, max_lat, max_lon}"""
        if len(self.bbox) == 4:
            return {
                "min_lat": self.bbox[1],
                "min_lon": self.bbox[0],
                "max_lat": self.bbox[3],
                "max_lon": self.bbox[2],
            }
        return {}

    @classmethod
    def from_region(cls, data_type: str, region: str,
                    limit: int = 1000, filters: Optional[Dict] = None,
                    zoom: int = 12) -> "DataQuery":
        """从预定义区域名称创建查询（自动填充 bbox）"""
        bbox_info = CITY_BBOX.get(region, {})
        if bbox_info:
            bbox = [bbox_info["min_lon"], bbox_info["min_lat"],
                    bbox_info["max_lon"], bbox_info["max_lat"]]
        else:
            bbox = []
        return cls(data_type=data_type, bbox=bbox, limit=limit,
                   filters=filters, region=region, zoom=zoom)


@dataclass
class DataResult:
    """统一数据返回对象

    所有数据源的返回结果统一为此格式，包含 GeoJSON FeatureCollection。

    Attributes:
        source: 数据源名称（如 "osm"、"amap"、"tianditu"、"local_file"）
        features: GeoJSON Feature 列表，每个 Feature 包含 type/geometry/properties
        metadata: 元数据字典，包含数据量、时效、精度、版权等信息
        quality_score: 数据质量评分 0-1，用于多源融合排序
        warnings: 获取过程中的警告信息列表
    """
    source: str
    features: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 1.0
    warnings: List[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        """要素数量"""
        return len(self.features)

    @property
    def geojson(self) -> Dict[str, Any]:
        """转换为 GeoJSON FeatureCollection"""
        return {
            "type": "FeatureCollection",
            "features": self.features,
            "metadata": self.metadata,
            "source": self.source,
            "quality_score": self.quality_score,
        }

    def __bool__(self) -> bool:
        """是否有数据"""
        return self.count > 0

    @classmethod
    def empty(cls, source: str, reason: str = "no data") -> "DataResult":
        """创建空结果（用于优雅降级）"""
        return cls(
            source=source,
            features=[],
            metadata={"empty_reason": reason},
            quality_score=0.0,
            warnings=[reason],
        )


# ============================================================================
# 数据源适配器抽象基类
# ============================================================================


class DataSourceAdapter(ABC):
    """数据源适配器抽象基类

    子类必须实现 fetch()、supports() 和 source_name 属性。
    所有子类的 fetch() 必须返回 DataResult 对象。

    设计约束：
        - fetch() 不应抛出异常：内部错误通过 DataResult.warnings 报告
        - supports() 仅根据 DataQuery 类型字段判断，不发起网络请求
        - source_name 全局唯一，用于 DataSourceRegistry 去重
    """

    @abstractmethod
    def fetch(self, query: DataQuery) -> DataResult:
        """从数据源获取数据

        Args:
            query: 统一查询对象

        Returns:
            DataResult: 统一返回对象，包含 GeoJSON Feature 列表和元数据。
            无数据或出错时返回空的 DataResult（features=[]）。
        """
        ...

    @abstractmethod
    def supports(self, query: DataQuery) -> bool:
        """检查是否支持该查询类型

        仅根据查询的 data_type 等静态字段判断，不发起网络请求。

        Args:
            query: 统一查询对象

        Returns:
            bool: 是否支持该查询
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称（全局唯一标识）"""
        ...

    # ---- 工具方法：供子类复用 ----

    @staticmethod
    def _make_feature(
        geom_type: str,
        coordinates: Any,
        properties: Optional[Dict] = None,
        feature_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建标准 GeoJSON Feature

        Args:
            geom_type: 几何类型 ("Point", "LineString", "Polygon", "MultiPolygon")
            coordinates: GeoJSON 坐标（注意 GeoJSON 规范：[lng, lat]）
            properties: 属性字典
            feature_id: 可选要素 ID

        Returns:
            标准 GeoJSON Feature 字典
        """
        feat: Dict[str, Any] = {
            "type": "Feature",
            "geometry": {
                "type": geom_type,
                "coordinates": coordinates,
            },
            "properties": properties or {},
        }
        if feature_id:
            feat["id"] = feature_id
        return feat

    @staticmethod
    def _safe_get(obj: Dict, *keys, default=None):
        """安全获取嵌套字典值"""
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key, {})
            else:
                return default
        return obj if obj != {} else default


# ============================================================================
# OSM 数据源适配器
# ============================================================================


class OSMSourceAdapter(DataSourceAdapter):
    """OSM 数据源适配器

    封装现有的 OSMService 为统一适配器接口。
    OSM 是全球最大的开放地理数据项目，在道路、水系、建筑等基础地理要素方面
    覆盖面最广、数据最丰富，质量评分 = 1.0。

    支持的数据类型：所有 OSM tag（highway, railway, waterway, building,
    amenity, tourism, natural, landuse, leisure, boundary, place 等）。
    """

    # 支持的所有 OSM 标签类型
    SUPPORTED_TYPES: Tuple[str, ...] = (
        "highway", "railway", "waterway", "building", "amenity",
        "shop", "tourism", "historic", "natural", "landuse",
        "leisure", "boundary", "place", "office", "aeroway",
        "power", "man_made", "barrier", "route",
    )

    # OSM 数据质量评分说明：
    # 1.0 = 数据来源权威、覆盖面广、全球标准化，作为多源融合的基准
    QUALITY_SCORE = 1.0

    def __init__(self, osm_service=None):
        """
        Args:
            osm_service: OSMService 实例，为 None 时延迟导入
        """
        self._osm_service = osm_service

    @property
    def osm_service(self):
        """延迟获取 OSMService 实例"""
        if self._osm_service is None:
            from app.services.osm_service import OSMService
            self._osm_service = OSMService()
        return self._osm_service

    @property
    def source_name(self) -> str:
        return "osm"

    def supports(self, query: DataQuery) -> bool:
        """OSM 支持所有常见地理标签类型的查询"""
        base_type = query.data_type.split("~")[0]
        return base_type in self.SUPPORTED_TYPES

    def fetch(self, query: DataQuery) -> DataResult:
        """通过 OSMService 获取数据，转换为 GeoJSON FeatureCollection

        流程：
        1. 确定查询区域（优先 bbox，其次 region）
        2. 调用 OSMService.fetch_elements() 或 fetch_by_region()
        3. 将 OSM 元素转换为 GeoJSON Feature 列表
        4. 返回 DataResult
        """
        warnings_list = []
        try:
            data_type = query.data_type

            # 确定查询方式：优先 bbox，其次 region
            if query.bbox and len(query.bbox) == 4:
                # 直接 bbox 查询
                osm_data = self.osm_service.fetch_elements(
                    bbox=query.bbox_osm,
                    element_types=[data_type],
                )
            elif query.region:
                # 按区域查询（带缓存）
                osm_data = self.osm_service.fetch_by_region(
                    region=query.region,
                    element_types=[data_type],
                )
            else:
                return DataResult.empty(self.source_name, "no bbox or region specified")

            # 转换 OSM 元素为 GeoJSON Feature
            features = []
            base_tag = data_type.split("~")[0]
            elements = osm_data.get(base_tag, [])

            for elem in elements:
                feat = self._osm_element_to_feature(elem, base_tag)
                if feat:
                    features.append(feat)

            if query.limit and len(features) > query.limit:
                features = features[:query.limit]

            return DataResult(
                source=self.source_name,
                features=features,
                metadata={
                    "total_available": len(elements),
                    "returned": len(features),
                    "query_type": data_type,
                    "region": query.region,
                    "data_source": "OpenStreetMap via Overpass API",
                    "license": "ODbL 1.0",
                    "attribution": "OpenStreetMap contributors",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                quality_score=self.QUALITY_SCORE,
                warnings=warnings_list,
            )

        except Exception as e:
            error_msg = f"OSM data fetch failed: {e}"
            warnings_list.append(error_msg)
            print(f"[OSMSourceAdapter] {error_msg}")
            return DataResult.empty(self.source_name, error_msg)

    def _osm_element_to_feature(self, elem: Dict, base_tag: str) -> Optional[Dict]:
        """将单个 OSM 元素转换为 GeoJSON Feature

        Args:
            elem: OSM 元素（node/way/relation）
            base_tag: 要素基础类型标签

        Returns:
            GeoJSON Feature 或 None（坐标无效时）
        """
        tags = elem.get("tags", {}) or {}
        elem_type = elem.get("type", "")

        # 处理 node 类型
        if elem_type == "node":
            lat = elem.get("lat")
            lon = elem.get("lon")
            if lat is None or lon is None:
                return None
            return self._make_feature(
                geom_type="Point",
                coordinates=[lon, lat],  # GeoJSON: [lng, lat]
                properties={
                    **tags,
                    "osm_id": elem.get("id"),
                    "osm_type": "node",
                    "base_tag": base_tag,
                },
                feature_id=str(elem.get("id", "")),
            )

        # 处理 way 类型
        geometry = elem.get("geometry") or []
        if len(geometry) < 2:
            return None

        coords = [[pt["lon"], pt["lat"]] for pt in geometry
                  if "lat" in pt and "lon" in pt]

        if len(coords) < 2:
            return None

        # 判断几何类型：闭合线为 Polygon，开放线为 LineString
        is_closed = (coords[0][0] == coords[-1][0] and
                     coords[0][1] == coords[-1][1])

        geom_type = "Polygon" if is_closed and len(coords) >= 4 else "LineString"

        return self._make_feature(
            geom_type=geom_type,
            coordinates=[coords] if geom_type == "Polygon" else coords,
            properties={
                **tags,
                "osm_id": elem.get("id"),
                "osm_type": elem_type,
                "base_tag": base_tag,
            },
            feature_id=str(elem.get("id", "")),
        )


# ============================================================================
# 高德 POI 适配器
# ============================================================================


class AmapPOIAdapter(DataSourceAdapter):
    """高德地图 POI 搜索适配器

    用于补充 OSM 中缺失的中文 POI 数据。高德在中文 POI 方面显著优于 OSM，
    尤其在餐饮、购物、生活服务等分类上覆盖面更广、更新更及时。

    API: https://restapi.amap.com/v3/place/text
    需要 API Key（从环境变量 AMAP_KEY 读取，未配置时自动禁用）

    支持的数据类型：
        - poi: 通用 POI 搜索
        - poi/restaurant, poi/hotel, poi/hospital 等分类 POI
        - geocode: 地理编码

    数据质量评分：0.85
        加分项：中文 POI 数据丰富、更新及时、分类细致
        扣分项：不开源、需 API Key、有调用限额、非全球覆盖
    """

    BASE_URL = "https://restapi.amap.com/v3/place"
    QUALITY_SCORE = 0.85

    # 高德 POI 分类编码映射 (部分常用分类)
    # 参考：https://lbs.amap.com/api/webservice/download
    AMAP_TYPE_MAP: Dict[str, str] = {
        "restaurant": "050000",    # 餐饮服务
        "cafe": "050300",          # 咖啡厅
        "fast_food": "050200",     # 快餐
        "hotel": "100000",         # 住宿服务
        "attraction": "110000",    # 风景名胜
        "museum": "140400",        # 博物馆
        "shopping": "060000",      # 购物服务
        "mall": "060100",          # 商场
        "supermarket": "060200",   # 超市
        "hospital": "090100",      # 综合医院
        "school": "141200",        # 学校
        "university": "141201",    # 高等院校
        "bank": "160100",          # 银行
        "parking": "150900",       # 停车场
        "fuel": "010700",          # 加油站
        "transport": "150000",     # 交通设施
        "subway": "150500",        # 地铁站
        "bus": "150600",           # 公交站
        "sports": "080000",        # 体育休闲
        "government": "130000",    # 政府机构
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: 高德 API Key，为 None 时从环境变量 AMAP_KEY 读取
        """
        self.api_key = api_key or os.getenv("AMAP_KEY") or os.getenv("AMAP_API_KEY") or ""
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CartoAgent/1.0 (Map Cartography Agent)",
        })
        if not self.api_key:
            print("[AmapPOIAdapter] 未配置 AMAP_KEY 环境变量，"
                  "高德 POI 适配器将自动跳过（在 .env 中设置 AMAP_KEY 后启用）")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def source_name(self) -> str:
        return "amap"

    def supports(self, query: DataQuery) -> bool:
        """支持 POI 类型查询（需要 API Key 且非空）"""
        if not self.enabled:
            return False
        dt = query.data_type
        return dt == "poi" or dt.startswith("poi/") or dt == "geocode"

    def fetch(self, query: DataQuery) -> DataResult:
        """调用高德 POI 搜索 API 获取数据

        流程：
        1. 解析 data_type 提取 POI 分类
        2. 确定搜索关键词和区域
        3. 批量分页调用高德 API
        4. 转换响应为 GeoJSON FeatureCollection

        Args:
            query: 统一查询对象，data_type 如 "poi/restaurant" 或 "poi"

        Returns:
            DataResult: 统一返回对象
        """
        if not self.enabled:
            return DataResult.empty(
                self.source_name,
                "AMAP_KEY not configured; set AMAP_KEY in .env to enable Amap POI adapter"
            )

        warnings_list = []
        try:
            # 解析搜索关键词
            keywords = self._resolve_keywords(query)
            if not keywords:
                return DataResult.empty(self.source_name, "no keywords resolved from query")

            # 确定搜索区域
            city = query.region or ""
            if not city and query.bbox:
                city = self._reverse_geocode_city(query.bbox)

            # 批量搜索
            all_pois = []
            for kw in keywords[:5]:  # 最多搜索 5 个关键词
                pois = self._search_pois(
                    keywords=kw,
                    city=city,
                    offset=min(query.limit // len(keywords[:5]), 50),
                )
                all_pois.extend(pois)

            # 去重（按坐标 + 名称）
            seen = set()
            unique = []
            for poi in all_pois:
                loc = poi.get("location", "")
                name = poi.get("name", "")
                key = (loc, name)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(poi)

            if query.limit and len(unique) > query.limit:
                unique = unique[:query.limit]

            # 转换为 GeoJSON Feature
            features = [self._poi_to_feature(p) for p in unique]
            features = [f for f in features if f]  # 过滤无效坐标

            return DataResult(
                source=self.source_name,
                features=features,
                metadata={
                    "total_available": len(unique),
                    "returned": len(features),
                    "query_keywords": keywords[:5],
                    "city": city,
                    "data_source": "高德地图 POI 搜索 API",
                    "license": "高德地图服务协议",
                    "attribution": "高德地图 AutoNavi",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                quality_score=self.QUALITY_SCORE,
                warnings=warnings_list,
            )

        except Exception as e:
            error_msg = f"Amap POI fetch failed: {e}"
            print(f"[AmapPOIAdapter] {error_msg}")
            warnings_list.append(error_msg)
            return DataResult.empty(self.source_name, error_msg)

    def _resolve_keywords(self, query: DataQuery) -> List[str]:
        """从查询中解析高德搜索关键词

        支持格式：
            - "poi" -> 通用搜索关键词
            - "poi/restaurant" -> ["餐厅", "餐馆"]
            - "poi/hotel" -> ["酒店", "宾馆"]
        """
        dt = query.data_type
        if dt == "poi":
            # 默认搜索生活服务类 POI
            return ["餐厅", "商场", "医院", "学校", "景点"]

        if dt.startswith("poi/"):
            category = dt.split("/", 1)[1]

            # 直接匹配高德分类关键词映射
            keyword_map = {
                "restaurant": ["餐厅", "餐馆", "火锅", "面馆", "小吃"],
                "cafe": ["咖啡", "茶馆"],
                "fast_food": ["快餐", "汉堡"],
                "hotel": ["酒店", "宾馆", "旅馆"],
                "attraction": ["景点", "景区", "公园"],
                "museum": ["博物馆", "展览馆"],
                "shopping": ["商场", "购物中心"],
                "mall": ["商场", "百货"],
                "supermarket": ["超市", "便利店"],
                "hospital": ["医院", "诊所"],
                "school": ["学校", "中学", "小学"],
                "university": ["大学", "学院"],
                "bank": ["银行", "ATM"],
                "parking": ["停车场"],
                "fuel": ["加油站"],
                "transport": ["火车站", "汽车站"],
                "subway": ["地铁站"],
                "bus": ["公交站"],
                "sports": ["体育馆", "运动场"],
                "government": ["政府", "政务中心"],
                "pharmacy": ["药店"],
                "theatre": ["电影院"],
                "police": ["派出所", "公安局"],
                "post": ["邮局"],
            }
            return keyword_map.get(category, [category])

        # 关键词模式查询
        if query.filters and "keywords" in query.filters:
            kw = query.filters["keywords"]
            return [kw] if isinstance(kw, str) else kw

        return [dt]

    def _search_pois(self, keywords: str, city: str, offset: int = 25) -> List[Dict]:
        """调用高德 POI 文本搜索 API

        Args:
            keywords: 搜索关键词
            city: 城市名称（中文，如"武汉"）
            offset: 每页返回数量

        Returns:
            POI 字典列表
        """
        try:
            resp = self._session.get(
                self.BASE_URL + "/text",
                params={
                    "key": self.api_key,
                    "keywords": keywords,
                    "city": city,
                    "offset": offset,
                    "page": 1,
                    "extensions": "base",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if str(data.get("status")) != "1":
                return []

            return data.get("pois") or []

        except requests.exceptions.RequestException as e:
            print(f"[AmapPOIAdapter] 关键词[{keywords}]请求失败: {e}")
            return []
        except Exception as e:
            print(f"[AmapPOIAdapter] 关键词[{keywords}]解析失败: {e}")
            return []

    def _reverse_geocode_city(self, bbox: List[float]) -> str:
        """通过 bbox 中心点反向地理编码获取城市名

        简单实现：通过 CITY_BBOX 反向匹配，精度要求不高时够用。
        """
        if len(bbox) != 4:
            return ""
        center_lng = (bbox[0] + bbox[2]) / 2
        center_lat = (bbox[1] + bbox[3]) / 2
        for city, info in CITY_BBOX.items():
            if (info["min_lat"] <= center_lat <= info["max_lat"] and
                    info["min_lon"] <= center_lng <= info["max_lon"]):
                return city
        return ""

    def _poi_to_feature(self, poi: Dict) -> Optional[Dict]:
        """将高德 POI 转换为 GeoJSON Feature

        Args:
            poi: 高德 POI 字典（含 name/location/address/type 等字段）

        Returns:
            GeoJSON Feature 或 None（坐标无效时）
        """
        loc = (poi.get("location") or "").split(",")
        if len(loc) != 2:
            return None
        try:
            lng, lat = float(loc[0]), float(loc[1])
        except (ValueError, TypeError):
            return None

        return self._make_feature(
            geom_type="Point",
            coordinates=[lng, lat],
            properties={
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "amap_type": poi.get("type", ""),
                "amap_typecode": poi.get("typecode", ""),
                "category": poi.get("type", "").split(";")[0] if poi.get("type") else "",
                "source": "amap",
                "poi_id": poi.get("id", ""),
            },
            feature_id=poi.get("id", ""),
        )


# ============================================================================
# 天地图瓦片服务适配器
# ============================================================================


class TiandituTileAdapter(DataSourceAdapter):
    """天地图瓦片服务适配器

    用于获取带中文标注的底图瓦片和矢量要素服务。
    天地图是中国国家地理信息公共服务平台，提供权威的中国基础地理数据。

    WMTS 服务: https://t{s}.tianditu.gov.cn/
    需要 API Key（默认使用项目配置中的天地图 token）

    支持的数据类型：
        - "vec": 矢量底图要素（道路、水系、居民地、境界等）
        - "cva": 矢量注记（中文地名标注）
        - "img": 影像底图
        - "cia": 影像注记

    数据质量评分：0.80
        加分项：国家官方数据、中国区域精度高、中文标注完整
        扣分项：仅限中国区域、需 token、数据更新较慢、细节不如 OSM 丰富
    """

    BASE_URL = "https://t0.tianditu.gov.cn"
    QUALITY_SCORE = 0.80

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: 天地图 API Key，为 None 时从环境变量 TIANDITU_KEY 读取，
                     再为 None 时使用默认项目 token
        """
        self.api_key = api_key or os.getenv(
            "TIANDITU_KEY",
            "a3bb2eed53ecf1d9a3c852f0ab4d27de"
        )
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CartoAgent/1.0 (Map Cartography Agent)",
        })

    @property
    def source_name(self) -> str:
        return "tianditu"

    def supports(self, query: DataQuery) -> bool:
        """支持中国区域的矢量底图要素查询"""
        dt = query.data_type
        supported = ("vec", "cva", "img", "cia", "tianditu")
        if dt in supported:
            return True
        # 也支持带前缀的查询，如 "tianditu/vec"
        if dt.startswith("tianditu/"):
            return True
        return False

    def fetch(self, query: DataQuery) -> DataResult:
        """从天地图 WMTS 获取矢量要素

        当前实现返回可用的瓦片服务 URL 作为元数据，供前端直接使用。
        后续可扩展为实际抓取 WMTS 矢量要素数据（TileJSON 格式）。

        Args:
            query: 统一查询对象

        Returns:
            DataResult: 包含瓦片服务元数据和可用的瓦片 URL
        """
        warnings_list = []
        try:
            # 确定请求的图层类型
            dt = query.data_type
            if dt.startswith("tianditu/"):
                layer_type = dt.split("/", 1)[1]
            else:
                layer_type = dt

            # 天地图支持的图层类型
            layer_configs = {
                "vec": {
                    "name": "矢量底图",
                    "url_template": (
                        "https://t{s}.tianditu.gov.cn/DataServer"
                        "?T=vec_w&x={x}&y={y}&l={z}&tk={key}"
                    ),
                },
                "cva": {
                    "name": "矢量注记",
                    "url_template": (
                        "https://t{s}.tianditu.gov.cn/DataServer"
                        "?T=cva_w&x={x}&y={y}&l={z}&tk={key}"
                    ),
                },
                "img": {
                    "name": "影像底图",
                    "url_template": (
                        "https://t{s}.tianditu.gov.cn/DataServer"
                        "?T=img_w&x={x}&y={y}&l={z}&tk={key}"
                    ),
                },
                "cia": {
                    "name": "影像注记",
                    "url_template": (
                        "https://t{s}.tianditu.gov.cn/DataServer"
                        "?T=cia_w&x={x}&y={y}&l={z}&tk={key}"
                    ),
                },
            }

            config = layer_configs.get(layer_type)
            if not config:
                return DataResult.empty(
                    self.source_name,
                    f"unsupported layer type: {layer_type}"
                )

            # 生成瓦片服务 URL（供前端直接加载）
            tile_url = config["url_template"].replace("{key}", self.api_key)

            # 构建 GeoJSON Feature（天地图当前返回瓦片服务元数据）
            features = []
            if query.bbox and len(query.bbox) == 4:
                # 添加 bbox 多边形作为参考区域
                bbox = query.bbox
                features.append(self._make_feature(
                    geom_type="Polygon",
                    coordinates=[[
                        [bbox[0], bbox[1]],
                        [bbox[2], bbox[1]],
                        [bbox[2], bbox[3]],
                        [bbox[0], bbox[3]],
                        [bbox[0], bbox[1]],
                    ]],
                    properties={
                        "name": f"天地图{config['name']}覆盖区域",
                        "layer_type": layer_type,
                        "source": "tianditu",
                    },
                ))

            # 添加瓦片 URL 标记
            features.append(self._make_feature(
                geom_type="Point",
                coordinates=[114.3055, 30.5928] if query.region == "武汉市"
                           else [116.4074, 39.9042],
                properties={
                    "name": f"天地图{config['name']}服务",
                    "tile_url_template": tile_url,
                    "layer_type": layer_type,
                    "service_type": "WMTS",
                    "source": "tianditu",
                    "attribution": "天地图 Tianditu",
                    "is_service_marker": True,
                },
            ))

            return DataResult(
                source=self.source_name,
                features=features,
                metadata={
                    "layer_type": layer_type,
                    "layer_name": config["name"],
                    "tile_url_template": tile_url,
                    "service_type": "WMTS",
                    "data_source": "天地图 国家地理信息公共服务平台",
                    "license": "天地图服务协议",
                    "attribution": "Tianditu 天地图",
                    "coverage": "China mainland",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                quality_score=self.QUALITY_SCORE,
                warnings=warnings_list,
            )

        except Exception as e:
            error_msg = f"Tianditu fetch failed: {e}"
            print(f"[TiandituTileAdapter] {error_msg}")
            warnings_list.append(error_msg)
            return DataResult.empty(self.source_name, error_msg)

    def get_tile_url(self, layer_type: str = "vec", subdomain: int = 0) -> str:
        """获取天地图瓦片 URL 模板

        Args:
            layer_type: 图层类型 (vec/cva/img/cia)
            subdomain: 子域名编号 (0-7)

        Returns:
            瓦片 URL 模板字符串
        """
        s = str(subdomain) if subdomain < 8 else "0"
        url = f"https://t{s}.tianditu.gov.cn/DataServer"
        url += f"?T={layer_type}_w&x={{x}}&y={{y}}&l={{z}}&tk={self.api_key}"
        return url


# ============================================================================
# 本地文件适配器
# ============================================================================


class LocalFileAdapter(DataSourceAdapter):
    """本地文件适配器

    从 backend/data/geo/ 目录读取预处理的 GeoJSON/CSV 文件。
    用于加载高精度本地地理数据（如武汉精确水系、道路数据），
    这些数据通常由 GIS 专业处理得到，精度优于 OSM。

    支持的文件格式：
        - GeoJSON (.geojson)
        - CSV (.csv) - 含 lat/lng 列的 POI 数据

    数据质量评分：0.70
        加分项：预校验数据、无网络依赖、加载速度快
        扣分项：静态数据、覆盖范围有限、更新需手动操作
    """

    QUALITY_SCORE = 0.70
    _DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "data", "geo")

    def __init__(self, data_dir: Optional[str] = None):
        """
        Args:
            data_dir: 本地数据目录路径，默认 backend/data/geo/
        """
        self.data_dir = data_dir or self._DATA_DIR
        if not os.path.isdir(self.data_dir):
            print(f"[LocalFileAdapter] 数据目录不存在: {self.data_dir}"
                  f"（将在首次查询时创建）")

    @property
    def source_name(self) -> str:
        return "local_file"

    def supports(self, query: DataQuery) -> bool:
        """支持查询本地文件中存在的要素类型"""
        if not os.path.isdir(self.data_dir):
            return False
        dt = query.data_type
        # 检查是否有匹配的本地文件
        return self._find_matching_files(dt) != []

    def fetch(self, query: DataQuery) -> DataResult:
        """从本地文件加载数据

        流程：
        1. 扫描 data/geo/ 目录找到匹配的文件
        2. 按文件类型解析（GeoJSON/CSV）
        3. 用 bbox 筛选要素
        4. 返回 DataResult

        Args:
            query: 统一查询对象

        Returns:
            DataResult: 包含本地文件中的地理要素
        """
        warnings_list = []
        try:
            if not os.path.isdir(self.data_dir):
                return DataResult.empty(
                    self.source_name,
                    f"data directory not found: {self.data_dir}"
                )

            matching_files = self._find_matching_files(query.data_type)
            if not matching_files:
                return DataResult.empty(
                    self.source_name,
                    f"no local file found for type: {query.data_type}"
                )

            all_features = []
            total_loaded = 0

            for filepath in matching_files:
                try:
                    features = self._load_file(filepath)
                    total_loaded += len(features)

                    # bbox 筛选
                    if query.bbox and len(query.bbox) == 4:
                        features = self._filter_by_bbox(
                            features,
                            query.bbox[0], query.bbox[1],
                            query.bbox[2], query.bbox[3],
                        )

                    all_features.extend(features)

                except Exception as e:
                    fname = os.path.basename(filepath)
                    warnings_list.append(f"failed to load {fname}: {e}")
                    print(f"[LocalFileAdapter] 加载 {fname} 失败: {e}")

            if query.limit and len(all_features) > query.limit:
                all_features = all_features[:query.limit]

            return DataResult(
                source=self.source_name,
                features=all_features,
                metadata={
                    "total_loaded": total_loaded,
                    "returned": len(all_features),
                    "files_used": [os.path.basename(f) for f in matching_files],
                    "data_dir": self.data_dir,
                    "data_source": "本地预处理地理数据",
                    "license": "项目内部数据",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                quality_score=self.QUALITY_SCORE,
                warnings=warnings_list if warnings_list else [],
            )

        except Exception as e:
            error_msg = f"Local file fetch failed: {e}"
            print(f"[LocalFileAdapter] {error_msg}")
            return DataResult.empty(self.source_name, error_msg)

    def _find_matching_files(self, data_type: str) -> List[str]:
        """根据 data_type 查找匹配的本地文件

        匹配规则：
            - "highway" 匹配 *_road*.geojson, *_highway*.geojson
            - "waterway" 匹配 *_water*.geojson, *_river*.geojson
            - "natural"  匹配 *_water*.geojson, *_lake*.geojson
            - "poi"      匹配 *_poi*.geojson
            - "*"        匹配所有文件（全量匹配）
        """
        if not os.path.isdir(self.data_dir):
            return []

        all_files = []
        for fname in os.listdir(self.data_dir):
            fpath = os.path.join(self.data_dir, fname)
            if not os.path.isfile(fpath):
                continue
            if not (fname.endswith(".geojson") or fname.endswith(".csv")):
                continue
            all_files.append(fpath)

        if not all_files:
            return []

        # 类型匹配映射
        type_patterns = {
            "highway": ["road", "highway", "street"],
            "highway_major": ["road", "highway", "street"],
            "highway_minor": ["road", "highway", "street"],
            "waterway": ["water", "river", "stream", "lake"],
            "waterway_major": ["water", "river", "lake"],
            "waterway_minor": ["water", "river", "stream"],
            "natural": ["water", "lake", "forest", "grass"],
            "building": ["building", "house"],
            "poi": ["poi", "landmark", "amenity"],
            "railway": ["railway", "rail", "subway", "metro"],
        }

        dt = data_type.split("~")[0]
        patterns = type_patterns.get(dt, [dt])

        matching = []
        for fpath in all_files:
            fname_lower = os.path.basename(fpath).lower()
            if any(p in fname_lower for p in patterns):
                matching.append(fpath)

        return matching if matching else all_files  # 无精确匹配时返回全部

    @staticmethod
    def _load_file(filepath: str) -> List[Dict]:
        """加载单个 GeoJSON 或 CSV 文件，返回 Feature 列表

        Args:
            filepath: 文件路径

        Returns:
            GeoJSON Feature 列表
        """
        if filepath.endswith(".geojson"):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                return data.get("features", [])
            elif isinstance(data, dict) and data.get("type") == "Feature":
                return [data]
            elif isinstance(data, list):
                return data
            else:
                return []

        elif filepath.endswith(".csv"):
            import csv
            features = []
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        lat = float(row.get("lat", row.get("latitude", "0")))
                        lng = float(row.get("lng", row.get("lon", row.get("longitude", "0"))))
                    except (ValueError, TypeError):
                        continue

                    properties = {k: v for k, v in row.items()
                                  if k not in ("lat", "lng", "lon", "latitude", "longitude")}

                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lng, lat],
                        },
                        "properties": {
                            **properties,
                            "source": "local_csv",
                        },
                    })

            return features

        return []

    @staticmethod
    def _filter_by_bbox(features: List[Dict],
                        min_lng: float, min_lat: float,
                        max_lng: float, max_lat: float) -> List[Dict]:
        """用 bbox 筛选要素

        对于 Point 几何，检查坐标是否在 bbox 内。
        对于 LineString/Polygon 几何，检查是否与 bbox 有交集（简化：任意点在 bbox 内）。
        """
        filtered = []
        for feat in features:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []

            if geom.get("type") == "Point":
                lng, lat = coords[0], coords[1]
                if min_lng <= lng <= max_lng and min_lat <= lat <= max_lat:
                    filtered.append(feat)

            elif geom.get("type") == "LineString":
                if any(min_lng <= p[0] <= max_lng and min_lat <= p[1] <= max_lat
                       for p in coords):
                    filtered.append(feat)

            elif geom.get("type") == "Polygon":
                ring = coords[0] if coords else []
                if any(min_lng <= p[0] <= max_lng and min_lat <= p[1] <= max_lat
                       for p in ring):
                    filtered.append(feat)

            else:
                # 未知几何类型保留
                filtered.append(feat)

        return filtered


# ============================================================================
# 数据源注册中心
# ============================================================================


class DataSourceRegistry:
    """数据源注册中心

    管理所有已注册的数据源适配器，提供智能路由和多源融合能力。

    核心功能：
    1. 智能数据源选择：根据 query.data_type 自动选择最优数据源
    2. 多源融合获取：从多个数据源获取数据后合并去重
    3. 质量排序：按 quality_score 排序结果
    4. 优雅降级：任意数据源失败时自动跳过

    使用示例：
        registry = DataSourceRegistry()
        registry.register(OSMSourceAdapter(osm_service))
        registry.register(AmapPOIAdapter())
        registry.register(TiandituTileAdapter())

        # 单源优先查询
        result = registry.fetch(DataQuery(data_type="poi", region="武汉市"))

        # 多源融合查询
        results = registry.fetch_multi_source(DataQuery(data_type="poi", region="武汉市"))
    """

    def __init__(self):
        self.adapters: OrderedDict[str, DataSourceAdapter] = OrderedDict()

    def register(self, adapter: DataSourceAdapter) -> None:
        """注册数据源适配器

        同名适配器会覆盖之前的注册（以最后注册的为准）。

        Args:
            adapter: 数据源适配器实例
        """
        name = adapter.source_name
        if name in self.adapters:
            print(f"[DataSourceRegistry] 覆盖已注册的适配器: {name}")
        self.adapters[name] = adapter
        print(f"[DataSourceRegistry] 已注册数据源: {name} ({type(adapter).__name__})")

    def unregister(self, source_name: str) -> bool:
        """注销数据源适配器

        Args:
            source_name: 数据源名称

        Returns:
            bool: 是否成功注销
        """
        if source_name in self.adapters:
            del self.adapters[source_name]
            print(f"[DataSourceRegistry] 已注销数据源: {source_name}")
            return True
        return False

    def get_adapter(self, source_name: str) -> Optional[DataSourceAdapter]:
        """获取指定数据源适配器"""
        return self.adapters.get(source_name)

    def get_available_sources(self) -> List[str]:
        """获取所有已注册数据源名称列表"""
        return list(self.adapters.keys())

    def fetch(self, query: DataQuery,
              preferred_source: Optional[str] = None) -> DataResult:
        """智能获取数据

        选择策略（按优先级）：
        1. 指定 preferred_source 且该源支持查询 → 直接使用
        2. 遍历所有适配器，选择第一个支持该查询的
        3. 无适配器支持 → 返回空结果

        Args:
            query: 统一查询对象
            preferred_source: 优先使用的数据源名称（如 "osm"、"amap"）

        Returns:
            DataResult: 统一返回对象
        """
        # 策略 1：指定优先源
        if preferred_source:
            adapter = self.adapters.get(preferred_source)
            if adapter and adapter.supports(query):
                print(f"[DataSourceRegistry] 使用指定数据源: {preferred_source}"
                      f" 查询 {query.data_type}")
                return adapter.fetch(query)
            else:
                print(f"[DataSourceRegistry] 指定数据源 {preferred_source}"
                      f" 不可用或不支持 {query.data_type}，回退到自动选择")

        # 策略 2：自动选择第一个支持的适配器
        for name, adapter in self.adapters.items():
            if adapter.supports(query):
                print(f"[DataSourceRegistry] 自动选择数据源: {name}"
                      f" 查询 {query.data_type}")
                return adapter.fetch(query)

        # 策略 3：无适配器支持
        print(f"[DataSourceRegistry] 无适配器支持查询类型: {query.data_type}")
        return DataResult.empty(
            "none",
            f"no adapter supports query type: {query.data_type}"
        )

    def fetch_multi_source(self, query: DataQuery,
                           sources: Optional[List[str]] = None) -> List[DataResult]:
        """多源融合获取

        从所有支持查询的（或指定的）数据源同时获取数据，
        返回每个源的独立结果，由调用方决定融合策略。

        Args:
            query: 统一查询对象
            sources: 限定使用的数据源列表，为 None 时使用所有支持的适配器

        Returns:
            List[DataResult]: 按 quality_score 降序排列的结果列表
        """
        target_sources = sources or list(self.adapters.keys())
        results: List[DataResult] = []

        for name in target_sources:
            adapter = self.adapters.get(name)
            if adapter is None:
                print(f"[DataSourceRegistry] 忽略未知数据源: {name}")
                continue
            if not adapter.supports(query):
                print(f"[DataSourceRegistry] 数据源 {name} 不支持 {query.data_type}")
                continue

            print(f"[DataSourceRegistry] 多源获取: 从 {name} 查询 {query.data_type}")
            result = adapter.fetch(query)
            if result and result.features:
                results.append(result)
            else:
                print(f"[DataSourceRegistry] 数据源 {name} 返回空结果")

        # 按质量评分降序排列
        results.sort(key=lambda r: r.quality_score, reverse=True)
        return results

    def merge_results(self, results: List[DataResult],
                      dedup_threshold_meters: float = 50.0) -> DataResult:
        """合并多个数据源的结果为一个统一结果

        去重策略：
        1. 按 quality_score 降序处理各源结果（高分源优先）
        2. 对同名 + 相近坐标的要素进行去重
        3. 合并所有要素到单一 DataResult

        Args:
            results: 多数据源结果列表
            dedup_threshold_meters: 去重距离阈值（约50米≈0.0005度）

        Returns:
            DataResult: 合并去重后的统一结果
        """
        if not results:
            return DataResult.empty("merged", "no results to merge")

        # 按质量评分降序排序
        sorted_results = sorted(results, key=lambda r: r.quality_score, reverse=True)

        merged_features = []
        seen_coords: List[Tuple[float, float, str]] = []  # (lng, lat, name_lower)
        sources_used = []
        total_available = 0
        all_warnings = []
        best_quality = 0.0

        for result in sorted_results:
            sources_used.append(result.source)
            total_available += result.metadata.get("total_available", result.count)
            all_warnings.extend(result.warnings)
            best_quality = max(best_quality, result.quality_score)

            for feat in result.features:
                # 提取坐标用于去重
                coords = self._extract_feature_coords(feat)
                if coords is None:
                    # 无法提取坐标的要素直接保留
                    merged_features.append(self._tag_feature_source(feat, result.source))
                    continue

                lng, lat = coords
                props = feat.get("properties", {}) or {}
                name = (props.get("name") or "").strip().lower()

                # 去重检查
                is_dup = False
                for slng, slat, sname in seen_coords:
                    dist = ((lng - slng) ** 2 + (lat - slat) ** 2) ** 0.5
                    deg_threshold = dedup_threshold_meters / 111000.0  # 约 50m
                    if dist < deg_threshold and (not name or not sname or name == sname):
                        is_dup = True
                        break

                if not is_dup:
                    seen_coords.append((lng, lat, name))
                    merged_features.append(
                        self._tag_feature_source(feat, result.source)
                    )

        return DataResult(
            source="merged",
            features=merged_features,
            metadata={
                "sources_used": sources_used,
                "total_available_across_sources": total_available,
                "merged_count": len(merged_features),
                "dedup_strategy": f"coordinate+name, threshold ~{dedup_threshold_meters}m",
                "data_source": "Multi-source fusion (see sources_used)",
                "license": "Mixed (see individual sources)",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            quality_score=best_quality,
            warnings=all_warnings,
        )

    @staticmethod
    def _extract_feature_coords(feat: Dict) -> Optional[Tuple[float, float]]:
        """从 GeoJSON Feature 提取代表性坐标（用于去重）"""
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []

        if geom.get("type") == "Point":
            if len(coords) >= 2:
                return (float(coords[0]), float(coords[1]))

        elif geom.get("type") == "LineString":
            if coords:
                mid = coords[len(coords) // 2]
                if len(mid) >= 2:
                    return (float(mid[0]), float(mid[1]))

        elif geom.get("type") == "Polygon":
            if coords and coords[0]:
                ring = coords[0]
                lng_avg = sum(p[0] for p in ring) / len(ring)
                lat_avg = sum(p[1] for p in ring) / len(ring)
                return (lng_avg, lat_avg)

        return None

    @staticmethod
    def _tag_feature_source(feat: Dict, source: str) -> Dict:
        """在 Feature 的 properties 中标记数据来源"""
        feat_copy = dict(feat)
        props = dict(feat_copy.get("properties", {}) or {})
        existing = props.get("_fusion_source", "")
        if existing:
            props["_fusion_source"] = f"{existing},{source}"
        else:
            props["_fusion_source"] = source
        feat_copy["properties"] = props
        return feat_copy

    def fetch_and_merge(self, query: DataQuery,
                        sources: Optional[List[str]] = None) -> DataResult:
        """多源获取并合并（便捷方法）

        等价于 fetch_multi_source + merge_results 的组合调用。

        Args:
            query: 统一查询对象
            sources: 限定数据源列表

        Returns:
            DataResult: 合并后的统一结果
        """
        results = self.fetch_multi_source(query, sources)
        return self.merge_results(results)
