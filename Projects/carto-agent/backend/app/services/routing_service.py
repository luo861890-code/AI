"""路径规划服务 - 基于OSRM公共API的路径规划

支持驾车、步行、骑行三种模式的路径规划，
返回路径坐标、距离、预计时间等信息。
当OSRM服务不可用时，使用直线连接作为降级方案。
"""
import math
from typing import List, Dict, Any, Optional

import requests

from app.core.exceptions import CartoAgentError


class RoutingService:
    """路径规划服务

    使用OSRM公共API进行路径规划，支持多种出行方式。
    OSRM不可用时自动降级为直线连接方案。
    """

    # OSRM公共服务器
    OSRM_SERVER = "https://router.project-osrm.org/route/v1"

    # 出行方式映射
    PROFILE_MAP = {
        "driving": "driving",    # 驾车
        "walking": "foot",       # 步行
        "cycling": "bike",       # 骑行
    }

    # 出行方式中文名
    PROFILE_NAMES = {
        "driving": "驾车",
        "walking": "步行",
        "cycling": "骑行",
    }

    def __init__(self):
        """初始化路径规划服务"""
        print("[RoutingService] 初始化完成，使用OSRM公共API")

    def plan_route(
        self,
        start: List[float],
        end: List[float],
        profile: str = "driving",
        waypoints: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """规划路径

        Args:
            start: 起点坐标 [lat, lng]
            end: 终点坐标 [lat, lng]
            profile: 出行方式 driving/walking/cycling
            waypoints: 途经点列表 [[lat, lng], ...]，可选

        Returns:
            路径规划结果:
            - coordinates: 路径坐标列表 [[lat, lng], ...]
            - distance: 总距离（米）
            - duration: 预计时间（秒）
            - profile: 出行方式
            - start: 起点坐标
            - end: 终点坐标
            - waypoints: 途经点列表

        Raises:
            CartoAgentError: 路径规划失败
        """
        osrm_profile = self.PROFILE_MAP.get(profile, "driving")

        # 构建OSRM请求坐标（OSRM使用 lng,lat 格式）
        coords = [f"{start[1]},{start[0]}"]
        if waypoints:
            for wp in waypoints:
                coords.append(f"{wp[1]},{wp[0]}")
        coords.append(f"{end[1]},{end[0]}")

        coord_str = ";".join(coords)
        url = f"{self.OSRM_SERVER}/{osrm_profile}/{coord_str}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
        }

        try:
            print(f"[RoutingService] 请求OSRM路径规划: {profile}模式, "
                  f"起点({start[0]:.4f}, {start[1]:.4f}) -> "
                  f"终点({end[0]:.4f}, {end[1]:.4f})")

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "Ok" or not data.get("routes"):
                print(f"[RoutingService] OSRM返回错误: {data.get('message', '未知错误')}")
                return self._fallback_route(start, end, profile, waypoints)

            route = data["routes"][0]
            geometry = route.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            # OSRM返回的坐标是 [lng, lat]，需要转换为 [lat, lng]
            route_coords = [[coord[1], coord[0]] for coord in coordinates]

            result = {
                "coordinates": route_coords,
                "distance": route.get("distance", 0),
                "duration": route.get("duration", 0),
                "profile": profile,
                "profile_name": self.PROFILE_NAMES.get(profile, profile),
                "start": start,
                "end": end,
                "waypoints": waypoints or [],
                "source": "osrm",
                "steps": self._extract_steps(route.get("legs", [])),
            }

            distance_km = result["distance"] / 1000
            duration_min = result["duration"] / 60
            print(f"[RoutingService] 路径规划成功: {len(route_coords)}个坐标点, "
                  f"距离{distance_km:.2f}km, 预计{duration_min:.0f}分钟")

            return result

        except requests.exceptions.RequestException as e:
            print(f"[RoutingService] OSRM请求失败: {e}，使用降级方案")
            return self._fallback_route(start, end, profile, waypoints)
        except Exception as e:
            print(f"[RoutingService] 路径规划异常: {e}，使用降级方案")
            return self._fallback_route(start, end, profile, waypoints)

    def _extract_steps(self, legs: List[dict]) -> List[Dict[str, str]]:
        """从OSRM返回的legs中提取导航步骤

        Args:
            legs: OSRM返回的路径段列表

        Returns:
            导航步骤列表，每项包含 instruction, distance, duration
        """
        steps = []
        for leg in legs:
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                instruction = maneuver.get("type", "继续")
                if maneuver.get("modifier"):
                    instruction = f"{maneuver['modifier']} {instruction}"

                # 获取道路名称
                name = step.get("name", "")
                if name:
                    instruction = f"{instruction}进入{name}"

                steps.append({
                    "instruction": instruction,
                    "distance": step.get("distance", 0),
                    "duration": step.get("duration", 0),
                })
        return steps[:20]  # 最多返回20步

    def _fallback_route(
        self,
        start: List[float],
        end: List[float],
        profile: str,
        waypoints: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """降级路径规划 - 使用直线连接

        当OSRM不可用时，用起点、途经点、终点的直线连接作为路径。

        Args:
            start: 起点坐标
            end: 终点坐标
            profile: 出行方式
            waypoints: 途经点列表

        Returns:
            路径规划结果（直线方案）
        """
        coords = [start]
        if waypoints:
            coords.extend(waypoints)
        coords.append(end)

        # 计算总距离（Haversine公式）
        total_distance = 0
        for i in range(len(coords) - 1):
            total_distance += self._haversine_distance(
                coords[i][0], coords[i][1],
                coords[i + 1][0], coords[i + 1][1],
            )

        # 根据出行方式估算时间
        speed_map = {"driving": 40, "walking": 5, "cycling": 15}  # km/h
        speed = speed_map.get(profile, 40)
        duration = (total_distance / 1000) / speed * 3600  # 转换为秒

        print(f"[RoutingService] 使用直线降级方案: {len(coords)}个点, "
              f"距离{total_distance / 1000:.2f}km")

        return {
            "coordinates": coords,
            "distance": total_distance,
            "duration": duration,
            "profile": profile,
            "profile_name": self.PROFILE_NAMES.get(profile, profile),
            "start": start,
            "end": end,
            "waypoints": waypoints or [],
            "source": "fallback",
            "steps": [],
        }

    def _haversine_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """使用Haversine公式计算两点间距离（米）

        Args:
            lat1, lng1: 第一个点的纬度和经度
            lat2, lng2: 第二个点的纬度和经度

        Returns:
            两点间距离（米）
        """
        R = 6371000  # 地球半径（米）
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c
