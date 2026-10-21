"""知识图谱数据模型"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class KGNode(BaseModel):
    """图谱节点"""
    id: str
    label: str
    name: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class KGEdge(BaseModel):
    """图谱边"""
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class KGGraphData(BaseModel):
    """图谱可视化数据（D3.js格式）"""
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
