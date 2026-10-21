"""对话API路由 - 会话管理与消息交互

提供会话的增删改查以及智能体消息交互能力。
用户发送消息后，由 AgentService 编排 LLM、知识图谱、OSM、地图服务完成制图任务。
支持SSE流式响应，实现LLM输出的实时推送。
"""
import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_session_service, get_agent_service, get_llm_service
from app.core.exceptions import CartoAgentError
from app.models.schemas import (
    CreateSessionRequest,
    SendMessageRequest,
    ApiResponse,
)
from app.services.session_service import SessionService
from app.services.agent_service import AgentService
from app.services.llm_service import LLMService
from app.utils.helpers import safe_json_loads, get_timestamp, run_in_thread

router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/sessions", response_model=ApiResponse, summary="创建会话")
async def create_session(
    request: CreateSessionRequest,
    session_service: SessionService = Depends(get_session_service),
):
    """创建一个新的对话会话"""
    try:
        session = session_service.create_session(title=request.title)
        return ApiResponse(success=True, message="会话创建成功", data=session)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"创建会话失败: {e}")


@router.get("/sessions", response_model=ApiResponse, summary="获取会话列表")
async def list_sessions(
    session_service: SessionService = Depends(get_session_service),
):
    """获取所有会话列表"""
    try:
        sessions = session_service.list_sessions()
        return ApiResponse(success=True, data=sessions)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取会话列表失败: {e}")


@router.get("/sessions/{session_id}", response_model=ApiResponse, summary="获取会话详情")
async def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """获取指定会话的完整信息（含历史消息）"""
    try:
        session = session_service.get_session(session_id)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")
        return ApiResponse(success=True, data=session)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取会话详情失败: {e}")


@router.delete("/sessions/{session_id}", response_model=ApiResponse, summary="删除会话")
async def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """删除指定会话及其所有消息"""
    try:
        session_service.delete_session(session_id)
        return ApiResponse(success=True, message="会话已删除")
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除会话失败: {e}")


