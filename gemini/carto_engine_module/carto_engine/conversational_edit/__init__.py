# -*- coding: utf-8 -*-
"""
[分类九：大模型多轮对话增量修改引擎与场景状态树] `conversational_edit`
支持通过大语言模型对已生成的地图进行多轮对话局部修改（精确寻址图层、要素、范围、色彩、线宽、比例尺）。
"""

from .map_scene_state import MapSceneState, LayerStateNode
from .dialogue_editor import ConversationalMapEditor, MapDeltaPatch

__all__ = ["MapSceneState", "LayerStateNode", "ConversationalMapEditor", "MapDeltaPatch"]
