"""六维任务解析器 - 从自然语言提取结构化制图任务描述

SixDimParser 是 DoMapAI 六维任务理解框架的核心解析组件，
支持 LLM 解析和关键词规则降级两种模式。
"""
from typing import Optional

from app.models.agent_models import CartographyTask


class SixDimParser:
    """六维任务解析器

    将用户自然语言输入解析为 CartographyTask 六维结构化描述。
    优先使用 LLM 进行语义解析，LLM 不可用时降级为关键词规则匹配。
    """

    SYSTEM_PROMPT = (
        "你是一个地图制图需求分析专家。从用户输入中提取六维信息：\n"
        "1. 空间范围(spatial_scope)：描述制图的地理区域，如\"武汉市\"\"洪山区\"\"长江经济带\"\n"
        "2. 时间区间(temporal_range)：数据的时间范围，如\"2020-2025\"\"冷战时期\"，无则填null\n"
        "3. 任务主题(topic)：地图要表达的专题内容，如\"交通\"\"人口密度\"\"GDP分布\"\"土地利用\"\n"
        "4. 用户受众(audience)：expert（专家）/student（学生）/public（公众）/child（儿童）/elderly（老人）\n"
        "5. 制图方法(cartographic_method)：choropleth（底色普染）/dot_density（点密度）/flow（流向）/heatmap（热力）/symbol_map（符号地图）/graduated_symbol（分级符号）\n"
        "6. 符号风格(symbol_style)：geometric（几何符号）/pictorial（象形符号）/abstract（抽象符号）/text（文字符号）\n"
        "\n"
        "返回严格的JSON格式，不要有任何额外文本。示例：\n"
        '{"spatial_scope":"武汉市","temporal_range":null,"topic":"交通","audience":"public","cartographic_method":"symbol_map","symbol_style":"geometric"}'
    )

    def __init__(self, llm_service=None):
        """初始化解析器

        Args:
            llm_service: LLM统一调度服务实例（可选，为None时仅使用降级规则）
        """
        self.llm_service = llm_service

    def parse(self, user_input: str, context_messages: list = None) -> CartographyTask:
        """主解析方法：从用户输入提取六维制图任务描述

        优先使用LLM进行语义解析，如果LLM不可用或解析失败，
        自动降级为关键词规则匹配。

        Args:
            user_input: 用户自然语言输入
            context_messages: 多轮对话上下文（可选）

        Returns:
            CartographyTask: 六维任务描述对象
        """
        if not user_input or not user_input.strip():
            return CartographyTask()

        # ===== 尝试LLM解析 =====
        if self.llm_service:
            try:
                result = self.llm_service.generate(
                    user_input,
                    self.SYSTEM_PROMPT,
                )
                if result:
                    task = self._parse_llm_response(result)
                    if task:
                        return task
            except Exception as e:
                print(f"[SixDimParser] LLM解析失败，使用降级规则: {e}")

        # ===== 降级：关键词规则解析 =====
        return self._fallback_parse(user_input)

    def _parse_llm_response(self, raw: str) -> Optional[CartographyTask]:
        """解析LLM返回的JSON字符串为CartographyTask

        处理LLM可能返回的各种格式（含markdown代码块包装）。

        Args:
            raw: LLM原始返回文本

        Returns:
            CartographyTask对象，解析失败返回None
        """
        import json

        text = raw.strip()
        # 去除markdown代码块包装
        if text.startswith("```"):
            lines = text.split("\n")
            if len(lines) > 1:
                text = "\n".join(lines[1:])
            else:
                text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个JSON对象
            import re
            match = re.search(r'\{[^{}]*\}', text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return None
            else:
                return None

        if not isinstance(data, dict):
            return None

        return CartographyTask(
            spatial_scope=data.get("spatial_scope", ""),
            temporal_range=data.get("temporal_range"),
            topic=data.get("topic", ""),
            audience=data.get("audience", "public"),
            cartographic_method=data.get("cartographic_method", "basic"),
            symbol_style=data.get("symbol_style", "geometric"),
        )

    def _fallback_parse(self, user_input: str) -> CartographyTask:
        """降级方案：基于关键词规则的六维解析

        LLM不可用时使用预定义关键词规则进行快速匹配。
        规则覆盖空间范围、受众、主题、制图方法等维度。

        Args:
            user_input: 用户自然语言输入

        Returns:
            CartographyTask: 六维任务描述对象
        """
        spatial_scope = self._extract_spatial_scope(user_input)
        temporal_range = self._extract_temporal_range(user_input)
        topic = self._extract_topic(user_input)
        audience = self._extract_audience(user_input)
        cartographic_method = self._extract_cartographic_method(user_input)
        symbol_style = self._extract_symbol_style(user_input)

        return CartographyTask(
            spatial_scope=spatial_scope,
            temporal_range=temporal_range,
            topic=topic,
            audience=audience,
            cartographic_method=cartographic_method,
            symbol_style=symbol_style,
        )

    # ==================== 各维度关键词匹配规则 ====================

    def _extract_spatial_scope(self, text: str) -> str:
        """从文本中提取空间范围"""
        spatial_keywords = [
            ("武汉", "武汉市"),
            ("洪山", "洪山区"),
            ("武昌", "武昌区"),
            ("汉口", "汉口区"),
            ("汉阳", "汉阳区"),
            ("长江经济带", "长江经济带"),
            ("湖北", "湖北省"),
            ("北京", "北京市"),
            ("上海", "上海市"),
            ("深圳", "深圳市"),
            ("广州", "广州市"),
        ]
        for keyword, scope in spatial_keywords:
            if keyword in text:
                return scope
        return ""

    def _extract_temporal_range(self, text: str) -> Optional[str]:
        """从文本中提取时间区间"""
        import re
        # 匹配 "2020-2025" 格式
        range_match = re.search(r'(\d{4})\s*[-~至到]\s*(\d{4})', text)
        if range_match:
            return f"{range_match.group(1)}-{range_match.group(2)}"
        # 匹配 "2020年" 格式
        year_match = re.search(r'(\d{4})年', text)
        if year_match:
            return year_match.group(1)
        # 特定时期关键词
        period_keywords = [
            ("冷战时期", "冷战时期"),
            ("改革开放", "改革开放"),
            ("近十年", "近十年"),
            ("近五年", "近五年"),
            ("近年", "近年"),
        ]
        for keyword, period in period_keywords:
            if keyword in text:
                return period
        return None

    def _extract_topic(self, text: str) -> str:
        """从文本中提取任务主题"""
        topic_keywords = [
            (["交通", "道路", "地铁", "公交", "轻轨", "BRT", "高速", "国道", "铁路", "高铁"],
             "交通"),
            (["旅游", "景点", "名胜", "游玩", "观光", "风景区", "景区"],
             "旅游"),
            (["美食", "餐饮", "吃饭", "餐厅", "小吃", "美食街", "饭店"],
             "美食"),
            (["人口", "居民", "户籍"],
             "人口"),
            (["GDP", "经济", "产值", "产业", "商业"],
             "经济"),
            (["土地", "用地", "规划", "功能区", "城市规划"],
             "土地利用"),
            (["教育", "学校", "大学", "中学", "小学", "高校"],
             "教育"),
            (["医疗", "医院", "诊所", "药店", "卫生"],
             "医疗"),
            (["行政", "区划", "政府", "开发区", "高新区"],
             "行政区划"),
        ]
        for keywords, topic_name in topic_keywords:
            if any(kw in text for kw in keywords):
                return topic_name
        return ""

    def _extract_audience(self, text: str) -> str:
        """从文本中提取目标受众"""
        audience_keywords = [
            (["给专家", "给学者", "学术研究", "科研", "用于研究", "专业"],
             "expert"),
            (["给学生", "教学", "课堂", "课程", "学校用"],
             "student"),
            (["给游客", "给公众", "给大家", "给市民", "给用户", "大众", "普通"],
             "public"),
            (["给小孩", "给儿童", "孩子", "小朋友", "小学生", "幼儿"],
             "child"),
            (["给老人", "老年人", "长者", "老龄"],
             "elderly"),
        ]
        for keywords, audience_type in audience_keywords:
            if any(kw in text for kw in keywords):
                return audience_type
        return "public"

    def _extract_cartographic_method(self, text: str) -> str:
        """从文本中推断制图方法

        注意：关键词匹配顺序很重要，更具体的术语（如"热力图"）
        必须排在通用术语（如"分布"）之前，避免被过早匹配。
        """
        method_keywords = [
            # ---- 具体方法优先匹配 ----
            (["热力图", "热力", "heatmap", "聚集密度"],
             "heatmap"),
            (["点密度", "散点", "dot"],
             "dot_density"),
            (["流向", "迁移", "OD", "起点终点", "流向图"],
             "flow"),
            (["分级符号", "graduated"],
             "graduated_symbol"),
            (["符号", "标记", "标注", "图标", "symbol", "点位"],
             "symbol_map"),
            # ---- 通用术语最后匹配 ----
            (["密度", "分布", "统计", "分级", "普染", "底色", "choropleth"],
             "choropleth"),
        ]
        for keywords, method_name in method_keywords:
            if any(kw in text for kw in keywords):
                return method_name
        return "basic"

    def _extract_symbol_style(self, text: str) -> str:
        """从文本中推断符号风格"""
        style_keywords = [
            (["几何", "圆形", "方形", "三角形", "geometric"],
             "geometric"),
            (["象形", "图标", "图形", "pictorial", "具象"],
             "pictorial"),
            (["抽象", "简约", "极简", "abstract", "艺术"],
             "abstract"),
            (["文字", "标签", "注记", "text", "标注"],
             "text"),
        ]
        for keywords, style_name in style_keywords:
            if any(kw in text for kw in keywords):
                return style_name
        return "geometric"
