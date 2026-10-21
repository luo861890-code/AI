"""KG驱动的制图任务规划器 - KG推理优先，LLM辅助补充

KGPriorPlanner 实现 KG 知识优先的制图任务规划策略：
1. 优先从知识图谱提取制图决策（图层配置、符号方案、配色方案、标注规则）
2. KG信息不足时，用LLM补充缺失的规划信息
3. 将执行计划转换为LLM可用的prompt上下文，用于后续任务规划
"""
from typing import Dict, Any, List, Optional

from app.models.agent_models import CartographyTask


class ExecutionPlan:
    """制图执行计划

    将制图任务分解为结构化的三个步骤序列：
    - data_steps: 数据获取步骤（图层数据源、OSM标签、城市范围）
    - style_steps: 样式配置步骤（符号类型、颜色、线宽等）
    - render_steps: 渲染步骤（背景色、主色调、标注配置）

    Attributes:
        data_steps: 数据获取步骤列表
        style_steps: 样式配置步骤列表
        render_steps: 渲染步骤列表
        llm_enhanced: 是否使用了LLM补充（True表示KG信息不足，已用LLM兜底）
        quality_warnings: 质量警告列表（KG信息缺失、置信度低等）
    """
    def __init__(self):
        self.data_steps: List[Dict] = []
        self.style_steps: List[Dict] = []
        self.render_steps: List[Dict] = []
        self.llm_enhanced: bool = False
        self.quality_warnings: List[str] = []

    def is_empty(self) -> bool:
        """判断执行计划是否为空（没有任何有效步骤）"""
        return len(self.data_steps) == 0 and len(self.style_steps) == 0


