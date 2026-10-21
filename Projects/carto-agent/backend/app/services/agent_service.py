"""制图智能体编排核心 - ReAct流程实现

AgentService是整个系统的核心，采用ReAct（Reasoning + Acting）模式编排制图流程：
1. 需求解析：从自然语言中提取城市、地图类型等关键信息
2. 知识检索：从知识图谱获取制图约束和样式推荐
3. 任务规划：生成执行步骤列表
4. 工具执行：调用OSM服务和地图服务获取数据并生成地图
5. 质量校验：检查坐标范围、图层数量等

同时支持自然语言地图修改指令的解析和执行。

v2.0: 新增 ToolRegistry 标准化工具注册体系和 GraphRAG 深度推理增强，
实现"知识-数据-工具"三元贯通的关键环节。
"""
import json
import re
from typing import List, Dict, Any, Optional

from app.core.constants import CITY_BBOX, MAP_TYPE_MAP
from app.core.exceptions import CartoAgentError
from app.models.agent_models import AgentStep, CartographyTask
from app.services.task_parser import SixDimParser
from app.utils.helpers import (
    generate_id,
    get_timestamp,
    extract_city,
    extract_map_type,
    safe_json_loads,
)
from app.services.cartographic_planner import KGPriorPlanner, ExecutionPlan
from app.services.cartography_validator import CartographyValidator
from app.services.tool_registry import (
    ToolRegistry,
    OSMFetchTool,
    StyleConfigTool,
    MapRenderTool,
    QualityCheckTool,
    ExportTool,
)


