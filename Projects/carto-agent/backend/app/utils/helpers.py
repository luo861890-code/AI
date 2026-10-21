"""工具函数"""
import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 全局线程池（避免每次调用创建新线程）
_thread_pool = ThreadPoolExecutor(max_workers=4)


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """在线程池中运行同步函数（Python 3.7兼容，替代asyncio.to_thread）"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_thread_pool, lambda: func(*args, **kwargs))

# 全局日志工厂：各服务模块通过 get_logger(__name__) 获取独立 logger
_logging_configured = False


def get_logger(name: str = "carto-agent") -> logging.Logger:
    """获取指定名称的 logger（自动配置格式和级别，仅首次调用时生效）"""
    global _logging_configured
    logger = logging.getLogger(name)
    if not _logging_configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        _logging_configured = True
    return logger


def generate_id(prefix: str = "id") -> str:
    """生成唯一ID"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def get_timestamp() -> float:
    """获取当前时间戳"""
    return time.time()


def format_datetime(ts: float) -> str:
    """格式化时间戳为可读字符串"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def safe_json_loads(text: str, default: Any = None) -> Any:
    """安全解析JSON"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any) -> str:
    """安全序列化JSON"""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return "{}"


def ensure_dir(path: str) -> str:
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)
    return path


def truncate_text(text: str, max_length: int = 500) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def extract_city(text: str, city_list: Optional[List[str]] = None) -> Optional[str]:
    """从文本中提取城市名"""
    if city_list is None:
        city_list = ["武汉", "北京", "上海", "广州", "深圳", "杭州",
                     "成都", "南京", "重庆", "西安"]
    for city in city_list:
        if city in text:
            # 补全"市"后缀
            return city + "市" if not city.endswith("市") else city
    return None


def extract_map_type(text: str) -> Optional[str]:
    """从文本中提取地图类型"""
    from app.core.constants import MAP_TYPE_MAP
    for zh_type, en_type in MAP_TYPE_MAP.items():
        if zh_type in text:
            return en_type
    return None
