# -*- coding: utf-8 -*-
"""数据瘦身迁移脚本

解决 maps.json / sessions.json 无限膨胀问题：
1. 地图：主文件只保留最近 N 张（默认 10），更早的按 map_id 归档到
   data/archive/maps/{map_id}.json，并生成 _manifest.json 清单；
2. 会话：assistant 消息不再内嵌完整地图数据，改为 map_id + map_summary 轻量引用；
3. 原文件整体搬入 data/archive/backup_YYYYMMDD/ 作为安全备份（移动，不复制）。

用法：
    python tools/migrate_data.py [--keep 10]
"""
import argparse
import json
import os
import shutil
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
MAPS_FILE = os.path.join(DATA_DIR, "maps.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")


def human_size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def build_map_summary(map_data: dict) -> dict:
    return {
        key: map_data.get(key)
        for key in ("name", "map_type", "region", "center", "zoom", "theme")
        if map_data.get(key) is not None
    }


def migrate_maps(keep: int) -> int:
    """归档旧地图并产出瘦身后的 maps.json.new，返回归档数量（不替换原文件）"""
    if not os.path.exists(MAPS_FILE):
        print("[migrate] maps.json 不存在，跳过")
        return 0
    with open(MAPS_FILE, "r", encoding="utf-8") as f:
        maps = json.load(f)
    if not isinstance(maps, dict):
        print(f"[migrate] maps.json 格式异常（期望 dict），跳过")
        return 0
    print(f"[migrate] 加载地图: {len(maps)} 张, {human_size(os.path.getsize(MAPS_FILE))}")

    items = sorted(
        maps.items(),
        key=lambda kv: (kv[1].get("created_at", 0) if isinstance(kv[1], dict) else 0),
    )
    overflow = items[: max(0, len(items) - keep)]
    archived = 0
    if overflow:
        archive_dir = os.path.join(DATA_DIR, "archive", "maps")
        os.makedirs(archive_dir, exist_ok=True)
        manifest_path = os.path.join(archive_dir, "_manifest.json")
        manifest = []
        for map_id, map_data in overflow:
            with open(os.path.join(archive_dir, f"{map_id}.json"), "w", encoding="utf-8") as f:
                json.dump(map_data, f, ensure_ascii=False)
            manifest.append({
                "map_id": map_id,
                "name": map_data.get("name", ""),
                "map_type": map_data.get("map_type", ""),
                "region": map_data.get("region", ""),
                "created_at": map_data.get("created_at"),
                "file": f"{map_id}.json",
            })
            del maps[map_id]
            archived += 1
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"[migrate] 归档地图: {archived} 张 -> data/archive/maps/")

    new_path = MAPS_FILE + ".new"
    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(maps, f, ensure_ascii=False)
    # 校验临时文件可解析
    with open(new_path, "r", encoding="utf-8") as f:
        json.load(f)
    print(f"[migrate] maps.json 瘦身后: {len(maps)} 张, {human_size(os.path.getsize(MAPS_FILE))}")
    return archived


def migrate_sessions() -> int:
    """将会话消息中的完整地图数据替换为轻量引用，产出 sessions.json.new，返回转换数（不替换原文件）"""
    if not os.path.exists(SESSIONS_FILE):
        print("[migrate] sessions.json 不存在，跳过")
        return 0
    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        sessions = json.load(f)
    if not isinstance(sessions, dict):
        print("[migrate] sessions.json 格式异常（期望 dict），跳过")
        return 0
    print(f"[migrate] 加载会话: {len(sessions)} 个, {human_size(os.path.getsize(SESSIONS_FILE))}")

    converted = 0
    for session in sessions.values():
        if not isinstance(session, dict):
            continue
        for msg in session.get("messages", []):
            if not isinstance(msg, dict):
                continue
            map_data = msg.get("map_data")
            if isinstance(map_data, dict):
                map_id = map_data.get("map_id") or map_data.get("id")
                if map_id:
                    msg["map_id"] = map_id
                    msg["map_summary"] = build_map_summary(map_data)
                    msg["map_data"] = None
                    converted += 1
                elif "layers" in map_data:
                    # 无 map_id 但确实携带了地图数据：仅保留摘要
                    msg["map_id"] = None
                    msg["map_summary"] = build_map_summary(map_data)
                    msg["map_data"] = None
                    converted += 1

    new_path = SESSIONS_FILE + ".new"
    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False)
    with open(new_path, "r", encoding="utf-8") as f:
        json.load(f)
    print(f"[migrate] 转换消息: {converted} 条")
    return converted


def backup_originals():
    """将迁移前的原始文件整体移入备份目录，保留可恢复现场"""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(DATA_DIR, "archive", f"backup_{stamp}")
    os.makedirs(backup_dir, exist_ok=True)
    for name in ("maps.json", "sessions.json", "maps.json.bak", "maps_test_backup.json"):
        src = os.path.join(DATA_DIR, name)
        if os.path.exists(src):
            dst = os.path.join(backup_dir, name)
            shutil.move(src, dst)
            print(f"[migrate] 原始文件已备份: {name} -> data/archive/backup_{stamp}/")
    return backup_dir


def finalize():
    """备份原文件后，将瘦身产物替换到位"""
    backup_dir = backup_originals()
    for name in ("maps.json", "sessions.json"):
        new_path = os.path.join(DATA_DIR, name + ".new")
        if os.path.exists(new_path):
            os.replace(new_path, os.path.join(DATA_DIR, name))
            print(f"[migrate] 已替换: {name} -> {human_size(os.path.getsize(os.path.join(DATA_DIR, name)))}")
    return backup_dir


def main():
    parser = argparse.ArgumentParser(description="carto-agent 数据瘦身迁移")
    parser.add_argument("--keep", type=int, default=10, help="主文件保留最近 N 张地图")
    args = parser.parse_args()

    print("=" * 60)
    print("carto-agent 数据瘦身迁移")
    print("=" * 60)
    migrated_maps = migrate_maps(args.keep)
    migrated_msgs = migrate_sessions()
    finalize()
    print("=" * 60)
    print(f"完成：归档地图 {migrated_maps} 张，转换消息 {migrated_msgs} 条")
    print("原始文件已完整保留在 data/archive/backup_* 中，可随时恢复")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
