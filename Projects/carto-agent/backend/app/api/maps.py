"""地图API路由 - 地图生成、图层/要素管理与动态修改"""
import asyncio
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional as Opt, Any

from app.utils.helpers import run_in_thread
from app.api.deps import (
    get_map_service,
    get_agent_service,
    get_export_service,
    get_routing_service,
)
from app.core.exceptions import CartoAgentError
from app.models.schemas import (
    GenerateMapRequest,
    AddLayerRequest,
    UpdateLayerStyleRequest,
    SetLayerVisibleRequest,
    UpdateViewRequest,
    UpdateThemeRequest,
    AddFeatureRequest,
    ModifyMapRequest,
    ExportMapRequest,
    PlanRouteRequest,
    ApiResponse,
)
from app.services.map_service import MapService
from app.services.agent_service import AgentService
from app.services.export_service import ExportService
from app.services.routing_service import RoutingService

router = APIRouter(prefix="/api/maps", tags=["地图"])



@router.get("/wiki", response_model=ApiResponse, summary="百科知识查询（重点建筑简介与图片）")
async def wiki_lookup(name: str = Query(..., description="要查询的建筑/地标名称")):
    """查询建筑/地标的百科简介与图片，用于地图弹窗展示"""
    from app.services.wiki_service import WikiService
    try:
        data = WikiService().lookup(name)
        return ApiResponse(success=True, message="百科查询成功" if data.get("found") else "未找到百科词条", data=data)
    except Exception as e:
        return ApiResponse(success=False, message=f"百科查询失败: {e}", data={"name": name, "found": False})

class AddMarkerRequest(BaseModel):
    """自定义标注点请求"""
    name: str = Field(..., min_length=1, max_length=40, description="标注名称")
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    lng: float = Field(..., ge=-180, le=180, description="经度")
    icon: Opt[str] = Field(default=None, description="象形符号(emoji)")
    color: Opt[str] = Field(default="#e11d48", description="标注颜色")


class UpdateLayerGeometryRequest(BaseModel):
    """编辑模式：整层几何/属性更新请求（QGIS/ArcGIS 式要素编辑保存）"""
    coordinates: Opt[Any] = Field(default=None, description="新的坐标数组（整层替换）")
    properties: Opt[Any] = Field(default=None, description="新的属性数组（整层替换）")
    style: Opt[dict] = Field(default=None, description="新的样式")
    features: Opt[Any] = Field(default=None, description="新的 features 数组（features 型图层）")


@router.post("/{map_id}/marker", response_model=ApiResponse, summary="添加自定义标注点（答辩演示：标注赏樱点/卫生间等）")
async def add_custom_marker(
    map_id: str,
    request: AddMarkerRequest,
    map_service: MapService = Depends(get_map_service),
):
    """在地图上添加自定义标注点，自动创建/复用"自定义标注"图层"""
    try:
        updated = map_service.add_custom_marker(
            map_id, request.name, request.lat, request.lng, request.icon, request.color
        )
        return ApiResponse(success=True, message=f"已添加标注: {request.name}", data=updated)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e), data=None)


@router.put("/{map_id}/layers/{layer_id}/geometry", response_model=ApiResponse,
            summary="更新图层几何/属性（编辑模式保存）")
async def update_layer_geometry(
    map_id: str,
    layer_id: str,
    request: UpdateLayerGeometryRequest,
    map_service: MapService = Depends(get_map_service),
):
    """编辑模式保存：整层替换坐标/属性/样式（前端编辑几何后回写）"""
    try:
        result = map_service.update_layer_geometry(
            map_id=map_id,
            layer_id=layer_id,
            coordinates=request.coordinates,
            properties=request.properties,
            style=request.style,
            features=request.features,
        )
        return ApiResponse(success=True, message="图层几何已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新图层几何失败: {e}")


@router.put("/{map_id}/layers/{layer_id}/visible", response_model=ApiResponse,
            summary="设置图层可见性（持久化隐藏/显示）")
async def set_layer_visible(
    map_id: str,
    layer_id: str,
    request: SetLayerVisibleRequest,
    map_service: MapService = Depends(get_map_service),
):
    """图层管理：隐藏/显示图层并写入地图数据（QGIS/ArcGIS 式）"""
    try:
        result = map_service.set_layer_visible(map_id, layer_id, request.visible)
        return ApiResponse(success=True, message="图层可见性已更新", data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"设置图层可见性失败: {e}")


@router.get("/thematic/types", response_model=ApiResponse, summary="获取支持的专题地图类型")
async def get_thematic_types():
    """获取系统支持的所有专题地图类型及其渲染配置"""
    from app.core.constants import THEMATIC_MAP_CONFIG
    return ApiResponse(success=True, data=THEMATIC_MAP_CONFIG)

