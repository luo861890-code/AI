"""多LLM统一调度服务 - 统一封装5个LLM提供者（Ollama/Qwen/OpenAI/DeepSeek/Zhipu）

通过Provider模式实现统一接口，支持运行时动态切换LLM提供者。
- OllamaProvider: 通过HTTP调用本地Ollama服务
- QwenProvider / OpenAIProvider / DeepSeekProvider / ZhipuProvider: 通过openai库兼容模式调用云端API
支持流式响应生成（streaming），用于SSE实时输出。
"""
import requests
import json
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Generator

from app.core.config import settings


class LLMProvider(ABC):
    """LLM提供者抽象基类 - 定义统一接口"""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）

        Returns:
            生成的文本内容，失败时返回空字符串
        """
        pass

    @abstractmethod
    def chat(self, messages: List[dict]) -> str:
        """对话接口

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]

        Returns:
            助手回复内容，失败时返回空字符串
        """
        pass

    def chat_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        """流式对话接口 - 逐块生成文本

        子类可重写此方法以支持流式输出。
        默认实现回退到非流式chat，一次性返回全部内容。

        Args:
            messages: 消息列表

        Yields:
            文本块（chunk）
        """
        # 默认实现：调用chat一次性返回
        result = self.chat(messages)
        if result:
            yield result

    def is_available(self) -> bool:
        """检查提供者是否可用（子类可重写）"""
        return True


class OllamaProvider(LLMProvider):
    """Ollama本地模型提供者 - 通过HTTP API调用"""

    def __init__(self):
        super().__init__("ollama", settings.ollama_model)
        self.base_url = settings.ollama_base_url
        # 复用 HTTP 连接池，减少反复建连的开销
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
        })

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """调用 /api/generate 接口生成文本"""
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
            }
            response = self._session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            print(f"[OllamaProvider] 生成失败: {e}")
            return ""

    def chat(self, messages: List[dict]) -> str:
        """调用 /api/chat 接口进行对话"""
        try:
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }
            response = self._session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except Exception as e:
            print(f"[OllamaProvider] 对话失败: {e}")
            return ""

    def is_available(self) -> bool:
        """检查Ollama服务是否在线"""
        try:
            response = self._session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI兼容接口提供者基类

    适用于所有支持OpenAI兼容API的提供者（Qwen/OpenAI/DeepSeek/Zhipu）。
    通过openai库的OpenAI客户端调用，只需配置不同的base_url和api_key。
    """

    def __init__(self, name: str, model: str, api_key: str, base_url: str):
        super().__init__(name, model)
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """懒加载OpenAI客户端"""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except Exception as e:
                print(f"[{self.name}] 初始化OpenAI客户端失败: {e}")
                return None
        return self._client

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """通过chat completions接口生成文本"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages)

    def chat(self, messages: List[dict]) -> str:
        """调用 chat completions 接口进行对话"""
        try:
            client = self._get_client()
            if client is None:
                return ""
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[{self.name}] 对话失败: {e}")
            return ""

    def chat_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        """流式调用 chat completions 接口 - 逐块生成文本

        Args:
            messages: 消息列表

        Yields:
            文本内容块
        """
        try:
            client = self._get_client()
            if client is None:
                return
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[{self.name}] 流式对话失败: {e}")
            yield f"[流式输出错误: {e}]"

    def is_available(self) -> bool:
        """检查API Key是否已配置"""
        return bool(self.api_key)


class QwenProvider(OpenAICompatibleProvider):
    """通义千问提供者 - 阿里云DashScope兼容模式"""

    def __init__(self):
        super().__init__(
            name="qwen",
            model=settings.qwen_model,
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI提供者 - GPT系列模型"""

    def __init__(self):
        super().__init__(
            name="openai",
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek提供者 - DeepSeek Chat/Reasoner模型"""

    def __init__(self):
        super().__init__(
            name="deepseek",
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )


class ZhipuProvider(OpenAICompatibleProvider):
    """智谱GLM提供者 - GLM-4系列模型"""

    def __init__(self):
        super().__init__(
            name="zhipu",
            model=settings.zhipu_model,
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
        )


class LLMService:
    """多LLM统一调度服务

    统一管理5个LLM提供者，支持运行时动态切换。
    所有调用均做了异常处理，LLM不可用时返回空字符串。
    """

    # 支持的提供者名称列表
    SUPPORTED_PROVIDERS = ["ollama", "qwen", "openai", "deepseek", "zhipu"]

    # 各 Provider 的常用模型目录（设置面板下拉展示）
    PROVIDER_MODEL_CATALOG = {
        "ollama": ["qwen3:8b", "qwen2.5:7b", "llama3:8b", "mistral:7b", "deepseek-r1:8b"],
        "qwen": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long", "qwen2.5-72b-instruct"],
        "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o3-mini"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "zhipu": ["glm-4-plus", "glm-4", "glm-4-flash", "glm-4-air"],
        "moonshot": ["kimi-latest", "moonshot-v1-8k", "moonshot-v1-32k"],
        "baidu": ["ernie-4.0", "ernie-4.0-turbo", "ernie-3.5"],
    }

    def __init__(self):
        """初始化所有provider并设置默认provider"""
        self.providers: Dict[str, LLMProvider] = {
            "ollama": OllamaProvider(),
            "qwen": QwenProvider(),
            "openai": OpenAIProvider(),
            "deepseek": DeepSeekProvider(),
            "zhipu": ZhipuProvider(),
        }
        self._current_provider: str = settings.llm_provider

        # 如果默认provider不在列表中，回退到ollama
        if self._current_provider not in self.providers:
            print(f"[LLMService] 未知的默认provider: {self._current_provider}，回退到ollama")
            self._current_provider = "ollama"

        print(f"[LLMService] 初始化完成，当前provider: {self._current_provider}, "
              f"模型: {self.get_current_model()}")

    def set_provider(self, provider: str) -> bool:
        """动态切换LLM提供者

        Args:
            provider: 提供者名称（ollama/qwen/openai/deepseek/zhipu）

        Returns:
            切换是否成功
        """
        if provider in self.providers:
            self._current_provider = provider
            print(f"[LLMService] 已切换provider为: {provider}, 模型: {self.get_current_model()}")
            return True
        print(f"[LLMService] 未知的provider: {provider}，支持的: {self.SUPPORTED_PROVIDERS}")
        return False

    @property
    def current_provider_name(self) -> str:
        """返回当前provider名称（属性式访问，与 get_current_provider 等价）"""
        return self._current_provider

    def _init_provider(self, provider_name: str):
        """重新初始化指定的LLM提供者

        在运行时更新API Key后调用，使新配置（api_key / base_url / model）生效。
        """
        provider_map = {
            "ollama": lambda: OllamaProvider(),
            "qwen": lambda: QwenProvider(),
            "openai": lambda: OpenAIProvider(),
            "deepseek": lambda: DeepSeekProvider(),
            "zhipu": lambda: ZhipuProvider(),
        }
        if provider_name in provider_map:
            self.providers[provider_name] = provider_map[provider_name]()
            print(f"[LLMService] 已重新初始化provider: {provider_name}")
        else:
            print(f"[LLMService] 未知的provider: {provider_name}，无法重新初始化")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """统一生成接口 - 路由到当前provider

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本，LLM不可用时返回空字符串
        """
        provider = self.providers.get(self._current_provider)
        if provider is None:
            print(f"[LLMService] 当前provider不存在: {self._current_provider}")
            return ""
        try:
            return provider.generate(prompt, system_prompt)
        except Exception as e:
            print(f"[LLMService] generate调用异常: {e}")
            return ""

    def chat(self, messages: List[dict]) -> str:
        """统一对话接口 - 路由到当前provider

        Args:
            messages: 消息列表 [{"role": "user/system/assistant", "content": "..."}]

        Returns:
            助手回复内容，LLM不可用时返回空字符串
        """
        provider = self.providers.get(self._current_provider)
        if provider is None:
            print(f"[LLMService] 当前provider不存在: {self._current_provider}")
            return ""
        try:
            return provider.chat(messages)
        except Exception as e:
            print(f"[LLMService] chat调用异常: {e}")
            return ""

    def chat_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        """统一流式对话接口 - 路由到当前provider

        Args:
            messages: 消息列表 [{"role": "user/system/assistant", "content": "..."}]

        Yields:
            文本内容块，LLM不可用时yield空字符串
        """
        provider = self.providers.get(self._current_provider)
        if provider is None:
            print(f"[LLMService] 当前provider不存在: {self._current_provider}")
            return
        try:
            yield from provider.chat_stream(messages)
        except Exception as e:
            print(f"[LLMService] chat_stream调用异常: {e}")
            yield f"[流式输出错误: {e}]"

    def list_providers(self) -> List[Dict[str, Any]]:
        """返回各provider的可用状态

        Returns:
            provider信息列表，每项包含 name, model, available, current
        """
        result = []
        for name, provider in self.providers.items():
            api_key = getattr(provider, "api_key", "") or ""
            masked_key = ""
            if api_key:
                masked_key = api_key[:5] + "****" + api_key[-4:]
            result.append({
                "name": name,
                "model": provider.model,
                "models": self.PROVIDER_MODEL_CATALOG.get(name, [provider.model] if provider.model else []),
                "api_key_masked": masked_key,
                "available": provider.is_available(),
                "current": name == self._current_provider,
            })
        return result

    def get_current_provider(self) -> str:
        """返回当前provider名称"""
        return self._current_provider

    def get_current_model(self) -> str:
        """返回当前provider使用的模型名称"""
        provider = self.providers.get(self._current_provider)
        return provider.model if provider else ""
