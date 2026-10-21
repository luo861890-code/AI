# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根目录
BACKEND = os.path.join(BASE, "backend")
FRONTEND = os.path.join(BASE, "frontend")

def modify_constants():
    fp = os.path.join(BACKEND, "app", "core", "constants.py")
    with open(fp, "r", encoding="utf-8") as f:
        c = f.read()
    changed = False

    # 1. 专题地图类型
    if '"population"' not in c:
        m = re.search(r'(MAP_TYPE_MAP[^{]*\{[^}]*?)(\})', c, re.DOTALL)
        if m:
            t = '\n    # 专题地图类型\n    "人口密度图": "population", "人口图": "population", "人口分布": "population",\n    "经济分布图": "economic", "经济图": "economic", "GDP分布": "economic",\n    "土地利用图": "landuse", "用地": "landuse", "土地覆盖": "landuse",\n    "气候图": "climate", "气象图": "climate",\n    "医疗资源图": "healthcare", "医疗图": "healthcare", "医院分布": "healthcare",\n    "教育设施图": "education", "教育图": "education", "学校分布": "education",\n    "商业分布图": "commercial", "商业图": "commercial", "商圈分布": "commercial",\n    "绿化覆盖图": "greenery", "绿化图": "greenery", "绿地分布": "greenery",\n    "热力图": "heatmap", "热力分布": "heatmap",\n'
            c = c[:m.end(1)] + t + c[m.start(2):]
            changed = True
            print("[OK] MAP_TYPE_MAP 添加专题地图类型")

    # 2. OSM标签
    if 'MAP_TYPE_OSM_TAGS' in c:
        after_tags = c.split('MAP_TYPE_OSM_TAGS', 1)[1] if 'MAP_TYPE_OSM_TAGS' in c else ''
        if '"population"' not in after_tags[:500]:
            m = re.search(r'(MAP_TYPE_OSM_TAGS[^{]*\{[^}]*?)(\})', c, re.DOTALL)
            if m:
                t = '\n    # 专题地图OSM标签\n    "population": {"amenity": ["place_of_worship", "school"], "highway": ["residential"]},\n    "economic": {"amenity": ["bank", "atm"], "shop": ["mall", "supermarket"], "office": ["company"]},\n    "landuse": {"landuse": ["residential", "commercial", "industrial", "farmland", "forest", "grass", "meadow"]},\n    "climate": {"natural": ["tree", "wood"], "water": ["river", "lake"]},\n    "healthcare": {"amenity": ["hospital", "clinic", "doctors", "pharmacy", "dentist"]},\n    "education": {"amenity": ["school", "university", "college", "kindergarten", "library"]},\n    "commercial": {"shop": ["mall", "supermarket", "convenience", "clothes", "electronics"], "amenity": ["marketplace"]},\n    "greenery": {"leisure": ["park", "garden"], "natural": ["wood", "tree"], "landuse": ["forest", "grass"]},\n    "heatmap": {"amenity": ["restaurant", "cafe", "shop", "bank"], "shop": ["*"]},\n'
                c = c[:m.end(1)] + t + c[m.start(2):]
                changed = True
                print("[OK] MAP_TYPE_OSM_TAGS 添加专题地图标签")

    # 3. 中文底图
    if '"amap_normal"' not in c:
        m = re.search(r'(MAP_THEMES[^{]*\{[^}]*?)(\})', c, re.DOTALL)
        if m:
            t = '\n    # 中文底图\n    "amap_normal": {"name": "高德地图", "url": "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", "attribution": "&copy; 高德地图", "subdomains": "1234", "maxZoom": 20},\n    "amap_satellite": {"name": "高德卫星", "url": "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}", "attribution": "&copy; 高德地图", "subdomains": "1234", "maxZoom": 20},\n    "tianditu_vec": {"name": "天地图矢量", "url": "https://t{s}.tianditu.gov.cn/DataServer?T=vec_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", "attribution": "&copy; 天地图", "subdomains": "01234567", "maxZoom": 18},\n    "tianditu_img": {"name": "天地图影像", "url": "https://t{s}.tianditu.gov.cn/DataServer?T=img_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", "attribution": "&copy; 天地图", "subdomains": "01234567", "maxZoom": 18},\n    "tianditu_cva": {"name": "天地图标注", "url": "https://t{s}.tianditu.gov.cn/DataServer?T=cva_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", "attribution": "&copy; 天地图", "subdomains": "01234567", "maxZoom": 18},\n    "tencent_normal": {"name": "腾讯地图", "url": "https://rt{s}.map.gtimg.com/realtimerender?z={z}&x={x}&y={-y}&type=vector&style=0", "attribution": "&copy; 腾讯地图", "subdomains": "0123", "maxZoom": 20},\n    "esri_street_cn": {"name": "Esri中文街道", "url": "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", "attribution": "&copy; Esri", "maxZoom": 19},\n'
            c = c[:m.end(1)] + t + c[m.start(2):]
            changed = True
            print("[OK] MAP_THEMES 添加中文底图")

    # 4. THEMATIC_MAP_CONFIG
    if 'THEMATIC_MAP_CONFIG' not in c:
        cfg = '\n\n# ========== 专题地图渲染配置 ==========\nTHEMATIC_MAP_CONFIG: Dict[str, Dict[str, Any]] = {\n    "population": {"name": "人口密度图", "render_type": "choropleth", "color_scheme": ["#fff7ec", "#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#ef6548", "#d7301f", "#990000"], "description": "展示人口空间分布密度", "unit": "人/km²", "legend_title": "人口密度"},\n    "economic": {"name": "经济分布图", "render_type": "proportional_symbol", "color_scheme": ["#ffffcc", "#d9f0a3", "#addd8e", "#78c679", "#31a354", "#006837"], "description": "展示经济活动空间分布", "unit": "亿元", "legend_title": "GDP规模"},\n    "landuse": {"name": "土地利用图", "render_type": "categorical", "color_scheme": {"residential": "#ffd699", "commercial": "#f97316", "industrial": "#9ca3af", "farmland": "#84cc16", "forest": "#16a34a", "water": "#3b82f6", "grass": "#86efac", "other": "#e7e5e4"}, "description": "展示城市土地利用类型分布", "legend_title": "用地类型"},\n    "climate": {"name": "气候分布图", "render_type": "graduated", "color_scheme": ["#f1eef6", "#d4b9da", "#c994c7", "#df65b0", "#dd1c77", "#980043"], "description": "展示气候要素空间分布", "unit": "°C", "legend_title": "年均气温"},\n    "healthcare": {"name": "医疗资源图", "render_type": "proportional_symbol", "color_scheme": ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"], "description": "展示医疗机构空间分布", "legend_title": "医疗设施"},\n    "education": {"name": "教育设施图", "render_type": "categorical", "color_scheme": {"university": "#7c3aed", "college": "#8b5cf6", "school": "#a78bfa", "kindergarten": "#c4b5fd", "library": "#5b21b6"}, "description": "展示教育机构空间分布", "legend_title": "教育类型"},\n    "commercial": {"name": "商业分布图", "render_type": "heatmap", "color_scheme": ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026"], "description": "展示商业活动热力分布", "legend_title": "商业热度"},\n    "greenery": {"name": "绿化覆盖图", "render_type": "choropleth", "color_scheme": ["#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476", "#41ab5d", "#238b45", "#005a32"], "description": "展示城市绿化覆盖分布", "unit": "%", "legend_title": "绿化率"},\n    "heatmap": {"name": "热力分布图", "render_type": "heatmap", "color_scheme": ["#000004", "#320a5e", "#781c6d", "#bb3754", "#ed6925", "#fcbf49", "#fcffa4"], "description": "综合热力分布图", "legend_title": "密度"},\n}\n'
        c = c.rstrip() + cfg
        changed = True
        print("[OK] 添加 THEMATIC_MAP_CONFIG")

    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(c)
        print("[DONE] constants.py 修改完成")

