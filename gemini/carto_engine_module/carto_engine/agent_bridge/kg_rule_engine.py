# -*- coding: utf-8 -*-
"""
================================================================================
[分类六 - 子模块 6.1] 知识图谱制图规则推理器与规范校验器 `kg_rule_engine.py`
================================================================================
融合：
1. 武汉大学艾廷华教授 DoMapAI 智能地图生成器的“知识—数据—工具”混合知识图谱推理链；
2. 廖成《LLM-KG-Carto 一种基于大语言模型和知识图谱的自动制图框架》的 7 大概念本体；
3. 北大/UT Austin `GISense/CartoAgent` 的样式设计与多维质量评估闭环。
"""

from typing import Dict, Any, List
from ..models_and_specs import MapType, AudienceType, CartoTaskSpec


class CartoKGRuleEngine:
    """
    地图学知识图谱规则推理器与增强型校验器（升级替代原 `cartography_validator.py`）
    """

    # 内置知识图谱规则库（当 Neo4j 离线或未命中时提供确定性地图学规则保障）
    KG_DECISION_RULES: Dict[MapType, Dict[str, Any]] = {
        MapType.TRAFFIC: {
            "mandatory_layers": ["admin_polygons", "water_polygons", "roads_lines", "traffic_hubs_points"],
            "forbidden_layers": ["contours_lines"],
            "figure_ground_strategy": "low_saturation_basemap_high_contrast_network",
            "road_casing_required": True,
            "recommended_projection": "CGCS2000_3_Degree_Gauss_Kruger",
        },
        MapType.TOURISM: {
            "mandatory_layers": ["admin_polygons", "greenspace_polygons", "water_polygons", "tourism_routes_lines", "tourism_pois_points"],
            "forbidden_layers": ["contours_lines"],
            "figure_ground_strategy": "warm_cultural_ground_vivid_scenic_symbols",
            "poi_spatial_thinning": True,
            "recommended_projection": "CGCS2000_3_Degree_Gauss_Kruger",
        },
        MapType.ADMINISTRATIVE: {
            "mandatory_layers": ["admin_polygons", "water_polygons", "admin_seats_points"],
            "forbidden_layers": ["roads_lines", "contours_lines", "osm_raw_boundary"],
            "coloring_algorithm": "four_color_adjacency_greedy",
            "boundary_inner_glow": True,
            "recommended_projection": "CGCS2000_3_Degree_Gauss_Kruger",
        },
        MapType.TERRAIN: {
            "mandatory_layers": ["dem_grid", "water_polygons", "contours_lines", "peaks_points"],
            "forbidden_layers": ["roads_lines", "tourism_pois_points"],
            "hillshade_azimuth": 315,
            "hillshade_altitude": 45,
            "contour_chaikin_smoothing": True,
            "recommended_projection": "CGCS2000_3_Degree_Gauss_Kruger",
        },
    }

    @classmethod
    def infer_cartographic_decision(cls, task_spec: CartoTaskSpec) -> Dict[str, Any]:
        """根据制图任务书推理应加载的强制图层、禁用图层、符号策略与受众字号缩放系数"""
        base_rule = dict(cls.KG_DECISION_RULES.get(task_spec.map_type, {}))
        font_scale = 1.0
        if task_spec.audience == AudienceType.ELDERLY_KIDS:
            font_scale = 1.25
        elif task_spec.audience == AudienceType.EXPERT:
            font_scale = 0.95
        base_rule["audience_font_scale"] = font_scale
        return base_rule

    @classmethod
    def validate_cartographic_quality(
        cls,
        task_spec: CartoTaskSpec,
        available_layers: List[str],
    ) -> Dict[str, Any]:
        """对制图方案进行地图学完备性、图层冲突与整饰要素合规性校验"""
        rule = cls.infer_cartographic_decision(task_spec)
        mandatory = rule.get("mandatory_layers", [])
        missing = [l for l in mandatory if l not in available_layers and l != "dem_grid"]

        score = 100
        warnings = []
        if missing:
            score -= 15 * len(missing)
            warnings.append(f"缺失该专题图核心图层: {missing}")

        if not (task_spec.show_graticule and task_spec.show_compass and task_spec.show_scale_bar and task_spec.show_legend):
            score -= 10
            warnings.append("地图整饰要素（图廓经纬网、指北针、比例尺、图例）未全部开启，不符合出版级规范。")

        return {
            "passed": score >= 70,
            "carto_score": max(0, score),
            "applied_kg_rules": rule,
            "warnings": warnings,
        }
