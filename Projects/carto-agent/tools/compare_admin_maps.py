# -*- coding: utf-8 -*-
"""对比 carto-agent-1 与 carto-agent 存储的武汉市行政区划图逐层差异

用于验证"完美复刻"：列出两张行政图在图层名称、样式、要素数量上的全部差异。

用法:
    python tools/compare_admin_maps.py                  # 对比 carto-agent-1 参考图与 carto-agent 当前最新行政图
    python tools/compare_admin_maps.py <ref.json> <cur.json>   # 对比任意两个 maps.json
"""
import json
import os
import re
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(os.path.dirname(ROOT), "carto-agent-1", "data", "maps.json")
CUR = os.path.join(ROOT, "data", "maps.json")

STYLE_KEYS = ["color", "fillColor", "weight", "opacity", "fillOpacity", "dashArray", "radius"]

# 道路中文名 -> 英文名（用于对齐比较）
ROAD_CN_TO_EN = {
    "居民区街区道路": "residential",
    "三级道路（次要道路）": "tertiary",
    "三级道路连接线": "tertiary_link",
    "高速互通匝道": "motorway_link",
    "城市次干道": "secondary",
    "次干道连接匝道": "secondary_link",
    "主干道衔接匝道": "primary_link",
    "城市主干道": "primary",
    "主干道连接匝道": "trunk_link",
    "城市干线主干道": "trunk",
    "高速公路主线": "motorway",
}


def load_admin(path, latest=True):
    with open(path, encoding="utf-8") as f:
        maps = json.load(f)
    admins = [md for md in maps.values() if md.get("map_type") == "administrative"]
    if latest:
        return admins[-1]
    return admins[0]


def norm(v):
    return round(v, 3) if isinstance(v, (int, float)) else v


def sig(layer):
    st = layer.get("style") or {}
    return {k: norm(st.get(k)) for k in STYLE_KEYS}


def norm_name(name):
    name = name or ""
    m = re.match(r"道路-(.+)$", name)
    if m:
        return "道路-" + ROAD_CN_TO_EN.get(m.group(1), m.group(1))
    return name


def main():
    if len(sys.argv) >= 3:
        ref = load_admin(sys.argv[1], latest=False)
        cur = load_admin(sys.argv[2])
    else:
        ref = load_admin(REF, latest=False)  # carto-agent-1 最旧的参考行政图
        cur = load_admin(CUR)                # carto-agent 最新的行政图
    print("参考(carto-agent-1):", ref["map_id"], ref["name"], "created", ref["created_at"])
    print("当前(carto-agent)  :", cur["map_id"], cur["name"], "created", cur["created_at"])
    print()

    diffs = 0
    cur_by_name = {norm_name(l["name"]): l for l in cur["layers"]}
    for lr in ref["layers"]:
        lc = cur_by_name.get(norm_name(lr["name"]))
        if lc is None:
            print("[仅参考有]", lr["name"])
            diffs += 1
            continue
        sr, sc = sig(lr), sig(lc)
        nr, nc = norm_name(lr["name"]), norm_name(lc["name"])
        style_diff = [k for k in STYLE_KEYS if sr[k] != sc[k]]
        name_diff = "" if nr == nc else "名称: %s -> %s" % (lr["name"], lc["name"])
        nref = lr.get("coordinates") or lr.get("features") or []
        ncur = lc.get("coordinates") or lc.get("features") or []
        cnt = "数量: %d -> %d" % (len(nref), len(ncur)) if len(nref) != len(ncur) else ""
        if style_diff or name_diff or cnt:
            diffs += 1
            print("•", lr["name"])
            if style_diff:
                print("   样式差:", {k: (sr[k], sc[k]) for k in style_diff})
            if name_diff:
                print("   ", name_diff)
            if cnt:
                print("   ", cnt)
    print()
    print("共 %d 处差异 / %d 层" % (diffs, len(ref["layers"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