def modify_map_service():
    fp = os.path.join(BACKEND, "app", "services", "map_service.py")
    with open(fp, "r", encoding="utf-8") as f:
        c = f.read()
    changed = False

    if '_generate_thematic_layers' not in c:
        method = '''
    def _generate_thematic_layers(self, map_type: str, region: str, center: List[float]) -> List[dict]:
        """生成专题地图图层数据"""
        from app.core.constants import THEMATIC_MAP_CONFIG
        import random
        config = THEMATIC_MAP_CONFIG.get(map_type, {})
        if not config:
            return []
        layers = []
        cs = config.get("color_scheme", ["#3388ff"])
        rt = config.get("render_type", "choropleth")
        lid = generate_id("layer")
        def rp(o=0.06):
            return [center[0] + random.uniform(-o, o), center[1] + random.uniform(-o, o)]
        if rt == "heatmap":
            pts = []
            for _ in range(120):
                p = rp(0.08)
                pts.append([p[0], p[1], random.uniform(0.2, 1.0)])
            layers.append({"id": lid, "type": "heatmap", "name": config.get("name", "热力图"), "coordinates": pts, "style": {"color_scheme": cs, "radius": 35, "blur": 25, "maxZoom": 17, "minOpacity": 0.3}, "metadata": {"render_type": "heatmap", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "point_count": len(pts)}})
        elif rt == "proportional_symbol":
            feats = []
            for i in range(60):
                p = rp(0.07)
                v = random.uniform(10, 100)
                s = 5 + (v / 100) * 25
                ci = min(int(v / 20), len(cs) - 1)
                feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"value": round(v, 1), "name": f"点{i+1}", "size": round(s, 1)}, "style": {"color": cs[ci], "radius": s, "fillOpacity": 0.7, "weight": 1}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "比例符号图"), "features": feats, "style": {"color_scheme": cs, "render_type": "proportional_symbol"}, "metadata": {"render_type": "proportional_symbol", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "feature_count": len(feats)}})
        elif rt == "choropleth":
            feats = []
            gs = 8
            off = 0.08
            step = (off * 2) / gs
            for i in range(gs):
                for j in range(gs):
                    lat = center[0] - off + i * step
                    lng = center[1] - off + j * step
                    v = random.uniform(0, 100)
                    ci = min(int(v / (100 / len(cs))), len(cs) - 1)
                    coords = [[lat, lng], [lat + step, lng], [lat + step, lng + step], [lat, lng + step], [lat, lng]]
                    feats.append({"id": generate_id("feat"), "type": "polygon", "coordinates": coords, "properties": {"value": round(v, 1), "grid_id": f"{i}_{j}"}, "style": {"color": cs[ci], "fillColor": cs[ci], "fillOpacity": 0.6, "weight": 0.5, "opacity": 0.3}})
            layers.append({"id": lid, "type": "polygon", "name": config.get("name", "分级色彩图"), "features": feats, "style": {"color_scheme": cs, "render_type": "choropleth"}, "metadata": {"render_type": "choropleth", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "grid_size": f"{gs}x{gs}", "feature_count": len(feats)}})
        elif rt == "categorical":
            feats = []
            if isinstance(cs, dict):
                cats = list(cs.keys())
                for i in range(80):
                    p = rp(0.07)
                    cat = random.choice(cats)
                    feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"category": cat, "name": cat}, "style": {"color": cs[cat], "fillColor": cs[cat], "radius": 6, "fillOpacity": 0.8, "weight": 1}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "分类图"), "features": feats, "style": {"color_scheme": cs, "render_type": "categorical"}, "metadata": {"render_type": "categorical", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "categories": list(cs.keys()) if isinstance(cs, dict) else [], "feature_count": len(feats)}})
        elif rt == "graduated":
            feats = []
            for i in range(70):
                p = rp(0.07)
                v = random.uniform(0, 50)
                if v < 10: s, col = 4, cs[0]
                elif v < 20: s, col = 8, cs[1] if len(cs) > 1 else cs[0]
                elif v < 30: s, col = 14, cs[2] if len(cs) > 2 else cs[-1]
                elif v < 40: s, col = 20, cs[3] if len(cs) > 3 else cs[-1]
                else: s, col = 28, cs[-1]
                feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"value": round(v, 1), "level": int(v / 10)}, "style": {"color": col, "fillColor": col, "radius": s, "fillOpacity": 0.6, "weight": 1.5}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "分级符号图"), "features": feats, "style": {"color_scheme": cs, "render_type": "graduated"}, "metadata": {"render_type": "graduated", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "feature_count": len(feats)}})
        return layers

'''
        if 'def _generate_fallback_layers' in c:
            c = c.replace('    def _generate_fallback_layers', method + '    def _generate_fallback_layers')
        elif 'def _elements_to_layers' in c:
            c = c.replace('    def _elements_to_layers', method + '    def _elements_to_layers')
        changed = True
        print("[OK] 添加 _generate_thematic_layers 方法")

    if 'THEMATIC_MAP_CONFIG' not in c:
        insert = '''
            # 专题地图特殊处理
            from app.core.constants import THEMATIC_MAP_CONFIG
            if map_type in THEMATIC_MAP_CONFIG:
                thematic_layers = self._generate_thematic_layers(map_type, region, center)
                if thematic_layers:
                    map_layers = thematic_layers
                    logger.info(f"专题地图生成完成: {map_type}, {len(map_layers)} 个图层")

'''
        for kw in ['如果OSM数据为空', '使用本地地标', '回退', 'fallback', '_generate_fallback_layers', 'WUHAN_LANDMARKS']:
            idx = c.find(kw)
            if idx > 0:
                ls = c.rfind('\n', 0, idx) + 1
                c = c[:ls] + insert + c[ls:]
                changed = True
                print(f"[OK] 在 '{kw}' 前插入专题地图逻辑")
                break

    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(c)
        print("[DONE] map_service.py 修改完成")

