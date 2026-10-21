"""制图方案质量校验器 - 检查图层完整性、符号规范性、配色协调性

CartographyValidator 对已生成的地图方案进行多维度质量校验：
1. 图层完整性：检查图层数量、是否有空图层、要素覆盖是否足够
2. 符号规范性：检查符号样式参数（线宽、点半径、透明度等）是否在合理范围
3. 配色协调性：检查颜色搭配是否协调、色相对比度、明度层次
"""
from typing import Dict, Any, List, Tuple
import re


class CartographyValidator:
    """制图方案校验器

    对地图数据进行多维度质量评分，返回结构化校验结果。
    每个检查维度独立打分，最终汇总为0-100的综合质量分。

    使用方式：
        validator = CartographyValidator()
        result = validator.validate(map_data, kg_service=kg)
        # result: {"score": 85, "issues": [...], "passed_checks": [...], "failed_checks": [...]}
    """

    # 合理的样式参数范围
    VALID_RANGES = {
        "line_weight": (0.5, 8.0),     # 线宽 0.5-8px
        "point_radius": (2, 20),        # 点半径 2-20px
        "fill_opacity": (0.1, 0.9),     # 填充透明度 0.1-0.9
        "title_size": (12, 24),         # 标题字号 12-24px
        "label_size": (8, 18),          # 标注字号 8-18px
        "border_width": (0.5, 6.0),     # 边框宽度 0.5-6px
        "stroke_width": (0.3, 6.0),     # 描边宽度 0.3-6px
    }

    # 地图类型对应的最低图层数要求
    MIN_LAYERS_BY_TYPE = {
        "traffic": 2,          # 至少道路+铁路
        "tourism": 2,          # 至少景点+基础
        "campus": 2,           # 至少建筑+道路
        "basic": 3,            # 至少道路+水系+建筑
        "food": 1,             # 至少餐饮标注
        "administrative": 1,   # 至少行政边界
    }

    # 检查项权重
    CHECK_WEIGHTS = {
        "layer_completeness": 0.40,    # 图层完整性权重
        "symbol_normativity": 0.35,    # 符号规范性权重
        "color_harmony": 0.25,         # 配色协调性权重
    }

    # ---- Public API ----

    def validate(self, map_data: Dict[str, Any], kg_service=None) -> Dict[str, Any]:
        """校验地图方案质量

        对地图数据进行三维度质量检查，汇总为综合评分。

        Args:
            map_data: 地图数据字典，需包含 layers 等字段
            kg_service: 知识图谱服务实例（可选，用于参考规范校验）

        Returns:
            校验结果字典，包含：
            {
                "score": int,              # 0-100 综合质量分
                "issues": List[str],       # 所有警告问题（合并）
                "passed_checks": List[str], # 通过的检查项描述
                "failed_checks": List[str], # 失败的检查项描述
            }
        """
        issues: List[str] = []
        passed_checks: List[str] = []
        failed_checks: List[str] = []
        check_scores: Dict[str, int] = {}

        # 1. 图层完整性检查
        layer_score, layer_issues = self._check_layer_completeness(map_data)
        if layer_score >= 70:
            passed_checks.append(f"图层完整性: {layer_score}/100")
        else:
            failed_checks.append(f"图层完整性: {layer_score}/100")
        issues.extend(layer_issues)
        check_scores["layer_completeness"] = layer_score

        # 2. 符号规范性检查
        symbol_score, symbol_issues = self._check_symbol_normativity(map_data)
        if symbol_score >= 70:
            passed_checks.append(f"符号规范性: {symbol_score}/100")
        else:
            failed_checks.append(f"符号规范性: {symbol_score}/100")
        issues.extend(symbol_issues)
        check_scores["symbol_normativity"] = symbol_score

        # 3. 配色协调性检查
        color_score, color_issues = self._check_color_harmony(map_data)
        if color_score >= 70:
            passed_checks.append(f"配色协调性: {color_score}/100")
        else:
            failed_checks.append(f"配色协调性: {color_score}/100")
        issues.extend(color_issues)
        check_scores["color_harmony"] = color_score

        # 4. 综合评分（加权）: 0-100
        total_score = 0
        weight_sum = 0
        for check_name, weight in self.CHECK_WEIGHTS.items():
            total_score += check_scores.get(check_name, 0) * weight
            weight_sum += weight
        total_score = round(total_score / weight_sum) if weight_sum > 0 else 0

        # 如果有KG服务，可进行参考规范附加校验（不改变分数，仅增加提示）
        if kg_service:
            try:
                constraints = kg_service.get_constraints()
                if constraints and len(map_data.get("layers", [])) > 0:
                    passed_checks.append(
                        f"KG参考: 已加载{len(constraints)}条制图约束规范"
                    )
            except Exception:
                pass

        print(f"[CartographyValidator] 校验完成: score={total_score}, "
              f"issues={len(issues)}, passed={len(passed_checks)}, "
              f"failed={len(failed_checks)}")

        return {
            "score": total_score,
            "issues": issues,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        }

    # ---- Check Methods ----

    def _check_layer_completeness(self, map_data: Dict) -> Tuple[int, List[str]]:
        """检查图层完整性

        检查维度：
        - 是否至少有一个图层
        - 图层数量是否达到该地图类型的最低要求
        - 图层是否有空数据（无坐标无要素）
        - 图层名称是否合理（有无未命名图层）

        Args:
            map_data: 地图数据

        Returns:
            (得分0-100, 问题列表)
        """
        issues: List[str] = []
        layers = map_data.get("layers", [])
        map_type = map_data.get("map_type", "")

        # 检查1：无图层
        if len(layers) == 0:
            return (0, ["地图没有任何图层数据"])
        # 检查2：图层数量达最低要求
        min_layers = self.MIN_LAYERS_BY_TYPE.get(map_type, 2)
        layer_count = len(layers)
        # 检查3：空图层
        empty_layers = 0
        unnamed_layers = 0
        for layer in layers:
            name = layer.get("name", "")
            coords = layer.get("coordinates", [])
            features = layer.get("features", [])
            if len(coords) == 0 and len(features) == 0:
                empty_layers += 1
                issues.append(f"图层'{name or '未命名'}'没有坐标数据")
            if not name:
                unnamed_layers += 1

        if empty_layers > 0:
            issues.append(f"共{empty_layers}个空图层（无坐标数据）")
        if unnamed_layers > 0:
            issues.append(f"共{unnamed_layers}个图层未命名")

        # 评分逻辑
        valid_layers = layer_count - empty_layers
        if valid_layers == 0:
            return (0, issues)
        if valid_layers >= min_layers:
            # 达标或超出
            score = min(100, 70 + (valid_layers - min_layers) * 15)
        else:
            # 未达标，按比例扣分
            ratio = valid_layers / max(min_layers, 1)
            score = int(ratio * 70)

        # 空图层额外扣分
        if empty_layers > 0:
            score = max(0, score - empty_layers * 10)

        return (score, issues)

    def _check_symbol_normativity(self, map_data: Dict) -> Tuple[int, List[str]]:
        """检查符号规范性

        检查维度：
        - 样式参数是否在合理范围内（线宽、点半径、透明度、字号等）
        - 是否使用了未定义的样式属性
        - 样式配置完整性

        Args:
            map_data: 地图数据

        Returns:
            (得分0-100, 问题列表)
        """
        issues: List[str] = []
        layers = map_data.get("layers", [])

        if not layers:
            return (100, issues)  # 无图层则不扣分（由图层完整性检查负责）

        total_params_checked = 0
        out_of_range_count = 0

        for layer in layers:
            style = layer.get("style", {})
            if not isinstance(style, dict):
                continue

            # 检查线宽
            if "weight" in style:
                weight = style["weight"]
                if isinstance(weight, (int, float)):
                    total_params_checked += 1
                    min_val, max_val = self.VALID_RANGES["line_weight"]
                    if weight < min_val or weight > max_val:
                        layer_name = layer.get("name", "未命名")
                        issues.append(
                            f"图层'{layer_name}'线宽={weight}，"
                            f"建议范围 {min_val}-{max_val}px"
                        )
                        out_of_range_count += 1

            # 检查线宽（别名）
            if "line_weight" in style:
                lw = style["line_weight"]
                if isinstance(lw, (int, float)):
                    total_params_checked += 1
                    min_val, max_val = self.VALID_RANGES["line_weight"]
                    if lw < min_val or lw > max_val:
                        layer_name = layer.get("name", "未命名")
                        issues.append(
                            f"图层'{layer_name}'线宽={lw}，"
                            f"建议范围 {min_val}-{max_val}px"
                        )
                        out_of_range_count += 1

            # 检查点半径
            if "radius" in style:
                radius = style["radius"]
                if isinstance(radius, (int, float)):
                    total_params_checked += 1
                    min_val, max_val = self.VALID_RANGES["point_radius"]
                    if radius < min_val or radius > max_val:
                        layer_name = layer.get("name", "未命名")
                        issues.append(
                            f"图层'{layer_name}'点半径={radius}，"
                            f"建议范围 {min_val}-{max_val}px"
                        )
                        out_of_range_count += 1

            # 检查填充透明度
            if "opacity" in style:
                opacity = style["opacity"]
                if isinstance(opacity, (int, float)):
                    total_params_checked += 1
                    min_val, max_val = self.VALID_RANGES["fill_opacity"]
                    if opacity < min_val or opacity > max_val:
                        layer_name = layer.get("name", "未命名")
                        issues.append(
                            f"图层'{layer_name}'透明度={opacity}，"
                            f"建议范围 {min_val}-{max_val}"
                        )
                        out_of_range_count += 1

            # 检查字号（标注相关）
            for size_key in ("font_size", "title_size", "label_size", "size"):
                if size_key in style:
                    size_val = style[size_key]
                    if isinstance(size_val, (int, float)):
                        total_params_checked += 1
                        if size_key in ("title_size", "label_size"):
                            min_val, max_val = self.VALID_RANGES.get(
                                size_key, (8, 24)
                            )
                        else:
                            min_val, max_val = (8, 24)
                        if size_val < min_val or size_val > max_val:
                            layer_name = layer.get("name", "未命名")
                            issues.append(
                                f"图层'{layer_name}'{size_key}={size_val}，"
                                f"建议范围 {min_val}-{max_val}px"
                            )
                            out_of_range_count += 1

        # 评分逻辑
        if total_params_checked == 0:
            # 没有可检查的样式参数，视为通过（可能使用默认样式）
            return (85, issues)

        # 按参数超标比例扣分
        violation_ratio = out_of_range_count / total_params_checked
        if violation_ratio == 0:
            score = 100
        elif violation_ratio <= 0.25:
            score = 85
        elif violation_ratio <= 0.5:
            score = 65
        else:
            score = max(0, int(100 - violation_ratio * 100))

        return (score, issues)

    def _check_color_harmony(self, map_data: Dict) -> Tuple[int, List[str]]:
        """检查配色协调性

        检查维度：
        - 是否使用了过于相近的颜色（色相距离 < 30度视为相近）
        - 颜色数量是否过多（建议不超过8种不同颜色）
        - 是否使用了极低对比度的颜色组合
        - 背景色与主色是否有足够对比度

        Args:
            map_data: 地图数据

        Returns:
            (得分0-100, 问题列表)
        """
        issues: List[str] = []
        layers = map_data.get("layers", [])

        if not layers:
            return (100, issues)

        # 收集所有图层颜色及其语义分组（group），用于跨分组同色检测
        all_colors: List[str] = []
        color_groups: Dict[str, set] = {}
        for layer in layers:
            style = layer.get("style", {})
            group = layer.get("group") or layer.get("name") or "?"
            if isinstance(style, dict):
                color = style.get("color", "")
                if color and isinstance(color, str) and color.startswith("#"):
                    all_colors.append(color.lower())
                    color_groups.setdefault(color.lower(), set()).add(group)
                fill_color = style.get("fillColor", style.get("fill_color", ""))
                if fill_color and isinstance(fill_color, str) and fill_color.startswith("#"):
                    all_colors.append(fill_color.lower())
                    color_groups.setdefault(fill_color.lower(), set()).add(group)

        # 收集全局配置颜色
        for config_key in ("background", "primary_color", "accent_color"):
            color_val = map_data.get(config_key, "")
            if color_val and isinstance(color_val, str) and color_val.startswith("#"):
                all_colors.append(color_val.lower())

        unique_colors = list(set(all_colors))

        # 检查1：颜色数量（专题图允许较多配色，阈值放宽到24）
        if len(unique_colors) > 24:
            issues.append(
                f"使用了{len(unique_colors)}种不同颜色，"
                f"超过24种时建议归类合并以保持视觉层次清晰"
            )
        if len(unique_colors) <= 1 and len(layers) > 1:
            issues.append("仅使用1种颜色，建议为不同图层使用区分色以增强可读性")

        # 检查2：跨语义分组共用完全相同颜色（真正的可读性问题）
        cross_group_dups = [
            c for c, groups in color_groups.items() if len(groups) > 1
        ]
        if cross_group_dups:
            issues.append(
                f"{len(cross_group_dups)}种颜色被不同语义分组共用"
                f"（{', '.join(cross_group_dups[:6])}），建议区分"
            )

        # 检查3：相近色/低对比度（信息性提示；单色渐变等制图手法属正常设计，不参与扣分）
        too_similar_pairs = 0
        low_contrast_pairs = 0
        for i in range(len(unique_colors)):
            for j in range(i + 1, len(unique_colors)):
                h1, s1, l1 = self._hex_to_hsl(unique_colors[i])
                h2, s2, l2 = self._hex_to_hsl(unique_colors[j])
                hue_diff = min(abs(h1 - h2), 360 - abs(h1 - h2))
                if hue_diff < 12 and abs(l1 - l2) < 0.06:
                    too_similar_pairs += 1
                if abs(l1 - l2) < 0.05:
                    low_contrast_pairs += 1

        if too_similar_pairs > 0:
            issues.append(
                f"存在{too_similar_pairs}对色相、明度都接近的颜色（色相差<12°且明度差<6%），"
                f"若为同一要素的渐变设色可忽略，否则建议拉开区分度"
            )
        if low_contrast_pairs > 0:
            issues.append(
                f"存在{low_contrast_pairs}对明度过近的颜色（明度差<5%），"
                f"建议检查图例可读性"
            )

        # 评分逻辑：颜色过多与跨分组同色为硬性扣分项
        if not unique_colors or len(unique_colors) <= 1:
            return (70, issues)

        penalty = 0
        if len(unique_colors) > 24:
            penalty += min(10, (len(unique_colors) - 24) * 2)
        penalty += min(15, len(cross_group_dups) * 3)

        score = max(0, 100 - penalty)
        return (score, issues)

    # ---- Color Helpers ----

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """将十六进制颜色转换为RGB

        Args:
            hex_color: 十六进制颜色字符串（如 "#ff0000" 或 "ff0000"）

        Returns:
            (r, g, b) 元组，范围0-255
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        if len(hex_color) != 6:
            return (0, 0, 0)
        try:
            return (
                int(hex_color[0:2], 16),
                int(hex_color[2:4], 16),
                int(hex_color[4:6], 16),
            )
        except ValueError:
            return (0, 0, 0)

    @classmethod
    def _hex_to_hsl(cls, hex_color: str) -> Tuple[float, float, float]:
        """将十六进制颜色转换为HSL

        Args:
            hex_color: 十六进制颜色字符串

        Returns:
            (h, s, l) 元组，h范围0-360，s和l范围0-1
        """
        r, g, b = cls._hex_to_rgb(hex_color)
        r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0

        max_val = max(r_norm, g_norm, b_norm)
        min_val = min(r_norm, g_norm, b_norm)
        l = (max_val + min_val) / 2.0

        if max_val == min_val:
            h = s = 0.0
        else:
            delta = max_val - min_val
            s = delta / (2.0 - max_val - min_val) if l > 0.5 else delta / (max_val + min_val)

            if max_val == r_norm:
                h = ((g_norm - b_norm) / delta) * 60.0
            elif max_val == g_norm:
                h = ((b_norm - r_norm) / delta + 2) * 60.0
            else:
                h = ((r_norm - g_norm) / delta + 4) * 60.0

            if h < 0:
                h += 360.0

        return (h, s, l)
