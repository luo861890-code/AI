# 给 Gemini（哈基米）的详细提示词 · 湖北省行政区划图攻坚

> **用法**：把下面「提示词正文」整段复制给 Gemini。它包含：已验证的缺陷清单（附复现命令）、数据源选型结论、地图学质量标准、以及可直接执行的验收判据。
> **配套**：本目录下 `评价报告.md`（证据）、`实施路线图.md`（阶段）、`证据截图/`（缺陷截图）、`参考样图/`（目标质量基准）。
> **重要**：本轮**不要**再让 Gemini 重写整个制图模块。目标是把**湖北省这一张图做到出版级**，并把做对的部分沉淀成可复用算子。

---

## ⚠️ 提示词正文（从这里开始复制）

### 你的 v3.0 交付物我已用**真实数据实跑**过了。结论：**地图学知识对，代码接线错**。本轮任务是把**湖北省行政区划图**做到可进结题答辩的出版级质量，并把过程沉淀成可复用算子。

我用的是仓库真实数据（`carto-agent/backend/data/geo/`，武汉范围 OSM + DataV 政区 + SRTM 30m DEM），Python 3.12.8（geopandas 1.1.4 / matplotlib 3.11.1 / pyproj 3.7.2）。

---

## 一、必须先修的 4 个致命缺陷（每条都有复现证据）

### 缺陷 1：行政区几何被静默丢弃 12/17 个地市 —— 最严重

`calibration/topology_calibrator.py:72` 对自相交的 MultiPolygon 调用 `make_valid()`，shapely 返回 **`GeometryCollection`**；紧接着 `:76` 行的类型过滤 `geom_type.isin(["Polygon","MultiPolygon"])` 把它们**全部丢掉**。

**复现**：
```python
import geopandas as gpd
from carto_engine.calibration.topology_calibrator import TopologyCalibrator
c = gpd.read_file(r"carto-agent/backend/data/geo/hubei_cities.geojson")
print(len(c))                                    # 17
print(len(TopologyCalibrator.repair_geometries(c, "polygon")))  # 5  ← 12个市蒸发
```
**后果**：省级行政图只剩 5 个色块，且接口返回 `status=success`、`carto_score=100` —— **静默失败**。

**修法**（我已验证，一处改动 17/17 恢复）：
```python
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.validation import make_valid

def repair_polygon(g):
    if g is None or g.is_empty: return g
    if g.is_valid: return g
    mv = make_valid(g)
    if isinstance(mv, GeometryCollection):
        polys = [p for p in mv.geoms if isinstance(p, (Polygon, MultiPolygon))]
        parts = [q for p in polys for q in (p.geoms if hasattr(p, "geoms") else [p])]
        parts = [q for q in parts if q.geom_type == "Polygon" and q.area > 0]
        return MultiPolygon(parts) if parts else g
    return mv
```
**额外要求**：修复后必须**统计并输出** `原始要素数 / 保留要素数 / 丢弃要素数`，丢弃数 > 0 时**报警而不是静默通过**。所有清洗算子都要有这条"**静默失败防护**"。

---

### 缺陷 2：中文渲染为豆腐块 □□□，且无任何提示

`renderers/base_renderer.py:27-34` 的 `detect_cjk_font()` 用 `f.name in fm.fontManager.ttflist` 判断字体存在 —— 这是**缓存列表**，可能包含文件已不存在的条目。

**复现**（注入一条失效条目即可复现）：
```python
from matplotlib.font_manager import FontEntry
import matplotlib.font_manager as fm
fm.fontManager.ttflist.insert(0, FontEntry(
    fname=r"C:\Windows\Fonts\wqy-microhei.ttc", name="WenQuanYi Micro Hei",
    style="normal", variant="normal", weight=400, stretch="normal", size="scalable"))
# 之后 detect_cjk_font() 会选中它 → 所有中文变 □，savefig 仍"成功"
```
**更根本的问题**：你的首选列表 `["Noto Sans CJK JP", "Noto Serif CJK JP", "WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]` **前三项全是 Linux 字体**。Windows 上真正可用的是 `Microsoft YaHei` / `SimHei` / `Noto Sans SC`。