def modify_maps_api():
    fp = os.path.join(BACKEND, "app", "api", "maps.py")
    with open(fp, "r", encoding="utf-8") as f:
        c = f.read()
    if '/thematic/types' in c:
        print("[SKIP] maps.py 已有 /thematic/types")
        return
    ep = '''
@router.get("/thematic/types", response_model=ApiResponse, summary="获取支持的专题地图类型")
async def get_thematic_types():
    """获取系统支持的所有专题地图类型及其渲染配置"""
    from app.core.constants import THEMATIC_MAP_CONFIG
    return ApiResponse(success=True, data=THEMATIC_MAP_CONFIG)

'''
    m = re.search(r'\n(@router\.(get|post))', c)
    if m:
        c = c[:m.start()] + '\n' + ep + c[m.start() + 1:]
        with open(fp, "w", encoding="utf-8") as f:
            f.write(c)
        print("[DONE] maps.py 添加 /thematic/types 端点")

def modify_frontend_config():
    fp = os.path.join(FRONTEND, "config.js")
    if not os.path.exists(fp):
        print(f"[SKIP] {fp} 不存在")
        return
    with open(fp, "r", encoding="utf-8") as f:
        c = f.read()
    changed = False

    # 添加中文底图
    if 'amap_normal' not in c:
        m = re.search(r'(mapThemes\s*:\s*\{[^}]*?)(\})', c, re.DOTALL)
        if m:
            t = ',\n            amap_normal: { name: "高德地图", url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", attribution: "&copy; 高德地图", maxZoom: 20, subdomains: "1234" },\n            amap_satellite: { name: "高德卫星", url: "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}", attribution: "&copy; 高德地图", maxZoom: 20, subdomains: "1234" },\n            tianditu_vec: { name: "天地图矢量", url: "https://t{s}.tianditu.gov.cn/DataServer?T=vec_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", attribution: "&copy; 天地图", maxZoom: 18, subdomains: "01234567" },\n            tianditu_img: { name: "天地图影像", url: "https://t{s}.tianditu.gov.cn/DataServer?T=img_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de", attribution: "&copy; 天地图", maxZoom: 18, subdomains: "01234567" },\n            tencent_normal: { name: "腾讯地图", url: "https://rt{s}.map.gtimg.com/realtimerender?z={z}&x={x}&y={-y}&type=vector&style=0", attribution: "&copy; 腾讯地图", maxZoom: 20, subdomains: "0123" },\n            esri_street_cn: { name: "Esri中文街道", url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", attribution: "&copy; Esri", maxZoom: 19 }'
            c = c[:m.end(1)] + t + c[m.start(2):]
            changed = True
            print("[OK] config.js 添加中文底图")

    # 添加专题地图快捷指令
    if '人口密度图' not in c:
        m = re.search(r'(quickCommands\s*:\s*\[[^\]]*?)(\])', c, re.DOTALL)
        if m:
            t = ',\n            { label: "人口密度图", icon: "fa-users", message: "生成一份武汉市人口密度图" },\n            { label: "土地利用图", icon: "fa-layer-group", message: "生成一份武汉市土地利用图" },\n            { label: "医疗资源图", icon: "fa-hospital", message: "生成一份武汉市医疗资源图" },\n            { label: "商业热力图", icon: "fa-fire", message: "生成一份武汉市商业分布热力图" },\n            { label: "教育设施图", icon: "fa-graduation-cap", message: "生成一份武汉市教育设施图" },\n            { label: "绿化覆盖图", icon: "fa-tree", message: "生成一份武汉市绿化覆盖图" }'
            c = c[:m.end(1)] + t + c[m.start(2):]
            changed = True
            print("[OK] config.js 添加专题地图快捷指令")

    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(c)
        print("[DONE] config.js 修改完成")

