"""GraphRAG服务 - 图检索增强生成管道

基于LLM-KG-Carto框架，实现4步GraphRAG管道：
1. 实体识别（Entity Recognition）：从用户查询中提取制图相关实体
2. 子图检索（Subgraph Retrieval）：从知识图谱获取多跳关联子图
3. 知识聚合（Knowledge Aggregation）：将子图信息结构化为推理上下文
4. 推理生成（Reasoning Generation）：结合LLM生成增强回答

GraphRAG区别于传统RAG：不仅检索单一文本块，而是通过图谱的多跳关系
获取结构化的关联知识，支持复杂推理任务如制图规则推导、样式冲突检测等。
"""
from typing import List, Dict, Any, Optional
import re


class GraphRAGService:
    """GraphRAG图检索增强生成服务
    
    依赖KGService进行图谱查询，依赖LLMService进行实体识别和推理生成。
    """
    
    def __init__(self, kg_service=None, llm_service=None):
        """初始化GraphRAG服务
        
        Args:
            kg_service: 知识图谱服务实例，提供子图检索能力
            llm_service: LLM服务实例，提供实体识别和推理生成能力
        """
        self.kg_service = kg_service
        self.llm_service = llm_service
        print("[GraphRAGService] 初始化完成")
    
    def search(self, query: str, depth: int = 2, top_k: int = 3) -> Dict[str, Any]:
        """GraphRAG搜索 - 完整4步管道
        
        Args:
            query: 用户自然语言查询
            depth: 图谱检索深度（跳数），默认2跳
            top_k: 最多返回的知识条目数
            
        Returns:
            {
                "entities": [识别到的实体列表],
                "subgraphs": [检索到的子图列表],
                "aggregated_knowledge": [聚合后的结构化知识],
                "reasoning_context": 供LLM推理的上下文文本
            }
        """
        # 步骤1：实体识别
        entities = self._extract_entities(query)
        print(f"[GraphRAGService] 实体识别: {entities}")
        
        if not entities:
            return {
                "entities": [],
                "subgraphs": [],
                "aggregated_knowledge": [],
                "reasoning_context": ""
            }
        
        # 步骤2：子图检索
        subgraphs = []
        for entity in entities[:top_k]:
            if self.kg_service:
                try:
                    subgraph = self.kg_service.get_subgraph(entity, depth=depth, limit=30)
                    if subgraph.get("nodes"):
                        subgraphs.append(subgraph)
                except Exception as e:
                    print(f"[GraphRAGService] 子图检索失败({entity}): {e}")
        
        print(f"[GraphRAGService] 检索到{len(subgraphs)}个子图")
        
        # 步骤3：知识聚合
        aggregated = self._aggregate_knowledge(subgraphs)
        
        # 步骤4：构建推理上下文
        reasoning_context = self._build_reasoning_context(entities, subgraphs, aggregated)
        
        return {
            "entities": entities,
            "subgraphs": subgraphs,
            "aggregated_knowledge": aggregated,
            "reasoning_context": reasoning_context
        }
    
    def _extract_entities(self, query: str) -> List[str]:
        """从查询中提取制图相关实体
        
        优先使用LLM进行实体识别，降级为关键词匹配。
        
        Args:
            query: 用户查询文本
            
        Returns:
            识别到的实体名称列表
        """
        # 先用关键词匹配快速提取
        keyword_entities = self._extract_entities_by_keywords(query)
        
        # LLM增强识别（如果可用且关键词提取不足）
        if self.llm_service and len(keyword_entities) < 2:
            llm_entities = self._extract_entities_with_llm(query)
            # 合并去重
            for ent in llm_entities:
                if ent not in keyword_entities:
                    keyword_entities.append(ent)
        
        return keyword_entities
    
    def _extract_entities_by_keywords(self, query: str) -> List[str]:
        """基于关键词的实体识别
        
        匹配制图领域常见实体名称和概念。
        
        Args:
            query: 用户查询文本
            
        Returns:
            匹配到的实体名称列表
        """
        entities = []
        
        # 地图类型实体
        map_types = {
            "交通图": "traffic", "交通": "traffic",
            "旅游图": "tourism", "旅游": "tourism",
            "校园图": "campus", "校园": "campus",
            "美食图": "food", "美食": "food",
            "基础地图": "basic",
        }
        for keyword, entity in map_types.items():
            if keyword in query:
                entities.append(entity)
        
        # 地图要素实体
        elements = {
            "道路": "road_element", "公路": "road_element", "高速": "road_element",
            "铁路": "railway_element", "地铁": "railway_element",
            "水系": "waterway_element", "河流": "waterway_element", "湖泊": "waterway_element",
            "建筑": "building_element", "楼房": "building_element",
            "景点": "poi_element", "兴趣点": "poi_element", "POI": "poi_element",
            "绿地": "green_space_element", "公园": "green_space_element",
            "边界": "boundary_element", "行政": "boundary_element",
        }
        for keyword, entity in elements.items():
            if keyword in query and entity not in entities:
                entities.append(entity)
        
        # 制图概念实体
        concepts = {
            "符号": "poi_symbol", "颜色": "color_constraint",
            "配色": "color_constraint", "比例尺": "scale_factor",
            "缩放": "scale_factor", "投影": "wgs84",
            "坐标系": "wgs84", "数据源": "osm_data",
            "OSM": "osm_data", "注记": "annotation_rule",
            "标签": "annotation_rule",
        }
        for keyword, entity in concepts.items():
            if keyword in query and entity not in entities:
                entities.append(entity)
        
        # 城市实体
        cities = ["武汉", "北京", "上海", "广州", "深圳", "成都", "杭州", "南京"]
        for city in cities:
            if city in query:
                entities.append(city)
        
        return entities
    
    def _extract_entities_with_llm(self, query: str) -> List[str]:
        """使用LLM进行实体识别
        
        Args:
            query: 用户查询文本
            
        Returns:
            LLM识别到的实体名称列表
        """
        if not self.llm_service:
            return []
        
        system_prompt = (
            "你是一个制图领域的实体识别器。从用户输入中提取与地图制图相关的实体。\n"
            "可能出现的实体类型包括：\n"
            "- 地图类型: traffic, tourism, campus, food, basic\n"
            "- 地图要素: road_element, railway_element, waterway_element, "
            "building_element, poi_element, green_space_element, boundary_element\n"
            "- 地图符号: highway_symbol, railway_symbol, waterway_symbol, "
            "building_symbol, poi_symbol, green_space_symbol, boundary_symbol\n"
            "- 制图数据: osm_data, local_landmark_data, osm_tile_data, satellite_data\n"
            "- 地图投影: wgs84, web_mercator, gcj02, cgcs2000\n"
            "- 影响因素: scale_factor, purpose_factor, color_constraint, "
            "audience_factor, density_constraint, accessibility_factor\n"
            "- 制图规则: scale_selection, color_scheme, symbol_design, annotation_rule\n"
            "- 城市: 武汉, 北京, 上海, 广州, 深圳, 成都, 杭州, 南京\n\n"
            "以JSON数组格式返回识别到的实体名称，如: [\"traffic\", \"road_element\"]\n"
            "只返回JSON数组，不要其他内容。"
        )
        
        try:
            result = self.llm_service.generate(query, system_prompt)
            if result:
                result = result.strip()
                if result.startswith("```"):
                    result = result.split("\n", 1)[1] if "\n" in result else result[3:]
                if result.endswith("```"):
                    result = result[:-3]
                result = result.strip()
                
                from app.utils.helpers import safe_json_loads
                entities = safe_json_loads(result, [])
                if isinstance(entities, list):
                    return [str(e) for e in entities]
        except Exception as e:
            print(f"[GraphRAGService] LLM实体识别失败: {e}")
        
        return []
    
    def _aggregate_knowledge(self, subgraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """知识聚合 - 将多个子图的结构化信息合并为统一的知识条目
        
        Args:
            subgraphs: 子图列表，每个子图包含nodes和links
            
        Returns:
            聚合后的知识条目列表，每条包含：
            - entity: 中心实体
            - related_entities: 关联实体
            - relations: 关系描述列表
            - properties: 实体属性
        """
        aggregated = []
        
        for subgraph in subgraphs:
            center = subgraph.get("center", "")
            nodes = subgraph.get("nodes", [])
            links = subgraph.get("links", [])
            
            # 收集关联实体
            related = []
            for node in nodes:
                name = node.get("name", "")
                label = node.get("label", "")
                if name and name != center:
                    related.append({"name": name, "label": label})
            
            # 收集关系描述
            relations = []
            for link in links:
                source = link.get("source", "")
                target = link.get("target", "")
                rel_type = link.get("type", "")
                relations.append(f"{source} --[{rel_type}]--> {target}")
            
            # 获取中心节点的属性
            center_props = {}
            for node in nodes:
                if node.get("name") == center:
                    center_props = node.get("properties", {})
                    break
            
            aggregated.append({
                "entity": center,
                "related_entities": related[:10],  # 限制数量
                "relations": relations[:15],
                "properties": center_props,
            })
        
        return aggregated
    
    def _build_reasoning_context(
        self,
        entities: List[str],
        subgraphs: List[Dict[str, Any]],
        aggregated: List[Dict[str, Any]],
    ) -> str:
        """构建供LLM推理的上下文文本
        
        将GraphRAG检索到的结构化知识转化为自然语言上下文，
        供LLM在生成制图方案时参考。
        
        Args:
            entities: 识别到的实体列表
            subgraphs: 检索到的子图列表
            aggregated: 聚合后的知识条目
            
        Returns:
            推理上下文文本
        """
        if not aggregated:
            return ""
        
        parts = ["=== GraphRAG知识上下文 ==="]
        parts.append(f"识别实体: {', '.join(entities)}")
        parts.append("")
        
        for entry in aggregated:
            entity = entry["entity"]
            related = entry.get("related_entities", [])
            relations = entry.get("relations", [])
            props = entry.get("properties", {})
            
            parts.append(f"【{entity}】")
            
            if props:
                # 只展示关键属性
                key_props = {k: v for k, v in props.items() 
                           if k in ("description", "color", "size", "style", "opacity",
                                   "element_type", "osm_tag", "symbol_type", "factor_type",
                                   "value_range", "crs_code", "data_source", "priority")}
                if key_props:
                    for k, v in key_props.items():
                        parts.append(f"  - {k}: {v}")
            
            if related:
                related_str = ", ".join([f"{r['name']}({r['label']})" for r in related[:5]])
                parts.append(f"  关联实体: {related_str}")
            
            if relations:
                parts.append(f"  关系链:")
                for rel in relations[:5]:
                    parts.append(f"    {rel}")
            
            parts.append("")
        
        return "\n".join(parts)
    
    # ==================== 增强方法1：多跳推理深度控制 ====================
    
    def search_with_depth(self, query: str, max_depth: int = 4,
                          branching_factor: int = 5) -> Dict[str, Any]:
        """支持更深层的多跳推理（max_depth=4对应4跳推理链）
        
        在标准GraphRAG管道基础上增加深度控制，逐跳构建推理链，
        累积各跳的知识并在必要时标记缺失的推理环节。
        
        Args:
            query: 用户自然语言查询
            max_depth: 最大推理深度（跳数），默认4跳
            branching_factor: 每跳最多扩展的实体数
            
        Returns:
            {
                "reasoning_chain": [...],     # 推理链条 [{hop, entities, relations, confidence}]
                "accumulated_knowledge": [...], # 累积知识
                "missing_links": [...],        # 缺失的关系（KG中不存在的推理步骤）
                "entities": [...],
                "subgraphs": [...],
                "aggregated_knowledge": [...],
                "reasoning_context": str,
            }
        """
        # 步骤1：实体识别
        entities = self._extract_entities(query)
        print(f"[GraphRAGService] search_with_depth 实体识别: {entities}")
        
        if not entities:
            return {
                "reasoning_chain": [],
                "accumulated_knowledge": [],
                "missing_links": [],
                "entities": [],
                "subgraphs": [],
                "aggregated_knowledge": [],
                "reasoning_context": "",
            }
        
        reasoning_chain: List[Dict[str, Any]] = []
        accumulated_knowledge: List[Dict[str, Any]] = []
        missing_links: List[Dict[str, Any]] = []
        all_subgraphs: List[Dict[str, Any]] = []
        visited_entities: set = set(entities[:branching_factor])
        frontier = list(entities[:branching_factor])
        
        # 逐跳检索
        for hop in range(1, max_depth + 1):
            hop_entities = []
            hop_relations = []
            hop_subgraphs = []
            next_frontier = []
            
            for entity in frontier:
                if self.kg_service:
                    try:
                        subgraph = self.kg_service.get_subgraph(
                            entity, depth=1, limit=30
                        )
                        if subgraph.get("nodes"):
                            hop_subgraphs.append(subgraph)
                            all_subgraphs.append(subgraph)
                            
                            # 提取此跳的新实体
                            for node in subgraph.get("nodes", []):
                                node_name = node.get("name", "")
                                if node_name and node_name != entity and node_name not in visited_entities:
                                    hop_entities.append(node_name)
                                    visited_entities.add(node_name)
                            
                            # 提取关系
                            for link in subgraph.get("links", []):
                                rel_type = link.get("type", "")
                                source = link.get("source", "")
                                target = link.get("target", "")
                                hop_relations.append({
                                    "source": source,
                                    "target": target,
                                    "type": rel_type,
                                })
                    except Exception as e:
                        print(f"[GraphRAGService] 深度检索失败({entity}, hop={hop}): {e}")
            
            # 计算此跳的置信度
            confidence = "high" if len(hop_subgraphs) > 0 else "none"
            if 0 < len(hop_subgraphs) < len(frontier):
                confidence = "medium"
            
            chain_entry = {
                "hop": hop,
                "entities": hop_entities[:branching_factor],
                "relations": hop_relations[:branching_factor * 2],
                "confidence": confidence,
            }
            reasoning_chain.append(chain_entry)
            
            # 累积知识
            if hop_subgraphs:
                hop_aggregated = self._aggregate_knowledge(hop_subgraphs)
                accumulated_knowledge.extend(hop_aggregated)
            
            # 如果当前跳没有任何新发现，标记为缺失环节
            if not hop_entities and not hop_relations:
                # 尝试用LLM推断可能缺失的关系
                missing_entry = {
                    "hop": hop,
                    "query_entities": frontier[:3],
                    "reason": "知识图谱中未找到进一步的关联实体",
                    "suggested_types": self._infer_missing_relations(
                        query, frontier[:3]
                    ),
                }
                missing_links.append(missing_entry)
                break  # 无法继续扩展
            
            # 准备下一跳的frontier
            next_frontier = hop_entities[:branching_factor]
            if not next_frontier:
                break
            frontier = next_frontier
        
        # 步骤N：聚合所有子图的知识
        aggregated = self._aggregate_knowledge(all_subgraphs)
        
        # 构建增强推理上下文
        reasoning_context = self._build_deep_reasoning_context(
            entities, reasoning_chain, accumulated_knowledge, missing_links
        )
        
        print(f"[GraphRAGService] search_with_depth完成: "
              f"{len(reasoning_chain)}跳, {len(accumulated_knowledge)}条累积知识, "
              f"{len(missing_links)}个缺失环节")
        
        return {
            "reasoning_chain": reasoning_chain,
            "accumulated_knowledge": accumulated_knowledge,
            "missing_links": missing_links,
            "entities": entities,
            "subgraphs": all_subgraphs,
            "aggregated_knowledge": aggregated,
            "reasoning_context": reasoning_context,
        }
    
    def _build_deep_reasoning_context(
        self,
        entities: List[str],
        reasoning_chain: List[Dict[str, Any]],
        accumulated_knowledge: List[Dict[str, Any]],
        missing_links: List[Dict[str, Any]],
    ) -> str:
        """构建深度推理上下文
        
        将多跳推理链和缺失关系转换为LLM可用的结构化上下文。
        """
        parts = ["=== GraphRAG深度推理上下文 ==="]
        parts.append(f"识别实体: {', '.join(entities)}")
        parts.append(f"推理深度: {len(reasoning_chain)}跳")
        parts.append("")
        
        # 推理链条
        parts.append("## 推理链条")
        for entry in reasoning_chain:
            hop = entry["hop"]
            hop_entities = entry.get("entities", [])
            hop_relations = entry.get("relations", [])
            confidence = entry.get("confidence", "none")
            
            parts.append(f"### 第{hop}跳 (置信度: {confidence})")
            if hop_entities:
                parts.append(f"  新实体: {', '.join(hop_entities[:10])}")
            if hop_relations:
                parts.append(f"  发现关系:")
                for rel in hop_relations[:8]:
                    parts.append(f"    {rel['source']} --[{rel['type']}]--> {rel['target']}")
            parts.append("")
        
        # 累积知识
        if accumulated_knowledge:
            parts.append("## 累积知识")
            for entry in accumulated_knowledge[:5]:
                entity = entry.get("entity", "")
                props = entry.get("properties", {})
                if entity:
                    parts.append(f"  【{entity}】")
                    for k, v in list(props.items())[:5]:
                        parts.append(f"    - {k}: {v}")
        
        # 缺失环节
        if missing_links:
            parts.append("")
            parts.append("## 缺失的知识链接（需LLM补充推理）")
            for i, missing in enumerate(missing_links, 1):
                parts.append(
                    f"  {i}. 第{missing['hop']}跳: 从'{', '.join(missing['query_entities'])}'出发，"
                    f"KG中无更多关联 (原因: {missing['reason']})"
                )
                suggested = missing.get("suggested_types", [])
                if suggested:
                    parts.append(f"     建议检索的关系类型: {', '.join(suggested[:5])}")
        
        return "\n".join(parts)
    
    def _infer_missing_relations(self, query: str, frontier_entities: List[str]) -> List[str]:
        """推断KG中缺失的可能关系类型
        
        基于查询上下文和已有实体，推测可能需要的但KG中不存在的关系类型。
        """
        # 基于规则推断常见缺失关系
        inferred = []
        
        # 制图领域常见关系模式
        relation_patterns = {
            "交通图": ["HAS_SYMBOL", "USES_COLOR", "REQUIRES_LAYER"],
            "旅游图": ["HAS_SYMBOL", "USES_COLOR", "REQUIRES_LAYER", "CONTAINS_POI"],
            "道路": ["HAS_SYMBOL", "BELONGS_TO_LAYER", "AFFECTED_BY_SCALE"],
            "水系": ["HAS_SYMBOL", "BELONGS_TO_LAYER", "USES_COLOR"],
            "配色": ["APPLIES_TO", "CONSTRAINED_BY", "RECOMMENDED_FOR"],
            "符号": ["VISUALIZES", "BELONGS_TO_SCHEME", "SCALES_WITH"],
        }
        
        for keyword, rel_types in relation_patterns.items():
            if keyword in query:
                for rt in rel_types:
                    if rt not in inferred:
                        inferred.append(rt)
        
        if not inferred:
            inferred = ["RELATES_TO", "INFLUENCES", "REQUIRES"]
        
        return inferred
    
    # ==================== 增强方法2：推理路径可视化 ====================
    
    def get_reasoning_paths(self, entity_a: str, entity_b: str,
                            max_depth: int = 3) -> List[List[Dict]]:
        """查找两个实体之间的推理路径
        
        在知识图谱中查找从entity_a到entity_b的所有可达推理路径，
        每条路径是关系跳转的序列。用于回答"为什么交通图要用暖色调？"
        这类需要推理链的问题。
        
        Args:
            entity_a: 起始实体名称
            entity_b: 目标实体名称
            max_depth: 最大搜索深度（跳数），默认3跳
            
        Returns:
            多条推理路径，每条路径是 [{source, relation, target}, ...] 序列
            按路径长度排序（短路径优先）
        """
        print(f"[GraphRAGService] 查找推理路径: {entity_a} -> {entity_b}, max_depth={max_depth}")
        
        if not self.kg_service:
            print("[GraphRAGService] KG服务不可用，无法查找推理路径")
            return []
        
        # 使用BFS查找所有路径
        all_paths = []
        visited_in_path: set = set()
        
        def bfs_find_paths(start: str, target: str, depth: int) -> List[List[Dict]]:
            """BFS查找从start到target的所有路径"""
            paths = []
            queue = [(start, [])]  # (当前节点, 当前路径)
            visited_local: Dict[str, int] = {start: 0}  # 节点 -> 最小深度
            
            while queue:
                current, path = queue.pop(0)
                current_depth = len(path)
                
                if current_depth >= depth:
                    continue
                
                # 获取当前节点的邻居子图
                try:
                    subgraph = self.kg_service.get_subgraph(current, depth=1, limit=30)
                except Exception as e:
                    print(f"[GraphRAGService] BFS子图检索失败({current}): {e}")
                    continue
                
                for link in subgraph.get("links", []):
                    rel_type = link.get("type", "")
                    source = link.get("source", "")
                    target = link.get("target", "")
                    
                    # 确定邻居节点（可能是source或target）
                    neighbor = None
                    if source == current:
                        neighbor = target
                    elif target == current:
                        neighbor = source
                    
                    if not neighbor:
                        continue
                    
                    # 避免环路
                    nodes_in_path = {step["source"] for step in path}
                    nodes_in_path.add(current)
                    if neighbor in nodes_in_path:
                        continue
                    
                    new_step = {
                        "source": current,
                        "relation": rel_type,
                        "target": neighbor,
                    }
                    new_path = path + [new_step]
                    
                    if neighbor == target:
                        # 找到目标
                        paths.append(new_path)
                    elif len(new_path) < depth:
                        # 继续搜索
                        if neighbor not in visited_local or visited_local[neighbor] > len(new_path):
                            visited_local[neighbor] = len(new_path)
                            queue.append((neighbor, new_path))
            
            return paths
        
        all_paths = bfs_find_paths(entity_a, entity_b, max_depth)
        
        # 去重（基于关系序列）
        unique_paths = []
        seen_signatures = set()
        for path in all_paths:
            sig = tuple((step["source"], step["relation"], step["target"]) for step in path)
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                unique_paths.append(path)
        
        # 按路径长度排序
        unique_paths.sort(key=len)
        
        print(f"[GraphRAGService] 找到{len(unique_paths)}条推理路径")
        return unique_paths
    
    # ==================== 增强方法3：知识冲突检测 ====================
    
    def detect_conflicts(self, entity_name: str) -> List[Dict]:
        """检测知识图谱中的冲突知识
        
        检测同一实体是否存在矛盾的属性或关系。
        例如：同一MapType关联了两种矛盾的配色方案。
        
        Args:
            entity_name: 要检测冲突的实体名称
            
        Returns:
            冲突列表，每项含：
            {
                "entity": str,
                "conflict_type": str,       # 冲突类型: attribute / relation / schema
                "description": str,          # 冲突描述
                "conflicting_items": [...],  # 冲突项
                "confidence": str,           # 冲突置信度: high / medium / low
                "resolution_suggestion": str, # 解决建议
            }
        """
        print(f"[GraphRAGService] 检测实体冲突: {entity_name}")
        conflicts = []
        
        if not self.kg_service:
            return conflicts
        
        # 获取实体的子图（深度为1跳，获取所有直接关联）
        try:
            subgraph = self.kg_service.get_subgraph(entity_name, depth=1, limit=50)
        except Exception as e:
            print(f"[GraphRAGService] 冲突检测子图检索失败: {e}")
            return conflicts
        
        nodes = subgraph.get("nodes", [])
        links = subgraph.get("links", [])
        
        if not nodes:
            return conflicts
        
        # === 冲突检测1: 同一关系类型但目标不同 ===
        rel_groups: Dict[str, List[Dict]] = {}
        for link in links:
            rel_type = link.get("type", "")
            if rel_type not in rel_groups:
                rel_groups[rel_type] = []
            rel_groups[rel_type].append({
                "source": link.get("source", ""),
                "target": link.get("target", ""),
                "type": rel_type,
            })
        
        for rel_type, rels in rel_groups.items():
            if len(rels) >= 2:
                # 检查是否是矛盾的推荐（如HAS_COLOR指向不同颜色）
                if rel_type in ("HAS_COLOR", "USES_COLOR", "RECOMMENDS", "MAPS_TO"):
                    targets = [r.get("target", "") for r in rels]
                    # 获取目标节点的属性差异
                    target_details = []
                    for node in nodes:
                        node_name = node.get("name", "")
                        if node_name in targets:
                            target_details.append({
                                "name": node_name,
                                "label": node.get("label", ""),
                                "properties": node.get("properties", {}),
                            })
                    
                    # 检查是否存在语义上的矛盾
                    if len(target_details) >= 2:
                        props_list = [td.get("properties", {}) for td in target_details]
                        # 简单启发式：同一实体经由同一关系关联到不同目标
                        conflict_desc = (
                            f"实体'{entity_name}'通过'{rel_type}'关系关联到{len(rels)}个不同目标: "
                            f"{', '.join(targets[:5])}"
                        )
                        conflicts.append({
                            "entity": entity_name,
                            "conflict_type": "relation",
                            "description": conflict_desc,
                            "conflicting_items": rels[:10],
                            "target_details": target_details[:5],
                            "confidence": "medium" if len(rels) <= 3 else "high",
                            "resolution_suggestion": (
                                f"请检查'{rel_type}'关系是否应存在优先级或条件筛选，"
                                f"或在目标实体中添加适用条件（如map_type, audience_level）"
                            ),
                        })
        
        # === 冲突检测2: 属性值矛盾 ===
        # 检查同类节点（同label）是否存在矛盾的属性
        label_groups: Dict[str, List[Dict]] = {}
        for node in nodes:
            label = node.get("label", "Unknown")
            if label not in label_groups:
                label_groups[label] = []
            label_groups[label].append(node)
        
        for label, group in label_groups.items():
            if len(group) < 2:
                continue
            
            # 检查attribute类型节点是否有冲突值
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    node_a = group[i]
                    node_b = group[j]
                    props_a = node_a.get("properties", {})
                    props_b = node_b.get("properties", {})
                    
                    # 找出共同的属性键
                    common_keys = set(props_a.keys()) & set(props_b.keys())
                    for key in common_keys:
                        val_a = props_a[key]
                        val_b = props_b[key]
                        # 检查数值型属性的显著差异
                        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                            if val_a != 0 and abs(val_a - val_b) / abs(val_a) > 0.5:
                                conflicts.append({
                                    "entity": entity_name,
                                    "conflict_type": "attribute",
                                    "description": (
                                        f"在'{entity_name}'的子图中，节点'{node_a.get('name', '')}'和"
                                        f"'{node_b.get('name', '')}'的'{key}'属性值差异显著: "
                                        f"{val_a} vs {val_b}"
                                    ),
                                    "conflicting_items": [
                                        {"node": node_a.get("name", ""), key: val_a},
                                        {"node": node_b.get("name", ""), key: val_b},
                                    ],
                                    "confidence": "high" if abs(val_a - val_b) / max(abs(val_a), abs(val_b)) > 0.8 else "medium",
                                    "resolution_suggestion": (
                                        f"请确认'{key}'属性的正确取值范围，"
                                        f"或检查两个节点是否应属于不同的上下文"
                                    ),
                                })
        
        print(f"[GraphRAGService] 检测到{len(conflicts)}个冲突")
        return conflicts
    
    def get_ontology_info(self) -> Dict[str, Any]:
        """获取本体概要信息
        
        Returns:
            本体类别和节点统计信息
        """
        try:
            from app.core.kg_ontology import get_ontology_summary
            return get_ontology_summary()
        except ImportError:
            return {"error": "本体模块未加载"}
