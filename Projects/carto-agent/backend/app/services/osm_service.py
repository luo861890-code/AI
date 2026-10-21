"""OSM数据获取服务 - 通过Overpass API获取OpenStreetMap地理要素数据

支持多服务器轮询重试机制，确保在服务器不可用时自动切换。
使用OVERPASS_QUERY_MAP构建查询语句，按要素类型分组返回结果。
"""
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import shutil
import subprocess
import tempfile
import sys

# Windows下不弹出cmd窗口
CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0

import re

import requests
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import CITY_BBOX, OVERPASS_QUERY_MAP


class OSMService:
    """OSM数据获取服务

    通过Overpass API获取OpenStreetMap地理要素（道路、铁路、水系、POI等）。
    支持多服务器轮询、自动重试、按区域和要素类型查询。
    """

    # 缓存最大条目数
    _CACHE_MAX_SIZE: int = 20
    # 缓存TTL（秒）
    _CACHE_TTL: float = 1800.0
    # 磁盘缓存（跨重启持久，制图提速）
    _DISK_CACHE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "runtime", "osm_cache.json",
    )
    _DISK_CACHE_TTL: float = 86400.0   # 24小时

    def __init__(self):
        """从配置获取Overpass服务器列表"""
        self.servers: List[str] = settings.overpass_server_list
        # 内存缓存：使用 OrderedDict 实现 LRU，{ (region, types): (timestamp, data) }
        self._cache: OrderedDict[tuple, tuple] = OrderedDict()
        # 复用 HTTP 连接池，减少反复建连的开销
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CartoAgent/1.0 (Map Cartography Agent)",
            "Accept": "application/json",
        })
        # 绕过本机失效代理（HTTP(S)_PROXY=127.0.0.1:9），requests 兜底时也直连
        self._session.trust_env = False
        self._probe_cache = {"ts": 0.0, "ok": True}
        self._disk_cache: Dict[tuple, dict] = {}
        try:
            if os.path.exists(self._DISK_CACHE_PATH):
                with open(self._DISK_CACHE_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    parts = k.split("||")
                    if len(parts) == 2:
                        self._disk_cache[(parts[0], tuple(sorted(parts[1].split(","))))] = v
                print(f"[OSMService] 磁盘缓存加载: {len(self._disk_cache)} 条")
        except Exception as e:
            print(f"[OSMService] 磁盘缓存加载失败: {e}")
        print(f"[OSMService] 初始化完成，可用服务器: {len(self.servers)}个")

    def _save_disk_cache(self):
        """将内存缓存落盘（跨重启复用，避免每次制图重复抓取 OSM）"""
        try:
            os.makedirs(os.path.dirname(self._DISK_CACHE_PATH), exist_ok=True)
            raw = {}
            for (region, types), data in self._disk_cache.items():
                raw[region + "||" + ",".join(sorted(types))] = data
            with open(self._DISK_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)
        except Exception as e:
            print(f"[OSMService] 磁盘缓存保存失败: {e}")

    def _probe_ok(self, ttl: float = 60.0) -> bool:
        """快速探测 Overpass 是否可达（任一服务器返回 HTTP 状态即视为可用）。

        全部镜像不可达（断网/被屏蔽）时直接跳过 OSM 抓取，
        避免每次制图都在不可达镜像上空等数分钟（本地数据可兜底）。
        """
        now = time.time()
        if now - self._probe_cache["ts"] < ttl:
            return self._probe_cache["ok"]
        ok = False
        for server in self.servers[:4]:
            try:
                r = subprocess.run(
                    ["curl.exe", "-s", "-o", os.devnull, "-w", "%{http_code}",
                     "--connect-timeout", "4", "--max-time", "6", server],
                    capture_output=True, text=True, timeout=10,
                    creationflags=CREATE_NO_WINDOW,
                )
                code = (r.stdout or "").strip()
                if code and code != "000":
                    ok = True
                    break
            except Exception:
                continue
        self._probe_cache = {"ts": now, "ok": ok}
        print(f"[OSMService] 连通性探测: {'可达' if ok else '全部镜像不可达，跳过OSM抓取'}")
        return ok

    def fetch_elements(
        self,
        bbox: Dict[str, float],
        element_types: List[str],
        max_retries: int = 1,
    ) -> Dict[str, List[dict]]:
        """从Overpass API获取OSM要素，支持多服务器轮询重试

        按要素类型分块并行请求：单个类型失败不影响其它类型，
        避免巨型组合请求被Overpass限流/超时而整体失败。

        Args:
            bbox: 边界框，格式 {min_lat, min_lon, max_lat, max_lon}
            element_types: 要素类型列表，如 ["highway", "railway"]
            max_retries: 最大重试次数（每轮遍历所有服务器）

        Returns:
            按类型分组的元素字典，key为要素类型，value为元素列表。
        """
        servers = self.servers if self.servers else [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://z.overpass-api.de/api/interpreter",
            "https://lz4.overpass-api.de/api/interpreter",
        ]

        # 为每个类型构建独立查询
        tasks = []
        for typ in element_types:
            query_part = OVERPASS_QUERY_MAP.get(typ)
            if not query_part:
                print(f"[OSMService] 未知要素类型: {typ}，已跳过")
                continue
            sub_queries = []
            for sub_query in query_part.split(";"):
                sub_query = sub_query.strip()
                if sub_query:
                    sub_queries.append(
                        f"{sub_query}"
                        f"({bbox['min_lat']},{bbox['min_lon']},"
                        f"{bbox['max_lat']},{bbox['max_lon']});"
                        f"out geom;"
                    )
            tasks.append((typ, "[out:json];" + "".join(sub_queries)))

        if not tasks:
            print("[OSMService] 没有有效的查询语句")
            return {}

        # 总抓取时限（秒）：超时后停止等待，用已获取部分 + 本地数据兜底
        self._fetch_deadline = time.time() + 180
        # 并行请求各类型（并发2-3，避免触发Overpass并发限流）
        results: Dict[str, List[dict]] = {}
        with ThreadPoolExecutor(max_workers=min(2, len(tasks))) as executor:
            # 每类型优先尝试前2台服务器，避免限流时逐台超时拖慢整体
            active_servers = servers[:2] if len(servers) > 2 else servers
            futures = {
                executor.submit(self._fetch_type, typ, query, active_servers, max_retries): typ
                for typ, query in tasks
            }
            for future in as_completed(futures):
                typ = futures[future]
                try:
                    elems = future.result()
                    if elems:
                        results[typ] = elems
                except Exception as e:
                    print(f"[OSMService] 类型[{typ}]获取失败: {e}")

        # 按标签分组汇总
        elements_by_type: Dict[str, List[dict]] = {}
        for typ, elems in results.items():
            base_tag = typ.split("~")[0]
            if base_tag in ("highway_major", "highway_minor"):
                tag_key = "highway"
            elif base_tag in ("waterway_major", "waterway_minor"):
                tag_key = "waterway"
            elif base_tag in ("place_city", "place_suburb"):
                tag_key = "place"
            else:
                tag_key = base_tag
            for elem in elems:
                tags = elem.get("tags", {})
                if not tags:
                    continue
                if tag_key in tags:
                    elements_by_type.setdefault(base_tag, []).append(elem)

        # 地理数据预处理：坐标校验、要素去重、名称清洗
        elements_by_type = self._preprocess(elements_by_type)
        total = sum(len(v) for v in elements_by_type.values())
        print(f"[OSMService] 汇总完成: {total}个要素，{len(elements_by_type)}类")
        return elements_by_type

    @staticmethod
    def _valid_coord(lat, lon) -> bool:
        """坐标有效性校验"""
        if lat is None or lon is None:
            return False
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return False
        return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0

    def _preprocess(self, elements_by_type: Dict[str, List[dict]], bbox: dict = None) -> Dict[str, List[dict]]:
        """地理数据预处理：过滤非法坐标/极小几何、清洗名称、去除重复要素

        bbox: 城市边界框（存在时二次裁剪越界点）
        """
        cleaned: Dict[str, List[dict]] = {}
        for base_tag, elems in elements_by_type.items():
            seen = set()
            out = []
            for elem in elems:
                tags = elem.get("tags", {}) or {}
                # node坐标校验
                if elem.get("type") == "node":
                    if not self._valid_coord(elem.get("lat"), elem.get("lon")):
                        continue
                # way/relation 几何校验：过滤非法坐标点，丢弃过短几何
                geom = elem.get("geometry") or []
                if geom:
                    valid = [p for p in geom
                             if isinstance(p, dict) and self._valid_coord(p.get("lat"), p.get("lon"))]
                    if len(valid) < 2:
                        continue
                    elem = dict(elem)
                    elem["geometry"] = valid
                    geom = valid
                # 名称清洗：去空白、截断、剔除占位名
                name = (tags.get("name") or "").strip()
                if name:
                    name = re.sub(r"\s+", " ", name)
                    if len(name) > 60:
                        name = name[:60]
                    if name.lower() in ("unnamed", "未命名", "unknown", "none"):
                        name = ""
                    tags = dict(tags)
                    tags["name"] = name
                    elem = dict(elem)
                    elem["tags"] = tags
                # 无名POI节点（清洗后仍无名）丢弃，避免地图上出现无意义标记
                if elem.get("type") == "node" and not name:
                    continue
                # 去重：类型 + 首尾坐标 + 名称
                if geom:
                    key = (base_tag, str(geom[0]), str(geom[-1]), name)
                else:
                    key = (base_tag, str(elem.get("lat")), str(elem.get("lon")), name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(elem)
            if out:
                cleaned[base_tag] = out
        return cleaned

    def _fetch_type(
        self,
        typ: str,
        query: str,
        servers: List[str],
        max_retries: int,
    ) -> List[dict]:
        """获取单个类型的OSM要素，多服务器轮询重试"""
        for attempt in range(max_retries):
            for server in servers:
                # 总抓取时限：超过后放弃该类型（本地数据兜底，避免长时间空等）
                if getattr(self, "_fetch_deadline", 0) and time.time() > self._fetch_deadline:
                    print(f"[OSMService] 类型[{typ}] 超过抓取时限，放弃")
                    return []
                try:
                    print(f"[OSMService] 尝试从 {server} 获取[{typ}] (轮次 {attempt + 1}/{max_retries})")
                    data = self._post_overpass(server, query, timeout=240)
                    elems = data.get("elements", [])
                    print(f"[OSMService] 类型[{typ}] 成功获取 {len(elems)} 个要素")
                    return elems
                except Exception as e:
                    print(f"[OSMService] 类型[{typ}] 请求失败 ({server}): {e}")
                finally:
                    time.sleep(0.5)
            if attempt < max_retries - 1:
                print(f"[OSMService] 类型[{typ}] 所有服务器失败，等待后重试...")
                time.sleep(1)
        return []

    def _post_overpass(self, server: str, query: str, timeout: int = 60) -> dict:
        """向 Overpass 发送 POST 查询，优先用 curl.exe 直连（绕过坏代理）。

        curl 不可用时回退 requests（已 trust_env=False 直连）。
        """
        curl_path = shutil.which("curl.exe") or (r"C:\Windows\System32\curl.exe"
                                                 if os.path.exists(r"C:\Windows\System32\curl.exe") else None)
        if curl_path:
            fd, qpath = tempfile.mkstemp(suffix=".ql", prefix="overpass_")
            os.close(fd)
            outpath = qpath + ".json"
            try:
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(query)
                r = subprocess.run(
                    [curl_path, "-s", "--max-time", str(timeout),
                     "--connect-timeout", "10",
                     "--data-binary", "@" + qpath, "-o", outpath, server],
                    capture_output=True, timeout=timeout + 20,
                    creationflags=CREATE_NO_WINDOW,
                )
                if r.returncode == 0 and os.path.exists(outpath) and os.path.getsize(outpath) > 0:
                    with open(outpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "error" not in data:
                        return data
                    raise RuntimeError(f"Overpass 返回错误: {data.get('remark', data)}")
                raise RuntimeError(f"curl 退出码 {r.returncode}")
            finally:
                for p in (qpath, outpath):
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
        # 兜底：requests 直连
        resp = self._session.post(server, data={"data": query}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_by_region(
        self,
        region: str,
        element_types: List[str],
    ) -> Dict[str, List[dict]]:
        """按区域名称获取OSM要素

        从CITY_BBOX获取区域的边界框后调用fetch_elements，
        并进行越界裁剪与数据预处理。

        Args:
            region: 区域名称（如"武汉市"、"北京市"）
            element_types: 要素类型列表

        Returns:
            按类型分组的元素字典
        """
        # 快速连通性探测：全部镜像不可达时直接跳过，避免数分钟空等
        if not self._probe_ok():
            return {}
        bbox = CITY_BBOX.get(region)
        if not bbox:
            print(
                f"[OSMService] 未知区域: {region}，"
                f"支持的城市: {list(CITY_BBOX.keys())}"
            )
            return {}

        # 对bbox做道路缓冲区扩展（避免边界裁剪导致道路截断）
        _buffer = 0.03  # 约3km缓冲区
        bbox_buffered = {
            "min_lat": bbox["min_lat"] - _buffer,
            "min_lon": bbox["min_lon"] - _buffer,
            "max_lat": bbox["max_lat"] + _buffer,
            "max_lon": bbox["max_lon"] + _buffer,
            "center_lat": bbox["center_lat"],
            "center_lon": bbox["center_lon"],
        }

        # 内存缓存：同一区域+同一要素组合30分钟内直接命中，避免重复请求Overpass
        cache_key = (region, tuple(sorted(set(element_types))))
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self._CACHE_TTL:
            # LRU：命中时移到末尾（最近使用）
            self._cache.move_to_end(cache_key)
            print(f"[OSMService] 命中缓存: {region} {len(cached[1])}类要素")
            return cached[1]
        # 磁盘缓存（跨重启）：24小时内同区域同类型直接复用
        disk = self._disk_cache.get(cache_key)
        if disk and now - disk.get("ts", 0) < self._DISK_CACHE_TTL and disk.get("data"):
            self._cache[cache_key] = (now, disk["data"])
            print(f"[OSMService] 命中磁盘缓存: {region} {len(disk['data'])}类要素")
            return disk["data"]

        result = self.fetch_elements(bbox_buffered, element_types, max_retries=2)

        # 越界裁剪 + 数据预处理：修剪异常顶点、清洗名称、去重
        if result:
            result = self._crop_to_bbox(result, bbox)
            result = self._preprocess(result, bbox)

        # 仅缓存非空结果，防止临时故障被缓存；
        # 若新结果类型数少于旧缓存（部分类型限流失败），保留更完整的旧缓存
        if result:
            old = self._cache.get(cache_key)
            if not (old and len(result) < len(old[1])):
                self._cache[cache_key] = (now, result)
                self._cache.move_to_end(cache_key)
                self._disk_cache[cache_key] = {"ts": now, "data": result}
                self._save_disk_cache()
            # LRU 淘汰：超过容量时移除最旧条目（OrderedDict 首项）
            while len(self._cache) > self._CACHE_MAX_SIZE:
                self._cache.popitem(last=False)
        return result

    def _crop_to_bbox(self, elements_by_type: Dict[str, List[dict]], bbox: dict) -> Dict[str, List[dict]]:
        """按城市边界框裁剪要素：剔除超出范围的顶点，保留有效要素

        防止越界点造成边界毛刺、碎线段与面积虚高。
        """
        buf = 0.02  # 缓冲，避免误删边界要素
        min_lat, min_lon = bbox["min_lat"] - buf, bbox["min_lon"] - buf
        max_lat, max_lon = bbox["max_lat"] + buf, bbox["max_lon"] + buf
        cropped: Dict[str, List[dict]] = {}
        for base_tag, elems in elements_by_type.items():
            out = []
            for elem in elems:
                if elem.get("type") == "node":
                    lat, lon = elem.get("lat"), elem.get("lon")
                    if lat is None or lon is None:
                        continue
                    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                        out.append(elem)
                    continue
                geom = elem.get("geometry") or []
                if not geom:
                    continue
                valid = [pt for pt in geom
                         if isinstance(pt, dict) and min_lat <= pt.get("lat", 999) <= max_lat
                         and min_lon <= pt.get("lon", 999) <= max_lon]
                if len(valid) >= 2:
                    elem = dict(elem)
                    elem["geometry"] = valid
                    out.append(elem)
            if out:
                cropped[base_tag] = out
        return cropped

    def get_region_center(self, region: str) -> Optional[List[float]]:
        """获取区域中心坐标

        Args:
            region: 区域名称

        Returns:
            [lat, lng] 中心坐标，未知区域返回None
        """
        bbox = CITY_BBOX.get(region)
        if not bbox:
            return None
        return [bbox["center_lat"], bbox["center_lon"]]
