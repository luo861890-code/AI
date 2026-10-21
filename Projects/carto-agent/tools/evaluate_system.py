# -*- coding: utf-8 -*-
"""系统评估脚本（申请书 2.4 实证驱动）：

对指定地图类型批量执行生成 -> 质量检测 -> 修改反馈，统计：
  - 任务完成率（生成成功且图层数>0）
  - 端到端延迟（生成耗时 / 修改耗时 / 质检耗时）
  - 质量异常项数（规范性反馈）
  - 修改反馈成功率（AI 是否能响应修改意见）

用法:
  python tools/evaluate_system.py            # 默认 4 类地图
  python tools/evaluate_system.py --types traffic,terrain
"""
import argparse
import json
import os
import subprocess
import sys
import time

API = os.environ.get("CARTO_API", "http://127.0.0.1:8080")


def _req(method, url, payload=None, timeout=1200):
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "eval_tmp.json")
    cmd = ["curl.exe", "-s", "-X", method, API + url, "--max-time", str(timeout)]
    if payload is not None:
        json.dump(payload, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@" + tmp]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"success": False, "message": r.stdout[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", default="administrative,traffic,tourism,terrain")
    args = ap.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]

    print(f"{'地图类型':<16}{'生成耗时':>10}{'图层数':>8}{'质检异常':>10}{'生成':>6}{'修改':>6}")
    print("-" * 62)
    results = []
    for mt in types:
        t0 = time.time()
        gen = _req("POST", "/api/maps/generate", {"map_type": mt, "region": "武汉市"})
        gen_time = time.time() - t0
        md = gen.get("data") or {}
        mid = md.get("map_id")
        layers = len(md.get("layers", []))
        gen_ok = bool(gen.get("success") and layers > 0)

        q_failed = "-"
        if gen_ok and mid:
            q = _req("GET", f"/api/maps/{mid}/quality", timeout=300)
            q_failed = (q.get("data") or {}).get("summary", {}).get("failed", 0)

        mod_ok = "-"
        if gen_ok and mid:
            t1 = time.time()
            mod = _req("POST", f"/api/maps/{mid}/modify", {"instruction": "把主要河流改成蓝色"}, timeout=120)
            mod_time = time.time() - t1
            inner = mod.get("data") or mod
            mod_ok = bool(inner.get("success"))
            print(f"{mt:<16}{gen_time:>8.1f}s{layers:>8}{str(q_failed):>10}{str(gen_ok):>6}{str(mod_ok):>6}  (修改{mod_time:.1f}s)")
        else:
            print(f"{mt:<16}{gen_time:>8.1f}s{layers:>8}{str(q_failed):>10}{str(gen_ok):>6}{str(mod_ok):>6}")

        results.append({
            "type": mt, "gen_time": round(gen_time, 1), "layers": layers,
            "gen_ok": gen_ok, "quality_failed": q_failed, "modify_ok": mod_ok,
        })
        if mid:
            _req("DELETE", f"/api/maps/{mid}", timeout=60)

    ok = sum(1 for r in results if r["gen_ok"])
    mods = [r for r in results if isinstance(r["modify_ok"], bool)]
    mod_ok = sum(1 for r in mods if r["modify_ok"])
    print("-" * 62)
    print(f"任务完成率: {ok}/{len(results)}")
    if mods:
        print(f"修改反馈成功率: {mod_ok}/{len(mods)}")
    print(f"平均生成耗时: {sum(r['gen_time'] for r in results) / len(results):.1f}s")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
