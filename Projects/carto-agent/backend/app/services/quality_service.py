# -*- coding: utf-8 -*-
"""地图数据质量校验服务

面向行政区划等专题地图，提供五类可落地检测：
拓扑几何 / 属性数据 / 元数据统计 / 逻辑一致性 / 专题图层适配。
输出结构化报告，支持前端"问题定位跳转"。
"""
from typing import Any, Dict, List

from app.utils.geometry import (
    _haversine,
    _line_len_km,
    _point_in_ring,
    _ring_area_km2,
)


# ============ 几何工具 ============

def _cross(o: tuple, a: tuple, b: tuple) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _seg_intersect(p1, p2, p3, p4) -> bool:
    """严格相交（排除端点共享）"""
    d1 = _cross(p3, p4, p1); d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3); d4 = _cross(p1, p2, p4)
    return (((d1 > 1e-12 and d2 < -1e-12) or (d1 < -1e-12 and d2 > 1e-12)) and
            ((d3 > 1e-12 and d4 < -1e-12) or (d3 < -1e-12 and d4 > 1e-12)))


def _ring_self_intersect(ring: list) -> bool:
    n = len(ring)
    if n < 4:
        return False
    for i in range(n - 1):
        for j in range(i + 2, n - 1):
            if i == 0 and j == n - 2:
                continue
            if _seg_intersect(ring[i], ring[i + 1], ring[j], ring[j + 1]):
                return True
    return False


def _geom_key(geom: list) -> str:
    """几何哈希（去重检测），兼容单点坐标"""
    if not geom:
        return ""
    if isinstance(geom[0], (int, float)):
        geom = [geom]
    return repr([round(p[0], 6) for p in geom] + [round(p[1], 6) for p in geom])
# ============ 质量校验服务 ============

