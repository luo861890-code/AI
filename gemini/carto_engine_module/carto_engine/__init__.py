# -*- coding: utf-8 -*-
"""
================================================================================
Carto-Engine v3.0: 基于地图学理论、知识图谱与大语言模型的独立封装智能制图引擎
适用项目：武汉大学资源与环境科学学院 GIS（地图制图方向）大创项目 `carto-agent`
================================================================================

【十大功能模块分类标注架构】
1. `models_and_specs.py`      —— [分类一：数据模型与制图任务规范]
2. `calibration/`             —— [分类二：空间要素(点/线/面SHP)校准与制图综合]
3. `symbology/`               —— [分类三：地图语言、分级符号与视觉变量库]
4. `layout_and_elements/`     —— [分类四：图层层级管理、注记避让与整饰要素]
5. `renderers/`               —— [分类五：四大核心基础地图专题渲染器]
6. `agent_bridge/`            —— [分类六：Carto-Agent (KG + LLM) 对接与服务适配器]
7. `prompt_and_llm/`          —— [分类七：六段式结构化提示词编译器、DeepSeek/GPT多模型网关与微调训练管线]
8. `data_cleaning/`           —— [分类八：多源数据清洗、质量溯源、精确范围标注与面状水系重构]
9. `conversational_edit/`     —— [分类九：大模型多轮对话增量修改状态机与图层/要素精准寻址]
10. `multiscale_lod/`         —— [分类十：多比例尺动态缩放(LOD)、载负量自适应、行政下钻与真实道路宽度缩放]
"""

from .models_and_specs import (
    MapType,
    AudienceType,
    CoordSystemType,
    CartoTaskSpec,
    VisualVariableSpec,
    LayerDefinition,
)
from .agent_bridge.service_adapter import CartoEngineFacade
from .prompt_and_llm import (
    VibeCartoPromptCompiler,
    StructuredCartoPrompt,
    UnifiedLLMGateway,
    LLMProviderConfig,
    CartoFineTuningPipeline,
)
from .data_cleaning import SpatialDataCleanerAndProvenance, LayerProvenanceReport
from .conversational_edit import MapSceneState, ConversationalMapEditor, MapDeltaPatch
from .multiscale_lod import MultiScaleLODEngine, ScaleLevelSpec

__version__ = "3.0.0"
__all__ = [
    "MapType",
    "AudienceType",
    "CoordSystemType",
    "CartoTaskSpec",
    "VisualVariableSpec",
    "LayerDefinition",
    "CartoEngineFacade",
    "VibeCartoPromptCompiler",
    "StructuredCartoPrompt",
    "UnifiedLLMGateway",
    "LLMProviderConfig",
    "CartoFineTuningPipeline",
    "SpatialDataCleanerAndProvenance",
    "LayerProvenanceReport",
    "MapSceneState",
    "ConversationalMapEditor",
    "MapDeltaPatch",
    "MultiScaleLODEngine",
    "ScaleLevelSpec",
]
