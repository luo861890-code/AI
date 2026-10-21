"""制图知识图谱本体定义 - 基于LLM-KG-Carto框架

定义论文核心的7类概念本体，构建制图领域知识图谱的概念层次结构：
1. MapElement: 地图要素（道路、建筑、水系等地理实体）
2. MapSymbol: 地图符号（点状/线状/面状符号的设计规范）
3. CartographicData: 制图数据（OSM/遥感/矢量等数据源）
4. MapProjection: 地图投影（坐标系、投影方式）
5. InfluencingFactor: 影响因素（比例尺、用途、受众等制图决策因素）
6. CartographicDecision: 制图行为决策（特定条件下的制图方案选择，如图层配置、符号方案、配色方案、标注规则）
7. LayerConfig: 图层配置（地图类型对应的图层叠置方案，定义图层名称、顺序、可见性、数据源等）

本体关系推理链：
    MapType → CONTAINS_ELEMENT → MapElement
    MapElement → REPRESENTED_BY → MapSymbol
    MapElement → SOURCED_FROM → CartographicData
    MapSymbol → GOVERNED_BY → CartographyRule
    CartographicData → REQUIRES → MapProjection
    InfluencingFactor → INFLUENCES → MapElement
    InfluencingFactor → DETERMINES → MapSymbol
    MapType → HAS_DECISION → CartographicDecision → HAS_LAYER → LayerConfig
    InfluencingFactor → INFLUENCES → CartographicDecision
"""
from typing import Dict, List, Any


# ========== 7类核心概念本体定义 ==========

ONTOLOGY_CLASSES: Dict[str, Dict[str, Any]] = {
    "MapElement": {
        "description": "地图要素 - 地理实体在地图上的抽象表示",
        "color": "#3b82f6",  # 蓝色
        "subtypes": ["PointElement", "LinearElement", "ArealElement", "NetworkElement"],
        "properties": ["element_type", "osm_tag", "geometry_type", "rendering_priority"],
    },
    "MapSymbol": {
        "description": "地图符号 - 地图要素的视觉表达规范",
        "color": "#a855f7",  # 紫色
        "subtypes": ["PointSymbol", "LineSymbol", "AreaSymbol", "TextSymbol"],
        "properties": ["symbol_type", "color", "size", "style", "opacity"],
    },
    "CartographicData": {
        "description": "制图数据 - 地图制作的数据来源与格式",
        "color": "#22c55e",  # 绿色
        "subtypes": ["OSMData", "RemoteSensingData", "VectorData", "RasterData"],
        "properties": ["data_source", "data_format", "update_frequency", "coverage", "license"],
    },
    "MapProjection": {
        "description": "地图投影 - 地理坐标系与投影方式",
        "color": "#f97316",  # 橙色
        "subtypes": ["GeographicCRS", "ProjectedCRS", "CustomCRS"],
        "properties": ["crs_code", "projection_method", "unit", "accuracy"],
    },
    "InfluencingFactor": {
        "description": "影响因素 - 影响制图决策的各种因素",
        "color": "#ef4444",  # 红色
        "subtypes": ["Scale", "MapPurpose", "TargetAudience", "VisualConstraint"],
        "properties": ["factor_type", "value_range", "priority", "description"],
    },
    "CartographicDecision": {
        "description": "制图行为决策 - 特定条件下的制图方案选择",
        "color": "#f59e0b",
        "subtypes": ["LayerConfigDecision", "SymbolSchemeDecision", "ColorSchemeDecision", "AnnotationRuleDecision"],
        "properties": ["decision_id", "decision_type", "map_type", "audience_level", "parameters", "priority", "rationale"],
    },
    "LayerConfig": {
        "description": "图层配置 - 地图类型对应的图层叠置方案",
        "color": "#06b6d4",
        "subtypes": ["BaseLayer", "ThematicLayer", "AnnotationLayer"],
        "properties": ["layer_name", "layer_order", "visibility_default", "min_zoom", "max_zoom", "data_source", "osm_tags", "symbol_type"],
    },
}


