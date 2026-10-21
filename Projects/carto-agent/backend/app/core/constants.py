"""系统常量 - 城市坐标、地图类型映射、Overpass查询模板等"""
from typing import Dict, List, Any

# ========== 城市bbox坐标 ==========
CITY_BBOX: Dict[str, Dict[str, float]] = {
    "武汉市": {"min_lat": 30.35, "min_lon": 113.95, "max_lat": 30.75, "max_lon": 114.65, "center_lat": 30.5928, "center_lon": 114.3055},
    "北京市": {"min_lat": 39.75, "min_lon": 116.20, "max_lat": 40.05, "max_lon": 116.55, "center_lat": 39.9042, "center_lon": 116.4074},
    "上海市": {"min_lat": 30.95, "min_lon": 121.30, "max_lat": 31.35, "max_lon": 121.80, "center_lat": 31.2304, "center_lon": 121.4737},
    "广州市": {"min_lat": 22.95, "min_lon": 113.20, "max_lat": 23.35, "max_lon": 113.55, "center_lat": 23.1291, "center_lon": 113.2644},
    "深圳市": {"min_lat": 22.45, "min_lon": 113.75, "max_lat": 22.85, "max_lon": 114.40, "center_lat": 22.5431, "center_lon": 114.0579},
    "杭州市": {"min_lat": 30.15, "min_lon": 120.05, "max_lat": 30.50, "max_lon": 120.40, "center_lat": 30.2741, "center_lon": 120.1551},
    "成都市": {"min_lat": 30.55, "min_lon": 103.95, "max_lat": 30.85, "max_lon": 104.20, "center_lat": 30.5728, "center_lon": 104.0668},
    "南京市": {"min_lat": 31.95, "min_lon": 118.60, "max_lat": 32.20, "max_lon": 118.90, "center_lat": 32.0603, "center_lon": 118.7969},
    "重庆市": {"min_lat": 29.40, "min_lon": 106.40, "max_lat": 29.80, "max_lon": 106.75, "center_lat": 29.5630, "center_lon": 106.5516},
    "西安市": {"min_lat": 34.20, "min_lon": 108.85, "max_lat": 34.40, "max_lon": 109.05, "center_lat": 34.3416, "center_lon": 108.9398},
    "天津市": {"min_lat": 38.90, "min_lon": 117.00, "max_lat": 39.25, "max_lon": 117.50, "center_lat": 39.0842, "center_lon": 117.2010},
    "苏州市": {"min_lat": 31.10, "min_lon": 120.40, "max_lat": 31.45, "max_lon": 120.85, "center_lat": 31.2989, "center_lon": 120.5853},
    "长沙市": {"min_lat": 28.10, "min_lon": 112.85, "max_lat": 28.35, "max_lon": 113.10, "center_lat": 28.2282, "center_lon": 112.9388},
    "青岛市": {"min_lat": 36.00, "min_lon": 120.30, "max_lat": 36.30, "max_lon": 120.60, "center_lat": 36.0671, "center_lon": 120.3826},
    "沈阳市": {"min_lat": 41.70, "min_lon": 123.30, "max_lat": 41.95, "max_lon": 123.60, "center_lat": 41.8057, "center_lon": 123.4315},
    "哈尔滨市": {"min_lat": 45.65, "min_lon": 126.50, "max_lat": 45.85, "max_lon": 126.75, "center_lat": 45.8038, "center_lon": 126.5350},
    "昆明市": {"min_lat": 24.90, "min_lon": 102.60, "max_lat": 25.10, "max_lon": 102.80, "center_lat": 24.8801, "center_lon": 102.8329},
    "大连市": {"min_lat": 38.80, "min_lon": 121.50, "max_lat": 39.05, "max_lon": 121.80, "center_lat": 38.9140, "center_lon": 121.6147},
    "厦门市": {"min_lat": 24.40, "min_lon": 118.00, "max_lat": 24.65, "max_lon": 118.30, "center_lat": 24.4798, "center_lon": 118.0894},
    "郑州市": {"min_lat": 34.65, "min_lon": 113.50, "max_lat": 34.85, "max_lon": 113.75, "center_lat": 34.7466, "center_lon": 113.6253},
}

# ========== 地图类型映射 ==========
MAP_TYPE_MAP: Dict[str, str] = {
    "交通图": "traffic", "交通": "traffic", "道路图": "traffic",
    "旅游图": "tourism", "旅游": "tourism", "景点图": "tourism",
    "樱花地图": "tourism", "樱花": "tourism", "武大樱花": "tourism", "赏樱": "tourism",
    "校园图": "campus", "校园": "campus", "校园导览": "campus",
    "基础地图": "basic", "基础": "basic", "普通地图": "basic",
    "美食图": "food", "美食": "food", "餐饮图": "food",
    "行政区划图": "administrative", "行政区划": "administrative",
    "地形图": "terrain", "地形": "terrain", "等高线图": "terrain",
    "等高线": "terrain", "高程图": "terrain",
    # ===== 专题地图类型 =====
    "人口密度图": "population", "人口图": "population", "人口分布": "population",
    "经济分布图": "economic", "经济图": "economic", "GDP分布": "economic",
    "土地利用图": "landuse", "用地": "landuse", "土地覆盖": "landuse",
    "气候图": "climate", "气象图": "climate",
    "医疗资源图": "healthcare", "医疗图": "healthcare", "医院分布": "healthcare",
    "教育设施图": "education", "教育图": "education", "学校分布": "education",
    "商业分布图": "commercial", "商业图": "commercial", "商圈分布": "commercial",
    "绿化覆盖图": "greenery", "绿化图": "greenery", "绿地分布": "greenery",
    "热力图": "heatmap", "热力分布": "heatmap",
}

# 地图类型对应的OSM要素查询标签
MAP_TYPE_OSM_TAGS: Dict[str, List[str]] = {
    "traffic": ["highway", "railway", "waterway", "natural", "amenity", "shop"],
    "tourism": ["tourism", "leisure", "historic", "amenity", "shop"],
    "campus": ["amenity", "building", "leisure"],
    "basic": ["natural", "landuse", "leisure", "waterway", "highway", "railway",
              "building", "amenity", "shop", "tourism", "historic", "office"],
    "food": ["amenity~restaurant|fast_food|cafe|bar|pub"],
    "administrative": ["boundary~administrative", "place"],

    # 专题地图OSM标签
    "population": {"amenity": ["place_of_worship", "school"], "highway": ["residential"]},
    "economic": {"amenity": ["bank", "atm"], "shop": ["mall", "supermarket"], "office": ["company"]},
    "landuse": {"landuse": ["residential", "commercial", "industrial", "farmland", "forest", "grass", "meadow"]},
    "climate": {"natural": ["tree", "wood"], "water": ["river", "lake"]},
    "healthcare": {"amenity": ["hospital", "clinic", "doctors", "pharmacy", "dentist"]},
    "education": {"amenity": ["school", "university", "college", "kindergarten", "library"]},
    "commercial": {"shop": ["mall", "supermarket", "convenience", "clothes", "electronics"], "amenity": ["marketplace"]},
    "greenery": {"leisure": ["park", "garden"], "natural": ["wood", "tree"], "landuse": ["forest", "grass"]},
    "heatmap": {"amenity": ["restaurant", "cafe", "shop", "bank"], "shop": ["*"]},
}

# Overpass查询模板
OVERPASS_QUERY_MAP: Dict[str, str] = {
    "highway": 'way["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|service|living_street"]',
    "highway_major": 'way["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified"]',
    "highway_minor": 'way["highway"~"residential|service|living_street"]',
    "railway": 'way["railway"~"rail|subway|light_rail|monorail|tram"]',
    "waterway": 'way["waterway"~"river|stream|canal|lake|reservoir"]',
    "waterway_major": 'way["waterway"~"river|lake|reservoir"]',
    "waterway_minor": 'way["waterway"~"stream|canal|ditch|drain"]',
    "natural": 'way["natural"~"water|wood|grass|wetland|beach"]',
    "landuse": 'way["landuse"~"forest|grass|meadow|recreation_ground|village_green"]',
    "leisure": 'node["leisure"~"park|garden|playground|sports_centre|stadium|swimming_pool"];way["leisure"~"park|garden|pitch|sports_centre|stadium"]',
    "tourism": 'node["tourism"~"attraction|museum|viewpoint|hotel|guest_house|theme_park|zoo|artwork"];way["tourism"~"attraction|museum|zoo|theme_park"]',
    "historic": 'node["historic"~"castle|monument|ruins|memorial|archaeological_site"];way["historic"~"castle|monument|ruins|memorial|archaeological_site"]',
    "amenity": 'node["amenity"~"restaurant|cafe|fast_food|bar|pub|hospital|clinic|doctors|dentist|pharmacy|school|university|college|kindergarten|library|bank|atm|police|fire_station|post_office|fuel|parking|bus_station|townhall|courthouse|theatre|cinema|arts_centre|stadium|gym|place_of_worship|hotel|hostel|marketplace|supermarket|toilets|veterinary"]',
    "shop": 'node["shop"~"supermarket|mall|convenience|department_store|clothes|electronics|books|bakery|pharmacy|florist|jewelry|shoes"]',
    "office": 'node["office"~"company|government|bank|insurance|estate_agent"]',
    "building": 'way["building"]',
    "boundary~administrative": 'way["boundary"="administrative"]["admin_level"~"4|6|8|9"];relation["boundary"="administrative"]["admin_level"~"4|6"];',
    "place": 'node["place"~"city|town|suburb|borough"]',
    "place_city": 'node["place"~"city|town"]',
    "place_suburb": 'node["place"~"suburb|borough"]',
}

