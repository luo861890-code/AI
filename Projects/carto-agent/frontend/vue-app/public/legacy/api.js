/**
 * API请求封装模块
 * 封装所有与后端的HTTP请求，统一处理错误、超时、重试
 * 所有方法返回Promise，异步操作使用async/await
 */

const API = {
    /**
     * 通用请求方法
     * @param {string} method - HTTP方法 GET/POST/PUT/DELETE
     * @param {string} url - 请求路径（不含baseUrl）
     * @param {object|null} data - 请求数据（GET时作为query参数）
     * @returns {Promise<object>} 响应JSON数据
     */
    async request(method, url, data = null) {
        const fullUrl = CONFIG.apiBaseUrl + url;
        const options = {
            method: method,
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            // 包含凭证（如果需要）
            credentials: "omit"
        };

        // GET请求将data作为query参数
        if (method === "GET" && data) {
            const params = new URLSearchParams(data).toString();
            const separator = fullUrl.includes("?") ? "&" : "?";
            options.url = fullUrl + separator + params;
        } else if (data) {
            options.body = JSON.stringify(data);
        }

        const requestUrl = options.url || fullUrl;

        // 使用AbortController实现超时控制
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.requestTimeout);
        options.signal = controller.signal;

        try {
            const response = await fetch(requestUrl, options);
            clearTimeout(timeoutId);

            // 检查HTTP状态码
            if (!response.ok) {
                const errorText = await response.text();
                let errorMsg;
                try {
                    const errorJson = JSON.parse(errorText);
                    errorMsg = errorJson.detail || errorJson.message || `请求失败 (${response.status})`;
                } catch (e) {
                    errorMsg = `请求失败 (${response.status}): ${errorText.substring(0, 200)}`;
                }
                throw new Error(errorMsg);
            }

            // 解析JSON响应
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return await response.json();
            } else {
                // 非JSON响应（如文件下载）
                return await response.blob();
            }
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === "AbortError") {
                throw new Error("请求超时，请检查网络连接或后端服务是否正常运行");
            }
            if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
                throw new Error("无法连接到后端服务，请确认服务已启动在 " + CONFIG.apiBaseUrl);
            }
            throw error;
        }
    },

    // ========== 会话管理 ==========

    /**
     * 创建新会话
     * @param {string} title - 会话标题
     * @returns {Promise<object>} 会话信息 {session_id, title, created_at}
     */
    async createSession(title = "新会话") {
        return await this.request("POST", "/api/chat/sessions", { title });
    },

    /**
     * 获取会话列表
     * @returns {Promise<array>} 会话列表
     */
    async listSessions() {
        return await this.request("GET", "/api/chat/sessions");
    },

    /**
     * 获取会话详情（含消息历史）
     * @param {string} sessionId - 会话ID
     * @returns {Promise<object>} 会话详情
     */
    async getSession(sessionId) {
        return await this.request("GET", `/api/chat/sessions/${sessionId}`);
    },

    /**
     * 删除会话
     * @param {string} sessionId - 会话ID
     * @returns {Promise<object>} 删除结果
     */
    async deleteSession(sessionId) {
        return await this.request("DELETE", `/api/chat/sessions/${sessionId}`);
    },

    /**
     * 发送消息到会话
     * @param {string} sessionId - 会话ID
     * @param {string} message - 消息内容
     * @returns {Promise<object>} 响应 {success, response, map_data, steps, thinking, provider, model}
     */
    async sendMessage(sessionId, message) {
        return await this.request("POST", `/api/chat/sessions/${sessionId}/messages`, { message });
    },

    /**
     * 流式发送消息（SSE）
     * 使用fetch + ReadableStream读取Server-Sent Events，实现LLM输出实时推送。
     *
     * @param {string} sessionId - 会话ID
     * @param {string} message - 消息内容
     * @param {object} callbacks - 回调函数集合
     *   - onThinking(text): 收到思考过程
     *   - onChunk(text): 收到文本块（增量）
     *   - onMap(mapData): 收到地图数据
     *   - onSteps(steps): 收到执行步骤
     *   - onRag(sources): 收到RAG知识来源
     *   - onGraphrag(data): 收到GraphRAG实体信息
     *   - onGeotoken(info): 收到GeoToken信息
     *   - onKnowledgeSources(sources): 收到知识来源（问答场景）
     *   - onDone(data): 流式完成 {provider, model}
     *   - onError(msg): 错误
     * @returns {Promise<void>}
     */
    async streamMessage(sessionId, message, callbacks = {}) {
        const fullUrl = CONFIG.apiBaseUrl + `/api/chat/sessions/${sessionId}/stream`;

        const response = await fetch(fullUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            body: JSON.stringify({ message }),
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`流式请求失败 (${response.status}): ${errText.substring(0, 200)}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // 按SSE协议解析：以 \n\n 分隔事件
                const events = buffer.split("\n\n");
                buffer = events.pop(); // 最后一段可能不完整，保留在buffer中

                for (const eventStr of events) {
                    const line = eventStr.trim();
                    if (!line.startsWith("data:")) continue;

                    const jsonStr = line.substring(5).trim();
                    if (!jsonStr) continue;

                    try {
                        const data = JSON.parse(jsonStr);
                        switch (data.type) {
                            case "thinking":
                                if (callbacks.onThinking) callbacks.onThinking(data.content || "");
                                break;
                            case "chunk":
                                if (callbacks.onChunk) callbacks.onChunk(data.content || "");
                                break;
                            case "map":
                                if (callbacks.onMap) callbacks.onMap(data.content);
                                break;
                            case "steps":
                                if (callbacks.onSteps) callbacks.onSteps(data.content || []);
                                break;
                            case "rag":
                                if (callbacks.onRag) callbacks.onRag(data.content || []);
                                break;
                            case "graphrag":
                                if (callbacks.onGraphrag) callbacks.onGraphrag(data.content || {});
                                break;
                            case "geotoken":
                                if (callbacks.onGeotoken) callbacks.onGeotoken(data.content || {});
                                break;
                            case "knowledge_sources":
                                if (callbacks.onKnowledgeSources) callbacks.onKnowledgeSources(data.content || {});
                                break;
                            case "done":
                                if (callbacks.onDone) callbacks.onDone(data);
                                break;
                            case "error":
                                if (callbacks.onError) callbacks.onError(data.content || "未知错误");
                                break;
                        }
                    } catch (e) {
                        console.warn("SSE事件解析失败:", e, jsonStr.substring(0, 100));
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    },

    /**
     * 获取会话历史消息
     * @param {string} sessionId - 会话ID
     * @returns {Promise<array>} 消息列表
     */
    async getMessages(sessionId) {
        return await this.request("GET", `/api/chat/sessions/${sessionId}/messages`);
    },

    // ========== 地图管理 ==========

    /**
     * 生成地图
     * @param {object} params - {map_type, region, center, zoom, layers}
     * @returns {Promise<object>} 地图数据
     */
    async generateMap(params) {
        return await this.request("POST", "/api/maps/generate", params);
    },

    /**
     * 获取地图列表
     * @returns {Promise<array>} 地图列表
     */
    async listMaps() {
        return await this.request("GET", "/api/maps");
    },

    /**
     * 获取单个地图详情
     * @param {string} mapId - 地图ID
     * @returns {Promise<object>} 地图数据
     */
    async getMap(mapId) {
        return await this.request("GET", `/api/maps/${mapId}`);
    },

    /**
     * 删除地图
     * @param {string} mapId - 地图ID
     * @returns {Promise<object>} 删除结果
     */
    async deleteMap(mapId) {
        return await this.request("DELETE", `/api/maps/${mapId}`);
    },

    /**
     * 添加图层
     * @param {string} mapId - 地图ID
     * @param {object} params - {layer_type, name, query}
     * @returns {Promise<object>} 添加结果
     */
    async addLayer(mapId, params) {
        return await this.request("POST", `/api/maps/${mapId}/layers`, params);
    },

    /**
     * 删除图层
     * @param {string} mapId - 地图ID
     * @param {string} layerId - 图层ID
     * @returns {Promise<object>} 删除结果
     */
    async removeLayer(mapId, layerId) {
        return await this.request("DELETE", `/api/maps/${mapId}/layers/${layerId}`);
    },

    /**
     * 更新图层样式
     * @param {string} mapId - 地图ID
     * @param {string} layerId - 图层ID
     * @param {object} style - {color, weight, opacity, fillOpacity, dashArray}
     * @returns {Promise<object>} 更新结果
     */
    async updateLayerStyle(mapId, layerId, style) {
        return await this.request("PUT", `/api/maps/${mapId}/layers/${layerId}`, style);
    },

    /**
     * 设置图层可见性（持久化隐藏/显示）
     * @param {string} mapId - 地图ID
     * @param {string} layerId - 图层ID
     * @param {boolean} visible - 是否可见
     */
    async setLayerVisible(mapId, layerId, visible) {
        return await this.request("PUT", `/api/maps/${mapId}/layers/${layerId}/visible`, { visible });
    },

    /**
     * 编辑模式：整层替换几何/属性（QGIS/ArcGIS 式编辑保存）
     */
    async updateLayerGeometry(mapId, layerId, payload) {
        return await this.request("PUT", `/api/maps/${mapId}/layers/${layerId}/geometry`, payload);
    },

    /**
     * 增量更新图层（PATCH）- 仅修改传入的字段，不影响其他属性
     * @param {string} mapId - 地图ID
     * @param {string} layerId - 图层ID
     * @param {object} patches - 增量更新字段 {style?: partial, visible?: bool, name?: string}
     * @returns {Promise<object>} 更新后的完整地图数据
     */
    async patchLayer(mapId, layerId, patches) {
        return await this.request("PATCH", `/api/maps/${mapId}/layers/${layerId}`, patches);
    },

    /**
     * 更新地图视图
     * @param {string} mapId - 地图ID
     * @param {object} params - {center, zoom}
     * @returns {Promise<object>} 更新结果
     */
    async updateView(mapId, params) {
        return await this.request("PUT", `/api/maps/${mapId}/view`, params);
    },

    /**
     * 更新地图主题
     * @param {string} mapId - 地图ID
     * @param {string} theme - 主题名 standard/positron/dark/satellite
     * @returns {Promise<object>} 更新结果
     */
    async updateTheme(mapId, theme) {
        return await this.request("PUT", `/api/maps/${mapId}/theme`, { theme });
    },

    /**
     * 自然语言修改地图
     * @param {string} mapId - 地图ID
     * @param {string} instruction - 修改指令
     * @returns {Promise<object>} 修改结果
     */
    async modifyMap(mapId, instruction) {
        return await this.request("POST", `/api/maps/${mapId}/modify`, { instruction });
    },

    /**
     * 导出地图
     * @param {string} mapId - 地图ID
     * @param {string} format - 导出格式 geojson/png/svg
     * @returns {Promise<object|Blob>} 导出结果
     */
    async exportMap(mapId, format) {
        return await this.request("POST", `/api/maps/${mapId}/export`, { format });
    },

    /**
     * 路径规划
     * @param {string} mapId - 地图ID
     * @param {object} params - {start, end, profile, waypoints}
     * @returns {Promise<object>} 路径规划结果
     */
    async planRoute(mapId, params) {
        return await this.request("POST", `/api/maps/${mapId}/route`, params);
    },

    // ========== 知识图谱 ==========

    /**
     * 获取知识图谱数据
     * @param {number} limit - 节点数量限制
     * @returns {Promise<object>} {nodes, links}
     */
    async getKGGraph(limit = 100) {
        return await this.request("GET", `/api/kg/graph?limit=${limit}`);
    },

    /**
     * 知识图谱问答
     * @param {string} question - 问题
     * @returns {Promise<object>} 问答结果
     */
    async kgQuery(question) {
        return await this.request("POST", "/api/kg/query", { question });
    },

    /**
     * 导入文档到知识图谱
     * @param {string} content - 文档内容
     * @param {array|null} entityLabels - 实体标签列表
     * @returns {Promise<object>} 导入结果
     */
    async importDocument(content, entityLabels = null) {
        const params = { content };
        if (entityLabels) params.entity_labels = entityLabels;
        return await this.request("POST", "/api/kg/import", params);
    },

    /**
     * 初始化知识图谱基础数据
     * @returns {Promise<object>} 初始化结果
     */
    async initKnowledge() {
        return await this.request("POST", "/api/kg/init");
    },

    // ========== 系统设置 ==========

    /**
     * 获取LLM提供者列表
     * @returns {Promise<object>} 提供者列表及当前选择
     */
    async getProviders() {
        return await this.request("GET", "/api/settings/llm/providers");
    },

    /**
     * 切换LLM提供者
     * @param {string} provider - 提供者名称
     * @param {string} model - 模型名称
     * @returns {Promise<object>} 切换结果
     */
    async switchProvider(provider, model) {
        return await this.request("PUT", "/api/settings/llm/provider", { provider, model });
    },

    /**
     * 更新指定LLM提供者的API Key
     * @param {string} provider - 提供者名称 deepseek/qwen/openai/zhipu
     * @param {string} apiKey - API密钥
     * @returns {Promise<object>} 更新结果
     */
    async updateApiKey(provider, apiKey) {
        return await this.request("PUT", "/api/settings/llm/apikey", { provider, api_key: apiKey });
    },

    /**
     * 获取地图主题列表
     * @returns {Promise<object>} 主题列表
     */
    async getThemes() {
        return await this.request("GET", "/api/settings/map/themes");
    }
};