@router.post("/sessions/{session_id}/messages", response_model=ApiResponse, summary="发送消息")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    session_service: SessionService = Depends(get_session_service),
    agent_service: AgentService = Depends(get_agent_service),
):
    """发送消息并获取智能体响应

    流程：
    1. 先将用户消息保存到会话历史
    2. 调用 AgentService.process_request 编排制图流程
    3. 将智能体响应（含地图数据、步骤、思考过程）保存到会话历史
    4. 返回完整响应结果
    """
    try:
        # 校验会话是否存在
        session = session_service.get_session(session_id)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")

        # 保存用户消息
        session_service.add_message(
            session_id=session_id,
            role="user",
            content=request.message,
        )

        # 调用智能体处理用户请求（在线程池中运行以避免阻塞事件循环）
        result = await run_in_thread(
            agent_service.process_request,
            message=request.message,
            session_id=session_id,
        )

        # 保存助手响应消息（含地图数据、执行步骤、思考过程）
        session_service.add_message(
            session_id=session_id,
            role="assistant",
            content=result.get("response", ""),
            map_data=result.get("map_data"),
            steps=result.get("steps"),
            thinking=result.get("thinking"),
        )

        return ApiResponse(
            success=result.get("success", True),
            message="消息处理完成",
            data={
                "response": result.get("response", ""),
                "map_data": result.get("map_data"),
                "steps": result.get("steps"),
                "thinking": result.get("thinking"),
                "provider": result.get("provider"),
                "model": result.get("model"),
                # 增强数据
                "geotoken_info": result.get("geotoken_info", {}),
                "rag_sources": result.get("rag_sources", []),
                "graphrag_entities": result.get("graphrag_entities", []),
                "knowledge_sources": result.get("knowledge_sources", {}),
            },
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"消息处理失败: {e}")


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse, summary="获取历史消息")
async def get_messages(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """获取指定会话的全部历史消息"""
    try:
        session = session_service.get_session(session_id)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")
        # 兼容 Session 对象与字典两种返回形式
        messages = getattr(session, "messages", None)
        if messages is None and isinstance(session, dict):
            messages = session.get("messages", [])
        return ApiResponse(success=True, data=messages)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取历史消息失败: {e}")


# ========== SSE流式响应端点 ==========

@router.post("/sessions/{session_id}/stream", summary="流式发送消息（SSE）")
async def send_message_stream(
    session_id: str,
    request: SendMessageRequest,
    session_service: SessionService = Depends(get_session_service),
    agent_service: AgentService = Depends(get_agent_service),
    llm_service: LLMService = Depends(get_llm_service),
):
    """流式发送消息 - 通过SSE实时推送LLM生成的文本

    流程：
    1. 先通过AgentService执行完整的制图流程（非流式）
    2. 如果是问答类请求，额外通过LLM流式生成回复
    3. 通过SSE逐步推送文本块给前端

    SSE事件格式：
    - data: {"type": "thinking", "content": "..."}  思考过程
    - data: {"type": "chunk", "content": "..."}     文本块
    - data: {"type": "map", "content": {...}}        地图数据
    - data: {"type": "done", "content": "..."}       完成
    """
    async def event_generator():
        try:
            # 校验会话
            session = session_service.get_session(session_id)
            if session is None:
                yield f"data: {json.dumps({'type': 'error', 'content': '会话不存在'}, ensure_ascii=False)}\n\n"
                return

            # 保存用户消息
            session_service.add_message(
                session_id=session_id,
                role="user",
                content=request.message,
            )

            # 推送思考过程
            yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析您的请求...'}, ensure_ascii=False)}\n\n"

            # 执行智能体处理（在线程池中运行）
            result = await run_in_thread(
                agent_service.process_request,
                message=request.message,
                session_id=session_id,
            )

            # 如果有地图数据，推送地图
            if result.get("map_data"):
                yield f"data: {json.dumps({'type': 'map', 'content': result['map_data']}, ensure_ascii=False)}\n\n"

            # 推送GeoToken信息（制图场景）
            geotoken_info = result.get("geotoken_info", {})
            if geotoken_info:
                yield f"data: {json.dumps({'type': 'geotoken', 'content': geotoken_info}, ensure_ascii=False)}\n\n"

            # 推送RAG知识来源
            rag_sources = result.get("rag_sources", [])
            if rag_sources:
                yield f"data: {json.dumps({'type': 'rag', 'content': rag_sources}, ensure_ascii=False)}\n\n"

            # 推送GraphRAG实体信息
            graphrag_entities = result.get("graphrag_entities", [])
            if graphrag_entities:
                yield f"data: {json.dumps({'type': 'graphrag', 'content': {'entities': graphrag_entities}}, ensure_ascii=False)}\n\n"

            # 推送知识来源（问答场景）
            knowledge_sources = result.get("knowledge_sources", {})
            if knowledge_sources and not result.get("map_data"):
                yield f"data: {json.dumps({'type': 'knowledge_sources', 'content': knowledge_sources}, ensure_ascii=False)}\n\n"

            # 推送执行步骤
            steps = result.get("steps", [])
            if steps:
                yield f"data: {json.dumps({'type': 'steps', 'content': steps}, ensure_ascii=False)}\n\n"

            # 推送思考过程
            thinking = result.get("thinking", "")
            if thinking:
                yield f"data: {json.dumps({'type': 'thinking', 'content': thinking}, ensure_ascii=False)}\n\n"

            # 推送LLM生成的回复（复用process_request已生成的回复，避免二次LLM调用）
            response_text = result.get("response", "")

            if response_text:
                # 直接推送完整回复文本（process_request已完成全部处理，无需分块延迟）
                yield f"data: {json.dumps({'type': 'chunk', 'content': response_text}, ensure_ascii=False)}\n\n"

            # 保存助手响应
            session_service.add_message(
                session_id=session_id,
                role="assistant",
                content=response_text,
                map_data=result.get("map_data"),
                steps=result.get("steps"),
                thinking=result.get("thinking"),
            )

            # 推送完成信号
            yield f"data: {json.dumps({'type': 'done', 'content': '完成', 'provider': result.get('provider'), 'model': result.get('model')}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'处理失败: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