# ========== 地图样式配置 ==========
MAP_STYLES: Dict[str, Dict[str, Any]] = {
    "highway": [
        {"subtypes": {"motorway": {"color": "#c0392b", "weight": 6},
                       "trunk": {"color": "#d97b1f", "weight": 5},
                       "primary": {"color": "#d9a52e", "weight": 4.5},
                       "secondary": {"color": "#e8c34d", "weight": 3.5},
                       "tertiary": {"color": "#c9c9c9", "weight": 2.5}},
         "default": {"color": "#a8a8a8", "weight": 2}}
    ],
    "railway": {"color": "#555555", "weight": 2, "dashArray": "5,5"},
    "waterway": {"color": "#7dd3fc", "weight": 3, "opacity": 0.8},
    "tourism": {"color": "#dc2626", "radius": 8, "icon": "🏛️"},
    "leisure": {"color": "#22c55e", "radius": 6, "icon": "🌳"},
    "historic": {"color": "#a855f7", "radius": 7, "icon": "🏛️"},
    "amenity": {"color": "#f59e0b", "radius": 5, "icon": "📍"},
    "building": {"color": "#d1d5db", "weight": 1, "fillOpacity": 0.3},
}

# ========== 城市行政区划代码（标准行政区划图面数据用） ==========
CITY_ADCODES: Dict[str, str] = {
    "武汉市": "420100", "北京市": "110100", "上海市": "310100", "广州市": "440100",
    "深圳市": "440300", "杭州市": "330100", "成都市": "510100", "南京市": "320100",
    "重庆市": "500100", "西安市": "610100", "天津市": "120100", "苏州市": "320500",
    "长沙市": "430100", "青岛市": "370200", "沈阳市": "210100", "哈尔滨市": "230100",
    "昆明市": "530100", "大连市": "210200", "厦门市": "350200", "郑州市": "410100",
}

# 行政区划面状底图配色（标准地图柔和设色，相邻区县交替区分）
# 高区分度柔和色板：相邻区县色相差异明显，避免视觉融合
# 规范配色：相邻区县色相差>=30°或明度差>=20%（浅/深交替），饱和度20-40%柔和
# 规范配色：4 色体系（浅蓝/浅绿/浅黄/浅粉），色相间隔>=40°、明度85-93%、
# 相邻行政区使用不同色，全图色彩总数<=8（含底色/水系/边界），符合政区图用色规范
DISTRICT_FILL_COLORS: List[str] = [
    "#CFE4F5", "#D2E8CF", "#F7E8C9", "#F3D8D4",
]

# ========== 武汉行政区四色普染色（相邻区不重复，色相清晰区分）==========
WUHAN_DISTRICT_FILLS: Dict[str, str] = {
    "江岸区": "#CFE4F5",   # 浅蓝
    "江汉区": "#D2E8CF",   # 浅绿
    "硚口区": "#F7E8C9",   # 浅黄
    "汉阳区": "#F3D8D4",   # 浅粉
    "武昌区": "#CFE4F5",   # 浅蓝
    "青山区": "#D2E8CF",   # 浅绿
    "洪山区": "#F7E8C9",   # 浅黄
    "东西湖区": "#F3D8D4", # 浅粉
    "蔡甸区": "#CFE4F5",   # 浅蓝
    "汉南区": "#D2E8CF",   # 浅绿
    "江夏区": "#F7E8C9",   # 浅黄
    "黄陂区": "#D2E8CF",   # 浅绿（与东西湖区分）
    "新洲区": "#CFE4F5",   # 浅蓝
}

# ========== 标准地图境界线（规范一：市界紫粗实线/区县界黑点划线/省界黑细点线）==========
BOUNDARY_STANDARD_STYLES: Dict[str, Dict[str, Any]] = {
    "province": {"name": "省界(周边外省)", "color": "#000000", "weight": 1.2, "opacity": 0.9, "dashArray": "1,4"},
    "city":     {"name": "地级市界",       "color": "#7040A0", "weight": 3.2, "opacity": 1.0},
    "county":   {"name": "区县界",         "color": "#8A8A8A", "weight": 1.2, "opacity": 0.9, "dashArray": "6,4"},
    "town":     {"name": "乡镇界",         "color": "#000000", "weight": 0.8, "opacity": 0.6, "dashArray": "2,3"},
}


# ========== 武汉市域主边界（标准市界：红色实线，降低突兀感）==========
WUHAN_MAIN_BOUNDARY: Dict[str, Any] = {
    "name": "武汉市域边界", "color": "#E03131", "weight": 3, "opacity": 0.9,
}

# ========== 行政中心标准符号（规范三：市级★/区县●/乡镇黑点）==========
ADMIN_CENTER_STYLES: Dict[str, Dict[str, Any]] = {
    "city":     {"name": "市级行政中心", "color": "#D82828", "fillColor": "#D82828", "fillOpacity": 1.0,
                 "weight": 1, "radius": 9, "icon": "★", "iconClass": "fa-star", "kind": "admin_city"},
    "district": {"name": "区县行政中心", "color": "#D82828", "fillColor": "#D82828", "fillOpacity": 1.0,
                 "weight": 1, "radius": 5},
    "outside":  {"name": "周边市县驻地", "color": "#D82828", "fillColor": "#D82828", "fillOpacity": 0.9,
                 "weight": 1, "radius": 3.5},
    "town":     {"name": "乡镇居民点",   "color": "#000000", "fillColor": "#000000", "fillOpacity": 0.85,
                 "weight": 1, "radius": 2.2},
}

# ========== 周边地市底图（规范二-3：极浅米黄衬托，突出武汉主体）==========
SURROUNDING_CITY_FILL = "#F5F0E1"

# ========== 市级行政中心红星位置 ==========
# 按用户要求标注于武昌区（注：官方驻地实际在江岸区沿江大道188号，如需改回可调整此值）
WUHAN_GOV_COORD: List[float] = [30.5544, 114.3159]

# ========== 武汉13区兜底简化面（DataV区划面不可用时的本地回退，中心+半轴的椭圆近似）==========
# ========== 武汉重点POI（GIS叠加风格标注：机场/景区/交通枢纽等） ==========
WUHAN_GIS_POI: List[Dict[str, Any]] = [
    {"name": "武汉天河国际机场", "lat": 30.7838, "lng": 114.2081, "type": "transport"},
    {"name": "木兰文化生态旅游区", "lat": 31.1500, "lng": 114.2600, "type": "attraction"},
    {"name": "黄鹤楼", "lat": 30.5443, "lng": 114.2961, "type": "attraction"},
    {"name": "东湖绿道", "lat": 30.5600, "lng": 114.3900, "type": "scenic"},
    {"name": "湖北省博物馆", "lat": 30.5656, "lng": 114.3631, "type": "museum"},
    {"name": "武汉站", "lat": 30.6070, "lng": 114.4230, "type": "transport"},
    {"name": "汉口站", "lat": 30.6210, "lng": 114.2500, "type": "transport"},
    {"name": "光谷广场", "lat": 30.5083, "lng": 114.3975, "type": "commercial"},
    {"name": "武汉大学樱花大道", "lat": 30.5408, "lng": 114.3645, "type": "scenic"},
    {"name": "东湖磨山樱花园", "lat": 30.5520, "lng": 114.4050, "type": "scenic"},
    {"name": "晴川阁樱花园", "lat": 30.5660, "lng": 114.2860, "type": "scenic"},
]

WUHAN_DISTRICT_FALLBACK: List[Dict[str, Any]] = [
    {"name": "江岸区",   "lat": 30.6005, "lng": 114.3045, "rx": 0.050, "ry": 0.035},
    {"name": "江汉区",   "lat": 30.6011, "lng": 114.2674, "rx": 0.035, "ry": 0.025},
    {"name": "硚口区",   "lat": 30.5826, "lng": 114.2104, "rx": 0.040, "ry": 0.030},
    {"name": "汉阳区",   "lat": 30.5494, "lng": 114.2186, "rx": 0.045, "ry": 0.035},
    {"name": "武昌区",   "lat": 30.5544, "lng": 114.3159, "rx": 0.050, "ry": 0.035},
    {"name": "青山区",   "lat": 30.6385, "lng": 114.3856, "rx": 0.045, "ry": 0.030},
    {"name": "洪山区",   "lat": 30.5004, "lng": 114.3426, "rx": 0.075, "ry": 0.055},
    {"name": "东西湖区", "lat": 30.6203, "lng": 114.1368, "rx": 0.100, "ry": 0.070},
    {"name": "汉南区",   "lat": 30.3092, "lng": 114.0308, "rx": 0.070, "ry": 0.050},
    {"name": "蔡甸区",   "lat": 30.5824, "lng": 114.0292, "rx": 0.130, "ry": 0.100},
    {"name": "江夏区",   "lat": 30.3494, "lng": 114.3202, "rx": 0.160, "ry": 0.110},
    {"name": "黄陂区",   "lat": 30.8742, "lng": 114.3752, "rx": 0.140, "ry": 0.110},
    {"name": "新洲区",   "lat": 30.8422, "lng": 114.8011, "rx": 0.140, "ry": 0.100},
]

