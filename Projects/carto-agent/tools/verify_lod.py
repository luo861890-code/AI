# -*- coding: utf-8 -*-
"""LOD 显隐规则验证脚本

用真实地图数据模拟 carto-agent-1 map-lod.js 的按比例尺分级显隐，
确认 carto-agent Vue 前端移植后的 LOD 行为一致。

用法: python tools/verify_lod.py [zoom ...]
"""
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_FILE = os.path.join(ROOT, "data", "maps.json")


ROAD_LEVEL = {
    "motorway": 0, "motorway_link": 1,
    "trunk": 1, "trunk_link": 2,
    "primary": 2, "primary_link": 3,
    "secondary": 3, "secondary_link": 4,
    "tertiary": 4, "tertiary_link": 5,
    "residential": 5, "living_street": 5, "service": 5,
    "unclassified": 5, "other": 5,
}


def road_level(layer: dict) -> int:
    nm = layer.get("name", "") or ""
    raw = (layer.get("metadata") or {}).get("raw_class")
    if raw in ROAD_LEVEL:
        return ROAD_LEVEL[raw]
    if nm.startswith("道路-"):
        head = nm.replace("道路-", "").split("_")[0]
        if head in ROAD_LEVEL:
            return ROAD_LEVEL[head]
        if "高速公路" in nm or "高速互通" in nm:
            return 0
        if "城市干线主干道" in nm or "主干道连接" in nm or "主干道衔接" in nm:
            return 1
        if "城市主干道" in nm:
            return 2
        if "城市次干道" in nm or "次干道连接" in nm:
            return 3
        if "三级道路" in nm:
            return 4
        return 5
    if "高速公路" in nm:
        return 0
    if "国道" in nm or "主干道" in nm:
        return 1
    if "省道" in nm:
        return 2
    if "次干道" in nm:
        return 3
    if "三级道路" in nm:
        return 4
    return 5


def lod_visible(layer: dict, z: float) -> bool:
    nm = layer.get("name", "") or ""
    t = layer.get("type", "") or ""
    if t in ("polyline", "line"):
        if nm.startswith("道路-") or any(k in nm for k in (
                "高速", "国道", "主干道", "省道", "次干道", "支路",
                "社区道路", "服务道路", "其他道路", "三级道路")):
            level = road_level(layer)
            max_show = 0 if z < 9 else 1 if z < 11 else 3 if z < 13 else 4 if z < 15 else 5
            return level <= max_show
        if nm == "河流中心线（主要）":
            return z >= 9
        if nm == "河流中心线（支流）":
            return z >= 12
        if nm == "等高线（计曲线）":
            return z >= 9
        if nm == "等高线（首曲线）":
            return z >= 11
        if nm == "支流溪流" or "河源细流" in nm:
            return z >= 13
        if nm == "主要河流":
            return z >= 11
        return True
    if t in ("polygon", "area"):
        if nm == "河流水面":
            return z >= 11
        if nm == "集中居民地（大型）":
            return z >= 11
        if nm == "集中居民地（中型）":
            return z >= 13
        if nm == "集中居民地（小型）":
            return z >= 15
        if nm in ("湖泊（概览级）", "湖泊点符号（概览）"):
            return 6 <= z < 9
        if nm == "湖泊（市域级）":
            return 9 <= z < 11
        if nm == "湖泊（城区级）":
            return 11 <= z < 13
        if nm == "湖泊（详图级）":
            return z >= 13
        if any(k in nm for k in ("住宅", "公寓", "宿舍", "商业", "零售", "酒店", "工业",
                                 "公共", "政府", "学校", "大学", "医院", "宗教", "文化",
                                 "体育", "停车", "车库", "仓储", "交通枢纽", "农业", "温室")):
            return z >= 13
        if any(k in nm for k in ("绿地", "公园", "森林", "草地", "草甸", "用地")):
            return z >= 11
        return True
    if t in ("textLabel", "label"):
        if nm == "水系注记":
            return z >= 12
        if nm == "区县名称标注":
            return z >= 9
        if nm in ("地标名称", "重点地标"):
            return z >= 11
        return True
    if t in ("circleMarker", "point", "marker"):
        if nm == "湖泊点符号（概览）":
            return 6 <= z < 9
        if nm in ("市级行政中心", "区县行政中心", "乡镇居民点"):
            return z >= 8
        if nm == "重点地标":
            return z >= 11
        return z >= 12
    return True


def main():
    zooms = [float(x) for x in sys.argv[1:]] or [9, 10.5, 12]
    with open(MAPS_FILE, encoding="utf-8") as f:
        maps = json.load(f)
    admin = next((md for md in maps.values() if md.get("map_type") == "administrative"), None)
    if admin is None:
        print("未找到行政区划图")
        return 1
    for z in zooms:
        shown = [ly["name"] for ly in admin["layers"] if lod_visible(ly, z)]
        hidden = [ly["name"] for ly in admin["layers"] if not lod_visible(ly, z)]
        print(f"--- zoom {z}: shown {len(shown)} / hidden {len(hidden)} ---")
        print("  shown:", shown)
        print("  hidden:", hidden)
    return 0


if __name__ == "__main__":
    sys.exit(main())
