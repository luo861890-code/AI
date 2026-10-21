# -*- coding: utf-8 -*-
"""从 SRTM 30m DEM 生成武汉等高线（含制图综合：舍谷/扩谷/鞍部保持）。

数据源: AWS Open Data SRTMGL1 .hgt 瓦片 (backend/data/dem/N*E*.hgt)
输出:   backend/data/geo/wuhan_contours.geojson

用法:
  python tools/generate_contours.py [--interval 20] [--index-every 100]

制图综合说明:
  1) 舍谷   : Douglas-Peucker 化简删除微小谷地锯齿；极小闭合圈(山头/凹地)保留。
  2) 扩谷   : 顶点转折角 < 135° 的典型弯曲(谷地/山脊特征)标记为受保护顶点，
              化简时保留，避免代表性谷地弯形丢失。
  3) 鞍部保持: 从 DEM 曲率(dxx*dyy<0)检测鞍部像素，等高线经过鞍部附近的
              顶点标记为受保护顶点，简化后鞍部形态不消失。
  4) 遇水断开: 湖泊面与主要河流缓冲区置 NaN，等高线不在水域内穿越
              (符合制图规范"等高线遇河断开")。
"""
import argparse
import json
import math
import os

import numpy as np
from shapely.geometry import shape
from shapely.ops import unary_union
from PIL import Image, ImageDraw


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEM_DIR = os.path.join(ROOT, "backend", "data", "dem")
GEO_DIR = os.path.join(ROOT, "backend", "data", "geo")
OUT_PATH = os.path.join(GEO_DIR, "wuhan_contours.geojson")

TILE_SIZE = 3601  # SRTMGL1 每瓦片 3601x3601
DEG = 1.0 / 3600.0


# ---------------------------------------------------------------- DEM 拼接
def load_tile(lat, lon):
    """读取一个 .hgt 瓦片 (big-endian int16, 3601x3601)。"""
    p = os.path.join(DEM_DIR, f"N{lat:02d}E{lon:03d}.hgt")
    a = np.fromfile(p, dtype=">i2").reshape(TILE_SIZE, TILE_SIZE).astype(np.float32)
    a[a <= -1000] = np.nan
    a[a == 0] = np.nan
    return a


def build_mosaic(lat_min, lat_max, lon_min, lon_max):
    """按武汉 bbox 裁剪拼接 3x3 瓦片，返回 dem, lons, lats（像素中心坐标）。"""
    lat0, lat1 = math.floor(lat_min), math.floor(lat_max)
    lon0, lon1 = math.floor(lon_min), math.floor(lon_max)
    rows, cols = [], []
    for la in range(lat1, lat0 - 1, -1):      # 从北向南
        row = load_tile(la, lon0)
        for lo in range(lon0 + 1, lon1 + 1):
            right = load_tile(la, lo)
            row = np.concatenate([row[:, :-1], right], axis=1)
        rows.append(row)
    dem = rows[0]
    for r in rows[1:]:
        dem = np.concatenate([dem, r[1:, :]], axis=0)

    n_row, n_col = dem.shape
    lons = lon0 + (np.arange(n_col) + 0.5) * DEG
    # 瓦片 N{lat1} 覆盖 [lat1, lat1+1]，行 0 位于北边 lat1+1
    lats = (lat1 + 1) - (np.arange(n_row) + 0.5) * DEG
    # 裁剪到 bbox（含边缘）
    r_sel = (lats >= lat_min) & (lats <= lat_max)
    c_sel = (lons >= lon_min) & (lons <= lon_max)
    return dem[np.ix_(r_sel, c_sel)], lons[c_sel], lats[r_sel]