**修法**（必须用 `findfont` 做存在性校验，且首选列表改为跨平台）：
```python
from matplotlib.font_manager import FontProperties, findfont

def detect_cjk_font() -> str:
    for name in ["Microsoft YaHei", "SimHei", "Noto Sans SC", "Noto Sans CJK SC",
                 "Source Han Sans SC", "WenQuanYi Micro Hei", "SimSun", "DejaVu Sans"]:
        try:
            findfont(FontProperties(family=name), fallback_to_default=False,
                     rebuild_if_missing=False)
            return name
        except Exception:
            continue
    return "DejaVu Sans"
```
**再加一条硬性要求**：出图前做 **missing-glyph 自检** —— 捕获 `UserWarning: Glyph xxx missing from font`，**有任何一条就判定出图失败**并抛异常，绝不能产出一张全是 □ 的"成功"图。我已把两个版本的对比图放在 `证据截图/字体缺陷_豆腐块.png` 与 `证据截图/字体缺陷_修复后.png`。

---

### 缺陷 3：「对话增量修改」完全不生效

`conversational_edit/dialogue_editor.py:151/157/165` 写入 `feature_style_overrides` / `class_scale_multipliers` / `hidden_feat_classes`，但**全仓库没有任何渲染器读取这三个字段**（grep 确认：只有写、没有读）。

**复现**：
```python
scene = MapSceneState(spec)
scene.register_cleaned_layer("admin_polygons", "行政区划面", 15, cleaned, report)
patches = ConversationalMapEditor.parse_natural_language_to_patches(
    "把武昌区改成暖橙色 #FDBA74，描边加粗到 1.8pt", scene)
ConversationalMapEditor.apply_patches(scene, patches, "...")
# 渲染前后 PNG 的 md5 完全相同 -> 14aad5e02aeb1fcd44b76c2697769657
```
**修法**：实现一个**样式解算层**，在渲染前统一结算：
```
最终样式 = 图层默认样式 ⊕ 分类级倍率 ⊕ 要素级覆盖 ⊕ 缩放自适应
```
`admin_map.py` 画填充色时必须先查 `feature_style_overrides[要素名]['fill_color']`；画线时必须乘 `class_scale_multipliers[feat_class]`；遍历时必须跳过 `hidden_feat_classes` / `hidden_feature_names`。

**验收判据（不接受肉眼判断）**：改"武昌区颜色"后重绘，与修改前做**逐像素差异掩膜**，差异区域必须**只落在武昌区**内，其他区域像素完全一致。

---

### 缺陷 4：多比例尺 LOD / Töpfer / 河流线转面 —— 全部零调用点

grep 全仓库的调用点统计：

| 函数 | 调用点 |
|---|---|
| `MultiScaleLODEngine.resolve_scale_level_spec` | **0**（除自身） |
| `CartoGeneralizer.topfer_radical_law_count` | **0** |
| `SpatialDataCleanerAndProvenance.river_centerline_to_polygon` | **0** |
| `SpatialDataCleanerAndProvenance.clean_and_register_layer` | **0** |

`traffic_map.py:80-82` 直接取 `CartoSymbolLibrary.get_traffic_road_styles()` 的**固定**样式、不传比例尺 → **渲染结果与比例尺完全无关**。你的引擎自己算得对（`1:2.5M` → motorway 1.43pt；`1:50K` → 5.5pt），但没人调用它。

`ScaleLevelSpec.admin_unit_level` 在其定义文件里出现 4 次，**没有一处被消费** → "省→市→区三级下钻"只停留在数据结构层面。

**修法**：
- `MultiScaleLODEngine` 必须被**每一个渲染器**调用，样式来源改为 `compute_scale_adaptive_road_style(road_class, current_scale_denom)`
- `topfer_radical_law_count` 接到要素选取环节（替代现在写死的 `zoom>=13` 加 `highway_minor` 这类硬编码）
- `river_centerline_to_polygon` 接到水系图层构建环节
- `clean_and_register_layer` 接到**每一个图层入口**，作为统一前置

---

## 二、一条被证伪的诊断 —— 请勿照抄

你首条诊断"GCJ-02 与 WGS-84 混用产生 300~500m 偏移"。我在**本仓库真实数据**上做了栅格互相关（1424×699 @ ~40m）与边界距离双测，结论是**该诊断在本仓库不成立**：

```
栅格互相关最佳相对位移：-1544m E / -976m N（重叠率仅 +2.3%）
边界顶点到最近 OSM 路线距离中位数：原始 115.3m → 套用 GCJ 纠偏后 115.3m（无改善）
400 个 OSM 路点落在任何政区外：原始 87 个 → 套用 GCJ 纠偏后 90 个（变差）
```

