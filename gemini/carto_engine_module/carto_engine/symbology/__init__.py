# -*- coding: utf-8 -*-
"""
[分类三：地图语言、分级符号与视觉变量子模块] `symbology`
涵盖国家基本比例尺地图图式配色、政区邻接四色算法、高程分层设色、定量分级算法与复合地图符号库。
"""

from .color_schemes import CartoColorSchemes
from .classification import ThematicClassifier
from .symbol_library import CartoSymbolLibrary

__all__ = ["CartoColorSchemes", "ThematicClassifier", "CartoSymbolLibrary"]
