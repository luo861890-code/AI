"""Pydantic Settings配置 - 从.env读取多LLM和环境配置"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv


# 将 backend/.env 注入进程环境变量（供 os.getenv 读取，如 AMAP_KEY / TIANDITU_KEY）
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    """应用配置"""

    # ========== LLM配置 ==========
    llm_provider: str = Field(default="deepseek", description="默认LLM提供者")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # 通义千问
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # DeepSeek：必须通过 backend/.env 的 DEEPSEEK_API_KEY 配置，禁止硬编码密钥到源码
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # 智谱
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # ========== Neo4j ==========
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "neo4j123"

    # ========== 地图数据 ==========
    overpass_servers: str = "https://maps.mail.ru/osm/tools/overpass/api/interpreter,https://overpass-api.de/api/interpreter,https://z.overpass-api.de/api/interpreter,https://lz4.overpass-api.de/api/interpreter"
    amap_api_key: str = ""
    # 多源数据融合适配器（兼容旧键名 AMAP_API_KEY）
    amap_key: str = ""
    tianditu_key: str = ""

    # ========== 服务 ==========
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = True
    data_dir: str = "../data"

    @property
    def overpass_server_list(self) -> List[str]:
        """获取Overpass服务器列表"""
        return [s.strip() for s in self.overpass_servers.split(",") if s.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
