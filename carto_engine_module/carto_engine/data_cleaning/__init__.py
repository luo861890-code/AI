# -*- coding: utf-8 -*-
"""
[分类八：多源数据清洗、面状水系重构与精确元数据标注] `data_cleaning`
确保在获取数据时完成几何/属性清洗、数据来源与质量评分标注、图层与要素精确范围注册，以及将线性河流转换为真实宽度面状水系。
"""

from .cleaner_and_provenance import SpatialDataCleanerAndProvenance, LayerProvenanceReport

__all__ = ["SpatialDataCleanerAndProvenance", "LayerProvenanceReport"]