# ---------------------------------------------------------------- 空洞填充
def fill_small_voids(dem, iterations=10):
    """仅填补孤立小洞（3x3 邻域内有效单元>=6 的 NaN，如 1-2 像素空洞）。

    大面积空洞（河流/湖泊/边界外）邻居少，不会被误填，
    保证"等高线遇水断开"的制图规范。
    """
    for _ in range(iterations):
        valid = ~np.isnan(dem)
        if valid.all():
            break
        pad = np.pad(np.where(valid, dem, 0.0), 1, mode="constant")
        pv = np.pad(valid.astype(np.float32), 1, mode="constant")
        total = np.zeros_like(dem)
        cnt = np.zeros_like(dem)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                total += pad[1 + di:1 + di + dem.shape[0], 1 + dj:1 + dj + dem.shape[1]]
                cnt += pv[1 + di:1 + di + dem.shape[0], 1 + dj:1 + dj + dem.shape[1]]
        fill = total / np.maximum(cnt, 1)
        dem = np.where(np.isnan(dem) & (cnt >= 6), fill, dem)
    return dem


def downsample_block_mean(dem, factor=4):
    """块内均值降采样（忽略 NaN），返回降采样后的 DEM 与中心坐标。"""
    n_row = dem.shape[0] // factor * factor
    n_col = dem.shape[1] // factor * factor
    d = dem[:n_row, :n_col]
    nan = np.isnan(d)
    d0 = np.where(nan, 0.0, d)
    r, c = n_row // factor, n_col // factor
    mean = d0.reshape(r, factor, c, factor).mean(axis=(1, 3))
    cnt = (~nan).reshape(r, factor, c, factor).sum(axis=(1, 3))
    return np.where(cnt > 0, mean, np.nan), r, c


def dilate_bool(mask, radius=1):
    """对 bool 掩膜做方形膨胀（消除栅格化边缘的半像素误差）。"""
    m = mask.astype(np.uint8)
    for _ in range(radius):
        pad = np.pad(m, 1, mode="constant")
        out = np.zeros_like(m)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                out |= pad[1 + di:1 + di + m.shape[0], 1 + dj:1 + dj + m.shape[1]]
        m = out
    return m.astype(bool)


# ---------------------------------------------------------------- 鞍部检测
def detect_saddles(dem):
    """dxx*dyy<0 的像素判为鞍部（一阶偏导符号相反方向）。返回 {(row,col)}。"""
    valid = ~np.isnan(dem)
    d = np.where(valid, dem, 0.0)
    dxx = d[2:, 1:-1] - 2 * d[1:-1, 1:-1] + d[:-2, 1:-1]
    dyy = d[1:-1, 2:] - 2 * d[1:-1, 1:-1] + d[1:-1, :-2]
    saddle = (dxx * dyy < 0) & valid[1:-1, 1:-1]
    rs, cs = np.nonzero(saddle)
    return set(zip(rs.tolist(), cs.tolist()))


def rasterize_geoms(geoms, r, c, lon_min, lon_max, lat_min, lat_max, line_width=0):
    """把多边形(面)/线状几何栅格化为 bool 掩膜（PIL，速度远快于逐点 contains）。"""
    img = Image.new("L", (c, r), 0)
    draw = ImageDraw.Draw(img)
    span_x = max(lon_max - lon_min, 1e-9)
    span_y = max(lat_max - lat_min, 1e-9)

    def to_px(x, y):
        return ((x - lon_min) / span_x * (c - 1), (lat_max - y) / span_y * (r - 1))

    for g in geoms:
        if g.geom_type == "Polygon":
            rings = [g.exterior] + list(g.interiors)
        elif g.geom_type == "MultiPolygon":
            rings = []
            for p in g.geoms:
                rings += [p.exterior] + list(p.interiors)
        elif g.geom_type in ("LineString", "MultiLineString"):
            lines = [g] if g.geom_type == "LineString" else list(g.geoms)
            for ln in lines:
                pts = [to_px(x, y) for x, y in ln.coords]
                if len(pts) >= 2:
                    draw.line(pts, fill=255, width=max(line_width, 1), joint="curve")
            continue
        else:
            continue
        for ring in rings:
            pts = [to_px(x, y) for x, y in ring.coords]
            if len(pts) >= 3:
                draw.polygon(pts, fill=255)
    return np.asarray(img, dtype=bool)