即：本地 `wuhan_districts.geojson` 的 DataV 边界**已接近 WGS-84**，真实问题是「DataV 权威边界与 OSM 路网各自精度不同造成的 100~600m 错位」，**不是**火星坐标系整体偏移。**强行套 GCJ-02 纠偏反而会引入约 500m 的新系统误差。**

**正确做法**（请改写 `crs_calibrator.py` 的策略）：
1. 每个数据源**显式标注 CRS**（`backend/data/geo/` 全部已是 WGS-84）
2. 跨源叠加时**以权威源为准**（DataV/GADM 政区 > OSM 路网），OSM 要素**捕捉对齐**到权威边界（`shapely.ops.snap`，容差 15~50m）
3. 产出一张**错位诊断图**（政区边界 vs OSM 路网叠加），量化到 p50/p90 米级
4. **不**做全局 GCJ 纠偏
5. `infer_cgcs2000_gauss_kruger_epsg()` 目前也是**零调用**，请接到实际投影环节

---

## 三、数据源选型（我已逐个连通性验证，请直接用）

| 数据 | 用途 | 端点 | 状态 |
|---|---|---|---|
| **GADM 4.1** | **省级行政区划（推荐主源）** | `https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CHN_2.json.zip` | ✅ 可下（1.4MB） |
| OSM Overpass | 水系/道路/POI/居住地 | `https://overpass.kumi.systems/api/interpreter` | ✅ 可用（**必须用 `curl.exe`**，Python requests 会被本机死代理 `127.0.0.1:9` 拦掉） |
| DataV GeoAtlas | 政区备用/校验 | `https://geo.datav.aliyun.com/areas_v3/bound/420000.json` | ✅ 可用 |
| SRTM 30m DEM | 分层设色 + 山体阴影 | `https://elevation-tiles-prod.s3.amazonaws.com/skadi/{N##}/{N##E###}.hgt.gz` | ✅ 可用（注意路径含纬度子目录） |
| Natural Earth / geoBoundaries | 备选/交叉校验 | `https://naciscdn.org/...` / `https://www.geoboundaries.org/api/current/gbOpen/CHN/ADM1/` | ✅ 可用 |
| ~~Overpass via requests~~ | — | — | ❌ 死代理，见上 |
| ~~QGIS / ArcGIS Pro~~ | — | 本机未安装 | ❌ 不可用 |

### 关键实测结论：**GADM 4.1 明显优于 DataV**
```
                       要素数   无效几何
GADM 4.1 (Hubei pref)   17        0     ← 全部有效
DataV  hubei_cities     17       12     ← 12 个自相交
```
省域 IoU = 0.9911（同一数据谱系），但 **GADM 直接可用，DataV 必须先修几何**。
⚠️ 注意 GADM 4.1 的 `NAME_2` 是英文（`Wuhan` / `Shiyan` / `EnshiTujiaandMiao`），**必须建立中英文映射表**，我已验证映射可用（见 `参考样图/` 那张图的成果）。

### OSM Overpass 的正确用法（本轮踩过的坑）
- ❌ `area["name:en"="Hubei"]["admin_level"="4"]->.a;` 形式**返回空**，要改用 `name` 正则匹配
- ✅ 行政区边界要 `out geom;` + 关系 ID，**用 `convert geom` 组装多边形**：
```
[out:json][timeout:300];
rel["admin_level"="6"]["boundary"="administrative"]["name"~"^(武汉|黄石|十堰|宜昌|襄阳|鄂州|荆门|孝感|荆州|黄冈|咸宁|随州|恩施|仙桃|潜江|天门|神农架)"];
convert geom ::id = id(), name = t["name"], adcode = t["adcode"];
out geom;
```
- ✅ 水系：`way["waterway"="river"]["name"~"^(长江|汉江|清江|...)$"](29.0,108.2,33.4,116.2); out geom;` → 湖北省域取到 **189 条河线**
- ⚠️ `out geom` 的 relation 元素**不含坐标**（只有 bounds 和 members），必须靠 `convert geom` 才有几何
- ⚠️ 本机 `HTTP_PROXY=127.0.0.1:9` 是**死代理**，`requests`/`urllib` 全部失败，**只能用 `curl.exe`**（仓库 `osm_service.py` 已用同样办法）

---

## 四、湖北省行政区划图的地图学质量标准（逐条验收）

我已用 **GADM + OSM 水系 + SRTM** 做出了一张基准样图放在 `参考样图/REFERENCE_hubei_admin.png`，**它就是质量下限**，请对标。

