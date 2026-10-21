# -*- coding: utf-8 -*-
"""百科知识服务 - 为重点建筑/地标提供简介与图片（点击后显示）

优先查询在线维基百科，网络不可用时回退到内置知识库，
保证百科附着功能始终可用。
"""
import requests
from typing import Dict, Optional

from app.core.constants import POI_ENCYCLOPEDIA


class WikiService:
    """百科知识查询服务"""

    def __init__(self):
        self._cache: Dict[str, dict] = {}

    def lookup(self, name: str) -> dict:
        name = (name or "").strip()
        if not name:
            return {"name": "", "found": False, "extract": "", "image": "", "source": ""}
        if name in self._cache:
            return self._cache[name]
        result = self._fetch_wikipedia(name) or self._builtin(name)
        self._cache[name] = result
        return result

    def _fetch_wikipedia(self, name: str) -> Optional[dict]:
        """尝试从中文维基百科获取词条摘要与图片"""
        try:
            resp = requests.get(
                "https://zh.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(name),
                timeout=6,
                headers={"User-Agent": "CartoAgent/1.0 (Map Cartography Agent)"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            title = data.get("title") or name
            extract = (data.get("extract") or "").strip()[:300]
            if not extract:
                return None
            return {
                "name": title, "found": True,
                "extract": extract,
                "image": (data.get("thumbnail") or {}).get("source", ""),
                "source": "维基百科",
            }
        except Exception:
            return None

    def _builtin(self, name: str) -> dict:
        """回退到内置知识库（含模糊匹配）"""
        if name in POI_ENCYCLOPEDIA:
            entry = POI_ENCYCLOPEDIA[name]
            return {"name": name, "found": True, "extract": entry.get("简介", ""),
                    "image": entry.get("图片", ""), "source": "内置知识库"}
        for key, entry in POI_ENCYCLOPEDIA.items():
            if key in name or name in key:
                return {"name": key, "found": True, "extract": entry.get("简介", ""),
                        "image": entry.get("图片", ""), "source": "内置知识库"}
        return {"name": name, "found": False, "extract": "", "image": "", "source": ""}