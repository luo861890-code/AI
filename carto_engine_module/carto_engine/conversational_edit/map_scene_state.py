# -*- coding: utf-8 -*-
"""
================================================================================
[分类九 - 子模块 9.1] 可寻址地图场景状态树 `conversational_edit/map_scene_state.py`
================================================================================
为什么需要 `MapSceneState`？
要实现“通过大语言模型对生成的地图进行进一步的对话修改”，地图不能只是一张静态死图片，
而必须是一棵**图层、要素、空间范围、样式参数、数据质量全部精确标注的可寻址状态树（Scene Graph）**！
"""

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import geopandas as gpd

from ..models_and_specs import MapType, CartoTaskSpec, VisualVariableSpec
from ..data_cleaning.cleaner_and_provenance import LayerProvenanceReport


@dataclass
class LayerStateNode:
    """单个图层的精确状态节点（含数据、样式覆盖字典、可见性、溯源卡片）"""
    layer_id: str
    layer_cn_name: str
    z_order: int
    gdf: gpd.GeoDataFrame
    provenance: LayerProvenanceReport
    visible: bool = True
    # 针对特定要素名称或 feature_id 的样式覆盖（例如单独修改“武昌区”填充色或“长江”边框色）
    feature_style_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 针对某类要素 (feat_class) 的线宽/尺寸缩放倍率（例如将高速和主干道加粗 1.4 倍）
    class_scale_multipliers: Dict[str, float] = field(default_factory=dict)
    # 隐藏特定要素名称或分类
    hidden_feature_names: set = field(default_factory=set)
    hidden_feat_classes: set = field(default_factory=set)


class MapSceneState:
    """
    维护整幅地图的图层树、要素精确索引、空间范围、比例尺与多轮对话修改历史栈（支持 Undo / Redo）
    """

    def __init__(self, task_spec: CartoTaskSpec):
        self.task_spec = task_spec
        self.layers: Dict[str, LayerStateNode] = {}
        self.edit_history_log: List[Dict[str, Any]] = []
        self._snapshots: List[Dict[str, Any]] = []

    def register_cleaned_layer(
        self,
        layer_id: str,
        layer_cn_name: str,
        z_order: int,
        gdf: gpd.GeoDataFrame,
        provenance: LayerProvenanceReport,
    ):
        """注册经过清洗与元数据标注的图层"""
        self.layers[layer_id] = LayerStateNode(
            layer_id=layer_id,
            layer_cn_name=layer_cn_name,
            z_order=z_order,
            gdf=gdf,
            provenance=provenance,
        )

    def save_snapshot(self):
        """在执行对话增量修改前保存状态快照，支持一键撤销 (Undo)"""
        state_copy = {
            "title": self.task_spec.title,
            "subtitle": self.task_spec.subtitle,
            "bbox_wgs84": self.task_spec.bbox_wgs84,
            "target_scale_denom": self.task_spec.target_scale_denom,
            "layer_overrides": {
                lid: {
                    "visible": node.visible,
                    "feature_style_overrides": copy.deepcopy(node.feature_style_overrides),
                    "class_scale_multipliers": copy.deepcopy(node.class_scale_multipliers),
                    "hidden_feature_names": set(node.hidden_feature_names),
                    "hidden_feat_classes": set(node.hidden_feat_classes),
                }
                for lid, node in self.layers.items()
            },
        }
        self._snapshots.append(state_copy)

    def undo_last_edit(self) -> bool:
        """回滚上一次大模型对话修改"""
        if not self._snapshots:
            return False
        snap = self._snapshots.pop()
        self.task_spec.title = snap["title"]
        self.task_spec.subtitle = snap["subtitle"]
        self.task_spec.bbox_wgs84 = snap["bbox_wgs84"]
        self.task_spec.target_scale_denom = snap["target_scale_denom"]
        for lid, ldata in snap["layer_overrides"].items():
            if lid in self.layers:
                node = self.layers[lid]
                node.visible = ldata["visible"]
                node.feature_style_overrides = ldata["feature_style_overrides"]
                node.class_scale_multipliers = ldata["class_scale_multipliers"]
                node.hidden_feature_names = ldata["hidden_feature_names"]
                node.hidden_feat_classes = ldata["hidden_feat_classes"]
        return True

    def export_llm_addressable_summary(self) -> Dict[str, Any]:
        """
        导出供大模型（DeepSeek / GPT）精确理解当前图面所有图层、要素名称、空间范围与数据质量的上下文摘要
        """
        layers_overview = {}
        for lid, node in self.layers.items():
            names_sample = [str(n) for n in node.gdf["name"].tolist() if str(n).strip()][:25]
            classes_sample = list(set(node.gdf["feat_class"].astype(str).tolist()))
            layers_overview[lid] = {
                "cn_name": node.layer_cn_name,
                "visible": node.visible,
                "z_order": node.z_order,
                "feature_count": len(node.gdf),
                "feature_names": names_sample,
                "feat_classes": classes_sample,
                "bbox_wgs84": node.provenance.bbox_wgs84,
                "source": node.provenance.source_name,
                "quality_score": node.provenance.quality_score,
            }
        return {
            "title": self.task_spec.title,
            "current_scale_denom": self.task_spec.target_scale_denom,
            "bbox_wgs84": self.task_spec.bbox_wgs84,
            "layers_overview": layers_overview,
            "edit_rounds": len(self.edit_history_log),
        }
