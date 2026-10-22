# -*- coding: utf-8 -*-
"""
[分类十：多比例尺动态缩放 (LOD)、载负量自适应与行政层级下钻引擎] `multiscale_lod`
实现：
1. 比例尺缩放触发的行政层级动态下钻（湖北省各市分隔 -> 放大至武汉市展示各区行政规划 -> 放大至核心片区展示街道与校园要素）；
2. 不同比例尺下的地图载负量（Map Load Capacity）动态裁剪；
3. 线性道路粗细随比例尺动态变化（贴合真实道路宽度等级）与长江/汉江真实宽度面状水系表达。
"""

from .scale_lod_engine import MultiScaleLODEngine, ScaleLevelSpec

__all__ = ["MultiScaleLODEngine", "ScaleLevelSpec"]