# ---------------------------------------------------------------- 化简/平滑
def _seg_dist(p, a, b):
    """点到线段距离（度为单位）。"""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _dp_simplify(pts, tol, protected):
    """带受保护顶点的 Douglas-Peucker 化简。"""
    n = len(pts)
    keep = [False] * n
    keep[0] = keep[-1] = True
    for i in protected:
        if 0 < i < n - 1:
            keep[i] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        best_d, best_k = -1.0, -1
        for k in range(i + 1, j):
            d = _seg_dist(pts[k], pts[i], pts[j])
            if d > best_d:
                best_d, best_k = d, k
        if best_d > tol:
            keep[best_k] = True
            stack.append((i, best_k))
            stack.append((best_k, j))
    return [p for p, k in zip(pts, keep) if k]


def simplify_with_anchors(pts, tol, protected_idx):
    """按受保护顶点切段后分别化简，保证鞍部/谷地特征点不被删除。"""
    anchors = sorted({0, len(pts) - 1} | {i for i in protected_idx if 0 < i < len(pts) - 1})
    out = [pts[0]]
    for a, b in zip(anchors, anchors[1:]):
        if b - a <= 1:
            if b < len(pts):
                out.append(pts[b])
            continue
        seg = _dp_simplify(pts[a:b + 1], tol, {i - a for i in protected_idx if a < i < b})
        out.extend(seg[1:])
    return out


def _turn_angle(pts, i):
    """顶点 i 的转角（度），尖锐弯曲返回小角度。"""
    p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
    v1 = (p0[0] - p1[0], p0[1] - p1[1])
    v2 = (p2[0] - p1[0], p2[1] - p1[1])
    d = math.hypot(*v1) * math.hypot(*v2)
    if d == 0:
        return 180.0
    c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / d))
    return math.degrees(math.acos(c))


def chaikin(pts, iterations=1, ratio=0.25, closed=False):
    """Chaikin 角点平滑（轻量，1 次迭代保持形态）。"""
    if len(pts) < 3:
        return pts
    seq = pts
    for _ in range(iterations):
        out = []
        n = len(seq)
        for i in range(n):
            p0 = seq[i]
            p1 = seq[(i + 1) % n]
            out.append([p0[0] + (p1[0] - p0[0]) * ratio, p0[1] + (p1[1] - p0[1]) * ratio])
            out.append([p0[0] + (p1[0] - p0[0]) * (1 - ratio), p0[1] + (p1[1] - p0[1]) * (1 - ratio)])
        seq = out
    if closed:
        seq = seq + [seq[0]]
    return seq


def length_km(pts):
    """折线长度（km），按纬度粗略换算。"""
    s = 0.0
    for a, b in zip(pts, pts[1:]):
        dlat = (a[1] - b[1]) * 111.0
        dlon = (a[0] - b[0]) * 111.0 * math.cos(math.radians((a[1] + b[1]) / 2))
        s += math.hypot(dlat, dlon)
    return s


