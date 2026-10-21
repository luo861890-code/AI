#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_decision_data.py
生成并追加制图行为决策知识数据到 data/kg/init_data.json。
包括: CartographicDecision 节点、LayerConfig 节点、新 MapSymbol 节点、
新增 MapType(administrative) 节点、以及对应的关系。

执行后 init_data.json 节点数将从 ~73 增长到 140+, 关系数从 ~142 增长到 400+。
"""

import json
import os
import copy
import sys

# ---------- 路径配置 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "kg", "init_data.json")

# ---------- 6种地图类型 ----------
MAP_TYPES = ["traffic", "tourism", "campus", "food", "basic", "administrative"]

# ---------- 4类决策类型 ----------
DECISION_TYPES = ["LAYER_CONFIG", "SYMBOL_SCHEME", "COLOR_SCHEME", "ANNOTATION_RULE"]

# ====================================================================
# 1. 新增 MapType 节点: administrative (现有只有5个 MapType)
# ====================================================================
NEW_MAPTYPE = {
    "label": "MapType",
    "name": "administrative",
    "description": "行政区划地图，侧重展示行政边界、区县级划分、城镇标注及行政区色块填充",
    "icon": "\U0001F3DB",
    "default_zoom": 11,
    "suitable_layers": ["admin_boundary", "district", "city_label", "town_label"],
    "feature_styles": {
        "boundary": [{"color": "#6b7280", "weight": 3, "opacity": 0.9}],
        "district": [{"color": "#9ca3af", "weight": 2, "opacity": 0.7, "fillColor": "#f3f4f6", "fillOpacity": 0.3}],
        "city_label": [{"color": "#111827", "radius": 6, "opacity": 1.0}],
        "town_label": [{"color": "#374151", "radius": 4, "opacity": 0.9}]
    }
}

# ====================================================================
# 2. CartographicDecision 节点 (6 MapTypes x 4 DecisionTypes = 24)
# ====================================================================
def build_decisions():
    """构建 24 个 CartographicDecision 节点。"""
    decisions = []

    # ---------- traffic ----------
    decisions.append({
        "label": "CartographicDecision",
        "name": "traffic_LAYER_CONFIG",
        "decision_type": "LAYER_CONFIG",
        "map_type": "traffic",
        "audience_level": "public",
        "parameters": {
            "layers": [
                {"name": "motorway_roads", "order": 1, "data_source": "OSM",
                 "osm_tags": "highway=motorway|highway=trunk|highway=primary",
                 "symbol_type": "LineSymbol"},
                {"name": "secondary_roads", "order": 2, "data_source": "OSM",
                 "osm_tags": "highway=secondary|highway=tertiary",
                 "symbol_type": "LineSymbol"},
                {"name": "railway_lines", "order": 3, "data_source": "OSM",
                 "osm_tags": "railway=*",
                 "symbol_type": "LineSymbol"},
                {"name": "subway_lines", "order": 4, "data_source": "OSM",
                 "osm_tags": "railway=subway",
                 "symbol_type": "LineSymbol"},
                {"name": "bus_stations", "order": 5, "data_source": "OSM",
                 "osm_tags": "highway=bus_stop|amenity=bus_station",
                 "symbol_type": "PointSymbol"}
            ]
        },
        "priority": "high",
        "rationale": "交通地图以道路网络和公共交通为核心，按道路等级分层确保视觉层次清晰"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "traffic_SYMBOL_SCHEME",
        "decision_type": "SYMBOL_SCHEME",
        "map_type": "traffic",
        "audience_level": "public",
        "parameters": {
            "symbols": {
                "motorway_element": {
                    "type": "LineSymbol", "color": "#e892a2", "weight": 5,
                    "opacity": 0.9, "style": "solid"
                },
                "primary_road_element": {
                    "type": "LineSymbol", "color": "#fbbf24", "weight": 4,
                    "opacity": 0.85, "style": "solid"
                },
                "secondary_road_element": {
                    "type": "LineSymbol", "color": "#d1d5db", "weight": 3,
                    "opacity": 0.8, "style": "solid"
                },
                "railway_element": {
                    "type": "LineSymbol", "color": "#555555", "weight": 3,
                    "opacity": 0.8, "style": "dashed"
                },
                "subway_element": {
                    "type": "LineSymbol", "color": "#0066cc", "weight": 4,
                    "opacity": 0.9, "style": "solid"
                },
                "bus_stop_element": {
                    "type": "PointSymbol", "color": "#f97316", "size": 6,
                    "opacity": 1.0, "style": "circle"
                }
            }
        },
        "priority": "high",
        "rationale": "道路符号按等级分色区分，高速公路用暖色突出，地铁用蓝色标识，公交站用橙色点状符号"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "traffic_COLOR_SCHEME",
        "decision_type": "COLOR_SCHEME",
        "map_type": "traffic",
        "audience_level": "public",
        "parameters": {
            "palette": {
                "primary": "#e892a2",
                "secondary": "#fbbf24",
                "accent": "#0066cc",
                "background": "#f0f9ff"
            },
            "rules": [
                "主色不超过5种",
                "高速公路用暖红色系(e892a2)，主干道用黄色系(fbbf24)",
                "地铁线路用蓝色系(0066cc)区别于地面道路",
                "铁路用灰色(555555)弱化显示",
                "背景用冷色浅底(f0f9ff)突出道路网络"
            ]
        },
        "priority": "high",
        "rationale": "交通地图需要清晰的视觉层次，暖色突出道路主干，冷色背景提供对比"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "traffic_ANNOTATION_RULE",
        "decision_type": "ANNOTATION_RULE",
        "map_type": "traffic",
        "audience_level": "public",
        "parameters": {
            "font_family": "sans-serif",
            "title_size": 16,
            "label_size": 11,
            "min_spacing": 3,
            "placement": "优先右侧",
            "road_label": {
                "font_size": 10,
                "placement": "沿道路走向",
                "color": "#374151",
                "font_weight": "normal"
            },
            "station_label": {
                "font_size": 11,
                "placement": "右侧偏移5px",
                "color": "#1f2937",
                "font_weight": "bold"
            }
        },
        "priority": "high",
        "rationale": "道路注记沿走向排列确保方向感，站点注记加粗放置在符号右侧避免遮挡"
    })

    # ---------- tourism ----------
    decisions.append({
        "label": "CartographicDecision",
        "name": "tourism_LAYER_CONFIG",
        "decision_type": "LAYER_CONFIG",
        "map_type": "tourism",
        "audience_level": "public",
        "parameters": {
            "layers": [
                {"name": "attractions", "order": 1, "data_source": "OSM",
                 "osm_tags": "tourism=attraction|historic=*",
                 "symbol_type": "PointSymbol"},
                {"name": "museums", "order": 2, "data_source": "OSM",
                 "osm_tags": "tourism=museum",
                 "symbol_type": "PointSymbol"},
                {"name": "hotels", "order": 3, "data_source": "OSM",
                 "osm_tags": "tourism=hotel",
                 "symbol_type": "PointSymbol"},
                {"name": "restaurants", "order": 4, "data_source": "OSM",
                 "osm_tags": "amenity=restaurant",
                 "symbol_type": "PointSymbol"},
                {"name": "viewpoints", "order": 5, "data_source": "OSM",
                 "osm_tags": "tourism=viewpoint",
                 "symbol_type": "PointSymbol"}
            ]
        },
        "priority": "high",
        "rationale": "旅游地图以景点为核心，按照吸引力层级（景点>博物馆>酒店>餐饮>观景点）排列图层顺序"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "tourism_SYMBOL_SCHEME",
        "decision_type": "SYMBOL_SCHEME",
        "map_type": "tourism",
        "audience_level": "public",
        "parameters": {
            "symbols": {
                "attraction_element": {
                    "type": "PointSymbol", "color": "#dc2626", "size": 10,
                    "opacity": 1.0, "style": "star"
                },
                "museum_element": {
                    "type": "PointSymbol", "color": "#f59e0b", "size": 8,
                    "opacity": 1.0, "style": "diamond"
                },
                "hotel_element": {
                    "type": "PointSymbol", "color": "#8b5cf6", "size": 7,
                    "opacity": 0.9, "style": "circle"
                },
                "restaurant_element": {
                    "type": "PointSymbol", "color": "#ef4444", "size": 6,
                    "opacity": 0.9, "style": "circle"
                },
                "viewpoint_element": {
                    "type": "PointSymbol", "color": "#10b981", "size": 7,
                    "opacity": 0.9, "style": "triangle"
                }
            }
        },
        "priority": "high",
        "rationale": "景点使用星形大红色符号吸引注意力，不同类型使用不同形状增强区分度"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "tourism_COLOR_SCHEME",
        "decision_type": "COLOR_SCHEME",
        "map_type": "tourism",
        "audience_level": "public",
        "parameters": {
            "palette": {
                "primary": "#dc2626",
                "secondary": "#f59e0b",
                "accent": "#8b5cf6",
                "background": "#fffbeb"
            },
            "rules": [
                "主色不超过4种",
                "景点用饱和度最高的红色(dc2626)作为主色",
                "博物馆/文化类用金色(f59e0b)表现文化价值",
                "住宿用紫色(8b5cf6)作为差异化配色",
                "餐饮用红色(ef4444)与景点红色区分明度",
                "暖黄底色(fffbeb)营造温暖活跃的旅游氛围"
            ]
        },
        "priority": "high",
        "rationale": "红橙暖色调激发旅行兴趣，金色突出文化遗产，暖色背景营造温馨活泼的旅游图体验"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "tourism_ANNOTATION_RULE",
        "decision_type": "ANNOTATION_RULE",
        "map_type": "tourism",
        "audience_level": "public",
        "parameters": {
            "font_family": "sans-serif",
            "title_size": 16,
            "label_size": 12,
            "min_spacing": 4,
            "placement": "优先右侧",
            "attraction_label": {
                "font_size": 13,
                "placement": "右侧偏移6px",
                "color": "#1f2937",
                "font_weight": "bold"
            },
            "hotel_label": {
                "font_size": 11,
                "placement": "下方偏移4px",
                "color": "#4b5563",
                "font_weight": "normal"
            }
        },
        "priority": "high",
        "rationale": "景点注记加粗放大放置在右侧，住宿注记小号置于下方，避免信息层次混乱"
    })

    # ---------- campus ----------
    decisions.append({
        "label": "CartographicDecision",
        "name": "campus_LAYER_CONFIG",
        "decision_type": "LAYER_CONFIG",
        "map_type": "campus",
        "audience_level": "public",
        "parameters": {
            "layers": [
                {"name": "buildings", "order": 1, "data_source": "OSM",
                 "osm_tags": "building=*",
                 "symbol_type": "AreaSymbol"},
                {"name": "education_facilities", "order": 2, "data_source": "OSM",
                 "osm_tags": "amenity=university|amenity=school|amenity=college",
                 "symbol_type": "PointSymbol"},
                {"name": "sports_facilities", "order": 3, "data_source": "OSM",
                 "osm_tags": "leisure=sports_centre|leisure=pitch|leisure=stadium",
                 "symbol_type": "AreaSymbol"},
                {"name": "footways", "order": 4, "data_source": "OSM",
                 "osm_tags": "highway=footway|highway=path",
                 "symbol_type": "LineSymbol"},
                {"name": "campus_amenities", "order": 5, "data_source": "OSM",
                 "osm_tags": "amenity=library|amenity=canteen|amenity=parking",
                 "symbol_type": "PointSymbol"}
            ]
        },
        "priority": "high",
        "rationale": "校园地图以建筑为核心，教学设施、运动场地、步行道、服务设施分层次组织"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "campus_SYMBOL_SCHEME",
        "decision_type": "SYMBOL_SCHEME",
        "map_type": "campus",
        "audience_level": "public",
        "parameters": {
            "symbols": {
                "building_element": {
                    "type": "AreaSymbol", "color": "#3b82f6", "weight": 2,
                    "fillColor": "#93c5fd", "fillOpacity": 0.5, "style": "fill"
                },
                "education_element": {
                    "type": "PointSymbol", "color": "#10b981", "size": 7,
                    "opacity": 1.0, "style": "square"
                },
                "sports_element": {
                    "type": "AreaSymbol", "color": "#f59e0b", "weight": 1,
                    "fillColor": "#fde68a", "fillOpacity": 0.4, "style": "fill"
                },
                "footway_element": {
                    "type": "LineSymbol", "color": "#a3a3a3", "weight": 1,
                    "opacity": 0.7, "style": "dashed"
                },
                "amenity_element": {
                    "type": "PointSymbol", "color": "#6366f1", "size": 5,
                    "opacity": 0.85, "style": "circle"
                }
            }
        },
        "priority": "high",
        "rationale": "建筑用蓝色面状符号填充，步道用浅灰虚线弱化，教学用绿色方块突出标识"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "campus_COLOR_SCHEME",
        "decision_type": "COLOR_SCHEME",
        "map_type": "campus",
        "audience_level": "public",
        "parameters": {
            "palette": {
                "primary": "#3b82f6",
                "secondary": "#10b981",
                "accent": "#6366f1",
                "background": "#eff6ff"
            },
            "rules": [
                "主色不超过4种",
                "建筑使用蓝色系(3b82f6)作为主色，浅蓝填充(93c5fd)",
                "教学设施使用绿色(10b981)代表知识与学习",
                "运动场地使用黄色(f59e0b)活跃氛围",
                "步道使用浅灰(a3a3a3)不干扰主体建筑阅读",
                "蓝绿清新色调(background: eff6ff)符合校园学术氛围"
            ]
        },
        "priority": "high",
        "rationale": "蓝绿清新色调传达学术与自然融合的校园形象，层次分明便于快速定位"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "campus_ANNOTATION_RULE",
        "decision_type": "ANNOTATION_RULE",
        "map_type": "campus",
        "audience_level": "public",
        "parameters": {
            "font_family": "sans-serif",
            "title_size": 15,
            "label_size": 12,
            "min_spacing": 4,
            "placement": "优先下方",
            "building_label": {
                "font_size": 12,
                "placement": "面状中心",
                "color": "#1e40af",
                "font_weight": "bold"
            },
            "facility_label": {
                "font_size": 10,
                "placement": "右侧偏移4px",
                "color": "#4b5563",
                "font_weight": "normal"
            }
        },
        "priority": "high",
        "rationale": "建筑注记居中加粗显示名称，服务设施注记置于右侧，步道不注记避免视觉杂乱"
    })

    # ---------- food ----------
    decisions.append({
        "label": "CartographicDecision",
        "name": "food_LAYER_CONFIG",
        "decision_type": "LAYER_CONFIG",
        "map_type": "food",
        "audience_level": "public",
        "parameters": {
            "layers": [
                {"name": "restaurants", "order": 1, "data_source": "OSM",
                 "osm_tags": "amenity=restaurant",
                 "symbol_type": "PointSymbol"},
                {"name": "cafes", "order": 2, "data_source": "OSM",
                 "osm_tags": "amenity=cafe",
                 "symbol_type": "PointSymbol"},
                {"name": "fast_food", "order": 3, "data_source": "OSM",
                 "osm_tags": "amenity=fast_food",
                 "symbol_type": "PointSymbol"},
                {"name": "bars", "order": 4, "data_source": "OSM",
                 "osm_tags": "amenity=bar|amenity=pub",
                 "symbol_type": "PointSymbol"}
            ]
        },
        "priority": "high",
        "rationale": "美食地图以餐饮场所为核心，按类型分为餐厅、咖啡、快餐、酒吧四个核心图层"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "food_SYMBOL_SCHEME",
        "decision_type": "SYMBOL_SCHEME",
        "map_type": "food",
        "audience_level": "public",
        "parameters": {
            "symbols": {
                "restaurant_element": {
                    "type": "PointSymbol", "color": "#ef4444", "size": 8,
                    "opacity": 1.0, "style": "circle"
                },
                "cafe_element": {
                    "type": "PointSymbol", "color": "#8b5cf6", "size": 6,
                    "opacity": 0.9, "style": "circle"
                },
                "fast_food_element": {
                    "type": "PointSymbol", "color": "#f59e0b", "size": 6,
                    "opacity": 0.9, "style": "diamond"
                },
                "bar_element": {
                    "type": "PointSymbol", "color": "#ec4899", "size": 5,
                    "opacity": 0.85, "style": "circle"
                }
            }
        },
        "priority": "high",
        "rationale": "餐厅用最大红色圆形符号突出主体地位，酒吧用粉色小圆区分夜生活场景"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "food_COLOR_SCHEME",
        "decision_type": "COLOR_SCHEME",
        "map_type": "food",
        "audience_level": "public",
        "parameters": {
            "palette": {
                "primary": "#ef4444",
                "secondary": "#f59e0b",
                "accent": "#8b5cf6",
                "background": "#fef2f2"
            },
            "rules": [
                "主色不超过4种",
                "暖红橙色调为主(e44f44/f59e0b)激发食欲",
                "咖啡用紫色(8b5cf6)提供差异化识别",
                "快餐用金色(f59e0b)表现快捷便利感",
                "酒吧用粉色(ec4899)表现轻松氛围",
                "浅粉底色(fef2f2)烘托温馨美食氛围"
            ]
        },
        "priority": "high",
        "rationale": "暖红橙色调激发食欲，配合浅粉底色营造温馨、诱人的美食探索体验"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "food_ANNOTATION_RULE",
        "decision_type": "ANNOTATION_RULE",
        "map_type": "food",
        "audience_level": "public",
        "parameters": {
            "font_family": "sans-serif",
            "title_size": 15,
            "label_size": 11,
            "min_spacing": 3,
            "placement": "优先右侧",
            "restaurant_label": {
                "font_size": 12,
                "placement": "右侧偏移5px",
                "color": "#991b1b",
                "font_weight": "bold"
            },
            "cafe_label": {
                "font_size": 10,
                "placement": "右侧偏移4px",
                "color": "#4b5563",
                "font_weight": "normal"
            }
        },
        "priority": "high",
        "rationale": "餐厅注记加粗放大，咖啡馆用小字，在密集餐饮区域自动隐藏次要注记避免拥挤"
    })

    # ---------- basic ----------
    decisions.append({
        "label": "CartographicDecision",
        "name": "basic_LAYER_CONFIG",
        "decision_type": "LAYER_CONFIG",
        "map_type": "basic",
        "audience_level": "public",
        "parameters": {
            "layers": [
                {"name": "waterways", "order": 1, "data_source": "OSM",
                 "osm_tags": "waterway=*|natural=water",
                 "symbol_type": "AreaSymbol"},
                {"name": "green_spaces", "order": 2, "data_source": "OSM",
                 "osm_tags": "leisure=park|landuse=forest|natural=wood",
                 "symbol_type": "AreaSymbol"},
                {"name": "boundaries", "order": 3, "data_source": "OSM",
                 "osm_tags": "boundary=administrative",
                 "symbol_type": "LineSymbol"},
                {"name": "place_labels", "order": 4, "data_source": "OSM",
                 "osm_tags": "place=*",
                 "symbol_type": "PointSymbol"},
                {"name": "landuse", "order": 5, "data_source": "OSM",
                 "osm_tags": "landuse=*",
                 "symbol_type": "AreaSymbol"}
            ]
        },
        "priority": "high",
        "rationale": "基础地图提供标准底图，涵盖水系、绿地、边界、地名标注和土地利用五大图层"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "basic_SYMBOL_SCHEME",
        "decision_type": "SYMBOL_SCHEME",
        "map_type": "basic",
        "audience_level": "public",
        "parameters": {
            "symbols": {
                "water_element": {
                    "type": "AreaSymbol", "color": "#46b8da", "weight": 2,
                    "fillColor": "#bae6fd", "fillOpacity": 0.6, "style": "fill"
                },
                "green_element": {
                    "type": "AreaSymbol", "color": "#22c55e", "weight": 1,
                    "fillColor": "#bbf7d0", "fillOpacity": 0.5, "style": "fill"
                },
                "boundary_element": {
                    "type": "LineSymbol", "color": "#6b7280", "weight": 2,
                    "opacity": 0.8, "style": "dashed"
                },
                "place_element": {
                    "type": "PointSymbol", "color": "#374151", "size": 5,
                    "opacity": 0.9, "style": "circle"
                },
                "landuse_element": {
                    "type": "AreaSymbol", "color": "#e8e8e8", "weight": 1,
                    "fillColor": "#f3f4f6", "fillOpacity": 0.4, "style": "fill"
                }
            }
        },
        "priority": "high",
        "rationale": "基础地图符号以自然色调为主，水系蓝、绿地绿、边界灰虚、土地浅灰填充"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "basic_COLOR_SCHEME",
        "decision_type": "COLOR_SCHEME",
        "map_type": "basic",
        "audience_level": "public",
        "parameters": {
            "palette": {
                "primary": "#374151",
                "secondary": "#46b8da",
                "accent": "#22c55e",
                "background": "#f9fafb"
            },
            "rules": [
                "主色不超过5种",
                "水系统一蓝色系(46b8da)保持行业惯例",
                "植被统一绿色系(22c55e)，填充浅绿(bbf7d0)",
                "边界用灰色虚线(6b7280)不与要素争视觉注意力",
                "地名用深灰(374151)确保可读性",
                "底图背景用极浅灰(f9fafb)提供中性衬底"
            ]
        },
        "priority": "high",
        "rationale": "自然色调为主，蓝色水系、绿色植被、灰色边界，形成经典基础地图配色"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "basic_ANNOTATION_RULE",
        "decision_type": "ANNOTATION_RULE",
        "map_type": "basic",
        "audience_level": "public",
        "parameters": {
            "font_family": "sans-serif",
            "title_size": 16,
            "label_size": 12,
            "min_spacing": 3,
            "placement": "优先下方",
            "water_label": {
                "font_size": 12,
                "placement": "沿水系走向",
                "color": "#1e40af",
                "font_weight": "italic"
            },
            "place_label": {
                "font_size": 11,
                "placement": "右侧偏移4px",
                "color": "#374151",
                "font_weight": "bold"
            }
        },
        "priority": "high",
        "rationale": "水系注记斜体蓝色沿走向排列，地名加粗置于右侧，保持基础底图信息简洁易读"
    })

    # ---------- administrative ----------
    decisions.append({
        "label": "CartographicDecision",
        "name": "administrative_LAYER_CONFIG",
        "decision_type": "LAYER_CONFIG",
        "map_type": "administrative",
        "audience_level": "public",
        "parameters": {
            "layers": [
                {"name": "admin_boundaries", "order": 1, "data_source": "OSM",
                 "osm_tags": "boundary=administrative&admin_level=4|admin_level=5|admin_level=6",
                 "symbol_type": "LineSymbol"},
                {"name": "district_boundaries", "order": 2, "data_source": "OSM",
                 "osm_tags": "boundary=administrative&admin_level=7|admin_level=8",
                 "symbol_type": "AreaSymbol"},
                {"name": "city_labels", "order": 3, "data_source": "OSM",
                 "osm_tags": "place=city|place=town",
                 "symbol_type": "PointSymbol"},
                {"name": "town_labels", "order": 4, "data_source": "OSM",
                 "osm_tags": "place=village|place=hamlet",
                 "symbol_type": "PointSymbol"}
            ]
        },
        "priority": "high",
        "rationale": "行政区划图按行政级别分层，市级边界、区县界线、城镇标注、村级标注四个层次"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "administrative_SYMBOL_SCHEME",
        "decision_type": "SYMBOL_SCHEME",
        "map_type": "administrative",
        "audience_level": "public",
        "parameters": {
            "symbols": {
                "admin_boundary_element": {
                    "type": "LineSymbol", "color": "#6b7280", "weight": 3,
                    "opacity": 0.9, "style": "solid"
                },
                "district_boundary_element": {
                    "type": "AreaSymbol", "color": "#9ca3af", "weight": 2,
                    "fillColor": "#f3f4f6", "fillOpacity": 0.3, "style": "fill"
                },
                "city_label_element": {
                    "type": "PointSymbol", "color": "#111827", "size": 7,
                    "opacity": 1.0, "style": "square"
                },
                "town_label_element": {
                    "type": "PointSymbol", "color": "#374151", "size": 4,
                    "opacity": 0.9, "style": "circle"
                }
            }
        },
        "priority": "high",
        "rationale": "市级边界用粗实线突出，区县边界用浅灰填充区分，城市标注用大号方块"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "administrative_COLOR_SCHEME",
        "decision_type": "COLOR_SCHEME",
        "map_type": "administrative",
        "audience_level": "public",
        "parameters": {
            "palette": {
                "primary": "#6b7280",
                "secondary": "#9ca3af",
                "accent": "#4f46e5",
                "background": "#ffffff"
            },
            "rules": [
                "主色不超过4种",
                "行政边界用灰色系(6b7280/9ca3af)弱化但不失辨识",
                "区县填充用极浅灰色(f3f4f6)避免视觉压迫",
                "城市标注用深色(111827)确保可读",
                "区县分色填充使用区分色(accent: 4f46e5)相邻区域用不同色相",
                "纯白底色(ffffff)适合打印和多场景叠加"
            ]
        },
        "priority": "high",
        "rationale": "区分色填充相邻行政区，灰色系边界线突出行政关系的专业感和权威感"
    })
    decisions.append({
        "label": "CartographicDecision",
        "name": "administrative_ANNOTATION_RULE",
        "decision_type": "ANNOTATION_RULE",
        "map_type": "administrative",
        "audience_level": "public",
        "parameters": {
            "font_family": "sans-serif",
            "title_size": 18,
            "label_size": 13,
            "min_spacing": 5,
            "placement": "优先面状中心",
            "city_label": {
                "font_size": 15,
                "placement": "面状中心",
                "color": "#111827",
                "font_weight": "bold"
            },
            "district_label": {
                "font_size": 12,
                "placement": "面状中心",
                "color": "#4b5563",
                "font_weight": "normal"
            }
        },
        "priority": "high",
        "rationale": "行政名称注记居中放置在区域中心，城市名大号加粗，区县名常规字号"
    })

    return decisions


# ====================================================================
# 3. LayerConfig 节点 (每种 MapType 3-5个)
# ====================================================================
def build_layer_configs():
    """构建 LayerConfig 节点。"""
    layers = []

    # ---- traffic: 5 layers ----
    layers.append({
        "label": "LayerConfig",
        "name": "traffic_motorway_roads",
        "layer_name": "motorway_roads",
        "layer_order": 1,
        "visibility_default": True,
        "min_zoom": 10,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "highway=motorway|highway=trunk|highway=primary",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "traffic_secondary_roads",
        "layer_name": "secondary_roads",
        "layer_order": 2,
        "visibility_default": True,
        "min_zoom": 12,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "highway=secondary|highway=tertiary",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "traffic_railway_lines",
        "layer_name": "railway_lines",
        "layer_order": 3,
        "visibility_default": True,
        "min_zoom": 10,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "railway=*",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "traffic_subway_lines",
        "layer_name": "subway_lines",
        "layer_order": 4,
        "visibility_default": True,
        "min_zoom": 12,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "railway=subway",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "traffic_bus_stations",
        "layer_name": "bus_stations",
        "layer_order": 5,
        "visibility_default": True,
        "min_zoom": 14,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "highway=bus_stop|amenity=bus_station",
        "symbol_type": "PointSymbol"
    })

    # ---- tourism: 5 layers ----
    layers.append({
        "label": "LayerConfig",
        "name": "tourism_attractions",
        "layer_name": "attractions",
        "layer_order": 1,
        "visibility_default": True,
        "min_zoom": 10,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "tourism=attraction|historic=*",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "tourism_museums",
        "layer_name": "museums",
        "layer_order": 2,
        "visibility_default": True,
        "min_zoom": 11,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "tourism=museum",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "tourism_hotels",
        "layer_name": "hotels",
        "layer_order": 3,
        "visibility_default": True,
        "min_zoom": 13,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "tourism=hotel",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "tourism_restaurants",
        "layer_name": "tourism_restaurants",
        "layer_order": 4,
        "visibility_default": True,
        "min_zoom": 14,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=restaurant",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "tourism_viewpoints",
        "layer_name": "viewpoints",
        "layer_order": 5,
        "visibility_default": False,
        "min_zoom": 14,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "tourism=viewpoint",
        "symbol_type": "PointSymbol"
    })

    # ---- campus: 5 layers ----
    layers.append({
        "label": "LayerConfig",
        "name": "campus_buildings",
        "layer_name": "buildings",
        "layer_order": 1,
        "visibility_default": True,
        "min_zoom": 15,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "building=*",
        "symbol_type": "AreaSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "campus_education_facilities",
        "layer_name": "education_facilities",
        "layer_order": 2,
        "visibility_default": True,
        "min_zoom": 15,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=university|amenity=school|amenity=college",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "campus_sports_facilities",
        "layer_name": "sports_facilities",
        "layer_order": 3,
        "visibility_default": True,
        "min_zoom": 15,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "leisure=sports_centre|leisure=pitch|leisure=stadium",
        "symbol_type": "AreaSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "campus_footways",
        "layer_name": "footways",
        "layer_order": 4,
        "visibility_default": True,
        "min_zoom": 16,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "highway=footway|highway=path",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "campus_amenities",
        "layer_name": "campus_amenities",
        "layer_order": 5,
        "visibility_default": True,
        "min_zoom": 16,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=library|amenity=canteen|amenity=parking",
        "symbol_type": "PointSymbol"
    })

    # ---- food: 4 layers ----
    layers.append({
        "label": "LayerConfig",
        "name": "food_restaurants",
        "layer_name": "restaurants",
        "layer_order": 1,
        "visibility_default": True,
        "min_zoom": 14,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=restaurant",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "food_cafes",
        "layer_name": "cafes",
        "layer_order": 2,
        "visibility_default": True,
        "min_zoom": 14,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=cafe",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "food_fast_food",
        "layer_name": "fast_food",
        "layer_order": 3,
        "visibility_default": True,
        "min_zoom": 14,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=fast_food",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "food_bars",
        "layer_name": "bars",
        "layer_order": 4,
        "visibility_default": True,
        "min_zoom": 15,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "amenity=bar|amenity=pub",
        "symbol_type": "PointSymbol"
    })

    # ---- basic: 5 layers ----
    layers.append({
        "label": "LayerConfig",
        "name": "basic_waterways",
        "layer_name": "waterways",
        "layer_order": 1,
        "visibility_default": True,
        "min_zoom": 8,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "waterway=*|natural=water",
        "symbol_type": "AreaSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "basic_green_spaces",
        "layer_name": "green_spaces",
        "layer_order": 2,
        "visibility_default": True,
        "min_zoom": 10,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "leisure=park|landuse=forest|natural=wood",
        "symbol_type": "AreaSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "basic_boundaries",
        "layer_name": "boundaries",
        "layer_order": 3,
        "visibility_default": True,
        "min_zoom": 8,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "boundary=administrative",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "basic_place_labels",
        "layer_name": "place_labels",
        "layer_order": 4,
        "visibility_default": True,
        "min_zoom": 8,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "place=*",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "basic_landuse",
        "layer_name": "landuse",
        "layer_order": 5,
        "visibility_default": False,
        "min_zoom": 12,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "landuse=*",
        "symbol_type": "AreaSymbol"
    })

    # ---- administrative: 4 layers ----
    layers.append({
        "label": "LayerConfig",
        "name": "administrative_admin_boundaries",
        "layer_name": "admin_boundaries",
        "layer_order": 1,
        "visibility_default": True,
        "min_zoom": 8,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "boundary=administrative&admin_level=4|admin_level=5|admin_level=6",
        "symbol_type": "LineSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "administrative_district_boundaries",
        "layer_name": "district_boundaries",
        "layer_order": 2,
        "visibility_default": True,
        "min_zoom": 10,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "boundary=administrative&admin_level=7|admin_level=8",
        "symbol_type": "AreaSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "administrative_city_labels",
        "layer_name": "city_labels",
        "layer_order": 3,
        "visibility_default": True,
        "min_zoom": 8,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "place=city|place=town",
        "symbol_type": "PointSymbol"
    })
    layers.append({
        "label": "LayerConfig",
        "name": "administrative_town_labels",
        "layer_name": "town_labels",
        "layer_order": 4,
        "visibility_default": False,
        "min_zoom": 12,
        "max_zoom": 18,
        "data_source": "OSM",
        "osm_tags": "place=village|place=hamlet",
        "symbol_type": "PointSymbol"
    })

    return layers


# ====================================================================
# 4. 新增 MapSymbol 节点（为各 MapType 专用符号）
# ====================================================================
def build_map_symbols():
    """构建新增的 MapSymbol 节点，为各 MapType 提供专用符号。"""
    symbols = [
        # traffic 专用符号
        {
            "label": "MapSymbol", "name": "traffic_motorway_symbol",
            "symbol_type": "LineSymbol", "color": "#e892a2", "size": 5,
            "style": "solid", "opacity": 0.9,
            "description": "交通图-高速公路符号，粗线红色"
        },
        {
            "label": "MapSymbol", "name": "traffic_primary_road_symbol",
            "symbol_type": "LineSymbol", "color": "#fbbf24", "size": 4,
            "style": "solid", "opacity": 0.85,
            "description": "交通图-主干道符号，黄色实线"
        },
        {
            "label": "MapSymbol", "name": "traffic_secondary_road_symbol",
            "symbol_type": "LineSymbol", "color": "#d1d5db", "size": 3,
            "style": "solid", "opacity": 0.8,
            "description": "交通图-次干道符号，浅灰实线"
        },
        {
            "label": "MapSymbol", "name": "traffic_bus_stop_symbol",
            "symbol_type": "PointSymbol", "color": "#f97316", "size": 6,
            "style": "circle", "opacity": 1.0,
            "description": "交通图-公交站符号，橙色圆形"
        },
        # tourism 专用符号
        {
            "label": "MapSymbol", "name": "tourism_attraction_symbol",
            "symbol_type": "PointSymbol", "color": "#dc2626", "size": 10,
            "style": "star", "opacity": 1.0,
            "description": "旅游图-景点符号，红色星形"
        },
        {
            "label": "MapSymbol", "name": "tourism_museum_symbol",
            "symbol_type": "PointSymbol", "color": "#f59e0b", "size": 8,
            "style": "diamond", "opacity": 1.0,
            "description": "旅游图-博物馆符号，金色菱形"
        },
        {
            "label": "MapSymbol", "name": "tourism_viewpoint_symbol",
            "symbol_type": "PointSymbol", "color": "#10b981", "size": 7,
            "style": "triangle", "opacity": 0.9,
            "description": "旅游图-观景点符号，绿色三角"
        },
        # campus 专用符号
        {
            "label": "MapSymbol", "name": "campus_building_symbol",
            "symbol_type": "AreaSymbol", "color": "#3b82f6", "size": 2,
            "fillColor": "#93c5fd", "fillOpacity": 0.5,
            "style": "fill", "opacity": 1.0,
            "description": "校园图-建筑符号，蓝色填充"
        },
        {
            "label": "MapSymbol", "name": "campus_edu_symbol",
            "symbol_type": "PointSymbol", "color": "#10b981", "size": 7,
            "style": "square", "opacity": 1.0,
            "description": "校园图-教育设施符号，绿色方块"
        },
        {
            "label": "MapSymbol", "name": "campus_sports_symbol",
            "symbol_type": "AreaSymbol", "color": "#f59e0b", "size": 1,
            "fillColor": "#fde68a", "fillOpacity": 0.4,
            "style": "fill", "opacity": 1.0,
            "description": "校园图-运动场地符号，黄色填充"
        },
        {
            "label": "MapSymbol", "name": "campus_footway_symbol",
            "symbol_type": "LineSymbol", "color": "#a3a3a3", "size": 1,
            "style": "dashed", "opacity": 0.7,
            "description": "校园图-步道符号，浅灰虚线"
        },
        # food 专用符号
        {
            "label": "MapSymbol", "name": "food_restaurant_symbol",
            "symbol_type": "PointSymbol", "color": "#ef4444", "size": 8,
            "style": "circle", "opacity": 1.0,
            "description": "美食图-餐厅符号，红色圆形"
        },
        {
            "label": "MapSymbol", "name": "food_cafe_symbol",
            "symbol_type": "PointSymbol", "color": "#8b5cf6", "size": 6,
            "style": "circle", "opacity": 0.9,
            "description": "美食图-咖啡厅符号，紫色圆形"
        },
        {
            "label": "MapSymbol", "name": "food_fastfood_symbol",
            "symbol_type": "PointSymbol", "color": "#f59e0b", "size": 6,
            "style": "diamond", "opacity": 0.9,
            "description": "美食图-快餐符号，金色菱形"
        },
        {
            "label": "MapSymbol", "name": "food_bar_symbol",
            "symbol_type": "PointSymbol", "color": "#ec4899", "size": 5,
            "style": "circle", "opacity": 0.85,
            "description": "美食图-酒吧符号，粉色圆形"
        },
        # basic 专用符号
        {
            "label": "MapSymbol", "name": "basic_water_symbol",
            "symbol_type": "AreaSymbol", "color": "#46b8da", "size": 2,
            "fillColor": "#bae6fd", "fillOpacity": 0.6,
            "style": "fill", "opacity": 0.8,
            "description": "基础图-水系符号，蓝色填充"
        },
        {
            "label": "MapSymbol", "name": "basic_green_symbol",
            "symbol_type": "AreaSymbol", "color": "#22c55e", "size": 1,
            "fillColor": "#bbf7d0", "fillOpacity": 0.5,
            "style": "fill", "opacity": 0.8,
            "description": "基础图-绿地符号，绿色填充"
        },
        {
            "label": "MapSymbol", "name": "basic_landuse_symbol",
            "symbol_type": "AreaSymbol", "color": "#e8e8e8", "size": 1,
            "fillColor": "#f3f4f6", "fillOpacity": 0.4,
            "style": "fill", "opacity": 0.7,
            "description": "基础图-土地利用符号，浅灰填充"
        },
        # administrative 专用符号
        {
            "label": "MapSymbol", "name": "admin_boundary_symbol",
            "symbol_type": "LineSymbol", "color": "#6b7280", "size": 3,
            "style": "solid", "opacity": 0.9,
            "description": "行政区划图-行政边界符号，灰色粗实线"
        },
        {
            "label": "MapSymbol", "name": "admin_district_symbol",
            "symbol_type": "AreaSymbol", "color": "#9ca3af", "size": 2,
            "fillColor": "#f3f4f6", "fillOpacity": 0.3,
            "style": "fill", "opacity": 0.7,
            "description": "行政区划图-区县界符号，浅灰填充"
        },
        {
            "label": "MapSymbol", "name": "admin_city_label_symbol",
            "symbol_type": "PointSymbol", "color": "#111827", "size": 7,
            "style": "square", "opacity": 1.0,
            "description": "行政区划图-城市标注符号，深色大方块"
        },
        {
            "label": "MapSymbol", "name": "admin_town_label_symbol",
            "symbol_type": "PointSymbol", "color": "#374151", "size": 4,
            "style": "circle", "opacity": 0.9,
            "description": "行政区划图-村镇标注符号，灰色小圆"
        }
    ]
    return symbols


# ====================================================================
# 5. 生成所有关系
# ====================================================================
def build_relations(layer_configs, map_symbols):
    """
    构建所有新关系，包括:
    - MapType -> HAS_DECISION -> CartographicDecision (24)
    - CartographicDecision(LAYER_CONFIG) -> SPECIFIES_LAYER -> LayerConfig
    - CartographicDecision(SYMBOL_SCHEME) -> SPECIFIES_SYMBOL -> MapSymbol
    - audience_factor -> INFLUENCES -> CartographicDecision (24)
    - scale_factor -> INFLUENCES -> CartographicDecision (24)
    - purpose_factor -> DETERMINES -> CartographicDecision (24)
    - CartographicDecision -> FOLLOWS -> CartographyRule
    - LayerConfig -> BELONGS_TO -> MapType
    """
    relations = []

    # 5a. MapType -> HAS_DECISION -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": mt,
                "to": decision_name,
                "type": "HAS_DECISION",
                "properties": {
                    "description": "{}地图包含{}类型决策".format(mt, dt),
                    "priority": "high"
                }
            })

    # 5b. CartographicDecision(LAYER_CONFIG) -> SPECIFIES_LAYER -> LayerConfig
    # 建立 map_type 到其 layer_configs 的映射
    layer_by_map = {}
    for lc in layer_configs:
        mt = lc["name"].split("_")[0]
        if mt not in layer_by_map:
            layer_by_map[mt] = []
        layer_by_map[mt].append(lc)

    for mt in MAP_TYPES:
        decision_name = "{}_LAYER_CONFIG".format(mt)
        for lc in layer_by_map.get(mt, []):
            relations.append({
                "from": decision_name,
                "to": lc["name"],
                "type": "SPECIFIES_LAYER",
                "properties": {
                    "description": "{}决策指定{}图层(order={}, zoom={}-{})".format(
                        decision_name, lc["layer_name"],
                        lc["layer_order"], lc["min_zoom"], lc["max_zoom"]
                    )
                }
            })

    # 5c. CartographicDecision(SYMBOL_SCHEME) -> SPECIFIES_SYMBOL -> MapSymbol
    # 每个 map_type 的 SYMBOL_SCHEME 决策关联其专用符号
    symbol_by_map = {
        "traffic": [
            "traffic_motorway_symbol", "traffic_primary_road_symbol",
            "traffic_secondary_road_symbol", "subway_symbol",
            "traffic_bus_stop_symbol", "railway_symbol"
        ],
        "tourism": [
            "tourism_attraction_symbol", "tourism_museum_symbol",
            "hotel_symbol", "restaurant_symbol", "tourism_viewpoint_symbol"
        ],
        "campus": [
            "campus_building_symbol", "campus_edu_symbol",
            "campus_sports_symbol", "campus_footway_symbol",
            "building_symbol"
        ],
        "food": [
            "food_restaurant_symbol", "food_cafe_symbol",
            "food_fastfood_symbol", "food_bar_symbol"
        ],
        "basic": [
            "basic_water_symbol", "basic_green_symbol",
            "basic_landuse_symbol", "boundary_symbol",
            "green_space_symbol", "waterway_symbol"
        ],
        "administrative": [
            "admin_boundary_symbol", "admin_district_symbol",
            "admin_city_label_symbol", "admin_town_label_symbol"
        ]
    }
    for mt in MAP_TYPES:
        decision_name = "{}_SYMBOL_SCHEME".format(mt)
        for sym_name in symbol_by_map.get(mt, []):
            relations.append({
                "from": decision_name,
                "to": sym_name,
                "type": "SPECIFIES_SYMBOL",
                "properties": {
                    "description": "{}决策指定使用{}符号".format(decision_name, sym_name)
                }
            })

    # 5d. audience_factor -> INFLUENCES -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": "audience_factor",
                "to": decision_name,
                "type": "INFLUENCES",
                "properties": {
                    "description": "目标受众因素影响{}的{}决策".format(mt, dt),
                    "influence_type": "audience"
                }
            })

    # 5e. scale_factor -> INFLUENCES -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": "scale_factor",
                "to": decision_name,
                "type": "INFLUENCES",
                "properties": {
                    "description": "比例尺因素影响{}的{}决策".format(mt, dt),
                    "influence_type": "scale"
                }
            })

    # 5f. purpose_factor -> DETERMINES -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": "purpose_factor",
                "to": decision_name,
                "type": "DETERMINES",
                "properties": {
                    "description": "地图用途因素决定{}的{}决策".format(mt, dt),
                    "priority": "high"
                }
            })

    # 5g. CartographicDecision -> FOLLOWS -> CartographyRule
    # 每个决策遵循对应的制图规则
    rule_mapping = {
        "LAYER_CONFIG": "scale_selection",
        "SYMBOL_SCHEME": "symbol_design",
        "COLOR_SCHEME": "color_scheme",
        "ANNOTATION_RULE": "annotation_rule"
    }
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            rule_name = rule_mapping.get(dt)
            if rule_name:
                relations.append({
                    "from": decision_name,
                    "to": rule_name,
                    "type": "FOLLOWS",
                    "properties": {
                        "description": "{}决策遵循{}制图规则".format(decision_name, rule_name)
                    }
                })

    # 5h. LayerConfig -> BELONGS_TO -> MapType (每个 layer 属于其 map_type)
    for lc in layer_configs:
        mt = lc["name"].split("_")[0]
        relations.append({
            "from": lc["name"],
            "to": mt,
            "type": "BELONGS_TO",
            "properties": {
                "description": "{}图层属于{}地图类型".format(lc["layer_name"], mt)
            }
        })

    # 5i. CartographicDecision(COLOR_SCHEME) -> color_constraint 关联
    for mt in MAP_TYPES:
        decision_name = "{}_COLOR_SCHEME".format(mt)
        relations.append({
            "from": decision_name,
            "to": "color_constraint",
            "type": "CONSTRAINED_BY",
            "properties": {
                "description": "{}决策受色彩约束限制".format(decision_name)
            }
        })

    # 5j. CartographicDecision(ANNOTATION_RULE) -> audience_factor 关联
    for mt in MAP_TYPES:
        decision_name = "{}_ANNOTATION_RULE".format(mt)
        relations.append({
            "from": decision_name,
            "to": "audience_factor",
            "type": "CONSIDERS",
            "properties": {
                "description": "{}决策考虑目标受众因素".format(decision_name)
            }
        })

    # 5k. color_constraint -> INFLUENCES -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": "color_constraint",
                "to": decision_name,
                "type": "INFLUENCES",
                "properties": {
                    "description": "色彩约束因素影响{}的{}决策".format(mt, dt),
                    "influence_type": "color"
                }
            })

    # 5l. density_constraint -> INFLUENCES -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": "density_constraint",
                "to": decision_name,
                "type": "INFLUENCES",
                "properties": {
                    "description": "密度约束因素影响{}的{}决策".format(mt, dt),
                    "influence_type": "density"
                }
            })

    # 5m. LayerConfig -> USES_SYMBOL -> MapSymbol (每个layer关联其对应符号类型, ~28条)
    layer_symbol_mapping = {
        "traffic_motorway_roads": "traffic_motorway_symbol",
        "traffic_secondary_roads": "traffic_secondary_road_symbol",
        "traffic_railway_lines": "railway_symbol",
        "traffic_subway_lines": "subway_symbol",
        "traffic_bus_stations": "traffic_bus_stop_symbol",
        "tourism_attractions": "tourism_attraction_symbol",
        "tourism_museums": "tourism_museum_symbol",
        "tourism_hotels": "hotel_symbol",
        "tourism_restaurants": "restaurant_symbol",
        "tourism_viewpoints": "tourism_viewpoint_symbol",
        "campus_buildings": "campus_building_symbol",
        "campus_education_facilities": "campus_edu_symbol",
        "campus_sports_facilities": "campus_sports_symbol",
        "campus_footways": "campus_footway_symbol",
        "campus_amenities": "building_symbol",
        "food_restaurants": "food_restaurant_symbol",
        "food_cafes": "food_cafe_symbol",
        "food_fast_food": "food_fastfood_symbol",
        "food_bars": "food_bar_symbol",
        "basic_waterways": "basic_water_symbol",
        "basic_green_spaces": "basic_green_symbol",
        "basic_boundaries": "boundary_symbol",
        "basic_place_labels": "poi_symbol",
        "basic_landuse": "basic_landuse_symbol",
        "administrative_admin_boundaries": "admin_boundary_symbol",
        "administrative_district_boundaries": "admin_district_symbol",
        "administrative_city_labels": "admin_city_label_symbol",
        "administrative_town_labels": "admin_town_label_symbol"
    }
    for layer_name, sym_name in layer_symbol_mapping.items():
        relations.append({
            "from": layer_name,
            "to": sym_name,
            "type": "USES_SYMBOL",
            "properties": {
                "description": "{}图层使用{}符号进行渲染".format(layer_name, sym_name)
            }
        })

    # 5n. accessibility_factor -> INFLUENCES -> CartographicDecision (24条)
    for mt in MAP_TYPES:
        for dt in DECISION_TYPES:
            decision_name = "{}_{}".format(mt, dt)
            relations.append({
                "from": "accessibility_factor",
                "to": decision_name,
                "type": "INFLUENCES",
                "properties": {
                    "description": "无障碍约束因素影响{}的{}决策".format(mt, dt),
                    "influence_type": "accessibility"
                }
            })

    # 5o. CartographicDecision(LAYER_CONFIG) -> zoom_level 关联 (6条)
    for mt in MAP_TYPES:
        decision_name = "{}_LAYER_CONFIG".format(mt)
        relations.append({
            "from": decision_name,
            "to": "zoom_level",
            "type": "CONSTRAINED_BY",
            "properties": {
                "description": "{}图层配置受缩放级别约束".format(mt)
            }
        })

    return relations


# ====================================================================
# 6. 主流程：读取 -> 生成 -> 追加 -> 更新统计 -> 写入
# ====================================================================
def main():
    # 检查文件是否存在
    if not os.path.exists(DATA_FILE):
        print("[ERROR] 文件不存在: {}".format(DATA_FILE))
        sys.exit(1)

    # 读取现有数据
    print("[INFO] 读取现有数据: {}".format(DATA_FILE))
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_node_count = len(data["nodes"])
    existing_relation_count = len(data["relations"])
    print("[INFO] 现有节点数: {}, 现有关系数: {}".format(existing_node_count, existing_relation_count))

    # 生成各类节点
    new_maptype = [NEW_MAPTYPE]  # administrative MapType
    decisions = build_decisions()
    layer_configs = build_layer_configs()
    map_symbols = build_map_symbols()

    # 合并新节点
    all_new_nodes = new_maptype + decisions + layer_configs + map_symbols

    new_node_count = len(all_new_nodes)
    print("[INFO] 生成新节点: administrative(1) + CartographicDecision({}) + LayerConfig({}) + MapSymbol({}) = {}".format(
        len(decisions), len(layer_configs), len(map_symbols), new_node_count
    ))

    # 生成新关系
    new_relations = build_relations(layer_configs, map_symbols)
    print("[INFO] 生成新关系: {}".format(len(new_relations)))

    # 追加到数据中
    data["nodes"].extend(all_new_nodes)
    data["relations"].extend(new_relations)

    # 更新 metadata 统计
    data["metadata"]["total_nodes"] = len(data["nodes"])
    data["metadata"]["total_relations"] = len(data["relations"])
    print("[INFO] 更新后总节点数: {}, 总关系数: {}".format(
        data["metadata"]["total_nodes"],
        data["metadata"]["total_relations"]
    ))

    # 写入文件 (UTF-8, 不转义非ASCII字符, 使用2空格缩进)
    print("[INFO] 写入更新后的文件: {}".format(DATA_FILE))
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("[DONE] 数据追加完成!")
    print("  节点: {} -> {} (+{})".format(
        existing_node_count,
        data["metadata"]["total_nodes"],
        data["metadata"]["total_nodes"] - existing_node_count
    ))
    print("  关系: {} -> {} (+{})".format(
        existing_relation_count,
        data["metadata"]["total_relations"],
        data["metadata"]["total_relations"] - existing_relation_count
    ))

    # 统计各个 label 的数量
    label_counts = {}
    for node in data["nodes"]:
        lbl = node["label"]
        label_counts[lbl] = label_counts.get(lbl, 0) + 1

    relation_type_counts = {}
    for rel in data["relations"]:
        rtype = rel["type"]
        relation_type_counts[rtype] = relation_type_counts.get(rtype, 0) + 1

    print("\n[STATS] 各类型节点数量:")
    for lbl, cnt in sorted(label_counts.items()):
        print("  {}: {}".format(lbl, cnt))

    print("\n[STATS] 各类型关系数量:")
    for rtype, cnt in sorted(relation_type_counts.items()):
        print("  {}: {}".format(rtype, cnt))


if __name__ == "__main__":
    main()
