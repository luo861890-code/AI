# -*- coding: utf-8 -*-
"""存量行政区划图样式规范化（与 carto-agent-1 参考图完全一致）

对 data/maps.json 与 data/archive/maps/ 中所有行政区划图执行：
1. 道路图层统一不透明度 0.9
2. 区县/市级行政中心 fillOpacity 恢复 1.0
3. 重点地标过滤掉 carto-agent 新增的樱花主题 POI（恢复 8 个）

用法: python tools/normalize_admin_maps.py
"""
import json
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
MAPS_FILE = os.path.join(DATA_DIR, "maps.json")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive", "maps")

ROAD_PREFIX = "道路-"
CHERRY_POIS = {"武汉大学樱花大道", "东湖磨山樱花园", "晴川阁樱花园"}
BASE_POI_NAMES = {
    "武汉天河国际机场", "木兰文化生态旅游区", "黄鹤楼", "东湖绿道",
    "湖北省博物馆", "武汉站", "汉口站", "光谷广场",
}


def normalize_map(md: dict) -> int:
    """规范化一张行政区划图，返回修改的图层数"""
    if md.get("map_type") != "administrative":
        return 0
    changed = 0
    for layer in md.get("layers", []):
        style = layer.get("style") or {}
        name = layer.get("name") or ""
        # 1) 道路统一不透明度 0.9
        if name.startswith(ROAD_PREFIX) and style.get("opacity") != 0.9:
            style["opacity"] = 0.9
            changed += 1
        # 2) 行政中心 fillOpacity 1.0
        if name in ("区县行政中心", "市级行政中心") and style.get("fillOpacity") != 1.0:
            style["fillOpacity"] = 1.0
            changed += 1
        # 3) 重点地标过滤樱花 POI
        if name == "重点地标":
            props = layer.get("properties") or []
            coords = layer.get("coordinates") or []
            keep_idx = [i for i, p in enumerate(props) if p.get("name") not in CHERRY_POIS]
            if len(keep_idx) != len(coords):
                layer["coordinates"] = [coords[i] for i in keep_idx]
                layer["properties"] = [props[i] for i in keep_idx]
                changed += 1
    return changed


def normalize_file(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    total = 0
    if isinstance(data, dict):
        for md in data.values():
            if isinstance(md, dict):
                total += normalize_map(md)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    print(f"[normalize] {path}: 修改 {total} 个图层")


def main():
    normalize_file(MAPS_FILE)
    if os.path.isdir(ARCHIVE_DIR):
        for fn in sorted(os.listdir(ARCHIVE_DIR)):
            if fn.endswith(".json") and not fn.startswith("_"):
                normalize_file(os.path.join(ARCHIVE_DIR, fn))
    print("[normalize] 完成：所有行政区划图已统一为 carto-agent-1 参考样式")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