# ========== 武汉主要水系兜底（OSM水系缺失时补充；线/面为贴合真实走向的近似轮廓）==========
# 河流：多点折线（带弯曲，体现真实河道走向）；湖泊：不规则多边形（贴合实际轮廓，非椭圆）
WUHAN_WATER_FALLBACK: Dict[str, Any] = {
    # 长江（湖北东段，武汉段带弯曲：西南入境→沌口→汉口/武昌之间→青山→阳逻→东南出境）
    "rivers": [
        {"name": "长江", "weight": 2.6, "coords": [
            [30.30, 113.95], [30.33, 114.02], [30.36, 114.08], [30.40, 114.13],
            [30.44, 114.18], [30.48, 114.23], [30.51, 114.28], [30.545, 114.315],
            [30.565, 114.34], [30.585, 114.37], [30.60, 114.41], [30.615, 114.45],
            [30.62, 114.49], [30.615, 114.53], [30.60, 114.57], [30.575, 114.61],
            [30.545, 114.65], [30.50, 114.70], [30.45, 114.75], [30.40, 114.80],
            [30.35, 114.85],
        ]},
        # 汉江（西北入境→蔡甸/汉阳→汉口南岸嘴汇入长江）
        {"name": "汉江", "weight": 2.0, "coords": [
            [30.60, 113.85], [30.585, 113.92], [30.575, 113.98], [30.565, 114.04],
            [30.56, 114.09], [30.555, 114.14], [30.555, 114.18], [30.562, 114.21],
            [30.568, 114.24], [30.572, 114.265], [30.575, 114.28],
        ]},
    ],
    # 湖泊：不规则多边形 [lat,lng] 闭合环，贴合真实轮廓；label=False 的小湖不标注名称
    "lakes": [
        {"name": "东湖", "label": True, "coords": [
            [30.580, 114.320], [30.585, 114.350], [30.590, 114.380], [30.585, 114.400],
            [30.575, 114.415], [30.560, 114.420], [30.545, 114.425], [30.535, 114.420],
            [30.530, 114.400], [30.525, 114.380], [30.520, 114.365], [30.525, 114.350],
            [30.535, 114.340], [30.550, 114.330], [30.565, 114.325], [30.575, 114.320],
            [30.580, 114.320]]},
        {"name": "汤逊湖", "label": True, "coords": [
            [30.450, 114.300], [30.455, 114.330], [30.450, 114.360], [30.440, 114.380],
            [30.420, 114.390], [30.400, 114.385], [30.390, 114.370], [30.380, 114.350],
            [30.385, 114.320], [30.400, 114.290], [30.430, 114.280], [30.450, 114.300]]},
        {"name": "梁子湖", "label": True, "coords": [
            [30.340, 114.450], [30.330, 114.500], [30.310, 114.550], [30.280, 114.600],
            [30.240, 114.620], [30.200, 114.600], [30.170, 114.550], [30.160, 114.500],
            [30.170, 114.450], [30.200, 114.410], [30.250, 114.400], [30.300, 114.420],
            [30.340, 114.450]]},
        {"name": "涨渡湖", "label": True, "coords": [
            [30.710, 114.790], [30.715, 114.820], [30.710, 114.850], [30.680, 114.870],
            [30.660, 114.860], [30.650, 114.830], [30.655, 114.800], [30.670, 114.780],
            [30.710, 114.790]]},
        {"name": "后官湖", "label": True, "coords": [
            [30.520, 114.010], [30.525, 114.040], [30.520, 114.070], [30.500, 114.090],
            [30.480, 114.080], [30.465, 114.050], [30.470, 114.020], [30.490, 114.000],
            [30.520, 114.010]]},
        {"name": "金银湖", "label": False, "coords": [
            [30.665, 114.130], [30.670, 114.150], [30.660, 114.170], [30.640, 114.175],
            [30.630, 114.150], [30.635, 114.130], [30.665, 114.130]]},
        {"name": "严西湖", "label": False, "coords": [
            [30.575, 114.430], [30.580, 114.450], [30.570, 114.470], [30.550, 114.485],
            [30.530, 114.480], [30.520, 114.450], [30.530, 114.430], [30.575, 114.430]]},
        {"name": "斧头湖", "label": True, "coords": [
            [30.040, 114.260], [30.050, 114.290], [30.040, 114.320], [30.020, 114.340],
            [29.980, 114.330], [29.960, 114.300], [29.970, 114.270], [30.000, 114.250],
            [30.040, 114.260]]},
        {"name": "西凉湖", "label": True, "coords": [
            [29.950, 114.060], [29.955, 114.090], [29.940, 114.120], [29.910, 114.140],
            [29.890, 114.120], [29.880, 114.080], [29.900, 114.060], [29.950, 114.060]]},
    ],
}

# ========== 武汉行政区划中心（离线兜底标注/区中心坐标） ==========
WUHAN_DISTRICTS: List[Dict[str, Any]] = [
    {"name": "江岸区", "lat": 30.6005, "lng": 114.3045},
    {"name": "江汉区", "lat": 30.6011, "lng": 114.2674},
    {"name": "硚口区", "lat": 30.5826, "lng": 114.2104},
    {"name": "汉阳区", "lat": 30.5494, "lng": 114.2186},
    {"name": "武昌区", "lat": 30.5544, "lng": 114.3159},
    {"name": "青山区", "lat": 30.6385, "lng": 114.3856},
    {"name": "洪山区", "lat": 30.5004, "lng": 114.3426},
    {"name": "东西湖区", "lat": 30.6203, "lng": 114.1368},
    {"name": "汉南区", "lat": 30.3092, "lng": 114.0308},
    {"name": "蔡甸区", "lat": 30.5824, "lng": 114.0292},
    {"name": "江夏区", "lat": 30.3494, "lng": 114.3202},
    {"name": "黄陂区", "lat": 30.8742, "lng": 114.3752},
    {"name": "新洲区", "lat": 30.8422, "lng": 114.8011},
]

LABEL_STYLES: Dict[str, Dict[str, Any]] = {
    "city":     {"fontSize": 18, "color": "#000000", "font": "song", "weight": 3, "offset": [0, 0]},
    "district": {"fontSize": 15, "color": "#000000", "font": "song", "weight": 3, "offset": [0, 0]},
    "town":     {"fontSize": 12, "color": "#000000", "font": "song", "weight": 2, "offset": [0, 0]},
    "water":    {"fontSize": 12, "color": "#2E6FA3", "font": "song", "weight": 2, "offset": [0, -10]},
    "landmark": {"fontSize": 13, "color": "#0f3d91", "font": "bold", "weight": 3, "offset": [0, 0]},
    "poi":      {"fontSize": 11, "color": "#475569", "font": "normal", "weight": 2, "offset": [0, 0]},
}

# ========== 重点建筑百科知识库（点击地标时显示简介与图片） ==========
POI_ENCYCLOPEDIA = {
    "黄鹤楼": {"简介": "黄鹤楼位于湖北省武汉市长江南岸的蛇山之巅，与湖南岳阳楼、江西滕王阁并称江南三大名楼。始建于三国时期，因唐代诗人崔颢题《黄鹤楼》诗而名扬天下，素有“天下江山第一楼”之美誉。", "图片": ""},
    "武汉大学": {"简介": "武汉大学是国家教育部直属重点综合性大学，国家“双一流”建设高校，溯源于1893年创办的自强学堂。校园环绕东湖水，坐拥珞珈山，中西合璧的宫殿式建筑群古朴典雅，被誉为“中国最美丽的大学”之一。", "图片": ""},
    "华中科技大学": {"简介": "华中科技大学是国家教育部直属重点综合性大学，国家“双一流”建设高校，由原华中理工大学、同济医科大学、武汉城市建设学院于2000年合并组建，光电、机械、医学等学科实力雄厚。", "图片": ""},
    "湖北省博物馆": {"简介": "湖北省博物馆是湖北省规模最大的综合性博物馆，馆藏文物20余万件，以越王勾践剑、曾侯乙编钟等国宝级文物闻名于世，是了解荆楚文化的重要窗口。", "图片": ""},
    "东湖": {"简介": "东湖位于武汉市武昌区东部，是中国第二大城中湖，水域面积约33平方公里。东湖绿道全长约100公里，环湖串联磨山、落雁岛等景区，是武汉市民休闲健身的城市绿心。", "图片": ""},
    "户部巷": {"简介": "户部巷位于武汉市武昌区，是一条有150多年历史的特色小吃街，全长约150米，汇聚热干面、豆皮、面窝等武汉名小吃，有“汉味小吃第一巷”之称。", "图片": ""},
    "江汉路": {"简介": "江汉路步行街位于武汉市汉口，全长1600米，是百年商业老街。街道两旁保留欧陆与民国风格历史建筑，与江汉关钟楼相呼应，是武汉最繁华的商业中心。", "图片": ""},
    "武汉长江大桥": {"简介": "武汉长江大桥是新中国成立后在长江上修建的第一座公铁两用大桥，1957年10月建成通车，全长1670米，上层公路下层铁路，与黄鹤楼共同构成武汉城市地标。", "图片": ""},
    "光谷广场": {"简介": "光谷广场位于武汉市洪山区，是武汉东湖新技术开发区（中国光谷）的核心地标，“星河”雕塑与环形通道交相辉映，是武汉创新活力的象征。", "图片": ""},
    "归元寺": {"简介": "归元寺位于武汉市汉阳区，始建于清顺治十五年（1658年），是武汉著名的佛教丛林，寺内五百罗汉堂供奉五百罗汉塑像，香火鼎盛。", "图片": ""},
    "古琴台": {"简介": "古琴台又名伯牙台，位于武汉市汉阳区月湖之滨，为纪念俞伯牙、钟子期“高山流水遇知音”的千古佳话而建，与黄鹤楼、晴川阁并称武汉三大名胜。", "图片": ""},
    "晴川阁": {"简介": "晴川阁位于武汉市汉阳区龟山东麓，始建于明代嘉靖年间，因崔颢“晴川历历汉阳树”诗句得名，与黄鹤楼隔江相望，是武汉著名古建筑。", "图片": ""},
    "武汉天地": {"简介": "武汉天地是位于汉口江岸区的商业综合体，由老租界洋房街区改造而成，融合历史建筑与现代商业，是武汉新晋的时尚地标。", "图片": ""},
    "楚河汉街": {"简介": "楚河汉街位于武汉市武昌区东湖与沙湖之间，全长约1.5公里，兼具楚汉建筑风格与现代商业，被誉为“现代版清明上河图”。", "图片": ""},
    "昙华林": {"简介": "昙华林是武昌老城区的一条历史文化街区，保留了大量近代历史建筑与文艺小店，是武汉的文艺打卡地，体现武汉近现代中西文化交融的城市记忆。", "图片": ""},
}

