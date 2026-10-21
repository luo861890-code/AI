# -*- coding: utf-8 -*-
"""高德地图数据服务 - 通过高德Web服务API获取POI数据，补充OSM数据源

当 backend/.env 配置 AMAP_API_KEY 后自动启用；
未配置时优雅降级（打印提示），不影响OSM主数据源。
"""
import requests

from app.core.config import settings


class AmapService:
    """高德POI数据获取服务"""

    BASE_URL = "https://restapi.amap.com/v3/place"

    # 高德POI类型关键字 -> 我们的POI分类(与POI_STYLES对应)
    TYPE_KEYWORDS = {
        "restaurant": ["餐厅", "火锅", "小吃", "面馆"],
        "cafe": ["咖啡", "茶馆"],
        "fast_food": ["快餐", "汉堡", "炸鸡"],
        "supermarket": ["超市", "便利店"],
        "mall": ["商场", "购物中心", "百货"],
        "hospital": ["医院", "诊所", "药店"],
        "school": ["学校", "小学", "中学"],
        "university": ["大学", "学院"],
        "library": ["图书馆"],
        "transport": ["火车站", "汽车站", "机场"],
        "subway": ["地铁站"],
        "bus": ["公交站"],
        "parking": ["停车场"],
        "fuel": ["加油站"],
        "hotel": ["酒店", "宾馆", "旅馆"],
        "attraction": ["景点", "景区", "公园"],
        "museum": ["博物馆", "展览馆"],
        "bank": ["银行", "ATM"],
        "police": ["派出所", "公安局"],
        "post": ["邮局"],
        "cinema": ["电影院"],
        "sports": ["体育馆", "运动场"],
        "government": ["政府", "政务"],
    }

    def __init__(self):
        self.key = getattr(settings, "amap_api_key", "") or ""
        self.enabled = bool(self.key)
        if not self.enabled:
            print("[AmapService] 未配置 AMAP_API_KEY，跳过高德数据补充（在 backend/.env 填写后自动启用）")

    def search_pois(self, keyword: str, city: str, offset: int = 25) -> list:
        """高德关键字搜索POI，返回OSM风格元素列表"""
        try:
            resp = requests.get(
                self.BASE_URL + "/text",
                params={
                    "key": self.key, "keywords": keyword, "city": city,
                    "offset": offset, "page": 1, "extensions": "base",
                },
                timeout=10,
                headers={"User-Agent": "CartoAgent/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[AmapService] 关键字[{keyword}]搜索失败: {e}")
            return []
        if str(data.get("status")) != "1":
            return []
        elements = []
        for poi in data.get("pois") or []:
            loc = (poi.get("location") or "").split(",")
            if len(loc) != 2:
                continue
            try:
                lng, lat = float(loc[0]), float(loc[1])
            except ValueError:
                continue
            elements.append({
                "type": "node",
                "lat": lat,
                "lon": lng,
                "tags": {
                    "amenity": keyword,  # 由搜索词归类，_classify_poi再映射到POI分类
                    "name": poi.get("name", ""),
                    "source": "amap",
                },
            })
        return elements

    def fetch_region_pois(self, region: str, map_type: str, limit_keywords: int = 10) -> list:
        """按地图类型获取城市POI集合（有key时调用，返回OSM风格元素）"""
        if not self.enabled:
            return []
        # 不同地图类型选择关注的POI类别
        type_priority = {
            "traffic": ["subway", "bus", "parking", "fuel", "transport"],
            "tourism": ["attraction", "museum", "hotel", "park"],
            "food": ["restaurant", "cafe", "fast_food"],
            "campus": ["school", "university", "library"],
            "commercial": ["mall", "supermarket", "bank"],
            "healthcare": ["hospital"],
            "education": ["school", "university", "library"],
            "basic": ["restaurant", "supermarket", "mall", "hospital", "school",
                      "subway", "bus", "parking", "fuel", "hotel", "attraction",
                      "museum", "bank", "cinema", "sports", "post", "police"],
        }
        keys = type_priority.get(map_type, type_priority["basic"])[:limit_keywords]
        all_elements = []
        for cat in keys:
            keywords = self.TYPE_KEYWORDS.get(cat, [cat])
            for kw in keywords[:2]:
                all_elements.extend(self.search_pois(kw, region))
        # 去重（按坐标+名称）
        seen = set()
        unique = []
        for e in all_elements:
            key = (round(e["lat"], 5), round(e["lon"], 5), e["tags"].get("name", ""))
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)
        print(f"[AmapService] 高德POI补充完成: {region} 共 {len(unique)} 个")
        return unique
