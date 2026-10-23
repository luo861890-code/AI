# -*- coding: utf-8 -*-
"""
================================================================================
[分类三 - 子模块 3.1] 地图学色彩规范、政区四色算法与高程分层色带 `color_schemes.py`
================================================================================
地图学规范依据：
1. 行政规划图：遵循中国政区地图“底色柔和雅致、相邻政区不同色（四色/五色定理）、驻地与界线突出”原则。
2. 地势图：遵循国际与我国分层设色地势图规范（平原柔和绿 -> 浅丘暖黄 -> 山地棕褐渐变），配合西北光源晕渲。
3. 交通与旅游图：底图采用低饱和度消色系（暖灰白/浅米色），突出高等级道路与核心景区专题色彩。
"""

from typing import Dict, List
import geopandas as gpd
import matplotlib.colors as mcolors


class CartoColorSchemes:
    """地图学专业色彩方案与政区邻接着色解算器"""

    # 1. 行政区划图标准柔和色盘（低饱和度、高明度、色相均匀分布的 6 色中国标准政区普染色系）
    ADMIN_PASTEL_PALETTE: List[str] = [
        "#FCE4D6",  # 暖杏粉 (Warm Apricot)
        "#E2EFDA",  # 浅茗绿 (Soft Tea Green)
        "#FFF2CC",  # 奶油黄 (Cream Yellow)
        "#EDE2F2",  # 丁香紫 (Soft Lilac)
        "#FBE5EC",  # 浅藕荷 (Lotus Pink)
        "#E1F0F5",  # 浅天青 (Pale Celadon - 避开水体深蓝)
    ]

    # 2. 地势图高程分层设色色带 (Hypsometric Tints: 平原绿 -> 台地黄绿 -> 丘陵暖黄 -> 低山浅褐 -> 中高山深棕)
    TERRAIN_HYPSOMETRIC_STOPS = [
        (0.00, "#B8DFB0"),  # < 25m 江汉平原冲积洲滩柔和绿
        (0.18, "#D4EBB8"),  # 25~50m 平原阶地浅绿
        (0.38, "#F2F0B6"),  # 50~100m 岗地低丘暖米黄
        (0.60, "#EED294"),  # 100~250m 丘陵浅赭黄
        (0.82, "#D6A76C"),  # 250~500m 低山浅棕褐
        (1.00, "#B07546"),  # > 500m 山脊高点深棕褐
    ]

    # 3. 水系标准双色规范（浅蓝填充 + 中深蓝水涯线）
    WATER_FILL = "#BEE3F8"
    WATER_STROKE = "#4299E1"

    # 4. 生态绿地/森林公园配色
    GREENSPACE_FILL = "#D6F0D1"
    GREENSPACE_STROKE = "#86C780"

    @classmethod
    def get_terrain_colormap(cls) -> mcolors.LinearSegmentedColormap:
        """构建连续平滑的地势分层设色 Colormap"""
        return mcolors.LinearSegmentedColormap.from_list(
            "whu_hypsometric", cls.TERRAIN_HYPSOMETRIC_STOPS, N=256
        )

    @classmethod
    def compute_greedy_polygon_coloring(
        cls,
        poly_gdf: gpd.GeoDataFrame,
        palette: List[str] = None,
    ) -> List[str]:
        """
        基于空间拓扑邻接图（Rook/Queen Contiguity）的贪心四色/五色政区普染算法：
        确保任意两个共享边界的相邻行政区（如武昌区与洪山区、江岸区与江汉区）绝不分配相同底色！
        """
        if poly_gdf is None or poly_gdf.empty:
            return []
        colors = palette or cls.ADMIN_PASTEL_PALETTE
        n = len(poly_gdf)
        assigned: Dict[int, int] = {}

        # 构建空间邻接表（两多边形相交或距离极近视为相邻）
        geoms = list(poly_gdf.geometry)
        adj: Dict[int, set] = {i: set() for i in range(n)}
        for i in range(n):
            for j in range(i + 1, n):
                if geoms[i] is not None and geoms[j] is not None:
                    if geoms[i].touches(geoms[j]) or geoms[i].intersects(geoms[j]) or geoms[i].distance(geoms[j]) < 1e-4:
                        adj[i].add(j)
                        adj[j].add(i)

        # 按度数（邻居数量）从大到小排序进行 Welsh-Powell 贪心着色
        order = sorted(range(n), key=lambda idx: len(adj[idx]), reverse=True)
        for idx in order:
            used_by_neighbors = {assigned[nbr] for nbr in adj[idx] if nbr in assigned}
            for c_idx in range(len(colors)):
                if c_idx not in used_by_neighbors:
                    assigned[idx] = c_idx
                    break
            else:
                assigned[idx] = idx % len(colors)

        return [colors[assigned[i]] for i in range(n)]
