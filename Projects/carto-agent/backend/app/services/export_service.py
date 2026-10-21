"""地图导出服务 - 支持GeoJSON、SVG、PNG格式导出

将内部地图数据结构转换为标准地理数据格式：
- GeoJSON: 标准地理JSON格式，可被GIS工具直接导入
- SVG: 矢量图形格式，适合打印和文档嵌入
- PNG: 位图格式（返回Base64编码占位图，提示前端使用leaflet-image截图）
"""
import base64
import json
from typing import Optional, Any

from app.core.exceptions import CartoAgentError


class ExportService:
    """地图导出服务

    提供多种格式的地图数据导出功能。
    所有方法接收地图数据字典，返回对应格式的字符串。
    """

    def __init__(self):
        """初始化导出服务"""
        print("[ExportService] 初始化完成")

    def export_geojson(self, map_data: dict) -> str:
        """将地图数据转为GeoJSON格式

        将内部地图图层结构转换为标准的GeoJSON FeatureCollection。
        每个图层要素转换为一个Feature，包含geometry和properties。

        Args:
            map_data: 地图数据字典（含layers列表）

        Returns:
            GeoJSON格式的JSON字符串
        """
        features = []
        for layer in map_data.get("layers", []):
            layer_type = layer.get("type", "polyline")
            base_props = {"layer": layer.get("name", ""), "type": layer_type}
            # 面要素（features结构，如区县政区）
            for feat in layer.get("features", []):
                ring = feat.get("coordinates") or []
                if len(ring) >= 3:
                    poly = [[pt[1], pt[0]] for pt in ring if isinstance(pt, list) and len(pt) >= 2]
                    fprops = dict(base_props)
                    fprops.update(feat.get("properties") or {})
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [poly]},
                        "properties": fprops,
                    })
            # 线/点要素
            for coords in layer.get("coordinates", []):
                if isinstance(coords[0], (int, float)) and len(coords) >= 2:
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [coords[1], coords[0]]},
                        "properties": dict(base_props),
                    })
                elif isinstance(coords[0], list) and len(coords) > 1:
                    line = [[pt[1], pt[0]] for pt in coords if isinstance(pt, list) and len(pt) >= 2]
                    if len(line) > 1:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": line},
                            "properties": dict(base_props),
                        })
        return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False)

    def export_svg(self, map_data: dict) -> str:
        """生成带标准制图整饰的SVG（标题/图廓/图例/比例尺/编制说明）

        将地图要素投影到SVG画布上，生成符合行政区划图规范的矢量图形。

        Args:
            map_data: 地图数据字典

        Returns:
            SVG格式的XML字符串
        """
        import datetime
        layers = map_data.get("layers", [])
        width, height = 900, 700

        # 收集坐标（含 features 面要素）
        all_coords = []
        for layer in layers:
            for feat in layer.get("features", []):
                c = feat.get("coordinates") or []
                for pt in c:
                    if isinstance(pt, list) and len(pt) >= 2:
                        all_coords.append((pt[0], pt[1]))
            for coords in layer.get("coordinates", []):
                if isinstance(coords[0], (int, float)):
                    all_coords.append((coords[0], coords[1]))
                elif isinstance(coords[0], list):
                    for pt in coords:
                        if isinstance(pt, list) and len(pt) >= 2:
                            all_coords.append((pt[0], pt[1]))

        if not all_coords:
            return self._empty_svg(width, height, map_data.get("name", ""))

        lats = [c[0] for c in all_coords]
        lngs = [c[1] for c in all_coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        lat_range = max_lat - min_lat or 0.01
        lng_range = max_lng - min_lng or 0.01

        margin = 52
        top = 56
        bottom = height - 58

        def project(lat, lng):
            x = margin + (lng - min_lng) / lng_range * (width - 2 * margin)
            y = bottom - (lat - min_lat) / lat_range * (bottom - top)
            return x, y

        svg_elements = []

        # 1. 面要素（features，如区县政区）
        for layer in layers:
            for feat in layer.get("features", []):
                fcoords = feat.get("coordinates") or []
                fstyle = feat.get("style") or {}
                if len(fcoords) < 3:
                    continue
                pts = " ".join("%.1f,%.1f" % project(p[0], p[1]) for p in fcoords)
                fill = fstyle.get("fillColor", "#eee")
                fo = fstyle.get("fillOpacity", 0.5)
                fc = fstyle.get("color", "#999")
                svg_elements.append(
                    '<polygon points="' + pts + '" fill="' + fill + '" fill-opacity="' + str(fo) +
                    '" stroke="' + fc + '" stroke-width="0.8"/>'
                )

        # 2. 线/点要素
        for layer in layers:
            layer_type = layer.get("type", "polyline")
            style = layer.get("style", {})
            color = style.get("color", "#3388ff")
            weight = style.get("weight", 2)
            opacity = style.get("opacity", 0.8)
            for coords in layer.get("coordinates", []):
                if layer_type in ("circleMarker", "marker") and isinstance(coords[0], (int, float)):
                    x, y = project(coords[0], coords[1])
                    radius = style.get("radius", 5)
                    fill = style.get("fillColor", color)
                    svg_elements.append(
                        '<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" stroke-width="1.5"/>'
                        % (x, y, radius, fill, color)
                    )
                elif isinstance(coords[0], list) and len(coords) > 1:
                    points = ["%.1f,%.1f" % project(pt[0], pt[1]) for pt in coords if isinstance(pt, list) and len(pt) >= 2]
                    if len(points) > 1:
                        svg_elements.append(
                            '<polyline points="' + " ".join(points) + '" fill="none" stroke="' +
                            color + '" stroke-width="' + str(weight) + '" stroke-opacity="' + str(opacity) + '"/>'
                        )

        # 3. 图廓（外粗内细）
        svg_elements.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#4b5563" stroke-width="2.5"/>'
                            % (margin - 9, top - 9, width - 2 * margin + 18, bottom - top + 18))
        svg_elements.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#9ca3af" stroke-width="1"/>'
                            % (margin - 5, top - 5, width - 2 * margin + 10, bottom - top + 10))

        # 4. 图名（图廓上方居中）
        name = map_data.get("name", "") or ""
        svg_elements.append('<text x="%d" y="%d" text-anchor="middle" font-size="22" font-weight="bold" font-family="SimHei, sans-serif">%s</text>'
                            % (width // 2, top - 20, name))

        # 5. 图例（右下角，行政区划规范顺序）
        if map_data.get("map_type") == "administrative":
            lx, ly = width - 205, bottom - 168
            svg_elements.append('<rect x="%d" y="%d" width="185" height="150" fill="#ffffff" fill-opacity="0.94" stroke="#cbd5e1"/>' % (lx, ly))
            svg_elements.append('<text x="%d" y="%d" text-anchor="middle" font-size="13" font-weight="bold">图例</text>' % (lx + 92, ly + 22))
            svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#DC143C" stroke-width="3.5"/>' % (lx + 14, ly + 42, lx + 66, ly + 42))
            svg_elements.append('<text x="%d" y="%d" font-size="11">市域行政界线</text>' % (lx + 74, ly + 46))
            svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#FF6666" stroke-width="2"/>' % (lx + 14, ly + 64, lx + 66, ly + 64))
            svg_elements.append('<text x="%d" y="%d" font-size="11">区县行政界线</text>' % (lx + 74, ly + 68))
            svg_elements.append('<circle cx="%d" cy="%d" r="5" fill="#fff" stroke="#DC143C" stroke-width="2.5"/>' % (lx + 40, ly + 86))
            svg_elements.append('<text x="%d" y="%d" font-size="11">市级行政中心</text>' % (lx + 74, ly + 90))
            svg_elements.append('<circle cx="%d" cy="%d" r="3.5" fill="#fff" stroke="#DC143C" stroke-width="2"/>' % (lx + 40, ly + 108))
            svg_elements.append('<text x="%d" y="%d" font-size="11">区县级行政中心</text>' % (lx + 74, ly + 112))
            svg_elements.append('<circle cx="%d" cy="%d" r="6" fill="#E1E1CA" stroke="#FF6666" stroke-width="0.8"/>' % (lx + 40, ly + 130))
            svg_elements.append('<text x="%d" y="%d" font-size="11">区县政区（设色）</text>' % (lx + 74, ly + 134))

        # 6. 比例尺（数字比例尺 + 直线比例尺 0-40km）
        sx, sy = margin + 12, bottom - 14
        seg_w = 42
        svg_elements.append('<text x="%d" y="%d" font-size="10" fill="#333">1:400 000</text>' % (sx, sy - 12))
        svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" stroke-width="2"/>' % (sx, sy, sx + seg_w * 4, sy))
        for i in range(5):
            svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" stroke-width="1.2"/>' % (sx + i * seg_w, sy - 5, sx + i * seg_w, sy + 5))
        labels = [(0, "0"), (1, "10"), (2, "20"), (3, "30"), (4, "40km")]
        for i, lab in labels:
            x = sx + i * seg_w - (18 if lab.endswith("km") else 3)
            svg_elements.append('<text x="%d" y="%d" font-size="9">%s</text>' % (x, sy + 16, lab))

        # 7. 编制说明（图廓外左下）
        now = datetime.datetime.now().strftime("%Y年%m月")
        svg_elements.append(
            '<text x="%d" y="%d" font-size="9" fill="#64748b">编制单位：地图制图智能体 CartoAgent | 资料来源：官方行政区划数据（DataV/OSM） | 制图时间：%s | 坐标系：CGCS2000（Web墨卡托显示）</text>'
            % (margin, height - 22, now)
        )

        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">\n'
            '<rect width="%d" height="%d" fill="#f7f5f0"/>\n' % (width, height, width, height, width, height)
            + "\n".join(svg_elements)
            + "\n</svg>"
        )

        return svg

    def _empty_svg(self, width: int, height: int, title: str) -> str:
        """生成空SVG（无坐标数据时使用）

        Args:
            width: 画布宽度
            height: 画布高度
            title: 地图标题

        Returns:
            SVG字符串
        """
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
            f'<rect width="{width}" height="{height}" fill="#f5f5f5"/>\n'
            f'<text x="{width // 2}" y="{height // 2}" text-anchor="middle" '
            f'font-size="14" fill="#999">{title}（无地理数据）</text>\n'
            f'</svg>'
        )

    def export_png(self, map_data: dict) -> str:
        """返回Base64编码的占位图

        由于服务器端无法直接渲染Leaflet地图，此方法返回一个占位图，
        提示前端使用leaflet-image插件进行客户端截图。

        Args:
            map_data: 地图数据字典

        Returns:
            Base64编码的PNG图片字符串（带data URI前缀）
        """
        # 生成一个简单的占位PNG（1x1像素透明图）
        # 实际使用时前端应通过leaflet-image插件截图
        placeholder_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(placeholder_png).decode("utf-8")

        # 返回带提示信息的data URI
        map_name = map_data.get("name", "地图")
        print(
            f"[ExportService] PNG导出返回占位图。"
            f"提示：前端请使用leaflet-image插件对地图「{map_name}」进行截图。"
        )

        return f"data:image/png;base64,{b64_str}"

    def export(self, map_data: dict, fmt: str = "geojson") -> str:
        """统一导出接口

        Args:
            map_data: 地图数据字典
            fmt: 导出格式（geojson/svg/png）

        Returns:
            对应格式的字符串

        Raises:
            CartoAgentError: 不支持的格式
        """
        if fmt == "geojson":
            return self.export_geojson(map_data)
        elif fmt == "svg":
            return self.export_svg(map_data)
        elif fmt == "png":
            return self.export_png(map_data)
        else:
            raise CartoAgentError(f"不支持的导出格式: {fmt}，支持: geojson, svg, png")