### 4.1 空间基准
- 投影：**CGCS2000 高斯-克吕格 3°带 CM 114°E（EPSG:4547）**，不是经纬度直接画
- ⚠️ 你的 `base_renderer.calibrate_all_layers()` 全部 `target_epsg=4326` → **成图是经纬度直接画的**，纬度方向拉伸、比例尺不严谨，而图上却印着"CGCS2000 / 高斯投影校准" —— **标注与实际不符**。请改为：几何在 EPSG:4547 下作业，**经纬度仅用于注记定位与图廓标注**。

### 4.2 图形-背景层次（自下而上）
| 层 | 内容 | 规范 |
|---|---|---|
| 1 | 高程分层设色 | 平原淡绿 → 台地黄绿 → 丘陵暖黄 → 低山浅褐 → 高山深棕，**低饱和** |
| 2 | 山体阴影 | **315° 西北光源 / 45° 高度角**（`LightSource(azdeg=315, altdeg=45)`，`vert_exag≈2.0`） |
| 3 | 政区普染 | 四色拓扑邻接，**相邻绝不同色**；用**低饱和淡雅色**（不是 Tailwind 亮色） |
| 4 | 长江/汉江 | **真实宽度面状**：长江 1400m、汉江 350m，浅蓝填充 + 深蓝水涯线 |
| 5 | 界线上色带 | 界两侧的半透明紫晕带（模拟晕滃） |
| 6 | 界线 | 省级=点划线 `dashdot`，市级=虚线 `dashed` |
| 7 | 驻地符号 | 省级行政中心=**红色五角星** + 白描边 + 红字加粗注记 |
| 8 | 注记 | 政区名居中，**白描边 Halo**，按优先级避让 |

### 4.3 四色普染
- 邻接判定必须用**真实共享边界**（`touches` 或 `intersects`），**不是** `distance < 1e-4`（那会把"隔着一条街的两个区"判成邻接）
- 我的实测：**17 市州用 5 色、13 个市辖区用 4 色，同色相邻对 = 0**（Welsh-Powell 贪心即可达到）
- 色板要用**国标淡雅色系**（我的基准用 `#DCE9D5 / #F2E2C4 / #E5D8EC / #FBE0DA / #D8E6EE / #EFEDD4`），不是你现在的 `#FCE4D6 / #E2EFDA / #FFF2CC ...`（那套在地图上偏粉偏艳）

### 4.4 长江面状化（你的头号未接线功能）
- **必须在米制投影下缓冲**（EPSG:4547），不能在经纬度空间 buffer
- 真实宽度查表（我已用 OSM 189 条河线验证过这个表在省域尺度效果良好）：长江 1400m、汉江 350m、清江 220m、沮河/漳河 150~160m、滠水 110m、内荆河 110m、府河/澴水/唐白河 90~100m、其余 70m
- ⚠️ 你的 `river_centerline_to_polygon()` 用 `real_half_deg = (real_w_m/2)/102000` 这种**经纬度近似**，在 30°N 附近有 ~8% 误差，且**无法表达面宽随比例尺变化**。请改为：米制投影缓冲 → 投影回 4326
- **面宽下限约束**：任何比例尺下长江都不得塌成一根线（保证双岸线可辨）
- **注意**：OSM 的水系是**分段的**（`长江` 有 35 段、`汉江` 34 段），必须先**按 name 合并**再缓冲，否则会出现 35 个不连续的水泡。参考样图里我是先合并再缓冲的。

### 4.5 图面整饰（你的 `map_elements.py` 有三处硬伤）
1. **图廓不闭合** —— `:82`/`:99` 用了**负值** `y_pos=-band_h` / `x_pos=-band_w` 配 `transform=ax.transAxes`，而 `savefig(bbox_inches="tight")` 会裁掉画布外图元。**像素级实测**：成品图四边 6px 内深色覆盖率**全部 0.0%**，只有顶边 1 行有（28%），且被图名框压住（zorder 100 > 99）。
   → **改法**：斑马纹画在 axes **内部**（或改用 `bbox_inches=None` + 固定画布尺寸 + `subplots_adjust`），确保 **4 边闭合**。
2. **比例尺只画 2 段** —— 国标图形比例尺应为 **4 段黑白交替**。
3. **缺经纬网分度带** —— 要有 1°/2° 经纬网 + 度分秒标注（你的 `format_dms` 写得不错，保留）。