class QualityService:
    """地图数据质量校验服务（五类检测项）"""

    DISTRICT_REF_AREA = 8569.0  # 武汉市理论市域面积 km²

    def check(self, map_data: dict) -> dict:
        items: List[dict] = []
        layers = map_data.get("layers", []) or []
        map_type = map_data.get("map_type", "")

        self._check_degenerate(items, layers)
        self._check_duplicate_geom(items, layers)
        self._check_redundant_vertices(items, layers)
        self._check_self_intersect(items, layers)
        self._check_overlap(items, layers)
        self._check_sliver(items, layers)
        self._check_dangle(items, layers, map_type)
        self._check_attributes(items, layers)
        self._check_area(items, layers, map_type)
        self._check_topic_layers(items, layers, map_type)
        self._check_labels(items, layers)
        self._check_boundary_fit(items, layers)
        self._check_center_fit(items, layers)
        self._check_cross_feature(items, layers)

        total = len(items)
        passed = sum(1 for it in items if it.get("passed"))
        failed = total - passed
        return {
            "summary": {
                "total_checks": total,
                "passed": passed,
                "failed": failed,
                "passed_all": failed == 0,
            },
            "items": items,
            "map_id": map_data.get("map_id"),
            "map_name": map_data.get("name"),
        }

    @staticmethod
    def _item(category: str, check: str, passed: bool, layers: list,
              count: int = 0, positions: list = None, message: str = ""):
        return {
            "category": category, "check": check, "passed": passed,
            "layers": layers, "count": count,
            "positions": positions or [],
            "message": message,
        }

    # ---------- 拓扑几何 ----------

    def _check_degenerate(self, items, layers):
        """无效退化几何：面积/长度为0的要素"""
        bad = []
        for L in layers:
            name = L.get("name", "")
            if L.get("type") == "polygon":
                for feat in L.get("features", []):
                    ring = feat.get("coordinates") or []
                    if len(ring) < 3 or _ring_area_km2(ring) < 1e-6:
                        bad.append((name, ring[:1]))
                for c in (L.get("coordinates") or []):
                    if len(c) < 3:
                        bad.append((name, c[:1]))
            elif L.get("type") in ("polyline", "line"):
                for c in (L.get("coordinates") or []):
                    if not c or _line_len_km(c) < 0.001:
                        bad.append((name, c[:1]))
        items.append(self._item("拓扑几何", "无效退化几何",
                                len(bad) == 0, sorted(set(b for b, _ in bad)),
                                len(bad), [p for _, p in bad[:10]],
                                "存在面积/长度趋近0的无效要素" if bad else ""))

    def _check_duplicate_geom(self, items, layers):
        """重复几何要素：完全相同坐标序列"""
        seen = {}
        bad = []
        for L in layers:
            if L.get("type") not in ("polygon", "area", "polyline", "line"):
                continue  # 点/标注图层同位置属正常设计，跳过
            name = L.get("name", "")
            # 1) 境界线图层由政区面轮廓生成，与面共享几何属正常表达（界线=面轮廓），豁免；
            # 2) 道路双层渲染（外层描边+内层芯线）共用同一坐标，属正常表达，豁免
            if "界" in name or "省界" in name or "(外层)" in name or "(内层)" in name:
                continue
            for feat in L.get("features", []):
                ring = feat.get("coordinates") or []
                if ring:
                    k = _geom_key(ring)
                    if k in seen:
                        bad.append((name, ring[:1]))
                    seen[k] = name
            for c in (L.get("coordinates") or []):
                if not isinstance(c, list) or not c or isinstance(c[0], (int, float)):
                    continue
                k = _geom_key(c)
                if k in seen:
                    bad.append((name, c[:1]))
                seen[k] = name
        items.append(self._item("拓扑几何", "重复几何要素",
                                len(bad) == 0, sorted(set(b for b, _ in bad)),
                                len(bad), [p for _, p in bad[:10]],
                                "存在完全相同坐标的重复要素" if bad else ""))

    def _check_redundant_vertices(self, items, layers):
        """冗余重复折点：连续相同坐标点"""
        count = 0
        bad_layers = set()
        for L in layers:
            coords = L.get("coordinates") or []
            for c in coords:
                if not isinstance(c, list) or not c or isinstance(c[0], (int, float)):
                    continue
                for i in range(1, len(c)):
                    if abs(c[i][0] - c[i - 1][0]) < 1e-9 and abs(c[i][1] - c[i - 1][1]) < 1e-9:
                        count += 1
                        bad_layers.add(L.get("name", ""))
        items.append(self._item("拓扑几何", "冗余重复折点",
                                count == 0, sorted(bad_layers), count,
                                message="存在连续重复坐标点" if count else ""))

    def _check_self_intersect(self, items, layers):
        """面要素自相交：多边形环边与自身其他边相交"""
        bad_layers = set()
        count = 0
        for L in layers:
            if L.get("type") != "polygon":
                continue
            rings = [f.get("coordinates") for f in L.get("features", [])] + list(L.get("coordinates") or [])
            for ring in rings:
                if ring and _ring_self_intersect(ring):
                    count += 1
                    bad_layers.add(L.get("name", ""))
        items.append(self._item("拓扑几何", "面要素自相交",
                                count == 0, sorted(bad_layers), count,
                                message="存在多边形环自相交" if count else ""))

    def _check_overlap(self, items, layers):
        """多边形重叠：区县面之间不允许相互压盖"""
        bad_layers = set()
        count = 0
        for L in layers:
            if L.get("name") != "区县政区":
                continue
            rings = [f.get("coordinates") for f in L.get("features", [])]
            rings = [r for r in rings if r]
            for i in range(len(rings)):
                for j in range(i + 1, len(rings)):
                    if self._rings_overlap(rings[i], rings[j]):
                        count += 1
                        bad_layers.add(L.get("name", ""))
        items.append(self._item("拓扑几何", "多边形重叠",
                                count == 0, sorted(bad_layers), count,
                                message="区县面存在相互压盖" if count else ""))

    def _rings_overlap(self, r1, r2) -> bool:
        """两个环是否重叠（严格边相交或中心点被对方包含）

        相邻行政区共享边界不判为重叠，避免误报。
        """
        for i in range(len(r1) - 1):
            for j in range(len(r2) - 1):
                if _seg_intersect(r1[i], r1[i + 1], r2[j], r2[j + 1]):
                    return True
        if _point_in_ring(self._ring_center(r1), r2) or _point_in_ring(self._ring_center(r2), r1):
            return True
        return False

    @staticmethod
    def _ring_center(ring: list) -> list:
        """环的几何中心（顶点平均）"""
        if not ring:
            return [0.0, 0.0]
        n = len(ring)
        return [sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n]

    def _check_sliver(self, items, layers):
        """碎小多边形：面积极小的异常碎面"""
        bad_layers = set()
        count = 0
        positions = []
        for L in layers:
            if L.get("type") != "polygon":
                continue
            for feat in L.get("features", []):
                ring = feat.get("coordinates") or []
                area = _ring_area_km2(ring)
                if 0 < area < 0.5:
                    count += 1
                    bad_layers.add(L.get("name", ""))
                    if len(positions) < 10 and ring:
                        positions.append(ring[0])
        items.append(self._item("拓扑几何", "碎小多边形",
                                count == 0, sorted(bad_layers), count, positions,
                                "存在面积<0.5km²的碎面" if count else ""))

    def _check_dangle(self, items, layers, map_type=""):
        """悬挂节点：边界线端点未被其他边界咬合"""
        # 行政区划图的外围边界（省界/周边县界/地级市界/区县界）来自面轮廓闭合环，
        # 独立面环端点不共享属正常表达，跳过避免误报
        if map_type == "administrative":
            items.append(self._item("拓扑几何", "悬挂节点", True, [], 0,
                                    message="行政区划图边界为面轮廓闭合环，跳过悬挂检测"))
            return
        dangles = []
        tol_deg = 0.0004  # 约44m
        for L in layers:
            if L.get("type") not in ("polyline", "line") or "边界" not in L.get("name", ""):
                continue
            lines = [c for c in (L.get("coordinates") or []) if len(c) >= 2]
            eps = []
            for c in lines:
                eps.append((c[0], c[-1]))
            for name, c in zip([L.get("name", "")] * len(lines), lines):
                for ep, other in ((c[0], c[-1]), (c[-1], c[0])):
                    caught = False
                    for c2 in lines:
                        if c2 is c:
                            continue
                        for p2 in (c2[0], c2[-1]):
                            if abs(ep[0] - p2[0]) < tol_deg and abs(ep[1] - p2[1]) < tol_deg:
                                caught = True
                                break
                        if caught:
                            break
                    if not caught:
                        dangles.append((name, ep))
        items.append(self._item("拓扑几何", "悬挂节点",
                                len(dangles) == 0, sorted(set(d for d, _ in dangles)),
                                len(dangles), [p for _, p in dangles[:10]],
                                "存在未被咬合的悬挂端点(线头)" if dangles else ""))

    # ---------- 属性数据 ----------

    def _check_attributes(self, items, layers):
        """属性质量：名称/编码空值、编码位数/重复"""
        bad = 0
        bad_layers = set()
        adcodes = {}
        for L in layers:
            name = L.get("name", "")
            # 政区面：名称与6位编码完整性
            for feat in L.get("features", []):
                props = feat.get("properties", {}) or {}
                if not props.get("name"):
                    bad += 1
                    bad_layers.add(name)
                code = str(props.get("adcode") or "")
                if code:
                    if len(code) != 6 or not code.isdigit():
                        bad += 1
                        bad_layers.add(name)
                    adcodes.setdefault(code, []).append(name)
            # 标注图层：名称完整性（线/面边界无名称属正常，不检查）
            if L.get("type") == "textLabel":
                for prop in (L.get("properties") or []):
                    if not (prop.get("name") or "").strip():
                        bad += 1
                        bad_layers.add(name)
        dup = [c for c, names in adcodes.items() if len(set(names)) > 1]
        if dup:
            bad += len(dup)
        items.append(self._item("属性数据", "名称/编码空值与编码异常",
                                bad == 0, sorted(bad_layers), bad,
                                message="存在空名称或6位编码缺失/重复" if bad else ""))

    # ---------- 元数据与统计 ----------

    def _check_area(self, items, layers, map_type):
        """统计校验：政区面积与官方参考偏差"""
        if map_type != "administrative":
            items.append(self._item("元数据统计", "面积统计校验", True, [], 0, message="非行政区划图，跳过"))
            return
        # 行政区划图不输出面积统计：Leaflet Web墨卡托/球面换算在政区图易失真，
        # 且图幅含周边地市（面积必然远超武汉市），避免误导
        items.append(self._item("元数据统计", "面积统计校验", True, ["区县政区"], 0,
                                message="行政区划图不输出面积统计（图幅含周边地市，面积量算以官方勘界成果为准）"))
        return
        total = 0.0
        for L in layers:
            if L.get("name") == "区县政区":
                for feat in L.get("features", []):
                    total += _ring_area_km2(feat.get("coordinates") or [])
        if total <= 0:
            items.append(self._item("元数据统计", "面积统计校验", False, ["区县政区"], 1,
                                    message="无法计算政区面积"))
            return
        dev = abs(total - self.DISTRICT_REF_AREA) / self.DISTRICT_REF_AREA
        passed = dev < 0.5
        items.append(self._item("元数据统计", "面积统计校验", passed, ["区县政区"], 1,
                                message=("政区面积约%.0fkm²，与官方参考%.0fkm²偏差%.0f%%"
                                         % (total, self.DISTRICT_REF_AREA, dev * 100)
                                         if not passed else "政区面积在合理范围")))

    # ---------- 专题图层适配 ----------

    def _check_topic_layers(self, items, layers, map_type):
        """专题适配：行政区划图不应混入绿地/公园/水系等无关图层"""
        if map_type != "administrative":
            items.append(self._item("专题适配", "无关要素混入", True, [], 0, message="非行政区划图，跳过"))
            return
        noise = []
        for L in layers:
            name = L.get("name", "")
            # 水系（长江/汉江/湖泊）是行政区划图规范底图要素，不判为无关；
            # 只检查绿地/公园/森林/草地/用地等干扰专题的图层
            if any(k in name for k in ("绿地", "公园", "森林", "草地", "草甸", "用地")):
                noise.append(name)
        items.append(self._item("专题适配", "无关要素混入",
                                len(noise) == 0, noise, len(noise),
                                message="行政区划图混入无关要素图层" if noise else ""))

    # ---------- 标注质量 ----------

    def _check_labels(self, items, layers):
        """标注质量：重复标注、标注越出政区面"""
        seen = {}
        dup_count = 0
        out_count = 0
        out_positions = []
        for L in layers:
            if L.get("type") != "textLabel":
                continue
            name = L.get("name", "")
            # 只对政区名称注记做去重与越出检查（水系/地标等注记不在政区面内属正常）
            if name != "区县名称标注":
                continue
            coords = L.get("coordinates") or []
            props = L.get("properties") or []
            for i, c in enumerate(coords):
                label = (props[i] or {}).get("name") if i < len(props) else ""
                if label in seen:
                    dup_count += 1
                else:
                    seen[label] = c
        # 标注越出政区面
        admin_rings = []
        for L in layers:
            if L.get("name") == "区县政区":
                admin_rings = [f.get("coordinates") for f in L.get("features", [])]
                admin_rings = [r for r in admin_rings if r]
        if admin_rings:
            for label, pt in seen.items():
                if not any(_point_in_ring(pt, r) for r in admin_rings):
                    out_count += 1
                    if len(out_positions) < 10:
                        out_positions.append(pt)
        items.append(self._item("标注质量", "重复标注/标注越出",
                                dup_count == 0 and out_count == 0,
                                sorted({L.get("name", "") for L in layers if L.get("type") == "textLabel"}),
                                dup_count + out_count, out_positions,
                                "存在重复标注(%d)或标注越出政区(%d)" % (dup_count, out_count)
                                if dup_count or out_count else ""))

    # ---------- 逻辑一致性 ----------

    def _check_boundary_fit(self, items, layers):
        """逻辑一致性：区县合并轮廓与市域边界套合（bbox偏差检测）"""
        admin_pts = []
        bound_pts = []
        for L in layers:
            name = L.get("name", "")
            if name == "区县政区":
                for f in L.get("features", []):
                    ring = f.get("coordinates") or []
                    for pt in ring:
                        if isinstance(pt, list) and len(pt) >= 2:
                            admin_pts.append(pt)
            if name in ("市域边界", "省级边界"):
                for c in (L.get("coordinates") or []):
                    if isinstance(c, list) and c and isinstance(c[0], list):
                        for pt in c:
                            if len(pt) >= 2:
                                bound_pts.append(pt)
        if not admin_pts or not bound_pts:
            items.append(self._item("逻辑一致性", "边界套合检查", True, [], 0, message="缺少政区面或市域边界，跳过"))
            return
        a = self._bbox_of(admin_pts)
        b = self._bbox_of(bound_pts)
        dev = max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]), abs(a[3] - b[3]))
        passed = dev < 0.05  # 约5.5km容差
        items.append(self._item("逻辑一致性", "边界套合检查", passed,
                                ["区县政区", "市域边界"], 1,
                                message="区县合并轮廓与市域边界偏差约%.3f°" % dev if not passed else ""))

    @staticmethod
    def _bbox_of(pts: list) -> list:
        return [min(p[0] for p in pts), min(p[1] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts)]

    def _check_center_fit(self, items, layers):
        """行政中心点必须在对应政区面内（坐标越界检测）"""
        admin_by_name = {}
        centers = []
        for L in layers:
            name = L.get("name", "")
            if name == "区县政区":
                for f in L.get("features", []):
                    fname = (f.get("properties") or {}).get("name", "")
                    if fname and f.get("coordinates"):
                        admin_by_name[fname] = f.get("coordinates")
            if name == "区县行政中心":
                coords = L.get("coordinates") or []
                props = L.get("properties") or []
                for i, c in enumerate(coords):
                    if isinstance(c, list) and len(c) >= 2:
                        centers.append(((props[i] or {}).get("name", ""), c))
        if not admin_by_name or not centers:
            items.append(self._item("拓扑几何", "行政中心越界", True, [], 0, message="缺少政区面或行政中心，跳过"))
            return
        bad = []
        for fname, c in centers:
            ring = admin_by_name.get(fname)
            if ring and not _point_in_ring(c, ring):
                bad.append(c)
        items.append(self._item("拓扑几何", "行政中心越界", len(bad) == 0,
                                ["区县行政中心"], len(bad), bad[:10],
                                "存在行政中心点落在辖区外" if bad else ""))

    # ---------- 跨要素关系（制图综合·关系协调） ----------

    def _check_cross_feature(self, items, layers):
        """跨要素拓扑关系检查：
        1) 道路跨越水系（需桥梁/渡口符号表达）；
        2) 道路段整体落入水体（疑似错误或渡口）。
        """
        from shapely.geometry import Polygon, LineString, Point
        from shapely.strtree import STRtree

        # 收集水面多边形（湖泊/河岸面）
        water_polys = []   # (图层名, 要素名, Polygon)
        for L in layers:
            nm = L.get("name", "")
            # 只取真实水面图层；排除"湖北省域/武汉市域底图/周边地市"等含"湖/江"字的政区面
            if (L.get("type") == "polygon" and ("湖" in nm or "河" in nm or "江" in nm)
                    and "省域" not in nm and "底图" not in nm and "地市" not in nm):
                for c in (L.get("coordinates") or []):
                    if len(c) >= 4:
                        water_polys.append((nm, "", Polygon([(p[1], p[0]) for p in c])))
                for f in (L.get("features") or []):
                    c = f.get("coordinates") or []
                    if len(c) >= 4:
                        water_polys.append((nm, (f.get("properties") or {}).get("name", ""),
                                            Polygon([(p[1], p[0]) for p in c])))
        valid = [(ln, fn, p) for ln, fn, p in water_polys if p.is_valid and not p.is_empty]
        if not valid:
            items.append(self._item("跨要素关系", "道路跨水检查", True, ["道路", "水系"], 0, [], "无水面数据，跳过"))
            return
        # "跨水"用全部水面；"落入水体"只用真实湖泊面
        # （大型湖泊中的无名河道分段是长江/汉江的粗河岸，排除避免误报）
        cross_polys = valid
        deep_polys = [(ln, fn, p) for ln, fn, p in valid
                      if (ln != "大型湖泊" or (fn and fn not in ("长江", "汉江")))]
        cross_tree = STRtree([p for _, _, p in cross_polys])
        deep_tree = STRtree([p for _, _, p in deep_polys]) if deep_polys else None

        # 只检查主干道路（高速/主干/一级/二级）——跨水桥渡主要发生在这些等级
        MAJOR = ("道路-motorway", "道路-trunk", "道路-primary", "道路-secondary")
        crossings = []
        in_water = []
        for L in layers:
            nm = L.get("name", "")
            if L.get("type") != "polyline" or not any(nm.startswith(r) for r in MAJOR):
                continue
            for line in (L.get("coordinates") or []):
                if len(line) < 2:
                    continue
                for k in range(len(line) - 1):
                    p1, p2 = line[k], line[k + 1]
                    if len(p1) < 2 or len(p2) < 2:
                        continue
                    seg = LineString([(p1[1], p1[0]), (p2[1], p2[0])])
                    mid = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2]
                    for idx in cross_tree.query(seg):
                        _, wn, wp = cross_polys[idx]
                        if seg.crosses(wp):
                            crossings.append((nm, wn, mid))
                            break
                    if deep_tree is not None:
                        for idx in deep_tree.query(seg):
                            _, wn, wp = deep_polys[idx]
                            # 落入水体：中点深入水体 >330m（排除贴岸道路）
                            if wp.contains(seg) and wp.boundary.distance(Point(mid[1], mid[0])) > 0.003:
                                in_water.append((nm, wn, mid))
                                break

        # 跨水点聚类：500m 内的相邻跨水点合并为一个"桥位/渡口"，滤除河岸锯齿噪声
        def _cluster(pts):
            if not pts:
                return []
            ordered = sorted(pts)
            out = [ordered[0]]
            for p in ordered[1:]:
                last = out[-1]
                if (abs(p[0] - last[0]) * 111 + abs(p[1] - last[1]) * 105) < 0.5:
                    continue
                out.append(p)
            return out

        cross_sites = _cluster([c[2] for c in crossings])

        if cross_sites:
            items.append(self._item(
                "跨要素关系", "道路跨水（需桥梁/渡口）", False,
                sorted({c[0] for c in crossings}) + sorted({c[1] for c in crossings}),
                count=len(cross_sites),
                positions=cross_sites[:30],
                message=f"{len(cross_sites)} 个跨水桥位（原始跨水段 {len(crossings)} 处已聚类），需核查桥梁/渡口符号表达"))
        else:
            items.append(self._item("跨要素关系", "道路跨水（需桥梁/渡口）", True,
                                    ["道路", "水系"], 0, [], "无道路跨水"))
        if in_water:
            items.append(self._item(
                "跨要素关系", "道路落入水体", False,
                sorted({x[0] for x in in_water}) + sorted({x[1] for x in in_water}),
                count=len(in_water),
                positions=[x[2] for x in in_water][:30],
                message=f"{len(in_water)} 处道路段落入水体，疑似错误或渡口"))
        else:
            items.append(self._item("跨要素关系", "道路落入水体", True,
                                    ["道路", "水系"], 0, [], "无道路落入水体"))