class KGPriorPlanner:
    """KG优先规划器

    核心策略：KG推理优先 + LLM辅助补充。
    先尝试从知识图谱获取完整的制图决策方案，
    仅当KG覆盖不足时才调用LLM进行补充规划。

    使用方式：
        planner = KGPriorPlanner(kg_service=kg, llm_service=llm)
        plan = planner.plan(task, map_type="traffic", city="武汉市")
        context = planner.plan_to_prompt_context(plan)
    """

    # LLM补充规划时使用的system prompt
    LLM_PLANNING_SYSTEM_PROMPT = (
        "你是一个专业的制图任务规划助手。根据已有的KG（知识图谱）决策方案，"
        "补充缺失的制图规划步骤。请输出JSON格式，包含以下字段：\n"
        '  "data_steps": [{{"step": "fetch_data", "layer_name": "图层名", '
        '"data_source": "OSM", "osm_tags": "OSM标签", "bbox_city": "城市", "order": 序号}}],\n'
        '  "style_steps": [{{"step": "apply_style", "element_type": "要素类型", '
        '"style": {{"color": "#颜色", "weight": 线宽, "opacity": 透明度}}}}],\n'
        '  "render_steps": [{{"step": "set_base_style", "background": "#背景色", '
        '"primary_color": "#主色"}}]\n'
        "只返回JSON，不要包含其他内容。"
    )

    def __init__(self, kg_service=None, llm_service=None):
        """初始化规划器

        Args:
            kg_service: 知识图谱服务实例（KGService），提供 query_cartographic_decision 等方法
            llm_service: LLM服务实例，KG信息不足时用于补充规划。为None时跳过LLM补充
        """
        self.kg_service = kg_service
        self.llm_service = llm_service

    def plan(self, task: Optional[CartographyTask], map_type: str, city: str) -> ExecutionPlan:
        """主规划方法：KG优先提取决策 -> LLM补充缺失信息

        规划流程：
        1. 从KG查询与 map_type 和 audience 匹配的制图决策方案
        2. 从决策中提取图层配置 -> data_steps
        3. 从决策中提取符号方案 -> style_steps
        4. 从决策中提取配色和标注规则 -> render_steps
        5. 如果KG信息覆盖不足（data_steps < 2 或 style_steps < 1），调用LLM补充

        Args:
            task: 六维任务理解结果（CartographyTask），为None时使用默认受众public
            map_type: 地图类型（traffic/tourism/campus/food/basic/administrative）
            city: 城市名称

        Returns:
            结构化的执行计划 ExecutionPlan
        """
        plan = ExecutionPlan()

        # 确定受众级别
        audience = task.audience if task else "public"

        # ===== 步骤1：从KG获取制图决策 =====
        kg_decision: Dict[str, Any] = {}
        if self.kg_service:
            try:
                kg_decision = self.kg_service.query_cartographic_decision(map_type, audience)
                confidence = kg_decision.get("confidence", "none")
                print(f"[KGPriorPlanner] KG决策获取成功 (confidence={confidence})")
            except Exception as e:
                print(f"[KGPriorPlanner] KG决策获取失败: {e}")
                plan.quality_warnings.append(f"KG决策查询异常: {str(e)[:80]}")

        # ===== 步骤2：从KG决策提取数据获取步骤 =====
        layer_configs = kg_decision.get("layer_configs", [])
        for layer in layer_configs:
            if isinstance(layer, dict):
                plan.data_steps.append({
                    "step": "fetch_data",
                    "layer_name": layer.get("name", ""),
                    "data_source": layer.get("data_source", "OSM"),
                    "osm_tags": layer.get("osm_tags", ""),
                    "bbox_city": city,
                    "order": layer.get("order", 99),
                })

        # 按图层叠置顺序排序
        plan.data_steps.sort(key=lambda x: x.get("order", 99))

        # ===== 步骤3：从KG决策提取样式配置步骤 =====
        symbol_scheme = kg_decision.get("symbol_scheme", {})
        for element_type, style in symbol_scheme.items():
            if isinstance(style, dict):
                plan.style_steps.append({
                    "step": "apply_style",
                    "element_type": element_type,
                    "style": style,
                })

        # ===== 步骤4：从KG决策提取渲染步骤 =====
        color_scheme = kg_decision.get("color_scheme", {})
        annotation_rules = kg_decision.get("annotation_rules", {})

        palette = color_scheme.get("palette", {})
        plan.render_steps.append({
            "step": "set_base_style",
            "background": palette.get("background", "#FAF8F3"),
            "primary_color": palette.get("primary", "#333333"),
        })

        # 添加配色规则
        color_rules = color_scheme.get("rules", [])
        if color_rules:
            plan.render_steps.append({
                "step": "apply_color_rules",
                "rules": color_rules,
            })

        # 添加标注规则
        if annotation_rules:
            plan.render_steps.append({
                "step": "configure_annotation",
                "rules": annotation_rules,
            })

        # ===== 步骤5：KG信息不足时用LLM补充 =====
        if len(plan.data_steps) < 2 or len(plan.style_steps) < 1:
            print("[KGPriorPlanner] KG信息不足，调用LLM补充...")
            plan.llm_enhanced = True
            plan.quality_warnings.append(
                f"KG覆盖不足（data_steps={len(plan.data_steps)}, "
                f"style_steps={len(plan.style_steps)}），已启用LLM补充"
            )

            llm_plan = self._llm_supplement_plan(map_type, city, audience, plan)
            if llm_plan:
                # 合并LLM补充的步骤（仅填充KG缺失的部分）
                if len(plan.data_steps) < 2 and llm_plan.get("data_steps"):
                    existing_names = {s.get("layer_name", "") for s in plan.data_steps}
                    for ds in llm_plan["data_steps"]:
                        if ds.get("layer_name") not in existing_names:
                            plan.data_steps.append(ds)
                            existing_names.add(ds.get("layer_name"))

                if len(plan.style_steps) < 1 and llm_plan.get("style_steps"):
                    existing_types = {s.get("element_type", "") for s in plan.style_steps}
                    for ss in llm_plan["style_steps"]:
                        if ss.get("element_type") not in existing_types:
                            plan.style_steps.append(ss)
                            existing_types.add(ss.get("element_type"))

                if llm_plan.get("render_steps"):
                    plan.render_steps.extend(llm_plan["render_steps"])

        return plan

    def _llm_supplement_plan(
        self, map_type: str, city: str, audience: str, existing_plan: ExecutionPlan
    ) -> Optional[Dict[str, Any]]:
        """调用LLM补充缺失的规划步骤

        将已有的KG规划结果作为上下文，让LLM补充缺失的部分。
        使用结构化JSON输出确保结果可解析。

        Args:
            map_type: 地图类型
            city: 城市名称
            audience: 目标受众
            existing_plan: 当前已有的执行计划

        Returns:
            LLM补充的规划字典，解析失败返回None
        """
        if not self.llm_service:
            print("[KGPriorPlanner] LLM服务不可用，跳过补充")
            return None

        from app.utils.helpers import safe_json_loads

        # 构建已有KG信息的上下文
        kg_context = self.plan_to_prompt_context(existing_plan)

        prompt = (
            f"地图类型: {map_type}\n"
            f"城市: {city}\n"
            f"目标受众: {audience}\n\n"
            f"已有的KG规划结果（部分信息可能缺失，请补充缺少的步骤）：\n{kg_context}\n\n"
            f"请补充缺失的制图规划步骤（JSON格式）:"
        )

        try:
            result = self.llm_service.generate(prompt, self.LLM_PLANNING_SYSTEM_PROMPT)
            if not result:
                return None

            # 清理LLM输出
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:]) if len(lines) > 1 else result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            parsed = safe_json_loads(result, None)
            if parsed and isinstance(parsed, dict):
                print(f"[KGPriorPlanner] LLM补充成功: "
                      f"data_steps={len(parsed.get('data_steps', []))}, "
                      f"style_steps={len(parsed.get('style_steps', []))}")
                return parsed
        except Exception as e:
            print(f"[KGPriorPlanner] LLM补充失败: {e}")

        return None

    def plan_to_prompt_context(self, plan: ExecutionPlan) -> str:
        """将执行计划转换为LLM可用的上下文文本

        将结构化的执行计划格式化为制图任务规划文本，
        可直接注入到LLM的system prompt或user prompt中，
        作为制图决策的约束和参考。

        Args:
            plan: 执行计划实例

        Returns:
            格式化的prompt上下文字符串，每部分用分隔符标识
        """
        parts: List[str] = ["【制图执行计划（KG推导）】"]

        # 数据获取步骤
        parts.append("\n## 数据获取步骤")
        if plan.data_steps:
            for i, step in enumerate(plan.data_steps, 1):
                layer_name = step.get("layer_name", "未命名图层")
                osm_tags = step.get("osm_tags", "")
                data_source = step.get("data_source", "OSM")
                parts.append(
                    f"  {i}. 获取「{layer_name}」数据 "
                    f"(OSM标签: {osm_tags}, 数据源: {data_source})"
                )
        else:
            parts.append("  （无预设数据步骤，需LLM根据地图类型推断）")

        # 样式配置步骤
        parts.append("\n## 样式配置步骤")
        if plan.style_steps:
            for i, step in enumerate(plan.style_steps, 1):
                element_type = step.get("element_type", "未知要素")
                style = step.get("style", {})
                color = style.get("color", "默认")
                weight = style.get("weight", "默认")
                opacity = style.get("opacity", "默认")
                parts.append(
                    f"  {i}. {element_type}: color={color}, "
                    f"weight={weight}, opacity={opacity}"
                )
        else:
            parts.append("  （无预设样式步骤，需LLM根据地图类型推断）")

        # 渲染步骤
        parts.append("\n## 渲染步骤")
        if plan.render_steps:
            for i, step in enumerate(plan.render_steps, 1):
                step_type = step.get("step", "未知")
                if step_type == "set_base_style":
                    background = step.get("background", "#FAF8F3")
                    primary = step.get("primary_color", "#333333")
                    parts.append(f"  {i}. 基础样式: 背景色={background}, 主色调={primary}")
                elif step_type == "configure_annotation":
                    rules = step.get("rules", {})
                    parts.append(
                        f"  {i}. 标注配置: "
                        f"font={rules.get('font_family', '默认')}, "
                        f"title_size={rules.get('title_size', '默认')}, "
                        f"label_size={rules.get('label_size', '默认')}"
                    )
                elif step_type == "apply_color_rules":
                    rules = step.get("rules", [])
                    if isinstance(rules, list):
                        parts.append(f"  {i}. 配色规则: {'; '.join(rules[:3])}")
                    else:
                        parts.append(f"  {i}. 配色规则: {rules}")
                else:
                    parts.append(f"  {i}. {step}")
        else:
            parts.append("  （无预设渲染步骤）")

        # 质量警告
        if plan.quality_warnings:
            parts.append("\n## 质量提醒")
            for warning in plan.quality_warnings:
                parts.append(f"  - {warning}")

        # LLM增强标记
        if plan.llm_enhanced:
            parts.append("\n> 注意：此计划已由LLM补充，部分步骤为推导结果，置信度可能较低。")

        return "\n".join(parts)
