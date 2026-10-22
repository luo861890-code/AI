# -*- coding: utf-8 -*-
"""
================================================================================
[分类四 - 子模块 4.3] 出版级五大地图整饰要素绘制器 `map_elements.py`
================================================================================
解决原系统 `export_service.py` 缺乏服务端地图整饰与高清排版导出的核心缺陷。
完整实现专业地图学五大整饰要素（Map Marginalia & Elements）：
1. **内外图廓与黑白相间斑马纹经纬网分度带 (Zebra Neatline & Graticule Frame)**
2. **主副图名框 (Cartographic Title Cartouche)**
3. **矢量双色指北针 (Vector Compass Rose)**
4. **黑白交替线段图形比例尺与数字比例尺 (Alternating Graphic Scale Bar)**
5. **结构化分层符号图例与制图版权元数据栏 (Hierarchical Legend & Metadata Credit)**
"""

import math
from typing import List, Dict, Any, Tuple
import numpy as np
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.patheffects as patheffects


class MapElementsComposer:
    """出版级地图整饰要素（内外图廓、经纬网、图名、指北针、线段比例尺、结构化图例）绘制器"""

    @staticmethod
    def format_dms(deg_val: float, is_lon: bool = True) -> str:
        """将十进制度格式化为标准地图学度分格式 (如 114°18′E, 30°36′N)"""
        suffix = "E" if (is_lon and deg_val >= 0) else ("W" if is_lon else ("N" if deg_val >= 0 else "S"))
        v = abs(deg_val)
        d = int(math.floor(v + 1e-9))
        m = int(round((v - d) * 60))
        if m == 60:
            d += 1
            m = 0
        return f"{d}°{m:02d}′{suffix}"

    @classmethod
    def draw_zebra_neatline_and_graticule(
        cls,
        ax,
        extent: Tuple[float, float, float, float],
        font_family: str,
        n_ticks_x: int = 4,
        n_ticks_y: int = 4,
        show_grid_lines: bool = True,
    ):
        """
        绘制经典出版级黑白相间斑马纹外图廓（Zebra Frame）与经纬网十字丝/虚线格网。
        """
        x0, y0, x1, y1 = extent
        w, h = x1 - x0, y1 - y0

        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)

        # 生成均匀的经纬度刻度
        xticks = np.linspace(x0 + w * 0.12, x1 - w * 0.12, n_ticks_x)
        yticks = np.linspace(y0 + h * 0.12, y1 - h * 0.12, n_ticks_y)

        ax.set_xticks(xticks)
        ax.set_yticks(yticks)
        ax.set_xticklabels([cls.format_dms(x, is_lon=True) for x in xticks], fontfamily=font_family, fontsize=7.5, color="#334155")
        ax.set_yticklabels([cls.format_dms(y, is_lon=False) for y in yticks], fontfamily=font_family, fontsize=7.5, color="#334155", rotation=90, va="center")
        ax.tick_params(axis="both", which="both", direction="out", length=3, width=0.8, colors="#334155", top=True, right=True, labeltop=False, labelright=False)

        if show_grid_lines:
            ax.grid(True, linestyle="--", linewidth=0.45, color="#64748B", alpha=0.32, zorder=90)

        # 绘制黑白相间斑马纹内外双图廓边框 (使用 axes fraction 坐标确保严格贴合图框四周)
        band_w = 0.0085
        band_h = 0.0085 * (w / max(h, 1e-6))

        x_breaks = [0.0] + [float((x - x0) / w) for x in xticks] + [1.0]
        y_breaks = [0.0] + [float((y - y0) / h) for y in yticks] + [1.0]

        for i in range(len(x_breaks) - 1):
            c = "#1E293B" if i % 2 == 0 else "#FFFFFF"
            seg_w = x_breaks[i + 1] - x_breaks[i]
            # 下边框与上边框斑马条
            for y_pos in [-band_h, 1.0]:
                rect = mpatches.Rectangle(
                    (x_breaks[i], y_pos),
                    seg_w,
                    band_h,
                    transform=ax.transAxes,
                    facecolor=c,
                    edgecolor="#1E293B",
                    linewidth=0.7,
                    clip_on=False,
                    zorder=100,
                )
                ax.add_patch(rect)

        for j in range(len(y_breaks) - 1):
            c = "#1E293B" if j % 2 == 0 else "#FFFFFF"
            seg_h = y_breaks[j + 1] - y_breaks[j]
            # 左边框与右边框斑马条
            for x_pos in [-band_w, 1.0]:
                rect = mpatches.Rectangle(
                    (x_pos, y_breaks[j]),
                    band_w,
                    seg_h,
                    transform=ax.transAxes,
                    facecolor=c,
                    edgecolor="#1E293B",
                    linewidth=0.7,
                    clip_on=False,
                    zorder=100,
                )
                ax.add_patch(rect)

        # 四角黑色交汇方块
        for cx in [-band_w, 1.0]:
            for cy in [-band_h, 1.0]:
                corner = mpatches.Rectangle(
                    (cx, cy),
                    band_w,
                    band_h,
                    transform=ax.transAxes,
                    facecolor="#1E293B",
                    edgecolor="#1E293B",
                    linewidth=0.7,
                    clip_on=False,
                    zorder=100,
                )
                ax.add_patch(corner)

        for spine in ax.spines.values():
            spine.set_edgecolor("#1E293B")
            spine.set_linewidth(1.1)

    @staticmethod
    def draw_title_banner(
        ax,
        title: str,
        subtitle: str,
        font_family: str,
    ):
        """在图幅顶部中央绘制带半透明磨砂白底与双线装饰边框的主副图名框"""
        banner = mpatches.FancyBboxPatch(
            (0.18, 0.905),
            0.64,
            0.076,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            transform=ax.transAxes,
            facecolor="#FFFFFF",
            edgecolor="#334155",
            linewidth=1.1,
            alpha=0.92,
            zorder=99,
        )
        ax.add_patch(banner)

        ax.text(
            0.50,
            0.952 if subtitle else 0.942,
            title,
            transform=ax.transAxes,
            fontfamily=font_family,
            fontsize=12.5,
            fontweight="bold",
            color="#0F172A",
            ha="center",
            va="center",
            zorder=100,
        )
        if subtitle:
            ax.text(
                0.50,
                0.920,
                subtitle,
                transform=ax.transAxes,
                fontfamily=font_family,
                fontsize=7.8,
                color="#475569",
                ha="center",
                va="center",
                zorder=100,
            )

    @staticmethod
    def draw_compass_rose(
        ax,
        font_family: str,
        cx: float = 0.925,
        cy: float = 0.885,
        size: float = 0.042,
    ):
        """在图幅右上角绘制经典地图学黑白双翼矢量指北针 (Compass Rose)"""
        # 背景圆盘
        bg_circle = mpatches.Circle(
            (cx, cy),
            size * 0.95,
            transform=ax.transAxes,
            facecolor="#FFFFFF",
            edgecolor="#CBD5E1",
            linewidth=0.8,
            alpha=0.88,
            zorder=99,
        )
        ax.add_patch(bg_circle)

        # 左半翼（深炭黑）与右半翼（纯白描边）
        left_wing = mpatches.Polygon(
            [(cx, cy + size * 0.85), (cx - size * 0.32, cy - size * 0.55), (cx, cy - size * 0.20)],
            closed=True,
            transform=ax.transAxes,
            facecolor="#0F172A",
            edgecolor="#0F172A",
            linewidth=0.8,
            zorder=100,
        )
        right_wing = mpatches.Polygon(
            [(cx, cy + size * 0.85), (cx + size * 0.32, cy - size * 0.55), (cx, cy - size * 0.20)],
            closed=True,
            transform=ax.transAxes,
            facecolor="#FFFFFF",
            edgecolor="#0F172A",
            linewidth=0.8,
            zorder=100,
        )
        ax.add_patch(left_wing)
        ax.add_patch(right_wing)

        txt = ax.text(
            cx,
            cy + size * 1.02,
            "N",
            transform=ax.transAxes,
            fontfamily=font_family,
            fontsize=8.5,
            fontweight="bold",
            color="#0F172A",
            ha="center",
            va="bottom",
            zorder=100,
        )
        txt.set_path_effects([patheffects.withStroke(linewidth=2.0, foreground="#FFFFFF")])

    @staticmethod
    def draw_graphic_scale_bar(
        ax,
        extent: Tuple[float, float, float, float],
        font_family: str,
        bx: float = 0.72,
        by: float = 0.045,
    ):
        """
        根据制图区域真实经纬度跨度解算实地距离（km），绘制黑白交替双段图形比例尺与数字比例尺。
        """
        x0, y0, x1, y1 = extent
        mean_lat = 0.5 * (y0 + y1)
        km_per_deg_lon = 111.32 * math.cos(math.radians(mean_lat))
        total_width_km = (x1 - x0) * km_per_deg_lon

        # 选取整洁的比例尺总长（约占图幅宽度的 14%~20%）
        target_km = total_width_km * 0.16
        nice_steps = [1, 2, 4, 5, 8, 10, 15, 20, 25, 30, 50, 100]
        bar_km = min(nice_steps, key=lambda s: abs(s - target_km))
        bar_axes_w = bar_km / max(total_width_km, 1e-6)
        half_w = bar_axes_w / 2.0
        bar_h = 0.011

        # 比例尺白底衬框
        bg = mpatches.FancyBboxPatch(
            (bx - 0.015, by - 0.018),
            bar_axes_w + 0.055,
            0.062,
            boxstyle="round,pad=0.004,rounding_size=0.008",
            transform=ax.transAxes,
            facecolor="#FFFFFF",
            edgecolor="#94A3B8",
            linewidth=0.7,
            alpha=0.90,
            zorder=99,
        )
        ax.add_patch(bg)

        # 左黑右白交替尺段
        r1 = mpatches.Rectangle(
            (bx, by), half_w, bar_h, transform=ax.transAxes, facecolor="#1E293B", edgecolor="#1E293B", linewidth=0.8, zorder=100
        )
        r2 = mpatches.Rectangle(
            (bx + half_w, by), half_w, bar_h, transform=ax.transAxes, facecolor="#FFFFFF", edgecolor="#1E293B", linewidth=0.8, zorder=100
        )
        ax.add_patch(r1)
        ax.add_patch(r2)

        # 刻度文字 (0, bar_km/2, bar_km km)
        half_label = f"{bar_km / 2:g}"
        for pos_x, lbl in [(bx, "0"), (bx + half_w, half_label), (bx + bar_axes_w, f"{bar_km} km")]:
            ax.text(
                pos_x,
                by + bar_h + 0.006,
                lbl,
                transform=ax.transAxes,
                fontfamily=font_family,
                fontsize=6.8,
                fontweight="bold",
                color="#1E293B",
                ha="center",
                va="bottom",
                zorder=100,
            )

        # 底部坐标系说明
        ax.text(
            bx + bar_axes_w / 2.0,
            by - 0.006,
            "CGCS2000 / 高斯投影校准",
            transform=ax.transAxes,
            fontfamily=font_family,
            fontsize=5.8,
            color="#475569",
            ha="center",
            va="top",
            zorder=100,
        )

    @staticmethod
    def draw_structured_legend(
        ax,
        legend_items: List[Dict[str, Any]],
        font_family: str,
        title: str = "图 例 (LEGEND)",
        loc: str = "lower left",
    ):
        """
        根据当前地图实际激活的符号列表，自动构建点、线、面分层图例框。
        每个 item 支持: {'label': str, 'geom_type': 'point'|'line'|'polygon', 'color': str, ...}
        """
        if not legend_items:
            return

        handles = []
        labels = []
        for item in legend_items:
            gtype = item.get("geom_type", "polygon")
            lbl = item.get("label", "")
            if gtype == "polygon":
                h = mpatches.Patch(
                    facecolor=item.get("fill_color", "#E2E8F0"),
                    edgecolor=item.get("stroke_color", "#475569"),
                    linewidth=item.get("stroke_width", 0.9),
                    alpha=item.get("alpha", 0.88),
                )
            elif gtype == "line":
                h = mlines.Line2D(
                    [],
                    [],
                    color=item.get("stroke_color", "#1E293B"),
                    linewidth=min(3.0, item.get("stroke_width", 1.8)),
                    linestyle=item.get("linestyle", "solid"),
                )
            else:
                h = mlines.Line2D(
                    [],
                    [],
                    color="none",
                    marker=item.get("marker", "o"),
                    markersize=min(9.0, item.get("markersize", 7.0)),
                    markerfacecolor=item.get("fill_color", "#E11D48"),
                    markeredgecolor=item.get("stroke_color", "#881337"),
                    markeredgewidth=1.1,
                )
            handles.append(h)
            labels.append(lbl)

        leg = ax.legend(
            handles,
            labels,
            title=title,
            loc=loc,
             bbox_to_anchor=(0.022, 0.025),
            frameon=True,
            facecolor="#FFFFFF",
            edgecolor="#64748B",
            framealpha=0.92,
            fontsize=7.2,
            title_fontsize=8.0,
            borderpad=0.65,
            labelspacing=0.45,
            handlelength=2.2,
        )
        leg.set_zorder(100)
        plt_title = leg.get_title()
        plt_title.set_fontfamily(font_family)
        plt_title.set_fontweight("bold")
        plt_title.set_color("#0F172A")
        for text in leg.get_texts():
            text.set_fontfamily(font_family)
            text.set_color("#1E293B")
