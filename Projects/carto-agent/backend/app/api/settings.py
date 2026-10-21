"""设置API路由 - 系统配置与LLM Provider管理

提供查看当前配置（隐藏敏感信息）、更新配置、列出与切换LLM Provider、
查询可用模型列表以及获取地图主题列表等功能。
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_llm_service
from app.core.config import settings
from app.core.constants import MAP_THEMES
from app.core.exceptions import CartoAgentError
from app.models.schemas import (
    UpdateSettingsRequest,
    SwitchProviderRequest,
    UpdateApiKeyRequest,
    ApiResponse,
)
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/settings", tags=["设置"])

# 各Provider可用的模型清单（用于前端选择）
MODEL_CATALOG = {
    "ollama": ["qwen3:8b", "qwen3:4b", "llama3.1:8b", "qwen2.5:7b"],
    "qwen": ["qwen-plus", "qwen-turbo", "qwen-max"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
    "deepseek": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
    "zhipu": ["glm-4", "glm-4-air", "glm-4-flash"],
}

# 各Provider的展示名称
PROVIDER_NAMES = {
    "ollama": "Ollama（本地）",
    "qwen": "通义千问",
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "zhipu": "智谱GLM",
}


def _mask_key(key: str) -> str:
    """对API Key进行脱敏处理，仅保留是否已配置的信息"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/", response_model=ApiResponse, summary="获取当前配置")
async def get_settings():
    """获取当前系统配置（敏感信息如API Key已脱敏）"""
    try:
        config = {
            "llm_provider": settings.llm_provider,
            "ollama": {
                "base_url": settings.ollama_base_url,
                "model": settings.ollama_model,
                "api_key": "",  # 本地服务无需密钥
                "configured": True,  # 本地服务无需API Key，始终视为已配置
            },
            "qwen": {
                "base_url": settings.qwen_base_url,
                "model": settings.qwen_model,
                "api_key": _mask_key(settings.qwen_api_key),
                "configured": bool(settings.qwen_api_key),
            },
            "openai": {
                "base_url": settings.openai_base_url,
                "model": settings.openai_model,
                "api_key": _mask_key(settings.openai_api_key),
                "configured": bool(settings.openai_api_key),
            },
            "deepseek": {
                "base_url": settings.deepseek_base_url,
                "model": settings.deepseek_model,
                "api_key": _mask_key(settings.deepseek_api_key),
                "configured": bool(settings.deepseek_api_key),
            },
            "zhipu": {
                "base_url": settings.zhipu_base_url,
                "model": settings.zhipu_model,
                "api_key": _mask_key(settings.zhipu_api_key),
                "configured": bool(settings.zhipu_api_key),
            },
            "neo4j": {
                "uri": settings.neo4j_uri,
                "username": settings.neo4j_username,
                # 密码脱敏
                "password": "****" if settings.neo4j_password else "",
                "configured": bool(settings.neo4j_password),
            },
            "server": {
                "host": settings.host,
                "port": settings.port,
                "debug": settings.debug,
            },
        }
        return ApiResponse(success=True, data=config)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取配置失败: {e}")


