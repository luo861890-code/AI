"""API请求/响应Schema"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


# ========== 对话相关 ==========
class CreateSessionRequest(BaseModel):
    title: Optional[str] = "新会话"


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: float
    map_data: Optional[Any] = None
    steps: Optional[List[Any]] = None
    thinking: Optional[str] = None


# ========== 地图相关 ==========
class GenerateMapRequest(BaseModel):
    map_type: str = "traffic"
    region: str = "武汉市"
    center: Optional[List[float]] = None
    zoom: Optional[int] = 12
    layers: Optional[List[str]] = None
    style: Optional[str] = None


class AddLayerRequest(BaseModel):
    layer_type: str
    name: str
    query: Optional[str] = None  # OSM查询标签


class UpdateLayerStyleRequest(BaseModel):
    color: Optional[str] = None
    weight: Optional[int] = None
    opacity: Optional[float] = None
    fillOpacity: Optional[float] = None
    dashArray: Optional[str] = None


class SetLayerVisibleRequest(BaseModel):
    """设置图层可见性（QGIS/ArcGIS 图层管理）"""
    visible: bool = True


class UpdateViewRequest(BaseModel):
    center: Optional[List[float]] = None
    zoom: Optional[int] = None


class UpdateThemeRequest(BaseModel):
    theme: str  # standard / positron / dark / satellite


class AddFeatureRequest(BaseModel):
    feature_type: str  # marker / polyline / polygon
    coordinates: Any
    properties: Optional[Dict[str, Any]] = None


class ModifyMapRequest(BaseModel):
    """自然语言修改地图请求"""
    instruction: str


class ExportMapRequest(BaseModel):
    format: str = "geojson"  # geojson / png / svg


class PlanRouteRequest(BaseModel):
    """路径规划请求"""
    start: List[float] = Field(..., description="起点坐标 [lat, lng]")
    end: List[float] = Field(..., description="终点坐标 [lat, lng]")
    profile: str = Field("driving", description="出行方式: driving/walking/cycling")
    waypoints: Optional[List[List[float]]] = Field(None, description="途经点列表 [[lat, lng], ...]")


# ========== 知识图谱相关 ==========
class CreateEntityRequest(BaseModel):
    label: str
    properties: Dict[str, Any]


class UpdateEntityRequest(BaseModel):
    properties: Dict[str, Any]


class CreateRelationRequest(BaseModel):
    source_label: str
    source_id: str
    target_label: str
    target_id: str
    relation_type: str
    properties: Optional[Dict[str, Any]] = None


class KGQueryRequest(BaseModel):
    question: str


class ImportDocumentRequest(BaseModel):
    content: str
    entity_labels: Optional[List[str]] = None


# ========== 设置相关 ==========
class UpdateSettingsRequest(BaseModel):
    llm_provider: Optional[str] = None
    ollama_model: Optional[str] = None
    qwen_model: Optional[str] = None
    openai_model: Optional[str] = None
    deepseek_model: Optional[str] = None
    zhipu_model: Optional[str] = None


class SwitchProviderRequest(BaseModel):
    provider: str
    model: Optional[str] = None


class UpdateApiKeyRequest(BaseModel):
    provider: str  # qwen / openai / deepseek / zhipu
    api_key: str   # API密钥


# ========== 通用响应 ==========
class ApiResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