# ========== 本体节点初始数据（用于扩展init_data.json和内存模式） ==========

ONTOLOGY_NODES: List[Dict[str, Any]] = [
    # --- MapElement 实例 ---
    {"label": "MapElement", "name": "road_element", "element_type": "linear", "osm_tag": "highway",
     "geometry_type": "line", "rendering_priority": 5,
     "description": "道路要素，包括高速公路、主干道、次干道等"},
    {"label": "MapElement", "name": "building_element", "element_type": "areal", "osm_tag": "building",
     "geometry_type": "polygon", "rendering_priority": 2,
     "description": "建筑要素，包括住宅、商业、工业建筑等"},
    {"label": "MapElement", "name": "waterway_element", "element_type": "linear", "osm_tag": "waterway",
     "geometry_type": "line", "rendering_priority": 4,
     "description": "水系要素，包括河流、运河、溪流等"},
    {"label": "MapElement", "name": "poi_element", "element_type": "point", "osm_tag": "tourism|amenity",
     "geometry_type": "point", "rendering_priority": 6,
     "description": "兴趣点要素，包括景点、餐厅、医院等"},
    {"label": "MapElement", "name": "railway_element", "element_type": "linear", "osm_tag": "railway",
     "geometry_type": "line", "rendering_priority": 5,
     "description": "铁路要素，包括高铁、地铁、轻轨等"},

    # --- MapSymbol 实例 ---
    {"label": "MapSymbol", "name": "highway_symbol", "symbol_type": "LineSymbol",
     "color": "#e892a2", "size": 5, "style": "solid", "opacity": 0.9,
     "description": "高速公路符号，粗线红色"},
    {"label": "MapSymbol", "name": "railway_symbol", "symbol_type": "LineSymbol",
     "color": "#555555", "size": 3, "style": "dashed", "opacity": 0.8,
     "description": "铁路符号，灰色虚线"},
    {"label": "MapSymbol", "name": "waterway_symbol", "symbol_type": "LineSymbol",
     "color": "#7dd3fc", "size": 3, "style": "solid", "opacity": 0.8,
     "description": "水系符号，蓝色实线"},
    {"label": "MapSymbol", "name": "building_symbol", "symbol_type": "AreaSymbol",
     "color": "#d1d5db", "size": 1, "style": "fill", "opacity": 0.3,
     "description": "建筑符号，浅灰填充"},
    {"label": "MapSymbol", "name": "poi_symbol", "symbol_type": "PointSymbol",
     "color": "#dc2626", "size": 8, "style": "circle", "opacity": 1.0,
     "description": "兴趣点符号，红色圆形标记"},

    # --- CartographicData 实例 ---
    {"label": "CartographicData", "name": "osm_data", "data_source": "OpenStreetMap",
     "data_format": "Overpass JSON", "update_frequency": "实时", "coverage": "全球",
     "license": "ODbL", "description": "OpenStreetMap开放数据，通过Overpass API获取"},
    {"label": "CartographicData", "name": "local_landmark_data", "data_source": "内置知识库",
     "data_format": "JSON", "update_frequency": "手动", "coverage": "武汉",
     "license": "自有", "description": "内置武汉地标数据，OSM不可用时降级使用"},

    # --- MapProjection 实例 ---
    {"label": "MapProjection", "name": "wgs84", "crs_code": "EPSG:4326",
     "projection_method": "地理坐标系", "unit": "度", "accuracy": "高",
     "description": "WGS84地理坐标系，GPS标准坐标系"},
    {"label": "MapProjection", "name": "web_mercator", "crs_code": "EPSG:3857",
     "projection_method": "Web墨卡托投影", "unit": "米", "accuracy": "中",
     "description": "Web墨卡托投影，在线地图标准投影"},

    # --- InfluencingFactor 实例 ---
    {"label": "InfluencingFactor", "name": "scale_factor", "factor_type": "Scale",
     "value_range": "zoom 8-19", "priority": "high",
     "description": "比例尺因素，决定地图详细程度和要素选择"},
    {"label": "InfluencingFactor", "name": "purpose_factor", "factor_type": "MapPurpose",
     "value_range": "traffic/tourism/campus/food/basic", "priority": "high",
     "description": "地图用途因素，决定图层选择和样式配置"},
    {"label": "InfluencingFactor", "name": "color_constraint", "factor_type": "VisualConstraint",
     "value_range": "主色不超过5种", "priority": "medium",
     "description": "色彩约束因素，确保视觉层次和信息可读性"},

    # --- CartographicDecision 实例 ---
    {"label": "CartographicDecision", "name": "traffic_layer_config", "decision_type": "LAYER_CONFIG",
     "map_type": "traffic", "audience_level": "public", "priority": "high",
     "parameters": {
         "layers": [
             {"name": "道路", "order": 1, "osm_tags": "highway=*", "symbol_type": "LineSymbol"},
             {"name": "铁路", "order": 2, "osm_tags": "railway=*", "symbol_type": "LineSymbol"},
             {"name": "地铁", "order": 3, "osm_tags": "railway=subway", "symbol_type": "LineSymbol"},
             {"name": "公交站", "order": 4, "osm_tags": "highway=bus_stop", "symbol_type": "PointSymbol"},
         ]
     },
     "rationale": "交通图需展示道路网络层次，按道路等级和交通工具类型分层",
     "description": "交通图的图层配置决策"},
    {"label": "CartographicDecision", "name": "tourism_color_scheme", "decision_type": "COLOR_SCHEME",
     "map_type": "tourism", "audience_level": "public", "priority": "high",
     "parameters": {
         "palette": {"primary": "#dc2626", "secondary": "#f97316", "accent": "#eab308", "background": "#fef3c7"},
         "rules": ["POI使用暖色系突出标注", "水域保持蓝色基准", "背景使用浅暖色提高对比度"]
     },
     "rationale": "旅游图需要醒目配色吸引注意力，暖色系激发探索欲望",
     "description": "旅游图的配色方案决策"},
    {"label": "CartographicDecision", "name": "campus_symbol_scheme", "decision_type": "SYMBOL_SCHEME",
     "map_type": "campus", "audience_level": "public", "priority": "medium",
     "parameters": {
         "building": {"type": "AreaSymbol", "color": "#bfdbfe", "border": "#3b82f6", "opacity": 0.4},
         "road": {"type": "LineSymbol", "color": "#94a3b8", "weight": 2, "style": "solid"},
         "green_space": {"type": "AreaSymbol", "color": "#bbf7d0", "opacity": 0.3},
         "facility": {"type": "PointSymbol", "color": "#6366f1", "size": 6, "style": "circle"},
     },
     "rationale": "校园图使用清新配色和简洁符号，区分教学区与生活区",
     "description": "校园图的符号方案决策"},
    {"label": "CartographicDecision", "name": "food_annotation_rule", "decision_type": "ANNOTATION_RULE",
     "map_type": "food", "audience_level": "public", "priority": "medium",
     "parameters": {
         "font_family": "sans-serif",
         "title_size": 16,
         "label_size": 11,
         "label_color": "#1e293b",
         "halo_color": "#ffffff",
         "halo_width": 1.5,
         "placement": "offset_right",
         "collision_rule": "hide_overflow",
     },
     "rationale": "美食图标注需清晰可读，标注框有明显光晕确保在各种底色上可见",
     "description": "美食图的标注规则决策"},
    {"label": "CartographicDecision", "name": "basic_layer_config", "decision_type": "LAYER_CONFIG",
     "map_type": "basic", "audience_level": "public", "priority": "medium",
     "parameters": {
         "layers": [
             {"name": "水系", "order": 1, "osm_tags": "waterway=*|natural=water", "symbol_type": "AreaSymbol"},
             {"name": "绿地", "order": 2, "osm_tags": "landuse=grass|leisure=park", "symbol_type": "AreaSymbol"},
             {"name": "道路", "order": 3, "osm_tags": "highway=*", "symbol_type": "LineSymbol"},
             {"name": "建筑", "order": 4, "osm_tags": "building=*", "symbol_type": "AreaSymbol"},
             {"name": "生活设施", "order": 5, "osm_tags": "amenity=*|shop=*", "symbol_type": "PointSymbol"},
         ]
     },
     "rationale": "基础地图按自然-人工层次叠置，先自然地理后人工设施",
     "description": "基础地图的图层配置决策"},
    {"label": "CartographicDecision", "name": "administrative_color_scheme", "decision_type": "COLOR_SCHEME",
     "map_type": "administrative", "audience_level": "professional", "priority": "high",
     "parameters": {
         "palette": {"primary": "#1e40af", "secondary": "#7c3aed", "tertiary": "#db2777", "background": "#f8fafc"},
         "rules": ["行政边界用深色实线", "各级行政区使用区分色填充", "标注行政名称置于区域中心"]
     },
     "rationale": "行政区划图需要清晰的边界区分和层级色彩编码",
     "description": "行政区划图的配色方案决策"},
    {"label": "CartographicDecision", "name": "traffic_symbol_scheme", "decision_type": "SYMBOL_SCHEME",
     "map_type": "traffic", "audience_level": "public", "priority": "high",
     "parameters": {
         "motorway": {"type": "LineSymbol", "color": "#e892a2", "weight": 5, "style": "solid"},
         "trunk": {"type": "LineSymbol", "color": "#fbb38c", "weight": 4, "style": "solid"},
         "primary": {"type": "LineSymbol", "color": "#fcd69b", "weight": 3, "style": "solid"},
         "railway": {"type": "LineSymbol", "color": "#555555", "weight": 2, "style": "dashed"},
         "station": {"type": "PointSymbol", "color": "#dc2626", "size": 7, "style": "square"},
     },
     "rationale": "交通图使用暖色调区分道路等级，铁路用灰色虚线区分",
     "description": "交通图的符号方案决策"},
    {"label": "CartographicDecision", "name": "tourism_annotation_rule", "decision_type": "ANNOTATION_RULE",
     "map_type": "tourism", "audience_level": "public", "priority": "medium",
     "parameters": {
         "font_family": "serif",
         "title_size": 18,
         "label_size": 12,
         "label_color": "#1e3a5f",
         "halo_color": "#fef3c7",
         "halo_width": 2,
         "placement": "top_center",
         "collision_rule": "prioritize_high_rank",
     },
     "rationale": "旅游图标注需美观大方，衬线字体提升文化感，按景点热度决定显示优先级",
     "description": "旅游图的标注规则决策"},
    {"label": "CartographicDecision", "name": "campus_layer_config", "decision_type": "LAYER_CONFIG",
     "map_type": "campus", "audience_level": "public", "priority": "medium",
     "parameters": {
         "layers": [
             {"name": "绿地水体", "order": 1, "osm_tags": "landuse=grass|natural=water", "symbol_type": "AreaSymbol"},
             {"name": "道路", "order": 2, "osm_tags": "highway=*", "symbol_type": "LineSymbol"},
             {"name": "教学楼", "order": 3, "osm_tags": "building=university|building=school", "symbol_type": "AreaSymbol"},
             {"name": "宿舍", "order": 4, "osm_tags": "building=dormitory", "symbol_type": "AreaSymbol"},
             {"name": "服务设施", "order": 5, "osm_tags": "amenity=*", "symbol_type": "PointSymbol"},
         ]
     },
     "rationale": "校园图优先展示绿地与教学设施，按校园功能区层次叠置",
     "description": "校园图的图层配置决策"},

    # --- LayerConfig 实例 ---
    {"label": "LayerConfig", "name": "road_base_layer", "layer_name": "道路基层",
     "layer_order": 1, "visibility_default": True, "min_zoom": 8, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "highway=*", "symbol_type": "LineSymbol",
     "description": "道路网络基层，包含各级道路"},
    {"label": "LayerConfig", "name": "water_base_layer", "layer_name": "水域基层",
     "layer_order": 0, "visibility_default": True, "min_zoom": 6, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "natural=water|waterway=*", "symbol_type": "AreaSymbol",
     "description": "水域基层，位于所有图层最下方"},
    {"label": "LayerConfig", "name": "railway_thematic_layer", "layer_name": "铁路专题层",
     "layer_order": 2, "visibility_default": True, "min_zoom": 9, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "railway=*", "symbol_type": "LineSymbol",
     "description": "铁路专题层，交通图中覆盖在道路层之上"},
    {"label": "LayerConfig", "name": "poi_annotation_layer", "layer_name": "POI标注层",
     "layer_order": 10, "visibility_default": True, "min_zoom": 13, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "tourism=*|amenity=*", "symbol_type": "PointSymbol",
     "description": "POI标注层，位于所有专题层之上，展示兴趣点标注"},
]


