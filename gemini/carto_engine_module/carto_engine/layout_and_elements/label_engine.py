# -*- coding: utf-8 -*-
"""
================================================================================
[分类四 - 子模块 4.2] 地图注记配置与碰撞检测避让引擎 `label_engine.py`
================================================================================
地图学注记（Map Typography & Labeling）核心规则：
1. **点状要素八方位优选模型 (Yoeli / Imhof 8-Position Priority Model)**：
   候选方位优先级依次为：①右上 (Top-Right) > ②左上 (Top-Left) > ③右下 (Bottom-Right) >
   ④左下 (Bottom-Left) > ⑤正上 (Top-Center) > ⑥正下 (Bottom-Center) > ⑦正右 > ⑧正左。
2. **面状政区注记字列排布 (Spaced Character Placement)**：
   行政区名称置于政区视觉中心（代表点 `representative_point()`），并根据多边形跨度插入字间空格（如“武 昌 区”）。
3. **水系注记规范**：
   采用深蓝色 (`#1E40AF`)、左倾/斜体 (`style='italic'`) 标注江河湖泊名称。
4. **等高线高程注记**：
   沿计曲线切线方向嵌印棕褐色高程数值（如 `100m`, `200m`），加白底 Halo 破开等高线。
5. **碰撞检测避让 (Bounding Box Collision Resolution)**：
   按注记优先级 (`priority` 1 最高) 维护已放置注记与核心点符号的屏幕空间包络矩形列表，
   自动尝试候选方位，若 8 个方位均发生碰撞且非强制保留地标，则自动隐去以保持图面整洁。
"""

import math
from typing import List, Tuple, Optional
from shapely.geometry import box
import matplotlib.patheffects as patheffects


