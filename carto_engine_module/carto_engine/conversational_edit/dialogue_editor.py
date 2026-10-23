# -*- coding: utf-8 -*-
"""
================================================================================
[分类九 - 子模块 9.2] 大模型多轮对话增量修改执行器 `conversational_edit/dialogue_editor.py`
================================================================================
支持通过自然语言对话（或 LLM 输出的 JSON Patch）对已生成的地图执行精确修改：
1. **针对特定地理要素的精准样式修改**：如“将武昌区突出显示为珊瑚橙色 `#FB923C`”、“将长江水体加深为深海蓝 `#3B82F6`”；
2. **针对特定等级要素的符号缩放与显隐控制**：如“把高速公路和主干道线宽加粗 1.4 倍，隐藏支路”；
3. **针对比例尺与空间视口的联动缩放修改**：如“将地图从湖北省放大到武汉市（1:40万）”、“继续放大到武昌—东湖核心区（1:5万）”；
4. **新增自定义高亮圈或专题标注**：如“高亮标记武汉大学与黄鹤楼核心文旅走廊”。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from .map_scene_state import MapSceneState


@dataclass
class MapDeltaPatch:
    """单条增量修改原子操作（由大模型解析用户追问后生成）"""
    operation_type: str                            # 'style_feature', 'scale_class_width', 'toggle_visibility', 'zoom_scale_and_bbox', 'update_title'
    target_layer_id: Optional[str] = None          # 目标图层 ID (如 'admin_polygons', 'roads_lines', 'water_polygons')
    target_feature_names: List[str] = field(default_factory=list)  # 精确匹配要素名 (如 ['武昌区', '洪山区'])
    target_feat_classes: List[str] = field(default_factory=list)   # 匹配要素分类 (如 ['motorway', 'primary'])
    style_updates: Dict[str, Any] = field(default_factory=dict)    # {'fill_color': '#FB923C', 'stroke_color': '#C2410C'}
    width_multiplier: Optional[float] = None       # 线宽/符号尺寸缩放倍率
    visible: Optional[bool] = None
    new_scale_denom: Optional[int] = None
    new_bbox_wgs84: Optional[Tuple[float, float, float, float]] = None
    new_title: Optional[str] = None
    new_subtitle: Optional[str] = None
    rationale: str = ""                            # 大模型给出的地图学修改依据说明


class ConversationalMapEditor:
    """
    对话式地图增量修改引擎：支持自然语言语义解析 + 结构化 Delta Patch 应用
    """

    @classmethod
    def parse_natural_language_to_patches(
        cls,
        user_edit_instruction: str,
        scene_state: MapSceneState,
    ) -> List[MapDeltaPatch]:
        """
        解析用户的自然语言修改指令（结合当前 `scene_state` 中注册的精确图层名与要素名），
        生成确定性的 `MapDeltaPatch` 列表。
        """
        text = user_edit_instruction.strip()
        patches: List[MapDeltaPatch] = []

        # 1. 检测要素级颜色高亮修改（例如：“把武昌区改成暖橙色/珊瑚红”）
        color_keywords = {
            "暖橙": "#FDBA74",
            "珊瑚": "#FCA5A5",
            "琥珀金": "#FDE047",
            "翡翠绿": "#86EFAC",
            "深海蓝": "#60A5FA",
            "丁香紫": "#D8B4FE",
        }
        if "admin_polygons" in scene_state.layers:
            admin_node = scene_state.layers["admin_polygons"]
            all_names = [str(n) for n in admin_node.gdf["name"].tolist() if str(n).strip()]
            matched_names = [nm for nm in all_names if nm in text or nm.replace("区", "").replace("市", "") in text]
            if matched_names:
                chosen_color = "#FDBA74"
                for ck, hex_v in color_keywords.items():
                    if ck in text:
                        chosen_color = hex_v
                        break
                patches.append(
                    MapDeltaPatch(
                        operation_type="style_feature",
                        target_layer_id="admin_polygons",
                        target_feature_names=matched_names,
                        style_updates={"fill_color": chosen_color, "stroke_color": "#C2410C", "stroke_width": 1.8},
                        rationale=f"精准寻址政区要素 {matched_names}，将其专题高亮填充色更新为 {chosen_color} 并強化边界描边。",
                    )
                )

        # 2. 检测道路线宽缩放或支路显隐修改
        if any(k in text for k in ["加粗", "线宽", "道路", "高速", "主干道"]):
            mult = 1.35
            for token in ["1.2", "1.3", "1.4", "1.5", "1.8", "2.0"]:
                if token in text:
                    mult = float(token)
                    break
            patches.append(
                MapDeltaPatch(
                    operation_type="scale_class_width",
                    target_layer_id="roads_lines",
                    target_feat_classes=["motorway", "primary"],
                    width_multiplier=mult,
                    rationale=f"响应道路视觉强化指令，将高速与主干道双线符号宽度按比例放大 {mult} 倍。",
                )
            )

        if any(k in text for k in ["隐藏支路", "去掉支路", "只保留主干", "精简道路"]):
            patches.append(
                MapDeltaPatch(
                    operation_type="toggle_visibility",
                    target_layer_id="roads_lines",
                    target_feat_classes=["tertiary"],
                    visible=False,
                    rationale="降低图面线状载负量，隐藏次要城市支路 (`tertiary`)，突出骨干路网。",
                )
            )

        # 3. 检测水系颜色或面状强化修改
        if any(k in text for k in ["长江", "水系", "湖泊", "深蓝"]):
            patches.append(
                MapDeltaPatch(
                    operation_type="style_feature",
                    target_layer_id="water_polygons",
                    target_feature_names=["长 江", "长江", "东 湖", "东湖"],
                    style_updates={"fill_color": "#93C5FD", "stroke_color": "#1D4ED8", "stroke_width": 1.2},
                    rationale="强化面状长江与东湖水体的双岸线对比度，采用深邃蓝描边配清澈蓝填充。",
                )
            )

        # 4. 检测标题修改
        if "标题" in text or "图名" in text:
            patches.append(
                MapDeltaPatch(
                    operation_type="update_title",
                    new_subtitle="经 DeepSeek/GPT 多轮对话增量调优 · 重点政区高亮与骨干路网视觉增强版",
                    rationale="同步更新图幅副标题说明，记录智能体对话修改状态。",
                )
            )

        return patches

    @classmethod
    def apply_patches(
        cls,
        scene_state: MapSceneState,
        patches: List[MapDeltaPatch],
        user_raw_query: str = "",
    ) -> Dict[str, Any]:
        """
        将增量修改算子列表原子化应用于 `MapSceneState`，自动保存 Undo 快照并记录审计日志
        """
        scene_state.save_snapshot()
        applied_descriptions = []

        for p in patches:
            if p.operation_type == "style_feature" and p.target_layer_id in scene_state.layers:
                node = scene_state.layers[p.target_layer_id]
                for fnm in p.target_feature_names:
                    node.feature_style_overrides.setdefault(fnm, {}).update(p.style_updates)
                applied_descriptions.append(p.rationale)

            elif p.operation_type == "scale_class_width" and p.target_layer_id in scene_state.layers:
                node = scene_state.layers[p.target_layer_id]
                for fc in p.target_feat_classes:
                    node.class_scale_multipliers[fc] = float(p.width_multiplier or 1.0)
                applied_descriptions.append(p.rationale)

            elif p.operation_type == "toggle_visibility" and p.target_layer_id in scene_state.layers:
                node = scene_state.layers[p.target_layer_id]
                if p.target_feat_classes:
                    for fc in p.target_feat_classes:
                        if p.visible is False:
                            node.hidden_feat_classes.add(fc)
                        else:
                            node.hidden_feat_classes.discard(fc)
                else:
                    node.visible = bool(p.visible)
                applied_descriptions.append(p.rationale)

            elif p.operation_type == "zoom_scale_and_bbox":
                if p.new_scale_denom:
                    scene_state.task_spec.target_scale_denom = p.new_scale_denom
                if p.new_bbox_wgs84:
                    scene_state.task_spec.bbox_wgs84 = p.new_bbox_wgs84
                applied_descriptions.append(p.rationale)

            elif p.operation_type == "update_title":
                if p.new_title:
                    scene_state.task_spec.title = p.new_title
                if p.new_subtitle:
                    scene_state.task_spec.subtitle = p.new_subtitle
                applied_descriptions.append(p.rationale)

        log_entry = {
            "round": len(scene_state.edit_history_log) + 1,
            "user_query": user_raw_query,
            "patch_count": len(patches),
            "applied_changes": applied_descriptions,
        }
        scene_state.edit_history_log.append(log_entry)
        return log_entry
