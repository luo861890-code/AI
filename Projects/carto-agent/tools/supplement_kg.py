# -*- coding: utf-8 -*-
"""知识图谱知识补录：补齐 CQ 验证缺失的 6 类制图规则。

对应申请书 2.1 的迭代优化闭环（验证不通过 -> 回溯补充知识）。
新增：比例尺、注记避让、境界、图层叠置顺序、道路线宽、水系境界冲突。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "kg", "init_data.json")

NEW_NODES = [
    {"name": "scale_rule_100k", "type": "CartographyRule", "label": "ScaleRule",
     "description": "1:10万比例尺地图：基本等高距10m，图上长度<1cm的河流原则上舍去，计曲线加粗表示",
     "icon": "📐"},
    {"name": "scale_rule_250k", "type": "CartographyRule", "label": "ScaleRule",
     "description": "1:25万比例尺地图：基本等高距50m，高速/国道/省道全部保留，县乡道按密度取舍",
     "icon": "📐"},
    {"name": "contour_interval_rule", "type": "CartographyRule", "label": "ScaleRule",
     "description": "等高距随比例尺减小而增大，同幅地图统一等高距，地形差异大时可加半距等高线",
     "icon": "📐"},
    {"name": "label_avoidance_rule", "type": "CartographyRule", "label": "LabelRule",
     "description": "注记不能压盖河流交汇点、道路交叉口、境界转折点等重要地物，密集区通过缩字号/移动避让",
     "icon": "🔤"},
    {"name": "label_priority_rule", "type": "CartographyRule", "label": "LabelRule",
     "description": "注记字号分级：首都>省会>地市>县>镇>村，舍去的居民点注记同步舍去",
     "icon": "🔤"},
    {"name": "boundary_rule", "type": "CartographyRule", "label": "BoundaryRule",
     "description": "国界/省界绝对保留并严格按权威资料绘制；地级界、县级界按比例尺取舍，飞地必须夸大保留",
     "icon": "🛂"},
    {"name": "boundary_displacement_rule", "type": "CartographyRule", "label": "BoundaryRule",
     "description": "境界沿山脊/河流/道路跳绘时，缩编后须保持跳绘关系准确；被其他符号压盖时境界断开让位",
     "icon": "🛂"},
    {"name": "layer_order_rule", "type": "CartographyRule", "label": "LayerConfig",
     "description": "图层叠置顺序：底图→水系→道路→境界→注记；高等级道路渲染在低等级之上，保证干线优先可见",
     "icon": "🗂️"},
    {"name": "layer_order_admin", "type": "CartographyRule", "label": "LayerConfig",
     "description": "行政区划图叠置顺序：省域底图→市域底图→区县面→境界线→行政中心→注记",
     "icon": "🗂️"},
    {"name": "road_level_rule", "type": "CartographyRule", "label": "SymbolRule",
     "description": "道路按等级分级设线宽与不透明度：高速>干线主干道>主干道>次干道>支路，等级越高线越粗越不透明",
     "icon": "🛣️"},
    {"name": "road_width_rule", "type": "CartographyRule", "label": "SymbolRule",
     "description": "道路线宽建议：高速4-5px、主干道3-4px、次干道2-3px、支路1-1.5px，且主线与匝道样式要区分",
     "icon": "🛣️"},
    {"name": "water_boundary_rule", "type": "CartographyRule", "label": "ConflictRule",
     "description": "以河流为界的境界区分主航道中心线/河流中心线/河岸线三种方式，岛屿归属必须明确",
     "icon": "🌊"},
    {"name": "symbol_conflict_rule", "type": "CartographyRule", "label": "ConflictRule",
     "description": "要素冲突时次要要素位移避让主要要素，优先级：控制点>国界/境界>主要水系>主要交通>居民地>地貌>植被",
     "icon": "⚖️"},
    {"name": "lake_merge_rule", "type": "CartographyRule", "label": "GeneralizationRule",
     "description": "湖泊制图综合：图上间距<0.2-0.3mm的相邻小湖可合并但保持湖群分布格局；最小上图面积2-4mm²",
     "icon": "🪷"},
]

NEW_RELATIONS = [
    ("administrative", "boundary_rule", "CONTAINS_ELEMENT"),
    ("administrative", "layer_order_admin", "HAS_DECISION"),
    ("basic", "layer_order_rule", "HAS_DECISION"),
    ("traffic", "road_level_rule", "HAS_DECISION"),
    ("traffic", "road_width_rule", "HAS_DECISION"),
    ("tourism", "label_avoidance_rule", "HAS_DECISION"),
    ("terrain", "contour_interval_rule", "HAS_DECISION"),
    ("terrain", "scale_rule_250k", "HAS_DECISION"),
    ("water", "water_boundary_rule", "GOVERNED_BY"),
    ("boundary_rule", "symbol_conflict_rule", "RELATES_TO"),
    ("scale_rule_100k", "contour_interval_rule", "RELATES_TO"),
    ("label_avoidance_rule", "symbol_conflict_rule", "RELATES_TO"),
    ("lake_merge_rule", "water_boundary_rule", "RELATES_TO"),
]


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    names = {n.get("name") for n in data["nodes"]}
    added = 0
    for n in NEW_NODES:
        if n["name"] not in names:
            data["nodes"].append(n)
            names.add(n["name"])
            added += 1
    rel_keys = {(r.get("from"), r.get("to"), r.get("type")) for r in data["relations"]}
    added_r = 0
    for f, t, typ in NEW_RELATIONS:
        if (f, t, typ) not in rel_keys:
            data["relations"].append({
                "from": f, "to": t, "type": typ,
                "properties": {"description": f"{f} -> {t}（{typ}）", "priority": "high"},
            })
            added_r += 1
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[KG] 补录完成: +{added} 节点, +{added_r} 关系 -> "
          f"共 {len(data['nodes'])} 节点 / {len(data['relations'])} 关系")


if __name__ == "__main__":
    main()
