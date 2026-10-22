# -*- coding: utf-8 -*-
"""
[分类二：空间要素(点/线/面SHP)校准与制图综合子模块] `calibration`
解决原 `carto-agent` 缺乏原生 SHP 几何/拓扑修复、GCJ02/WGS84 混用偏移、无高斯投影转换及缺乏制图综合的问题。
"""

from .crs_calibrator import CRSCalibrator
from .topology_calibrator import TopologyCalibrator
from .generalization import CartoGeneralizer

__all__ = ["CRSCalibrator", "TopologyCalibrator", "CartoGeneralizer"]