@router.post("/generate", response_model=ApiResponse, summary="生成地图")
async def generate_map(
    request: GenerateMapRequest,
    map_service: MapService = Depends(get_map_service),
):
    """根据地图类型与区域生成地图数据"""
    try:
        result = await run_in_thread(
            map_service.generate_map,
            map_type=request.map_type,
            region=request.region,
            center=request.center,
            zoom=request.zoom,
            layers=request.layers,
        )
        return ApiResponse(success=True, message="地图生成成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"地图生成失败: {e}")


@router.get("", response_model=ApiResponse, summary="获取地图列表")
@router.get("/", response_model=ApiResponse, include_in_schema=False)
async def list_maps(
    map_service: MapService = Depends(get_map_service),
):
    """获取所有已生成的地图列表"""
    try:
        result = map_service.list_maps()
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取地图列表失败: {e}")


@router.get("/{map_id}/quality", response_model=ApiResponse, summary="地图数据质量检测（拓扑/属性/统计/专题/标注）")
async def map_quality_check(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """对地图数据执行五类质量检测，返回结构化报告（支持前端定位跳转）"""
    try:
        from app.services.quality_service import QualityService
        map_data = map_service.get_map(map_id)
        if not map_data:
            return ApiResponse(success=False, message=f"地图不存在: {map_id}")
        report = QualityService().check(map_data)
        return ApiResponse(success=True, message="质量检测完成", data=report)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"质量检测失败: {e}")

@router.get("/{map_id}", response_model=ApiResponse, summary="获取地图数据")
async def get_map(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """获取指定地图的完整数据（含图层、视图、样式等）"""
    try:
        result = map_service.get_map(map_id)
        if result is None:
            return ApiResponse(success=False, message="地图不存在")
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取地图数据失败: {e}")


@router.delete("/{map_id}", response_model=ApiResponse, summary="删除地图")
async def delete_map(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """删除指定地图"""
    try:
        map_service.delete_map(map_id)
        return ApiResponse(success=True, message="地图已删除")
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除地图失败: {e}")


@router.post("/{map_id}/layers", response_model=ApiResponse, summary="添加图层")
async def add_layer(
    map_id: str,
    request: AddLayerRequest,
    map_service: MapService = Depends(get_map_service),
):
    """向指定地图添加新图层（如道路、POI、水系等）"""
    try:
        result = map_service.add_layer(
            map_id=map_id,
            layer_type=request.layer_type,
            name=request.name,
            query=request.query,
        )
        return ApiResponse(success=True, message="图层添加成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"添加图层失败: {e}")


@router.delete("/{map_id}/layers/{layer_id}", response_model=ApiResponse, summary="删除图层")
async def remove_layer(
    map_id: str,
    layer_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """删除指定地图中的某个图层"""
    try:
        result = map_service.remove_layer(map_id=map_id, layer_id=layer_id)
        return ApiResponse(success=True, message="图层已删除", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除图层失败: {e}")


@router.put("/{map_id}/layers/{layer_id}", response_model=ApiResponse, summary="更新图层样式")
async def update_layer_style(
    map_id: str,
    layer_id: str,
    request: UpdateLayerStyleRequest,
    map_service: MapService = Depends(get_map_service),
):
    """更新指定图层的样式（颜色、线宽、透明度等）"""
    try:
        # 过滤出用户实际提供的样式字段（忽略未传的None值）
        style = {k: v for k, v in request.model_dump().items() if v is not None}
        result = map_service.update_layer_style(
            map_id=map_id,
            layer_id=layer_id,
            style=style,
        )
        return ApiResponse(success=True, message="图层样式已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新图层样式失败: {e}")


@router.patch("/{map_id}/layers/{layer_id}", response_model=ApiResponse, summary="增量更新图层")
async def patch_layer(
    map_id: str,
    layer_id: str,
    request: dict,
    map_service: MapService = Depends(get_map_service),
):
    """增量更新图层 - 仅修改传入的字段，不影响其他属性

    支持的增量操作：
    - style: 部分更新样式（如仅修改color，保留weight/opacity）
    - visible: 切换图层可见性
    - name: 重命名图层
    """
    try:
        # 获取当前地图数据
        map_data = map_service.get_map(map_id)
        if not map_data:
            return ApiResponse(success=False, message="地图不存在")

        # 找到目标图层
        layers = map_data.get("layers", [])
        target_layer = None
        for layer in layers:
            if layer.get("id") == layer_id:
                target_layer = layer
                break

        if not target_layer:
            return ApiResponse(success=False, message=f"图层不存在: {layer_id}")

        # 应用增量更新
        updated = False
        if "style" in request:
            current_style = target_layer.get("style", {})
            current_style.update(request["style"])
            result = map_service.update_layer_style(map_id, layer_id, current_style)
            updated = True

        if "visible" in request:
            target_layer["visible"] = request["visible"]
            updated = True

        if "name" in request:
            target_layer["name"] = request["name"]
            updated = True

        if not updated:
            return ApiResponse(success=False, message="未提供有效的更新字段")

        # 返回更新后的地图数据
        updated_map = map_service.get_map(map_id)
        return ApiResponse(success=True, message="图层已增量更新", data=updated_map)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"增量更新失败: {e}")


@router.put("/{map_id}/view", response_model=ApiResponse, summary="更新地图视图")
async def update_view(
    map_id: str,
    request: UpdateViewRequest,
    map_service: MapService = Depends(get_map_service),
):
    """更新地图中心点与缩放级别"""
    try:
        result = map_service.update_view(
            map_id=map_id,
            center=request.center,
            zoom=request.zoom,
        )
        return ApiResponse(success=True, message="地图视图已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新地图视图失败: {e}")


@router.put("/{map_id}/theme", response_model=ApiResponse, summary="更新地图主题")
async def update_theme(
    map_id: str,
    request: UpdateThemeRequest,
    map_service: MapService = Depends(get_map_service),
):
    """切换地图底图主题（标准/浅色/深色/卫星）"""
    try:
        result = map_service.update_theme(map_id=map_id, theme=request.theme)
        return ApiResponse(success=True, message="地图主题已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新地图主题失败: {e}")


@router.post(
    "/{map_id}/layers/{layer_id}/features",
    response_model=ApiResponse,
    summary="添加要素",
)
async def add_feature(
    map_id: str,
    layer_id: str,
    request: AddFeatureRequest,
    map_service: MapService = Depends(get_map_service),
):
    """向指定图层添加地理要素（标注点/线/面）"""
    try:
        result = map_service.add_feature(
            map_id=map_id,
            layer_id=layer_id,
            feature_type=request.feature_type,
            coordinates=request.coordinates,
            properties=request.properties,
        )
        return ApiResponse(success=True, message="要素添加成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"添加要素失败: {e}")


@router.delete(
    "/{map_id}/layers/{layer_id}/features/{feature_id}",
    response_model=ApiResponse,
    summary="删除要素",
)
async def remove_feature(
    map_id: str,
    layer_id: str,
    feature_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """删除指定图层中的某个地理要素"""
    try:
        result = map_service.remove_feature(
            map_id=map_id,
            layer_id=layer_id,
            feature_id=feature_id,
        )
        return ApiResponse(success=True, message="要素已删除", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除要素失败: {e}")


@router.post("/{map_id}/modify", response_model=ApiResponse, summary="自然语言修改地图")
async def modify_map(
    map_id: str,
    request: ModifyMapRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """通过自然语言指令动态修改已有地图

    示例指令："把道路颜色改成红色"、"添加武汉大学周边的餐饮点"
    """
    try:
        result = await run_in_thread(
            agent_service.modify_map,
            instruction=request.instruction,
            map_id=map_id,
        )
        return ApiResponse(success=True, message="地图修改完成", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"地图修改失败: {e}")


@router.post("/{map_id}/export", response_model=ApiResponse, summary="导出地图")
async def export_map(
    map_id: str,
    request: ExportMapRequest,
    map_service: MapService = Depends(get_map_service),
    export_service: ExportService = Depends(get_export_service),
):
    """将指定地图导出为 GeoJSON / SVG / PNG 格式"""
    try:
        # 先获取地图数据
        map_data = map_service.get_map(map_id)
        if map_data is None:
            return ApiResponse(success=False, message="地图不存在")

        fmt = request.format.lower()
        if fmt == "geojson":
            result = export_service.export_geojson(map_data)
        elif fmt == "svg":
            result = export_service.export_svg(map_data)
        elif fmt == "png":
            result = export_service.export_png(map_data)
        else:
            return ApiResponse(success=False, message=f"不支持的导出格式: {fmt}")

        return ApiResponse(
            success=True,
            message=f"地图已导出为 {fmt} 格式",
            data=result,
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"地图导出失败: {e}")


@router.post("/{map_id}/route", response_model=ApiResponse, summary="规划路径")
async def plan_route(
    map_id: str,
    request: PlanRouteRequest,
    routing_service: RoutingService = Depends(get_routing_service),
):
    """在指定地图上规划两点之间的路径

    支持驾车(driving)、步行(walking)、骑行(cycling)三种模式，
    可选途经点。返回路径坐标、距离、预计时间及导航步骤。
    """
    try:
        result = await run_in_thread(
            routing_service.plan_route,
            start=request.start,
            end=request.end,
            profile=request.profile,
            waypoints=request.waypoints,
        )
        return ApiResponse(success=True, message="路径规划成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"路径规划失败: {e}")
