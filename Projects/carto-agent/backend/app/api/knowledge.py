"""知识图谱API路由 - 实体/关系管理与图谱可视化

提供知识图谱的实体增删改查、关系创建、图谱可视化数据获取、
自然语言查询、文档导入、初始化以及制图约束与样式推荐查询。
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_kg_service, get_graphrag_service
from app.core.exceptions import CartoAgentError
from app.models.schemas import (
    CreateEntityRequest,
    UpdateEntityRequest,
    CreateRelationRequest,
    KGQueryRequest,
    ImportDocumentRequest,
    ApiResponse,
)
from app.services.kg_service import KGService
from app.services.graphrag_service import GraphRAGService
from pydantic import BaseModel

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


@router.post("/entities", response_model=ApiResponse, summary="创建实体")
async def create_entity(
    request: CreateEntityRequest,
    kg_service: KGService = Depends(get_kg_service),
):
    """在知识图谱中创建一个新实体（节点）"""
    try:
        result = kg_service.create_entity(
            label=request.label,
            properties=request.properties,
        )
        return ApiResponse(success=True, message="实体创建成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"创建实体失败: {e}")


@router.get("/entities/{label}", response_model=ApiResponse, summary="按标签查询实体")
async def get_entities(
    label: str,
    kg_service: KGService = Depends(get_kg_service),
):
    """按标签（label）查询知识图谱中的实体列表"""
    try:
        result = kg_service.get_entities(label=label)
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"查询实体失败: {e}")


@router.put("/entities/{node_id}", response_model=ApiResponse, summary="更新实体")
async def update_entity(
    node_id: str,
    request: UpdateEntityRequest,
    kg_service: KGService = Depends(get_kg_service),
):
    """更新指定实体的属性"""
    try:
        result = kg_service.update_entity(
            node_id=node_id,
            properties=request.properties,
        )
        return ApiResponse(success=True, message="实体更新成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新实体失败: {e}")


@router.delete("/entities/{node_id}", response_model=ApiResponse, summary="删除实体")
async def delete_entity(
    node_id: str,
    kg_service: KGService = Depends(get_kg_service),
):
    """从知识图谱中删除指定实体"""
    try:
        kg_service.delete_entity(node_id=node_id)
        return ApiResponse(success=True, message="实体已删除")
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除实体失败: {e}")


@router.post("/relations", response_model=ApiResponse, summary="创建关系")
async def create_relation(
    request: CreateRelationRequest,
    kg_service: KGService = Depends(get_kg_service),
):
    """在两个实体之间创建关系（边）"""
    try:
        result = kg_service.create_relation(
            source_label=request.source_label,
            source_id=request.source_id,
            target_label=request.target_label,
            target_id=request.target_id,
            relation_type=request.relation_type,
            properties=request.properties,
        )
        return ApiResponse(success=True, message="关系创建成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"创建关系失败: {e}")


@router.get("/graph", response_model=ApiResponse, summary="获取图谱可视化数据")
async def get_graph(
    limit: int = 100,
    kg_service: KGService = Depends(get_kg_service),
):
    """获取知识图谱的可视化数据（D3.js格式的节点与边）"""
    try:
        result = kg_service.get_graph_data(limit=limit)
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取图谱数据失败: {e}")


@router.post("/query", response_model=ApiResponse, summary="自然语言查询")
async def query_kg(
    request: KGQueryRequest,
    kg_service: KGService = Depends(get_kg_service),
):
    """通过自然语言问题查询知识图谱"""
    try:
        result = kg_service.query(question=request.question)
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"知识图谱查询失败: {e}")


@router.post("/import", response_model=ApiResponse, summary="文档导入")
async def import_document(
    request: ImportDocumentRequest,
    kg_service: KGService = Depends(get_kg_service),
):
    """将文档内容导入知识图谱，自动抽取实体与关系"""
    try:
        result = kg_service.import_document(
            content=request.content,
            entity_labels=request.entity_labels,
        )
        return ApiResponse(success=True, message="文档导入成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"文档导入失败: {e}")


@router.post("/init", response_model=ApiResponse, summary="初始化知识图谱数据")
async def init_knowledge(
    kg_service: KGService = Depends(get_kg_service),
):
    """初始化知识图谱的基础数据（城市、地标、地图类型等）"""
    try:
        result = kg_service.init_knowledge()
        return ApiResponse(success=True, message="知识图谱初始化完成", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"知识图谱初始化失败: {e}")


@router.get("/constraints", response_model=ApiResponse, summary="获取制图约束")
async def get_constraints(
    kg_service: KGService = Depends(get_kg_service),
):
    """获取知识图谱中存储的制图约束规则"""
    try:
        result = kg_service.get_constraints()
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取制图约束失败: {e}")


@router.get("/styles/{map_type}", response_model=ApiResponse, summary="获取样式推荐")
async def get_style_recommendations(
    map_type: str,
    kg_service: KGService = Depends(get_kg_service),
):
    """根据地图类型获取知识图谱推荐的图层样式"""
    try:
        result = kg_service.get_style_recommendations(map_type=map_type)
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取样式推荐失败: {e}")


# ========== GraphRAG端点 ==========

class GraphRAGRequest(BaseModel):
    """GraphRAG查询请求"""
    query: str
    depth: int = 2
    top_k: int = 3


@router.post("/graphrag", response_model=ApiResponse, summary="GraphRAG图检索增强查询")
async def graphrag_search(
    request: GraphRAGRequest,
    graphrag_service: GraphRAGService = Depends(get_graphrag_service),
):
    """通过GraphRAG管道进行多跳知识检索

    实现4步GraphRAG管道：
    1. 实体识别 - 从查询中提取制图相关实体
    2. 子图检索 - 从知识图谱获取多跳关联子图
    3. 知识聚合 - 将子图信息结构化为推理上下文
    4. 推理生成 - 构建供LLM推理的上下文文本
    """
    try:
        result = graphrag_service.search(
            query=request.query,
            depth=request.depth,
            top_k=request.top_k,
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"GraphRAG查询失败: {e}")


@router.get("/subgraph/{entity_name}", response_model=ApiResponse, summary="获取实体子图")
async def get_subgraph(
    entity_name: str,
    depth: int = 2,
    limit: int = 50,
    kg_service: KGService = Depends(get_kg_service),
):
    """获取以指定实体为中心的子图（支持多跳检索）

    用于知识图谱可视化中的实体关联展示。
    """
    try:
        result = kg_service.get_subgraph(
            entity_name=entity_name,
            depth=depth,
            limit=limit,
        )
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"子图检索失败: {e}")


@router.get("/ontology", response_model=ApiResponse, summary="获取制图本体概要")
async def get_ontology(
    graphrag_service: GraphRAGService = Depends(get_graphrag_service),
):
    """获取DoMapAI框架5类核心本体概要信息

    返回MapElement、MapSymbol、CartographicData、MapProjection、InfluencingFactor
    五类本体的定义、子类型和属性信息。
    """
    try:
        result = graphrag_service.get_ontology_info()
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取本体信息失败: {e}")