# ========== 武汉地标数据 ==========
WUHAN_LANDMARKS: List[Dict[str, Any]] = [
    {"name": "武汉大学", "lat": 30.5408, "lng": 114.3645, "type": "university"},
    {"name": "华中科技大学", "lat": 30.5135, "lng": 114.4175, "type": "university"},
    {"name": "黄鹤楼", "lat": 30.5443, "lng": 114.2961, "type": "attraction"},
    {"name": "东湖", "lat": 30.5561, "lng": 114.3896, "type": "scenic"},
    {"name": "湖北省博物馆", "lat": 30.5656, "lng": 114.3631, "type": "museum"},
    {"name": "户部巷", "lat": 30.5456, "lng": 114.2989, "type": "food"},
    {"name": "江汉路", "lat": 30.5873, "lng": 114.2917, "type": "commercial"},
    {"name": "光谷广场", "lat": 30.5083, "lng": 114.3975, "type": "commercial"},
    {"name": "武汉长江大桥", "lat": 30.5492, "lng": 114.2981, "type": "landmark"},
    {"name": "古琴台", "lat": 30.5536, "lng": 114.2658, "type": "attraction"},
    {"name": "晴川阁", "lat": 30.5667, "lng": 114.2806, "type": "attraction"},
    {"name": "归元寺", "lat": 30.5458, "lng": 114.2689, "type": "attraction"},
    {"name": "武汉天地", "lat": 30.6075, "lng": 114.3167, "type": "commercial"},
    {"name": "楚河汉街", "lat": 30.5667, "lng": 114.3333, "type": "commercial"},
    {"name": "昙华林", "lat": 30.5583, "lng": 114.3167, "type": "cultural"},
]

