"""知识图谱服务 - Neo4j知识图谱管理与查询

支持两种运行模式：
1. Neo4j可用模式：完整图数据库，支持Cypher查询、实体/关系管理
2. 内存规则模式（降级）：Neo4j不可用时自动降级，使用CITY_BBOX和WUHAN_LANDMARKS作为内置知识

KGService为制图智能体提供知识支撑：
- 制图约束（不同地图类型的规范要求）
- 样式推荐（地图类型对应的推荐配色和样式）
- 地标查询（城市地标POI信息）
- 图谱可视化（D3.js格式的节点和边数据）
- 制图决策查询（指定地图类型的完整制图方案，含图层配置、符号方案、配色方案、标注规则）
- 图层顺序查询（指定地图类型的图层叠置顺序）
"""
import json
import os
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import CITY_BBOX, WUHAN_LANDMARKS, MAP_STYLES
from app.core.exceptions import KnowledgeGraphError
from app.utils.helpers import generate_id


class KGService:
    """知识图谱服务

    管理制图领域知识图谱，提供约束查询、样式推荐、自然语言问答等功能。
    Neo4j连接失败时自动降级为内存规则模式。
    """

    def __init__(self, llm_service=None):
        """初始化知识图谱服务

        尝试连接Neo4j，连接失败则降级为内存规则模式。

        Args:
            llm_service: LLM服务实例（可选），用于自然语言查询生成Cypher
        """
        self.llm_service = llm_service
        self.driver = None
        self._memory_store: Dict[str, List[dict]] = {}  # 内存模式的数据存储

        # 无论 Neo4j 是否可用，都先加载内存知识库：
        # 1) Neo4j 不可用时作为主数据源；
        # 2) Neo4j 可用时作为决策查询的兜底，避免图库缺数据时静默回退到硬编码。
        self._init_memory_store()

        # 尝试连接Neo4j
        try:
            from neo4j import GraphDatabase

            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            # 验证连接
            self.driver.verify_connectivity()
            print("[KGService] Neo4j连接成功，使用图数据库模式")
            # 幂等补齐制图决策数据：仅在图谱缺少 CartographicDecision 时写入，
            # 否则每此启动都全量 MERGE 会产生不必要的写开销。
            self.ensure_decision_data()
        except Exception as e:
            print(f"[KGService] Neo4j连接失败: {e}，降级为内存规则模式")
            self.driver = None

    # ==================== 知识初始化 ====================

    def init_knowledge(self) -> bool:
        """初始化图谱数据

        在Neo4j中创建制图领域知识节点和关系，包括：
        - 地图类型节点（MapType）及其样式约束
        - 制图规则节点（CartographyRule）
        - 城市和地标节点（City, Landmark）

        Returns:
            初始化是否成功
        """
        if self.driver is None:
            print("[KGService] 内存模式，知识已内置，无需初始化")
            return True

        try:
            with self.driver.session() as session:
                # 创建约束（防止重复节点）
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:MapType) REQUIRE m.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Landmark) REQUIRE l.name IS UNIQUE")

                # 创建地图类型节点及制图约束
                map_type_constraints = {
                    "traffic": "交通图应包含道路和铁路网络，使用暖色调区分道路等级",
                    "tourism": "旅游图应标注景点、博物馆、历史遗迹，使用醒目标记",
                    "campus": "校园图应包含教学楼、宿舍、绿地等设施，使用清新配色",
                    "basic": "基础地图应包含道路、水系、生活设施，使用中性色调",
                    "food": "美食图应标注餐厅、咖啡馆等餐饮场所，使用暖色标记",
                    "administrative": "行政区划图应包含行政边界，使用区分色填充",
                }

                for map_type, constraint in map_type_constraints.items():
                    session.run(
                        "MERGE (m:MapType {name: $name}) "
                        "SET m.constraint = $constraint, m.updated_at = timestamp()",
                        name=map_type,
                        constraint=constraint,
                    )

                # 创建城市和地标节点
                for city_name, bbox in CITY_BBOX.items():
                    session.run(
                        "MERGE (c:City {name: $name}) "
                        "SET c.min_lat = $min_lat, c.min_lon = $min_lon, "
                        "c.max_lat = $max_lat, c.max_lon = $max_lon, "
                        "c.center_lat = $center_lat, c.center_lon = $center_lon",
                        name=city_name,
                        min_lat=bbox["min_lat"],
                        min_lon=bbox["min_lon"],
                        max_lat=bbox["max_lat"],
                        max_lon=bbox["max_lon"],
                        center_lat=bbox["center_lat"],
                        center_lon=bbox["center_lon"],
                    )

                # 创建武汉地标节点并关联到城市
                for landmark in WUHAN_LANDMARKS:
                    session.run(
                        "MERGE (l:Landmark {name: $name}) "
                        "SET l.lat = $lat, l.lng = $lng, l.type = $type",
                        name=landmark["name"],
                        lat=landmark["lat"],
                        lng=landmark["lng"],
                        type=landmark["type"],
                    )
                    session.run(
                        "MATCH (c:City {name: '武汉市'}), (l:Landmark {name: $name}) "
                        "MERGE (c)-[:HAS_LANDMARK]->(l)",
                        name=landmark["name"],
                    )

                print("[KGService] 知识图谱初始化完成")
                return True

        except Exception as e:
            print(f"[KGService] 知识初始化失败: {e}")
            return False

    # ==================== 制图决策数据导入 ====================

    def ensure_decision_data(self) -> None:
        """幂等确保 Neo4j 中存在 CartographicDecision 节点

        启动时调用：检查 Neo4j 中是否已有 CartographicDecision 节点，
        若为空则从 init_data.json 批量导入，并建立 HAS_DECISION 关系。
        已有数据时跳过，避免重复写入。
        """
        if self.driver is None:
            return

        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (d:CartographicDecision) RETURN count(d) AS cnt"
                )
                cnt = result.single()["cnt"]
                if cnt > 0:
                    print(f"[KGService] Neo4j已有 {cnt} 条CartographicDecision，跳过导入")
                    return

            # 库中无决策数据 → 从 init_data.json 导入
            init_path = self._resolve_init_data_path()
            if not init_path:
                print("[KGService] 未找到 init_data.json，无法导入制图决策数据")
                return

            with open(init_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            nodes = data.get("nodes", [])
            decisions = [n for n in nodes if n.get("label") == "CartographicDecision"]

            if not decisions:
                print("[KGService] init_data.json 中无 CartographicDecision 节点")
                return

            with self.driver.session() as session:
                # 确保 MapType 节点存在
                map_types = set(d.get("map_type") for d in decisions if d.get("map_type"))
                for mt in map_types:
                    session.run("MERGE (m:MapType {name: $name})", name=mt)

                # 批量写入 CartographicDecision 节点
                for d in decisions:
                    props = {
                        "name": d.get("name"),
                        "decision_type": d.get("decision_type"),
                        "map_type": d.get("map_type"),
                        "audience_level": d.get("audience_level", "public"),
                        "parameters": json.dumps(d.get("parameters", {}), ensure_ascii=False),
                        "priority": d.get("priority", "medium"),
                        "rationale": d.get("rationale", ""),
                    }
                    session.run(
                        "MERGE (d:CartographicDecision {name: $name}) "
                        "SET d.decision_type = $decision_type, "
                        "d.map_type = $map_type, "
                        "d.audience_level = $audience_level, "
                        "d.parameters = $parameters, "
                        "d.priority = $priority, "
                        "d.rationale = $rationale",
                        **props,
                    )
                    # 建立 HAS_DECISION 关系
                    session.run(
                        "MATCH (m:MapType {name: $mt}), (d:CartographicDecision {name: $name}) "
                        "MERGE (m)-[:HAS_DECISION]->(d)",
                        mt=d.get("map_type"),
                        name=d.get("name"),
                    )

            print(f"[KGService] 已从 init_data.json 导入 {len(decisions)} 条CartographicDecision到Neo4j")

        except Exception as e:
            print(f"[KGService] ensure_decision_data 失败: {e}（不影响运行，内存模式仍可用）")

    def _resolve_init_data_path(self) -> Optional[str]:
        """定位 init_data.json 文件路径"""
        candidates = [
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "data", "kg", "init_data.json"
            ),
            os.path.join(os.getcwd(), "data", "kg", "init_data.json"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    # ==================== 知识查询 ====================

    def get_constraints(self) -> List[Dict[str, str]]:
        """获取制图约束列表

        Returns:
            约束列表，每项包含 map_type 和 constraint 字段
        """
        if self.driver is None:
            # 内存模式：返回内置约束
            constraints = self._memory_store.get("constraints", [])
            return constraints

        try:
            with self.driver.session() as session:
                result = session.run("MATCH (m:MapType) RETURN m.name AS map_type, m.constraint AS constraint")
                return [
                    {"map_type": record["map_type"], "constraint": record["constraint"]}
                    for record in result
                ]
        except Exception as e:
            print(f"[KGService] 查询约束失败: {e}")
            return []

    def get_style_recommendations(self, map_type: str,
                                  extra_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """获取指定地图类型的样式推荐

        Args:
            map_type: 地图类型（traffic/tourism/campus等）
            extra_params: 附加查询参数（audience/topic/region 等），兼容 AgentService 调用

        Returns:
            样式推荐列表，每项包含 element_type 和 style 字段
        """
        # 从MAP_STYLES获取样式配置
        recommendations = []
        for element_type, style in MAP_STYLES.items():
            if isinstance(style, list):
                # highway类型有子类型，展开为多个推荐
                for config in style:
                    subtypes = config.get("subtypes", {})
                    for subtype, sub_style in subtypes.items():
                        recommendations.append({
                            "element_type": element_type,
                            "subtype": subtype,
                            "style": sub_style,
                        })
                    default_style = config.get("default")
                    if default_style:
                        recommendations.append({
                            "element_type": element_type,
                            "subtype": "default",
                            "style": default_style,
                        })
            elif isinstance(style, dict):
                recommendations.append({
                    "element_type": element_type,
                    "subtype": "default",
                    "style": style,
                })

        # 如果Neo4j可用，尝试获取图谱中的额外样式推荐
        if self.driver is not None:
            try:
                with self.driver.session() as session:
                    result = session.run(
                        "MATCH (m:MapType {name: $map_type})-[:RECOMMENDS_STYLE]->(s:StyleRecommendation) "
                        "RETURN s.element_type AS element_type, s.style AS style",
                        map_type=map_type,
                    )
                    for record in result:
                        recommendations.append({
                            "element_type": record["element_type"],
                            "subtype": "recommended",
                            "style": record["style"],
                        })
            except Exception as e:
                print(f"[KGService] 查询样式推荐失败: {e}")

        return recommendations

    def get_graph_data(self, limit: int = 100) -> Dict[str, List[dict]]:
        """获取图谱可视化数据（D3.js格式）

        Args:
            limit: 最多返回的节点数量

        Returns:
            {"nodes": [{id, label, name, properties}], "links": [{source, target, type}]}
        """
        if self.driver is None:
            # 内存模式：返回内置地标图谱
            return self._get_memory_graph_data(limit)

        try:
            with self.driver.session() as session:
                # 查询节点
                node_result = session.run(
                    f"MATCH (n) RETURN id(n) AS id, labels(n) AS labels, "
                    f"n.name AS name, properties(n) AS properties LIMIT {limit}"
                )
                nodes = []
                node_id_map = {}  # Neo4j内部ID到字符串ID的映射
                for record in node_result:
                    neo4j_id = record["id"]
                    str_id = str(neo4j_id)
                    node_id_map[neo4j_id] = str_id
                    labels = record["labels"]
                    label = labels[0] if labels else "Unknown"
                    nodes.append({
                        "id": str_id,
                        "label": label,
                        "name": record["name"] or "未命名",
                        "properties": dict(record["properties"]),
                    })

                # 查询关系
                link_result = session.run(
                    f"MATCH (a)-[r]->(b) "
                    f"RETURN id(a) AS source, id(b) AS target, type(r) AS type LIMIT {limit * 2}"
                )
                links = []
                for record in link_result:
                    source_id = node_id_map.get(record["source"])
                    target_id = node_id_map.get(record["target"])
                    if source_id and target_id:
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "type": record["type"],
                        })

                return {"nodes": nodes, "links": links}

        except Exception as e:
            print(f"[KGService] 获取图谱数据失败: {e}")
            return {"nodes": [], "links": []}

    def get_subgraph(self, entity_name: str, depth: int = 2, limit: int = 50) -> Dict[str, List[dict]]:
        """获取以指定实体为中心的子图 - 支持多跳检索（GraphRAG核心）

        从指定实体出发，检索depth跳范围内的所有节点和关系。
        Neo4j可用时使用Cypher变长路径查询，否则使用内存BFS遍历。

        Args:
            entity_name: 中心实体名称
            depth: 检索深度（跳数），默认2跳
            limit: 最多返回的节点数量

        Returns:
            {"nodes": [...], "links": [...], "center": entity_name}
        """
        if self.driver is None:
            return self._get_memory_subgraph(entity_name, depth, limit)

        try:
            with self.driver.session() as session:
                # Cypher多跳查询
                result = session.run(
                    f"MATCH path = (n {{name: $name}})-[*1..{depth}]-(m) "
                    f"WITH DISTINCT n, m, relationships(path) AS rels "
                    f"LIMIT {limit} "
                    f"RETURN n, m, rels",
                    name=entity_name,
                )
                # 构建子图数据
                nodes_set = {}
                links = []
                for record in result:
                    n_node = record["n"]
                    m_node = record["m"]
                    for neo4j_node in [n_node, m_node]:
                        nid = str(neo4j_node.id)
                        if nid not in nodes_set:
                            labels = list(neo4j_node.labels)
                            nodes_set[nid] = {
                                "id": nid,
                                "label": labels[0] if labels else "Unknown",
                                "name": neo4j_node.get("name", "未命名"),
                                "properties": dict(neo4j_node),
                            }
                    # 添加关系
                    for rel in record["rels"]:
                        links.append({
                            "source": str(rel.start_node.id),
                            "target": str(rel.end_node.id),
                            "type": rel.type,
                        })

                return {
                    "nodes": list(nodes_set.values())[:limit],
                    "links": links,
                    "center": entity_name,
                }
        except Exception as e:
            print(f"[KGService] 子图检索失败: {e}")
            return {"nodes": [], "links": [], "center": entity_name}

    def _get_memory_subgraph(self, entity_name: str, depth: int, limit: int) -> Dict[str, List[dict]]:
        """内存模式的子图检索 - 广度优先遍历

        Args:
            entity_name: 中心实体名称
            depth: 检索深度
            limit: 最多返回节点数

        Returns:
            子图数据 {"nodes": [...], "links": [...], "center": entity_name}
        """
        all_nodes = self._memory_store.get("nodes", [])
        all_relations = self._memory_store.get("relations", [])

        # 找到起始节点（按name匹配）
        start_nodes = [
            n for n in all_nodes
            if n.get("name") == entity_name
            or entity_name in str(n.get("properties", {}).get("name", ""))
        ]
        if not start_nodes:
            return {"nodes": [], "links": [], "center": entity_name}

        # BFS遍历
        visited = set()
        queue = [(n, 0) for n in start_nodes]
        result_nodes = []
        result_links = []

        while queue and len(result_nodes) < limit:
            node, current_depth = queue.pop(0)
            node_id = node.get("id", node.get("name", ""))
            if node_id in visited:
                continue
            visited.add(node_id)

            result_nodes.append({
                "id": node_id,
                "label": node.get("label", "Unknown"),
                "name": node.get("name", node.get("properties", {}).get("name", "未命名")),
                "properties": node.get("properties", {}),
            })

            if current_depth >= depth:
                continue

            # 查找相邻节点（通过关系）
            node_name = node.get("name", "")
            for rel in all_relations:
                rel_from = rel.get("from", rel.get("source", ""))
                rel_to = rel.get("to", rel.get("target", ""))

                if rel_from == node_name:
                    # 出边关系
                    target_name = rel_to
                    result_links.append({
                        "source": node_id,
                        "target": target_name,
                        "type": rel.get("type", "RELATED"),
                    })
                    # 查找目标节点加入队列
                    next_nodes = [n for n in all_nodes if n.get("name") == target_name]
                    for nn in next_nodes:
                        nn_id = nn.get("id", nn.get("name", ""))
                        if nn_id not in visited:
                            queue.append((nn, current_depth + 1))

                elif rel_to == node_name:
                    # 入边关系
                    source_name = rel_from
                    result_links.append({
                        "source": source_name,
                        "target": node_id,
                        "type": rel.get("type", "RELATED"),
                    })
                    # 查找源节点加入队列
                    next_nodes = [n for n in all_nodes if n.get("name") == source_name]
                    for nn in next_nodes:
                        nn_id = nn.get("id", nn.get("name", ""))
                        if nn_id not in visited:
                            queue.append((nn, current_depth + 1))

        return {"nodes": result_nodes, "links": result_links, "center": entity_name}

    def query_cartographic_decision(self, map_type: str, audience: str = "public") -> Dict[str, Any]:
        """查询指定地图类型和受众的完整制图决策方案

        从知识图谱中检索与指定地图类型和受众相关的所有制图决策，
        按decision_type分组组装为结构化方案。

        Args:
            map_type: 地图类型（traffic/tourism/campus/food/basic/administrative）
            audience: 目标受众级别（public/professional/expert），默认public

        Returns:
            结构化制图决策方案字典，包含：
            {
                "map_type": str,
                "audience": str,
                "layer_configs": [{...}],
                "symbol_scheme": {...},
                "color_scheme": {...},
                "annotation_rules": {...},
                "confidence": str,
            }
            如果找不到决策数据，返回空字典。
        """
        if self.driver is None:
            return self._query_cartographic_decision_memory(map_type, audience)

        try:
            with self.driver.session() as session:
                # 查询指定地图类型和受众的所有制图决策（parameters 为 JSON 字符串，需解析）
                decisions = self._fetch_decision_records(session, map_type, audience)
                if not decisions:
                    # 放宽受众匹配（与内存模式保持一致）
                    decisions = self._fetch_decision_records(session, map_type, None)

                if not decisions:
                    print(f"[KGService] 未找到地图类型'{map_type}'受众'{audience}'的制图决策数据，回退内存模式")
                    return self._query_cartographic_decision_memory(map_type, audience)

                # 按decision_type分组组装结果
                decision_map: Dict[str, Any] = {}
                for d in decisions:
                    dtype = d.get("decision_type", "")
                    if dtype and dtype not in decision_map:
                        decision_map[dtype] = d

                assembled = self._assemble_decision(decision_map, map_type, audience)
                print(f"[KGService] 查询制图决策成功(Neo4j): map_type={map_type}, audience={audience}, "
                      f"decisions={len(decisions)}, confidence={assembled['confidence']}")
                return assembled

        except Exception as e:
            print(f"[KGService] 查询制图决策失败: {e}，回退到内存模式")
            return self._query_cartographic_decision_memory(map_type, audience)

    def _fetch_decision_records(self, session, map_type: str, audience: Optional[str]) -> List[Dict[str, Any]]:
        """从 Neo4j 读取制图决策记录

        将 Neo4j 中以 JSON 字符串存储的 parameters 还原为字典。

        Args:
            session: Neo4j 会话
            map_type: 地图类型
            audience: 受众级别；为 None 时不按受众过滤

        Returns:
            决策记录列表
        """
        if audience is None:
            cypher = (
                "MATCH (m:MapType {name: $map_type})-[:HAS_DECISION]->(d:CartographicDecision) "
                "RETURN d.decision_type AS decision_type, d.parameters AS parameters, "
                "d.priority AS priority, d.rationale AS rationale, d.name AS name"
            )
            params: Dict[str, Any] = {"map_type": map_type}
        else:
            cypher = (
                "MATCH (m:MapType {name: $map_type})-[:HAS_DECISION]->(d:CartographicDecision) "
                "WHERE d.audience_level = $audience "
                "RETURN d.decision_type AS decision_type, d.parameters AS parameters, "
                "d.priority AS priority, d.rationale AS rationale, d.name AS name"
            )
            params = {"map_type": map_type, "audience": audience}

        records: List[Dict[str, Any]] = []
        for record in session.run(cypher, **params):
            d = record.data()
            d["parameters"] = self._parse_json_prop(d.get("parameters"))
            records.append(d)
        return records

    @staticmethod
    def _parse_json_prop(value: Any) -> Any:
        """将 Neo4j 中以 JSON 字符串存储的复杂属性还原为 Python 对象"""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    def _assemble_decision(self, decision_map: Dict[str, Any], map_type: str,
                           audience: str) -> Dict[str, Any]:
        """将按 decision_type 分组的决策统一组装为结构化制图方案

        Neo4j 模式与内存模式共用此方法，保证两条路径输出结构完全一致。
        符号方案兼容 {symbols: {...}} 与扁平 {...} 两种结构。

        Args:
            decision_map: {decision_type: 决策记录}
            map_type: 地图类型
            audience: 受众级别

        Returns:
            结构化制图决策方案
        """
        assembled: Dict[str, Any] = {
            "map_type": map_type,
            "audience": audience,
        }

        # 图层配置
        layer_cfg = decision_map.get("LAYER_CONFIG")
        lc_params = layer_cfg.get("parameters", {}) if layer_cfg else {}
        assembled["layer_configs"] = lc_params.get("layers", []) if isinstance(lc_params, dict) else []

        # 符号方案：兼容 {symbols: {...}} 与扁平 {...} 两种结构
        symbol_decision = decision_map.get("SYMBOL_SCHEME")
        sym_params = symbol_decision.get("parameters", {}) if symbol_decision else {}
        if isinstance(sym_params, dict):
            assembled["symbol_scheme"] = sym_params.get("symbols", sym_params)
        else:
            assembled["symbol_scheme"] = {}

        # 配色方案
        color_decision = decision_map.get("COLOR_SCHEME")
        col_params = color_decision.get("parameters", {}) if color_decision else {}
        assembled["color_scheme"] = col_params if isinstance(col_params, dict) else {}

        # 标注规则
        annotation_decision = decision_map.get("ANNOTATION_RULE")
        ann_params = annotation_decision.get("parameters", {}) if annotation_decision else {}
        assembled["annotation_rules"] = ann_params if isinstance(ann_params, dict) else {}

        # 计算置信度（基于找到的决策数量占4种类型的比例）
        type_count = sum(
            1 for t in ["LAYER_CONFIG", "SYMBOL_SCHEME", "COLOR_SCHEME", "ANNOTATION_RULE"]
            if t in decision_map
        )
        if type_count >= 4:
            assembled["confidence"] = "high"
        elif type_count >= 2:
            assembled["confidence"] = "medium"
        elif type_count >= 1:
            assembled["confidence"] = "low"
        else:
            assembled["confidence"] = "none"
        return assembled

    def _query_cartographic_decision_memory(self, map_type: str, audience: str) -> Dict[str, Any]:
        """内存模式的制图决策查询

        从 self._memory_store 中过滤 CartographicDecision 节点，
        查找与指定地图类型和受众匹配的决策，按decision_type分组组装结果。

        Args:
            map_type: 地图类型
            audience: 目标受众级别

        Returns:
            结构化制图决策方案字典
        """
        all_nodes = self._memory_store.get("nodes", [])

        # 过滤出匹配的CartographicDecision节点
        matched_decisions = []
        for node in all_nodes:
            if node.get("label") != "CartographicDecision":
                continue
            props = node.get("properties", node)
            node_map_type = props.get("map_type", "")
            node_audience = props.get("audience_level", "public")
            if node_map_type == map_type and node_audience == audience:
                matched_decisions.append(props)

        if not matched_decisions:
            # 尝试放宽受众匹配
            for node in all_nodes:
                if node.get("label") != "CartographicDecision":
                    continue
                props = node.get("properties", node)
                if props.get("map_type") == map_type:
                    matched_decisions.append(props)

        if not matched_decisions:
            print(f"[KGService] 内存模式未找到地图类型'{map_type}'的制图决策数据")
            return {}

        # 按decision_type分组（与 Neo4j 路径共用同一套组装逻辑）
        decision_map: Dict[str, Any] = {}
        for d in matched_decisions:
            dtype = d.get("decision_type", "")
            if dtype and dtype not in decision_map:
                decision_map[dtype] = d

        assembled = self._assemble_decision(decision_map, map_type, audience)
        print(f"[KGService] 内存模式查询制图决策: map_type={map_type}, audience={audience}, "
              f"decisions={len(matched_decisions)}, confidence={assembled['confidence']}")
        return assembled

    def query_layer_order(self, map_type: str) -> List[Dict[str, Any]]:
        """查询指定地图类型的图层叠置顺序

        从知识图谱中检索与指定地图类型关联的图层配置决策，
        提取并返回按叠置顺序排列的图层列表。

        Args:
            map_type: 地图类型（traffic/tourism/campus/food/basic/administrative）

        Returns:
            排序后的图层列表，每项包含 name, order, osm_tags, symbol_type 等字段。
            如果找不到图层配置，返回空列表并打印警告。
        """
        if self.driver is None:
            return self._query_layer_order_memory(map_type)

        try:
            with self.driver.session() as session:
                # parameters 在 Neo4j 中为 JSON 字符串，需解析后再取 layers
                records = self._fetch_decision_records(session, map_type, None)
                records = [r for r in records if r.get("decision_type") == "LAYER_CONFIG"]

                if not records:
                    print(f"[KGService] 未找到地图类型'{map_type}'的图层配置决策")
                    return []

                # 从决策参数中提取图层列表并排序
                layers = []
                for record in records:
                    params = record.get("parameters", {})
                    if not isinstance(params, dict):
                        continue
                    layer_list = params.get("layers", [])
                    for layer in layer_list:
                        if isinstance(layer, dict):
                            layers.append(layer)

                # 按order排序并按名称去重
                layers.sort(key=lambda x: x.get("order", 999))
                layers = self._dedupe_layers_by_name(layers)
                print(f"[KGService] 查询图层顺序成功: map_type={map_type}, layers={len(layers)}")
                return layers

        except Exception as e:
            print(f"[KGService] 查询图层顺序失败: {e}，回退到内存模式")
            return self._query_layer_order_memory(map_type)

    def _query_layer_order_memory(self, map_type: str) -> List[Dict[str, Any]]:
        """内存模式的图层顺序查询

        从 self._memory_store 中过滤与指定地图类型匹配的
        CartographicDecision（decision_type=LAYER_CONFIG）节点，
        提取并排序图层列表。

        Args:
            map_type: 地图类型

        Returns:
            排序后的图层列表
        """
        all_nodes = self._memory_store.get("nodes", [])

        # 查找匹配的图层配置决策
        layers = []
        for node in all_nodes:
            if node.get("label") != "CartographicDecision":
                continue
            props = node.get("properties", node)
            if props.get("map_type") == map_type and props.get("decision_type") == "LAYER_CONFIG":
                params = props.get("parameters", {})
                layer_list = params.get("layers", [])
                for layer in layer_list:
                    if isinstance(layer, dict):
                        layers.append(layer)

        if not layers:
            print(f"[KGService] 内存模式未找到地图类型'{map_type}'的图层配置")
            return []

        # 按order排序并按名称去重（init_data.json 与本体可能同时提供同地图类型配置）
        layers.sort(key=lambda x: x.get("order", 999))
        layers = self._dedupe_layers_by_name(layers)
        print(f"[KGService] 内存模式查询图层顺序: map_type={map_type}, layers={len(layers)}")
        return layers

    @staticmethod
    def _dedupe_layers_by_name(layers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按图层名称去重，保留排序后首个出现的图层"""
        seen = set()
        result = []
        for layer in layers:
            name = layer.get("name", "")
            key = name or id(layer)
            if key in seen:
                continue
            seen.add(key)
            result.append(layer)
        return result

    def query(self, question: str) -> str:
        """自然语言查询

        Neo4j可用时尝试用LLM生成Cypher查询执行；
        不可用时用关键词匹配WUHAN_LANDMARKS返回结果。

        Args:
            question: 自然语言问题

        Returns:
            查询结果文本
        """
        if self.driver is not None and self.llm_service is not None:
            # 尝试用LLM生成Cypher查询
            return self._query_with_llm(question)
        else:
            # 降级：关键词匹配
            return self._query_with_keywords(question)

    @staticmethod
    def _is_readonly_cypher(cypher: str) -> bool:
        """校验Cypher查询是否为只读，防止LLM生成写语句破坏图谱

        允许以只读关键字开头的查询；包含写操作关键字则拒绝。
        """
        import re as _re
        # 去除行注释后取语句主体
        cleaned = _re.sub(r"//.*", "", cypher).strip()
        upper = cleaned.upper()
        # 写操作关键字
        write_keywords = [
            "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE",
            "DROP", "LOAD", "FOREACH", "ALTER", "INDEX", "CONSTRAINT",
        ]
        if any(kw in upper for kw in write_keywords):
            return False
        # 必须以只读查询开头
        allowed_prefixes = ("MATCH", "RETURN", "WITH", "UNWIND", "OPTIONAL", "CALL")
        return upper.startswith(allowed_prefixes)

    def _query_with_llm(self, question: str) -> str:
        """使用LLM生成Cypher查询并执行

        Args:
            question: 自然语言问题

        Returns:
            查询结果文本
        """
        system_prompt = (
            "你是一个Cypher查询生成器。根据用户问题生成Neo4j Cypher查询语句。\n"
            "图谱中包含以下节点类型：MapType, City, Landmark, StyleRecommendation, CartographyRule\n"
            "关系类型包括：HAS_LANDMARK, RECOMMENDS_STYLE, FLOWS_THROUGH\n"
            "只返回Cypher查询语句，不要包含其他内容。"
        )
        prompt = f"用户问题: {question}\n\n请生成对应的Cypher查询语句："

        cypher = self.llm_service.generate(prompt, system_prompt)
        if not cypher:
            return self._query_with_keywords(question)

        # 清理LLM输出（去除markdown标记）
        cypher = cypher.strip()
        if cypher.startswith("```"):
            cypher = cypher.split("\n", 1)[1] if "\n" in cypher else cypher[3:]
        if cypher.endswith("```"):
            cypher = cypher[:-3]
        cypher = cypher.strip()

        # 安全校验：拒绝写操作，防止 LLM 生成的 Cypher 破坏图谱数据
        if not self._is_readonly_cypher(cypher):
            print(f"[KGService] 拒绝执行非只读Cypher查询: {cypher[:100]}")
            return self._query_with_keywords(question)

        try:
            from neo4j import READ_ACCESS
            # 以只读模式执行，并限制返回行数，避免大结果集拖垮服务
            with self.driver.session(default_access_mode=READ_ACCESS) as session:
                result = session.run(cypher)
                records = [dict(record) for record in result]
                if records:
                    return str(records[:50])
                else:
                    return "查询未返回结果。"
        except Exception as e:
            print(f"[KGService] Cypher查询执行失败: {e}，回退到关键词匹配")
            return self._query_with_keywords(question)

    def _query_with_keywords(self, question: str) -> str:
        """使用关键词匹配进行查询（降级模式）

        Args:
            question: 自然语言问题

        Returns:
            匹配结果文本
        """
        # 检查是否查询地标
        if any(kw in question for kw in ["地标", "景点", " landmark", "哪里", "有什么"]):
            # 尝试匹配城市
            matched_city = None
            for city in CITY_BBOX:
                short_name = city.replace("市", "")
                if short_name in question or city in question:
                    matched_city = city
                    break

            if matched_city == "武汉市" or (not matched_city and "武汉" in question):
                # 返回武汉地标
                results = []
                for landmark in WUHAN_LANDMARKS:
                    name = landmark["name"]
                    if name in question or any(
                        char in question for char in name[:2]
                    ):
                        results.append(
                            f"{landmark['name']}（{landmark['type']}）"
                            f"位于({landmark['lat']}, {landmark['lng']})"
                        )
                if results:
                    return "匹配到以下地标：\n" + "\n".join(results)
                else:
                    # 返回所有武汉地标
                    all_landmarks = [
                        f"- {lm['name']}（{lm['type']}）"
                        for lm in WUHAN_LANDMARKS
                    ]
                    return f"武汉市的已知地标有：\n" + "\n".join(all_landmarks)

        # 检查是否查询城市信息
        if any(kw in question for kw in ["城市", "范围", "坐标", "bbox"]):
            city_lines = []
            for city, bbox in CITY_BBOX.items():
                city_lines.append(
                    f"- {city}: 中心({bbox['center_lat']}, {bbox['center_lon']})"
                )
            return "支持的城市有：\n" + "\n".join(city_lines)

        # 检查是否查询制图知识
        if any(kw in question for kw in ["制图", "地图", "样式", "颜色"]):
            constraints = self.get_constraints()
            lines = [f"- {c['map_type']}: {c['constraint']}" for c in constraints]
            return "制图约束如下：\n" + "\n".join(lines)

        return f"抱歉，无法理解问题「{question}」。您可以询问城市地标、制图约束等信息。"

    # ==================== 实体/关系管理 ====================

    def create_entity(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """创建实体节点

        Args:
            label: 节点标签（如"Landmark", "City"）
            properties: 节点属性字典

        Returns:
            创建的节点信息 {"id": ..., "label": ..., "properties": ...}

        Raises:
            KnowledgeGraphError: 创建失败
        """
        if self.driver is None:
            # 内存模式
            node_id = generate_id("node")
            node = {"id": node_id, "label": label, "properties": properties}
            self._memory_store.setdefault("nodes", []).append(node)
            print(f"[KGService] 内存模式创建实体: {label} (ID: {node_id})")
            return node

        try:
            with self.driver.session() as session:
                # 动态构建属性键值对
                prop_keys = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                cypher = f"CREATE (n:{label} {{{prop_keys}}}) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties"
                result = session.run(cypher, **properties)
                record = result.single()
                if record:
                    return {
                        "id": str(record["id"]),
                        "label": record["labels"][0] if record["labels"] else label,
                        "properties": dict(record["properties"]),
                    }
                raise KnowledgeGraphError("创建实体失败：无返回结果")
        except Exception as e:
            raise KnowledgeGraphError(f"创建实体失败: {e}")

    def update_entity(self, node_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """更新实体节点属性

        Args:
            node_id: 节点ID
            properties: 要更新的属性字典

        Returns:
            更新后的节点信息

        Raises:
            KnowledgeGraphError: 更新失败
        """
        if self.driver is None:
            # 内存模式
            for node in self._memory_store.get("nodes", []):
                if node["id"] == node_id:
                    node["properties"].update(properties)
                    print(f"[KGService] 内存模式更新实体: {node_id}")
                    return node
            raise KnowledgeGraphError(f"节点不存在: {node_id}")

        try:
            with self.driver.session() as session:
                set_clauses = ", ".join([f"n.{k} = ${k}" for k in properties.keys()])
                cypher = f"MATCH (n) WHERE id(n) = toInteger($node_id) SET {set_clauses} RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties"
                params = {"node_id": node_id, **properties}
                result = session.run(cypher, **params)
                record = result.single()
                if record:
                    return {
                        "id": str(record["id"]),
                        "label": record["labels"][0] if record["labels"] else "Unknown",
                        "properties": dict(record["properties"]),
                    }
                raise KnowledgeGraphError(f"节点不存在: {node_id}")
        except Exception as e:
            raise KnowledgeGraphError(f"更新实体失败: {e}")

    def delete_entity(self, node_id: str) -> bool:
        """删除实体节点

        Args:
            node_id: 节点ID

        Returns:
            删除是否成功

        Raises:
            KnowledgeGraphError: 删除失败
        """
        if self.driver is None:
            # 内存模式
            nodes = self._memory_store.get("nodes", [])
            original_count = len(nodes)
            self._memory_store["nodes"] = [n for n in nodes if n["id"] != node_id]
            if len(self._memory_store["nodes"]) < original_count:
                print(f"[KGService] 内存模式删除实体: {node_id}")
                return True
            raise KnowledgeGraphError(f"节点不存在: {node_id}")

        try:
            with self.driver.session() as session:
                session.run("MATCH (n) WHERE id(n) = toInteger($node_id) DETACH DELETE n", node_id=node_id)
                print(f"[KGService] 删除实体: {node_id}")
                return True
        except Exception as e:
            raise KnowledgeGraphError(f"删除实体失败: {e}")

    def get_entities(self, label: str) -> List[Dict[str, Any]]:
        """按标签查询实体列表

        Args:
            label: 节点标签（如"Landmark", "MapType", "Style"等）

        Returns:
            实体列表，每项包含 id, label, properties
        """
        if self.driver is None:
            # 内存模式
            nodes = self._memory_store.get("nodes", [])
            return [n for n in nodes if n.get("label") == label]

        try:
            with self.driver.session() as session:
                result = session.run(
                    f"MATCH (n:{label}) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties LIMIT 100"
                )
                entities = []
                for record in result:
                    entities.append({
                        "id": str(record["id"]),
                        "label": record["labels"][0] if record["labels"] else label,
                        "properties": dict(record["properties"]),
                    })
                return entities
        except Exception as e:
            print(f"[KGService] 查询实体失败: {e}")
            return []

    def create_relation(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建关系

        Args:
            source_label: 源节点标签
            source_id: 源节点ID
            target_label: 目标节点标签
            target_id: 目标节点ID
            relation_type: 关系类型
            properties: 关系属性（可选）

        Returns:
            创建的关系信息

        Raises:
            KnowledgeGraphError: 创建失败
        """
        if self.driver is None:
            # 内存模式
            relation = {
                "source": source_id,
                "target": target_id,
                "type": relation_type,
                "properties": properties or {},
            }
            self._memory_store.setdefault("relations", []).append(relation)
            print(f"[KGService] 内存模式创建关系: {source_id}-[{relation_type}]->{target_id}")
            return relation

        try:
            with self.driver.session() as session:
                prop_str = ""
                params = {"source_id": source_id, "target_id": target_id}
                if properties:
                    prop_keys = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                    prop_str = f" {{{prop_keys}}}"
                    params.update(properties)

                cypher = (
                    f"MATCH (a:{source_label}) WHERE id(a) = toInteger($source_id) "
                    f"MATCH (b:{target_label}) WHERE id(b) = toInteger($target_id) "
                    f"CREATE (a)-[r:{relation_type}{prop_str}]->(b) "
                    f"RETURN type(r) AS type, id(a) AS source, id(b) AS target"
                )
                result = session.run(cypher, **params)
                record = result.single()
                if record:
                    return {
                        "source": str(record["source"]),
                        "target": str(record["target"]),
                        "type": record["type"],
                        "properties": properties or {},
                    }
                raise KnowledgeGraphError("创建关系失败：无返回结果")
        except Exception as e:
            raise KnowledgeGraphError(f"创建关系失败: {e}")

    def import_document(self, content: str, entity_labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """文档导入 - 从文本中提取实体创建节点

        简单的文档导入：通过分句和关键词匹配提取实体，
        为每个识别到的实体创建知识图谱节点。

        Args:
            content: 文档文本内容
            entity_labels: 期望提取的实体标签列表（可选）

        Returns:
            {"imported_count": N, "entities": [...]}
        """
        if entity_labels is None:
            entity_labels = ["Landmark", "City", "MapType"]

        imported_entities = []

        # 简单实体提取：匹配已知城市和地标
        for city in CITY_BBOX:
            short_name = city.replace("市", "")
            if short_name in content:
                entity = self.create_entity("City", {"name": city, "source": "document"})
                imported_entities.append(entity)

        for landmark in WUHAN_LANDMARKS:
            if landmark["name"] in content:
                entity = self.create_entity(
                    "Landmark",
                    {
                        "name": landmark["name"],
                        "lat": landmark["lat"],
                        "lng": landmark["lng"],
                        "type": landmark["type"],
                        "source": "document",
                    },
                )
                imported_entities.append(entity)

        # 如果有LLM可用，尝试用LLM增强实体提取
        if self.llm_service is not None:
            llm_prompt = (
                f"请从以下文本中提取地理实体（地名、地标、机构名），"
                f"以JSON数组格式返回，每项包含name和type字段：\n\n{content[:500]}"
            )
            llm_result = self.llm_service.generate(llm_prompt)
            if llm_result:
                # 简单解析LLM返回的JSON
                from app.utils.helpers import safe_json_loads
                entities = safe_json_loads(llm_result, [])
                if isinstance(entities, list):
                    for ent in entities:
                        if isinstance(ent, dict) and "name" in ent:
                            entity = self.create_entity(
                                entity_labels[0] if entity_labels else "Entity",
                                {"name": ent["name"], "type": ent.get("type", "unknown"), "source": "llm_extract"},
                            )
                            imported_entities.append(entity)

        print(f"[KGService] 文档导入完成，共创建{len(imported_entities)}个实体")
        return {"imported_count": len(imported_entities), "entities": imported_entities}

    # ==================== 内部辅助方法 ====================

    def _init_memory_store(self):
        """初始化内存模式的数据存储
        
        优先从 init_data.json 加载完整的知识图谱数据（含扩展本体节点），
        同时加载 kg_ontology.py 中的本体定义作为补充。
        """
        # 内置制图约束
        self._memory_store["constraints"] = [
            {"map_type": "traffic", "constraint": "交通图应包含道路和铁路网络，使用暖色调区分道路等级"},
            {"map_type": "tourism", "constraint": "旅游图应标注景点、博物馆、历史遗迹，使用醒目标记"},
            {"map_type": "campus", "constraint": "校园图应包含教学楼、宿舍、绿地等设施，使用清新配色"},
            {"map_type": "basic", "constraint": "基础地图应包含道路、水系、生活设施，使用中性色调"},
            {"map_type": "food", "constraint": "美食图应标注餐厅、咖啡馆等餐饮场所，使用暖色标记"},
            {"map_type": "administrative", "constraint": "行政区划图应包含行政边界，使用区分色填充"},
        ]

        # 优先从 init_data.json 加载完整知识图谱数据
        init_data_path = self._resolve_init_data_path()

        loaded_from_file = False
        if init_data_path and os.path.exists(init_data_path):
            try:
                with open(init_data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 加载init_data.json中的所有节点和关系
                json_nodes = data.get("nodes", [])
                json_relations = data.get("relations", [])

                # 转换节点格式：将顶层属性移入properties
                converted_nodes = []
                for node in json_nodes:
                    node = dict(node)
                    name = node.pop("name", "")
                    label = node.pop("label", "")
                    # 剩余属性放入properties
                    properties = dict(node)
                    properties["name"] = name
                    converted_nodes.append({
                        "id": name,  # 用name作为ID
                        "label": label,
                        "name": name,
                        "properties": properties,
                    })

                self._memory_store["nodes"] = converted_nodes
                self._memory_store["relations"] = json_relations
                print(f"[KGService] 从init_data.json加载: {len(converted_nodes)}个节点, "
                      f"{len(json_relations)}条关系")
                loaded_from_file = True
            except Exception as e:
                print(f"[KGService] 加载init_data.json失败: {e}，回退到本体模块")

        if not loaded_from_file:
            self._memory_store["nodes"] = []
            self._memory_store["relations"] = []

        # 补齐 kg_ontology.py 中的本体节点（按 name 去重）。
        # 对 CartographicDecision 进一步按 (map_type, decision_type) 去重：
        # 若 init_data.json 已提供某地图类型的某类决策，则跳过本体中同类的决策，
        # 避免出现「英文图层名 + 中文图层名」两套并存导致的重复图层。
        try:
            from app.core.kg_ontology import ONTOLOGY_NODES, ONTOLOGY_RELATIONS

            existing_names = {n.get("name") for n in self._memory_store["nodes"]}
            covered_decisions = set()
            for n in self._memory_store["nodes"]:
                props = n.get("properties", n)
                if n.get("label") == "CartographicDecision":
                    covered_decisions.add(
                        (props.get("map_type"), props.get("decision_type"))
                    )

            added_nodes = 0
            for node in ONTOLOGY_NODES:
                name = node.get("name")
                if not name or name in existing_names:
                    continue
                if node.get("label") == "CartographicDecision":
                    key = (node.get("map_type"), node.get("decision_type"))
                    if key in covered_decisions:
                        continue
                    covered_decisions.add(key)

                node = dict(node)
                label = node.pop("label", "")
                properties = dict(node)
                properties["name"] = name
                self._memory_store["nodes"].append({
                    "id": name,
                    "label": label,
                    "name": name,
                    "properties": properties,
                })
                existing_names.add(name)
                added_nodes += 1

            rel_keys = {
                (r.get("from"), r.get("to"), r.get("type"))
                for r in self._memory_store["relations"]
            }
            added_rels = 0
            for rel in ONTOLOGY_RELATIONS:
                key = (rel.get("from"), rel.get("to"), rel.get("type"))
                if key not in rel_keys:
                    self._memory_store["relations"].append(rel)
                    rel_keys.add(key)
                    added_rels += 1

            print(f"[KGService] 内存知识库已初始化: {len(self._memory_store['nodes'])}个节点, "
                  f"{len(self._memory_store['relations'])}条关系"
                  f"（补充本体节点{added_nodes}个/关系{added_rels}条）")
        except ImportError:
            print("[KGService] 本体模块未加载，使用已加载数据")

    def _get_memory_graph_data(self, limit: int) -> Dict[str, List[dict]]:
        """获取内存模式的图谱数据

        从已加载的init_data.json节点和关系构建D3.js格式的图谱数据。
        
        Args:
            limit: 最多返回节点数

        Returns:
            D3.js格式的图谱数据
        """
        all_nodes = self._memory_store.get("nodes", [])
        all_relations = self._memory_store.get("relations", [])
        
        nodes = []
        links = []
        node_name_set = set()
        
        # 添加已加载的节点（限制数量）
        for node in all_nodes[:limit]:
            node_id = node.get("id", node.get("name", ""))
            if node_id in node_name_set:
                continue
            node_name_set.add(node_id)
            nodes.append({
                "id": node_id,
                "label": node.get("label", "Unknown"),
                "name": node.get("name", node.get("properties", {}).get("name", "未命名")),
                "properties": node.get("properties", {}),
            })
        
        # 构建关系链接（仅包含已添加节点之间的关系）
        for rel in all_relations:
            source_name = rel.get("from", rel.get("source", ""))
            target_name = rel.get("to", rel.get("target", ""))
            if source_name in node_name_set and target_name in node_name_set:
                links.append({
                    "source": source_name,
                    "target": target_name,
                    "type": rel.get("type", "RELATED"),
                })
        
        # 如果没有加载到任何节点，回退到内置城市和地标
        if not nodes:
            for i, (city_name, bbox) in enumerate(CITY_BBOX.items()):
                if len(nodes) >= limit:
                    break
                node_id = f"city_{i}"
                nodes.append({
                    "id": node_id,
                    "label": "City",
                    "name": city_name,
                    "properties": {
                        "center_lat": bbox["center_lat"],
                        "center_lon": bbox["center_lon"],
                    },
                })
            
            city_node_id = "city_0"
            for i, landmark in enumerate(WUHAN_LANDMARKS):
                if len(nodes) >= limit:
                    break
                node_id = f"landmark_{i}"
                nodes.append({
                    "id": node_id,
                    "label": "Landmark",
                    "name": landmark["name"],
                    "properties": {
                        "lat": landmark["lat"],
                        "lng": landmark["lng"],
                        "type": landmark["type"],
                    },
                })
                links.append({
                    "source": city_node_id,
                    "target": node_id,
                    "type": "HAS_LANDMARK",
                })
        
        return {"nodes": nodes, "links": links}

    def close(self):
        """关闭Neo4j连接"""
        if self.driver is not None:
            self.driver.close()
            print("[KGService] Neo4j连接已关闭")
