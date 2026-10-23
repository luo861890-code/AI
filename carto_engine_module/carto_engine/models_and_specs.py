# -*- coding: utf-8 -*-
"""
================================================================================
[分类一：数据模型与制图任务规范] `models_and_specs.py`
================================================================================
设计依据：
1. 武汉大学艾廷华教授《DeepSeek驱动下的地图生成》（DoMapAI 框架）中的制图任务书六维解析模型：
   空间范围(Region) - 时间区间(Time) - 尺度比例尺(Scale) - 任务主题(Theme) - 用户受众(Audience) - 符号表达(Symbology)。
2. 样例文献 `LLM-KG-Carto` 中的 7 大核心地图学概念本体：
   MapElement, MapSymbol, CartographicData, MapProjection, InfluencingFactor, CartographicDecision, LayerConfig。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any


class MapType(str, Enum):
    """四大基础地图专题类型枚举"""
    TRAFFIC = "traffic"               # 交通图（道路网、铁路、地铁、交通枢纽）
    TOURISM = "tourism"               # 旅游景点图（A级景区、人文/自然地标、游览路线、生态廊道）
    ADMINISTRATIVE = "administrative" # 行政规划图（省/市/区县三级政区、境界跳绘与色带、行政驻地）
    TERRAIN = "terrain"               # 地势图（高程分层设色、山体阴影Hillshade、计曲线/首曲线、山峰点）


class AudienceType(str, Enum):
    """目标读者受众画像（决定色彩饱和度、注记字号与符号抽象程度）"""
    PUBLIC = "public"                 # 公众查阅（色彩明快、象形符号直观、字号适中）
    EXPERT = "expert"                 # 专家规划/科研（严谨国标图式、高信息负载、精确坐标网）
    EDUCATION = "education"           # 教学演示（高对比度、夸张分级、清晰层次）
    ELDERLY_KIDS = "elderly_kids"     # 老人/儿童（大字号、极简要素选取、高辨识度配色）


class CoordSystemType(str, Enum):
    """常见国内空间数据坐标系枚举（用于 SHP 数据校准）"""
    WGS84 = "WGS84"                   # EPSG:4326 (OSM、GPS、SRTM DEM 原始坐标)
    CGCS2000 = "CGCS2000"             # EPSG:4490 (中国2000国家大地坐标系，天地图/自然资源部标准)
    GCJ02 = "GCJ02"                   # 国测局火星坐标系（高德地图 API、DataV GeoAtlas、腾讯地图）
    BD09 = "BD09"                     # 百度坐标系
    PROJECTED_METRIC = "PROJECTED"    # 已投影的平面直角坐标系（如 CGCS2000 高斯-克吕格 3°带）


@dataclass
class VisualVariableSpec:
    """
    Bertin 视觉变量与地图符号样式规范
    涵盖形状(Shape)、尺寸(Size)、色彩(Hue/Value/Saturation)、纹理(Pattern)、方向(Orientation)
    """
    geometry_type: str                           # 'point', 'line', 'polygon', 'raster'
    fill_color: str = "#E8EEF5"                  # 填充色 (Hex)
    fill_opacity: float = 0.85                   # 填充不透明度 (0.0 - 1.0)
    stroke_color: str = "#333333"                # 描边/线状符号主色
    stroke_width: float = 1.0                    # 线宽 (pt)
    stroke_linestyle: str = "solid"              # 线型 ('solid', 'dashed', 'dashdot', 'dotted')
    # 复合符号扩展属性（地图学高级语言）
    casing_color: Optional[str] = None           # 双线道路外廓线颜色 (Road Casing)
    casing_width: Optional[float] = None         # 双线道路外廓线宽度 (必须 > stroke_width)
    inner_glow_color: Optional[str] = None       # 政区境界内侧晕染带颜色 (Boundary Tint Band)
    inner_glow_width: Optional[float] = None     # 政区境界内侧晕染带宽度
    railway_ticks: bool = False                  # 是否绘制铁路黑白相间轨枕符
    marker_symbol: str = "o"                     # 点状符号形状 ('*', 'double_circle', 'o', '^', 's', 'D')
    marker_size: float = 6.0                     # 点状符号尺寸 (pt)
    marker_halo_color: str = "#FFFFFF"           # 点状符号外白边光晕色
    marker_halo_width: float = 1.2               # 点状符号外白边宽度
    hatch_pattern: Optional[str] = None          # 面状纹理填充 ('//', '..', 'xx')


@dataclass
class LabelStyleSpec:
    """地图注记（地图语言文字要素）样式规范"""
    enabled: bool = True
    field_name: str = "name"                     # 注记绑定的属性字段名
    font_size: float = 9.0                       # 字号 (pt)
    font_weight: str = "normal"                  # 字重 ('normal', 'bold')
    font_style: str = "normal"                   # 字形 ('normal', 'italic' 水系左斜体)
    font_color: str = "#222222"                  # 字体颜色
    halo_color: str = "#FFFFFF"                  # 文字描边光晕颜色 (Text Buffer/Halo)
    halo_width: float = 2.0                      # 文字描边宽度 (pt)
    char_spacing: int = 0                        # 面状政区注记字列间隔空格数
    priority: int = 5                            # 碰撞避让优先级 (1 最高 ~ 10 最低)
    placement: str = "eight_position"            # 'eight_position'(点), 'centroid_spaced'(面), 'along_line'(线)


@dataclass
class LayerDefinition:
    """标准图层定义（遵循地图学图层堆栈与多尺度 LOD 约束）"""
    layer_id: str
    layer_name: str
    geometry_type: str                           # 'polygon', 'line', 'point', 'raster'
    z_order: int                                 # 图层渲染层级 (值越大越靠上)
    source_crs: CoordSystemType = CoordSystemType.WGS84
    visual_style: VisualVariableSpec = field(default_factory=lambda: VisualVariableSpec("polygon"))
    label_style: Optional[LabelStyleSpec] = None
    classify_field: Optional[str] = None         # 分类/分级字段名
    classify_method: Optional[str] = None        # 'categorical', 'jenks', 'quantile', 'equal_interval'
    category_styles: Dict[Any, VisualVariableSpec] = field(default_factory=dict)
    min_scale_denom: int = 1000                  # 最小可见比例尺分母
    max_scale_denom: int = 10000000              # 最大可见比例尺分母


@dataclass
class CartoTaskSpec:
    """
    制图任务书配置对象（对接 KGPriorPlanner 与 LLM 意图解析输出）
    消除原系统中硬编码城市与硬编码 Zoom 的问题
    """
    title: str                                   # 主图名（如“武汉市交通网络专题图”）
    subtitle: str = ""                           # 副图名/制图说明
    map_type: MapType = MapType.ADMINISTRATIVE   # 四大核心地图类型之一
    region_name: str = "武汉市"                   # 制图区域名称
    bbox_wgs84: Optional[Tuple[float, float, float, float]] = None  # (min_lon, min_lat, max_lon, max_lat)
    source_scale_denom: int = 100000             # 原始数据比例尺分母 (如 1:10万)
    target_scale_denom: int = 250000             # 目标成图比例尺分母 (如 1:25万，用于开方根综合)
    audience: AudienceType = AudienceType.PUBLIC # 目标受众
    use_metric_projection: bool = True           # 是否启用高斯-克吕格/Albers平面投影渲染后换算经纬网
    show_graticule: bool = True                  # 是否绘制经纬网分度带外图廓
    show_compass: bool = True                    # 是否绘制指北针
    show_scale_bar: bool = True                  # 是否绘制黑白交替线段比例尺
    show_legend: bool = True                     # 是否绘制结构化分层图例
    author_credit: str = "武汉大学资源与环境科学学院 · Carto-Agent 智能制图系统"
    dpi: int = 300                               # 出版级输出分辨率