@router.put("/", response_model=ApiResponse, summary="更新配置")
async def update_settings(
    request: UpdateSettingsRequest,
    llm_service: LLMService = Depends(get_llm_service),
):
    """更新系统配置（运行时生效，重启后需写入.env持久化）"""
    try:
        updated = []

        # 更新LLM Provider
        if request.llm_provider is not None:
            settings.llm_provider = request.llm_provider
            llm_service.set_provider(request.llm_provider)
            updated.append("llm_provider")

        # 更新各Provider的模型配置
        if request.ollama_model is not None:
            settings.ollama_model = request.ollama_model
            updated.append("ollama_model")
        if request.qwen_model is not None:
            settings.qwen_model = request.qwen_model
            updated.append("qwen_model")
        if request.openai_model is not None:
            settings.openai_model = request.openai_model
            updated.append("openai_model")
        if request.deepseek_model is not None:
            settings.deepseek_model = request.deepseek_model
            updated.append("deepseek_model")
        if request.zhipu_model is not None:
            settings.zhipu_model = request.zhipu_model
            updated.append("zhipu_model")

        return ApiResponse(
            success=True,
            message="配置更新成功",
            data={"updated_fields": updated},
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新配置失败: {e}")


@router.get("/llm/providers", response_model=ApiResponse, summary="列出所有可用LLM Provider")
async def list_providers(
    llm_service: LLMService = Depends(get_llm_service),
):
    """列出所有支持的LLM Provider及其配置状态

    LLMService.list_providers() 返回格式为：
    [{"name": "ollama", "model": "qwen3:8b", "available": True, "current": True}, ...]
    此处在此基础上补充展示名称与激活状态。
    """
    try:
        # 获取服务支持的Provider列表
        raw_providers = llm_service.list_providers()
        current = llm_service.get_current_provider()
        current_model = llm_service.get_current_model()

        providers = []
        for item in raw_providers:
            # 兼容 dict 与 str 两种返回形式
            if isinstance(item, dict):
                name = item.get("name", "")
                configured = item.get("available", False)
                model = item.get("model")
                models = item.get("models") or ([model] if model else [])
                masked_key = item.get("api_key_masked", "")
            else:
                name = str(item)
                configured = False
                model = None
                models = []
                masked_key = ""
            providers.append({
                "id": name,
                "name": PROVIDER_NAMES.get(name, name),
                "configured": configured,
                "model": model,
                "models": models,
                "masked_key": masked_key,
                "active": name == current,
            })

        return ApiResponse(
            success=True,
            data={
                "current": current,
                "current_model": current_model,
                "providers": providers,
            },
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取Provider列表失败: {e}")


@router.put("/llm/provider", response_model=ApiResponse, summary="切换LLM Provider")
async def switch_provider(
    request: SwitchProviderRequest,
    llm_service: LLMService = Depends(get_llm_service),
):
    """切换当前使用的LLM Provider，可选指定模型"""
    try:
        # set_provider 返回布尔值表示切换是否成功
        ok = llm_service.set_provider(request.provider)
        if not ok:
            return ApiResponse(
                success=False,
                message=f"不支持的LLM Provider: {request.provider}",
            )

        # 同步更新配置中的provider
        settings.llm_provider = request.provider

        # 若指定了模型，更新对应Provider的模型配置
        if request.model is not None:
            model_map = {
                "ollama": "ollama_model",
                "qwen": "qwen_model",
                "openai": "openai_model",
                "deepseek": "deepseek_model",
                "zhipu": "zhipu_model",
            }
            field = model_map.get(request.provider)
            if field is not None:
                setattr(settings, field, request.model)

        return ApiResponse(
            success=True,
            message=f"已切换至 {PROVIDER_NAMES.get(request.provider, request.provider)}",
            data={
                "provider": request.provider,
                "model": request.model,
            },
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"切换Provider失败: {e}")


@router.put("/llm/apikey", response_model=ApiResponse, summary="更新LLM API Key")
async def update_api_key(
    request: UpdateApiKeyRequest,
    llm_service: LLMService = Depends(get_llm_service),
):
    """运行时更新指定LLM提供者的API Key

    更新后立即重新初始化对应Provider使新密钥生效；
    若更新的Provider恰为当前激活Provider，则同步刷新当前实例。
    注意：此为运行时更新，重启后需写入.env持久化。
    """
    try:
        provider = request.provider
        api_key = request.api_key

        # 根据provider更新对应的settings字段
        key_map = {
            "qwen": "qwen_api_key",
            "openai": "openai_api_key",
            "deepseek": "deepseek_api_key",
            "zhipu": "zhipu_api_key",
        }

        if provider not in key_map:
            return ApiResponse(success=False, message=f"不支持的提供者: {provider}")

        # 更新settings
        setattr(settings, key_map[provider], api_key)

        # 重新初始化对应的provider，使新API Key生效
        llm_service._init_provider(provider)

        # 如果当前provider就是切换的provider，重新设置为当前
        if llm_service.current_provider_name == provider:
            llm_service.set_provider(provider)

        return ApiResponse(
            success=True,
            message=f"{provider} API Key 已更新",
            data={"provider": provider, "configured": bool(api_key)},
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新API Key失败: {e}")


@router.get("/llm/models", response_model=ApiResponse, summary="列出当前Provider可用模型")
async def list_models(
    llm_service: LLMService = Depends(get_llm_service),
):
    """列出当前LLM Provider支持的模型列表"""
    try:
        current = llm_service.get_current_provider()
        current_model = llm_service.get_current_model()
        models = MODEL_CATALOG.get(current, [])

        return ApiResponse(
            success=True,
            data={
                "provider": current,
                "current_model": current_model,
                "models": models,
            },
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取模型列表失败: {e}")


@router.get("/map/themes", response_model=ApiResponse, summary="获取可用地图主题列表")
async def get_map_themes():
    """获取所有可用的地图底图主题"""
    try:
        themes = [
            {
                "id": theme_id,
                "name": info["name"],
                "url": info["url"],
                "attribution": info["attribution"],
            }
            for theme_id, info in MAP_THEMES.items()
        ]
        return ApiResponse(success=True, data=themes)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取地图主题失败: {e}")