# ========== 本体关系初始数据 ==========

ONTOLOGY_RELATIONS: List[Dict[str, Any]] = [
    # MapElement → REPRESENTED_BY → MapSymbol
    {"from": "road_element", "to": "highway_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "道路要素由高速公路符号表示"}},
    {"from": "railway_element", "to": "railway_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "铁路要素由铁路符号表示"}},
    {"from": "waterway_element", "to": "waterway_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "水系要素由水系符号表示"}},
    {"from": "building_element", "to": "building_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "建筑要素由建筑符号表示"}},
    {"from": "poi_element", "to": "poi_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "兴趣点要素由POI符号表示"}},

    # MapElement → SOURCED_FROM → CartographicData
    {"from": "road_element", "to": "osm_data", "type": "SOURCED_FROM",
     "properties": {"description": "道路数据来源于OSM"}},
    {"from": "building_element", "to": "osm_data", "type": "SOURCED_FROM",
     "properties": {"description": "建筑数据来源于OSM"}},
    {"from": "poi_element", "to": "osm_data", "type": "SOURCED_FROM",
     "properties": {"description": "POI数据来源于OSM"}},
    {"from": "poi_element", "to": "local_landmark_data", "type": "SOURCED_FROM",
     "properties": {"description": "POI数据降级来源于本地地标库"}},

    # MapElement → INFLUENCED_BY → InfluencingFactor
    {"from": "road_element", "to": "scale_factor", "type": "INFLUENCED_BY",
     "properties": {"description": "道路要素的显示受比例尺影响"}},
    {"from": "road_element", "to": "purpose_factor", "type": "INFLUENCED_BY",
     "properties": {"description": "道路要素的选取受地图用途影响"}},
    {"from": "poi_element", "to": "purpose_factor", "type": "INFLUENCED_BY",
     "properties": {"description": "POI要素的选取受地图用途影响"}},

    # InfluencingFactor → DETERMINES → MapSymbol
    {"from": "color_constraint", "to": "poi_symbol", "type": "DETERMINES",
     "properties": {"description": "色彩约束决定POI符号的颜色选择"}},
    {"from": "purpose_factor", "to": "highway_symbol", "type": "DETERMINES",
     "properties": {"description": "地图用途决定道路符号的样式"}},

    # CartographicData → REQUIRES → MapProjection
    {"from": "osm_data", "to": "wgs84", "type": "REQUIRES",
     "properties": {"description": "OSM数据使用WGS84坐标系"}},
    {"from": "osm_data", "to": "web_mercator", "type": "REQUIRES",
     "properties": {"description": "OSM数据在Web展示时转换为Web墨卡托投影"}},

    # 连接新本体与现有MapType节点
    {"from": "traffic", "to": "road_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "交通图包含道路要素"}},
    {"from": "traffic", "to": "railway_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "交通图包含铁路要素"}},
    {"from": "tourism", "to": "poi_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "旅游图包含POI要素"}},
    {"from": "campus", "to": "building_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "校园图包含建筑要素"}},
    {"from": "basic", "to": "waterway_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "基础图包含水系要素"}},

    # --- 决策关系链：MapType → HAS_DECISION → CartographicDecision ---
    {"from": "traffic", "to": "traffic_layer_config", "type": "HAS_DECISION",
     "properties": {"description": "交通图关联图层配置决策"}},
    {"from": "traffic", "to": "traffic_symbol_scheme", "type": "HAS_DECISION",
     "properties": {"description": "交通图关联符号方案决策"}},
    {"from": "tourism", "to": "tourism_color_scheme", "type": "HAS_DECISION",
     "properties": {"description": "旅游图关联配色方案决策"}},
    {"from": "tourism", "to": "tourism_annotation_rule", "type": "HAS_DECISION",
     "properties": {"description": "旅游图关联标注规则决策"}},
    {"from": "campus", "to": "campus_symbol_scheme", "type": "HAS_DECISION",
     "properties": {"description": "校园图关联符号方案决策"}},
    {"from": "campus", "to": "campus_layer_config", "type": "HAS_DECISION",
     "properties": {"description": "校园图关联图层配置决策"}},
    {"from": "food", "to": "food_annotation_rule", "type": "HAS_DECISION",
     "properties": {"description": "美食图关联标注规则决策"}},
    {"from": "basic", "to": "basic_layer_config", "type": "HAS_DECISION",
     "properties": {"description": "基础地图关联图层配置决策"}},
    {"from": "administrative", "to": "administrative_color_scheme", "type": "HAS_DECISION",
     "properties": {"description": "行政区划图关联配色方案决策"}},

    # --- 决策 → HAS_LAYER → LayerConfig ---
    {"from": "traffic_layer_config", "to": "road_base_layer", "type": "HAS_LAYER",
     "properties": {"description": "交通图图层配置包含道路基层"}},
    {"from": "traffic_layer_config", "to": "railway_thematic_layer", "type": "HAS_LAYER",
     "properties": {"description": "交通图图层配置包含铁路专题层"}},
    {"from": "basic_layer_config", "to": "water_base_layer", "type": "HAS_LAYER",
     "properties": {"description": "基础地图图层配置包含水域基层"}},
    {"from": "basic_layer_config", "to": "poi_annotation_layer", "type": "HAS_LAYER",
     "properties": {"description": "基础地图图层配置包含POI标注层"}},

    # --- InfluencingFactor → INFLUENCES → CartographicDecision ---
    {"from": "purpose_factor", "to": "traffic_layer_config", "type": "INFLUENCES",
     "properties": {"description": "地图用途因素影响交通图层配置决策"}},
    {"from": "purpose_factor", "to": "campus_symbol_scheme", "type": "INFLUENCES",
     "properties": {"description": "地图用途因素影响校园图符号方案决策"}},
    {"from": "color_constraint", "to": "tourism_color_scheme", "type": "INFLUENCES",
     "properties": {"description": "色彩约束因素影响旅游图配色方案决策"}},
    {"from": "color_constraint", "to": "administrative_color_scheme", "type": "INFLUENCES",
     "properties": {"description": "色彩约束因素影响行政区划图配色方案决策"}},
    {"from": "scale_factor", "to": "basic_layer_config", "type": "INFLUENCES",
     "properties": {"description": "比例尺因素影响基础地图图层配置的缩放范围"}},
]


def get_ontology_summary() -> Dict[str, Any]:
    """获取本体概要信息

    Returns:
        包含类别数量、节点数量、关系数量和类别详情的字典
    """
    return {
        "class_count": len(ONTOLOGY_CLASSES),
        "classes": list(ONTOLOGY_CLASSES.keys()),
        "node_count": len(ONTOLOGY_NODES),
        "relation_count": len(ONTOLOGY_RELATIONS),
        "class_details": {
            k: {
                "description": v["description"],
                "color": v["color"],
                "subtypes": v["subtypes"],
            }
            for k, v in ONTOLOGY_CLASSES.items()
        }
    }