def modify_map_js():
    fp = os.path.join(FRONTEND, "src", "js", "map.js")
    if not os.path.exists(fp):
        print(f"[SKIP] {fp} 不存在")
        return
    with open(fp, "r", encoding="utf-8") as f:
        c = f.read()
    changed = False

    # 添加热力图渲染支持
    if 'L.heatLayer' not in c and 'renderHeatmap' not in c:
        heatmap_code = '''
    renderHeatmap(layer) {
        if (typeof L.heatLayer === 'undefined') {
            console.warn('leaflet.heat 插件未加载，使用圆形标记替代热力图');
            const group = L.layerGroup();
            const coords = layer.coordinates || [];
            const style = layer.style || {};
            const colorScheme = style.color_scheme || ['#000004', '#320a5e', '#781c6d', '#bb3754', '#ed6925', '#fcbf49', '#fcffa4'];
            coords.forEach(pt => {
                if (pt && pt.length >= 3 && pt[0] != null && pt[1] != null) {
                    const intensity = pt[2] || 0.5;
                    const colorIdx = Math.min(Math.floor(intensity * colorScheme.length), colorScheme.length - 1);
                    L.circleMarker([pt[0], pt[1]], {
                        radius: 8 + intensity * 12,
                        fillColor: colorScheme[colorIdx],
                        color: colorScheme[colorIdx],
                        fillOpacity: intensity * 0.6,
                        weight: 0
                    }).addTo(group);
                }
            });
            return group;
        }
        const coords = (layer.coordinates || []).filter(pt => pt && pt[0] != null && pt[1] != null);
        const style = layer.style || {};
        return L.heatLayer(coords, {
            radius: style.radius || 35,
            blur: style.blur || 25,
            maxZoom: style.maxZoom || 17,
            minOpacity: style.minOpacity || 0.3,
            gradient: this._buildHeatGradient(style.color_scheme)
        });
    }

    _buildHeatGradient(colors) {
        if (!colors || !Array.isArray(colors)) return { 0.0: '#000004', 0.3: '#320a5e', 0.6: '#bb3754', 1.0: '#fcffa4' };
        const gradient = {};
        colors.forEach((color, i) => {
            gradient[i / (colors.length - 1)] = color;
        });
        return gradient;
    }

'''
        # 在 renderLayer 方法之前或 renderFeatures 方法之前插入
        if 'renderLayer(' in c:
            c = c.replace('    renderLayer(', heatmap_code + '    renderLayer(')
        elif 'renderFeatures(' in c:
            c = c.replace('    renderFeatures(', heatmap_code + '    renderFeatures(')
        changed = True
        print("[OK] map.js 添加热力图渲染方法")

    # 在图层渲染中添加热力图类型检测
    if "layer.type === 'heatmap'" not in c and "type == 'heatmap'" not in c:
        # 找到图层渲染逻辑中的类型判断
        if "layer.type === 'polyline'" in c:
            heatmap_check = "        if (layer.type === 'heatmap') {\n            return this.renderHeatmap(layer);\n        }\n"
            c = c.replace("        if (layer.type === 'polyline')", heatmap_check + "        if (layer.type === 'polyline')")
            changed = True
            print("[OK] map.js 添加热力图类型检测")
        elif "type === 'polyline'" in c:
            heatmap_check = "        if (layer.type === 'heatmap') {\n            return this.renderHeatmap(layer);\n        }\n"
            c = c.replace("        if (type === 'polyline')", heatmap_check + "        if (type === 'polyline')")
            changed = True
            print("[OK] map.js 添加热力图类型检测")

    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(c)
        print("[DONE] map.js 修改完成")

