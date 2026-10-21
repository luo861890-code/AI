"""RAG检索增强服务 - 基于关键词匹配的知识库检索

从本地知识库文件加载制图领域知识，提供关键词匹配检索。
用于在智能体制图过程中增强上下文信息，提供制图规范、配色方案等参考。
"""
import os
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.utils.helpers import ensure_dir


class RAGService:
    """RAG检索增强服务

    加载本地制图知识库（JSON格式），基于关键词匹配进行检索。
    知识库文件不存在时使用内置默认知识库。
    """

    # 内置默认知识库（当外部知识库文件不存在时使用）
    _DEFAULT_KB = [
        {
            "title": "交通图制图规范",
            "content": "交通图应包含主要道路网络（高速公路、主干道、次干道）和铁路线路。"
                       "道路按等级使用不同颜色和线宽：高速公路用红色粗线，主干道用橙色，"
                       "次干道用黄色。铁路使用灰色虚线表示。",
            "keywords": ["交通", "道路", "铁路", "highway", "traffic", "交通图"],
        },
        {
            "title": "旅游图制图规范",
            "content": "旅游图应标注主要景点、博物馆、历史遗迹和观景台。"
                       "使用醒目的图标标记各类景点，景点名称使用清晰字体标注。"
                       "旅游路线用彩色线条连接相关景点。",
            "keywords": ["旅游", "景点", "tourism", "旅游图", "景点图"],
        },
        {
            "title": "校园图制图规范",
            "content": "校园图应包含教学楼、图书馆、宿舍楼、食堂、运动场等设施。"
                       "建筑物使用浅色填充，绿地使用绿色，道路使用灰色细线。"
                       "重要建筑添加名称标注。",
            "keywords": ["校园", "学校", "campus", "校园图", "校园导览"],
        },
        {
            "title": "地图配色原则",
            "content": "地图配色应遵循视觉层次原则：重要要素使用高饱和度颜色，"
                       "次要要素使用低饱和度颜色。道路用暖色系（红/橙/黄），"
                       "水系用蓝色系，绿地用绿色系，建筑用中性灰色系。"
                       "整体配色不宜超过5种主色。",
            "keywords": ["配色", "颜色", "样式", "色彩", "color", "style"],
        },
        {
            "title": "地图比例尺与缩放",
            "content": "城市级地图推荐缩放级别11-13，街区级推荐14-16。"
                       "比例尺越大（缩放级别越高），显示的细节越多。"
                       "不同地图类型适用不同缩放范围：交通图适合11-13，"
                       "旅游图适合13-15，校园图适合15-17。",
            "keywords": ["比例尺", "缩放", "zoom", "级别", "scale"],
        },
        {
            "title": "OSM数据获取最佳实践",
            "content": "使用Overpass API获取OSM数据时，建议设置合理的bbox范围，"
                       "避免一次性查询过大区域导致超时。多服务器轮询可提高成功率。"
                       "查询结果按要素类型分组，way类型提取geometry坐标序列，"
                       "node类型提取lat/lon坐标点。",
            "keywords": ["OSM", "overpass", "数据", "获取", "data"],
        },
        {
            "title": "地图图层管理",
            "content": "地图图层按要素类型组织，每种类型一个图层。"
                       "支持动态添加/删除图层和图层内要素。"
                       "图层样式包括颜色(color)、线宽(weight)、透明度(opacity)、"
                       "填充透明度(fillOpacity)、虚线样式(dashArray)。",
            "keywords": ["图层", "layer", "管理", "样式", "要素"],
        },
        {
            "title": "武汉地理概况",
            "content": "武汉市位于东经113.95-114.65，北纬30.35-30.75。"
                       "主要地标包括武汉大学、黄鹤楼、东湖、湖北省博物馆等。"
                       "长江和汉江在市区交汇，将城市分为武昌、汉口、汉阳三镇。",
            "keywords": ["武汉", "地标", "武汉地理", "三镇", "长江"],
        },
    ]

    def __init__(self):
        """初始化RAG服务，加载知识库"""
        self.knowledge_base: List[Dict[str, Any]] = []
        # 预计算的文档 bigrams 缓存，避免每次检索重复计算
        self._doc_bigrams: List[set] = []
        self._load_knowledge_base()
        self._precompute_bigrams()
        print(f"[RAGService] 初始化完成，知识库共{len(self.knowledge_base)}条")

    def _precompute_bigrams(self):
        """预计算所有知识条目的 2-gram 集合，缓存到 _doc_bigrams"""
        self._doc_bigrams = []
        for entry in self.knowledge_base:
            title = entry.get("title", "")
            content = entry.get("content", "")
            doc_text = (title + content).lower().replace(" ", "")
            if len(doc_text) < 2:
                bigrams = {doc_text} if doc_text else set()
            else:
                bigrams = {doc_text[i:i+2] for i in range(len(doc_text) - 1)}
            self._doc_bigrams.append(bigrams)

    def _load_knowledge_base(self):
        """加载知识库文件

        优先从data/kg/cartography_kb.json加载，文件不存在时使用内置默认知识库。
        """
        kb_path = os.path.join(settings.data_dir, "kg", "cartography_kb.json")

        try:
            if os.path.exists(kb_path):
                from app.utils.helpers import safe_json_loads
                import json

                with open(kb_path, "r", encoding="utf-8") as f:
                    content = f.read()
                data = safe_json_loads(content, [])
                if isinstance(data, list) and len(data) > 0:
                    self.knowledge_base = data
                    print(f"[RAGService] 从 {kb_path} 加载知识库成功")
                    return
                else:
                    print(f"[RAGService] 知识库文件格式无效，使用默认知识库")
            else:
                print(f"[RAGService] 知识库文件不存在: {kb_path}，使用默认知识库")
        except Exception as e:
            print(f"[RAGService] 加载知识库失败: {e}，使用默认知识库")

        # 使用内置默认知识库
        self.knowledge_base = list(self._DEFAULT_KB)

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """基于关键词匹配检索相关知识条目

        Args:
            query: 查询文本
            top_k: 返回的最大条目数

        Returns:
            匹配的知识条目列表，按相关度排序，每项包含 title, content, score
        """
        if not self.knowledge_base:
            return []

        # 查询 bigrams 只需计算一次
        query_lower = query.lower().replace(" ", "")
        if len(query_lower) < 2:
            query_bigrams = {query_lower} if query_lower else set()
        else:
            query_bigrams = {query_lower[i:i+2] for i in range(len(query_lower) - 1)}

        results = []
        for idx, entry in enumerate(self.knowledge_base):
            score = self._calculate_score(query, query_lower, query_bigrams, entry, idx)
            if score > 0:
                results.append({
                    "title": entry.get("title", ""),
                    "content": entry.get("content", ""),
                    "score": score,
                })

        # 按相关度排序，取前top_k条
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _calculate_score(
        self,
        query: str,
        query_lower: str,
        query_bigrams: set,
        entry: Dict[str, Any],
        entry_idx: int,
    ) -> float:
        """计算查询与知识条目的匹配分数 - 2-gram Jaccard相似度 + 关键词加权

        融合两种检索策略：
        1. 关键词精确匹配（权重0.5）：覆盖率越高分数越高
        2. 2-gram Jaccard相似度（权重0.5）：文本层面的语义相似度

        Args:
            query: 原始查询文本
            query_lower: 小写查询文本
            query_bigrams: 查询的 2-gram 集合（预计算）
            entry: 知识条目
            entry_idx: 知识条目索引（用于取预计算的 bigrams）

        Returns:
            匹配分数（0表示不匹配），范围[0, 1]
        """
        score = 0.0

        # ===== 1. 关键词精确匹配（高权重） =====
        keywords = entry.get("keywords", [])
        matched_keywords = 0
        for kw in keywords:
            if kw.lower() in query_lower:
                matched_keywords += 1
        if keywords:
            # 关键词覆盖率 * 0.5权重
            score += (matched_keywords / len(keywords)) * 0.5

        # ===== 2. 2-gram Jaccard相似度（使用预计算的文档 bigrams） =====
        doc_bigrams = self._doc_bigrams[entry_idx] if entry_idx < len(self._doc_bigrams) else set()

        if query_bigrams and doc_bigrams:
            intersection = query_bigrams & doc_bigrams
            union = query_bigrams | doc_bigrams
            jaccard_score = len(intersection) / len(union) if union else 0
            score += jaccard_score * 0.5  # Jaccard相似度 * 0.5权重

        return score

    def close(self):
        """清理资源"""
        self.knowledge_base = []
        print("[RAGService] 资源已清理")