class CartoLabelEngine:
    """具有空间碰撞避让与地图学字体规范的注记配置引擎"""

    # 八方位偏移向量 (dx_factor, dy_factor, ha, va)
    EIGHT_POSITIONS = [
        (1.0, 0.85, "left", "bottom"),    # 1. 右上 (最优)
        (-1.0, 0.85, "right", "bottom"),  # 2. 左上
        (1.0, -0.85, "left", "top"),      # 3. 右下
        (-1.0, -0.85, "right", "top"),    # 4. 左下
        (0.0, 1.25, "center", "bottom"),  # 5. 正上
        (0.0, -1.25, "center", "top"),    # 6. 正下
        (1.3, 0.0, "left", "center"),     # 7. 正右
        (-1.3, 0.0, "right", "center"),   # 8. 正左
    ]

    def __init__(self, extent: Tuple[float, float, float, float]):
        """
        参数:
            extent: (min_x, min_y, max_x, max_y) 当前地图数据坐标范围
        """
        self.extent = extent
        self.width = max(1e-6, extent[2] - extent[0])
        self.height = max(1e-6, extent[3] - extent[1])
        self.occupied_boxes: List[box] = []
        self._register_marginalia_obstacles()

    def _axes_frac_to_box(self, fx0: float, fy0: float, fx1: float, fy1: float) -> box:
        x0, y0, _, _ = self.extent
        return box(
            x0 + fx0 * self.width,
            y0 + fy0 * self.height,
            x0 + fx1 * self.width,
            y0 + fy1 * self.height,
        )

    def _register_marginalia_obstacles(self):
        """预先将图名框、左下角图例框、右下角比例尺框、右上角指北针注册为注记禁区，杜绝注记与整饰要素碰撞"""
        # 1. 顶部中央主副图名框禁区
        self.occupied_boxes.append(self._axes_frac_to_box(0.16, 0.885, 0.84, 1.00))
        # 2. 左下角结构化图例框禁区
        self.occupied_boxes.append(self._axes_frac_to_box(0.00, 0.00, 0.34, 0.38))
        # 3. 右下角图形比例尺框禁区
        self.occupied_boxes.append(self._axes_frac_to_box(0.66, 0.00, 1.00, 0.13))
        # 4. 右上角指北针禁区
        self.occupied_boxes.append(self._axes_frac_to_box(0.86, 0.81, 1.00, 1.00))

    def register_symbol_obstacle(self, x: float, y: float, radius_ratio: float = 0.012):
        """将已绘制的重要点状符号注册为障碍物包络框，防止文字直接压盖在符号中心"""
        rx = self.width * radius_ratio
        ry = self.height * radius_ratio
        self.occupied_boxes.append(box(x - rx, y - ry, x + rx, y + ry))

    def _estimate_text_bbox(
        self,
        x: float,
        y: float,
        text: str,
        font_size: float,
        ha: str,
        va: str,
    ) -> box:
        """在数据坐标系下估算中文字符与数字注记的包络矩形 (Bounding Box)"""
        # 每个中文字符约占图面宽度的比例随字号线性缩放
        char_w = self.width * (font_size / 520.0)
        char_h = self.height * (font_size / 420.0)
        w = max(char_w * 1.5, len(text) * char_w)
        h = char_h * 1.25

        if ha == "left":
            x0, x1 = x, x + w
        elif ha == "right":
            x0, x1 = x - w, x
        else:
            x0, x1 = x - w / 2.0, x + w / 2.0

        if va == "bottom":
            y0, y1 = y, y + h
        elif va == "top":
            y0, y1 = y - h, y
        else:
            y0, y1 = y - h / 2.0, y + h / 2.0

        # 图廓内缩安全边界检查
        margin_x = self.width * 0.015
        margin_y = self.height * 0.015
        return box(x0 - margin_x * 0.1, y0 - margin_y * 0.1, x1 + margin_x * 0.1, y1 + margin_y * 0.1)

    def _has_collision(self, candidate_box: box) -> bool:
        """检测候选注记框是否越出图廓或与已有注记/符号发生重叠"""
        ex0, ey0, ex1, ey1 = self.extent
        mx, my = self.width * 0.01, self.height * 0.01
        if (
            candidate_box.bounds[0] < ex0 + mx
            or candidate_box.bounds[2] > ex1 - mx
            or candidate_box.bounds[1] < ey0 + my
            or candidate_box.bounds[3] > ey1 - my
        ):
            return True
        for existing in self.occupied_boxes:
            if candidate_box.intersects(existing):
                return True
        return False

    def place_point_label(
        self,
        ax,
        x: float,
        y: float,
        text: str,
        font_family: str,
        font_size: float = 8.5,
        font_weight: str = "bold",
        font_color: str = "#1E293B",
        halo_color: str = "#FFFFFF",
        halo_width: float = 2.2,
        offset_ratio: float = 0.014,
        force_place: bool = False,
        zorder: int = 96,
    ) -> bool:
        """
        使用八方位候选模型为点状地标/驻地/山峰配置注记，自动避让碰撞。
        """
        if not text:
            return False

        dx_base = self.width * offset_ratio
        dy_base = self.height * offset_ratio

        chosen = None
        for dx_f, dy_f, ha, va in self.EIGHT_POSITIONS:
            tx = x + dx_base * dx_f
            ty = y + dy_base * dy_f
            cand_box = self._estimate_text_bbox(tx, ty, text, font_size, ha, va)
            if not self._has_collision(cand_box):
                chosen = (tx, ty, ha, va, cand_box)
                break

        if chosen is None:
            if force_place:
                dx_f, dy_f, ha, va = self.EIGHT_POSITIONS[0]
                tx, ty = x + dx_base * dx_f, y + dy_base * dy_f
                cand_box = self._estimate_text_bbox(tx, ty, text, font_size, ha, va)
                chosen = (tx, ty, ha, va, cand_box)
            else:
                return False

        tx, ty, ha, va, cand_box = chosen
        self.occupied_boxes.append(cand_box)

        txt_obj = ax.text(
            tx,
            ty,
            text,
            fontfamily=font_family,
            fontsize=font_size,
            fontweight=font_weight,
            color=font_color,
            ha=ha,
            va=va,
            zorder=zorder,
            clip_on=True,
        )
        if halo_width > 0:
            txt_obj.set_path_effects([
                patheffects.withStroke(linewidth=halo_width, foreground=halo_color)
            ])
        return True

    def place_polygon_spaced_label(
        self,
        ax,
        poly,
        text: str,
        font_family: str,
        font_size: float = 9.5,
        font_color: str = "#334155",
        halo_color: str = "#FFFFFF",
        halo_width: float = 2.4,
        char_spacing: int = 1,
        is_water: bool = False,
        zorder: int = 92,
    ) -> bool:
        """
        为面状政区或湖泊水体配置居中字列注记（水体自动采用斜体蓝色，政区自动插入字列间距）。
        """
        if poly is None or poly.is_empty or not text:
            return False

        rep_pt = poly.representative_point()
        x, y = rep_pt.x, rep_pt.y
        spaced_text = (" " * char_spacing).join(list(text)) if (char_spacing > 0 and not is_water) else text

        cand_box = self._estimate_text_bbox(x, y, spaced_text, font_size, "center", "center")
        if self._has_collision(cand_box):
            # 尝试微调位置
            for dx_f, dy_f in [(0, -0.03), (0, -0.06), (-0.04, -0.05), (0.04, -0.05), (0, 0.03), (-0.05, 0), (0.05, 0)]:
                tx, ty = x + self.width * dx_f, y + self.height * dy_f
                alt_box = self._estimate_text_bbox(tx, ty, spaced_text, font_size, "center", "center")
                if not self._has_collision(alt_box):
                    x, y, cand_box = tx, ty, alt_box
                    break
            else:
                return False

        self.occupied_boxes.append(cand_box)
        txt_obj = ax.text(
            x,
            y,
            spaced_text,
            fontfamily=font_family,
            fontsize=font_size,
            fontweight="bold" if not is_water else "normal",
            fontstyle="italic" if is_water else "normal",
            color="#1D4ED8" if is_water else font_color,
            ha="center",
            va="center",
            alpha=0.88 if is_water else 0.95,
            zorder=zorder,
            clip_on=True,
        )
        if halo_width > 0:
            txt_obj.set_path_effects([
                patheffects.withStroke(linewidth=halo_width, foreground=halo_color)
            ])
        return True

    def place_contour_elevation_label(
        self,
        ax,
        line_geom,
        elev_value: float,
        font_family: str,
        font_size: float = 7.0,
        color: str = "#5C3A21",
        zorder: int = 94,
    ):
        """在计曲线中段沿切线倾角嵌印高程注记（如 200m）"""
        if line_geom is None or line_geom.is_empty:
            return
        if line_geom.geom_type == "MultiLineString":
            line_geom = max(line_geom.geoms, key=lambda g: g.length)
        coords = list(line_geom.coords)
        if len(coords) < 6:
            return
        mid = len(coords) // 2
        x0, y0 = coords[mid - 1]
        x1, y1 = coords[mid + 1]
        xm, ym = coords[mid]

        label_str = f"{int(round(elev_value))}m"
        cand_box = self._estimate_text_bbox(xm, ym, label_str, font_size, "center", "center")
        if self._has_collision(cand_box):
            return

        angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180

        self.occupied_boxes.append(cand_box)
        txt = ax.text(
            xm,
            ym,
            label_str,
            fontfamily=font_family,
            fontsize=font_size,
            color=color,
            ha="center",
            va="center",
            rotation=angle,
            zorder=zorder,
            clip_on=True,
        )
        txt.set_path_effects([patheffects.withStroke(linewidth=2.2, foreground="#FAF6F0")])