def modify_index_html():
    fp = os.path.join(FRONTEND, "src", "index.html")
    if not os.path.exists(fp):
        print(f"[SKIP] {fp} 不存在")
        return
    with open(fp, "r", encoding="utf-8") as f:
        c = f.read()
    changed = False

    # 添加 leaflet.heat 插件
    if 'leaflet.heat' not in c:
        heat_script = '\n    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>\n'
        # 在 Leaflet JS 之后插入
        if 'leaflet@1.9.4/dist/leaflet.js' in c:
            c = c.replace('leaflet@1.9.4/dist/leaflet.js"></script>', 'leaflet@1.9.4/dist/leaflet.js"></script>' + heat_script)
            changed = True
            print("[OK] index.html 添加 leaflet.heat 插件")

    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(c)
        print("[DONE] index.html 修改完成")

def verify():
    os.chdir(BASE)
    try:
        import importlib
        import app.core.constants as const
        importlib.reload(const)
        print(f"\n=== 验证结果 ===")
        print(f"专题地图类型(THEMATIC_MAP_CONFIG): {len(const.THEMATIC_MAP_CONFIG)} 种")
        print(f"底图主题(MAP_THEMES): {len(const.MAP_THEMES)} 种")
        print(f"地图类型映射(MAP_TYPE_MAP): {len(const.MAP_TYPE_MAP)} 种")
        for k in list(const.THEMATIC_MAP_CONFIG.keys()):
            print(f"  - {k}: {const.THEMATIC_MAP_CONFIG[k]['name']} ({const.THEMATIC_MAP_CONFIG[k]['render_type']})")
        print(f"\n中文底图:")
        for k, v in const.MAP_THEMES.items():
            if k not in ['standard', 'positron', 'dark', 'satellite']:
                print(f"  - {k}: {v.get('name', k)}")
        from app.services.map_service import MapService
        print("\n[OK] MapService 导入成功")
        from app.api.maps import router
        print("[OK] maps 路由导入成功")
        print("\n[成功] 所有后端修改验证通过!")
    except Exception as e:
        print(f"\n[错误] 验证失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("Carto-Agent 系统修复脚本")
    print("=" * 60)
    print("\n--- 1. 修改 constants.py ---")
    modify_constants()
    print("\n--- 2. 修改 map_service.py ---")
    modify_map_service()
    print("\n--- 3. 修改 maps.py ---")
    modify_maps_api()
    print("\n--- 4. 修改 frontend/config.js ---")
    modify_frontend_config()
    print("\n--- 5. 修改 frontend/src/js/map.js ---")
    modify_map_js()
    print("\n--- 6. 修改 frontend/src/index.html ---")
    modify_index_html()
    print("\n--- 7. 验证修改 ---")
    verify()
    print("\n" + "=" * 60)
    print("修复完成! 请重启后端服务。")
    print("=" * 60)