class AgentService:
    """制图智能体编排服务

    整合LLM、知识图谱、OSM数据获取和地图生成服务，
    实现从自然语言到地图生成的完整智能化流程。
    """

    # 制图相关关键词
    MAP_KEYWORDS = ["画", "制图", "地图", "生成", "绘制", "做个", "制作", "创建"]
    MODIFY_KEYWORDS = ["修改", "改", "换", "调整", "变", "设置", "更新", "添加", "删除", "移除"]

    # 颜色名称到十六进制的映射
    COLOR_MAP = {
        "红色": "#ff0000", "红": "#ff0000", "red": "#ff0000",
        "蓝色": "#0000ff", "蓝": "#0000ff", "blue": "#0000ff",
        "绿色": "#00ff00", "绿": "#00ff00", "green": "#00ff00",
        "黄色": "#ffff00", "黄": "#ffff00", "yellow": "#ffff00",
        "紫色": "#800080", "紫": "#800080", "purple": "#800080",
        "橙色": "#ffa500", "橙": "#ffa500", "orange": "#ffa500",
        "黑色": "#000000", "黑": "#000000", "black": "#000000",
        "白色": "#ffffff", "白": "#ffffff", "white": "#ffffff",
        "灰色": "#808080", "灰": "#808080", "gray": "#808080", "grey": "#808080",
        "粉色": "#ff69b4", "粉": "#ff69b4", "pink": "#ff69b4",
        "青色": "#00ffff", "青": "#00ffff", "cyan": "#00ffff",
    }

    # 地图类型中文名映射
    MAP_TYPE_NAMES = {
        "traffic": "交通图", "tourism": "旅游图", "campus": "校园图",
        "basic": "基础地图", "food": "美食图", "administrative": "行政区划图",
        "terrain": "地形图（等高线）",
    }

    def __init__(self, llm_service=None, kg_service=None, osm_service=None,
                 map_service=None, rag_service=None, session_service=None,
                 graphrag_service=None, geotoken_service=None):
        """初始化智能体服务

        Args:
            llm_service: LLM统一调度服务实例
            kg_service: 知识图谱服务实例
            osm_service: OSM数据获取服务实例
            map_service: 地图生成与管理服务实例
            rag_service: RAG检索增强服务实例（用于制图知识库检索）
            session_service: 会话管理服务实例（用于多轮对话上下文）
            graphrag_service: GraphRAG服务实例（用于多跳知识推理）
            geotoken_service: GeoToken服务实例（用于地理数据Token化）
        """
        self.llm_service = llm_service
        self.kg_service = kg_service
        self.osm_service = osm_service
        self.map_service = map_service
        self.rag_service = rag_service
        self.session_service = session_service
        self.graphrag_service = graphrag_service
        self.geotoken_service = geotoken_service
        self.task_parser = SixDimParser(llm_service)
        self.planner = KGPriorPlanner(kg_service=self.kg_service, llm_service=self.llm_service)

        # ===== ToolRegistry: "知识-数据-工具"三元体系核心 =====
        self.tool_registry = ToolRegistry()
        self._register_tools()
        # 注意：AgentService 是全局单例，请求级数据（上下文/RAG/GraphRAG结果）
        # 必须作为局部变量在方法间传递，禁止存为实例属性，否则并发请求会互相污染。
        print("[AgentService] 初始化完成")

    def _register_tools(self):
        """注册所有标准化工具到 ToolRegistry

        将"知识-数据-工具"三元体系中的工具层映射到具体服务调用。
        支持运行时动态添加新工具，只需调用 tool_registry.register() 即可。
        """
        # 数据层工具：OSM数据获取
        if self.osm_service:
            self.tool_registry.register(OSMFetchTool(self.osm_service))

        # 渲染层工具：样式配置
        if self.kg_service:
            self.tool_registry.register(StyleConfigTool(self.kg_service))

        # 渲染层工具：地图渲染
        if self.map_service:
            self.tool_registry.register(MapRenderTool(self.map_service))

        # 分析层工具：质量校验
        # CartographyValidator 是无状态工具类，每次创建新实例
        self.tool_registry.register(
            QualityCheckTool(CartographyValidator(), kg_service=self.kg_service)
        )

        # 输出层工具：地图导出（GeoJSON/PNG/SVG）
        try:
            from app.services.export_service import ExportService
            self.tool_registry.register(ExportTool(ExportService()))
        except Exception as e:
            print(f"[AgentService] 导出工具注册失败: {e}")

        print(f"[AgentService] ToolRegistry 初始化完成: "
              f"已注册{self.tool_registry.tool_count}个工具: {self.tool_registry.list_tools()}")

    # ==================== 核心方法：处理用户请求 ====================

    def process_request(self, message: str, session_id: str = None) -> dict:
        """处理用户请求 - 实现ReAct流程

        自动识别请求类型（制图/问答/修改），执行对应流程。
        支持多轮上下文和RAG知识检索增强。

        Args:
            message: 用户自然语言输入
            session_id: 会话ID（可选，用于上下文管理）

        Returns:
            结果字典，包含:
            - success: 是否成功
            - response: 文本回复
            - map_data: 地图数据（制图请求时）
            - steps: 执行步骤列表
            - thinking: 思考过程
            - provider: 使用的LLM提供者
            - model: 使用的模型名
        """
        print(f"[AgentService] 处理请求: {message[:100]}...")

        # 获取当前LLM信息
        provider = self.llm_service.get_current_provider() if self.llm_service else "none"
        model = self.llm_service.get_current_model() if self.llm_service else "none"

        # ===== 快速路径：明显的地图请求直接跳过RAG/GraphRAG/六维解析 =====
        is_map = self._is_map_request(message)
        is_modify = self._is_modify_request(message)

        if is_map and not is_modify:
            # 明显的地图生成请求，直接进入制图流程，跳过RAG和GraphRAG
            print(f"[AgentService] 快速路径：识别为地图生成请求，跳过RAG/GraphRAG")
            return self._handle_map_generation(
                message, provider, model,
                rag_results=[],
                graphrag_context="",
                graphrag_result={"entities": [], "subgraph_count": 0, "aggregated_knowledge": []},
                cartography_task=None,
            )

        if is_modify and not is_map:
            # 明显的地图修改请求，直接进入修改流程
            print(f"[AgentService] 快速路径：识别为地图修改请求，跳过RAG/GraphRAG")
            return self._handle_modify_request(message, provider, model)

        # ===== 构建多轮上下文 =====
        context_messages = self._build_context(session_id)

        # ===== RAG知识检索增强 =====
        rag_results = self._search_rag(message)

        # ===== GraphRAG多跳知识推理 =====
        graphrag_result = self._search_graphrag(message)
        graphrag_context = graphrag_result.get("reasoning_context", "") if graphrag_result else ""

        # ===== LLM意图检测（带关键词降级） =====
        intent = self._detect_intent(message, context_messages)

        # ===== 六维任务理解（DoMapAI框架核心） =====
        cartography_task = None
        if intent in ("map_generation", "map_modification", "question"):
            try:
                cartography_task = self.task_parser.parse(message, context_messages)
                print(f"[AgentService] 六维解析: audience={cartography_task.audience}, "
                      f"topic={cartography_task.topic}, method={cartography_task.cartographic_method}")
            except Exception as e:
                print(f"[AgentService] 六维解析失败（降级）: {e}")
                cartography_task = CartographyTask()

        if intent == "map_generation":
            # 制图请求
            return self._handle_map_generation(
                message, provider, model,
                rag_results=rag_results,
                graphrag_context=graphrag_context,
                graphrag_result=graphrag_result,
                cartography_task=cartography_task,
            )
        elif intent == "map_modification":
            # 地图修改请求
            return self._handle_modify_request(message, provider, model)
        else:
            # 问答请求
            return self._handle_question(
                message, provider, model,
                context_messages=context_messages,
                rag_results=rag_results,
                graphrag_context=graphrag_context,
                graphrag_result=graphrag_result,
            )

    # ==================== 请求级上下文构建（线程安全） ====================

    def _build_context(self, session_id: str = None) -> List[Dict[str, str]]:
        """构建多轮对话上下文（请求级局部状态）"""
        context_messages: List[Dict[str, str]] = []
        if self.session_service and session_id:
            try:
                context_messages = self.session_service.build_llm_context(
                    session_id, max_messages=6
                )
                if context_messages:
                    print(f"[AgentService] 构建上下文: {len(context_messages)}条历史消息")
            except Exception as e:
                print(f"[AgentService] 构建上下文失败: {e}")
        return context_messages

    def _search_rag(self, message: str) -> List[Dict[str, Any]]:
        """RAG知识检索增强（请求级局部状态）"""
        rag_results: List[Dict[str, Any]] = []
        if self.rag_service:
            try:
                rag_results = self.rag_service.search(message, top_k=3)
                if rag_results:
                    print(f"[AgentService] RAG检索到{len(rag_results)}条相关知识")
            except Exception as e:
                print(f"[AgentService] RAG检索失败: {e}")
        return rag_results

    def _search_graphrag(self, message: str) -> Dict[str, Any]:
        """GraphRAG多跳知识推理（请求级局部状态）

        增强了深度推理能力：在标准 GraphRAG 检索基础上，
        额外调用 search_with_depth() 进行更深层的多跳推理，
        将推理链条注入到后续的任务规划 prompt 中。

        Args:
            message: 用户输入

        Returns:
            GraphRAG 推理结果，包含 reasoning_chain, missing_links 等增强字段
        """
        graphrag_result: Dict[str, Any] = {}
        if self.graphrag_service:
            try:
                # 标准 GraphRAG 检索（2跳，快速获取基础上下文）
                graphrag_result = self.graphrag_service.search(message, depth=2, top_k=3)
                context = graphrag_result.get("reasoning_context", "")
                if context:
                    entity_count = len(graphrag_result.get("entities", []))
                    subgraph_count = len(graphrag_result.get("subgraphs", []))
                    print(f"[AgentService] GraphRAG检索: {entity_count}个实体, {subgraph_count}个子图")

                # 增强：深度多跳推理（4跳，逐跳构建推理链）
                deep_result = self.graphrag_service.search_with_depth(
                    message, max_depth=4, branching_factor=5
                )
                if deep_result.get("reasoning_chain"):
                    chain_len = len(deep_result["reasoning_chain"])
                    missing_count = len(deep_result.get("missing_links", []))
                    print(f"[AgentService] GraphRAG深度推理: {chain_len}跳推理链, "
                          f"{missing_count}个缺失环节")
                    # 合并深度推理结果
                    graphrag_result["reasoning_chain"] = deep_result.get("reasoning_chain", [])
                    graphrag_result["accumulated_knowledge"] = deep_result.get("accumulated_knowledge", [])
                    graphrag_result["missing_links"] = deep_result.get("missing_links", [])
                    # 用更丰富的推理上下文覆盖标准上下文
                    deep_context = deep_result.get("reasoning_context", "")
                    if deep_context:
                        graphrag_result["reasoning_context"] = deep_context
            except Exception as e:
                print(f"[AgentService] GraphRAG检索失败: {e}")
        return graphrag_result

    def _detect_intent(self, message: str, context: list) -> str:
        """检测用户意图 - 关键词优先，LLM 仅在模糊时兜底

        先用关键词快速匹配，命中制图或修改关键词时直接返回，省去一次 LLM 调用。
        仅当关键词无法明确判断时，才调用 LLM 进行意图分类。

        Args:
            message: 用户输入
            context: 多轮对话上下文消息列表

        Returns:
            意图类型: "map_generation" / "map_modification" / "question"
        """
        # ===== 1. 关键词快速匹配（零延迟） =====
        is_map = self._is_map_request(message)
        is_modify = self._is_modify_request(message)

        if is_map and not is_modify:
            return "map_generation"
        if is_modify and not is_map:
            return "map_modification"

        # ===== 2. 关键词无法明确判断时，使用 LLM 兜底 =====
        if not self.llm_service:
            # LLM 不可用时，关键词匹配不明确则按问答处理
            return "question"

        # 构建包含上下文的prompt
        context_str = ""
        if context:
            recent = context[-3:]  # 最近3轮对话
            context_str = "\n".join([
                f"{m['role']}: {m['content'][:50]}" for m in recent
            ])

        system_prompt = (
            "你是一个意图分类器。判断用户输入的意图类型：\n"
            "1. map_generation: 生成新地图（包含'画'、'制图'、'生成'、'制作'等词）\n"
            "2. map_modification: 修改已有地图（包含'修改'、'调整'、'换'、'改'等词，"
            "或上下文中已存在地图时用户要求变更）\n"
            "3. question: 知识问答（其他情况）\n"
            "只返回意图类型名称（map_generation/map_modification/question），不要包含其他内容。"
        )

        prompt = f"对话上下文:\n{context_str}\n\n用户输入: {message}\n\n意图类型:"

        try:
            result = self.llm_service.generate(prompt, system_prompt)
            if result:
                result = result.strip().lower()
                if "generation" in result or "map_generation" in result:
                    return "map_generation"
                elif "modification" in result or "map_modification" in result:
                    return "map_modification"
                elif "question" in result:
                    return "question"
        except Exception as e:
            print(f"[AgentService] LLM意图检测失败: {e}")

        # LLM 也无法判断时，按关键词最终结果或默认问答处理
        if is_map:
            return "map_generation"
        elif is_modify:
            return "map_modification"
        return "question"

    def modify_map(self, instruction: str, map_id: str) -> dict:
        """自然语言修改地图

        使用LLM解析修改意图，调用map_service对应方法执行修改。

        Args:
            instruction: 自然语言修改指令（如"把道路颜色改成红色"）
            map_id: 目标地图ID

        Returns:
            结果字典，包含:
            - success: 是否成功
            - response: 文本回复
            - map_data: 更新后的地图数据
            - action: 执行的操作类型
        """
        print(f"[AgentService] 修改地图 {map_id}: {instruction}")

        # 获取地图数据
        map_data = self.map_service.get_map(map_id) if self.map_service else None
        if not map_data:
            return {
                "success": False,
                "response": f"地图不存在: {map_id}",
                "map_data": None,
                "action": "error",
            }

        # 尝试用LLM解析修改意图
        modification = self._parse_modification_with_llm(instruction, map_data)

        # 如果LLM解析失败，使用关键词匹配
        if not modification:
            modification = self._parse_modification_with_keywords(instruction, map_data)

        if not modification:
            return {
                "success": False,
                "response": f"无法理解修改指令: {instruction}",
                "map_data": map_data,
                "action": "unknown",
            }

        # 执行修改
        try:
            action = modification.get("action")
            params = modification.get("params", {})
            reason = modification.get("reason", "")
            _note = f"（AI推理：{reason}）" if reason else ""

            def _resolve_ids():
                """执行时兜底解析目标图层ID（LLM/关键词都未定位时）"""
                ids = params.get("layer_ids") or (
                    [params["layer_id"]] if params.get("layer_id") else []
                )
                if isinstance(ids, str):
                    ids = [ids]
                if not ids:
                    target = str(params.get("target") or "")
                    hint = target or instruction
                    ids = [l["id"] for l in self._find_layers_by_keyword(
                        hint, map_data.get("layers", []))]
                return ids

            if action == "update_style":
                layer_ids = _resolve_ids()
                style = params.get("style", {})
                if not layer_ids:
                    return {"success": False,
                            "response": f"未找到可修改的目标图层（指令：{instruction}）",
                            "map_data": map_data, "action": action}
                updated = map_data
                for layer_id in layer_ids:
                    updated = self.map_service.update_layer_style(map_id, layer_id, style)
                return self._modify_success_response(
                    updated, f"已更新 {len(layer_ids)} 个图层样式: {style}{_note}"
                )

            elif action == "set_visible":
                layer_ids = _resolve_ids()
                visible = bool(params.get("visible", True))
                if not layer_ids:
                    return {"success": False,
                            "response": f"未找到目标图层（指令：{instruction}）",
                            "map_data": map_data, "action": action}
                updated = map_data
                for layer_id in layer_ids:
                    updated = self.map_service.set_layer_visible(map_id, layer_id, visible)
                return self._modify_success_response(
                    updated, f"已{'显示' if visible else '隐藏'} {len(layer_ids)} 个图层{_note}"
                )

            elif action == "rename_layer":
                layer_ids = _resolve_ids()
                name = str(params.get("name") or "")
                if not layer_ids or not name:
                    return {"success": False,
                            "response": f"重命名缺少图层或新名称（指令：{instruction}）",
                            "map_data": map_data, "action": action}
                updated = self.map_service.rename_layer(map_id, layer_ids[0], name)
                return self._modify_success_response(updated, f"已重命名图层为: {name}{_note}")

            elif action == "add_layer":
                layer_type = params.get("layer_type", "polyline")
                name = params.get("name", "新图层")
                query = params.get("query")
                updated = self.map_service.add_layer(map_id, layer_type, name, query)
                return self._modify_success_response(updated, f"已添加图层: {name}")

            elif action == "remove_layer":
                layer_ids = _resolve_ids()
                if not layer_ids:
                    return {"success": False,
                            "response": f"未找到要删除的目标图层（指令：{instruction}）",
                            "map_data": map_data, "action": action}
                updated = map_data
                for layer_id in layer_ids:
                    updated = self.map_service.remove_layer(map_id, layer_id)
                return self._modify_success_response(
                    updated, f"已移除 {len(layer_ids)} 个图层{_note}"
                )

            elif action == "update_view":
                center = params.get("center")
                zoom = params.get("zoom")
                updated = self.map_service.update_view(map_id, center, zoom)
                return self._modify_success_response(updated, "已更新地图视图")

            elif action == "update_theme":
                theme = params.get("theme", "standard")
                updated = self.map_service.update_theme(map_id, theme)
                return self._modify_success_response(updated, f"已切换底图主题: {theme}")

            else:
                return {
                    "success": False,
                    "response": f"不支持的操作类型: {action}",
                    "map_data": map_data,
                    "action": action,
                }

        except Exception as e:
            print(f"[AgentService] 修改地图失败: {e}")
            return {
                "success": False,
                "response": f"修改地图失败: {e}",
                "map_data": map_data,
                "action": "error",
            }

    # ==================== 内部流程：制图请求处理 ====================

    def _handle_map_generation(self, message: str, provider: str, model: str,
                              rag_results=None, graphrag_context="",
                              graphrag_result=None, cartography_task=None) -> dict:
        """处理制图请求 - 完整ReAct流程

        Args:
            message: 用户输入
            provider: LLM提供者名称
            model: 模型名称
            cartography_task: 六维任务理解结果（可选）

        Returns:
            结果字典
        """
        steps: List[AgentStep] = []
        thinking_parts: List[str] = []

        # ===== 六维任务信息注入 =====
        if cartography_task:
            six_dim_context = cartography_task.to_prompt_context()
            print(f"[AgentService] 六维上下文已注入: {six_dim_context[:100]}...")

        # ===== 步骤1：需求解析 =====
        step1 = self._create_step("需求解析", "解析用户输入，提取城市和地图类型")
        steps.append(step1)
        step1.status = "running"
        step1.started_at = get_timestamp()

        city = extract_city(message)
        map_type = extract_map_type(message)

        # 使用六维任务信息辅助地图类型选择
        if cartography_task:
            if cartography_task.spatial_scope and not city:
                city = cartography_task.spatial_scope
            if cartography_task.topic:
                # 将六维主题映射为地图类型
                topic_to_map_type = {
                    "交通": "traffic", "旅游": "tourism",
                    "美食": "food", "行政区划": "administrative",
                    "教育": "campus", "地形": "terrain", "等高线": "terrain",
                }
                mapped = topic_to_map_type.get(cartography_task.topic)
                if mapped and not map_type:
                    map_type = mapped

        # 使用LLM增强解析（如果可用）
        if self.llm_service and (not city or not map_type):
            llm_result = self._llm_parse_requirement(message)
            if llm_result:
                if not city:
                    city = llm_result.get("city")
                if not map_type:
                    map_type = llm_result.get("map_type")

        # 默认值
        if not city:
            city = "武汉市"
        if not map_type:
            map_type = "basic"

        step1.thinking = f"从输入中提取到城市={city}, 地图类型={map_type}"
        # 注入六维任务理解到thinking
        if cartography_task and cartography_task.topic:
            step1.thinking += f"\n六维解析: 主题={cartography_task.topic}, 受众={cartography_task.audience}, 方法={cartography_task.cartographic_method}"
        step1.result = {"city": city, "map_type": map_type}
        step1.status = "success"
        step1.finished_at = get_timestamp()
        thinking_parts.append(f"用户希望制作{city}的{self.MAP_TYPE_NAMES.get(map_type, map_type)}。")
        if cartography_task and cartography_task.topic:
            thinking_parts.append(
                f"六维任务解析: 空间范围={cartography_task.spatial_scope or city}, "
                f"主题={cartography_task.topic}, "
                f"目标受众={cartography_task.AUDIENCE_NAMES.get(cartography_task.audience, cartography_task.audience)}, "
                f"制图方法={cartography_task.METHOD_NAMES.get(cartography_task.cartographic_method, cartography_task.cartographic_method)}。"
            )

        # ===== 步骤2：知识检索 =====
        step2 = self._create_step("知识检索", "从知识图谱获取制图约束和样式推荐")
        steps.append(step2)
        step2.status = "running"
        step2.started_at = get_timestamp()

        constraints = []
        style_recs = []
        if self.kg_service:
            try:
                constraints = self.kg_service.get_constraints()
                # 使用六维任务信息增强KG查询
                if cartography_task:
                    kg_params = cartography_task.get_kg_query_params()
                    if kg_params:
                        style_recs = self.kg_service.get_style_recommendations(
                            map_type, extra_params=kg_params
                        )
                    else:
                        style_recs = self.kg_service.get_style_recommendations(map_type)
                else:
                    style_recs = self.kg_service.get_style_recommendations(map_type)
            except Exception as e:
                print(f"[AgentService] 知识检索失败: {e}")
                if self.kg_service:
                    try:
                        style_recs = self.kg_service.get_style_recommendations(map_type)
                    except Exception:
                        pass

        step2.thinking = f"获取到{len(constraints)}条制图约束, {len(style_recs)}条样式推荐"
        step2.result = {"constraints_count": len(constraints), "style_count": len(style_recs)}
        step2.status = "success"
        step2.finished_at = get_timestamp()
        thinking_parts.append(
            f"知识图谱提供了{len(constraints)}条制图约束和{len(style_recs)}条样式推荐作为参考。"
        )

        # ===== RAG知识增强 =====
        if rag_results:
            rag_context = "\n".join([
                f"[{r.get('title', '')}] {r.get('content', '')}"
                for r in rag_results
            ])
            step2.thinking += f"\nRAG检索到{len(rag_results)}条制图规范知识"
            step2.result["rag_count"] = len(rag_results)
            thinking_parts.append(
                f"RAG提供了{len(rag_results)}条制图规范参考。"
            )

        # ===== GraphRAG多跳知识增强 =====
        if graphrag_context:
            step2.thinking += f"\nGraphRAG推理上下文已构建"
            step2.result["graphrag_enabled"] = True
            thinking_parts.append(
                "GraphRAG提供了多跳关联知识推理，增强了制图决策的上下文理解。"
            )

            # ===== 注入推理链到步骤结果 =====
            reasoning_chain = (graphrag_result or {}).get("reasoning_chain", [])
            missing_links = (graphrag_result or {}).get("missing_links", [])
            if reasoning_chain:
                chain_hops = len(reasoning_chain)
                step2.result["graphrag_reasoning_hops"] = chain_hops
                step2.result["graphrag_missing_links"] = len(missing_links)
                step2.thinking += (
                    f"\nGraphRAG深度推理: {chain_hops}跳推理链, "
                    f"{len(missing_links)}个缺失知识环节"
                )
                thinking_parts.append(
                    f"GraphRAG深度推理发现{chain_hops}跳推理链"
                    + (f"，检测到{len(missing_links)}个知识图谱缺失环节" if missing_links else "")
                    + "。"
                )

        # ===== 步骤2.5：KG决策查询 =====
        step2_5 = self._create_step("KG决策查询", "从知识图谱获取制图决策方案（图层配置、符号方案、配色方案、标注规则）")
        steps.append(step2_5)
        step2_5.status = "running"
        step2_5.started_at = get_timestamp()

        kg_execution_plan = ExecutionPlan()
        kg_plan_context = ""
        try:
            kg_execution_plan = self.planner.plan(
                cartography_task, map_type, city
            )
            kg_plan_context = self.planner.plan_to_prompt_context(kg_execution_plan)
            data_count = len(kg_execution_plan.data_steps)
            style_count = len(kg_execution_plan.style_steps)
            render_count = len(kg_execution_plan.render_steps)
            step2_5.thinking = (
                f"KG决策方案: {data_count}个数据步骤, "
                f"{style_count}个样式配置, {render_count}个渲染步骤"
            )
            if kg_execution_plan.llm_enhanced:
                step2_5.thinking += " (已使用LLM补充)"
            step2_5.result = {
                "data_steps_count": data_count,
                "style_steps_count": style_count,
                "render_steps_count": render_count,
                "llm_enhanced": kg_execution_plan.llm_enhanced,
            }
            step2_5.status = "success"
            thinking_parts.append(
                f"KG决策方案: {data_count}个数据步骤 + {style_count}个样式配置 + {render_count}个渲染步骤"
                + (" (LLM已补充)" if kg_execution_plan.llm_enhanced else "")
            )
        except Exception as e:
            step2_5.thinking = f"KG决策查询失败: {e}"
            step2_5.result = {"error": str(e)}
            step2_5.status = "success"
            print(f"[AgentService] KG决策查询异常: {e}")

        step2_5.finished_at = get_timestamp()

        # ===== 步骤2.6：ToolRegistry工具自动推导 =====
        # 根据KG决策结果，自动匹配需要的工具链
        step2_6 = self._create_step("工具匹配", "根据KG决策方案自动推导需要的工具链并注入推理路径")
        steps.append(step2_6)
        step2_6.status = "running"
        step2_6.started_at = get_timestamp()

        matched_tools = []
        tool_plan_context = ""
        try:
            # 获取KG决策原始数据（用于工具匹配）
            kg_decision_raw = {}
            if self.kg_service and cartography_task:
                try:
                    kg_decision_raw = self.kg_service.query_cartographic_decision(
                        map_type, cartography_task.audience
                    )
                except Exception:
                    pass

            # 自动推导需要的工具
            matched_tools = self.tool_registry.get_tools_for_decision(kg_decision_raw)
            tool_names = [t.definition.name for t in matched_tools]
            tool_descriptions = [
                f"  - {t.definition.name} ({t.definition.category}): {t.definition.description[:60]}..."
                for t in matched_tools
            ]

            # 构建工具规划上下文（注入到任务规划prompt中）
            tool_plan_lines = ["## 可用工具链（由KG决策自动推导）"]
            tool_plan_lines.append(f"匹配到{len(matched_tools)}个工具:")
            tool_plan_lines.extend(tool_descriptions)

            # 将GraphRAG推理路径也注入到工具规划中
            reasoning_chain = (graphrag_result or {}).get("reasoning_chain", [])
            if reasoning_chain:
                tool_plan_lines.append("")
                tool_plan_lines.append("## GraphRAG推理路径（指导工具调用）")
                for entry in reasoning_chain[:3]:
                    hop = entry.get("hop", "?")
                    entities = entry.get("entities", [])[:3]
                    confidence = entry.get("confidence", "none")
                    if entities:
                        tool_plan_lines.append(
                            f"  第{hop}跳(置信度:{confidence}): {', '.join(entities)}"
                        )

            tool_plan_context = "\n".join(tool_plan_lines)

            step2_6.thinking = (
                f"自动匹配到{len(matched_tools)}个工具: {', '.join(tool_names)}"
            )
            step2_6.result = {
                "matched_tools": tool_names,
                "tool_count": len(matched_tools),
            }
            step2_6.status = "success"
            thinking_parts.append(
                f"ToolRegistry自动匹配了{len(matched_tools)}个制图工具: {', '.join(tool_names)}。"
            )
        except Exception as e:
            step2_6.thinking = f"工具匹配失败: {e}"
            step2_6.result = {"error": str(e)}
            step2_6.status = "success"
            print(f"[AgentService] ToolRegistry工具匹配异常: {e}")

        step2_6.finished_at = get_timestamp()

        # ===== 步骤3：任务规划 =====
        step3 = self._create_step("任务规划", "制定数据获取和地图生成计划")
        steps.append(step3)
        step3.status = "running"
        step3.started_at = get_timestamp()

        step3.thinking = f"计划: 1.获取{city}的OSM数据 2.生成{map_type}地图 3.质量校验"
        if kg_plan_context:
            step3.thinking += f"\nKG决策约束:\n{kg_plan_context}"
        if tool_plan_context:
            step3.thinking += f"\n\n{tool_plan_context}"
        step3.result = {
            "plan": "已制定",
            "kg_guided": bool(kg_plan_context),
            "tool_count": len(matched_tools),
        }
        step3.status = "success"
        step3.finished_at = get_timestamp()

        # ===== 步骤4：工具执行 =====
        step4 = self._create_step("地图生成", f"获取OSM数据并生成{city}{self.MAP_TYPE_NAMES.get(map_type, '')}")
        steps.append(step4)
        step4.status = "running"
        step4.started_at = get_timestamp()

        map_data = None
        try:
            map_data = self.map_service.generate_map(
                map_type=map_type,
                region=city,
            )
            # ReAct容错：生成失败/空图层时自动重试一次，仍失败降级为基础图
            if not map_data or not map_data.get("layers"):
                print(f"[AgentService] 地图生成结果为空，重试一次 ({map_type})")
                map_data = self.map_service.generate_map(map_type=map_type, region=city)
            if not map_data or not map_data.get("layers"):
                print(f"[AgentService] 重试仍失败，降级生成基础地图")
                map_data = self.map_service.generate_map(map_type="basic", region=city)
            layer_count = len(map_data.get("layers", []))
            step4.thinking = f"地图生成成功，共{layer_count}个图层"
            step4.result = {"map_id": map_data.get("map_id"), "layer_count": layer_count}
            step4.status = "success"
        except Exception as e:
            step4.thinking = f"地图生成失败: {e}"
            step4.result = str(e)
            step4.status = "failed"
        step4.finished_at = get_timestamp()

        # 如果地图生成失败，提前返回
        if not map_data:
            return {
                "success": False,
                "response": f"地图生成失败，请稍后重试。错误信息: {step4.result}",
                "map_data": None,
                "steps": [s.model_dump() for s in steps],
                "thinking": "\n".join(thinking_parts),
                "provider": provider,
                "model": model,
            }

        thinking_parts.append(f"地图已生成，包含{len(map_data.get('layers', []))}个图层。")

        # ===== GeoToken数据预处理 =====
        geotoken_info: Dict[str, Any] = {}
        if self.geotoken_service:
            try:
                geo_features = self.geotoken_service.extract_geo_features(map_data)
                geotoken_context = self.geotoken_service.build_context_for_llm(map_data, message)
                # 计算总覆盖面积（行政区划图图幅含周边地市且面积量算易失真，不输出数值）
                if map_data.get("map_type") == "administrative":
                    total_area = 0.0
                else:
                    total_area = sum(
                        ls.get("coverage_area_km2", 0)
                        for ls in geo_features.get("layer_summaries", [])
                    )
                geotoken_info = {
                    "layer_count": geo_features.get("total_layers", 0),
                    "total_elements": geo_features.get("total_elements", 0),
                    "total_area_km2": (round(total_area, 2) if total_area else None),
                    "layer_details": geo_features.get("layer_summaries", []),
                    "map_type": geo_features.get("map_type", ""),
                }
                step4.thinking += f"\nGeoToken: {geo_features.get('total_elements', 0)}个要素已Token化"
                thinking_parts.append(
                    f"GeoToken已将{geo_features.get('total_elements', 0)}个地理要素Token化处理。"
                )
            except Exception as e:
                print(f"[AgentService] GeoToken处理失败: {e}")

        # ===== 步骤5：质量校验 =====
        step5 = self._create_step("质量校验", "检查坐标范围、图层数量和制图方案质量")
        steps.append(step5)
        step5.status = "running"
        step5.started_at = get_timestamp()

        # 基础质量校验（坐标范围、空图层）
        quality_issues = self._validate_map_quality(map_data, city)

        # 制图方案质量校验（图层完整性、符号规范性、配色协调性）
        quality_score = 0
        carto_validation = {}
        try:
            validator = CartographyValidator()
            carto_validation = validator.validate(map_data, kg_service=self.kg_service)
            quality_score = carto_validation.get("score", 0)
            carto_issues = carto_validation.get("issues", [])
            failed_checks = carto_validation.get("failed_checks", [])
            # 合并校验问题
            quality_issues.extend(carto_issues)
            if failed_checks:
                quality_issues.extend(failed_checks)

            step5.thinking = (
                f"制图质量评分: {quality_score}/100, "
                f"通过检查项: {len(carto_validation.get('passed_checks', []))}, "
                f"失败检查项: {len(failed_checks)}"
            )
        except Exception as e:
            print(f"[AgentService] 制图方案校验失败: {e}")
            carto_validation = {"error": str(e)}
            quality_score = -1
            step5.thinking = f"制图方案校验异常: {e}"

        if quality_issues:
            step5.thinking += f"\n质量问题: {quality_issues}"
            step5.result = {"issues": quality_issues, "quality_score": quality_score}
            step5.status = "success"  # 有问题但不算失败
        else:
            step5.thinking += "\n质量校验通过"
            step5.result = {"issues": [], "quality_score": quality_score}
            step5.status = "success"
        step5.finished_at = get_timestamp()

        # ===== 生成回复文本 =====
        response = self._generate_response_text(map_data, city, map_type, quality_issues)

        thinking_parts.append(
            f"质量校验{'发现'+str(len(quality_issues))+'个问题' if quality_issues else '通过'}。"
        )

        return {
            "success": True,
            "response": response,
            "map_data": map_data,
            "steps": [s.model_dump() for s in steps],
            "thinking": "\n".join(thinking_parts),
            "provider": provider,
            "model": model,
            # ===== 增强数据暴露 =====
            "geotoken_info": geotoken_info,
            "rag_sources": [
                {"title": r.get("title", ""), "score": round(r.get("score", 0), 3)}
                for r in (rag_results or [])
            ],
            "graphrag_entities": (graphrag_result or {}).get("entities", []),
            # ===== Sprint 3: 制图质量评分 =====
            "quality_score": quality_score,
            # ===== 三元贯通: GraphRAG推理链 + ToolRegistry =====
            "graphrag_reasoning_chain": (graphrag_result or {}).get("reasoning_chain", []),
            "graphrag_missing_links": (graphrag_result or {}).get("missing_links", []),
            "tool_registry": {
                "matched_tools": [t.definition.name for t in matched_tools],
                "tool_count": len(matched_tools),
            },
        }

    # ==================== 内部流程：问答请求处理 ====================

    def _handle_question(self, message: str, provider: str, model: str,
                        context_messages=None, rag_results=None,
                        graphrag_context="", graphrag_result=None) -> dict:
        """处理问答请求

        Args:
            message: 用户输入
            provider: LLM提供者名称
            model: 模型名称

        Returns:
            结果字典
        """
        steps: List[AgentStep] = []
        thinking_parts: List[str] = []

        step1 = self._create_step("意图识别", "判断用户意图为知识问答")
        step1.status = "success"
        step1.started_at = get_timestamp()
        step1.finished_at = get_timestamp()
        step1.thinking = "用户输入不包含制图关键词，判断为问答请求"
        steps.append(step1)
        thinking_parts.append("用户的问题不涉及制图，作为知识问答处理。")

        # ===== 闲聊快速回复（零延迟） =====
        chat_response = self._try_chat_reply(message)
        if chat_response:
            step2 = self._create_step("闲聊回复", "识别为日常问候，直接回复")
            step2.status = "success"
            step2.started_at = get_timestamp()
            step2.finished_at = get_timestamp()
            step2.thinking = "检测到日常问候语，快速回复"
            steps.append(step2)
            thinking_parts.append("检测到日常问候，直接友好回复。")

            return {
                "success": True,
                "response": chat_response,
                "map_data": None,
                "steps": [s.model_dump() for s in steps],
                "thinking": "\n".join(thinking_parts),
                "provider": provider,
                "model": model,
                "knowledge_sources": {
                    "rag": [],
                    "graphrag": {"entities": [], "subgraph_count": 0, "aggregated_knowledge": []},
                    "kg_answer": "",
                },
            }

        # 优先使用知识图谱查询
        step2 = self._create_step("知识查询", "从知识图谱检索相关信息")
        step2.status = "running"
        step2.started_at = get_timestamp()
        steps.append(step2)

        kg_answer = ""
        if self.kg_service:
            try:
                kg_answer = self.kg_service.query(message)
            except Exception as e:
                print(f"[AgentService] 知识图谱查询失败: {e}")

        step2.thinking = f"知识图谱返回: {kg_answer[:100] if kg_answer else '无结果'}..."
        step2.result = {"kg_answer": kg_answer[:200] if kg_answer else ""}
        step2.status = "success"
        step2.finished_at = get_timestamp()

        # 使用LLM生成最终回复
        step3 = self._create_step("生成回复", "结合知识图谱和RAG信息生成自然语言回复")
        step3.status = "running"
        step3.started_at = get_timestamp()
        steps.append(step3)

        response = ""
        if self.llm_service:
            system_prompt = (
                "你是一个专业的地图制图智能体助手。请根据用户问题、知识图谱检索结果和RAG参考知识，"
                "给出准确、简洁的回答。如果知识图谱或RAG有相关信息，请优先参考。"
                "请结合对话上下文理解用户的真实意图。"
                "如果提供了GraphRAG知识上下文，请参考其中的多跳关联知识来增强回答。"
            )

            # 构建RAG上下文
            rag_context = ""
            if rag_results:
                rag_context = "\n\n参考知识:\n" + "\n".join([
                    f"- {r.get('content', '')}" for r in rag_results
                ])

            # 构建GraphRAG上下文
            graphrag_ctx = ""
            if graphrag_context:
                graphrag_ctx = f"\n\n{graphrag_context}"

            # 如果有多轮上下文，使用chat接口
            if context_messages:
                messages = [{"role": "system", "content": system_prompt}]
                # 添加历史上下文（最近4条）
                messages.extend(context_messages[-4:])
                # 添加当前问题（含知识检索结果）
                messages.append({
                    "role": "user",
                    "content": f"用户问题: {message}\n\n知识图谱检索结果: {kg_answer}{rag_context}{graphrag_ctx}"
                })
                response = self.llm_service.chat(messages)
            else:
                # 无上下文时使用generate接口
                prompt = f"用户问题: {message}\n\n知识图谱检索结果: {kg_answer}{rag_context}{graphrag_ctx}\n\n请回答用户问题："
                response = self.llm_service.generate(prompt, system_prompt)

        if not response:
            # LLM不可用时，直接返回知识图谱结果
            response = kg_answer if kg_answer else "抱歉，我暂时无法回答这个问题。请尝试询问关于地图制图、城市地标等方面的问题。"

        step3.thinking = "已生成回复"
        step3.result = {"response_length": len(response)}
        step3.status = "success"
        step3.finished_at = get_timestamp()
        thinking_parts.append("已结合知识图谱和LLM生成回复。")

        return {
            "success": True,
            "response": response,
            "map_data": None,
            "steps": [s.model_dump() for s in steps],
            "thinking": "\n".join(thinking_parts),
            "provider": provider,
            "model": model,
            # ===== 知识来源暴露 =====
            "knowledge_sources": {
                "rag": [
                    {"title": r.get("title", ""), "content": r.get("content", "")[:200], "score": round(r.get("score", 0), 3)}
                    for r in (rag_results or [])
                ],
                "graphrag": {
                    "entities": (graphrag_result or {}).get("entities", []),
                    "subgraph_count": len((graphrag_result or {}).get("subgraphs", [])),
                    "aggregated_knowledge": (graphrag_result or {}).get("aggregated_knowledge", [])[:3],
                },
                "kg_answer": kg_answer[:500] if kg_answer else "",
            },
        }

    # ==================== 闲聊快速回复 ====================

    def _try_chat_reply(self, message: str) -> Optional[str]:
        """尝试快速回复闲聊/问候语，无需调用LLM和知识图谱

        Args:
            message: 用户输入

        Returns:
            快速回复内容，如果不是闲聊则返回None
        """
        msg = message.strip().lower()

        # 问候语
        greetings = {
            "你好": "你好！我是地图制图智能体，很高兴为你服务。我可以帮你生成各种类型的地图，回答地图制图相关的问题。有什么我可以帮你的吗？",
            "您好": "您好！我是地图制图智能体，很高兴为您服务。我可以帮您生成各种类型的地图，回答地图制图相关的问题。有什么我可以帮您的吗？",
            "hi": "Hi! 我是地图制图智能体，很高兴为你服务。有什么我可以帮你的吗？",
            "hello": "Hello! 我是地图制图智能体，很高兴为你服务。有什么我可以帮你的吗？",
            "嗨": "嗨！我是地图制图智能体，很高兴为你服务。有什么我可以帮你的吗？",
            "哈喽": "哈喽！我是地图制图智能体，很高兴为你服务。有什么我可以帮你的吗？",
            "在吗": "在的！我是地图制图智能体，随时为你服务。有什么我可以帮你的吗？",
            "在不在": "在的！我是地图制图智能体，随时为你服务。有什么我可以帮你的吗？",
            "有人吗": "有的！我是地图制图智能体，很高兴为你服务。有什么我可以帮你的吗？",
            "你是谁": "我是地图制图智能体（CartoAgent），一个集成了大语言模型与知识图谱的在线地图制图助手。我可以帮你生成各种类型的地图，回答地图制图相关的问题。",
            "你叫什么名字": "我叫CartoAgent，是一个地图制图智能体。我可以帮你生成各种类型的地图，回答地图制图相关的问题。",
            "你能做什么": "我可以帮你做以下事情：\n1. 生成各种类型的地图（交通图、旅游图、校园图、医疗资源图等）\n2. 修改地图样式（颜色、线宽、透明度等）\n3. 回答地图制图相关的知识问题\n4. 提供制图规范和样式建议\n\n你可以直接告诉我你想要什么样的地图，我来帮你生成！",
            "你会什么": "我会生成各种类型的地图，回答地图制图相关的问题。比如你可以说\"生成一份武汉交通图\"，我就会帮你生成武汉市的交通地图。",
            "谢谢": "不客气！很高兴能帮到你。如果还有其他地图相关的需求，随时告诉我哦！",
            "感谢": "不用谢！很高兴能帮到你。如果还有其他地图相关的需求，随时告诉我哦！",
            "好的": "好的！如果还有其他地图相关的需求，随时告诉我哦！",
            "嗯": "嗯，如果还有其他地图相关的需求，随时告诉我哦！",
            "再见": "再见！如果以后需要生成地图，随时来找我哦！",
            "拜拜": "拜拜！如果以后需要生成地图，随时来找我哦！",
            "早安": "早安！新的一天，让我来帮你生成地图吧！有什么我可以帮你的吗？",
            "早上好": "早上好！新的一天，让我来帮你生成地图吧！有什么我可以帮你的吗？",
            "晚安": "晚安！好好休息，明天需要生成地图的话随时来找我哦！",
            "晚上好": "晚上好！有什么地图相关的需求我可以帮你的吗？",
            "下午好": "下午好！有什么地图相关的需求我可以帮你的吗？",
        }

        # 精确匹配
        if msg in greetings:
            return greetings[msg]

        # 模糊匹配（包含关键词）
        for keyword, reply in greetings.items():
            if keyword in msg and len(msg) <= len(keyword) + 5:
                return reply

        # 简单的感谢+语气词
        if any(w in msg for w in ["谢谢", "感谢", "多谢"]) and len(msg) <= 10:
            return "不客气！很高兴能帮到你。如果还有其他地图相关的需求，随时告诉我哦！"

        # ===== 常见知识问题快速回复 =====
        knowledge_faq = {
            "什么是专题地图": "专题地图是突出表示一种或几种自然或社会经济现象的地图，它与普通地图的区别在于内容的专门化。常见的专题地图类型包括：\n1. 自然地图：地形图、气候图、水文图、土壤图、植被图等\n2. 社会经济地图：人口图、经济图、交通图、政区图等\n3. 环境地图：环境污染图、环境质量评价图等\n\n专题地图的特点是主题明确、内容专一、形式多样。",
            "专题地图": "专题地图是突出表示一种或几种自然或社会经济现象的地图，与普通地图的区别在于内容的专门化。常见类型包括自然地图、社会经济地图、环境地图等。",
            "地图制图有哪些基本原则": "地图制图的基本原则包括：\n1. **科学性原则**：地图内容必须真实、准确，符合客观实际\n2. **实用性原则**：满足用户的实际需求，用途明确\n3. **艺术性原则**：地图视觉效果美观，色彩协调\n4. **清晰性原则**：图面清晰易读，层次分明\n5. **完整性原则**：地图要素齐全，信息完整\n6. **一致性原则**：同一幅地图内的符号、色彩、注记等保持一致",
            "制图基本原则": "地图制图的基本原则：科学性、实用性、艺术性、清晰性、完整性、一致性。",
            "什么是比例尺": "比例尺是地图上某一线段的长度与地面上相应线段水平距离之比。常见的比例尺表示方式有：\n1. **数字比例尺**：如1:10000、1:50000\n2. **文字比例尺**：如\"图上1厘米代表实地500米\"\n3. **图解比例尺**：用线段图形表示\n\n比例尺越大，地图表示的内容越详细；比例尺越小，地图表示的范围越大。",
            "比例尺": "比例尺是地图上某一线段的长度与地面上相应线段水平距离之比。常见表示方式有数字比例尺、文字比例尺和图解比例尺。",
            "什么是图例": "图例是地图上表示各种地理事物的符号及其说明的集合。它是地图的重要组成部分，帮助读者理解地图上的符号、颜色、线条等所代表的含义。\n\n图例通常包括：\n1. 符号和对应的说明文字\n2. 颜色和对应的含义\n3. 线型和对应的地理要素",
            "图例": "图例是地图上表示各种地理事物的符号及其说明的集合，帮助读者理解地图内容。",
            "什么是等高线": "等高线是地图上高程相等的各相邻点所连成的闭合曲线。它是表示地形起伏的重要方法。\n\n等高线的特点：\n1. 同一条等高线上的各点高程相等\n2. 等高线是闭合曲线\n3. 等高线的疏密反映坡度的陡缓（密陡疏缓）\n4. 等高线一般不相交、不重合（悬崖除外）",
            "等高线": "等高线是地图上高程相等的各相邻点所连成的闭合曲线，用于表示地形起伏。等高线越密，坡度越陡；等高线越疏，坡度越缓。",
            "你能生成什么地图": "我可以生成各种类型的地图，包括：\n\n**基础地图类：**\n- 交通图（道路、轨道交通）\n- 旅游图（景点、名胜古迹）\n- 校园分布图\n- 医疗资源图（医院、诊所）\n- 教育设施图（学校分布）\n- 商业热力图\n- 人口密度图\n- 土地利用图\n- 绿化覆盖图\n\n**专题地图类：**\n- 自然地理专题图\n- 社会经济专题图\n- 环境专题图\n\n你可以直接告诉我你想要什么样的地图，比如\"生成一份武汉交通图\"，我就会帮你生成！",
            "能生成什么地图": "我可以生成交通图、旅游图、校园图、医疗资源图、教育设施图、商业热力图、人口密度图、土地利用图、绿化覆盖图等各种类型的地图。",
            "怎么生成地图": "生成地图很简单！你只需要用自然语言告诉我你想要什么样的地图，我就会帮你生成。\n\n比如你可以说：\n- \"生成一份武汉市交通图\"\n- \"做一个武汉旅游景点分布图\"\n- \"帮我画一张医疗资源分布图\"\n\n我会自动理解你的需求，规划制图任务，然后生成对应的地图。",
            "如何使用": "使用方法很简单：直接在对话框中用自然语言描述你想要的地图，我会自动理解你的需求并生成地图。你也可以点击快捷指令快速开始。",
        }

        # 常见知识问题快速回复
        for question, answer in knowledge_faq.items():
            if question in msg and len(msg) <= len(question) + 10:
                return answer

        return None

    # ==================== 内部流程：修改请求处理 ====================

    def _handle_modify_request(self, message: str, provider: str, model: str) -> dict:
        """处理修改请求（当未提供map_id时的入口）

        Args:
            message: 用户输入
            provider: LLM提供者名称
            model: 模型名称

        Returns:
            结果字典
        """
        # 尝试找到最近创建的地图
        maps = self.map_service.list_maps() if self.map_service else []
        if not maps:
            return {
                "success": False,
                "response": "当前没有可修改的地图，请先生成一张地图。",
                "map_data": None,
                "steps": [],
                "thinking": "用户请求修改地图，但没有已存在的地图。",
                "provider": provider,
                "model": model,
            }

        # 取最近一张地图
        # dict 保持插入顺序，最后一张才是最近创建的地图
        latest_map = maps[-1]
        map_id = latest_map["map_id"]

        # 调用modify_map执行修改
        result = self.modify_map(message, map_id)
        result["provider"] = provider
        result["model"] = model
        result["steps"] = []
        result["thinking"] = f"对地图「{latest_map['name']}」执行修改: {message}"
        return result

    # ==================== 修改意图解析 ====================

    def _parse_modification_with_llm(self, instruction: str, map_data: dict) -> Optional[dict]:
        """使用LLM解析修改意图

        让大模型理解自然语言、推理目标图层并输出结构化修改操作；
        兼容 action/operation 字段，解析后用关键词补齐图层ID，
        并把推理过程（reason）带回给前端展示。

        Args:
            instruction: 自然语言修改指令
            map_data: 当前地图数据

        Returns:
            修改操作字典 {action, params}，解析失败返回None
        """
        if not self.llm_service:
            return None

        # 构建紧凑图层目录（QGIS 式：名称/类型/颜色/线宽/填充/虚线）
        layers_info = []
        for layer in map_data.get("layers", []):
            st = layer.get("style", {}) or {}
            layers_info.append({
                "id": layer["id"],
                "name": layer.get("name", ""),
                "type": layer.get("type", ""),
                "color": st.get("color", ""),
                "fillColor": st.get("fillColor", ""),
                "weight": st.get("weight", ""),
                "opacity": st.get("opacity", ""),
                "dashArray": st.get("dashArray", ""),
            })

        system_prompt = (
            "你是一个专业的地图制图助手（类似QGIS/ArcGIS的智能图层管理器）。"
            "根据用户的自然语言修改指令，推理出要修改的图层和具体参数，"
            "输出JSON格式的修改操作。支持的操作类型：\n"
            "1. update_style: 修改图层样式，params包含 target(目标图层类别词，如\"道路\"/\"湖泊\"/\"水系\")、style(color/weight/opacity/fillOpacity/dashArray，颜色用十六进制)\n"
            "2. set_visible: 显示/隐藏图层，params包含 target 和 visible(true/false)\n"
            "3. rename_layer: 重命名图层，params包含 target 和 name\n"
            "4. remove_layer: 删除图层，params包含 target\n"
            "5. add_layer: 添加图层，params包含layer_type(polyline/marker/polygon)、name、query(OSM标签)\n"
            "6. update_view: 修改视图，params包含center([lat,lng])和zoom\n"
            "7. update_theme: 修改底图主题，params包含theme(standard/positron/dark/satellite)\n\n"
            "规则：\n"
            "- 只返回JSON，不要包含markdown代码块或任何其他文字。\n"
            "- 顶层字段：{\"action\": \"...\", \"params\": {...}, \"reason\": \"用中文一句话说明你的修改推理\"}。\n"
            "- 涉及图层的操作，target 写图层类别词（优先用图层名称中的中文关键词）；"
            "如果无法确定 target，给出最合理的推测。"
        )

        prompt = (
            f"当前地图图层目录（id/名称/类型/颜色/线宽/填充/虚线）:\n"
            f"{json.dumps(layers_info, ensure_ascii=False)}\n\n"
            f"用户修改指令: {instruction}\n\n"
            f"请推理并输出修改操作JSON: "
        )

        result = self.llm_service.generate(prompt, system_prompt)
        if not result:
            return None

        modification = self._extract_llm_json(result)
        if not modification:
            return None

        # 兼容 operation/action 两种字段
        action = modification.get("action") or modification.get("operation")
        params = modification.get("params") or {}
        reason = modification.get("reason", "")
        if not action or not isinstance(params, dict):
            return None
        action = str(action).strip()

        # 需要图层定位的操作：用 target（或指令文本）补齐图层ID
        if action in ("update_style", "set_visible", "rename_layer", "remove_layer"):
            layer_ids = params.get("layer_ids") or []
            if isinstance(layer_ids, str):
                layer_ids = [layer_ids]
            if not layer_ids:
                target = str(params.get("target") or "")
                hint = target or instruction
                matched = self._find_layers_by_keyword(hint, map_data.get("layers", []))
                layer_ids = [l["id"] for l in matched]
                if not matched and target:
                    # target 是具体图层名时按名称包含匹配
                    layer_ids = [l["id"] for l in map_data.get("layers", [])
                                 if target in l.get("name", "")]
            params["layer_ids"] = layer_ids

        return {"action": action, "params": params, "reason": reason}

    @staticmethod
    def _extract_llm_json(text: str) -> Optional[dict]:
        """从LLM输出中稳健提取JSON对象（兼容代码块/前后缀文字）。"""
        if not text:
            return None
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        parsed = safe_json_loads(text, None)
        if isinstance(parsed, dict):
            return parsed
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    parsed = safe_json_loads(text[start:i + 1], None)
                    return parsed if isinstance(parsed, dict) else None
        return None

    def _parse_modification_with_keywords(self, instruction: str, map_data: dict) -> Optional[dict]:
        """使用关键词匹配解析修改意图（LLM不可用时的降级方案）

        Args:
            instruction: 自然语言修改指令
            map_data: 当前地图数据

        Returns:
            修改操作字典，无法匹配返回None
        """
        layers = map_data.get("layers", [])
        instruction_lower = instruction.lower()

        # ===== 样式修改 =====
        _style_kws = ["颜色", "color", "配色", "线宽", "weight", "透明", "opacity",
                      "虚线", "加粗", "变粗", "加宽", "变宽", "变细", "改粗", "改细",
                      "改成", "改为", "变为", "调成", "换成", "设成"]
        _has_color_name = any(cn in instruction for cn in self.COLOR_MAP)
        if any(kw in instruction for kw in _style_kws) or _has_color_name:
            # 匹配目标图层
            target_layers = self._find_layers_by_keyword(instruction, layers)
            if not target_layers:
                # 默认修改第一个图层
                target_layers = layers[:1] if layers else []

            if target_layers:
                style = {}
                # 解析颜色
                color = self._extract_color(instruction)
                if color:
                    style["color"] = color
                    if any(l.get("type") == "polygon" for l in target_layers):
                        style["fillColor"] = color
                # 解析线宽
                weight_match = re.search(r"线宽|粗细|weight|宽度", instruction)
                if weight_match and re.search(r"(\d+)", instruction):
                    num_match = re.search(r"(\d+)", instruction)
                    style["weight"] = int(num_match.group(1))
                elif any(kw in instruction for kw in ["加粗", "变粗", "加宽", "变宽", "改粗"]):
                    # 无数字的"加粗"：在当前线宽基础上 +1（保持渐进调整）
                    cur = (target_layers[0].get("style") or {}).get("weight") or 3
                    style["weight"] = int(cur) + 1
                elif any(kw in instruction for kw in ["变细", "改细", "减细"]):
                    cur = (target_layers[0].get("style") or {}).get("weight") or 3
                    style["weight"] = max(1, int(cur) - 1)
                # 解析透明度
                if "透明" in instruction or "opacity" in instruction_lower:
                    num_match = re.search(r"(\d+(?:\.\d+)?)", instruction)
                    if num_match:
                        val = float(num_match.group(1))
                        style["opacity"] = val / 100 if val > 1 else val
                # 虚线
                if "虚线" in instruction or "dash" in instruction_lower:
                    style["dashArray"] = "6,4"

                if style:
                    return {
                        "action": "update_style",
                        "params": {
                            "layer_ids": [l["id"] for l in target_layers],
                            "style": style,
                        },
                    }

        # ===== 添加图层 =====
        if any(kw in instruction for kw in ["添加", "加", "新增", "add"]) and any(kw in instruction for kw in ["图层", "layer", "道路", "铁路", "水系", "景点"]):
            query = None
            name = "新图层"
            layer_type = "polyline"

            if "道路" in instruction or "road" in instruction_lower or "highway" in instruction_lower:
                query = "highway"
                name = "道路"
            elif "铁路" in instruction or "railway" in instruction_lower:
                query = "railway"
                name = "铁路"
            elif "水" in instruction or "water" in instruction_lower or "river" in instruction_lower:
                query = "waterway"
                name = "水系"
            elif "景点" in instruction or "旅游" in instruction or "tourism" in instruction_lower:
                query = "tourism"
                name = "旅游景点"
                layer_type = "marker"
            elif "建筑" in instruction or "building" in instruction_lower:
                query = "building"
                name = "建筑物"

            return {"action": "add_layer", "params": {"layer_type": layer_type, "name": name, "query": query}}

        # ===== 删除图层 =====
        if any(kw in instruction for kw in ["删除", "移除", "去掉", "remove", "delete"]) and any(kw in instruction for kw in ["图层", "layer"]):
            target_layer = self._find_layer_by_keyword(instruction, layers)
            if target_layer:
                return {"action": "remove_layer", "params": {"layer_id": target_layer["id"]}}

        # ===== 修改视图 =====
        if any(kw in instruction for kw in ["缩放", "zoom", "放大", "缩小", "中心", "居中", "移动"]):
            params = {}
            if "放大" in instruction:
                params["zoom"] = 14
            elif "缩小" in instruction:
                params["zoom"] = 10
            elif "缩放" in instruction or "zoom" in instruction_lower:
                num_match = re.search(r"(\d+)", instruction)
                if num_match:
                    params["zoom"] = int(num_match.group(1))
            return {"action": "update_view", "params": params}

        # ===== 修改主题 =====
        theme_map = {
            "标准": "standard", "浅色": "positron", "亮色": "positron",
            "深色": "dark", "暗色": "dark", "黑色": "dark",
            "卫星": "satellite", "影像": "satellite",
        }
        for zh, en in theme_map.items():
            if zh in instruction or en in instruction_lower:
                if any(kw in instruction for kw in ["主题", "底图", "theme", "切换", "换"]):
                    return {"action": "update_theme", "params": {"theme": en}}

        return None

    # ==================== 辅助方法 ====================

    def _is_map_request(self, message: str) -> bool:
        """判断是否为制图请求"""
        return any(kw in message for kw in self.MAP_KEYWORDS)

    def _is_modify_request(self, message: str) -> bool:
        """判断是否为地图修改请求"""
        return any(kw in message for kw in self.MODIFY_KEYWORDS) and not self._is_map_request(message)

    def _create_step(self, name: str, description: str) -> AgentStep:
        """创建执行步骤"""
        return AgentStep(
            step_id=generate_id("step"),
            name=name,
            description=description,
            status="pending",
        )

    def _llm_parse_requirement(self, message: str) -> Optional[dict]:
        """使用LLM增强需求解析

        Args:
            message: 用户输入

        Returns:
            解析结果 {city, map_type}，失败返回None
        """
        if not self.llm_service:
            return None

        system_prompt = (
            "你是一个地图制图需求解析器。从用户输入中提取城市名称和地图类型。\n"
            "支持的地图类型: traffic(交通图), tourism(旅游图), campus(校园图), "
            "basic(基础地图), food(美食图), administrative(行政区划图)\n"
            "返回JSON格式: {\"city\": \"城市名\", \"map_type\": \"地图类型\"}"
        )

        result = self.llm_service.generate(message, system_prompt)
        if not result:
            return None

        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1] if "\n" in result else result[3:]
        if result.endswith("```"):
            result = result[:-3]
        result = result.strip()

        parsed = safe_json_loads(result, None)
        if parsed and isinstance(parsed, dict):
            return parsed

        return None

    def _validate_map_quality(self, map_data: dict, city: str) -> List[str]:
        """地图质量校验

        Args:
            map_data: 地图数据
            city: 城市名称

        Returns:
            质量问题列表（空列表表示无问题）
        """
        issues = []
        map_type = map_data.get("map_type", "")

        # 检查图层数量
        layers = map_data.get("layers", [])
        if len(layers) == 0:
            issues.append("地图没有图层，可能OSM数据获取失败")

        # 检查坐标范围（行政区划图图幅含周边地市/省界/湖泊，坐标超出市区bbox属正常表达，跳过）
        bbox = CITY_BBOX.get(city)
        if bbox and map_type != "administrative":
            for layer in layers:
                coords = layer.get("coordinates", [])
                for coord in coords:
                    if isinstance(coord, list) and len(coord) == 2 and isinstance(coord[0], (int, float)):
                        # 单点 [lat, lng]
                        lat, lng = coord[0], coord[1]
                        if not (bbox["min_lat"] <= lat <= bbox["max_lat"] and
                                bbox["min_lon"] <= lng <= bbox["max_lon"]):
                            issues.append(f"坐标({lat}, {lng})超出{city}的范围")
                            break
                    elif isinstance(coord, list) and len(coord) > 0 and isinstance(coord[0], list):
                        # 点列表 [[lat, lng], ...]
                        for pt in coord[:3]:  # 只检查前几个点
                            if isinstance(pt, list) and len(pt) >= 2:
                                lat, lng = pt[0], pt[1]
                                if not (bbox["min_lat"] - 1 <= lat <= bbox["max_lat"] + 1 and
                                        bbox["min_lon"] - 1 <= lng <= bbox["max_lon"] + 1):
                                    issues.append(f"图层'{layer.get('name')}'有坐标超出{city}范围")
                                    break

        # 检查空图层（兼容features型图层：区县政区等坐标在features数组内）
        for layer in layers:
            if not layer.get("coordinates") and not layer.get("features"):
                issues.append(f"图层'{layer.get('name')}'没有坐标数据")

        return issues

    def _generate_response_text(
        self,
        map_data: dict,
        city: str,
        map_type: str,
        quality_issues: List[str],
    ) -> str:
        """生成制图结果的文本回复

        Args:
            map_data: 地图数据
            city: 城市名称
            map_type: 地图类型
            quality_issues: 质量问题列表

        Returns:
            自然语言回复文本
        """
        type_name = self.MAP_TYPE_NAMES.get(map_type, "地图")
        layer_count = len(map_data.get("layers", []))
        center = map_data.get("center", [])
        zoom = map_data.get("zoom", 12)

        # 统计各图层要素数量
        layer_summary = []
        for layer in map_data.get("layers", []):
            name = layer.get("name", "未命名")
            count = len(layer.get("coordinates", []))
            layer_summary.append(f"{name}({count}个要素)")

        parts = [
            f"已为您生成{city}{type_name}。",
            f"地图包含{layer_count}个图层：{', '.join(layer_summary)}。",
            f"中心坐标: ({center[0]:.4f}, {center[1]:.4f})，缩放级别: {zoom}。",
        ]

        if quality_issues:
            parts.append(f"注意：质量校验发现{len(quality_issues)}个问题：{'；'.join(quality_issues)}")

        parts.append("您可以通过自然语言指令修改地图，例如「把道路颜色改成红色」或「添加水系图层」。")

        return "".join(parts)

    def _find_layer_by_keyword(self, text: str, layers: list) -> Optional[dict]:
        """根据关键词匹配图层

        Args:
            text: 包含图层关键词的文本
            layers: 图层列表

        Returns:
            匹配到的图层，无匹配返回None
        """
        matched = self._find_layers_by_keyword(text, layers)
        return matched[0] if matched else None

    def _find_layers_by_keyword(self, text: str, layers: list) -> list:
        """根据关键词匹配全部目标图层（如"道路"匹配所有 道路-* 图层）。"""
        name_keywords = {
            "道路": ["道路", "road", "highway"],
            "铁路": ["铁路", "railway", "rail"],
            "水系": ["水系", "水", "water", "river", "河流", "河道", "江"],
            "湖泊": ["湖泊", "湖", "lake"],
            "景点": ["景点", "旅游", "tourism", "attraction"],
            "建筑": ["建筑", "building"],
            "设施": ["设施", "amenity", "生活"],
            "绿地": ["绿地", "休闲", "leisure", "park"],
            "居民地": ["居民地", "街区", "住宅"],
            "等高线": ["等高线", "contour", "地形"],
            "边界": ["边界", "界", "boundary"],
            "注记": ["注记", "标注", "label"],
        }
        # 1) 优先按完整目标/指令中的具体图层名做名称包含匹配（如"主要河流"）
        exact_hits = []
        for layer in layers:
            n = layer.get("name", "") or ""
            if text and len(text) >= 2 and text in n:
                exact_hits.append(layer)
        if exact_hits:
            return exact_hits
        # 2) 按类别关键词匹配：用"指令中出现的具体关键词"匹配图层名
        matched = []
        for layer_name, keywords in name_keywords.items():
            kws_in_text = [kw for kw in keywords if kw in text]
            if not kws_in_text:
                continue
            for layer in layers:
                n = layer.get("name", "") or ""
                if layer_name in n or any(kw in n for kw in kws_in_text):
                    if layer not in matched:
                        matched.append(layer)
            if matched:
                break
        # 3) 兜底：仅类别名在名称中（如"水系"）
        if not matched:
            for layer_name, keywords in name_keywords.items():
                if any(kw in text for kw in keywords):
                    for layer in layers:
                        if layer_name in layer.get("name", ""):
                            if layer not in matched:
                                matched.append(layer)
                    if matched:
                        break
        # 4) 类型兜底：道路类 polyline
        if not matched and any(kw in text for kw in ("道路", "road", "highway")):
            matched = [l for l in layers if l.get("type") == "polyline" and "河流" not in l.get("name", "")]
        return matched

    def _extract_color(self, text: str) -> Optional[str]:
        """从文本中提取颜色

        支持中文颜色名称和十六进制颜色值。

        Args:
            text: 包含颜色描述的文本

        Returns:
            十六进制颜色字符串，无法提取返回None
        """
        # 检查十六进制颜色
        hex_match = re.search(r"#([0-9a-fA-F]{6})", text)
        if hex_match:
            return f"#{hex_match.group(1)}"

        # 检查中文颜色名称
        for color_name, hex_value in self.COLOR_MAP.items():
            if color_name in text:
                return hex_value

        return None

    def _modify_success_response(self, map_data: dict, message: str) -> dict:
        """构建修改成功响应

        记录KG反馈：将用户的修改决策反馈到知识图谱中，
        用于后续制图推荐的优化。

        Args:
            map_data: 更新后的地图数据
            message: 回复消息

        Returns:
            响应字典
        """
        # ===== KG反馈记录 =====
        if self.kg_service:
            try:
                # 记录修改操作到知识图谱（内存模式与Neo4j模式均记录，
                # 形成"用户反馈沉淀为知识"的闭环）
                feedback_entity = {
                    "action": "map_modification",
                    "map_type": map_data.get("map_type", "unknown"),
                    "timestamp": get_timestamp(),
                    "description": message,
                }
                self.kg_service.create_entity("ModificationFeedback", feedback_entity)
                print(f"[AgentService] KG反馈已记录: {message[:50]}")
            except Exception as e:
                print(f"[AgentService] KG反馈记录失败: {e}")

        return {
            "success": True,
            "response": message,
            "map_data": map_data,
            "action": "success",
        }
