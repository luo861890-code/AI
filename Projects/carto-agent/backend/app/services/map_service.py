"""地图生成与管理服务 - 生成JSON格式地图数据并支持动态修改

MapService负责地图的完整生命周期管理：
- 生成地图：调用OSM服务获取真实地理数据，构建结构化地图JSON
- 管理图层：增删图层、修改样式、添加/删除要素
- 视图控制：中心点、缩放级别、底图主题
- 多源数据融合：通过DataSourceRegistry统一接入OSM/高德/天地图等数据源
- 所有修改方法返回更新后的完整地图数据，便于前端实时更新
"""
import json
import os
import re
import time
import threading
import shutil
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import (
    CITY_BBOX,
    CITY_ADCODES,
    MAP_TYPE_OSM_TAGS,
    MAP_STYLES,
    MAP_THEMES,
    WUHAN_LANDMARKS,
    WUHAN_DISTRICTS,
    BUILDING_STYLES,
    ROAD_CLASSIFICATION,
    RAILWAY_CLASSIFICATION,
    TOURISM_CATEGORIES,
    POI_STYLES,
    WATERWAY_STYLES,
    WATER_SYMBOL_STYLES,
    ADMIN_CENTER_STYLES,
    WUHAN_GOV_COORD,
    WUHAN_WATER_FALLBACK,
    WUHAN_GIS_POI,
    GREENSPACE_STYLES,
    LANDUSE_STYLES,
    LEGEND_TEMPLATES,
    LABEL_STYLES,
    THEMATIC_MAP_CONFIG,
)
from app.core.exceptions import MapGenerationError
from app.utils.helpers import generate_id, get_timestamp, ensure_dir
from app.utils.geometry import _point_in_ring

# 多源数据融合适配器
from app.services.data_source_adapter import (
    DataSourceRegistry,
    DataQuery,
    DataResult,
    OSMSourceAdapter,
    AmapPOIAdapter,
    TiandituTileAdapter,
)


