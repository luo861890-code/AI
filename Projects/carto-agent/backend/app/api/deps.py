"""依赖注入模块 - 管理全局单例服务实例

通过模块级变量缓存服务单例，避免重复创建带来的开销，
同时统一各服务之间的依赖关系（如 AgentService 依赖 LLM、知识图谱、OSM、地图服务）。
在测试场景中也可通过替换模块级变量来注入 Mock 实例。
"""
from typing import Optional

from app.services.llm_service import LLMService
from app.services.agent_service import AgentService
from app.services.map_service import MapService
from app.services.kg_service import KGService
from app.services.rag_service import RAGService
from app.services.export_service import ExportService
from app.services.session_service import SessionService
from app.services.osm_service import OSMService
from app.services.routing_service import RoutingService
from app.services.graphrag_service import GraphRAGService
from app.services.geotoken_service import GeoTokenService

# ========== 模块级单例缓存 ==========
_llm_service: Optional[LLMService] = None
_osm_service: Optional[OSMService] = None
_map_service: Optional[MapService] = None
_kg_service: Optional[KGService] = None
_agent_service: Optional[AgentService] = None
_rag_service: Optional[RAGService] = None
_export_service: Optional[ExportService] = None
_session_service: Optional[SessionService] = None
_routing_service: Optional[RoutingService] = None
_graphrag_service: Optional[GraphRAGService] = None
_geotoken_service: Optional[GeoTokenService] = None


def get_osm_service() -> OSMService:
    """获取OSM数据服务单例（负责Overpass API查询）"""
    global _osm_service
    if _osm_service is None:
        _osm_service = OSMService()
    return _osm_service


def get_llm_service() -> LLMService:
    """获取LLM大模型服务单例（支持多Provider切换）"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def get_map_service() -> MapService:
    """获取地图服务单例（地图生成、图层与要素管理）

    MapService 依赖 OSMService 获取真实地理数据，并注入 KGService
    用于查询制图规则（要素清单/符号/配色），实现知识图谱驱动的制图决策。
    """
    global _map_service
    if _map_service is None:
        _map_service = MapService(
            osm_service=get_osm_service(),
            kg_service=get_kg_service(),
        )
    return _map_service


def get_kg_service() -> KGService:
    """获取知识图谱服务单例（Neo4j实体/关系管理）"""
    global _kg_service
    if _kg_service is None:
        # 注入 LLMService：Neo4j 模式下用于"自然语言 -> Cypher"查询生成，
        # 否则 KG 问答永远只能走关键词匹配降级。
        _kg_service = KGService(llm_service=get_llm_service())
    return _kg_service


def get_rag_service() -> RAGService:
    """获取RAG检索服务单例（向量检索增强）"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


def get_export_service() -> ExportService:
    """获取地图导出服务单例（GeoJSON/SVG/PNG导出）"""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service


def get_session_service() -> SessionService:
    """获取会话管理服务单例（会话与消息持久化）"""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


def get_routing_service() -> RoutingService:
    """获取路径规划服务单例（OSRM路径规划）"""
    global _routing_service
    if _routing_service is None:
        _routing_service = RoutingService()
    return _routing_service


def get_graphrag_service() -> GraphRAGService:
    """获取GraphRAG服务单例（图检索增强生成）

    GraphRAGService 依赖 KGService 进行图谱查询，
    依赖 LLMService 进行实体识别和推理生成。
    """
    global _graphrag_service
    if _graphrag_service is None:
        _graphrag_service = GraphRAGService(
            kg_service=get_kg_service(),
            llm_service=get_llm_service(),
        )
    return _graphrag_service


def get_geotoken_service() -> GeoTokenService:
    """获取GeoToken服务单例（地理数据Token化预处理）"""
    global _geotoken_service
    if _geotoken_service is None:
        _geotoken_service = GeoTokenService()
    return _geotoken_service


def get_agent_service() -> AgentService:
    """获取智能体服务单例

    AgentService 是系统核心编排者，需要注入以下依赖：
    - llm_service:       大语言模型服务，负责自然语言理解与生成
    - kg_service:        知识图谱服务，提供制图约束与样式推荐
    - osm_service:       OSM数据服务，负责地理要素查询
    - map_service:       地图服务，负责地图数据生成与管理
    - rag_service:       RAG检索增强服务，提供制图知识库检索
    - session_service:   会话管理服务，提供多轮对话上下文
    - graphrag_service:  GraphRAG服务，提供多跳知识推理
    - geotoken_service:  GeoToken服务，提供地理数据Token化
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(
            llm_service=get_llm_service(),
            kg_service=get_kg_service(),
            osm_service=get_osm_service(),
            map_service=get_map_service(),
            rag_service=get_rag_service(),          # RAG检索增强
            session_service=get_session_service(),   # 多轮上下文管理
            graphrag_service=get_graphrag_service(), # GraphRAG多跳推理
            geotoken_service=get_geotoken_service(), # GeoToken数据预处理
        )
    return _agent_service
