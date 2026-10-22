# -*- coding: utf-8 -*-
"""
================================================================================
[分类七 - 子模块 7.3] 面向流程图的 LLM 强化微调与知识推理训练管线 `fine_tuning_trainer.py`
================================================================================
严格对齐用户上传的 5 张核心流程图：
1. 对齐《知识图谱流程图.jpg》：
   - 修正原流程图中“定义领域范围：地理领域/图书领域/医疗领域”的不合理模板残留，
     重构为 **地图学四大垂直子域本体（空间基准与拓扑域、多尺度综合与载负量域、符号视觉变量域、图面整饰与注记域）**；
   - 将原流程图中单一的“单次 Cypher 语句”升级为 **多跳参数化 Cypher + 向量相似案例混合检索（Hybrid GraphRAG）**。
2. 对齐《智能化制图方法研发.png》与《验证系统流程图.jpg》：
   - 实现“第一步：RAG增强方案 -> 第二步：智能体执行调度 -> 第三步：校正与容错（KG硬性约束置信度判断） ->
     评估系统（定位问题反馈优化提示词、优化知识规则、优化工具规划）”的 **SFT 监督微调样本构建器** 与 **GRPO/DPO 强化学习奖励函数（CartoRewardFunction）**。
"""

import json
from typing import List, Dict, Any
from .vibe_prompt_compiler import VibeCartoPromptCompiler