def generalize_contour(pts, tol, saddle_keys, dlat, dlon, lat_max, lon_min, min_km):
    """单条等高线：保护鞍部/尖弯 → 分段 DP 化简 → 轻平滑 → 长度过滤。"""
    pts = [list(p) for p in pts]
    if len(pts) < 4:
        return None
    closed = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-9
    if closed:
        pts = pts[:-1]
    # 闭合环多为山头/凹地（必须保留），阈值放宽；开放碎线多为平原噪声，阈值收紧
    if closed:
        min_km = min(min_km * 0.4, 0.25)

    protected = set()
    angle = {}
    for i in range(1, len(pts) - 1):
        a = _turn_angle(pts, i)
        angle[i] = a
        if a < 135.0:                            # 典型谷地/山脊弯曲 -> 保留
            protected.add(i)
    # 鞍部像素邻域内的顶点受保护（半径1px，避免过度保护导致无法化简）
    for i, (x, y) in enumerate(pts):
        row = int(round((lat_max - y) / dlat))
        col = int(round((x - lon_min) / dlon))
        hit = False
        for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            if (row + dr, col + dc) in saddle_keys:
                hit = True
                break
        if hit:
            protected.add(i)

    # 保护比例上限 35%：超过时按“尖弯优先(谷地/山脊特征)、鞍部其次”保留最强特征
    cap = max(3, int(len(pts) * 0.35))
    if len(protected) > cap:
        ranked = sorted(protected, key=lambda i: angle.get(i, 180.0))
        protected = set(ranked[:cap])

    simp = simplify_with_anchors(pts, tol, protected)
    if len(simp) < 3:
        return None
    if closed:
        simp = chaikin(simp, 1, 0.25, closed=True)
    else:
        simp = chaikin(simp, 1, 0.25, closed=False)
    if length_km(simp) < min_km:
        return None
    return simp


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=20.0, help="等高距(米)")
    ap.add_argument("--index-every", type=float, default=100.0, help="计曲线间隔(米)")
    ap.add_argument("--tol-minor", type=float, default=0.00055, help="首曲线化简容差(度)")
    ap.add_argument("--tol-index", type=float, default=0.00038, help="计曲线化简容差(度)")
    ap.add_argument("--min-len-minor", type=float, default=0.3, help="首曲线最短长度(km)")
    ap.add_argument("--min-len-index", type=float, default=0.8, help="计曲线最短长度(km)")
    args = ap.parse_args()

    # 武汉边界
    with open(os.path.join(GEO_DIR, "wuhan_districts.geojson"), encoding="utf-8") as f:
        dist = json.load(f)
    raw_boundary = unary_union([shape(feat["geometry"]) for feat in dist["features"]])
    boundary = raw_boundary.buffer(0.002)  # 掩膜边界外留 200m 余量
    minx, miny, maxx, maxy = boundary.bounds

    print(f"[DEM] bbox: lon {minx:.3f}-{maxx:.3f}, lat {miny:.3f}-{maxy:.3f}", flush=True)
    dem, lons, lats = build_mosaic(miny - 0.03, maxy + 0.03, minx - 0.03, maxx + 0.03)
    print(f"[DEM] mosaic shape {dem.shape}", flush=True)

    # 30m -> ~120m 降采样：制图比例尺下等高线无需 30m 细节，速度提升数十倍
    dem, r_new, c_new = downsample_block_mean(dem, factor=4)
    lons = lons[:c_new * 4:4] + (3 / 2) * (lons[1] - lons[0])
    lats = lats[:r_new * 4:4] + (3 / 2) * (lats[1] - lats[0])
    print(f"[DEM] downsampled shape {dem.shape} (~120m)", flush=True)

    # 边界掩膜 + 水体掩膜（等高线遇河/湖断开）
    r_n, c_n = dem.shape
    lon_min_g, lon_max_g = float(lons[0]), float(lons[-1])
    lat_min_g, lat_max_g = float(lats[-1]), float(lats[0])
    inside = rasterize_geoms(
        list(boundary.geoms) if boundary.geom_type == "MultiPolygon" else [boundary],
        r_n, c_n, lon_min_g, lon_max_g, lat_min_g, lat_max_g,
    )
    dem = np.where(inside, dem, np.nan)

    water_mask = np.zeros(dem.shape, dtype=bool)
    wpath = os.path.join(GEO_DIR, "wuhan_water.geojson")
    if os.path.exists(wpath):
        with open(wpath, encoding="utf-8") as f:
            wdata = json.load(f)
        lake_geoms = []
        river_geoms = []
        for feat in wdata.get("features", []):
            g = shape(feat["geometry"])
            if g.geom_type in ("Polygon", "MultiPolygon"):
                lake_geoms.append(g)
            elif g.geom_type in ("LineString", "MultiLineString"):
                river_geoms.append(g)
        if lake_geoms:
            water_mask |= rasterize_geoms(
                lake_geoms, r_n, c_n, lon_min_g, lon_max_g, lat_min_g, lat_max_g,
            )
        if river_geoms:
            water_mask |= rasterize_geoms(
                river_geoms, r_n, c_n, lon_min_g, lon_max_g, lat_min_g, lat_max_g,
                line_width=3,   # ~180m 河道缓冲
            )
    # 膨胀1像素：抵消 120m 栅格化边缘误差，等高线在湖岸外自然收住
    water_mask = dilate_bool(water_mask, radius=1)
    dem = np.where(water_mask, np.nan, dem)

    dem = fill_small_voids(dem, iterations=8)
    valid = ~np.isnan(dem)
    print(f"[DEM] valid {int(valid.sum())}/{dem.size}, ele {np.nanmin(dem):.0f}~{np.nanmax(dem):.0f}m", flush=True)

    # 严格边界（未缓冲）：等高线最终裁剪到行政边界内，避免越界
    strict_boundary = raw_boundary
    from shapely.geometry import LineString as _LS, MultiLineString as _MLS

    saddle_keys = detect_saddles(dem)
    print(f"[DEM] saddle pixels: {len(saddle_keys)}", flush=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    levels = np.arange(
        math.ceil(np.nanmin(dem) / args.interval) * args.interval,
        np.nanmax(dem),
        args.interval,
    )
    print(f"[Contour] levels: {len(levels)} ({levels[0]:.0f}~{levels[-1]:.0f}m, 间距{args.interval:.0f}m)", flush=True)

    dlat = lats[0] - lats[1]
    dlon = lons[1] - lons[0]
    lat_max = lats[0]
    lon_min = lons[0]

    features = []
    cs = plt.contour(lons, lats, dem, levels=levels)
    for lev, segs in zip(cs.levels, cs.allsegs):
        is_index = abs(lev % args.index_every) < 1e-6
        tol = args.tol_index if is_index else args.tol_minor
        min_km = args.min_len_index if is_index else args.min_len_minor
        count = 0
        for seg in segs:
            if len(seg) < 4:
                continue
            pts = generalize_contour(seg, tol, saddle_keys, dlat, dlon, lat_max, lon_min, min_km)
            if not pts:
                continue
            coords = [[round(float(x), 6), round(float(y), 6)] for x, y in pts]
            ls = _LS(coords)
            clipped = ls.intersection(strict_boundary)
            clipped_parts = []
            if clipped.is_empty:
                continue
            if clipped.geom_type == "LineString":
                clipped_parts = [clipped]
            elif clipped.geom_type == "MultiLineString":
                clipped_parts = list(clipped.geoms)
            elif clipped.geom_type == "GeometryCollection":
                clipped_parts = [g for g in clipped.geoms if g.geom_type in ("LineString", "MultiLineString")]
                flat = []
                for g in clipped_parts:
                    if g.geom_type == "MultiLineString":
                        flat.extend(g.geoms)
                    else:
                        flat.append(g)
                clipped_parts = flat
            for part in clipped_parts:
                if len(part.coords) < 2:
                    continue
                c2 = [[round(float(x), 6), round(float(y), 6)] for x, y in part.coords]
                if length_km(c2) < min_km * 0.6:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {"ele": int(round(float(lev))), "index": 1 if is_index else 0},
                    "geometry": {"type": "LineString", "coordinates": c2},
                })
                count += 1
        print(f"  level {lev:6.0f}m {'计曲线' if is_index else '首曲线'} -> {count} 条", flush=True)
    plt.close(cs.figure)

    out = {
        "type": "FeatureCollection",
        "name": "wuhan_contours",
        "interval_m": args.interval,
        "index_every_m": args.index_every,
        "source": "SRTMGL1 (AWS Open Data)",
        "features": features,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    idx = sum(1 for ft in features if ft["properties"]["index"])
    print(f"[Contour] 完成: 共 {len(features)} 条 (计曲线 {idx}, 首曲线 {len(features)-idx}) -> {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