### 4.6 图廓外的合规信息（GB/T 20257 / 审图要求）
- 主图名（中文）+ 副图名（英文）
- **数据来源与版权**：`GADM 4.1（省级行政区划）· 水系：OpenStreetMap (ODbL) · 高程：SRTM 30m (NASA)`
- **投影说明**：`CGCS2000 高斯-克吕格 3°带 CM 114°E (EPSG:4547)`
- **编制单位**：`武汉大学资源与环境科学学院 · Carto-Agent 地图制图智能体`
- **成图日期**（自动填当前日期）

---

## 五、必须落地的工程约束

1. **模块目录**：制图代码**单独封装在一个文件夹**里，内部功能**分类标注**（你已做对的 `carto_engine/` 十分类结构保留），每个文件的 docstring 写「地图学原理 → 本函数做什么 → 输入输出 → 引用规范」。
2. **图层契约**：定义一份**图层键名契约表**（`admin_polygons` / `water_polygons` / `roads_lines` / `contours_lines` / `peaks_points` / `tourism_pois_points` / `admin_seats_points` …），后端数据适配器负责把 `wuhan_*.geojson` 映射进去。**现在的图层名对不上，导致 `tourism_map.py` 图例数 = 0。**
3. **字段契约**：等高线真实字段是 `ele` + `index`(0/1)，你的代码按 `feat_class` 过滤 → **对不上**。要么改代码，要么在适配器里做字段映射（推荐后者）。
4. **静默失败防护**：所有清洗/过滤步骤必须输出「原始数/保留数/丢弃数」，丢弃数异常时报警。
5. **依赖**：本机 Python 3.12.8 已有 `geopandas 1.1.4 / matplotlib 3.11.1 / pyproj 3.7.2 / scipy 1.18.1`；**但仓库 `requirements.txt` 只有 shapely**。请把新增依赖写进 `requirements.txt` 并注明版本。
6. **不要重造轮子**：
   - **不要**移植你的 `llm_gateway.py` —— 仓库 `backend/app/services/llm_service.py` 已有 5 个 provider（ollama/qwen/openai/deepseek/zhipu）+ 流式 + 重试，更成熟
   - **不要**保留 `carto_engine_core.py`（188KB 单文件）—— 与分包目录内容重复，双份维护必然漂移
   - **不要**新建 `KG_DECISION_RULES` 硬编码 dict —— 仓库已有 Neo4j 知识图谱（`kg_service.py` + `data/kg/init_data.json`），规则应**入库**而不是另建一套
7. **重复计算防护**：`CartoEngineFacade.render_thematic_map` 每次都 `plt.subplots`，请支持**复用 Figure/Axes** 或至少在批量出图时避免内存爆炸。

---

## 六、本轮交付物（请按此清单交付）

| # | 交付物 | 验收判据（**必须可执行、可复现**） |
|---|---|---|
| 1 | 湖北省行政区划图（1:250万）PNG | 17/17 市州齐全；四色同色相邻对 = 0；长江为**双岸线面状**且有真实宽度；图廓 4 边闭合；**无豆腐块**；图廓含数据来源/投影/编制单位 |
| 2 | 同一张图的**三个比例尺**版本 | 1:250万 / 1:40万（武汉 13 区） / 1:5万（武昌-东湖）；**道路线宽随比例尺连续变化**；要素按载负量随尺度增减 |
| 3 | **数据溯源报告**（JSON） | 每图层：来源/许可/原始要素数/清洗后要素数/丢弃数/几何有效性/CRS/属性完整率/质量分 |
| 4 | **错位诊断图 + 量化表** | 政区 vs OSM 路网叠加图 + p50/p90 米级数值表 |
| 5 | **可复现脚本** | 一个命令能重新生成上面所有图与报告（如 `python tools/build_hubei_map.py`），且**数据获取 → 清洗 → 制图**全链路包含在内（含 Overpass 的 curl 调用与缓存） |
| 6 | **回归自检脚本** | `python tools/eval_carto.py --map <id>` 输出：四色合规/注记碰撞数/图廓闭合性/中文字体缺失数/载负量/各 zoom 档显隐矩阵 —— **这是后续一切改动的验收基线** |
| 7 | **缺陷修复说明** | 逐条对应第 1 节的 4 个缺陷，每条给出「改动位置 → 复现命令 → 修复前后数值对比」 |

**不要**再输出"架构设计文档"或"十大分类说明"作为主要交付 —— 那些已经有了。**这一轮要的是能进结题材料的高质量地图和可复现的代码。**