class MapService:
    """地图生成与管理服务

    使用内存字典存储地图数据，支持地图的生成、查询、修改和删除。
    每个地图包含多个图层，每个图层包含多个地理要素。
    """

    # 防抖写入参数：修改后延迟 2 秒写入，期间的新修改会重置计时器
    _SAVE_DEBOUNCE_SECONDS: float = 2.0
    # 主文件保留地图数量上限，超出部分自动归档到 data/archive/maps/
    MAPS_MAIN_LIMIT: int = 10

    def __init__(self, osm_service=None, kg_service=None, persist_path: Optional[str] = None):
        """初始化地图服务

        Args:
            osm_service: OSM数据获取服务实例，用于获取真实地理数据
            kg_service: 知识图谱服务实例，用于查询制图规则（要素清单/符号/配色）
            persist_path: 地图数据持久化文件路径，默认 data/maps.json
        """
        self.osm_service = osm_service
        self.kg_service = kg_service
        # 内存字典存储所有地图 {map_id: map_data}
        self.maps: Dict[str, dict] = {}
        # 持久化：重启后自动恢复已生成的地图
        self.persist_path = persist_path or os.path.join(settings.data_dir, "maps.json")
        # 历史地图归档目录（迁移后的旧地图按 map_id 独立存放，按需加载）
        self.archive_dir = os.path.join(os.path.dirname(self.persist_path), "archive", "maps")
        # 防抖写入相关
        self._save_timer: Optional[threading.Timer] = None
        self._save_lock = threading.Lock()
        # LocalGeoService 缓存单例（避免每次 generate_map 都重新实例化）
        self._local_geo_service = None

        # ========== 多源数据融合适配器注册中心 ==========
        self.data_registry = DataSourceRegistry()
        # 注册 OSM 适配器（核心数据源，始终可用）
        self.data_registry.register(OSMSourceAdapter(self.osm_service))
        # 高德 POI 适配器（仅在有 API Key 时注册）
        if os.getenv("AMAP_KEY") or os.getenv("AMAP_API_KEY"):
            self.data_registry.register(AmapPOIAdapter())
        else:
            print("[MapService] 未配置 AMAP_KEY，高德 POI 适配器未注册"
                  "（在 .env 中设置 AMAP_KEY 后启用）")
        # 天地图瓦片适配器（仅在有 API Key 时注册）
        if os.getenv("TIANDITU_KEY"):
            self.data_registry.register(TiandituTileAdapter())
        else:
            print("[MapService] 未配置 TIANDITU_KEY，天地图适配器未注册"
                  "（在 .env 中设置 TIANDITU_KEY 后启用）")

        self._load()
        print(f"[MapService] 初始化完成，已注册数据源:"
              f" {self.data_registry.get_available_sources()}")

    def _load(self):
        """从磁盘加载地图数据（重启恢复）——带容错
        
        优先从主文件加载，主文件损坏时尝试从备份恢复。
        """
        backup_path = self.persist_path + ".bak"
        for source_path, source_label in [(self.persist_path, "主文件"), (backup_path, "备份文件")]:
            if not os.path.exists(source_path):
                continue
            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.maps = data
                    print(f"[MapService] 已从{source_label} {source_path} 恢复 {len(self.maps)} 张地图")
                    return
            except (json.JSONDecodeError, OSError) as e:
                print(f"[MapService] {source_label}加载失败: {e}")
                # 记录损坏文件以便排查
                corrupted = self.persist_path + f".corrupted.{int(time.time())}"
                try:
                    os.rename(source_path, corrupted)
                    print(f"[MapService] 损坏文件已重命名: {corrupted}")
                except OSError:
                    pass
        # 全部恢复失败，从空开始（下次保存自动修复）
        print("[MapService] 所有持久化文件加载失败，使用空内存（下次保存会自动重建）")
        self.maps = {}

    def _schedule_save(self):
        """防抖调度持久化：延迟 _SAVE_DEBOUNCE_SECONDS 后写入，期间的新调用会重置计时器"""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(
                self._SAVE_DEBOUNCE_SECONDS, self._save
            )
            self._save_timer.daemon = True
            self._save_timer.start()

    def flush(self):
        """立即将待写入的数据持久化到磁盘（用于服务关闭前的安全落盘）"""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
        self._save()

    def _save(self):
        """原子写入：先写临时文件，成功后替换原文件 + 备份旧文件
        
        原子写入三步法：
        1. 写入 .tmp 临时文件
        2. 将旧主文件重命名为 .bak 备份
        3. 将临时文件重命名为主文件
        
        任何一步失败都不会丢失已有数据（原始主文件或备份文件仍存在）。
        """
        import shutil, time as _time
        # 先归档超限的最旧地图，避免主文件再次膨胀
        self._archive_old_maps()
        tmp_path = self.persist_path + ".tmp"
        backup_path = self.persist_path + ".bak"
        try:
            ensure_dir(os.path.dirname(self.persist_path) or ".")
            # 步骤1: 写入临时文件
            with open(tmp_path, "w", encoding="utf-8") as f:
                # 紧凑写入（不带缩进）：文件体积减小约 2/3，仅机器读写无需人类阅读
                json.dump(self.maps, f, ensure_ascii=False)
            # 步骤2: 备份旧主文件（如果存在）
            if os.path.exists(self.persist_path):
                try:
                    os.replace(self.persist_path, backup_path)
                except OSError:
                    pass  # 备份失败不阻塞
            # 步骤3: 原子替换为主文件
            os.replace(tmp_path, self.persist_path)
        except Exception as e:
            print(f"[MapService] 地图数据持久化失败: {e}")
            # 清理临时文件
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _archive_old_maps(self):
        """主文件超过 MAPS_MAIN_LIMIT 时，将最旧的地图移入归档目录"""
        if len(self.maps) <= self.MAPS_MAIN_LIMIT:
            return
        items = sorted(
            self.maps.items(),
            key=lambda kv: kv[1].get("created_at", 0) if isinstance(kv[1], dict) else 0,
        )
        overflow = items[: len(self.maps) - self.MAPS_MAIN_LIMIT]
        for map_id, map_data in overflow:
            if self._write_archived_map(map_id, map_data):
                del self.maps[map_id]
                print(f"[MapService] 旧地图已归档: {map_id}")

    def _write_archived_map(self, map_id: str, map_data: dict) -> bool:
        """将单张地图写入归档目录，并更新归档清单"""
        try:
            ensure_dir(self.archive_dir)
            archive_path = os.path.join(self.archive_dir, f"{map_id}.json")
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(map_data, f, ensure_ascii=False)
            manifest_path = os.path.join(self.archive_dir, "_manifest.json")
            manifest = []
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    if not isinstance(manifest, list):
                        manifest = []
                except (json.JSONDecodeError, OSError):
                    manifest = []
            entry = {
                "map_id": map_id,
                "name": map_data.get("name", ""),
                "map_type": map_data.get("map_type", ""),
                "region": map_data.get("region", ""),
                "created_at": map_data.get("created_at"),
                "file": f"{map_id}.json",
            }
            manifest = [m for m in manifest if m.get("map_id") != map_id] + [entry]
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
            return True
        except OSError as e:
            print(f"[MapService] 地图归档失败 {map_id}: {e}")
            return False

    # ==================== 地图基础操作 ====================

    def generate_map(
        self,
        map_type: str,
        region: str,
        center: Optional[List[float]] = None,
        zoom: int = 12,
        layers: Optional[List[str]] = None,
    ) -> dict:
        """生成地图

        调用OSM服务获取真实地理数据，构建JSON格式地图数据。

        Args:
            map_type: 地图类型（traffic/tourism/campus/basic/food/administrative）
            region: 区域名称（如"武汉市"）
            center: 中心坐标 [lat, lng]，为None时从CITY_BBOX获取
            zoom: 缩放级别，默认12
            layers: 自定义图层类型列表，为None时根据map_type自动确定

        Returns:
            完整的地图数据字典，包含map_id, name, center, zoom, theme, layers, created_at

        Raises:
            MapGenerationError: 地图生成失败
        """
        try:
            # 确定中心坐标
            if center is None:
                bbox = CITY_BBOX.get(region, {})
                if bbox:
                    center = [bbox["center_lat"], bbox["center_lon"]]
                else:
                    center = [30.5928, 114.3055]  # 默认武汉

            # 行政区划标准图：图幅范围包含周边相邻地市（规范九-5），限制最大缩放
            if map_type == "administrative" and (zoom is None or zoom > 10):
                zoom = 10

            # 确定要素类型：优先从知识图谱查询制图规则，KG未命中才fallback硬编码
            if layers is None:
                element_types = self._resolve_element_types_from_kg(map_type)
                print(f"[MapService] 地图类型={map_type}，要素清单来源={'KG' if element_types.get('from_kg') else '硬编码兜底'}，"
                      f"要素={element_types['types']}")
                element_types = element_types["types"]
            else:
                element_types = layers

            # 非专题地图统一补充水系要素（陆地/水系底图需要）；
            # 行政区划图（GIS叠加底图风格）同样叠加水系与路网要素
            if map_type not in THEMATIC_MAP_CONFIG:
                for _extra in ("waterway", "natural", "highway"):
                    if _extra not in element_types:
                        element_types.append(_extra)

            # 制图综合：按缩放级别选取要素等级（大比例尺显示更多细节）
            if "highway" in element_types:
                element_types = [t for t in element_types if t != "highway"]
                element_types.append("highway_major")
                if zoom >= 13:
                    element_types.append("highway_minor")
            if "waterway" in element_types:
                element_types = [t for t in element_types if t != "waterway"]
                element_types.append("waterway_major")
                if zoom >= 12:
                    element_types.append("waterway_minor")
            if "place" in element_types:
                element_types = [t for t in element_types if t != "place"]
                element_types.append("place_city")
                if zoom >= 13:
                    element_types.append("place_suburb")

            # 专题地图特殊处理
            if map_type in THEMATIC_MAP_CONFIG:
                map_layers = self._generate_thematic_layers(map_type, region, center)
                print(f"[MapService] 专题地图生成完成: {map_type}, {len(map_layers)} 个图层")
            else:
                map_layers = []

            # 本地精确数据优先（backend/data/geo/*.geojson）：
            # 存在本地水系/路网时跳过 OSM 对应抓取，避免兜底近似数据
            _local_water = []
            _local_roads = []
            _local_tourism = []
            _local_transit = []
            _local_builtup = []
            try:
                from app.services.local_geo_service import LocalGeoService
                # 缓存 LocalGeoService 单例，避免每次 generate_map 都重新实例化
                if self._local_geo_service is None:
                    self._local_geo_service = LocalGeoService()
                _lgs = self._local_geo_service
                _local_water = _lgs.get_water_layers(region)
                _local_roads = _lgs.get_roads_layers(region)
                _local_builtup = []
                try:
                    # 居民地街区（制图综合：合并/化简/分级），仅大比例尺显示
                    _local_builtup = _lgs.get_builtup_layers(region)
                except Exception as _be:
                    print(f"[MapService] 居民地街区图层加载失败: {_be}")
                if map_type == "tourism":
                    _local_tourism = _lgs.get_tourism_layers(region)
                elif map_type == "traffic":
                    _local_transit = _lgs.get_transit_layers(region)
                if _local_water:
                    element_types = [t for t in element_types
                                     if not t.startswith("waterway") and t != "natural"]
                if _local_roads:
                    element_types = [t for t in element_types if not t.startswith("highway")]
            except Exception as e:
                print(f"[MapService] 本地地理数据加载失败: {e}")

            # 获取OSM数据（非专题地图才获取）
            osm_data = {}
            if not map_layers and self.osm_service:
                print(f"[MapService] 正在获取{region}的OSM数据，类型: {element_types}")
                osm_data = self.osm_service.fetch_by_region(region, element_types)
                # 高德POI数据补充（配置AMAP_API_KEY后自动启用，无key时自动跳过）
                try:
                    from app.services.amap_service import AmapService
                    amap = AmapService()
                    if amap.enabled and "amenity" in element_types:
                        pois = amap.fetch_region_pois(region, map_type)
                        if pois:
                            osm_data.setdefault("amenity", []).extend(pois)
                except Exception as e:
                    print(f"[MapService] 高德数据补充失败: {e}")

            # 将OSM元素转换为图层（仅当没有专题图层时）
            if not map_layers:
                map_layers = self._elements_to_layers(osm_data, element_types)
            # 叠加本地精确数据图层（水系在底层、路网在上；GIS叠加顺序由前端layerZ控制）
            if _local_water:
                map_layers = _local_water + map_layers
            if _local_roads:
                map_layers = map_layers + _local_roads
            if _local_transit:
                map_layers = map_layers + _local_transit
            if _local_tourism:
                map_layers = map_layers + _local_tourism
            if _local_builtup:
                map_layers = map_layers + _local_builtup

            # 标准行政区划图：叠加官方区划面底图（DataV GeoAtlas，含区县政区面/注记/行政中心）
            if map_type == "administrative":
                try:
                    from app.services.geo_service import GeoService
                    gs = GeoService()
                    geo_layers = gs.build_district_layers(region)
                    if geo_layers:
                        # 移除OSM place生成的区县注记（与DataV注记重复），保留街道地名标注
                        map_layers = [
                            l for l in map_layers
                            if not (l.get("type") == "textLabel" and l.get("name") == "区县名称标注")
                        ]
                        # 移除OSM生成的边界线（改用DataV标准境界线；紫色地级市界已按用户要求删除）
                        map_layers = [
                            l for l in map_layers
                            if not (l.get("type") == "polyline"
                                    and (l.get("style", {}).get("osm_boundary") or "边界" in (l.get("name") or "")))
                        ]
                        # 移除与专题无关的绿地面（公园/森林/草地），保留湖泊水域面
                        map_layers = [
                            l for l in map_layers
                            if l.get("name") not in ("公园", "森林", "草地", "草甸", "其他绿地", "绿化用地")
                        ]
                        # 区名白名单校验：只保留武汉市13个标准区名注记，
                        # 过滤数据源错误名称（如"汝南区"等非规范区名）
                        _std_names = {d["name"] for d in WUHAN_DISTRICTS}
                        map_layers = [
                            ({
                                **l,
                                "coordinates": [c for c, p in zip(l.get("coordinates") or [], l.get("properties") or [])
                                                if p.get("name") in _std_names],
                                "properties": [p for p in (l.get("properties") or []) if p.get("name") in _std_names],
                            } if (l.get("type") == "textLabel" and l.get("name") == "区县名称标注") else l)
                            for l in map_layers
                        ]
                        # 周边地市底图(极浅米黄) + 标准境界线（省界/地级市界）
                        surrounding = gs.build_surrounding_layers(region)
                        map_layers = surrounding + geo_layers + map_layers
                        # 市级行政中心（红色五角星★，正红#D82828，规范三-1）
                        # 坐标按用户要求标注于武昌区（官方驻地实际在江岸区沿江大道188号）
                        cc = ADMIN_CENTER_STYLES["city"]
                        _gov = WUHAN_GOV_COORD if region == "武汉市" else None
                        if _gov:
                            map_layers.append({
                                "id": generate_id("layer"),
                                "type": "circleMarker",
                                "name": cc["name"],
                                "coordinates": [[_gov[0], _gov[1]]],
                                "properties": [{"name": region}],
                                "style": {"color": cc["color"], "fillColor": cc["fillColor"],
                                          "fillOpacity": cc["fillOpacity"], "weight": cc["weight"],
                                          "radius": cc["radius"], "icon": cc["icon"],
                                          "iconClass": cc.get("iconClass"), "kind": cc.get("kind")},
                            })
                    # 水系：本地精确数据优先；本地缺失时走 OSM → 兜底近似
                    if not _local_water:
                        has_water = any(
                            any(k in (l.get("name") or "") for k in ("河", "湖", "水库", "水系"))
                            for l in map_layers
                        )
                        map_layers += self._fallback_water_layers(region, surrounding_only=has_water)
                    # 重点POI标注（机场/景区/交通枢纽等，GIS叠加风格绿点）
                    gis_pois = WUHAN_GIS_POI if region == "武汉市" else []
                    # 完美复刻 carto-agent-1 行政区划图：行政图不叠加新增的樱花主题地标
                    if map_type == "administrative":
                        _CHERRY_POIS = {"武汉大学樱花大道", "东湖磨山樱花园", "晴川阁樱花园"}
                        gis_pois = [p for p in gis_pois if p.get("name") not in _CHERRY_POIS]
                    if gis_pois:
                        map_layers.append({
                            "id": generate_id("layer"),
                            "type": "circleMarker",
                            "name": "重点地标",
                            "coordinates": [[p["lat"], p["lng"]] for p in gis_pois],
                            "properties": [{"name": p["name"], "category": p["type"]} for p in gis_pois],
                            "style": {"color": "#16a34a", "fillColor": "#ffffff", "fillOpacity": 0.9,
                                      "weight": 2.5, "radius": 7, "icon": "🏞️", "iconClass": "fa-location-dot",
                                      "group": "兴趣点(POI)"},
                        })
                except Exception as e:
                    print(f"[MapService] 区划面底图获取失败: {e}")

            # 非行政区划图：叠加"上一级行政边界"上下文（湖北省市级边界 + 武汉市域）
            # 生成的地图仅含用户所需区域 + 行政规划上一级，两个模块颜色区分
            if map_type != "administrative" and region in CITY_ADCODES:
                try:
                    from app.services.geo_service import GeoService
                    _gs = GeoService()
                    _ctx = _gs.build_surrounding_layers(region)
                    if _ctx:
                        map_layers = _ctx + map_layers
                except Exception as e:
                    print(f"[MapService] 上一级行政边界叠加失败: {e}")

            # 如果图层为空（OSM数据为空或API不可用），使用本地地标数据作为回退
            if not map_layers:
                print(f"[MapService] OSM数据为空，使用本地地标数据作为回退: {region}")
                map_layers = self._generate_fallback_layers(map_type, region, center, zoom)

            # 陆地/水系底图：所有地图插入"陆地底图"米色面（水系蓝色面由OSM数据生成）；
            # 行政区划图除外（政区面即陆地底图）
            if map_type not in THEMATIC_MAP_CONFIG and map_type != "administrative":
                _bbox = CITY_BBOX.get(region, {})
                if _bbox:
                    _land = [[_bbox["min_lat"], _bbox["min_lon"]], [_bbox["min_lat"], _bbox["max_lon"]],
                             [_bbox["max_lat"], _bbox["max_lon"]], [_bbox["max_lat"], _bbox["min_lon"]],
                             [_bbox["min_lat"], _bbox["min_lon"]]]
                    map_layers = [{
                        "id": generate_id("layer"),
                        "type": "polygon",
                        "name": "陆地底图",
                        "coordinates": [_land],
                        "style": {"fillColor": "#f3ead9", "fillOpacity": 0.6,
                                  "color": "#e5d9c0", "weight": 0.5},
                    }] + map_layers

            # 县级行政区划专题规范：隐藏乡镇边界图层；"武汉市"总注记由图廓标题承担，移除图内重复
            if map_type == "administrative":
                map_layers = [
                    l for l in map_layers
                    if l.get("name") not in ("乡镇边界", "城市名称标注")
                ]

            # 行政区划图兜底：place数据缺失(Overpass限流)时补充武汉区县标注
            if map_type == "administrative" and region == "武汉市":
                has_label = any(l.get("type") == "textLabel" for l in map_layers)
                if not has_label:
                    map_layers.append({
                        "id": generate_id("layer"),
                        "type": "textLabel",
                        "name": "区县名称标注",
                        "coordinates": [[d["lat"], d["lng"]] for d in WUHAN_DISTRICTS],
                        "properties": [{"name": d["name"]} for d in WUHAN_DISTRICTS],
                        "style": {"color": "#000000", "fontSize": 15, "weight": 3, "font": "song"},
                    })

            # 重要地标名称常驻注记（直接附着在地图上，直观可见）
            if region == "武汉市" and map_type in ("tourism", "basic", "traffic"):
                if not any(l.get("name") == "地标名称" for l in map_layers):
                    map_layers.append({
                        "id": generate_id("layer"),
                        "type": "textLabel",
                        "name": "地标名称",
                        "coordinates": [[lm["lat"], lm["lng"]] for lm in WUHAN_LANDMARKS],
                        "properties": [{"name": lm["name"]} for lm in WUHAN_LANDMARKS],
                        "style": {"color": LABEL_STYLES["landmark"]["color"],
                                  "fontSize": LABEL_STYLES["landmark"]["fontSize"],
                                  "weight": LABEL_STYLES["landmark"]["weight"],
                                  "font": LABEL_STYLES["landmark"]["font"]},
                    })

            # 按制图规范调整图层叠置顺序（面状底图→建筑→水系→铁路→道路→点状符号）
            map_layers = self._sort_layers(map_layers)

            # 生成图例数据
            legend = self._generate_legend(map_type, map_layers)

            # 构建地图数据
            map_id = generate_id("map")
            # 获取地图类型中文名
            type_names = {
                "traffic": "交通图", "tourism": "旅游图", "campus": "校园图",
                "basic": "基础地图", "food": "美食图", "administrative": "行政区划图",
            }
            map_name = f"{region}{type_names.get(map_type, '地图')}"

            # 数据质量校验：行政区划图不再自动输出面积统计（坐标投影换算易失真，
            # 需求8：关闭错误的自动面积统计），只保留其他通用告警
            quality = {"warnings": []}

            map_data = {
                "map_id": map_id,
                "name": map_name,
                "map_type": map_type,
                "region": region,
                "center": center,
                "zoom": zoom,
                "theme": "plain",   # 默认无瓦片制图底图（矢量制图）
                "layers": map_layers,
                "legend": legend,
                "quality": quality,
                # 编制说明（规范3.7：坐标系/投影/数据来源/资料截止）
                "metadata": {
                    "坐标系": "CGCS2000 国家大地坐标系",
                    "投影": "高斯-克吕格投影 3°分带（标准地图）/ Web墨卡托（网页显示）",
                    "数据来源": "DataV GeoAtlas 官方行政区划数据 / OpenStreetMap",
                    "地图类型": "行政区划图（政区版）· 普通参考地图",
                    "图幅范围": "武汉市及周边相邻地市（区位关系）",
                    "幅面版式": "竖版",
                    "审图号": "鄂S(2022)100号",
                    "编制单位": "地图制图智能体 CartoAgent",
                    "出版日期": "2026年8月",
                    "资料截止": "民政部行政区划现状 / OSM实时",
                    "说明": "依据《行政区划地图制作规范》编制；正式出版需取得审图号并配置标准投影",
                },
                "created_at": get_timestamp(),
            }

            # 存储到内存
            self.maps[map_id] = map_data
            self._schedule_save()
            print(f"[MapService] 地图生成成功: {map_name} (ID: {map_id})，"
                  f"共{len(map_layers)}个图层")

            return map_data

        except Exception as e:
            print(f"[MapService] 地图生成失败: {e}")
            raise MapGenerationError(f"地图生成失败: {e}")

    def _resolve_element_types_from_kg(self, map_type: str) -> dict:
        """从知识图谱查询指定地图类型应包含的要素清单

        优先调用 KG 的 query_cartographic_decision 获取图层配置；
        KG 未命中（空结果 / confidence=none / kg_service 未注入）时，
        fallback 到 constants.MAP_TYPE_OSM_TAGS 硬编码表。

        Returns:
            {"types": List[str], "from_kg": bool}
        """
        fallback_types = MAP_TYPE_OSM_TAGS.get(map_type, ["highway"])

        # KG 服务未注入 → 直接用硬编码
        if self.kg_service is None:
            return {"types": fallback_types, "from_kg": False}

        try:
            decision = self.kg_service.query_cartographic_decision(map_type, audience="public")
        except Exception as e:
            print(f"[MapService] KG查询异常，回退硬编码: {e}")
            return {"types": fallback_types, "from_kg": False}

        if not decision:
            return {"types": fallback_types, "from_kg": False}

        confidence = decision.get("confidence", "none")
        if confidence == "none":
            print(f"[MapService] KG对'{map_type}'置信度为none，使用硬编码兜底")
            return {"types": fallback_types, "from_kg": False}

        layer_configs = decision.get("layer_configs", [])
        if not layer_configs:
            print(f"[MapService] KG返回的layer_configs为空，使用硬编码兜底")
            return {"types": fallback_types, "from_kg": False}

        # 从KG的layer_configs中提取要素类型列表
        # layer_configs 每项格式: {"name": "...", "osm_tags": "highway=motorway|highway=trunk", ...}
        extracted = []
        seen = set()
        for layer in layer_configs:
            if not isinstance(layer, dict):
                continue
            # 优先从 osm_tags 提取（如 "highway=motorway|highway=trunk" → highway）
            osm_tags = layer.get("osm_tags") or layer.get("osm_tag") or ""
            if osm_tags and isinstance(osm_tags, str):
                # 取等号前的标签名，去重
                for tag_pair in osm_tags.split("|"):
                    tag_key = tag_pair.split("=")[0].strip()
                    if tag_key and tag_key not in seen:
                        seen.add(tag_key)
                        extracted.append(tag_key)
            else:
                # 兜底：从 type/feature_type/name 字段提取
                tag = (layer.get("type")
                       or layer.get("feature_type")
                       or layer.get("layer_type")
                       or layer.get("name"))
                if tag and isinstance(tag, str) and tag not in seen:
                    seen.add(tag)
                    extracted.append(tag)

        if not extracted:
            print(f"[MapService] KG layer_configs未解析出要素类型，使用硬编码兜底")
            return {"types": fallback_types, "from_kg": False}

        print(f"[MapService] KG制图决策生效: map_type={map_type}, confidence={confidence}, "
              f"layers={len(layer_configs)}, resolved={extracted}")
        return {"types": extracted, "from_kg": True}

    def get_map(self, map_id: str) -> Optional[dict]:
        """获取地图数据

        Args:
            map_id: 地图ID

        Returns:
            地图数据字典，不存在时返回None
        """
        map_data = self.maps.get(map_id)
        if map_data is not None:
            self._classify_layers(map_data)
            return map_data
        # 主存储未命中时，尝试从归档目录按需加载（不写回主文件，避免再次膨胀）
        return self._load_archived_map(map_id)

    def _load_archived_map(self, map_id: str) -> Optional[dict]:
        """从归档目录加载历史地图（data/archive/maps/{map_id}.json）"""
        if not map_id:
            return None
        archive_path = os.path.join(self.archive_dir, f"{map_id}.json")
        if not os.path.exists(archive_path):
            return None
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                map_data = json.load(f)
            if isinstance(map_data, dict) and map_data.get("map_id"):
                self._classify_layers(map_data)
                return map_data
        except (json.JSONDecodeError, OSError) as e:
            print(f"[MapService] 归档地图加载失败 {map_id}: {e}")
        return None

    def _classify_layers(self, map_data: dict) -> None:
        """图层分类综合（QGIS/ArcGIS 图层管理）：

        给每个图层补齐持久化的分类元数据：
          - group   按制图要素类别分组的名称（底图/行政区划/水系/湖泊/…）
          - format  颜色/线宽/填充/虚线等视觉格式摘要
          - visible 图层可见性（默认True，可隐藏并持久化）

        分类依据"颜色与格式 + 名称语义"，与前端图层面板联动。
        """
        if not map_data or "layers" not in map_data:
            return
        changed = False
        # 老图迁移：道路图层英文名 -> 中文名 + 子分组
        ROAD_CN = {
            "motorway": "高速公路主线", "motorway_link": "高速互通匝道",
            "trunk": "城市干线主干道", "trunk_link": "主干道连接匝道",
            "primary": "城市主干道", "primary_link": "主干道衔接匝道",
            "secondary": "城市次干道", "secondary_link": "次干道连接匝道",
            "tertiary": "三级道路（次要道路）", "tertiary_link": "三级道路连接线",
            "residential": "居民区街区道路", "living_street": "生活性街道",
            "service": "服务性道路", "unclassified": "未分级道路", "other": "其他道路",
        }
        ROAD_SUB = {
            "motorway": "高速路网", "motorway_link": "高速路网",
            "trunk": "城市主干道", "trunk_link": "城市主干道",
            "primary": "城市主干道", "primary_link": "城市主干道",
            "secondary": "城区道路", "secondary_link": "城区道路",
            "tertiary": "城区道路", "tertiary_link": "城区道路",
            "residential": "城区道路", "living_street": "城区道路",
            "service": "其他道路", "unclassified": "其他道路", "other": "其他道路",
        }
        ROAD_OPACITY = {
            # 与 carto-agent-1 行政区划图完全一致：道路统一不透明度 0.9
            "motorway": 0.9, "motorway_link": 0.9, "trunk": 0.9, "trunk_link": 0.9,
            "primary": 0.9, "primary_link": 0.9, "secondary": 0.9,
            "secondary_link": 0.9, "tertiary": 0.9, "tertiary_link": 0.9,
            "residential": 0.9, "living_street": 0.9, "service": 0.9,
            "unclassified": 0.9, "other": 0.9,
        }

        def _cat(layer: dict) -> str:
            n = layer.get("name", "") or ""
            t = layer.get("type", "") or ""
            if re.search(r"陆地底图|省域|周边地市|市域底图|湖北省", n):
                return "底图"
            if re.search(r"政区|区县|边界|行政中心|区划", n):
                return "行政区划"
            if re.search(r"河流|水系|河道|中心线|大江|水面", n):
                return "水系"
            if "湖泊" in n:
                return "湖泊"
            if "居民地" in n:
                return "居民地"
            if "等高线" in n:
                return "等高线"
            if n.startswith("道路-") or re.search(r"高速|国道|省道|主干道|次干道|支路|街巷", n):
                return "道路"
            if re.search(r"轨道|铁路|地铁|轻轨", n):
                return "轨道/铁路"
            if t in ("circleMarker", "marker", "point", "circle"):
                return "POI/符号"
            if t in ("textLabel", "label") or "注记" in n or "标注" in n:
                return "注记/标注"
            return "其他"

        for layer in map_data["layers"]:
            # 老图道路图层命名迁移
            _m = re.match(r"^道路-([a-z_]+)$", layer.get("name", "") or "")
            if _m and _m.group(1) in ROAD_CN:
                hw = _m.group(1)
                new_name = f"道路-{ROAD_CN[hw]}"
                if layer.get("name") != new_name:
                    layer["name"] = new_name
                    changed = True
                if layer.get("subgroup") != ROAD_SUB[hw]:
                    layer["subgroup"] = ROAD_SUB[hw]
                    changed = True
                _st = layer.setdefault("style", {})
                if _st.get("opacity", 1.0) != ROAD_OPACITY.get(hw):
                    _st["opacity"] = ROAD_OPACITY.get(hw, 0.9)
                    changed = True
                layer.setdefault("metadata", {})["raw_class"] = hw
                layer.setdefault("metadata", {})["description"] = ROAD_CN[hw]
            # 道路样式迁移（按 raw_class / properties.subtype 设置分级不透明度）
            _rc = (layer.get("metadata") or {}).get("raw_class")
            if not _rc and layer.get("properties") and isinstance(layer.get("properties"), list):
                _p0 = layer["properties"][0] if layer["properties"] else None
                _rc = _p0.get("subtype") if isinstance(_p0, dict) else None
            if _rc in ROAD_OPACITY:
                _st = layer.setdefault("style", {})
                if _st.get("opacity", 1.0) != ROAD_OPACITY[_rc]:
                    _st["opacity"] = ROAD_OPACITY[_rc]
                    changed = True
            if "group" not in layer:
                layer["group"] = _cat(layer)
                changed = True
            if "format" not in layer:
                st = layer.get("style") or {}
                layer["format"] = {
                    "color": st.get("color", ""),
                    "fillColor": st.get("fillColor", ""),
                    "weight": st.get("weight"),
                    "dashArray": st.get("dashArray", ""),
                    "opacity": st.get("opacity"),
                }
                changed = True
            if "visible" not in layer:
                layer["visible"] = True
                changed = True
        if changed:
            self._schedule_save()

    def list_maps(self) -> List[dict]:
        """列出所有地图

        Returns:
            地图摘要列表（不含完整图层数据，减少传输量）
        """
        result = []
        for map_data in self.maps.values():
            result.append({
                "map_id": map_data["map_id"],
                "name": map_data["name"],
                "map_type": map_data.get("map_type", ""),
                "region": map_data.get("region", ""),
                "center": map_data["center"],
                "zoom": map_data["zoom"],
                "theme": map_data["theme"],
                "layer_count": len(map_data["layers"]),
                "created_at": map_data["created_at"],
            })
        return result

    def delete_map(self, map_id: str) -> bool:
        """删除地图

        Args:
            map_id: 地图ID

        Returns:
            删除是否成功
        """
        if map_id in self.maps:
            del self.maps[map_id]
            self._schedule_save()
            print(f"[MapService] 地图已删除: {map_id}")
            return True
        # 归档地图也可删除（同步清理归档文件）
        archive_path = os.path.join(self.archive_dir, f"{map_id}.json")
        if os.path.exists(archive_path):
            try:
                os.remove(archive_path)
                print(f"[MapService] 归档地图已删除: {map_id}")
                return True
            except OSError as e:
                print(f"[MapService] 归档地图删除失败 {map_id}: {e}")
                return False
        print(f"[MapService] 地图不存在: {map_id}")
        return False

    # ==================== 多源数据融合 ====================

    def fetch_data_multi_source(
        self,
        data_type: str,
        bbox: Optional[List[float]] = None,
        region: Optional[str] = None,
        limit: int = 1000,
        preferred_source: Optional[str] = None,
        merge: bool = True,
        **filters,
    ) -> DataResult:
        """多源数据融合获取

        通过 DataSourceRegistry 从多个数据源获取地理要素数据，
        支持自动选择最优源、多源查询、结果合并去重。

        Args:
            data_type: 要素类型，如 "highway", "poi/restaurant", "vec"
            bbox: 边界框 [min_lng, min_lat, max_lng, max_lat]，
                  为 None 时自动根据 region 填充
            region: 区域名称（如"武汉市"），在 bbox 为 None 时使用
            limit: 返回数量上限
            preferred_source: 优先使用的数据源
            merge: 是否合并多源结果（True=合并去重, False=返回第一个源的结果）
            **filters: 额外筛选条件

        Returns:
            DataResult: 统一返回对象

        Example:
            # 多源融合获取武汉餐饮 POI
            result = map_service.fetch_data_multi_source(
                "poi/restaurant", region="武汉市", merge=True
            )
            # 获取 OSM 道路数据
            result = map_service.fetch_data_multi_source(
                "highway", region="武汉市", preferred_source="osm"
            )
        """
        # 构建查询对象
        if bbox:
            query = DataQuery(
                data_type=data_type,
                bbox=bbox,
                limit=limit,
                filters=filters if filters else None,
                region=region,
            )
        elif region:
            query = DataQuery.from_region(
                data_type=data_type,
                region=region,
                limit=limit,
                filters=filters if filters else None,
            )
        else:
            return DataResult.empty("map_service", "no bbox or region specified")

        print(f"[MapService] 多源数据获取: type={data_type},"
              f" region={region}, merge={merge}, preferred={preferred_source}")

        if merge:
            # 多源融合：获取所有源的结果并合并去重
            result = self.data_registry.fetch_and_merge(query)
        elif preferred_source:
            # 指定优先源
            result = self.data_registry.fetch(query, preferred_source=preferred_source)
        else:
            # 自动选择第一个支持的源
            result = self.data_registry.fetch(query)

        print(f"[MapService] 多源数据获取完成: {result.count} 个要素,"
              f" source={result.source}, quality={result.quality_score}")
        return result

    def get_data_sources(self) -> List[str]:
        """获取当前可用的数据源列表"""
        return self.data_registry.get_available_sources()

    # ==================== 图层操作 ====================

    def add_layer(
        self,
        map_id: str,
        layer_type: str,
        name: str,
        query: Optional[str] = None,
    ) -> dict:
        """向地图添加新图层

        如果提供了query参数（OSM标签类型），会自动查询OSM数据填充图层。

        Args:
            map_id: 地图ID
            layer_type: 图层类型（polyline/marker/polygon）
            name: 图层名称
            query: OSM查询标签（如"highway"、"railway"），可选

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图不存在或添加失败
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        coordinates = []

        # 如果提供了OSM查询标签，获取真实数据
        if query and self.osm_service:
            region = map_data.get("region", "武汉市")
            osm_data = self.osm_service.fetch_by_region(region, [query])
            elements = osm_data.get(query, [])

            for elem in elements:
                coords = self._extract_coordinates(elem, layer_type)
                if coords:
                    coordinates.append(coords)

        # 获取默认样式
        style = self._get_default_style(query or layer_type)

        # 创建新图层
        layer = {
            "id": generate_id("layer"),
            "type": layer_type,
            "name": name,
            "coordinates": coordinates,
            "style": style,
        }

        map_data["layers"].append(layer)
        self._schedule_save()
        print(f"[MapService] 图层已添加: {name} (ID: {layer['id']})，"
              f"包含{len(coordinates)}个要素")
        return map_data

    def remove_layer(self, map_id: str, layer_id: str) -> dict:
        """从地图移除图层

        Args:
            map_id: 地图ID
            layer_id: 图层ID

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图或图层不存在
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        original_count = len(map_data["layers"])
        map_data["layers"] = [
            layer for layer in map_data["layers"] if layer["id"] != layer_id
        ]

        if len(map_data["layers"]) == original_count:
            raise MapGenerationError(f"图层不存在: {layer_id}")

        self._schedule_save()
        print(f"[MapService] 图层已移除: {layer_id}")
        return map_data

    def update_layer_style(self, map_id: str, layer_id: str, style: dict) -> dict:
        """更新图层样式

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            style: 样式字典（color, weight, opacity, fillOpacity, dashArray等）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图或图层不存在
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                # 合并样式，保留未更新的字段
                layer["style"].update(style)
                self._schedule_save()
                print(f"[MapService] 图层样式已更新: {layer_id}，新样式: {layer['style']}")
                return map_data

        raise MapGenerationError(f"图层不存在: {layer_id}")

    def set_layer_visible(self, map_id: str, layer_id: str, visible: bool) -> dict:
        """设置图层可见性（QGIS/ArcGIS 图层管理：隐藏/显示并持久化）"""
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                layer["visible"] = bool(visible)
                self._schedule_save()
                print(f"[MapService] 图层可见性已更新: {layer_id} -> {visible}")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def rename_layer(self, map_id: str, layer_id: str, name: str) -> dict:
        """重命名图层（QGIS/ArcGIS 图层管理）"""
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                layer["name"] = name
                self._schedule_save()
                print(f"[MapService] 图层已重命名: {layer_id} -> {name}")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def update_layer_geometry(
        self,
        map_id: str,
        layer_id: str,
        coordinates: Optional[Any] = None,
        properties: Optional[Any] = None,
        style: Optional[dict] = None,
        features: Optional[Any] = None,
    ) -> dict:
        """编辑模式：整层替换几何/属性/样式（QGIS/ArcGIS 式编辑保存）

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            coordinates: 新的坐标数组（整层替换，coordinates 型图层）
            properties: 新的属性数组（与 coordinates 一一对应）
            style: 新的样式字典
            features: 新的 features 数组（features 型图层）
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                if coordinates is not None:
                    layer["coordinates"] = coordinates
                if properties is not None:
                    layer["properties"] = properties
                if style is not None:
                    layer["style"] = style
                if features is not None:
                    layer["features"] = features
                self._schedule_save()
                print(f"[MapService] 图层几何已更新: {layer_id} "
                      f"(coords={len(coordinates or []) if coordinates is not None else '-'}, "
                      f"features={len(features or []) if features is not None else '-'})")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def update_view(
        self,
        map_id: str,
        center: Optional[List[float]] = None,
        zoom: Optional[int] = None,
    ) -> dict:
        """更新地图视图（中心点和缩放级别）

        Args:
            map_id: 地图ID
            center: 新的中心坐标 [lat, lng]，可选
            zoom: 新的缩放级别，可选

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图不存在
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        if center is not None:
            map_data["center"] = center
        if zoom is not None:
            map_data["zoom"] = zoom

        self._schedule_save()
        print(f"[MapService] 视图已更新: center={map_data['center']}, zoom={map_data['zoom']}")
        return map_data

    def update_theme(self, map_id: str, theme: str) -> dict:
        """更新地图底图主题

        Args:
            map_id: 地图ID
            theme: 主题名称（standard/positron/dark/satellite）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图不存在或主题不支持
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        if theme not in MAP_THEMES:
            raise MapGenerationError(
                f"不支持的主题: {theme}，支持的主题: {list(MAP_THEMES.keys())}"
            )

        map_data["theme"] = theme
        self._schedule_save()
        print(f"[MapService] 主题已更新: {theme} ({MAP_THEMES[theme]['name']})")
        return map_data

    def add_feature(
        self,
        map_id: str,
        layer_id: str,
        feature_type: str,
        coordinates: Any,
        properties: Optional[dict] = None,
    ) -> dict:
        """向图层添加单个要素

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            feature_type: 要素类型（marker/polyline/polygon）
            coordinates: 要素坐标
                - marker: [lat, lng]
                - polyline/polygon: [[lat, lng], [lat, lng], ...]
            properties: 要素属性（可选）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图或图层不存在
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                layer["coordinates"].append(coordinates)
                # 如果图层类型与新要素类型不一致，更新图层类型
                if feature_type and layer["type"] != feature_type:
                    layer["type"] = feature_type
                self._schedule_save()
                print(f"[MapService] 要素已添加到图层: {layer_id}")
                return map_data

        raise MapGenerationError(f"图层不存在: {layer_id}")

    def remove_feature(self, map_id: str, layer_id: str, feature_id: str) -> dict:
        """从图层移除要素

        通过要素索引（feature_id格式为"index:N"）移除指定要素。

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            feature_id: 要素ID（索引格式 "index:0"）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图、图层或要素不存在
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                # 解析要素索引
                try:
                    if feature_id.startswith("index:"):
                        index = int(feature_id.split(":")[1])
                    else:
                        index = int(feature_id)
                except (ValueError, IndexError):
                    raise MapGenerationError(f"无效的要素ID: {feature_id}")

                if 0 <= index < len(layer["coordinates"]):
                    layer["coordinates"].pop(index)
                    self._schedule_save()
                    print(f"[MapService] 要素已移除: {feature_id}")
                    return map_data
                else:
                    raise MapGenerationError(f"要素索引超出范围: {index}")

        raise MapGenerationError(f"图层不存在: {layer_id}")

    # ==================== 内部辅助方法 ====================


    def _generate_thematic_layers(self, map_type: str, region: str, center: List[float]) -> List[dict]:
        """生成专题地图图层数据"""
        from app.core.constants import THEMATIC_MAP_CONFIG
        import random
        if map_type == "terrain":
            return self._generate_terrain_layers(region, center)
        config = THEMATIC_MAP_CONFIG.get(map_type, {})
        if not config:
            return []
        layers = []
        cs = config.get("color_scheme", ["#3388ff"])
        rt = config.get("render_type", "choropleth")
        lid = generate_id("layer")
        def rp(o=0.06):
            return [center[0] + random.uniform(-o, o), center[1] + random.uniform(-o, o)]
        if rt == "heatmap":
            pts = []
            for _ in range(120):
                p = rp(0.08)
                pts.append([p[0], p[1], random.uniform(0.2, 1.0)])
            layers.append({"id": lid, "type": "heatmap", "name": config.get("name", "热力图"), "coordinates": pts, "style": {"color_scheme": cs, "radius": 35, "blur": 25, "maxZoom": 17, "minOpacity": 0.3}, "metadata": {"render_type": "heatmap", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "point_count": len(pts)}})
        elif rt == "proportional_symbol":
            feats = []
            for i in range(60):
                p = rp(0.07)
                v = random.uniform(10, 100)
                s = 5 + (v / 100) * 25
                ci = min(int(v / 20), len(cs) - 1)
                feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"value": round(v, 1), "name": f"点{i+1}", "size": round(s, 1)}, "style": {"color": cs[ci], "radius": s, "fillOpacity": 0.7, "weight": 1}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "比例符号图"), "features": feats, "style": {"color_scheme": cs, "render_type": "proportional_symbol"}, "metadata": {"render_type": "proportional_symbol", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "feature_count": len(feats)}})
        elif rt == "choropleth":
            feats = []
            gs = 8
            off = 0.08
            step = (off * 2) / gs
            for i in range(gs):
                for j in range(gs):
                    lat = center[0] - off + i * step
                    lng = center[1] - off + j * step
                    v = random.uniform(0, 100)
                    ci = min(int(v / (100 / len(cs))), len(cs) - 1)
                    coords = [[lat, lng], [lat + step, lng], [lat + step, lng + step], [lat, lng + step], [lat, lng]]
                    feats.append({"id": generate_id("feat"), "type": "polygon", "coordinates": coords, "properties": {"value": round(v, 1), "grid_id": f"{i}_{j}"}, "style": {"color": cs[ci], "fillColor": cs[ci], "fillOpacity": 0.6, "weight": 0.5, "opacity": 0.3}})
            layers.append({"id": lid, "type": "polygon", "name": config.get("name", "分级色彩图"), "features": feats, "style": {"color_scheme": cs, "render_type": "choropleth"}, "metadata": {"render_type": "choropleth", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "grid_size": f"{gs}x{gs}", "feature_count": len(feats)}})
        elif rt == "categorical":
            feats = []
            if isinstance(cs, dict):
                cats = list(cs.keys())
                for i in range(80):
                    p = rp(0.07)
                    cat = random.choice(cats)
                    feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"category": cat, "name": cat}, "style": {"color": cs[cat], "fillColor": cs[cat], "radius": 6, "fillOpacity": 0.8, "weight": 1}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "分类图"), "features": feats, "style": {"color_scheme": cs, "render_type": "categorical"}, "metadata": {"render_type": "categorical", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "categories": list(cs.keys()) if isinstance(cs, dict) else [], "feature_count": len(feats)}})
        elif rt == "graduated":
            feats = []
            for i in range(70):
                p = rp(0.07)
                v = random.uniform(0, 50)
                if v < 10: s, col = 4, cs[0]
                elif v < 20: s, col = 8, cs[1] if len(cs) > 1 else cs[0]
                elif v < 30: s, col = 14, cs[2] if len(cs) > 2 else cs[-1]
                elif v < 40: s, col = 20, cs[3] if len(cs) > 3 else cs[-1]
                else: s, col = 28, cs[-1]
                feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"value": round(v, 1), "level": int(v / 10)}, "style": {"color": col, "fillColor": col, "radius": s, "fillOpacity": 0.6, "weight": 1.5}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "分级符号图"), "features": feats, "style": {"color_scheme": cs, "render_type": "graduated"}, "metadata": {"render_type": "graduated", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "feature_count": len(feats)}})
        return layers

    def _generate_terrain_layers(self, region: str = "武汉市", center: Optional[List[float]] = None) -> List[dict]:
        """地形图（等高线）：陆地底图 + 计曲线/首曲线 + （水系/道路由通用流程叠加）。

        等高线数据来自 SRTM 30m DEM（tools/generate_contours.py 已做制图综合：
        舍谷-微小谷地锯齿化简、扩谷-典型弯曲保护、鞍部保持-鞍部邻域顶点保护，
        以及遇河/湖断开处理）。
        """
        from app.core.constants import CITY_BBOX
        from app.services.contour_service import ContourService
        layers = []

        # 陆地底图（米黄色，衬托等高线）
        bbox = CITY_BBOX.get(region, {})
        if bbox:
            land = [[bbox["min_lat"], bbox["min_lon"]], [bbox["min_lat"], bbox["max_lon"]],
                    [bbox["max_lat"], bbox["max_lon"]], [bbox["max_lat"], bbox["min_lon"]],
                    [bbox["min_lat"], bbox["min_lon"]]]
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": "陆地底图",
                "coordinates": [land],
                "style": {"fillColor": "#f2ead7", "fillOpacity": 0.85,
                          "color": "#e2d5b8", "weight": 0.5, "opacity": 0.6},
            })

        # 等高线（计曲线/首曲线）
        try:
            contour_layers = ContourService().get_contour_layers()
            layers.extend(contour_layers)
        except Exception as e:
            print(f"[MapService] 等高线图层加载失败: {e}")

        return layers

    def _generate_fallback_layers(self, map_type: str, region: str = "武汉市", center: Optional[List[float]] = None, zoom: Optional[int] = None) -> List[dict]:
        """生成本地回退图层（当OSM数据不可用时使用本地地标数据）

        对于武汉市使用WUHAN_LANDMARKS中的详细地标数据；
        对于其他城市，根据中心坐标生成模拟地标数据。

        Args:
            map_type: 地图类型
            region: 区域名称
            center: 中心坐标 [lat, lng]

        Returns:
            图层列表，包含地标的marker要素
        """
        # 根据地图类型筛选合适的地标
        type_filter = {
            "tourism": ["attraction", "scenic", "museum", "cultural"],
            "food": ["food"],
            "campus": ["university"],
            "traffic": ["landmark", "commercial"],
            "basic": None,  # None表示所有类型
        }
        filter_types = type_filter.get(map_type, None)

        markers = []

        if region == "武汉市":
            # 使用武汉详细地标数据
            for landmark in WUHAN_LANDMARKS:
                if filter_types is None or landmark["type"] in filter_types:
                    markers.append({
                        "name": landmark["name"],
                        "lat": landmark["lat"],
                        "lng": landmark["lng"],
                        "type": landmark["type"],
                    })
        else:
            # 其他城市：根据中心坐标生成模拟地标
            if center and len(center) == 2:
                base_lat, base_lng = center[0], center[1]
                # 模拟地标数据（围绕中心点分布）
                sim_landmarks = [
                    {"name": f"{region}中心地标", "lat": base_lat, "lng": base_lng, "type": "landmark"},
                    {"name": f"{region}博物馆", "lat": base_lat + 0.02, "lng": base_lng + 0.01, "type": "museum"},
                    {"name": f"{region}公园", "lat": base_lat - 0.015, "lng": base_lng + 0.02, "type": "scenic"},
                    {"name": f"{region}大学", "lat": base_lat + 0.025, "lng": base_lng - 0.015, "type": "university"},
                    {"name": f"{region}商业区", "lat": base_lat - 0.01, "lng": base_lng - 0.02, "type": "commercial"},
                    {"name": f"{region}美食街", "lat": base_lat + 0.015, "lng": base_lng + 0.025, "type": "food"},
                ]
                for landmark in sim_landmarks:
                    if filter_types is None or landmark["type"] in filter_types:
                        markers.append(landmark)

        if not markers:
            # 如果没有匹配的地标，至少返回所有地标
            if region == "武汉市":
                markers = [{"name": lm["name"], "lat": lm["lat"], "lng": lm["lng"], "type": lm["type"]} for lm in WUHAN_LANDMARKS]
            elif center:
                markers = [{"name": f"{region}中心", "lat": center[0], "lng": center[1], "type": "landmark"}]

        if not markers:
            return []

        # 旅游图使用分类标记（不同类型不同颜色和符号）
        if map_type == "tourism":
            cat_map = {
                "attraction": "scenic", "scenic": "scenic", "museum": "museum",
                "cultural": "cultural", "university": "university", "food": "food",
                "commercial": "commercial", "landmark": "landmark",
            }
            by_cat = {}
            for m in markers:
                cat = cat_map.get(m.get("type", "default"), "default")
                by_cat.setdefault(cat, []).append(m)

            layers = []
            for cat, items in by_cat.items():
                cfg = TOURISM_CATEGORIES.get(cat, TOURISM_CATEGORIES["default"])
                layers.append({
                    "id": generate_id("layer"),
                    "type": "circleMarker",
                    "name": cfg["name"],
                    "coordinates": [[m["lat"], m["lng"]] for m in items],
                    "properties": [{"name": m["name"], "category": cat} for m in items],
                    "style": {
                        "color": cfg["color"],
                        "fillColor": cfg.get("fillColor", cfg["color"]),
                        "fillOpacity": cfg.get("fillOpacity", 0.7),
                        "weight": cfg.get("weight", 2),
                        "radius": cfg.get("radius", 6),
                        "icon": cfg.get("icon", "📍"),
                    },
                })
            return layers

        # 交通图：生成模拟分级道路 + 铁路 + 地标
        if map_type == "traffic":
            layers = []
            if center and len(center) == 2:
                import random
                clat, clng = center[0], center[1]
                # 模拟各级道路
                road_templates = [
                    ("motorway", "高速公路", [[clat - 0.06, clng - 0.08], [clat - 0.02, clng - 0.03], [clat + 0.01, clng + 0.02], [clat + 0.05, clng + 0.07]]),
                    ("trunk", "主干道-南北", [[clat - 0.07, clng + 0.01], [clat - 0.03, clng + 0.005], [clat + 0.02, clng], [clat + 0.06, clng - 0.01]]),
                    ("primary", "主要道路-东西", [[clat + 0.005, clng - 0.09], [clat, clng - 0.04], [clat - 0.005, clng + 0.03], [clat - 0.01, clng + 0.08]]),
                    ("secondary", "次干道1", [[clat - 0.04, clng - 0.05], [clat - 0.01, clng - 0.02], [clat + 0.02, clng + 0.01]]),
                    ("secondary", "次干道2", [[clat + 0.03, clng - 0.06], [clat + 0.01, clng - 0.02], [clat - 0.01, clng + 0.04]]),
                    ("tertiary", "支路1", [[clat - 0.02, clng - 0.03], [clat, clng - 0.01], [clat + 0.01, clng + 0.02]]),
                    ("tertiary", "支路2", [[clat + 0.02, clng + 0.01], [clat + 0.03, clng + 0.03], [clat + 0.04, clng + 0.05]]),
                ]
                if zoom is None or zoom >= 13:
                    road_templates += [
                        ("residential", "社区道路1", [[clat - 0.01, clng - 0.01], [clat + 0.005, clng + 0.005]]),
                        ("residential", "社区道路2", [[clat + 0.01, clng - 0.02], [clat + 0.02, clng - 0.01]]),
                    ]
                # 按道路等级分组渲染
                by_class = {}
                for rtype, rname, rcoords in road_templates:
                    by_class.setdefault(rtype, []).append({"coords": rcoords, "name": rname})
                sorted_classes = sorted(
                    by_class.items(),
                    key=lambda x: ROAD_CLASSIFICATION.get(x[0], {}).get("level", 99)
                )
                for road_class, items in sorted_classes:
                    cfg = ROAD_CLASSIFICATION.get(road_class, ROAD_CLASSIFICATION["default"])
                    if "outer" in cfg:
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(外层)",
                            "coordinates": [item["coords"] for item in items],
                            "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                            "style": dict(cfg["outer"]),
                        })
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(内层)",
                            "coordinates": [item["coords"] for item in items],
                            "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                            "style": dict(cfg["inner"]),
                        })
                    else:
                        style = {k: v for k, v in cfg.items() if k not in ("name", "level")}
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": cfg["name"],
                            "coordinates": [item["coords"] for item in items],
                            "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                            "style": dict(style),
                        })
                # 模拟铁路
                rail_coords = [[clat - 0.05, clng + 0.06], [clat - 0.02, clng + 0.04], [clat + 0.02, clng + 0.02], [clat + 0.06, clng - 0.02]]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "普通铁路(外层)",
                    "coordinates": [rail_coords],
                    "style": dict(RAILWAY_CLASSIFICATION["rail"]["outer"]),
                })
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "普通铁路(内层)",
                    "coordinates": [rail_coords],
                    "style": dict(RAILWAY_CLASSIFICATION["rail"]["inner"]),
                })
                # 地铁
                subway_coords = [[clat - 0.03, clng - 0.06], [clat, clng - 0.02], [clat + 0.03, clng + 0.03]]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "地铁",
                    "coordinates": [subway_coords],
                    "style": {k: v for k, v in RAILWAY_CLASSIFICATION["subway"].items() if k != "name"},
                })
            # 添加地标标记
            if markers:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "circleMarker",
                    "name": "交通枢纽",
                    "coordinates": [[m["lat"], m["lng"]] for m in markers],
                    "properties": [{"name": m["name"], "category": "landmark"} for m in markers],
                    "style": {
                        "color": TOURISM_CATEGORIES["landmark"]["color"],
                        "fillColor": TOURISM_CATEGORIES["landmark"]["fillColor"],
                        "fillOpacity": 0.8, "weight": 2, "radius": 7,
                        "icon": TOURISM_CATEGORIES["landmark"]["icon"],
                        "iconClass": TOURISM_CATEGORIES["landmark"].get("iconClass"),
                    },
                })
            return layers

        # 基础地图：生成模拟道路 + 建筑物面状要素 + 水系 + 地标
        if map_type == "basic":
            layers = []
            if center and len(center) == 2:
                import random
                clat, clng = center[0], center[1]
                # 模拟主要道路
                road_templates = [
                    ("motorway", "高速公路", [[clat - 0.06, clng - 0.08], [clat - 0.02, clng - 0.03], [clat + 0.05, clng + 0.07]]),
                    ("primary", "主要道路", [[clat - 0.07, clng + 0.01], [clat + 0.06, clng - 0.01]]),
                    ("secondary", "次干道", [[clat + 0.005, clng - 0.09], [clat - 0.01, clng + 0.08]]),
                    ("tertiary", "支路", [[clat - 0.02, clng - 0.03], [clat + 0.01, clng + 0.02]]),
                ]
                by_class = {}
                for rtype, rname, rcoords in road_templates:
                    by_class.setdefault(rtype, []).append({"coords": rcoords, "name": rname})
                for road_class, items in by_class.items():
                    cfg = ROAD_CLASSIFICATION.get(road_class, ROAD_CLASSIFICATION["default"])
                    if "outer" in cfg:
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(外层)",
                            "coordinates": [item["coords"] for item in items],
                            "style": dict(cfg["outer"]),
                        })
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(内层)",
                            "coordinates": [item["coords"] for item in items],
                            "style": dict(cfg["inner"]),
                        })
                    else:
                        style = {k: v for k, v in cfg.items() if k not in ("name", "level")}
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": cfg["name"],
                            "coordinates": [item["coords"] for item in items],
                            "style": dict(style),
                        })
                # 模拟河流
                river_coords = [[clat - 0.08, clng - 0.02], [clat - 0.04, clng + 0.01], [clat, clng + 0.03], [clat + 0.04, clng + 0.05], [clat + 0.08, clng + 0.06]]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "河流",
                    "coordinates": [river_coords],
                    "style": {k: v for k, v in WATERWAY_STYLES["river"].items() if k != "name"},
                })
                # 模拟建筑物面状要素
                building_templates = [
                    ("residential", "住宅小区", clat + 0.02, clng - 0.03, 0.008),
                    ("residential", "居民楼", clat - 0.03, clng + 0.04, 0.006),
                    ("commercial", "商业中心", clat + 0.01, clng + 0.05, 0.01),
                    ("public", "政府大楼", clat - 0.01, clng - 0.05, 0.008),
                    ("school", "学校", clat + 0.04, clng - 0.02, 0.012),
                    ("hospital", "医院", clat - 0.04, clng - 0.01, 0.01),
                ]
                by_btype = {}
                for btype, bname, blat, blng, bsize in building_templates:
                    coords = [
                        [blat - bsize, blng - bsize],
                        [blat - bsize, blng + bsize],
                        [blat + bsize, blng + bsize],
                        [blat + bsize, blng - bsize],
                        [blat - bsize, blng - bsize],
                    ]
                    by_btype.setdefault(btype, []).append({"coords": coords, "name": bname})
                for btype, items in by_btype.items():
                    style = BUILDING_STYLES.get(btype, BUILDING_STYLES["default"])
                    layers.append({
                        "id": generate_id("layer"),
                        "type": "polygon",
                        "name": style["name"],
                        "coordinates": [item["coords"] for item in items],
                        "properties": [{"name": item["name"], "subtype": btype} for item in items],
                        "style": {
                            "color": style["color"],
                            "fillColor": style["fillColor"],
                            "fillOpacity": style["fillOpacity"],
                            "weight": style["weight"],
                        },
                    })
                # 模拟公园
                park_coords = [
                    [clat + 0.05, clng + 0.02],
                    [clat + 0.05, clng + 0.06],
                    [clat + 0.02, clng + 0.06],
                    [clat + 0.02, clng + 0.02],
                    [clat + 0.05, clng + 0.02],
                ]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polygon",
                    "name": "公园",
                    "coordinates": [park_coords],
                    "properties": [{"name": "城市公园", "subtype": "park"}],
                    "style": {
                        "color": GREENSPACE_STYLES["park"]["color"],
                        "fillColor": GREENSPACE_STYLES["park"]["fillColor"],
                        "fillOpacity": GREENSPACE_STYLES["park"]["fillOpacity"],
                        "weight": GREENSPACE_STYLES["park"]["weight"],
                    },
                })
            # 添加地标标记
            if markers:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "circleMarker",
                    "name": "地标建筑",
                    "coordinates": [[m["lat"], m["lng"]] for m in markers],
                    "properties": [{"name": m["name"], "category": m.get("type", "landmark")} for m in markers],
                    "style": {
                        "color": TOURISM_CATEGORIES["landmark"]["color"],
                        "fillColor": TOURISM_CATEGORIES["landmark"]["fillColor"],
                        "fillOpacity": 0.8, "weight": 2, "radius": 6,
                        "icon": TOURISM_CATEGORIES["landmark"]["icon"],
                        "iconClass": TOURISM_CATEGORIES["landmark"].get("iconClass"),
                    },
                })
            return layers

        # 行政区划图：离线回退时生成模拟省/市/区边界，避免只有地标点
        if map_type == "administrative":
            layers = []
            if center and len(center) == 2:
                clat, clng = center[0], center[1]

                def _box(half):
                    return [[clat - half, clng - half], [clat - half, clng + half],
                            [clat + half, clng + half], [clat + half, clng - half],
                            [clat - half, clng - half]]

                for name, color, weight, half, dash in [
                    ("省界(周边外省)", "#000000", 1.2, 0.35, "1,4"),
                    ("地级市界", "#7040A0", 3.2, 0.22, None),
                    ("区县界", "#000000", 1.5, 0.10, "7,3,1,3"),
                ]:
                    _style = {"color": color, "weight": weight, "opacity": 0.9}
                    if dash:
                        _style["dashArray"] = dash
                    layers.append({
                        "id": generate_id("layer"), "type": "polyline", "name": name,
                        "coordinates": [_box(half)],
                        "style": _style,
                    })
                layers.append({
                    "id": generate_id("layer"), "type": "polyline", "name": "乡镇界",
                    "coordinates": [
                        [[clat - 0.10, clng], [clat + 0.10, clng]],
                        [[clat, clng - 0.10], [clat, clng + 0.10]],
                    ],
                    "style": {"color": "#000000", "weight": 0.8, "opacity": 0.6, "dashArray": "2,3"},
                })
            # 行政区名称标注（武汉区县中心兜底）
            if region == "武汉市":
                layers.append({
                    "id": generate_id("layer"),
                    "type": "textLabel",
                    "name": "区县名称标注",
                    "coordinates": [[d["lat"], d["lng"]] for d in WUHAN_DISTRICTS],
                    "properties": [{"name": d["name"]} for d in WUHAN_DISTRICTS],
                    "style": {"color": "#1e3a8a", "fontSize": 15, "weight": 3},
                })
            return layers

        # 其他地图类型保持原有逻辑
        layer_style = MAP_STYLES.get("amenity", {"color": "#f59e0b", "radius": 6})
        return [{
            "id": generate_id("layer"),
            "type": "marker",
            "name": f"{region}地标（本地数据）",
            "coordinates": [[m["lat"], m["lng"]] for m in markers],
            "properties": [{"name": m["name"], "type": m["type"]} for m in markers],
            "style": layer_style,
        }]

    @staticmethod
    def _district_area(layers: List[dict]) -> float:
        """计算区县政区面的球面总面积（km²），用于质量校验"""
        import math
        R = 6371.0
        total = 0.0
        for layer in layers:
            if layer.get("name") != "区县政区":
                continue
            for feat in layer.get("features", []):
                ring = feat.get("coordinates") or []
                if len(ring) < 3:
                    continue
                area = 0.0
                n = len(ring)
                for i in range(n):
                    j = (i + 1) % n
                    lat1 = math.radians(ring[i][0])
                    lon1 = math.radians(ring[i][1])
                    lat2 = math.radians(ring[j][0])
                    lon2 = math.radians(ring[j][1])
                    area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
                total += abs(area * R * R / 2.0)
        return round(total, 2)

    def add_custom_marker(self, map_id: str, name: str, lat: float, lng: float,
                          icon: str = None, color: str = "#e11d48") -> dict:
        """添加自定义标注点（答辩演示：标注赏樱点/卫生间等自定义点位）

        自动创建/复用"自定义标注"circleMarker图层。
        """
        map_data = self.maps.get(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        layer = None
        for L in map_data["layers"]:
            if L.get("name") == "自定义标注":
                layer = L
                break
        if layer is None:
            layer = {
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": "自定义标注",
                "coordinates": [],
                "properties": [],
                "style": {"color": color, "fillColor": "#ffffff", "fillOpacity": 1.0,
                          "radius": 7, "weight": 2.5, "icon": icon or "\U0001f4cd"},
            }
            map_data["layers"].append(layer)
        layer["coordinates"].append([lat, lng])
        layer["properties"].append({"name": name})
        map_data["layers"] = self._sort_layers(map_data["layers"])
        self._schedule_save()
        print(f"[MapService] 已添加自定义标注: {name} ({lat},{lng})")
        return map_data

    def _sort_layers(self, layers: List[dict]) -> List[dict]:
        """按制图规范调整图层叠置顺序

        面状底图（绿地/用地/水体）→ 建筑面 → 水系线 → 铁路 → 道路 → 点状符号。
        高等级道路最后绘制（位于顶层），保证主干道视觉突出；
        采用稳定排序，同层要素保持原有相对顺序。
        """
        road_rank = {
            "高速公路": 90, "国道": 80, "主干道": 80, "省道": 70, "主要道路": 70,
            "次干道": 60, "支路": 50, "社区道路": 40, "服务道路": 30, "其他道路": 20,
        }

        def zkey(layer: dict) -> int:
            t = layer.get("type", "")
            name = layer.get("name", "")
            if t in ("polygon", "area"):
                if "陆地" in name:
                    return 0
                if any(k in name for k in ("水体", "湖泊", "水库")):
                    return 50
                if any(k in name for k in ("用地", "绿地", "公园", "花园", "森林", "草地",
                                           "草甸", "土地", "政区", "区划")):
                    return 100
                if any(k in name for k in ("建筑", "住宅", "公寓", "宿舍", "商业", "零售", "酒店",
                                           "工业", "公共", "政府", "学校", "大学", "医院", "宗教",
                                           "文化", "体育", "停车", "车库", "仓储", "交通枢纽",
                                           "农业", "温室")):
                    return 200
                return 100
            if t in ("polyline", "line"):
                if any(k in name for k in ("水系", "河流", "溪流", "运河", "湖泊", "水库")):
                    return 300
                if "边界" in name:
                    return 350
                if any(k in name for k in ("铁路", "地铁", "轻轨", "高铁")):
                    return 400
                rank = next((r for k, r in road_rank.items() if k in name), 10)
                return 500 + rank
            if t in ("textLabel", "label"):
                return 650
            return 600

        return sorted(layers, key=zkey)

    def _generate_legend(self, map_type: str, map_layers: List[dict]) -> dict:
        """根据地图类型和图层生成图例数据

        优先使用LEGEND_TEMPLATES中的预设模板，并根据实际图层过滤；
        若无模板则从图层数据动态生成。

        Args:
            map_type: 地图类型
            map_layers: 图层列表

        Returns:
            图例字典 {title, items: [{label, type, color, ...}]}
        """
        # 收集实际存在的图层名称（去除"(外层)""(内层)"后缀）
        actual_names = set()
        actual_styles = {}
        for layer in map_layers:
            name = layer.get("name", "")
            # 去除后缀得到基础名称
            base_name = name.replace("(外层)", "").replace("(内层)", "").strip()
            actual_names.add(base_name)
            actual_styles[base_name] = layer.get("style", {})

        # 优先使用预设模板（根据实际图层过滤）
        if map_type in LEGEND_TEMPLATES:
            template = LEGEND_TEMPLATES[map_type]
            filtered_items = []
            for item in template["items"]:
                label = item.get("label", "")
                # 对交通图等模板：仅保留实际存在的图层对应的图例项
                if map_type in ("traffic", "basic", "campus", "administrative"):
                    if label in actual_names:
                        filtered_items.append(item)
                else:
                    # 其他类型保留全部图例项
                    filtered_items.append(item)

            # 如果过滤后为空（可能名称不完全匹配），回退到全部模板项
            if not filtered_items:
                filtered_items = template["items"]

            # 补充实际存在但模板未覆盖的图层项（POI象形符号/线/面），保证整套图例完整
            covered = {it.get("label") for it in filtered_items}
            for layer in map_layers:
                base_name = layer.get("name", "").replace("(外层)", "").replace("(内层)", "").strip()
                if base_name in covered:
                    continue
                style = layer.get("style", {})
                ltype = layer.get("type", "")
                if ltype in ("circleMarker", "marker", "point") and style.get("icon"):
                    filtered_items.append({
                        "label": base_name, "type": "point",
                        "color": style.get("color", "#f59e0b"),
                        "icon": style.get("icon", "\U0001f4cd"),
                        "iconClass": style.get("iconClass"),
                        "radius": style.get("radius", 6),
                        "group": style.get("group", "兴趣点(POI)"),
                    })
                elif ltype in ("textLabel", "label"):
                    filtered_items.append({
                        "label": base_name, "type": "point",
                        "color": style.get("color", "#1e3a8a"),
                        "icon": "\U0001f3f7\ufe0f",
                        "group": "行政区划",
                    })
                elif ltype in ("polygon", "area"):
                    filtered_items.append({
                        "label": base_name, "type": "polygon",
                        "fillColor": style.get("fillColor", style.get("color", "#3388ff")),
                        "color": style.get("color", "#3388ff"),
                        "fillOpacity": style.get("fillOpacity", 0.3),
                    })
                elif ltype in ("polyline", "line"):
                    filtered_items.append({
                        "label": base_name, "type": "line",
                        "color": style.get("color", "#3388ff"),
                        "weight": style.get("weight", 3),
                        "dashArray": style.get("dashArray"),
                    })
                covered.add(base_name)

            return {"title": template["title"], "items": filtered_items}

        # 动态生成：从图层数据中提取图例项
        legend_items = []
        seen_labels = set()
        for layer in map_layers:
            name = layer.get("name", "")
            # 去除后缀，避免"外层""内层"生成重复图例
            base_name = name.replace("(外层)", "").replace("(内层)", "").strip()
            if base_name in seen_labels:
                continue
            style = layer.get("style", {})
            ltype = layer.get("type", "")

            if ltype in ("polyline", "line"):
                legend_items.append({
                    "label": base_name, "type": "line",
                    "color": style.get("color", "#3388ff"),
                    "weight": style.get("weight", 3),
                    "dashArray": style.get("dashArray"),
                })
            elif ltype in ("polygon", "area"):
                legend_items.append({
                    "label": base_name, "type": "polygon",
                    "fillColor": style.get("fillColor", style.get("color", "#3388ff")),
                    "color": style.get("color", "#3388ff"),
                    "fillOpacity": style.get("fillOpacity", 0.3),
                })
            elif ltype in ("circleMarker", "marker", "point", "circle"):
                legend_items.append({
                    "label": base_name, "type": "point",
                    "color": style.get("color", "#f59e0b"),
                    "icon": style.get("icon", "📍"),
                    "iconClass": style.get("iconClass"),
                    "radius": style.get("radius", 6),
                    "group": style.get("group", "兴趣点(POI)"),
                })
            seen_labels.add(base_name)

        return {"title": f"图例（{len(legend_items)}项）", "items": legend_items}

    def _elements_to_layers(
        self,
        elements_by_type: Dict[str, List[dict]],
        element_types: List[str],
    ) -> List[dict]:
        """将OSM元素按类型转换为图层列表（增强版）

        按要素类型分发到专用处理器，支持：
        - 建筑物面状渲染（按类型分色）
        - 道路分级渲染（主要道路双层渲染）
        - 铁路分类渲染
        - 水系分类渲染
        - 旅游地分类标记（不同颜色和符号）
        - 绿地面状渲染

        Args:
            elements_by_type: 按类型分组的OSM元素字典
            element_types: 要素类型列表

        Returns:
            图层列表
        """
        layers = []
        # 水系类型（waterway_major/waterway_minor等）合并为一次处理，
        # 保证河源/汇入口检测能同时看到主河与支流
        _water_merged = False

        for typ in element_types:
            base_tag = typ.split("~")[0]
            elements = elements_by_type.get(base_tag, [])
            if not elements:
                continue
            if base_tag.startswith("waterway"):
                if _water_merged:
                    continue
                _water_merged = True
                merged = []
                for _t in element_types:
                    if _t.split("~")[0].startswith("waterway"):
                        merged.extend(elements_by_type.get(_t, []))
                elements = merged

            way_elements = [e for e in elements if e.get("type") == "way"]
            node_elements = [e for e in elements if e.get("type") == "node"]
            other_elements = [e for e in elements if e.get("type") not in ("way", "node")]
            way_elements.extend(other_elements)

            # 按要素类型分发到专用处理器
            if base_tag == "building":
                layers.extend(self._process_buildings(way_elements))
            elif base_tag.startswith("highway"):
                layers.extend(self._process_roads(way_elements))
            elif base_tag == "railway":
                layers.extend(self._process_railways(way_elements))
            elif base_tag.startswith("waterway"):
                layers.extend(self._process_waterways(way_elements))
            elif base_tag == "boundary":
                layers.extend(self._process_boundaries(way_elements))
            elif base_tag in ("place", "place_city", "place_suburb"):
                layers.extend(self._process_place_labels(node_elements))
            elif base_tag in ("tourism", "historic", "amenity", "shop", "office"):
                layers.extend(self._process_poi(node_elements, way_elements, base_tag))
            elif base_tag in ("landuse", "natural"):
                layers.extend(self._process_landuse(way_elements))
            elif base_tag == "leisure":
                layers.extend(self._process_greenspace(way_elements))
            else:
                layers.extend(self._process_default(way_elements, node_elements, base_tag))

        return layers

    # ==================== 要素分类处理方法 ====================

    def _process_buildings(self, way_elements: List[dict]) -> List[dict]:
        """处理建筑物要素 - 面状渲染，按类型分色"""
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 3:
                continue
            # 确保面状闭合
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            tags = elem.get("tags", {})
            btype = self._classify_building(tags)
            name = tags.get("name", "")
            by_type.setdefault(btype, []).append({"coords": coords, "name": name})

        layers = []
        for btype, items in by_type.items():
            style = BUILDING_STYLES.get(btype, BUILDING_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": style["name"],
                "coordinates": [item["coords"] for item in items],
                "properties": [{"name": item["name"], "subtype": btype} for item in items],
                "style": {
                    "color": style["color"],
                    "fillColor": style["fillColor"],
                    "fillOpacity": style["fillOpacity"],
                    "weight": style["weight"],
                },
            })
        return layers

    def _classify_building(self, tags: dict) -> str:
        """根据OSM标签判断建筑物子类型

        优先级：building标签 → amenity标签 → 属性标签推断。
        amenity类别的建筑用途通过映射归入对应建筑大类，保证分类完整。
        """
        bval = tags.get("building", "yes")
        if bval != "yes" and bval in BUILDING_STYLES:
            return bval
        # 检查amenity标签推断建筑类型
        amenity = tags.get("amenity", "")
        if amenity in BUILDING_STYLES:
            return amenity
        amenity_fallback = {
            "restaurant": "commercial", "cafe": "commercial", "fast_food": "commercial",
            "bar": "commercial", "pub": "commercial", "bank": "commercial",
            "pharmacy": "commercial", "fuel": "commercial", "marketplace": "retail",
            "supermarket": "retail", "mall": "retail",
            "library": "public", "post_office": "public", "community_centre": "civic",
            "townhall": "government", "courthouse": "government",
            "police": "government", "fire_station": "government", "embassy": "government",
            "clinic": "hospital", "doctors": "hospital", "dentist": "hospital",
            "kindergarten": "school", "college": "university",
            "theatre": "civic", "cinema": "civic", "arts_centre": "civic",
            "events_venue": "civic", "stadium": "sports", "sports_centre": "sports",
            "gym": "sports", "place_of_worship": "religious",
            "hostel": "hotel", "motel": "hotel", "guest_house": "hotel",
            "transportation": "train_station", "bus_station": "train_station",
        }
        if amenity in amenity_fallback:
            return amenity_fallback[amenity]
        # 检查其他标签
        if tags.get("shop"):
            return "retail"
        if tags.get("office"):
            return "commercial"
        if tags.get("residential") == "yes":
            return "residential"
        if tags.get("commercial") == "yes":
            return "commercial"
        if tags.get("industrial") == "yes":
            return "industrial"
        return "default"

    def _process_roads(self, way_elements: List[dict]) -> List[dict]:
        """处理道路要素 - 按等级分级渲染，主要道路双层渲染"""
        by_class = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            highway_type = tags.get("highway", "default")
            if highway_type not in ROAD_CLASSIFICATION:
                highway_type = "default"
            name = tags.get("name", tags.get("ref", ""))
            by_class.setdefault(highway_type, []).append({"coords": coords, "name": name})

        layers = []
        # 按道路等级排序（高等级优先渲染，低等级在上层）
        sorted_classes = sorted(
            by_class.items(),
            key=lambda x: ROAD_CLASSIFICATION.get(x[0], {}).get("level", 99)
        )

        for road_class, items in sorted_classes:
            cfg = ROAD_CLASSIFICATION.get(road_class, ROAD_CLASSIFICATION["default"])

            if "outer" in cfg:
                # 主要道路双层渲染：外层（深色粗线）+ 内层（浅色细线）
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(外层)",
                    "coordinates": [item["coords"] for item in items],
                    "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                    "style": dict(cfg["outer"]),
                })
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(内层)",
                    "coordinates": [item["coords"] for item in items],
                    "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                    "style": dict(cfg["inner"]),
                })
            else:
                # 普通道路单层渲染
                style = {k: v for k, v in cfg.items() if k not in ("name", "level")}
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"],
                    "coordinates": [item["coords"] for item in items],
                    "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                    "style": dict(style),
                })
        return layers

    def _process_railways(self, way_elements: List[dict]) -> List[dict]:
        """处理铁路要素 - 按类型分类渲染"""
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            rtype = tags.get("railway", "default")
            if rtype not in RAILWAY_CLASSIFICATION:
                rtype = "default"
            # 高速铁路特殊判断
            if rtype == "rail" and tags.get("highspeed") == "yes":
                rtype = "high_speed"
            name = tags.get("name", "")
            by_type.setdefault(rtype, []).append({"coords": coords, "name": name})

        layers = []
        for rtype, items in by_type.items():
            cfg = RAILWAY_CLASSIFICATION.get(rtype, RAILWAY_CLASSIFICATION["default"])
            if "outer" in cfg:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(外层)",
                    "coordinates": [item["coords"] for item in items],
                    "style": dict(cfg["outer"]),
                })
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(内层)",
                    "coordinates": [item["coords"] for item in items],
                    "style": dict(cfg["inner"]),
                })
            else:
                style = {k: v for k, v in cfg.items() if k != "name"}
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"],
                    "coordinates": [item["coords"] for item in items],
                    "style": dict(style),
                })
        return layers

    def _fallback_water_layers(self, region: str, surrounding_only: bool = False) -> List[dict]:
        """本地水系底图：长江/汉江干流折线 + 全图幅主要湖泊面 + 蓝色水系注记

        图幅包含武汉及周边地市（规范底图要素：长江/汉江/湖泊构成水路底图）。
        OSM 水系抓取缺失时补全图幅；OSM 已有武汉水系时只补周边地市水系（surrounding_only）。
        """
        import math
        layers = []
        rivers = WUHAN_WATER_FALLBACK.get("rivers", [])
        lakes = list(WUHAN_WATER_FALLBACK.get("lakes", []))
        if surrounding_only:
            # 只补周边地市水系（武汉核心湖泊已由OSM精细数据提供，避免重叠）
            core = {"东湖", "汤逊湖", "梁子湖", "涨渡湖", "后官湖", "金银湖", "严西湖", "青菱湖"}
            lakes = [lk for lk in lakes if lk["name"] not in core]
        if rivers:
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": "河流干流",
                "coordinates": [r["coords"] for r in rivers],
                "properties": [{"name": r["name"], "subtype": "river"} for r in rivers],
                "style": {"color": "#1e90ff", "weight": 2.6, "opacity": 0.9},
            })
        lake_polys = []
        lake_labels = []
        for lk in lakes:
            coords = lk.get("coords") or []
            if len(coords) < 3:
                continue
            lake_polys.append({"coords": coords, "name": lk["name"]})
            # 大湖标注名称（质心位置），小湖不标避免文字压面外
            if lk.get("label", False):
                _c0 = sum(p[0] for p in coords) / len(coords)
                _c1 = sum(p[1] for p in coords) / len(coords)
                lake_labels.append({"coords": [_c0, _c1], "name": lk["name"]})
        if lake_polys:
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": "湖泊",
                "coordinates": [p["coords"] for p in lake_polys],
                "properties": [{"name": p["name"], "subtype": "lake"} for p in lake_polys],
                "style": {"fillColor": "#1e90ff", "fillOpacity": 0.5,
                          "color": "#1e90ff", "weight": 1.2, "opacity": 0.8},
            })
        if lake_labels:
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": "水系注记" if not surrounding_only else "水系注记(周边)",
                "coordinates": [l["coords"] for l in lake_labels],
                "properties": [{"name": l["name"], "rotation": 0} for l in lake_labels],
                "style": {"color": "#2E6FA3", "fontSize": 12, "weight": 2, "font": "song"},
            })
        return layers

    def _process_waterways(self, way_elements: List[dict]) -> List[dict]:
        """处理水系要素 - 单线河由细到粗渐变，注记沿河道布局

        制图规范：
        - 单线河符号由细到粗渐变（河源细线→干流粗线），体现上下游关系；
        - 河源生成"河源"点状符号；支流汇入主河/湖泊处生成"汇入口"符号，
          汇入口定位于主河曲率最大处的顶点（水涯线在曲率最大处相交）；
        - 湖泊水库按蓝色面渲染；主要河流生成沿河道方向的注记（字头顺流向）。
        """
        import math
        tiers = {}          # tier_index -> [segment_coords,...]
        tier_names = ["河源细流", "上游河道", "中游河道", "下游河道", "干流主河道"]
        # 规范一-2：水系统一蓝色#4088C8，河流等级越高线条越粗（干流≈0.5mm/2.4px）
        tier_weights = [1.2, 1.6, 2.0, 2.4, 2.8]
        tier_colors = ["#1e90ff", "#1e90ff", "#1e90ff", "#1e90ff", "#1e90ff"]
        minor = []
        river_lines = []    # {"coords": [...], "name": str}
        areas = {}
        labels = []
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            if "waterway" in tags:
                wtype = tags["waterway"]
            elif tags.get("natural") == "water":
                wtype = "lake"
            elif tags.get("landuse") == "reservoir":
                wtype = "reservoir"
            else:
                wtype = "default"
            name = tags.get("name", "")
            if wtype in ("lake", "reservoir") or tags.get("natural") == "water" or tags.get("landuse") == "reservoir":
                if coords[0] != coords[-1]:
                    coords = coords + [coords[0]]
                areas.setdefault(wtype, []).append({"coords": coords, "name": name})
                # 湖泊/水库名称注记：蓝色宋体，置于水面内部（规范四）
                if name:
                    _c0 = sum(p[0] for p in coords) / len(coords)
                    _c1 = sum(p[1] for p in coords) / len(coords)
                    labels.append({"coords": [_c0, _c1], "name": name, "rotation": 0})
            elif wtype == "river":
                n = len(coords)
                river_lines.append({"coords": coords, "name": name})
                # 按顶点数切分为 2~5 段渐变（权重/颜色逐级递增，体现上下游）
                ntier = 2 if n < 9 else (3 if n < 15 else (4 if n < 24 else 5))
                step = (n - 1) / max(1, ntier - 1)
                for t in range(ntier):
                    a = int(round(t * step))
                    b = int(round((t + 1) * step))
                    if b > n - 1:
                        b = n - 1
                    if a >= b:
                        continue
                    tiers.setdefault(t, []).append(coords[a:b + 1])
                if name:
                    c_idx = n // 2
                    p0 = coords[max(0, c_idx - 1)]
                    p1 = coords[min(n - 1, c_idx + 1)]
                    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
                    labels.append({"coords": coords[c_idx], "name": name, "rotation": round(ang)})
            else:
                minor.append({"coords": coords, "name": name})

        layers = []
        # ---- 河流渐变渲染（多级宽度/颜色渐变）----
        for t in sorted(tiers.keys()):
            segs = tiers[t]
            if not segs:
                continue
            layers.append({
                "id": generate_id("layer"), "type": "polyline",
                "name": tier_names[t] if t < len(tier_names) else "河道%d级" % (t + 1),
                "coordinates": segs,
                "style": {
                    "color": tier_colors[t], "weight": tier_weights[t],
                    "opacity": min(0.95, 0.85 + 0.03 * t),
                },
            })
        # ---- 支流溪流 ----
        if minor:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "支流溪流",
                "coordinates": [m["coords"] for m in minor],
                "properties": [{"name": m["name"]} for m in minor],
                "style": {"color": "#1e90ff", "weight": 1.0, "opacity": 0.75},
            })
        # ---- 面状水体（湖泊/水库，蓝色）----
        for wtype, items in areas.items():
            cfg = WATERWAY_STYLES.get(wtype, WATERWAY_STYLES["default"])
            layers.append({
                "id": generate_id("layer"), "type": "polygon", "name": cfg["name"],
                "coordinates": [it["coords"] for it in items],
                "properties": [{"name": it["name"], "subtype": wtype} for it in items],
                "style": {
                    "color": cfg.get("color", "#0ea5e9"),
                    "fillColor": cfg.get("fillColor", "#7dd3fc"),
                    "fillOpacity": cfg.get("fillOpacity", 0.4),
                    "weight": cfg.get("weight", 1),
                },
            })
        # ---- 河源符号（主河上游端点，蓝色水滴形符号）----
        springs = []
        for rl in river_lines:
            if len(rl["coords"]) >= 12:
                springs.append({"coords": rl["coords"][0], "name": rl["name"]})
                if len(springs) >= 10:
                    break
        if springs:
            scfg = WATER_SYMBOL_STYLES["spring"]
            layers.append({
                "id": generate_id("layer"), "type": "circleMarker", "name": "河源",
                "coordinates": [s["coords"] for s in springs],
                "properties": [{"name": (s["name"] + "河源") if s["name"] else "河源", "kind": "spring"} for s in springs],
                "style": {
                    "color": scfg["color"], "fillColor": scfg["fillColor"],
                    "fillOpacity": scfg["fillOpacity"], "weight": scfg["weight"],
                    "radius": scfg["radius"], "icon": scfg["icon"],
                    "iconClass": scfg["iconClass"], "kind": "spring", "group": "水系符号",
                },
            })
        # ---- 汇入口（支流端点→主河/湖泊；定位于主河曲率最大处）----
        confluences = self._detect_confluences(minor, river_lines, areas)
        if confluences:
            cfg = WATER_SYMBOL_STYLES["confluence"]
            layers.append({
                "id": generate_id("layer"), "type": "circleMarker", "name": "汇入口",
                "coordinates": [c["coords"] for c in confluences],
                "properties": [
                    {"name": c["name"], "kind": c["kind"], "target": c.get("target", "")}
                    for c in confluences
                ],
                "style": {
                    "color": cfg["color"], "fillColor": cfg["fillColor"],
                    "fillOpacity": cfg["fillOpacity"], "weight": cfg["weight"],
                    "radius": cfg["radius"], "icon": cfg["icon"],
                    "iconClass": cfg["iconClass"], "kind": "confluence", "group": "水系符号",
                },
            })
        # ---- 水系注记 ----
        if labels:
            seen = set()
            uniq = []
            for lb in labels:
                if lb["name"] in seen:
                    continue
                seen.add(lb["name"])
                uniq.append(lb)
                if len(uniq) >= 16:
                    break
            wcfg = LABEL_STYLES["water"]
            for lb in uniq:
                # 字头朝上：注记旋转角限制在[-60,60]，避免文字倒置
                rot = lb["rotation"]
                lb["rotation"] = max(-60, min(60, ((rot + 180) % 360) - 180 if rot > 90 or rot < -90 else rot))
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": "水系注记",
                "coordinates": [lb["coords"] for lb in uniq],
                "properties": [{"name": lb["name"], "rotation": lb["rotation"]} for lb in uniq],
                "style": {"color": wcfg["color"], "fontSize": wcfg["fontSize"],
                          "weight": wcfg["weight"], "font": wcfg["font"]},
            })
        return layers

    def _detect_confluences(self, minor_lines: List[dict], river_lines: List[dict], areas: dict) -> List[dict]:
        """检测支流汇入主河/湖泊的汇入口

        制图规范：汇入口与主河/湖/海的水涯线在曲率最大处相交。
        实现：支流端点贴近主河时，把汇入口定位到主河最近处曲率最大的顶点；
        支流端点落入湖泊/水库时生成入湖口。
        """
        import math
        tol = 0.004  # 约400m（局部小范围平面近似）
        results = []
        seen = set()
        for mline in minor_lines:
            coords = mline.get("coords", [])
            if not coords or len(coords) < 2:
                continue
            name = mline.get("name", "")
            for ep in (coords[0], coords[-1]):
                key = (round(ep[0], 4), round(ep[1], 4))
                if key in seen:
                    continue
                seen.add(key)
                # 1) 支流端点贴近主河 → 汇入口（定位到主河曲率最大处顶点）
                best = None
                for rl in river_lines:
                    rc = rl.get("coords", [])
                    for i in range(len(rc) - 1):
                        d = self._point_seg_dist(ep, rc[i], rc[i + 1])
                        if d < tol and (best is None or d < best[0]):
                            best = (d, rl)
                if best:
                    rl = best[1]
                    v = self._max_curvature_vertex(rl["coords"], ep, window=6)
                    results.append({
                        "coords": v,
                        "name": name or "支流汇入",
                        "kind": "confluence",
                        "target": rl.get("name", "主河"),
                    })
                    continue
                # 2) 支流端点落入湖泊/水库 → 入湖口
                matched = False
                for wtype in ("lake", "reservoir"):
                    for item in areas.get(wtype, []):
                        if _point_in_ring(ep, item["coords"]):
                            results.append({
                                "coords": ep,
                                "name": name or "河流入湖",
                                "kind": "to_lake",
                                "target": item.get("name", "湖泊"),
                            })
                            matched = True
                            break
                    if matched:
                        break
        return results

    def _point_seg_dist(self, p: list, a: list, b: list) -> float:
        """点到线段距离（经纬度平面近似，局部小范围足够）"""
        import math
        px, py = p[1], p[0]
        ax, ay = a[1], a[0]
        bx, by = b[1], b[0]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        return math.hypot(px - cx, py - cy)

    def _max_curvature_vertex(self, coords: list, near: list, window: int = 6) -> list:
        """在汇入点附近寻找河道曲率最大处的顶点

        曲率用相邻两段线段的转角绝对值近似（弧度）；
        汇入口与水涯线在曲率最大处相交。
        """
        import math
        n = len(coords)
        if n < 3:
            return near
        closest = min(range(n), key=lambda i: (coords[i][0] - near[0]) ** 2 + (coords[i][1] - near[1]) ** 2)
        lo, hi = max(1, closest - window), min(n - 2, closest + window)
        best_i, best_ang = closest, -1.0
        for i in range(lo, hi + 1):
            p0, p1, p2 = coords[i - 1], coords[i], coords[i + 1]
            a1 = math.atan2(p1[0] - p0[0], p1[1] - p0[1])
            a2 = math.atan2(p2[0] - p1[0], p2[1] - p1[1])
            d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            if abs(d) > best_ang:
                best_ang = abs(d)
                best_i = i
        return coords[best_i]

    def _process_place_labels(self, node_elements: List[dict]) -> List[dict]:
        """处理行政区划/地名标注 - 按行政级别分级排布

        城市(place=city)大号黑体、区县中号黑体、街道小号弱化；
        注记位置位于要素点右上方，字头朝上。
        """
        city, district, street = [], [], []
        for elem in node_elements:
            coords = self._extract_coordinates(elem, "marker")
            if not coords or not isinstance(coords, list) or len(coords) != 2:
                continue
            tags = elem.get("tags", {})
            name = tags.get("name", "")
            if not name:
                continue
            place = tags.get("place", "")
            # 城市标注仅收真正的城市（排除区/县名，防止与区县标注重复）
            if place == "city" and not name.endswith(("区", "县")):
                city.append({"coords": coords, "name": name})
            elif name.endswith(("区", "县")) or place in ("town", "borough"):
                district.append({"coords": coords, "name": name})
            else:
                street.append({"coords": coords, "name": name})

        layer_names = {"city": "城市名称标注", "district": "区县名称标注", "town": "街道地名标注"}
        layers = []
        for items, key in ((city, "city"), (district, "district"), (street, "town")):
            if not items:
                continue
            cfg = LABEL_STYLES[key]
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": layer_names[key],
                "coordinates": [d["coords"] for d in items],
                "properties": [{"name": d["name"]} for d in items],
                "style": {"color": cfg["color"], "fontSize": cfg["fontSize"],
                          "weight": cfg["weight"], "font": cfg["font"],
                          "center": key in ("city", "district")},
            })
        return layers

    def _process_boundaries(self, way_elements: List[dict]) -> List[dict]:
        """处理行政区划边界 - 按行政等级分级渲染（省/市/区县/乡镇）"""
        # 行政区划界线（国家标准地图规范）：已定界禁用虚线，区县界用点划线示意；按级别区分线型/线宽/颜色
        # 省级：黑色细点线(周边外省界线)；地级市界：紫色#7040A0粗实线；县级：黑色点划线；乡级：黑色细点线
        boundary_styles = {
            "4": {"name": "省界(周边外省)", "color": "#000000", "weight": 1.2, "opacity": 0.9, "dashArray": "1,4"},
            "6": {"name": "地级市界", "color": "#7040A0", "weight": 3.2, "opacity": 0.9},
            "8": {"name": "区县界", "color": "#000000", "weight": 1.5, "opacity": 0.9, "dashArray": "7,3,1,3"},
            "9": {"name": "乡镇界", "color": "#000000", "weight": 0.8, "opacity": 0.6, "dashArray": "2,3"},
        }
        by_level = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            level = str(tags.get("admin_level", ""))
            name = tags.get("name", "")
            by_level.setdefault(level, []).append({"coords": coords, "name": name})

        layers = []
        for level, items in by_level.items():
            cfg = boundary_styles.get(level, {"name": "其他边界", "color": "#FF6666", "weight": 1})
            inner_cfg = cfg.get("inner")
            # 外层
            style = {k: v for k, v in cfg.items() if k not in ("name", "inner")}
            style["osm_boundary"] = True  # 标记OSM来源界线，行政区划图按需过滤
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": cfg["name"] + ("(外层)" if inner_cfg else ""),
                "coordinates": [it["coords"] for it in items],
                "properties": [{"name": it["name"], "subtype": "boundary", "admin_level": level} for it in items],
                "style": style,
            })
            # 内层（双线表达：浅色中心线，增强视觉层次）
            if inner_cfg:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"] + "(内层)",
                    "coordinates": [it["coords"] for it in items],
                    "properties": [{"name": it["name"], "subtype": "boundary", "admin_level": level} for it in items],
                    "style": dict(inner_cfg),
                })
        return layers

    def _classify_poi(self, tags: dict, base_tag: str) -> str:
        """将OSM标签归类为POI象形符号分类

        优先级：tourism > amenity > shop > office > leisure > historic
        """
        t = tags.get("tourism", "")
        if t:
            return {"attraction": "attraction", "museum": "museum", "viewpoint": "scenic",
                    "hotel": "hotel", "guest_house": "hotel", "theme_park": "park",
                    "zoo": "park", "artwork": "museum"}.get(t, "attraction")
        a = tags.get("amenity", "")
        if a:
            return {
                "restaurant": "restaurant", "cafe": "cafe", "fast_food": "fast_food",
                "bar": "bar", "pub": "pub", "biergarten": "bar", "nightclub": "bar",
                "hospital": "hospital", "clinic": "clinic", "doctors": "clinic",
                "dentist": "clinic", "veterinary": "clinic", "pharmacy": "pharmacy",
                "school": "school", "university": "university", "college": "university",
                "kindergarten": "kindergarten", "library": "library",
                "bank": "bank", "atm": "atm", "bureau_de_change": "bank",
                "police": "police", "fire_station": "fire", "post_office": "post",
                "townhall": "government", "courthouse": "government", "embassy": "government",
                "place_of_worship": "place_of_worship",
                "fuel": "fuel", "parking": "parking", "bus_station": "bus",
                "bus_stop": "bus", "taxi": "transport", "ferry_terminal": "transport",
                "train_station": "transport", "airport": "transport",
                "theatre": "theatre", "cinema": "cinema", "arts_centre": "theatre",
                "community_centre": "theatre", "marketplace": "marketplace",
                "supermarket": "supermarket", "toilets": "toilet",
                "hostel": "hostel", "motel": "hotel", "guest_house": "hotel",
                "gym": "gym", "stadium": "sports", "sports_centre": "sports",
                "swimming_pool": "sports", "bus": "bus", "subway": "subway", "hotel": "hotel", "mall": "mall",
                "attraction": "attraction", "museum": "museum", "park": "park",
                "viewpoint": "scenic", "toilet": "toilet", "post": "post",
                "public_building": "government", "civic": "civic", "arts_centre": "theatre",
            }.get(a, "default")
        if tags.get("shop"):
            s = tags["shop"]
            if s in ("supermarket", "mall", "convenience", "department_store", "pharmacy"):
                return s
            return "shop"
        if tags.get("office"):
            return "office"
        if tags.get("railway"):
            r = tags["railway"]
            if r == "subway_entrance" or (r in ("station", "halt") and tags.get("station") == "subway"):
                return "subway"
            if r in ("station", "halt", "tram_stop"):
                return "transport"
        if base_tag == "leisure" or tags.get("leisure"):
            lv = tags.get("leisure", "")
            return {"park": "park", "garden": "garden", "playground": "park",
                    "sports_centre": "sports", "stadium": "sports",
                    "swimming_pool": "sports", "pitch": "sports"}.get(lv, "park")
        if tags.get("historic"):
            return "historic"
        return "default"

    def _process_poi(self, node_elements: List[dict], way_elements: List[dict], base_tag: str) -> List[dict]:
        """处理兴趣点要素 - 按分类使用整套象形符号表示

        node要素生成点标记，way要素取中心点生成标记；
        每个分类对应专属象形符号(icon)与配色。
        """
        all_features = []

        for elem in node_elements:
            coords = self._extract_coordinates(elem, "marker")
            if not coords or not isinstance(coords, list) or len(coords) != 2:
                continue
            tags = elem.get("tags", {})
            category = self._classify_poi(tags, base_tag)
            name = tags.get("name", "")
            all_features.append({"coords": coords, "name": name, "category": category})

        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            lat_sum = sum(p[0] for p in coords) / len(coords)
            lng_sum = sum(p[1] for p in coords) / len(coords)
            tags = elem.get("tags", {})
            category = self._classify_poi(tags, base_tag)
            name = tags.get("name", "")
            all_features.append({"coords": [lat_sum, lng_sum], "name": name, "category": category})

        if not all_features:
            return []

        # 按分类分组创建图层
        by_category = {}
        for feat in all_features:
            by_category.setdefault(feat["category"], []).append(feat)

        layers = []
        for cat, features in by_category.items():
            cfg = POI_STYLES.get(cat, POI_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": cfg["name"],
                "coordinates": [f["coords"] for f in features],
                "properties": [{"name": f["name"], "category": cat} for f in features],
                "style": {
                    "color": cfg["color"],
                    "fillColor": "#ffffff",
                    "fillOpacity": 0.9,
                    "weight": 2.5,
                    "radius": cfg.get("radius", 6),
                    "icon": cfg.get("icon", "📍"),
                    "iconClass": cfg.get("iconClass"),
                },
            })
        return layers

    def _process_tourism(self, node_elements: List[dict], way_elements: List[dict], base_tag: str) -> List[dict]:
        """处理旅游要素 - 按类别用不同颜色和符号表示

        node要素生成点标记，way要素取中心点生成标记。
        """
        all_features = []

        for elem in node_elements:
            coords = self._extract_coordinates(elem, "marker")
            if not coords or not isinstance(coords, list) or len(coords) != 2:
                continue
            tags = elem.get("tags", {})
            category = self._classify_tourism(tags, base_tag)
            name = tags.get("name", tags.get("tourism", tags.get("historic", "")))
            all_features.append({"coords": coords, "name": name, "category": category})

        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            # 取中心点作为标记位置
            lat_sum = sum(p[0] for p in coords) / len(coords)
            lng_sum = sum(p[1] for p in coords) / len(coords)
            tags = elem.get("tags", {})
            category = self._classify_tourism(tags, base_tag)
            name = tags.get("name", tags.get("tourism", tags.get("historic", "")))
            all_features.append({"coords": [lat_sum, lng_sum], "name": name, "category": category})

        # 按类别分组创建图层
        by_category = {}
        for feat in all_features:
            by_category.setdefault(feat["category"], []).append(feat)

        layers = []
        for cat, features in by_category.items():
            cfg = TOURISM_CATEGORIES.get(cat, TOURISM_CATEGORIES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": cfg["name"],
                "coordinates": [f["coords"] for f in features],
                "properties": [{"name": f["name"], "category": cat} for f in features],
                "style": {
                    "color": cfg["color"],
                    "fillColor": cfg.get("fillColor", cfg["color"]),
                    "fillOpacity": cfg.get("fillOpacity", 0.7),
                    "weight": cfg.get("weight", 2),
                    "radius": cfg.get("radius", 6),
                    "icon": cfg.get("icon", "📍"),
                    "iconClass": cfg.get("iconClass"),
                },
            })
        return layers

    def _classify_tourism(self, tags: dict, base_tag: str) -> str:
        """根据OSM标签判断旅游地类别"""
        # 历史遗迹
        if base_tag == "historic" or "historic" in tags:
            return "historic"

        tourism_val = tags.get("tourism", "")
        if tourism_val == "museum":
            return "museum"
        if tourism_val in ("attraction", "viewpoint", "artwork"):
            if tags.get("natural") or tags.get("water"):
                return "attraction"
            return "scenic"

        leisure_val = tags.get("leisure", "")
        if leisure_val in ("park", "garden", "playground", "pitch", "stadium"):
            return "park"

        amenity_val = tags.get("amenity", "")
        if amenity_val in ("restaurant", "fast_food", "cafe", "bar", "pub", "food_court"):
            return "food"
        if tourism_val == "hotel" or "shop" in tags:
            return "commercial"
        if amenity_val in ("theatre", "arts_centre", "cinema", "library"):
            return "cultural"
        if amenity_val in ("university", "college"):
            return "university"
        if tags.get("religion") or amenity_val in ("place_of_worship", "monastery"):
            return "religious"
        if tags.get("man_made"):
            return "landmark"

        return "default"

    def _process_greenspace(self, way_elements: List[dict]) -> List[dict]:
        """处理绿地要素 - 面状渲染，按类型分色"""
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 3:
                continue
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            tags = elem.get("tags", {})
            gtype = "default"
            if "landuse" in tags:
                lu = tags["landuse"]
                if lu in GREENSPACE_STYLES:
                    gtype = lu
            if "leisure" in tags and gtype == "default":
                lv = tags["leisure"]
                if lv in GREENSPACE_STYLES:
                    gtype = lv
            name = tags.get("name", "")
            by_type.setdefault(gtype, []).append({"coords": coords, "name": name})

        layers = []
        for gtype, items in by_type.items():
            style = GREENSPACE_STYLES.get(gtype, GREENSPACE_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": style["name"],
                "coordinates": [item["coords"] for item in items],
                "properties": [{"name": item["name"], "subtype": gtype} for item in items],
                "style": {
                    "color": style["color"],
                    "fillColor": style["fillColor"],
                    "fillOpacity": style["fillOpacity"],
                    "weight": style["weight"],
                },
            })
        return layers

    def _process_landuse(self, way_elements: List[dict]) -> List[dict]:
        """处理土地利用要素 - 面状渲染，按用地类型全面分类

        涵盖居住、商业、工业、农业、绿地等所有土地利用类型，
        绿地类型复用GREENSPACE_STYLES，其余使用LANDUSE_STYLES。
        """
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 3:
                continue
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            tags = elem.get("tags", {})
            # 判断用地类型
            ltype = "default"
            if "landuse" in tags:
                lu = tags["landuse"]
                # 绿地类型优先用GREENSPACE_STYLES
                if lu in GREENSPACE_STYLES:
                    ltype = lu
                elif lu in LANDUSE_STYLES:
                    ltype = lu
            if "leisure" in tags and ltype == "default":
                lv = tags["leisure"]
                if lv in GREENSPACE_STYLES:
                    ltype = lv
            if "natural" in tags and ltype == "default":
                nat = tags["natural"]
                if nat == "wood":
                    ltype = "forest"
                elif nat == "grass":
                    ltype = "grass"
                elif nat == "water":
                    ltype = "water"
            name = tags.get("name", "")
            by_type.setdefault(ltype, []).append({"coords": coords, "name": name})

        layers = []
        for ltype, items in by_type.items():
            # 优先从GREENSPACE_STYLES取样式，其次从LANDUSE_STYLES
            if ltype in GREENSPACE_STYLES:
                style = GREENSPACE_STYLES[ltype]
            elif ltype == "water":
                style = {"name": "水体", "fillColor": "#7dd3fc", "color": "#0ea5e9", "fillOpacity": 0.4, "weight": 0.5}
            else:
                style = LANDUSE_STYLES.get(ltype, LANDUSE_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": style["name"],
                "coordinates": [item["coords"] for item in items],
                "properties": [{"name": item["name"], "subtype": ltype} for item in items],
                "style": {
                    "color": style["color"],
                    "fillColor": style["fillColor"],
                    "fillOpacity": style["fillOpacity"],
                    "weight": style["weight"],
                },
            })
        return layers

    def _process_default(self, way_elements: List[dict], node_elements: List[dict], base_tag: str) -> List[dict]:
        """默认要素处理（amenity等通用类型）"""
        type_names = {
            "amenity": "生活设施", "shop": "商店", "office": "办公",
            "natural": "自然要素", "landuse": "用地类型",
        }
        layers = []
        style = self._get_default_style(base_tag)

        if way_elements:
            way_coords = []
            for elem in way_elements:
                coords = self._extract_coordinates(elem, "polyline")
                if coords and isinstance(coords, list) and len(coords) >= 2:
                    way_coords.append(coords)
            if way_coords:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": type_names.get(base_tag, base_tag),
                    "coordinates": way_coords,
                    "style": style,
                })

        if node_elements:
            node_coords = []
            node_props = []
            for elem in node_elements:
                coords = self._extract_coordinates(elem, "marker")
                if coords and isinstance(coords, list) and len(coords) == 2:
                    node_coords.append(coords)
                    tags = elem.get("tags", {})
                    node_props.append({
                        "name": tags.get("name", ""),
                        "type": tags.get("amenity", base_tag),
                    })
            if node_coords:
                marker_style = dict(style)
                if "weight" in marker_style:
                    del marker_style["weight"]
                if "dashArray" in marker_style:
                    del marker_style["dashArray"]
                if "radius" not in marker_style:
                    marker_style["radius"] = 6
                layers.append({
                    "id": generate_id("layer"),
                    "type": "marker",
                    "name": f"{type_names.get(base_tag, base_tag)}(点)",
                    "coordinates": node_coords,
                    "properties": node_props,
                    "style": marker_style,
                })
        return layers

    def _extract_coordinates(self, elem: dict, layer_type: str) -> Optional[Any]:
        """从OSM元素中提取坐标

        Args:
            elem: OSM元素
            layer_type: 目标图层类型

        Returns:
            坐标数据：
                - marker: [lat, lng]
                - polyline: [[lat, lng], ...]
            无法提取时返回None
        """
        # 辅助函数：检查坐标值是否有效（非None且为数字）
        def _is_valid_coord(val):
            return val is not None and isinstance(val, (int, float))

        # way类型有geometry字段（坐标点列表）
        geometry = elem.get("geometry", [])
        if geometry:
            # 过滤掉lat/lon为None或非数字的点
            coords = [
                [pt["lat"], pt["lon"]]
                for pt in geometry
                if "lat" in pt and "lon" in pt
                and _is_valid_coord(pt["lat"]) and _is_valid_coord(pt["lon"])
            ]
            if coords:
                if layer_type == "marker" and len(coords) == 1:
                    return coords[0]
                return coords

        # node类型直接有lat/lon字段，检查值有效性
        lat = elem.get("lat")
        lon = elem.get("lon")
        if _is_valid_coord(lat) and _is_valid_coord(lon):
            return [lat, lon]

        return None

    def _get_default_style(self, key: str) -> dict:
        """获取图层默认样式

        从MAP_STYLES中获取对应类型的样式配置。
        highway类型有子类型配置，取默认样式。

        Args:
            key: 要素类型或图层类型

        Returns:
            样式字典
        """
        style_config = MAP_STYLES.get(key)

        if style_config is None:
            # 未知类型使用通用默认样式
            return {"color": "#3388ff", "weight": 2, "opacity": 0.8}

        # highway类型的样式是列表结构（含子类型）
        if isinstance(style_config, list):
            for config in style_config:
                default_style = config.get("default")
                if default_style:
                    return dict(default_style)
            # 回退到列表第一个配置
            if style_config:
                return dict(style_config[0].get("default", {"color": "#999999", "weight": 2}))

        # 普通类型直接返回样式字典的副本
        if isinstance(style_config, dict):
            return dict(style_config)

        return {"color": "#3388ff", "weight": 2, "opacity": 0.8}
