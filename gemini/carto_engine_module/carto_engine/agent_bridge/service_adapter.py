# -*- coding: utf-8 -*-
"""
================================================================================
[分类六 - 子模块 6.2] Carto-Agent 服务门面适配器 `service_adapter.py`
================================================================================
提供统一的 `CartoEngineFacade` 接口：
1. 可直接挂载到 `Projects/carto-agent/backend/app/services/` 中，替换原 `export_service.py` 的占位图逻辑；
2. 同时支持输出出版级高分辨率 PNG/SVG/PDF 地图文件，以及返回供前端 Vue3 + Leaflet/Mapbox 渲染的标准 JSON。
"""

from typing import Dict, Any, Optional
import geopandas as gpd
import matplotlib.pyplot as plt

from ..models_and_specs import MapType, CartoTaskSpec, CoordSystemType
from ..renderers import (
    TrafficMapRenderer,
    TourismMapRenderer,
    AdministrativeMapRenderer,
    TerrainMapRenderer,
)
from .kg_rule_engine import CartoKGRuleEngine


class CartoEngineFacade:
    """
    独立封装制图模块的统一门面入口（对接 Carto-Agent 后端 API 与 Agent 工具链）
    """

    RENDERER_REGISTRY = {
        MapType.TRAFFIC: TrafficMapRenderer,
        MapType.TOURISM: TourismMapRenderer,
        MapType.ADMINISTRATIVE: AdministrativeMapRenderer,
        MapType.TERRAIN: TerrainMapRenderer,
    }

    @classmethod
    def render_thematic_map(
        cls,
        task_spec: CartoTaskSpec,
        raw_layers: Dict[str, gpd.GeoDataFrame],
        output_path: str,
        source_crs_map: Optional[Dict[str, CoordSystemType]] = None,
        dem_grid: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的“KG规则推理 -> SHP空间校准 -> 制图综合 -> 符号化与避让注记 -> 五大整饰排版 -> 出版级导出”流水线。
        """
        validation = CartoKGRuleEngine.validate_cartographic_quality(
            task_spec, list(raw_layers.keys())
        )
        renderer_cls = cls.RENDERER_REGISTRY.get(task_spec.map_type, AdministrativeMapRenderer)
        renderer = renderer_cls(task_spec)

        fig, ax = plt.subplots(figsize=(8.5, 6.8), dpi=task_spec.dpi)
        renderer.render_on_axes(ax, raw_layers, source_crs_map=source_crs_map, dem_grid=dem_grid)
        fig.tight_layout(pad=1.2)
        fig.savefig(output_path, dpi=task_spec.dpi, bbox_inches="tight", facecolor="#FFFFFF")
        plt.close(fig)

        return {
            "status": "success",
            "output_path": output_path,
            "map_type": task_spec.map_type.value,
            "validation": validation,
            "legend_count": len(renderer.legend_items),
        }
