# -*- coding: utf-8 -*-
"""几何工具函数（纯函数，无业务依赖）

集中散落在各 service 中的通用几何计算，供 geo_service / quality_service /
local_geo_service / map_service 等复用，消除重复实现。

约定：
- 坐标统一使用 [lat, lng]（纬度在前，经度在后）；
- 环（ring）为闭合点列表 [[lat, lng], ...]；
- 距离/面积使用球面近似（地球半径 R=6371km）。
"""
import math

R_EARTH_KM = 6371.0


def _point_in_ring(pt: list, ring: list) -> bool:
    """射线法判断点 [lat, lng] 是否在环内（经纬度平面近似）。

    与 map_service 原实现一致，带除零保护。
    """
    x, y = pt[1], pt[0]
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][1], ring[i][0]
        xj, yj = ring[j][1], ring[j][0]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _ring_area_km2(ring: list) -> float:
    """环的球面面积（km²）"""
    if len(ring) < 3:
        return 0.0
    area = 0.0
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        la1, lo1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        la2, lo2 = math.radians(ring[j][0]), math.radians(ring[j][1])
        area += (lo2 - lo1) * (2 + math.sin(la1) + math.sin(la2))
    return abs(area * R_EARTH_KM * R_EARTH_KM / 2.0)


def _convex_hull(points: list) -> list:
    """Andrew 单调链凸包：输入 [lat, lng] 点列表，输出闭合凸包环"""
    pts = sorted({(p[0], p[1]) for p in points})
    if len(pts) <= 3:
        return [list(p) for p in pts] + [list(pts[0])]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return [list(p) for p in hull] + [list(hull[0])]


def _interior_point(ring: list) -> list:
    """多边形内点：质心优先，质心在环外时用扫描线多纬度取内区间中点"""
    if not ring:
        return [0.0, 0.0]
    n = len(ring)
    ys = [p[0] for p in ring]
    xs = [p[1] for p in ring]
    cy = sum(ys) / n
    cx = sum(xs) / n
    # 候选纬度：质心纬度 + 南北边界 1/4、1/2、3/4 处
    cand_lats = [cy]
    for frac in (0.5, 0.25, 0.75, 0.35, 0.65):
        cand_lats.append(min(ys) + (max(ys) - min(ys)) * frac)
    for lat in cand_lats:
        if _point_in_ring([lat, cx], ring):
            return [lat, cx]
        crossings = []
        for i in range(n):
            p1, p2 = ring[i], ring[(i + 1) % n]
            if (p1[0] <= lat < p2[0]) or (p2[0] <= lat < p1[0]):
                x = p1[1] + (lat - p1[0]) * (p2[1] - p1[1]) / (p2[0] - p1[0])
                crossings.append(x)
        crossings.sort()
        if len(crossings) >= 2:
            return [lat, (crossings[0] + crossings[1]) / 2]
    return [cy, cx]


def _haversine(p1: list, p2: list) -> float:
    """两点球面距离（km）"""
    la1, lo1 = math.radians(p1[0]), math.radians(p1[1])
    la2, lo2 = math.radians(p2[0]), math.radians(p2[1])
    dla, dlo = la2 - la1, lo2 - lo1
    a = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R_EARTH_KM * math.asin(math.sqrt(a))


def _line_len_km(line: list) -> float:
    """折线总长度（km）"""
    if len(line) < 2:
        return 0.0
    return sum(_haversine(line[i], line[i + 1]) for i in range(len(line) - 1))
