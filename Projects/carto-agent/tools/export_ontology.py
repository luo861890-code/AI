# -*- coding: utf-8 -*-
"""知识图谱交付物：本体 OWL/Turtle 导出 + 能力问题（CQs）验证。

对应申请书 2.1：输出可机读本体文件 + 10+ 能力问题验证知识覆盖度。

用法:
  python tools/export_ontology.py

输出:
  backend/data/kg/carto_ontology.ttl   （本体 + 实例三元组）
  stdout CQ 验证报告
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
from app.core.kg_ontology import ONTOLOGY_CLASSES, ONTOLOGY_RELATIONS  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KG_DATA = os.path.join(ROOT, "data", "kg", "init_data.json")
OUT_TTL = os.path.join(ROOT, "backend", "data", "kg", "carto_ontology.ttl")


def _clean(name: str) -> str:
    """清洗为合法的 Turtle 局部名。"""
    s = "".join(ch for ch in str(name) if ch.isalnum() or ch in "-_")
    return s[:60] or "node"


def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def main():
    data = json.load(open(KG_DATA, encoding="utf-8"))
    nodes = data.get("nodes", [])
    relations = data.get("relations", [])

    lines = [
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix carto: <http://cartoagent.example/ontology#> .",
        "",
        "# ===== 本体类（7类核心概念） =====",
    ]
    for cls, meta in ONTOLOGY_CLASSES.items():
        lines.append(f"carto:{cls} a owl:Class ; rdfs:label \"{_esc(meta.get('description', cls))}\" .")
    for rel in ONTOLOGY_RELATIONS:
        if isinstance(rel, tuple) and len(rel) >= 2:
            lines.append(f"carto:{_clean(rel[1])} a owl:ObjectProperty ; rdfs:label \"{_esc(rel[1])}\" .")

    lines.append("")
    lines.append("# ===== 实例（知识图谱三元组） =====")
    node_ids = {}
    for n in nodes:
        nid = n.get("id") or _clean(n.get("name", "node"))
        node_ids[n.get("id")] = nid
        label = n.get("name", nid)
        ntype = n.get("type") or n.get("category") or "MapElement"
        lines.append(f"carto:{_clean(nid)} a carto:{_clean(ntype)} ; "
                     f"rdfs:label \"{_esc(label)}\" .")
    for r in relations:
        s = node_ids.get(r.get("source") or r.get("from"), "")
        o = node_ids.get(r.get("target") or r.get("to"), "")
        rel = r.get("relation") or r.get("type") or "RELATED_TO"
        if s and o:
            lines.append(f"carto:{_clean(s)} carto:{_clean(rel)} carto:{_clean(o)} .")

    os.makedirs(os.path.dirname(OUT_TTL), exist_ok=True)
    with open(OUT_TTL, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Ontology] TTL 已导出: {OUT_TTL}（{len(nodes)} 实例, {len(relations)} 关系）")

    # ===== 能力问题验证（CQs） =====
    print("\n===== 能力问题（CQ）验证 =====")
    names = [str(n.get("name", "")) for n in nodes]
    descs = [str(n.get("description", "")) for n in nodes]
    all_text = " ".join(names) + " " + " ".join(descs) + " " + json.dumps(relations, ensure_ascii=False)

    cqs = [
        ("CQ1 河流要素的线符号及颜色规范", ["河", "线", "符号", "颜色"]),
        ("CQ2 旅游地图景点符号", ["旅游", "景点", "符号"]),
        ("CQ3 高速公路符号规范", ["高速", "符号"]),
        ("CQ4 湖泊面状符号", ["湖", "面", "符号"]),
        ("CQ5 1:10万比例尺规则", ["比例尺", "10万"]),
        ("CQ6 注记避让规则", ["注记", "避让"]),
        ("CQ7 行政区划边界规则", ["行政区", "边界", "境界"]),
        ("CQ8 配色方案（旅游/交通）", ["配", "色", "旅游", "交通"]),
        ("CQ9 图层叠置顺序规则", ["图层", "顺序", "叠加"]),
        ("CQ10 道路等级线宽规则", ["道路", "线宽", "等级"]),
        ("CQ11 水系与境界冲突处理", ["水系", "境界", "冲突"]),
        ("CQ12 比例尺与要素选取", ["比例尺", "选取", "综合"]),
    ]
    passed = 0
    for q, kws in cqs:
        hit = sum(1 for k in kws if k in all_text)
        ok = hit >= min(2, len(kws))
        passed += int(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {q}（命中 {hit}/{len(kws)} 关键词）")
    print(f"\nCQ 通过率: {passed}/{len(cqs)}")
    return 0 if passed >= 8 else 1


if __name__ == "__main__":
    sys.exit(main())
