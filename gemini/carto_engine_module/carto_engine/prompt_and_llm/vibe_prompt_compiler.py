# -*- coding: utf-8 -*-
"""
================================================================================
[分类七 - 子模块 7.1] 结构化制图提示词编译器 (Vibe Coding Prompt Compiler)
文件: `prompt_and_llm/vibe_prompt_compiler.py`
================================================================================
设计目标：
针对用户输入给智能体的模糊、口语化指令（如“帮我画一张湖北省行政规划图，放大到武汉能看到各个区和面状长江”），
进行深刻的地图学语义剖析，结合《GB/T 20257 国家基本比例尺地图图式》与知识图谱规则，
将其自动编译为严谨的 **六段式 Vibe Coding 结构化提示词**，再交由 DeepSeek / GPT 大模型执行或生成代码：
  - 【目标】：明确制图主题、区域层级、多尺度缩放与交互修改目标
  - 【制图单元与载负量】：明确各级比例尺下的最小空间观测/制图单元、要素选取阈值与 Töpfer 开方根载负量约束
  - 【空间基准与数据清洗】：明确定义 CRS 投影坐标系（如 CGCS2000 EPSG:4547）、GCJ-02 纠偏、拓扑闭合清洗与水系线转面规则
  - 【图层模型与视觉变量】：明确 Z-Order 图层栈、四色普染、道路双线 Casing 随比例尺幂律线宽公式、面状水系与注记八方位避让
  - 【输出】：明确返回的结构化 MapSceneState JSON Schema、图层/要素唯一寻址 ID、质量溯源报告及五大出版级整饰要素
  - 【边界】：明确地图学硬性禁忌（严禁相邻政区同色、严禁跨比例尺过载堆叠、严禁伪造坐标或将低精度非权威界线用于行政区划图）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StructuredCartoPrompt:
    """六段式 Vibe Coding 地图制图结构化提示词对象"""
    raw_user_instruction: str
    goal_section: str                # 【目标】
    unit_and_load_section: str       # 【制图单元与载负量】
    crs_and_cleaning_section: str    # 【空间基准与数据清洗】
    layer_and_model_section: str     # 【图层模型与视觉变量】
    output_section: str              # 【输出】
    boundary_section: str            # 【边界】
    detected_intent: Dict[str, str] = field(default_factory=dict)

    def to_vibe_coding_prompt(self) -> str:
        """导出可直接逐字复制发送给 DeepSeek / GPT 智能体或编程助手的标准格式提示词"""
        return (
            f"【目标】{self.goal_section}\n"
            f"【制图单元与载负量】{self.unit_and_load_section}\n"
            f"【空间基准与数据清洗】{self.crs_and_cleaning_section}\n"
            f"【图层模型与视觉变量】{self.layer_and_model_section}\n"
            f"【输出】{self.output_section}\n"
            f"【边界】{self.boundary_section}"
        )


class VibeCartoPromptCompiler:
    """
    自然语言制图指令深度剖析与六段式 Vibe Coding 提示词编译器
    结合地图知识图谱（Carto-KG）自动补全缺失的地图学隐性约束
    """

    # 比例尺与行政层级联动知识表
    SCALE_HIERARCHY_SPECS = {
        "province_to_city_drilldown": {
            "scales": "L1 省级宏观比例尺 (1:2,500,000, Zoom=7) -> L2 市级中观比例尺 (1:400,000, Zoom=10) -> L3 城区微观比例尺 (1:50,000, Zoom=13)",
            "units": "L1 以地级市/自治州多边形为基本制图单元（湖北省 17 个市州分隔，仅保留市级驻地与省界/市界）；"
                     "当视口缩放进入武汉市包络框 [113.70°E~115.08°E, 29.97°N~31.36°N] 且比例尺 >= 1:500,000 时，"
                     "自动触发层级下钻（Spatial Drill-Down），切换以市辖区（武昌、江岸、江汉、汉阳、洪山等 13 区）为基本制图单元；"
                     "比例尺 >= 1:80,000 时进一步下钻至街道/高校园区面状单元。",
        }
    }

    @classmethod
    def analyze_user_intent(cls, raw_text: str) -> Dict[str, str]:
        """第一阶段：剖析用户自然语言指令中的显式诉求与隐性地图学需求"""
        text = raw_text.strip()
        map_type = "administrative"
        if any(k in text for k in ["交通", "道路", "高速", "地铁", "铁路", "路网"]):
            map_type = "traffic"
        elif any(k in text for k in ["旅游", "景点", "赏樱", "景区", "游线", "公园"]):
            map_type = "tourism"
        elif any(k in text for k in ["地势", "地形", "等高线", "高程", "山体", "晕渲", "DEM"]):
            map_type = "terrain"

        is_edit = any(k in text for k in ["修改", "改成", "调大", "加粗", "换成", "隐藏", "删除", "放大到", "缩小到"])
        needs_multiscale = any(k in text for k in ["缩放", "比例尺", "放大", "湖北", "下钻", "各市", "各个区"])
        return {
            "map_type": map_type,
            "interaction_mode": "conversational_delta_edit" if is_edit else "initial_generation",
            "multiscale_enabled": "true" if needs_multiscale else "auto",
            "target_region": "湖北省 -> 武汉市 -> 核心片区" if "湖北" in text else "武汉市",
        }

    @classmethod
    def compile_instruction(
        cls,
        raw_instruction: str,
        current_scale_denom: int = 2500000,
        target_scale_denom: int = 400000,
    ) -> StructuredCartoPrompt:
        """
        第二阶段：将原始用户指令编译为完整的六段式标准地图提示词
        """
        intent = cls.analyze_user_intent(raw_instruction)
        mtype = intent["map_type"]

        # 1. 【目标】
        goal_sec = (
            f"响应用户指令“{raw_instruction}”，构建支持多比例尺无级缩放（1:{current_scale_denom:,} 至 1:{target_scale_denom:,}）"
            f"与多轮对话增量修改的{intent['target_region']}出版级地图场景状态树（MapSceneState），"
            f"实际运行空间坐标校准、Töpfer 开方根多尺度制图综合、线面尺度自适应符号化与八方位避让注记解算。"
        )

        # 2. 【制图单元与载负量】
        unit_sec = (
            "每个空间要素必须绑定唯一可寻址 `feature_id`、`adcode`（如湖北省 420000、武汉市 420100、武昌区 420106）与精确 `bbox`；"
            "严格执行尺度驱动的动态载负量控制（图面视觉面积负载率 ≤ 28%）："
            "① 在 1:2,500,000（湖北省视图）下，仅渲染 17 个地级市州多边形分隔、省会/市级驻地、面状长江与汉江干流、国家高速主干网（过滤全部区县界与城市次干道）；"
            "② 当用户放大至 1:400,000（武汉市视图）时，自动卸载省域外围市州，裂变加载武汉市各市辖区行政区划多边形、区级政府驻地、城市快速路/主干道与 5A/4A 景区；"
            "③ 当继续放大至 1:50,000（街区/校园级视图）时，加载次干道、支路、地铁站点及重点高校/景区面状范围；"
            "各比例尺保留要素数严格遵循 Töpfer 开方根定律 $n_F = n_A \\cdot C_b \\cdot C_z \\cdot \\sqrt{M_A / M_F}$。"
        )

        # 3. 【空间基准与数据清洗】
        crs_sec = (
            "读取点、线、面 SHP/GeoJSON 数据源并记录 `source_provenance`（DataV/天地图标准政区、OSM 路网、SRTM 30m DEM）；"
            "先对 GCJ-02/BD-09 坐标执行克拉索夫斯基椭球非线性逆向纠偏至 WGS-84，再重投影至 CGCS2000 高斯-克吕格 3° 分带平面坐标系（中心经线 114°E，EPSG:4547）；"
            "执行 `make_valid` 修复自相交环，剔除面积 < 0.05 km² 的碎多边形噪声（Sliver Polygons），并将支流/道路端点向权威政区边界与主河道捕捉对齐（Snap Tolerance = 15m）；"
            "对长江（城区段实测河宽 1,000~1,800m）、汉江（河宽 200~450m）禁止使用单线符号，必须基于河道中心线与实测河宽断面缓冲重构为双岸线面状多边形（Polygon）。"
        )

        # 4. 【图层模型与视觉变量】
        layer_sec = (
            "按 7 级 Z-Order 视觉栈叠置（背景政区面 Z=15 -> 生态绿地 Z=22 -> 面状长江/湖泊水系 Z=32 -> 境界内侧晕染带 Z=48 -> 等级道路网 Z=52~65 -> 政区跳绘界线 Z=70~72 -> 驻地/地标符号 Z=80~88 -> 避让注记 Z=91~98）；"
            "行政区划面采用基于 Queen 邻接矩阵的 Welsh-Powell 贪心四色/五色普染算法；"
            "线性道路采用双线外壳符号（Road Casing），其屏幕线宽 $w(S)$ 随当前比例尺分母 $S$ 按幂律函数动态缩放："
            "$w(S) = \\max(w_{\\min}, w_{\\text{real\\_m}} / S \\cdot \\text{DPI\\_factor} \\cdot (S / S_{\\text{ref}})^{0.65})$，"
            "确保放大时道路粗细平滑增宽并贴合真实路幅等级（高速 > 主干道 > 次干道 > 支路）；"
            "点状注记执行 Yoeli 八方位权重候选框与 R-Tree 包络框碰撞避让，政区名称采用代表点居中字列排布。"
        )

        # 5. 【输出】
        output_sec = (
            "输出：① 完整的 `MapSceneState` JSON（含图层树 `layers`、要素寻址索引 `feature_index`、当前比例尺 `scale_denom`、视口 `bbox_wgs84`、数据源清洗质检报告 `cleaning_report`）；"
            "② 若为多轮对话修改模式，输出精确的 `MapDeltaPatch` 增量修改指令列表（指明 `target_layer_id`、`feature_filter`、`updated_visual_vars`）及修改前后差异说明；"
            "③ 附带黑白斑马纹经纬网内外图廓、主副图名框、双色矢量指北针、动态重算实地距离的黑白交替线段比例尺与分层图例的 300 DPI 渲染图。"
        )

        # 6. 【边界】
        boundary_sec = (
            "严格保持地理几何精度，大模型仅能通过修改样式配置表（Stylesheet）或调用确定性 GIS 算子更新地图，严禁直接捏造或篡改要素坐标；"
            "严禁相邻行政区分配相同填充色；严禁在小比例尺省域图中强行塞入区县内部道路导致黑团压盖；"
            "任何注记不得压盖图名框、指北针、图例框与比例尺框。"
        )

        return StructuredCartoPrompt(
            raw_user_instruction=raw_instruction,
            goal_section=goal_sec,
            unit_and_load_section=unit_sec,
            crs_and_cleaning_section=crs_sec,
            layer_and_model_section=layer_sec,
            output_section=output_sec,
            boundary_section=boundary_sec,
            detected_intent=intent,
        )
