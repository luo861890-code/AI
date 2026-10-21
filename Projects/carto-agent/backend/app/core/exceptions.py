"""自定义异常类"""


class CartoAgentError(Exception):
    """制图智能体基础异常"""
    pass


class LLMError(CartoAgentError):
    """LLM调用异常"""
    pass


class MapGenerationError(CartoAgentError):
    """地图生成异常"""
    pass


class OSMDataError(CartoAgentError):
    """OSM数据获取异常"""
    pass


class KnowledgeGraphError(CartoAgentError):
    """知识图谱异常"""
    pass


class SessionError(CartoAgentError):
    """会话管理异常"""
    pass