# ========== 地图底图主题 ==========
MAP_THEMES: Dict[str, Dict[str, str]] = {
    "standard": {"name": "标准地图", "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                 "attribution": "&copy; OpenStreetMap"},
    "positron": {"name": "浅色地图", "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                 "attribution": "&copy; CARTO"},
    "dark": {"name": "深色地图", "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
             "attribution": "&copy; CARTO"},
    "satellite": {"name": "卫星地图", "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                  "attribution": "&copy; Esri"},
    # 中文底图
    "amap_normal": {"name": "高德地图", "url": "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", "attribution": "&copy; 高德地图", "subdomains": "1234", "maxZoom": 20},
    "amap_satellite": {"name": "高德卫星", "url": "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}", "attribution": "&copy; 高德地图", "subdomains": "1234", "maxZoom": 20},
    "tianditu_vec": {"name": "天地图矢量", "url": "https://t{s}.tianditu.gov.cn/DataServer?T=vec_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", "attribution": "&copy; 天地图", "subdomains": "01234567", "maxZoom": 18},
    "tianditu_img": {"name": "天地图影像", "url": "https://t{s}.tianditu.gov.cn/DataServer?T=img_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", "attribution": "&copy; 天地图", "subdomains": "01234567", "maxZoom": 18},
    "tianditu_cva": {"name": "天地图标注", "url": "https://t{s}.tianditu.gov.cn/DataServer?T=cva_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", "attribution": "&copy; 天地图", "subdomains": "01234567", "maxZoom": 18},
    "tencent_normal": {"name": "腾讯地图", "url": "https://rt{s}.map.gtimg.com/realtimerender?z={z}&x={x}&y={-y}&type=vector&style=0", "attribution": "&copy; 腾讯地图", "subdomains": "0123", "maxZoom": 20},
    "esri_street_cn": {"name": "Esri中文街道", "url": "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", "attribution": "&copy; Esri", "maxZoom": 19},
}

# ========== 专题地图渲染配置 ==========
THEMATIC_MAP_CONFIG: Dict[str, Dict[str, Any]] = {
    "population": {"name": "人口密度图", "render_type": "choropleth", "color_scheme": ["#fff7ec", "#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#ef6548", "#d7301f", "#990000"], "description": "展示人口空间分布密度", "unit": "人/km²", "legend_title": "人口密度"},
    "economic": {"name": "经济分布图", "render_type": "proportional_symbol", "color_scheme": ["#ffffcc", "#d9f0a3", "#addd8e", "#78c679", "#31a354", "#006837"], "description": "展示经济活动空间分布", "unit": "亿元", "legend_title": "GDP规模"},
    "landuse": {"name": "土地利用图", "render_type": "categorical", "color_scheme": {"residential": "#ffd699", "commercial": "#f97316", "industrial": "#9ca3af", "farmland": "#84cc16", "forest": "#16a34a", "water": "#3b82f6", "grass": "#86efac", "other": "#e7e5e4"}, "description": "展示城市土地利用类型分布", "legend_title": "用地类型"},
    "climate": {"name": "气候分布图", "render_type": "graduated", "color_scheme": ["#f1eef6", "#d4b9da", "#c994c7", "#df65b0", "#dd1c77", "#980043"], "description": "展示气候要素空间分布", "unit": "°C", "legend_title": "年均气温"},
    "healthcare": {"name": "医疗资源图", "render_type": "proportional_symbol", "color_scheme": ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"], "description": "展示医疗机构空间分布", "legend_title": "医疗设施"},
    "education": {"name": "教育设施图", "render_type": "categorical", "color_scheme": {"university": "#7c3aed", "college": "#8b5cf6", "school": "#a78bfa", "kindergarten": "#c4b5fd", "library": "#5b21b6"}, "description": "展示教育机构空间分布", "legend_title": "教育类型"},
    "commercial": {"name": "商业分布图", "render_type": "heatmap", "color_scheme": ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026"], "description": "展示商业活动热力分布", "legend_title": "商业热度"},
    "greenery": {"name": "绿化覆盖图", "render_type": "choropleth", "color_scheme": ["#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476", "#41ab5d", "#238b45", "#005a32"], "description": "展示城市绿化覆盖分布", "unit": "%", "legend_title": "绿化率"},
    "heatmap": {"name": "热力分布图", "render_type": "heatmap", "color_scheme": ["#000004", "#320a5e", "#781c6d", "#bb3754", "#ed6925", "#fcbf49", "#fcffa4"], "description": "综合热力分布图", "legend_title": "密度"},
    "terrain": {"name": "地形图（等高线）", "render_type": "contour", "color_scheme": {"index": "#7A5230", "minor": "#C8A268"}, "description": "基于SRTM 30m DEM生成等高线，叠加水系与行政边界", "legend_title": "等高线（米）"},
}

# ========== 兴趣点(POI)象形符号分类（点状要素整套象形标识）==========
# 分类与高德/百度地图POI体系对应，每个分类使用专属象形符号(icon)与配色
POI_STYLES: Dict[str, Dict[str, Any]] = {
    # ===== 餐饮美食 =====
    "restaurant":  {"name": "餐厅",   "group": "餐饮美食", "color": "#e11d48", "icon": "🍜", "radius": 7, "iconClass": "fa-utensils"},
    "cafe":        {"name": "咖啡厅", "group": "餐饮美食", "color": "#92400e", "icon": "☕", "radius": 6, "iconClass": "fa-mug-hot"},
    "fast_food":   {"name": "快餐",   "group": "餐饮美食", "color": "#ea580c", "icon": "🍔", "radius": 6, "iconClass": "fa-burger"},
    "bar":         {"name": "酒吧",   "group": "餐饮美食", "color": "#7c3aed", "icon": "🍺", "radius": 6, "iconClass": "fa-martini-glass-citrus"},
    "pub":         {"name": "小酒馆", "group": "餐饮美食", "color": "#6d28d9", "icon": "🍻", "radius": 6, "iconClass": "fa-beer-mug-empty"},
    "marketplace": {"name": "集市",   "group": "餐饮美食", "color": "#d97706", "icon": "🥬", "radius": 7, "iconClass": "fa-store"},
    # ===== 购物消费 =====
    "supermarket": {"name": "超市",   "group": "购物消费", "color": "#0284c7", "icon": "🛒", "radius": 7, "iconClass": "fa-cart-shopping"},
    "mall":        {"name": "商场",   "group": "购物消费", "color": "#db2777", "icon": "🛍️", "radius": 8, "iconClass": "fa-bag-shopping"},
    "convenience": {"name": "便利店", "group": "购物消费", "color": "#0891b2", "icon": "🏪", "radius": 6, "iconClass": "fa-shop"},
    "department_store": {"name": "百货商场", "group": "购物消费", "color": "#be185d", "icon": "🏬", "radius": 7, "iconClass": "fa-store"},
    "shop":        {"name": "商店",   "group": "购物消费", "color": "#0d9488", "icon": "🛍️", "radius": 6, "iconClass": "fa-tag"},
    # ===== 医疗健康 =====
    "hospital":    {"name": "医院",   "group": "医疗健康", "color": "#dc2626", "icon": "🏥", "radius": 8, "iconClass": "fa-hospital"},
    "clinic":      {"name": "诊所",   "group": "医疗健康", "color": "#f43f5e", "icon": "💊", "radius": 6, "iconClass": "fa-stethoscope"},
    "pharmacy":    {"name": "药店",   "group": "医疗健康", "color": "#16a34a", "icon": "💊", "radius": 6, "iconClass": "fa-pills"},
    # ===== 教育培训 =====
    "school":      {"name": "学校",   "group": "教育培训", "color": "#2563eb", "icon": "🏫", "radius": 7, "iconClass": "fa-school"},
    "university":  {"name": "大学",   "group": "教育培训", "color": "#4f46e5", "icon": "🎓", "radius": 8, "iconClass": "fa-graduation-cap"},
    "kindergarten":{"name": "幼儿园", "group": "教育培训", "color": "#7c3aed", "icon": "🧸", "radius": 6, "iconClass": "fa-child-reaching"},
    "library":     {"name": "图书馆", "group": "教育培训", "color": "#9333ea", "icon": "📚", "radius": 6, "iconClass": "fa-book-open"},
    # ===== 交通出行 =====
    "transport":   {"name": "交通枢纽", "group": "交通出行", "color": "#0ea5e9", "icon": "🚉", "radius": 8, "iconClass": "fa-train-subway"},
    "bus":         {"name": "公交站", "group": "交通出行", "color": "#06b6d4", "icon": "🚌", "radius": 7, "iconClass": "fa-bus"},
    "subway":      {"name": "地铁站", "group": "交通出行", "color": "#6366f1", "icon": "🚇", "radius": 7, "iconClass": "fa-train-subway"},
    "parking":     {"name": "停车场", "group": "交通出行", "color": "#475569", "icon": "🅿️", "radius": 6, "iconClass": "fa-square-parking"},
    "fuel":        {"name": "加油站", "group": "交通出行", "color": "#f59e0b", "icon": "⛽", "radius": 6, "iconClass": "fa-gas-pump"},
    # ===== 住宿酒店 =====
    "hotel":       {"name": "酒店",   "group": "住宿酒店", "color": "#be185d", "icon": "🏨", "radius": 7, "iconClass": "fa-hotel"},
    "hostel":      {"name": "青旅",   "group": "住宿酒店", "color": "#9d174d", "icon": "🎒", "radius": 6, "iconClass": "fa-backpack"},
    # ===== 旅游景点 =====
    "attraction":  {"name": "景点",   "group": "旅游景点", "color": "#059669", "icon": "🏞️", "radius": 8, "iconClass": "fa-camera-retro"},
    "museum":      {"name": "博物馆", "group": "旅游景点", "color": "#dc2626", "icon": "🏛️", "radius": 7, "iconClass": "fa-landmark"},
    "historic":    {"name": "历史遗迹", "group": "旅游景点", "color": "#7c3aed", "icon": "🗿", "radius": 7, "iconClass": "fa-monument"},
    "scenic":      {"name": "风景名胜", "group": "旅游景点", "color": "#0d9488", "icon": "🏔️", "radius": 8, "iconClass": "fa-mountain-sun"},
    # ===== 休闲娱乐 =====
    "park":        {"name": "公园",   "group": "休闲娱乐", "color": "#16a34a", "icon": "🌳", "radius": 7, "iconClass": "fa-tree"},
    "garden":      {"name": "花园",   "group": "休闲娱乐", "color": "#65a30d", "icon": "🌷", "radius": 6, "iconClass": "fa-seedling"},
    "theatre":     {"name": "剧院",   "group": "休闲娱乐", "color": "#c026d3", "icon": "🎭", "radius": 7, "iconClass": "fa-masks-theater"},
    "cinema":      {"name": "影院",   "group": "休闲娱乐", "color": "#a21caf", "icon": "🎬", "radius": 6, "iconClass": "fa-film"},
    "sports":      {"name": "体育场馆", "group": "休闲娱乐", "color": "#15803d", "icon": "⚽", "radius": 7, "iconClass": "fa-futbol"},
    "gym":         {"name": "健身房", "group": "休闲娱乐", "color": "#166534", "icon": "🏋️", "radius": 6, "iconClass": "fa-dumbbell"},
    # ===== 金融商务 =====
    "bank":        {"name": "银行",   "group": "金融商务", "color": "#b45309", "icon": "🏦", "radius": 7, "iconClass": "fa-building-columns"},
    "atm":         {"name": "ATM",   "group": "金融商务", "color": "#d97706", "icon": "💳", "radius": 6, "iconClass": "fa-credit-card"},
    "office":      {"name": "写字楼", "group": "金融商务", "color": "#64748b", "icon": "🏢", "radius": 6, "iconClass": "fa-building"},
    # ===== 公共服务 =====
    "government":  {"name": "政府机构", "group": "公共服务", "color": "#334155", "icon": "🏛️", "radius": 7, "iconClass": "fa-building-flag"},
    "police":      {"name": "警察局", "group": "公共服务", "color": "#1d4ed8", "icon": "👮", "radius": 7, "iconClass": "fa-shield-halved"},
    "fire":        {"name": "消防站", "group": "公共服务", "color": "#dc2626", "icon": "🚒", "radius": 7, "iconClass": "fa-fire-extinguisher"},
    "post":        {"name": "邮局",   "group": "公共服务", "color": "#b45309", "icon": "📮", "radius": 6, "iconClass": "fa-envelope-open-text"},
    "toilet":      {"name": "卫生间", "group": "公共服务", "color": "#0ea5e9", "icon": "🚻", "radius": 5, "iconClass": "fa-restroom"},
    "place_of_worship": {"name": "宗教场所", "group": "公共服务", "color": "#ca8a04", "icon": "⛩️", "radius": 6, "iconClass": "fa-place-of-worship"},
    "default":     {"name": "其他地点", "group": "其他", "color": "#64748b", "icon": "📍", "radius": 6, "iconClass": "fa-location-dot"},
}

# ========== 建筑物分类样式（面状要素）==========
BUILDING_STYLES: Dict[str, Dict[str, Any]] = {
    "residential":    {"name": "住宅建筑",   "fillColor": "#ffe8b3", "color": "#c98a1e", "fillOpacity": 0.35, "weight": 0.5},
    "house":          {"name": "独栋住宅",   "fillColor": "#fde68a", "color": "#d97706", "fillOpacity": 0.35, "weight": 0.5},
    "apartments":     {"name": "公寓",       "fillColor": "#fcd34d", "color": "#b45309", "fillOpacity": 0.4, "weight": 0.5},
    "dormitory":      {"name": "宿舍",       "fillColor": "#fef9c3", "color": "#ca8a04", "fillOpacity": 0.4, "weight": 0.5},
    "commercial":     {"name": "商业建筑",   "fillColor": "#fca5a5", "color": "#dc2626", "fillOpacity": 0.5, "weight": 0.5},
    "retail":         {"name": "零售商业",   "fillColor": "#fdba74", "color": "#ea580c", "fillOpacity": 0.5, "weight": 0.5},
    "hotel":          {"name": "酒店宾馆",   "fillColor": "#fbcfe8", "color": "#be185d", "fillOpacity": 0.5, "weight": 0.5},
    "industrial":     {"name": "工业建筑",   "fillColor": "#d1d5db", "color": "#6b7280", "fillOpacity": 0.4, "weight": 0.5},
    "public":         {"name": "公共建筑",   "fillColor": "#bfdbfe", "color": "#2563eb", "fillOpacity": 0.55, "weight": 0.5},
    "government":     {"name": "政府机构",   "fillColor": "#a5b4fc", "color": "#4f46e5", "fillOpacity": 0.6, "weight": 0.5},
    "school":         {"name": "学校建筑",   "fillColor": "#e9d5ff", "color": "#9333ea", "fillOpacity": 0.5, "weight": 0.5},
    "university":     {"name": "大学建筑",   "fillColor": "#ddd6fe", "color": "#7c3aed", "fillOpacity": 0.45, "weight": 0.5},
    "hospital":       {"name": "医院建筑",   "fillColor": "#fecaca", "color": "#b91c1c", "fillOpacity": 0.6, "weight": 0.5},
    "religious":      {"name": "宗教建筑",   "fillColor": "#fef3c7", "color": "#a16207", "fillOpacity": 0.55, "weight": 0.5},
    "civic":          {"name": "文化场馆",   "fillColor": "#a5f3fc", "color": "#0891b2", "fillOpacity": 0.5, "weight": 0.5},
    "sports":         {"name": "体育场馆",   "fillColor": "#bbf7d0", "color": "#15803d", "fillOpacity": 0.45, "weight": 0.5},
    "parking":        {"name": "停车设施",   "fillColor": "#e5e7eb", "color": "#9ca3af", "fillOpacity": 0.3, "weight": 0.3},
    "garage":         {"name": "车库",       "fillColor": "#e5e7eb", "color": "#6b7280", "fillOpacity": 0.3, "weight": 0.3},
    "warehouse":      {"name": "仓储建筑",   "fillColor": "#d1d5db", "color": "#4b5563", "fillOpacity": 0.35, "weight": 0.5},
    "train_station":  {"name": "交通枢纽",   "fillColor": "#fecdd3", "color": "#be123c", "fillOpacity": 0.55, "weight": 0.5},
    "farm":           {"name": "农业建筑",   "fillColor": "#d9f99d", "color": "#4d7c0f", "fillOpacity": 0.35, "weight": 0.5},
    "greenhouse":     {"name": "温室大棚",   "fillColor": "#ecfccb", "color": "#65a30d", "fillOpacity": 0.3, "weight": 0.5},
    "default":        {"name": "其他建筑",   "fillColor": "#e7e5e4", "color": "#a8a29e", "fillOpacity": 0.3, "weight": 0.5},
}

# ========== 道路分级样式（线状要素双层渲染）==========
ROAD_CLASSIFICATION: Dict[str, Dict[str, Any]] = {
    "motorway": {
        "name": "高速公路", "level": 1,
        "outer": {"color": "#c0392b", "weight": 6, "opacity": 0.9},
        "inner": {"color": "#f6cbc3", "weight": 3.5, "opacity": 1.0},
    },
    "trunk": {
        "name": "国道/主干道", "level": 2,
        "outer": {"color": "#d97b1f", "weight": 5, "opacity": 0.9},
        "inner": {"color": "#fce3c2", "weight": 3, "opacity": 1.0},
    },
    "primary": {
        "name": "省道/主要道路", "level": 3,
        "outer": {"color": "#d9a52e", "weight": 4.5, "opacity": 0.9},
        "inner": {"color": "#fdf0c9", "weight": 2.8, "opacity": 1.0},
    },
    "secondary": {
        "name": "次干道", "level": 4,
        "outer": {"color": "#e8c34d", "weight": 3.5, "opacity": 0.85},
        "inner": {"color": "#fdf6d8", "weight": 2.2, "opacity": 1.0},
    },
    "tertiary": {
        "name": "支路", "level": 5,
        "outer": {"color": "#c9c9c9", "weight": 2.5, "opacity": 0.85},
        "inner": {"color": "#ffffff", "weight": 1.6, "opacity": 1.0},
    },
    "residential": {
        "name": "社区道路", "level": 6,
        "color": "#cfcfcf", "weight": 2, "opacity": 0.75,
    },
    "service": {
        "name": "服务道路", "level": 7,
        "color": "#d6d6d6", "weight": 1.5, "opacity": 0.6,
    },
    "default": {
        "name": "其他道路", "level": 8,
        "color": "#a8a8a8", "weight": 1.5, "opacity": 0.6,
    },
}

# ========== 铁路分级样式 ==========
RAILWAY_CLASSIFICATION: Dict[str, Dict[str, Any]] = {
    "rail": {
        "name": "普通铁路",
        "outer": {"color": "#52525b", "weight": 3, "opacity": 0.9},
        "inner": {"color": "#ffffff", "weight": 1.5, "opacity": 1.0, "dashArray": "6,4"},
    },
    "subway": {
        "name": "地铁",
        "color": "#6366f1", "weight": 2.5, "opacity": 0.8, "dashArray": "4,3",
    },
    "light_rail": {
        "name": "轻轨",
        "color": "#06b6d4", "weight": 2.5, "opacity": 0.8, "dashArray": "4,3",
    },
    "high_speed": {
        "name": "高速铁路",
        "outer": {"color": "#f97316", "weight": 3.5, "opacity": 0.9},
        "inner": {"color": "#ffffff", "weight": 1.5, "opacity": 1.0, "dashArray": "8,5"},
    },
    "default": {
        "name": "其他铁路",
        "color": "#52525b", "weight": 2, "opacity": 0.7, "dashArray": "5,3",
    },
}

# ========== 旅游地分类样式（点状要素分类表示）==========
TOURISM_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "historic": {
        "name": "历史遗迹", "color": "#7c3aed", "fillColor": "#c4b5fd",
        "icon": "🏛️", "radius": 8, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-monument"},
    "attraction": {
        "name": "自然景观", "color": "#059669", "fillColor": "#6ee7b7",
        "icon": "🌿", "radius": 7, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-camera-retro"},
    "museum": {
        "name": "博物馆", "color": "#dc2626", "fillColor": "#fca5a5",
        "icon": "🎭", "radius": 7, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-landmark"},
    "cultural": {
        "name": "文化设施", "color": "#c026d3", "fillColor": "#f0abfc",
        "icon": "🎨", "radius": 6, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-palette"},
    "scenic": {
        "name": "风景名胜", "color": "#0d9488", "fillColor": "#5eead4",
        "icon": "🏔️", "radius": 8, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-mountain-sun"},
    "commercial": {
        "name": "商业景点", "color": "#ea580c", "fillColor": "#fdba74",
        "icon": "🛍️", "radius": 6, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-bag-shopping"},
    "university": {
        "name": "高校学府", "color": "#2563eb", "fillColor": "#93c5fd",
        "icon": "🎓", "radius": 7, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-graduation-cap"},
    "food": {
        "name": "美食地标", "color": "#e11d48", "fillColor": "#fda4af",
        "icon": "🍜", "radius": 5, "fillOpacity": 0.7, "weight": 1.5, "iconClass": "fa-utensils"},
    "landmark": {
        "name": "城市地标", "color": "#f59e0b", "fillColor": "#fcd34d",
        "icon": "⭐", "radius": 8, "fillOpacity": 0.8, "weight": 2, "iconClass": "fa-star"},
    "religious": {
        "name": "宗教场所", "color": "#ca8a04", "fillColor": "#fef08a",
        "icon": "⛩️", "radius": 6, "fillOpacity": 0.7, "weight": 2, "iconClass": "fa-place-of-worship"},
    "park": {
        "name": "公园绿地", "color": "#16a34a", "fillColor": "#86efac",
        "icon": "🌳", "radius": 6, "fillOpacity": 0.6, "weight": 1.5, "iconClass": "fa-tree"},
    "default": {
        "name": "其他地点", "color": "#64748b", "fillColor": "#cbd5e1",
        "icon": "📍", "radius": 5, "fillOpacity": 0.6, "weight": 1, "iconClass": "fa-location-dot"},
}

# ========== 水系分类样式 ==========
WATERWAY_STYLES: Dict[str, Dict[str, Any]] = {
    "river":     {"name": "河流",   "color": "#1e90ff", "weight": 4, "opacity": 0.8, "fillColor": "#1e90ff", "fillOpacity": 0.4},
    "stream":    {"name": "溪流",   "color": "#38bdf8", "weight": 2, "opacity": 0.7},
    "canal":     {"name": "运河",   "color": "#0284c7", "weight": 3, "opacity": 0.8},
    "lake":      {"name": "湖泊",   "fillColor": "#1e90ff", "color": "#1e90ff", "fillOpacity": 0.5, "weight": 1.2, "opacity": 0.8},
    "reservoir": {"name": "水库",   "fillColor": "#1e90ff", "color": "#1e90ff", "fillOpacity": 0.5, "weight": 1.2, "opacity": 0.8},
    "default":   {"name": "其他水系", "color": "#7dd3fc", "weight": 2, "opacity": 0.7},
}
# ========== 水系要素成套符号（统一蓝色；河源/汇入口/入湖口/入海口）==========
WATER_SYMBOL_STYLES: Dict[str, Dict[str, Any]] = {
    "spring":      {"name": "河源",   "kind": "spring",     "color": "#1e90ff", "fillColor": "#bae6fd", "fillOpacity": 0.95, "weight": 2, "radius": 5, "icon": "💧", "iconClass": "fa-droplet"},
    "confluence":  {"name": "汇入口", "kind": "confluence", "color": "#1e90ff", "fillColor": "#7dd3fc", "fillOpacity": 0.95, "weight": 2.5, "radius": 6, "icon": "🌊", "iconClass": "fa-water"},
    "to_lake":     {"name": "入湖口", "kind": "to_lake",    "color": "#1e90ff", "fillColor": "#bae6fd", "fillOpacity": 0.95, "weight": 2.5, "radius": 6, "icon": "🌊", "iconClass": "fa-water"},
    "to_sea":      {"name": "入海口", "kind": "to_sea",     "color": "#0284c7", "fillColor": "#bae6fd", "fillOpacity": 0.95, "weight": 2.5, "radius": 6, "icon": "🌊", "iconClass": "fa-water"},
}






# ========== 绿地分类样式 ==========
GREENSPACE_STYLES: Dict[str, Dict[str, Any]] = {
    "park":      {"name": "公园",       "fillColor": "#86efac", "color": "#16a34a", "fillOpacity": 0.4, "weight": 0.5},
    "garden":    {"name": "花园",       "fillColor": "#bbf7d0", "color": "#15803d", "fillOpacity": 0.4, "weight": 0.5},
    "forest":    {"name": "森林",       "fillColor": "#16a34a", "color": "#14532d", "fillOpacity": 0.5, "weight": 0.5},
    "grass":     {"name": "草地",       "fillColor": "#d9f99d", "color": "#65a30d", "fillOpacity": 0.35, "weight": 0.3},
    "meadow":    {"name": "草甸",       "fillColor": "#bef264", "color": "#4d7c0f", "fillOpacity": 0.35, "weight": 0.3},
    "default":   {"name": "其他绿地",   "fillColor": "#bbf7d0", "color": "#22c55e", "fillOpacity": 0.3, "weight": 0.5},
}

# ========== 土地利用分类样式（面状要素）==========
LANDUSE_STYLES: Dict[str, Dict[str, Any]] = {
    "residential":    {"name": "居住用地",   "fillColor": "#fde68a", "color": "#d97706", "fillOpacity": 0.4, "weight": 0.5},
    "commercial":     {"name": "商业用地",   "fillColor": "#fca5a5", "color": "#dc2626", "fillOpacity": 0.4, "weight": 0.5},
    "industrial":     {"name": "工业用地",   "fillColor": "#d1d5db", "color": "#6b7280", "fillOpacity": 0.4, "weight": 0.5},
    "retail":         {"name": "零售用地",   "fillColor": "#fed7aa", "color": "#ea580c", "fillOpacity": 0.4, "weight": 0.5},
    "farmland":       {"name": "农业用地",   "fillColor": "#bef264", "color": "#4d7c0f", "fillOpacity": 0.4, "weight": 0.5},
    "farmyard":       {"name": "农家院落",   "fillColor": "#fef3c7", "color": "#a16207", "fillOpacity": 0.35, "weight": 0.5},
    "cemetery":       {"name": "墓地",       "fillColor": "#d1fae5", "color": "#059669", "fillOpacity": 0.4, "weight": 0.5},
    "construction":   {"name": "在建用地",   "fillColor": "#fecaca", "color": "#b91c1c", "fillOpacity": 0.3, "weight": 0.5},
    "military":       {"name": "军事用地",   "fillColor": "#e0e7ff", "color": "#4338ca", "fillOpacity": 0.4, "weight": 0.5},
    "quarry":         {"name": "采石场",     "fillColor": "#e7e5e4", "color": "#78716c", "fillOpacity": 0.4, "weight": 0.5},
    "landfill":       {"name": "垃圾填埋场", "fillColor": "#d6d3d1", "color": "#57534e", "fillOpacity": 0.4, "weight": 0.5},
    "brownfield":     {"name": "棕地",       "fillColor": "#f5f5f4", "color": "#a8a29e", "fillOpacity": 0.35, "weight": 0.5},
    "default":        {"name": "其他用地",   "fillColor": "#e7e5e4", "color": "#a8a29e", "fillOpacity": 0.3, "weight": 0.5},
}

# ========== 图例配置模板 ==========
LEGEND_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "traffic": {
        "title": "交通图图例",
        "items": [
            {"label": "高速公路",   "type": "line", "color": "#c0392b", "weight": 6, "group": "道路分级"},
            {"label": "国道/主干道", "type": "line", "color": "#d97b1f", "weight": 5, "group": "道路分级"},
            {"label": "省道/主要道路", "type": "line", "color": "#d9a52e", "weight": 4.5, "group": "道路分级"},
            {"label": "次干道",     "type": "line", "color": "#e8c34d", "weight": 3.5, "group": "道路分级"},
            {"label": "支路",       "type": "line", "color": "#c9c9c9", "weight": 2.5, "group": "道路分级"},
            {"label": "社区道路",   "type": "line", "color": "#cfcfcf", "weight": 2, "group": "道路分级"},
            {"label": "普通铁路",   "type": "line", "color": "#52525b", "weight": 3, "dashArray": "6,4", "group": "铁路"},
            {"label": "高速铁路",   "type": "line", "color": "#f97316", "weight": 3.5, "dashArray": "8,5", "group": "铁路"},
            {"label": "地铁",       "type": "line", "color": "#6366f1", "weight": 2.5, "dashArray": "4,3", "group": "铁路"},
        ],
    },
    "tourism": {
        "title": "旅游图图例",
        "items": [
            {"label": "历史遗迹",   "type": "point", "color": "#7c3aed", "icon": "🏛️", "group": "旅游景点"},
            {"label": "自然景观",   "type": "point", "color": "#059669", "icon": "🌿", "group": "旅游景点"},
            {"label": "博物馆",     "type": "point", "color": "#dc2626", "icon": "🎭", "group": "旅游景点"},
            {"label": "文化设施",   "type": "point", "color": "#c026d3", "icon": "🎨", "group": "旅游景点"},
            {"label": "风景名胜",   "type": "point", "color": "#0d9488", "icon": "🏔️", "group": "旅游景点"},
            {"label": "商业景点",   "type": "point", "color": "#ea580c", "icon": "🛍️", "group": "旅游景点"},
            {"label": "高校学府",   "type": "point", "color": "#2563eb", "icon": "🎓", "group": "教育培训"},
            {"label": "美食地标",   "type": "point", "color": "#e11d48", "icon": "🍜", "group": "餐饮美食"},
            {"label": "城市地标",   "type": "point", "color": "#f59e0b", "icon": "⭐", "group": "旅游景点"},
            {"label": "宗教场所",   "type": "point", "color": "#ca8a04", "icon": "⛩️", "group": "旅游景点"},
            {"label": "公园绿地",   "type": "point", "color": "#16a34a", "icon": "🌳", "group": "休闲娱乐"},
        ],
    },
    "basic": {
        "title": "基础地图图例",
        "items": [
            {"label": "高速公路",   "type": "line", "color": "#c0392b", "weight": 6, "group": "道路分级"},
            {"label": "国道/主干道", "type": "line", "color": "#d97b1f", "weight": 5, "group": "道路分级"},
            {"label": "省道/主要道路", "type": "line", "color": "#d9a52e", "weight": 4.5, "group": "道路分级"},
            {"label": "次干道",     "type": "line", "color": "#e8c34d", "weight": 3.5, "group": "道路分级"},
            {"label": "支路",       "type": "line", "color": "#c9c9c9", "weight": 2.5, "group": "道路分级"},
            {"label": "社区道路",   "type": "line", "color": "#cfcfcf", "weight": 2, "group": "道路分级"},
            {"label": "普通铁路",   "type": "line", "color": "#52525b", "weight": 3, "dashArray": "6,4", "group": "铁路"},
            {"label": "高速铁路",   "type": "line", "color": "#f97316", "weight": 3.5, "dashArray": "8,5", "group": "铁路"},
            {"label": "地铁",       "type": "line", "color": "#6366f1", "weight": 2.5, "dashArray": "4,3", "group": "铁路"},
            {"label": "河流",       "type": "line", "color": "#0ea5e9", "weight": 4, "group": "水系"},
            {"label": "湖泊",       "type": "polygon", "fillColor": "#7dd3fc", "color": "#0ea5e9", "fillOpacity": 0.4, "group": "水系"},
            {"label": "公园",       "type": "polygon", "fillColor": "#86efac", "color": "#16a34a", "fillOpacity": 0.4, "group": "绿地"},
            {"label": "森林",       "type": "polygon", "fillColor": "#16a34a", "color": "#14532d", "fillOpacity": 0.5, "group": "绿地"},
            {"label": "草地",       "type": "polygon", "fillColor": "#d9f99d", "color": "#65a30d", "fillOpacity": 0.35, "group": "绿地"},
            {"label": "住宅建筑",   "type": "polygon", "fillColor": "#ffe8b3", "color": "#c98a1e", "fillOpacity": 0.35, "group": "建筑物"},
            {"label": "公寓",       "type": "polygon", "fillColor": "#fcd34d", "color": "#b45309", "fillOpacity": 0.4, "group": "建筑物"},
            {"label": "商业建筑",   "type": "polygon", "fillColor": "#fca5a5", "color": "#dc2626", "fillOpacity": 0.5, "group": "建筑物"},
            {"label": "工业建筑",   "type": "polygon", "fillColor": "#d1d5db", "color": "#6b7280", "fillOpacity": 0.4, "group": "建筑物"},
            {"label": "公共建筑",   "type": "polygon", "fillColor": "#bfdbfe", "color": "#2563eb", "fillOpacity": 0.55, "group": "建筑物"},
            {"label": "学校建筑",   "type": "polygon", "fillColor": "#e9d5ff", "color": "#9333ea", "fillOpacity": 0.5, "group": "建筑物"},
            {"label": "医院建筑",   "type": "polygon", "fillColor": "#fecaca", "color": "#b91c1c", "fillOpacity": 0.6, "group": "建筑物"},
            {"label": "餐厅",       "type": "point", "color": "#e11d48", "icon": "🍜", "group": "兴趣点(POI)"},
            {"label": "咖啡厅",     "type": "point", "color": "#92400e", "icon": "☕", "group": "兴趣点(POI)"},
            {"label": "超市",       "type": "point", "color": "#0284c7", "icon": "🛒", "group": "兴趣点(POI)"},
            {"label": "商场",       "type": "point", "color": "#db2777", "icon": "🛍️", "group": "兴趣点(POI)"},
            {"label": "医院",       "type": "point", "color": "#dc2626", "icon": "🏥", "group": "兴趣点(POI)"},
            {"label": "学校",       "type": "point", "color": "#2563eb", "icon": "🏫", "group": "兴趣点(POI)"},
            {"label": "大学",       "type": "point", "color": "#4f46e5", "icon": "🎓", "group": "兴趣点(POI)"},
            {"label": "地铁站",     "type": "point", "color": "#6366f1", "icon": "🚇", "group": "兴趣点(POI)"},
            {"label": "公交站",     "type": "point", "color": "#06b6d4", "icon": "🚌", "group": "兴趣点(POI)"},
            {"label": "停车场",     "type": "point", "color": "#475569", "icon": "🅿️", "group": "兴趣点(POI)"},
            {"label": "加油站",     "type": "point", "color": "#f59e0b", "icon": "⛽", "group": "兴趣点(POI)"},
            {"label": "酒店",       "type": "point", "color": "#be185d", "icon": "🏨", "group": "兴趣点(POI)"},
            {"label": "银行",       "type": "point", "color": "#b45309", "icon": "🏦", "group": "兴趣点(POI)"},
            {"label": "景点",       "type": "point", "color": "#059669", "icon": "🏞️", "group": "兴趣点(POI)"},
            {"label": "博物馆",     "type": "point", "color": "#dc2626", "icon": "🏛️", "group": "兴趣点(POI)"},
            {"label": "公园",       "type": "point", "color": "#16a34a", "icon": "🌳", "group": "兴趣点(POI)"},
            {"label": "其他地点",   "type": "point", "color": "#64748b", "icon": "📍", "group": "兴趣点(POI)"},
        ],
    },
    "food": {
        "title": "美食图图例",
        "items": [
            {"label": "餐厅",   "type": "point", "color": "#e11d48", "icon": "🍜"},
            {"label": "咖啡厅", "type": "point", "color": "#92400e", "icon": "☕"},
            {"label": "酒吧",   "type": "point", "color": "#7c3aed", "icon": "🍺"},
            {"label": "快餐",   "type": "point", "color": "#ea580c", "icon": "🍔"},
        ],
    },
    "campus": {
        "title": "校园图图例",
        "items": [
            {"label": "大学",     "type": "point", "color": "#2563eb", "icon": "🎓"},
            {"label": "图书馆",   "type": "point", "color": "#7c3aed", "icon": "📚"},
            {"label": "教学楼",   "type": "polygon", "fillColor": "#e9d5ff", "color": "#9333ea", "fillOpacity": 0.5},
            {"label": "宿舍",     "type": "polygon", "fillColor": "#fef9c3", "color": "#ca8a04", "fillOpacity": 0.4},
            {"label": "体育设施", "type": "point", "color": "#059669", "icon": "⚽"},
        ],
    },
    "population": {
        "title": "人口密度图例",
        "items": [
            {"label": "极低密度 (<20人/km²)",  "type": "polygon", "fillColor": "#fff7ec", "color": "#fee8c8", "fillOpacity": 0.7},
            {"label": "低密度 (20-40)",        "type": "polygon", "fillColor": "#fdd49e", "color": "#fdbb84", "fillOpacity": 0.7},
            {"label": "中密度 (40-60)",        "type": "polygon", "fillColor": "#fc8d59", "color": "#ef6548", "fillOpacity": 0.7},
            {"label": "高密度 (60-80)",        "type": "polygon", "fillColor": "#d7301f", "color": "#b30000", "fillOpacity": 0.7},
            {"label": "极高密度 (>80)",        "type": "polygon", "fillColor": "#7f0000", "color": "#4d0000", "fillOpacity": 0.8},
        ],
    },
    "healthcare": {
        "title": "医疗资源图例",
        "items": [
            {"label": "大型医院",   "type": "point", "color": "#a50f15", "icon": "🏥", "radius": 10},
            {"label": "中型医院",   "type": "point", "color": "#de2d26", "icon": "🏥", "radius": 7},
            {"label": "社区诊所",   "type": "point", "color": "#fb6a4a", "icon": "💊", "radius": 5},
            {"label": "药店",       "type": "point", "color": "#fcae91", "icon": "💊", "radius": 4},
            {"label": "牙科诊所",   "type": "point", "color": "#fee5d9", "icon": "🦷", "radius": 4},
        ],
    },
    "education": {
        "title": "教育设施图例",
        "items": [
            {"label": "大学",       "type": "point", "color": "#7c3aed", "icon": "🎓", "radius": 8},
            {"label": "学院",       "type": "point", "color": "#8b5cf6", "icon": "🏫", "radius": 7},
            {"label": "中小学",     "type": "point", "color": "#a78bfa", "icon": "🏫", "radius": 6},
            {"label": "幼儿园",     "type": "point", "color": "#c4b5fd", "icon": "🧒", "radius": 5},
            {"label": "图书馆",     "type": "point", "color": "#5b21b6", "icon": "📚", "radius": 6},
        ],
    },
    "commercial": {
        "title": "商业分布图例",
        "items": [
            {"label": "极高温区",   "type": "polygon", "fillColor": "#b10026", "color": "#800026", "fillOpacity": 0.7},
            {"label": "高温区",     "type": "polygon", "fillColor": "#e31a1c", "color": "#bd0026", "fillOpacity": 0.6},
            {"label": "中温区",     "type": "polygon", "fillColor": "#fd8d3c", "color": "#fc4e2a", "fillOpacity": 0.5},
            {"label": "低温区",     "type": "polygon", "fillColor": "#fed976", "color": "#feb24c", "fillOpacity": 0.4},
            {"label": "极低温区",   "type": "polygon", "fillColor": "#ffffcc", "color": "#ffeda0", "fillOpacity": 0.3},
        ],
    },
    "greenery": {
        "title": "绿化覆盖图例",
        "items": [
            {"label": "高覆盖 (>70%)",  "type": "polygon", "fillColor": "#005a32", "color": "#00441b", "fillOpacity": 0.7},
            {"label": "中高 (50-70%)",  "type": "polygon", "fillColor": "#41ab5d", "color": "#238b45", "fillOpacity": 0.6},
            {"label": "中等 (30-50%)",  "type": "polygon", "fillColor": "#a1d99b", "color": "#74c476", "fillOpacity": 0.5},
            {"label": "中低 (15-30%)",  "type": "polygon", "fillColor": "#d9f0d3", "color": "#c7e9c0", "fillOpacity": 0.4},
            {"label": "低覆盖 (<15%)",  "type": "polygon", "fillColor": "#f7fcf5", "color": "#e5f5e0", "fillOpacity": 0.3},
        ],
    },
    "landuse": {
        "title": "土地利用图例",
        "items": [
            {"label": "居住用地",   "type": "polygon", "fillColor": "#fde68a", "color": "#d97706", "fillOpacity": 0.4},
            {"label": "商业用地",   "type": "polygon", "fillColor": "#fca5a5", "color": "#dc2626", "fillOpacity": 0.4},
            {"label": "工业用地",   "type": "polygon", "fillColor": "#d1d5db", "color": "#6b7280", "fillOpacity": 0.4},
            {"label": "农业用地",   "type": "polygon", "fillColor": "#bef264", "color": "#4d7c0f", "fillOpacity": 0.4},
            {"label": "森林",       "type": "polygon", "fillColor": "#16a34a", "color": "#14532d", "fillOpacity": 0.5},
            {"label": "草地",       "type": "polygon", "fillColor": "#d9f99d", "color": "#65a30d", "fillOpacity": 0.35},
            {"label": "公园",       "type": "polygon", "fillColor": "#86efac", "color": "#16a34a", "fillOpacity": 0.4},
            {"label": "水体",       "type": "polygon", "fillColor": "#7dd3fc", "color": "#0ea5e9", "fillOpacity": 0.4},
        ],
    },
    "economic": {
        "title": "经济分布图例",
        "items": [
            {"label": "大型商圈",   "type": "point", "color": "#006837", "icon": "🏦", "radius": 12},
            {"label": "中型商圈",   "type": "point", "color": "#31a354", "icon": "🏢", "radius": 8},
            {"label": "小型商圈",   "type": "point", "color": "#78c679", "icon": "🏪", "radius": 5},
            {"label": "微型商圈",   "type": "point", "color": "#addd8e", "icon": "🏪", "radius": 3},
        ],
    },
    "climate": {
        "title": "气候分布图例",
        "items": [
            {"label": "高温区 (>35°C)",   "type": "point", "color": "#980043", "icon": "🔥", "radius": 10},
            {"label": "温暖区 (25-35°C)", "type": "point", "color": "#dd1c77", "icon": "☀️", "radius": 8},
            {"label": "温和区 (15-25°C)", "type": "point", "color": "#df65b0", "icon": "🌤️", "radius": 6},
            {"label": "凉爽区 (5-15°C)",  "type": "point", "color": "#d4b9da", "icon": "❄️", "radius": 5},
            {"label": "寒冷区 (<5°C)",    "type": "point", "color": "#f1eef6", "icon": "❄️", "radius": 4},
        ],
    },
        "administrative": {
        "title": "行政区划图例",
        "items": [

            {"label": "武汉市域边界", "type": "line", "color": "#FF0000", "weight": 4, "group": "行政界线"},
            {"label": "区县界", "type": "line", "color": "#CCCCCC", "weight": 1, "dashArray": "5,5", "group": "行政界线"},
            {"label": "周边县界(细点线)", "type": "line", "color": "#999999", "weight": 0.9, "dashArray": "1,4", "group": "行政界线"},
            {"label": "湖泊", "type": "polygon", "fillColor": "#1e90ff", "color": "#1e90ff", "fillOpacity": 0.5, "group": "地理底图"},
            {"label": "重点地标", "type": "point", "color": "#16a34a", "icon": "🏞️", "group": "兴趣点(POI)"},
            {"label": "市级行政中心", "type": "point", "color": "#D82828", "icon": "★", "group": "行政中心"},
            {"label": "区县行政中心", "type": "point", "color": "#D82828", "icon": "●", "group": "行政中心"},
            {"label": "区县名称标注", "type": "point", "color": "#000000", "icon": "🏷️", "group": "地图注记"},
        ],
    },
    "heatmap": {
        "title": "热力分布图例",
        "items": [
            {"label": "极低密度",   "type": "polygon", "fillColor": "#000004", "color": "#320a5e", "fillOpacity": 0.5},
            {"label": "低密度",     "type": "polygon", "fillColor": "#320a5e", "color": "#781c6d", "fillOpacity": 0.6},
            {"label": "中密度",     "type": "polygon", "fillColor": "#781c6d", "color": "#bb3754", "fillOpacity": 0.7},
            {"label": "高密度",     "type": "polygon", "fillColor": "#bb3754", "color": "#ed6925", "fillOpacity": 0.8},
            {"label": "极高密度",   "type": "polygon", "fillColor": "#ed6925", "color": "#fcffa4", "fillOpacity": 0.9},
        ],
    },
}
