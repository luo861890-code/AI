"""智能体数据模型"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
import time
import json


class MapRequirement(BaseModel):
    """地图需求模型"""
    map_type: Optional[str] = None       # traffic, tourism, campus, basic, food
    region: Optional[str] = None         # 武汉市
    center: Optional[List[float]] = None # [lat, lng]
    zoom: Optional[int] = 12
    layers: List[str] = Field(default_factory=list)  # highway, railway, poi
    style: Optional[str] = None
    output_format: str = "html"


class AgentStep(BaseModel):
    """智能体执行步骤"""
    step_id: str
    name: str
    description: str
    status: str = "pending"  # pending, running, success, failed
    thinking: Optional[str] = None
    result: Optional[Any] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class AgentResponse(BaseModel):
    """智能体响应"""
    success: bool
    response: str
    map_data: Optional[Any] = None
    steps: List[AgentStep] = Field(default_factory=list)
    thinking: Optional[str] = None
    provider: Optional[str] = None  # 使用的LLM provider
    model: Optional[str] = None     # 使用的模型名


class SessionMessage(BaseModel):
    """会话消息"""
    role: str  # user / assistant
    content: str
    timestamp: float = Field(default_factory=time.time)
    # 地图引用（轻量化存储）：不内嵌完整地图数据，避免 sessions.json 无限膨胀
    map_id: Optional[str] = None
    map_summary: Optional[Dict[str, Any]] = None
    # 兼容旧数据：早期版本直接内嵌完整地图数据，迁移后置为 None
    map_data: Optional[Any] = None
    steps: Optional[List[AgentStep]] = None
    thinking: Optional[str] = None


class Session(BaseModel):
    """会话"""
    session_id: str
    title: str = "新会话"
    messages: List[SessionMessage] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class CartographyTask(BaseModel):
    """制图任务六维模型 - 对标DoMapAI六维任务理解框架

    从用户自然语言中提取结构化的制图任务描述，六个维度全面刻画
    地图制图的时空、语义、受众和方法论特征。
    """
    spatial_scope: str = ""           # 空间范围："武汉市"/"洪山区"/"长江经济带"
    temporal_range: Optional[str] = None  # 时间区间："2020-2025"/"冷战时期"
    topic: str = ""                   # 任务主题："交通"/"人口密度"/"GDP分布"
    audience: str = "public"          # 用户受众：expert/student/public/child/elderly
    cartographic_method: str = "basic"  # 制图方法：choropleth/dot_density/flow/heatmap/symbol_map/graduated_symbol
    symbol_style: str = "geometric"   # 符号风格：geometric/pictorial/abstract/text

    # 受众与制图方法的推荐映射
    AUDIENCE_METHOD_MAP: Dict[str, List[str]] = {
        "expert":   ["choropleth", "graduated_symbol", "dot_density"],
        "student":  ["choropleth", "symbol_map", "flow"],
        "public":   ["symbol_map", "choropleth", "heatmap"],
        "child":    ["symbol_map", "pictorial_map"],
        "elderly":  ["choropleth", "symbol_map"],
    }

    # 制图方法中文名
    METHOD_NAMES: Dict[str, str] = {
        "choropleth": "底色普染图",
        "dot_density": "点密度图",
        "flow": "流向图",
        "heatmap": "热力图",
        "symbol_map": "符号地图",
        "graduated_symbol": "分级符号图",
        "basic": "基础地图",
    }

    # 受众中文名
    AUDIENCE_NAMES: Dict[str, str] = {
        "expert": "专家",
        "student": "学生",
        "public": "公众",
        "child": "儿童",
        "elderly": "老人",
    }

    # 符号风格中文名
    SYMBOL_STYLE_NAMES: Dict[str, str] = {
        "geometric": "几何符号",
        "pictorial": "象形符号",
        "abstract": "抽象符号",
        "text": "文字符号",
    }

    def to_prompt_context(self) -> str:
        """将六维任务转换为LLM prompt上下文

        生成一段结构化的制图任务描述文本，可直接注入到LLM prompt中，
        为地图生成提供明确的任务约束和风格指导。

        Returns:
            格式化的prompt上下文字符串
        """
        parts: List[str] = ["【制图任务六维描述】"]

        if self.spatial_scope:
            parts.append(f"- 空间范围: {self.spatial_scope}")
        if self.temporal_range:
            parts.append(f"- 时间区间: {self.temporal_range}")
        if self.topic:
            parts.append(f"- 任务主题: {self.topic}")
        if self.audience:
            audience_name = self.AUDIENCE_NAMES.get(self.audience, self.audience)
            parts.append(f"- 目标受众: {audience_name}（{self.audience}）")
        if self.cartographic_method:
            method_name = self.METHOD_NAMES.get(self.cartographic_method, self.cartographic_method)
            parts.append(f"- 推荐制图方法: {method_name}（{self.cartographic_method}）")
        if self.symbol_style:
            style_name = self.SYMBOL_STYLE_NAMES.get(self.symbol_style, self.symbol_style)
            parts.append(f"- 符号风格: {style_name}（{self.symbol_style}）")

        # 根据受众给出设计建议
        design_tips = self._get_design_tips()
        if design_tips:
            parts.append(f"- 设计建议: {design_tips}")

        return "\n".join(parts)

    def get_kg_query_params(self) -> Dict[str, str]:
        """从六维任务推导KG（知识图谱）查询参数

        根据六维信息生成知识图谱查询所需的关键参数，
        用于检索制图约束、样式推荐和领域知识。

        Returns:
            KG查询参数字典，包含 topic, method, audience 等键
        """
        params: Dict[str, str] = {}

        if self.topic:
            params["topic"] = self.topic
        if self.cartographic_method and self.cartographic_method != "basic":
            params["method"] = self.cartographic_method
        if self.audience and self.audience != "public":
            params["audience"] = self.audience
        if self.spatial_scope:
            params["spatial_scope"] = self.spatial_scope
        if self.temporal_range:
            params["temporal_range"] = self.temporal_range

        return params

    def to_json(self) -> str:
        """导出为JSON字符串"""
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=2)

    def _get_design_tips(self) -> str:
        """根据受众和主题给出制图设计建议"""
        tips_parts: List[str] = []

        # 受众相关建议
        audience_tips = {
            "expert": "使用精确的分类体系和统计图例，可展示数据置信区间",
            "student": "适当增加标注和图例说明，帮助理解制图原理",
            "public": "配色醒目、图例简洁，突出主要信息避免信息过载",
            "child": "使用鲜艳色彩和象形符号，减少文字标注，增加图例趣味性",
            "elderly": "使用高对比度配色，适当增大字体和图例，避免过度复杂的符号",
        }
        if self.audience in audience_tips:
            tips_parts.append(audience_tips[self.audience])

        # 方法相关建议
        if self.cartographic_method == "heatmap":
            tips_parts.append("热力图建议使用红-黄-蓝渐变，标注密度峰值区域")
        elif self.cartographic_method == "choropleth":
            tips_parts.append("底色普染图建议使用5-7级分级，配色方案应与数据含义一致")

        return "；".join(tips_parts) if tips_parts else ""