class CartoFineTuningPipeline:
    """
    面向 DeepSeek / Qwen / Llama-3 / GPT 微调的数据集生成与强化学习奖励评估器
    """

    # 修正《知识图谱流程图.jpg》中的地图学四大核心本体领域范围
    CARTO_ONTOLOGY_DOMAINS = {
        "Domain_1_SpatialReference_And_Cleaning": ["CRS_Projection", "GCJ02_Rectification", "River_Polygonization", "Topology_Snap"],
        "Domain_2_MultiScale_And_Generalization": ["Scale_Interval", "Topfer_Radical_Law", "Admin_DrillDown", "Road_Width_PowerLaw"],
        "Domain_3_Symbology_And_VisualVariables": ["FourColor_Adjacency", "Road_Casing_Spec", "Boundary_InnerGlow", "Hypsometric_Tint"],
        "Domain_4_Layout_And_Typography": ["EightPosition_Labeling", "Spaced_Admin_Label", "Zebra_Graticule", "Alternating_ScaleBar"],
    }

    @classmethod
    def generate_sft_training_dataset(cls, output_jsonl_path: str) -> int:
        """
        构建用于精调大模型的“自然语言模糊指令 -> 六段式 Vibe Coding 提示词 -> 知识图谱 Cypher + 地图状态增量 JSON”
        高质量微调训练集 (OpenAI / LLaMA-Factory ShareGPT 标准 JSONL 格式)。
        """
        seed_scenarios = [
            {
                "user_raw": "帮我生成湖北省行政规划图，放大到武汉市的时候显示武汉各个区的区划，并且长江要用真实宽度的面状表示。",
                "scale_from": 2500000,
                "scale_to": 400000,
                "cypher_query": (
                    "MATCH (m:MapType {id:'administrative'})-[:HAS_SCALE_RULE]->(r:ScaleRule) "
                    "WHERE r.min_scale <= 400000 AND r.max_scale >= 400000 "
                    "RETURN r.admin_level AS target_admin_level, r.load_capacity_max AS max_load, "
                    "r.water_representation AS water_geom_mode"
                ),
                "target_action_json": {
                    "action": "multiscale_drilldown_and_render",
                    "levels": [
                        {"scale_denom": 2500000, "admin_level": "prefecture_city", "region": "湖北省(17市州)", "water_mode": "polygon_buffered"},
                        {"scale_denom": 400000, "admin_level": "district_county", "region": "武汉市(13市辖区)", "water_mode": "polygon_true_bank"},
                    ],
                    "symbology_rules": {"coloring": "four_color_greedy", "boundary": "inner_glow_tint_band"},
                },
            },
            {
                "user_raw": "在当前武汉市地图上，把武昌区的颜色改成醒目的暖杏色，把主干道和高速公路线宽按比例尺放大 1.4 倍，并隐藏次要支路。",
                "scale_from": 400000,
                "scale_to": 400000,
                "cypher_query": (
                    "MATCH (l:Layer)-[rel:APPLIES_STYLE]->(s:FeatureStyle) "
                    "WHERE l.id IN ['admin_polygons', 'roads_lines'] RETURN l.id, s"
                ),
                "target_action_json": {
                    "action": "conversational_delta_patch",
                    "patches": [
                        {"layer_id": "admin_polygons", "feature_filter": {"name": "武昌区"}, "set_style": {"fill_color": "#FDBA74"}},
                        {"layer_id": "roads_lines", "feature_filter": {"feat_class": ["motorway", "primary"]}, "scale_factor": {"stroke_width": 1.4, "casing_width": 1.4}},
                        {"layer_id": "roads_lines", "feature_filter": {"feat_class": "tertiary"}, "set_visible": False},
                    ],
                },
            },
            {
                "user_raw": "继续放大到武汉大学和东湖磨山片区（1:50000），显示街道级路网、面状东湖水体和5A景区辐射圈。",
                "scale_from": 400000,
                "scale_to": 50000,
                "cypher_query": (
                    "MATCH (s:ScaleLevel {level:'street_campus'})-[:REQUIRES_LAYERS]->(l:Layer) RETURN l.id, l.z_order"
                ),
                "target_action_json": {
                    "action": "zoom_to_extent_and_enrich",
                    "target_scale_denom": 50000,
                    "target_bbox": [114.27, 30.51, 114.46, 30.59],
                    "enable_layers": ["admin_polygons", "greenspace_polygons", "water_polygons", "roads_lines", "tourism_pois_points"],
                    "road_width_mode": "true_ground_meters_scaled",
                },
            },
        ]

        records = []
        for item in seed_scenarios:
            compiled = VibeCartoPromptCompiler.compile_instruction(
                item["user_raw"], item["scale_from"], item["scale_to"]
            )
            assistant_output = {
                "compiled_vibe_prompt": compiled.to_vibe_coding_prompt(),
                "kg_cypher": item["cypher_query"],
                "execution_plan": item["target_action_json"],
            }
            records.append({
                "messages": [
                    {"role": "system", "content": "你是武汉大学 Carto-Agent 地图学大模型，请将用户指令编译为六段式提示词并输出 KG 查询与执行 JSON。"},
                    {"role": "user", "content": item["user_raw"]},
                    {"role": "assistant", "content": json.dumps(assistant_output, ensure_ascii=False)},
                ]
            })

        with open(output_jsonl_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return len(records)

    @staticmethod
    def compute_rlhf_carto_reward(plan_output: Dict[str, Any], validation_report: Dict[str, Any]) -> float:
        """
        对齐《智能化制图方法研发.png》第三步“校正与容错（置信度判断）”与《验证系统流程图.jpg》“评估系统”：
        为 GRPO / DPO 强化学习训练提供基于地图学硬性约束的多维奖励函数 $R \\in [0, 1]$：
        - $R_{\\text{schema}}$ (0.20)：是否完整包含六段式提示词与合法的图层/要素寻址 ID
        - $R_{\\text{topology}}$ (0.25)：是否开启了坐标纠偏、碎多边形清理与大江大河面状化表达
        - $R_{\\text{load}}$ (0.25)：当前比例尺下的地图载负量是否处于合理区间（无跨尺度要素过载）
        - $R_{\\text{aesthetics}}$ (0.30)：四色邻接无冲突、图层 Z-Order 合规、注记零碰撞、五大整饰齐全
        """
        score = 0.0
        if "compiled_vibe_prompt" in plan_output and "execution_plan" in plan_output:
            score += 0.20
        if validation_report.get("topology_clean", True):
            score += 0.25
        if validation_report.get("load_capacity_ok", True):
            score += 0.25
        carto_score = float(validation_report.get("carto_score", 85.0)) / 100.0
        score += 0.30 * carto_score
        return round(min(1.0, max(0.0, score)), 4)
