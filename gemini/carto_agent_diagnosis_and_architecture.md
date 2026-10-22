# 武汉大学 GIS（制图方向）大创项目 `carto-agent` 深度完善与 v3.0 升级方案

本方案基于 [luo861890-code/AI](https://github.com/luo861890-code/AI) 仓库源码、大创申报书与中期报告、项目组会议记录、艾廷华教授《[DeepSeek 驱动下的地图生成](https://pdf.dfcfw.com/pdf/H3_AP202504301664855584_1.pdf)》以及五张核心设计流程图（《知识图谱流程图》《智能化制图方法研发》《技术路线》《验证系统流程图》《智能体核心工作流》），对系统可进一步完善的核心功能进行全面重构升级，并将全部代码按 **十大功能分类** 封装于独立模块包 `carto_engine`（v3.0）中。

## 一、 对照五张核心流程图的诊断与强化迭代方案

通过对项目五张流程图的逐一审查，发现原流程设计与现有代码实现之间存在 5 处断层或不合理之处，现已在 `carto_engine` v3.0 中予以修正落地：

| 流程图名称 | 原流程设计中的不合理或断层之处 | `carto_engine` v3.0 的强化修改与代码落地 |
| :--- | :--- | :--- |
| **1.《知识图谱流程图.jpg》** | ① “定义领域范围”中仍残留“地理领域 / **图书领域 / 医疗领域**”通用模板字样，未聚焦地图学本体；<br>② 右下角“知识推理”仅支持“**单次 Cypher 语句**”，无法同时推理跨比例尺行政下钻、道路线宽缩放与多图层样式规则 | ① 在 `fine_tuning_trainer.py` 中重构为**地图学四大垂直子域本体**（空间基准与清洗域、多尺度综合与载负量域、符号视觉变量域、图面整饰与注记域）；<br>② 升级为 **多跳参数化 Cypher + 向量相似案例混合检索（Hybrid GraphRAG）** |
| **2.《智能化制图方法研发.png》** | ① 第一步直接将用户口语指令（如“画一幅武大赏樱地图”）喂给 LLM，缺乏**标准地图学结构化提示词编译环节**，易引发幻觉；<br>② 第二步“调用工具获得数据”后直接送入地图引擎，缺失**数据清洗、水系线转面与唯一寻址 ID 注册**环节 | ① 新增 `vibe_prompt_compiler.py`（**六段式 Vibe Coding 提示词编译器**）；<br>② 新增 `cleaner_and_provenance.py`，在获取数据时强制执行坐标纠偏、自相交修复、碎多边形剔除、线性河流转面状水体及精确 `feature_id`/`bbox` 注册 |
| **3.《技术路线.jpg》** | ① 第一部分写死 `ERNIE`，缺乏对市面主流大模型（**DeepSeek-V3/R1、OpenAI GPT-4o/4.1、Qwen**）的统一调度；<br>② 第四部分写为 `Vue.js + Flask + OpenLayers`，与实际仓库 `Vue 3 + FastAPI + Leaflet/Mapbox` 不一致 | ① 新增 `llm_gateway.py`（`UnifiedLLMGateway`），统一支持 **DeepSeek、OpenAI GPT、Qwen 与本地微调模型**，支持透传 DeepSeek-R1 思考链；<br>② 统一对齐为 `Vue 3 + FastAPI + CartoEngineFacade` 架构 |
| **4.《智能体.png》** | 仅支持“单次生成地图成果”的单向流水线，缺乏**多轮对话增量修改状态机（Conversational Delta Editing）**，每次追问都重头生成整张图 | 新增 `conversational_edit/` 子包（`MapSceneState` 可寻址场景状态树 + `ConversationalMapEditor` 增量补丁执行器 + Undo/Redo 快照栈） |
| **5.《验证系统流程图.jpg》** | 第三部分“评估系统 -> 优化提示词 / 优化知识或规则 / 优化工具或规划”仅有概念框，缺乏可量化训练大模型的 **SFT 数据集与强化学习奖励函数** | 在 `fine_tuning_trainer.py` 中实现 ShareGPT/OpenAI 标准格式 **SFT 微调样本生成器** 与融合地图学硬约束（Schema、拓扑、载负量、美学评分）的 **GRPO/DPO 强化学习奖励函数** |

## 二、 用户指令深度剖析与“六段式 Vibe Coding 标准地图提示词”体系

针对用户输入的简短自然语言指令，`carto_engine/prompt_and_llm/vibe_prompt_compiler.py` 会先解析显式诉求与隐性地图学规范，将其编译为可直接复制发送给 **DeepSeek / GPT** 的六段式结构化提示词：

### 样例 1：多比例尺行政规划下钻与线面尺度自适应提示词（可直接逐字复制发送给 AI）

> **【目标】** 将湖北省与武汉市多源矢量要素构建为支持三级比例尺无级缩放（L1 省域 `1:2,500,000` $\rightarrow$ L2 市域 `1:400,000` $\rightarrow$ L3 核心片区 `1:50,000`）的出版级动态行政规划与骨干路网地图（`MapSceneState`），实际运行空间坐标校准、Töpfer 开方根载负量裁剪、政区四色邻接普染、道路真实宽度幂律缩放与长江面状水系重构。
> **【制图单元与载负量】** 每个空间要素绑定唯一 `feature_id`、标准政区编码 `adcode` 与精确 `bbox_wgs84`；严格控制图面视觉面积负载率 $\le 28\%$：① 在 `1:2,500,000`（湖北省视图）下，以 17 个地级市州多边形为基本制图单元（武汉市作为单一市级图斑，不显示内部区界），仅保留省会/地市驻地、面状长江/汉江与国高网（`motorway`/`railway`）；② 当视口放大至武汉市（`1:400,000`）时，自动触发行政层级下钻（Spatial Drill-Down），裂变显示武汉市 13 个市辖区行政规划边界与区级驻地，加载城市快速路与主次干道（过滤 `tertiary` 支路）；③ 当继续放大至武昌—东湖片区（`1:50,000`）时，全量显示街道支路、高校园区面与 5A/4A 地标，各尺度保留要素数遵循 Töpfer 开方根定律 $n_F = n_A \cdot C_b \cdot C_z \cdot \sqrt{M_A / M_F}$。
> **【空间基准与数据清洗】** 读取点、线、面 SHP/GeoJSON 并记录数据源 `source_provenance`；先对高德/DataV（`GCJ-02`）执行克拉索夫斯基椭球非线性逆向纠偏至 `WGS-84`，再重投影至 `CGCS2000` 高斯-克吕格 3° 分带坐标系（中央经线 114°E，`EPSG:4547`）；执行 `make_valid` 修复自相交多边形，剔除面积 $< 0.05\text{ km}^2$ 的碎多边形噪声；对长江（实测河宽 $1,200\sim 1,800\text{ m}$）、汉江（河宽 $260\sim 450\text{ m}$）禁止使用单线表示，必须基于实测河宽与比例尺可视下限缓冲重构为双岸线面状多边形（`Polygon`）。
> **【图层模型与视觉变量】** 按 7 级 Z-Order 视觉栈叠置；行政区划面采用基于 Queen 邻接矩阵的 Welsh-Powell 贪心四色/五色普染算法，境界线采用跳绘虚线/点划线叠加内侧半透明色带晕染（`Boundary Inner Glow`）；线性道路采用双线外壳符号（`Road Casing`），其线宽随比例尺分母 $S$ 按幂律函数动态缩放 $w(S) = w_{\text{ref}} \cdot (S_{\text{ref}} / S)^{0.36}$，贴合真实道路物理路幅等级（高速 $36\text{m}$ > 主干道 $28\text{m}$ > 次干道 $18\text{m}$ > 支路 $10\text{m}$）；注记执行 Yoeli 八方位权重候选框碰撞避让与政区代表点居中字列排布。
> **【输出】** 输出每个图层的清洗溯源卡片 `LayerProvenanceReport`（原始/清洗后要素数、自相交修复数、属性完整率、质量评分 `quality_score`）、可寻址 `MapSceneState` JSON 索引，以及包含黑白斑马纹经纬网内外图廓、主副图名框、双色矢量指北针、动态重算实地距离的黑白交替线段比例尺与分层图例的 300 DPI 成果图。
> **【边界】** 严格分离地理矢量数据与样式表（Data-Style Separation），大模型不得直接捏造或篡改要素几何坐标；严禁相邻行政区分配相同底色；严禁在小比例尺省域图中渲染区县内部支路造成视觉团黑；任何文字注记不得碰撞压盖图名框、指北针、图例与比例尺。

### 样例 2：多轮对话增量修改提示词（针对已生成地图进行追问微调）

> **【目标】** 基于当前已生成的武汉市 `MapSceneState`（比例尺 `1:400,000`），解析用户追问指令，生成精确寻址图层与要素的增量修改补丁序列 ` List[MapDeltaPatch]` 并实时重绘，支持一键撤销（`Undo`）。
> **【制图单元与载负量】** 精确锁定 `admin_polygons` 图层中的 `name == '武昌区'`（`adcode=420106`）、`water_polygons` 图层中的 `name IN ['长 江', '东 湖']`，以及 `roads_lines` 图层中的 `feat_class IN ['motorway', 'primary', 'tertiary']`；隐藏 `tertiary` 支路以降低图面线状载负量。
> **【空间基准与数据清洗】** 保持现有 `EPSG:4547` / `WGS-84` 校准后几何坐标与拓扑关系不变，零几何重算损耗。
> **【图层模型与视觉变量】** ① 将 `武昌区` 填充色覆写为高辨识度暖杏橙 `#FDBA74`，外廓描边加粗为 `#C2410C`（`1.8pt`）；② 将面状 `长 江` 与 `东 湖` 填充色更新为深海蓝 `#93C5FD`，水涯线更新为 `#1D4ED8`（`1.2pt`）；③ 将 `motorway` 与 `primary` 的双线道路外壳与内芯宽度乘以 `1.4x` 缩放倍率。
> **【输出】** 输出结构化 `MapDeltaPatch` JSON 数组、每条修改的地图学依据说明 `rationale`、更新后的版本审计日志 `edit_history_log` 及 300 DPI 重绘对比图。
> **【边界】** 严禁改动未提及的其他行政区（江岸、江汉、汉阳等）原有四色普染方案；修改后必须重新运行 `CartoLabelEngine` 八方位碰撞检测，确保新增高亮注记不压盖相邻要素。

## 三、 独立封装制图模块 `carto_engine` (v3.0) 十大功能分类全景架构

升级后的 `carto_engine/` 文件夹共包含 **10 大功能分类子模块（24 个核心代码文件）**，结构清晰、职责单一：

```text
carto_engine/                                  # 独立封装的地图学智能体制图核心模块包 (v3.0)
├── __init__.py                                # 模块统一导出入口与版本元数据
├── models_and_specs.py                        # [分类一：数据模型与制图任务规范] DoMapAI六维任务书、视觉变量Schema、图层定义
├── calibration/                               # [分类二：空间要素(点/线/面SHP)校准与制图综合子模块]
│   ├── crs_calibrator.py                      # 2.1 坐标系识别、GCJ02/BD09/WGS84非线性纠偏、CGCS2000高斯3°带动态投影
│   ├── topology_calibrator.py                 # 2.2 点线面SHP几何有效性修复(make_valid)、碎多边形剔除、跨源边界捕捉(Snap)与裁剪
│   └── generalization.py                      # 2.3 Töpfer开方根定律选取、道格拉斯化简、Chaikin等高线圆滑、POI空间优先级抽稀
├── symbology/                                 # [分类三：地图语言、分级符号与视觉变量子模块]
│   ├── color_schemes.py                       # 3.1 国家图式标准配色、政区拓扑邻接四色/五色着色算法、高程分层设色色带
│   ├── classification.py                      # 3.2 定量专题分级引擎(Fisher-Jenks自然断点、分位数、等间距)
│   └── symbol_library.py                      # 3.3 四大地图标准符号库(双线道路外壳Casing、铁路轨枕、境界跳绘与内晕带、双圈/五角星驻地)
├── layout_and_elements/                       # [分类四：图层层级管理、注记避让与地图整饰要素子模块]
│   ├── layer_manager.py                       # 4.1 地图学7级视觉层次(Visual Hierarchy) Z-Order堆栈管理与压盖校验
│   ├── label_engine.py                        # 4.2 八方位候选框注记配置、BBox碰撞检测避让(含整饰禁区保护)、政区字列、水系斜体
│   └── map_elements.py                        # 4.3 五大出版级整饰要素(斑马纹经纬网内外图廓、主副图名框、矢量指北针、交替比例尺、分层图例)
├── renderers/                                 # [分类五：四大核心基础地图专题渲染器子模块]
│   ├── base_renderer.py                       # 5.0 专题地图渲染抽象基类
│   ├── traffic_map.py                         # 5.1 交通图渲染器
│   ├── tourism_map.py                         # 5.2 旅游景点图渲染器
│   ├── admin_map.py                           # 5.3 行政规划图渲染器
│   └── terrain_map.py                         # 5.4 地势图渲染器
├── agent_bridge/                              # [分类六：Carto-Agent (KG + LLM) 对接与服务适配子模块]
│   ├── kg_rule_engine.py                      # 6.1 融合LLM-KG-Carto与DoMapAI的知识图谱规则推理器与地图学规范校验器
│   └── service_adapter.py                     # 6.2 无缝对接原carto-agent后端的统一门面类CartoEngineFacade
├── prompt_and_llm/                            # [分类七：六段式结构化提示词编译器、主流大模型统一网关与微调训练管线] ★v3.0新增
│   ├── vibe_prompt_compiler.py                # 7.1 自然语言指令深度剖析与六段式 Vibe Coding 地图提示词编译器
│   ├── llm_gateway.py                         # 7.2 统一接入 DeepSeek-V3/R1、OpenAI GPT-4o/4.1、Qwen 与本地微调模型的多模型路由网关
│   └── fine_tuning_trainer.py                 # 7.3 对齐流程图的 SFT 微调数据集生成器与基于地图学硬约束的 DPO/GRPO 强化学习奖励函数
├── data_cleaning/                             # [分类八：多源数据清洗、质量溯源、精确范围标注与面状水系重构] ★v3.0新增
│   └── cleaner_and_provenance.py              # 8.1 数据清洗质检评分、唯一feature_id与bbox标注、线性河流转真实宽度双岸线面状水系算法
├── conversational_edit/                       # [分类九：大模型多轮对话增量修改状态机与图层/要素精准寻址] ★v3.0新增
│   ├── map_scene_state.py                     # 9.1 可寻址地图场景状态树 (MapSceneState) 与 Undo/Redo 历史版本栈
│   └── dialogue_editor.py                     # 9.2 自然语言追问解析与增量修改补丁 (MapDeltaPatch) 原子化执行器
└── multiscale_lod/                            # [分类十：多比例尺动态缩放(LOD)、载负量自适应、行政下钻与真实道路宽度缩放] ★v3.0新增
    └── scale_lod_engine.py                    # 10.1 省->市->片区三级行政下钻、Töpfer动态载负量过滤、道路物理路幅幂律缩放计算器
```