---

## 七、参考目录说明

```
test/gemini/
├── 提示词_给Gemini.md              ← 本文件（你正在读）
├── 评价报告.md                      ← 逐条核验 + 缺陷清单 + 移植 ROI 清单
├── 实施路线图.md                    ← 6 阶段路线图（阶段 1 = 你本轮要做的）
├── 会话记忆与决策台账.md             ← 项目事实基线（现有系统技术栈、代码位置索引）
├── 证据截图/                        ← 缺陷证据
│   ├── admin_prov.png               ← 12/17 个市消失（缺陷 1）
│   ├── admin_map.png                ← 中文豆腐块（缺陷 2）
│   ├── 字体缺陷_豆腐块.png / 字体缺陷_修复后.png
│   ├── 图廓缺陷_顶边.png / 图廓缺陷_底边.png
│   ├── traffic.png                  ← 交通图（唯一可直接采纳的成果）
│   └── fixed_admin_province.png / fixed_admin_wuhan.png   ← 我修正后的 17/17 版本
├── 参考样图/                        ← ★ 质量基准
│   ├── REFERENCE_hubei_admin.png    ← ★★★ 请对标这张
│   ├── build_reference_hubei.py     ← 完整可运行链路（取数→清洗→制图）
│   ├── get_dem.py                   ← SRTM 批量下载（37 tiles，8 线程）
│   └── fetch_osm_rivers.py          ← Overpass 抓水系（必须用 curl.exe）
└── carto_engine_module/             ← 你的 v3.0 交付物
```

### `参考样图/REFERENCE_hubei_admin.png` 是怎么做的（可直接照抄流程）
```
[1] ACQUIRE   GADM 4.1 CHN_2（17 个市州，0 无效；NAME_2 是英文，需中文映射表）
              Overpass 189 条长江/汉江/清江…河线（必须先按 name 合并）
              SRTM 30m（37 tiles，1° 分幅，需二维拼接 + 缺测插值消缝）
[2] CLEAN     make_valid + GeometryCollection 重组 → 0 无效
[3] PROJECT   → EPSG:4547（CGCS2000 3°带 CM 114E）
[4] TERRAIN   SRTM → 0.01° 网格 → 用**省域多边形裁剪**（否则四周会出现色晕）
              → LightSource(azdeg=315, altdeg=45).shade(vert_exag=2.2) + 6 段低饱和色带
[5] SYMBOLIZE 四色 Welsh-Powell（5 色，同色相邻 0）
              河流按真实米数在米制投影下 buffer → 面
              界线：内侧 4.2pt 紫晕带(alpha .38) + 1.05pt 虚线；省界 5.0pt 晕带 + 2.0pt 点划线
[6] ANNOTATE  代表点取名 + 优先级排序 + 矩形碰撞检测 + 白描边 Halo
[7] COMPOSE   标题(中/英) + 4 段黑白比例尺 + 分层图例 + 斑马图廓 + 经纬网 + 数据来源脚注
```
完整可运行脚本就在 `参考样图/build_reference_hubei.py`（配套 `get_dem.py` 下载 DEM、`fetch_osm_rivers.py` 抓河线）。
**请把这条链路产品化**：从"取数 → 清洗 → 制图"全在一个脚本里跑通，这就是你要交付的 `tools/build_hubei_map.py`。

### 参考样图的已知不足（别照抄这些）
1. 斑马纹图廓只是**加了粗边框**，还没做黑白交替分段（你的 `map_elements.py` 有这个能力，但**画在了画布外**）
2. 经纬网**没有度分秒标注**
3. 图例色带条是**示意**，没有标注高程区间
4. 只有**省级**一档比例尺，缺 1:40万 / 1:5万 的下钻版本
5. 缺**指北针**
→ 这 5 条正是本轮要你补齐的。

---

## 八、给 Gemini 的一句话总结

> **你的地图学知识（GB/T 20257、Bertin、Töpfer、四色定理、Chaikin、Yoeli 八方位）全部用对了，问题全出在"最后一步"**：
> 几何重组漏了 GeometryCollection、字体探测没做存在性校验、样式覆盖没接到渲染器、LOD 引擎没被调用、投影没真用。
> **本轮把这 5 件事做对，把湖北省这张图做到 `参考样图/` 的水平，并把过程沉淀成 `tools/` 下可复现的脚本。**
> **不要重写架构，要交付能进结题答辩的图。**
