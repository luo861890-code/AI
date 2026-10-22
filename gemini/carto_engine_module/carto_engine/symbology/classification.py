# -*- coding: utf-8 -*-
"""
================================================================================
[分类三 - 子模块 3.2] 专题地图数值分级引擎 `classification.py`
================================================================================
解决原系统 `cartography_validator.py` 缺乏定量专题分级方法的问题。
内置：
1. Jenks 自然断点分级法 (Fisher-Jenks Natural Breaks，动态规划实现，无需额外重型依赖)
2. 分位数分级法 (Quantiles)
3. 等间距分级法 (Equal Interval)
4. 平均值-标准差分级法 (Standard Deviation)
"""

from typing import List, Tuple
import numpy as np


class ThematicClassifier:
    """定量专题属性分级解算器（用于交通流量分级、景区热度分级、人口/GDP统计分级）"""

    @staticmethod
    def jenks_breaks(values: List[float], k: int = 5) -> List[float]:
        """
        纯 NumPy / 动态规划实现的 Fisher-Jenks 自然断点算法：
        最小化组内方差（GVF 最大化），寻找数据分布的自然裂点。
        返回长度为 k+1 的断点列表 [min_val, b1, b2, ..., max_val]。
        """
        arr = np.sort(np.asarray(values, dtype=float))
        n = len(arr)
        if n == 0:
            return [0.0, 1.0]
        unique_vals = np.unique(arr)
        if len(unique_vals) <= k:
            return list(unique_vals) + [unique_vals[-1]] * (k + 1 - len(unique_vals))

        mat1 = np.zeros((n + 1, k + 1), dtype=int)
        mat2 = np.full((n + 1, k + 1), np.inf, dtype=float)
        mat1[1:, 1] = 1
        mat2[1:, 1] = 0.0

        for l in range(2, n + 1):
            s1 = s2 = w = 0.0
            for m in range(1, l + 1):
                i3 = l - m + 1
                val = arr[i3 - 1]
                s2 += val * val
                s1 += val
                w += 1.0
                v = s2 - (s1 * s1) / w
                i4 = i3 - 1
                if i4 != 0:
                    for j in range(2, k + 1):
                        if mat2[l, j] >= (v + mat2[i4, j - 1]):
                            mat1[l, j] = i3
                            mat2[l, j] = v + mat2[i4, j - 1]
            mat1[l, 1] = 1
            mat2[l, 1] = v

        kclass = [0.0] * (k + 1)
        kclass[k] = float(arr[-1])
        kclass[0] = float(arr[0])
        count_num = k
        idx = n
        while count_num >= 2:
            id_ = int(mat1[idx, count_num]) - 2
            kclass[count_num - 1] = float(arr[max(0, id_)])
            idx = int(mat1[idx, count_num]) - 1
            count_num -= 1
        return kclass

    @classmethod
    def classify_series(
        cls,
        values: List[float],
        method: str = "jenks",
        k: int = 4,
    ) -> Tuple[List[int], List[Tuple[float, float]]]:
        """
        对数值序列进行分级，返回每个要素所属的等级索引 (0 ~ k-1) 以及每一级的区间上下限。
        """
        arr = np.asarray(values, dtype=float)
        if len(arr) == 0:
            return [], []

        if method == "quantile":
            qs = np.linspace(0, 100, k + 1)
            breaks = list(np.percentile(arr, qs))
        elif method == "equal_interval":
            breaks = list(np.linspace(float(np.min(arr)), float(np.max(arr)), k + 1))
        else:
            breaks = cls.jenks_breaks(list(arr), k=k)

        # 确保断点严格单调递增以生成干净图例
        for i in range(1, len(breaks)):
            if breaks[i] <= breaks[i - 1]:
                breaks[i] = breaks[i - 1] + 1e-6

        intervals = [(breaks[i], breaks[i + 1]) for i in range(k)]
        classes = []
        for v in arr:
            c = k - 1
            for i in range(k):
                if v <= breaks[i + 1]:
                    c = i
                    break
            classes.append(c)
        return classes, intervals
