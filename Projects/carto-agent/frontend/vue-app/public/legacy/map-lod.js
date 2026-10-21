/**
 * 载负量（LOD）分级控制（MapPanel.prototype 扩展）
 *
 * 模块职责：
 *  - _lodVisible：按比例尺分级显隐图层（概览/市域/城区/街区/详图五档）
 *  - _applyLoadControl：大图层按比例尺预算“按重要性保留”要素——
 *    保留命名、长距离主干路与大湖等完整要素，优先丢弃小碎块，
 *    避免把连续道路打散成点/断线。
 *  - refreshLabels / _symbolZoomFactor：缩放联动重渲染与符号缩放
 *
 * 依赖：map.js（本模块方法通过 prototype 挂载到 MapPanel）
 */

/**
 * 载负量控制：按“重要性”保留前 N 个完整要素
 *
 * 重要性打分（依据制图综合理论）：
 *  - 命名要素 +1000；线/面按点数 + 几何长度加权（干流/长路优先）；
 *  - 道路网「断头路优先舍去」：两端不与其他路连通的孤立/支岔路段重罚；
 *  - 密度对比：邻域要素多的密集区多删、稀疏区少删（保持区域密度差异）；
 *  - 水系长度下限：中比例尺下过短的支流碎段直接剔除。
 * 保留 top-N 完整要素；边界/政区/底图/行政中心/注记/大型湖泊不抽稀。
 */
MapPanel.prototype._applyLoadControl = function(layerData, zoom) {
    if (this.editMode) return layerData;   // 编辑模式必须全量，避免保存丢要素
    const t = layerData.type;
    const name = layerData.name || "";
    if (t !== "polyline" && t !== "polygon" && t !== "circleMarker") return layerData;
    // 关键图层不抽稀：边界/政区/底图/行政中心/注记/湖泊档位（已按比例尺选取并设载负量上限）
    if (/边界|界$|政区|底图|行政中心|注记|标注|省域|周边地市|湖泊（|湖泊点符号/.test(name)) return layerData;
    const budget = zoom < 9 ? 300 : zoom < 11 ? 800 : zoom < 13 ? 2500 : zoom < 15 ? 7000 : Infinity;
    const coords = layerData.coordinates;
    const feats = layerData.features;
    const props = layerData.properties;
    const items = coords ? coords : feats;
    const count = items ? items.length : 0;
    if (!count || count <= budget) return layerData;

    const isRoad = name.indexOf("道路-") === 0;
    const isStream = name === "支流溪流";
    // 水系综合：中比例尺下支流按长度下限选取（去掉过短碎段）
    const MIN_LEN = (isStream && zoom < 15) ? 0.003 : 0;   // ~330m

    const lineLen = (c) => {
        if (!Array.isArray(c) || !Array.isArray(c[0])) return 0;
        let len = 0;
        for (let k = 1; k < c.length; k++) {
            const a = c[k - 1];
            const b = c[k];
            if (Array.isArray(a) && Array.isArray(b)) {
                len += Math.hypot(b[0] - a[0], b[1] - a[1]);
            }
        }
        return len;
    };
    const midOf = (c) => {
        if (Array.isArray(c) && Array.isArray(c[0])) {
            const p = c[Math.floor(c.length / 2)];
            return [p[0], p[1]];
        }
        return Array.isArray(c) ? [c[0], c[1]] : [0, 0];
    };

    // 密度网格（约 2.2km 格网，3x3 邻域统计局部密度）
    const CELL = 0.02;
    const grid = new Map();
    const lengths = new Array(count).fill(0);
    const cellKey = new Array(count);
    for (let i = 0; i < count; i++) {
        const c = coords ? coords[i] : (feats ? feats[i].coordinates : null);
        lengths[i] = lineLen(c);
        const m = midOf(c);
        cellKey[i] = Math.round(m[0] / CELL) + "," + Math.round(m[1] / CELL);
        grid.set(cellKey[i], (grid.get(cellKey[i]) || 0) + 1);
    }

    // 道路网连通性：端点被共享次数（判断断头/支岔）
    const epCount = new Map();
    if (isRoad) {
        for (let i = 0; i < count; i++) {
            const c = coords ? coords[i] : (feats ? feats[i].coordinates : null);
            if (!Array.isArray(c) || !Array.isArray(c[0]) || c.length < 2) continue;
            for (const e of [c[0], c[c.length - 1]]) {
                const k = Math.round(e[0] * 1000) + "," + Math.round(e[1] * 1000);
                epCount.set(k, (epCount.get(k) || 0) + 1);
            }
        }
    }

    // 计算每个要素的重要性分数
    const scored = [];
    for (let i = 0; i < count; i++) {
        const c = coords ? coords[i] : (feats ? feats[i].coordinates : null);
        // 长度下限（水系）
        if (MIN_LEN > 0 && lengths[i] < MIN_LEN) {
            scored.push({ idx: i, score: -1e9 });
            continue;
        }
        let score = 0;
        const prop = props ? props[i] : null;
        if (prop && prop.name) score += 1000;                    // 命名要素优先
        if (Array.isArray(c)) {
            if (Array.isArray(c[0])) {                           // 线/面要素
                score += c.length;                               // 点数（≈ 长度/面积）
                score += Math.round(lengths[i] * 2000);          // 几何长度/周长
            } else {
                score += 5;                                      // 点要素
            }
        }
        // 断头路惩罚：孤立端点越多越优先舍去（无贯通作用的死路）
        if (isRoad && Array.isArray(c) && Array.isArray(c[0]) && c.length >= 2) {
            let lonely = 0;
            for (const e of [c[0], c[c.length - 1]]) {
                const k = Math.round(e[0] * 1000) + "," + Math.round(e[1] * 1000);
                if ((epCount.get(k) || 0) <= 1) lonely += 1;
            }
            score -= lonely * 2500;
        }
        // 密度对比惩罚：密集区多删、稀疏区少删（保持区域密度差异）
        const [cx, cy] = cellKey[i].split(",").map(Number);
        let dens = 0;
        for (let dx = -1; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                dens += grid.get((cx + dx) + "," + (cy + dy)) || 0;
            }
        }
        score -= dens * 15;
        scored.push({ idx: i, score });
    }
    // 按重要性降序保留前 budget 个，其余（小碎块）剔除
    scored.sort((a, b) => b.score - a.score);
    const keep = new Set(scored.slice(0, budget).map((x) => x.idx));

    const copy = Object.assign({}, layerData);
    if (coords) {
        copy.coordinates = coords.filter((_, i) => keep.has(i));
        if (props && props.length === coords.length) {
            copy.properties = props.filter((_, i) => keep.has(i));
        }
    } else if (feats) {
        copy.features = feats.filter((_, i) => keep.has(i));
    }
    return copy;
};

/**
 * 图层显隐 LOD（载负量规划）：
 *   z<9   概览级：高速主干道 + 大型湖泊 + 政区边界 + 行政中心
 *   z9-10 市域级：+主干道/区县名
 *   z11-12 城区级：+主要河流/中型湖泊/次干道/地标/水系注记/轨道
 *   z13-14 街区级：+支流/小型湖泊/三级道路/POI
 *   z>=15 详图级：全量（支路/建筑/全部POI）
 */
MapPanel.prototype._lodVisible = function(layerData, zoom) {
    const _z = zoom;
    const _nm = layerData.name || "";
    const t = layerData.type;
    // ---- 道路分级：0高速 1主干 2一级 3二级 4三级 5支路 ----
    if (t === "polyline" && (_nm.indexOf("道路-") === 0 || /高速|国道|主干道|省道|次干道|支路|社区道路|服务道路|其他道路|三级道路/.test(_nm))) {
        const _order = ["motorway", "trunk", "primary", "secondary", "tertiary",
                        "residential", "service", "living_street", "unclassified", "other"];
        let level = 5;
        // 优先使用后端标注的道路等级（metadata.raw_class），与 Vue 前端 roadLevel 一致，
        // 兼容 carto-agent 已迁移为中文名的道路图层（否则中文名会全部 fallback 到 5，破坏分级）
        const raw = layerData.metadata && layerData.metadata.raw_class;
        if (raw) {
            const _base = raw.replace(/_link$/, "");
            level = _order.indexOf(_base);
            if (level < 0) level = 5;
            // 连接线（匝道）降一级显示，避免小比例尺匝道噪音
            if (raw.indexOf("_link") > 0) level = Math.min(5, level + 1);
        } else if (_nm.indexOf("道路-") === 0) {
            const _l = _nm.replace("道路-", "").split("_")[0];
            level = _order.indexOf(_l);
            if (level < 0) {
                // 中文道路名映射（无 raw_class 兜底，与 Vue 前端保持一致）
                if (/高速公路|高速互通/.test(_nm)) level = 0;
                else if (/城市干线主干道|主干道连接|主干道衔接/.test(_nm)) level = 1;
                else if (/城市主干道/.test(_nm)) level = 2;
                else if (/城市次干道|次干道连接/.test(_nm)) level = 3;
                else if (/三级道路/.test(_nm)) level = 4;
                else level = 5;
            } else {
                // 连接线（匝道）降一级显示，避免小比例尺匝道噪音
                if (_l.indexOf("_link") > 0) level = Math.min(5, level + 1);
            }
        } else if (/高速公路/.test(_nm)) level = 0;
        else if (/国道|主干道/.test(_nm)) level = 1;
        else if (/省道|主要道路/.test(_nm)) level = 2;
        else if (/次干道/.test(_nm)) level = 3;
        else if (/三级道路/.test(_nm)) level = 4;
        let maxShow = 5;
        if (_z < 9) maxShow = 0;
        else if (_z < 11) maxShow = 1;
        else if (_z < 13) maxShow = 3;
        else if (_z < 15) maxShow = 4;
        return level <= maxShow;
    }
    // ---- 水系 ----
    if (t === "polyline") {
        // 单线河（双线河→单线河过渡）：小比例尺即显示主要中心线
        if (_nm === "河流中心线（主要）") return _z >= 9;
        if (_nm === "河流中心线（支流）") return _z >= 12;
        // 等高线LOD：计曲线(100m)概览级可见，首曲线(20m)城区级才显示，避免小比例尺载负过重
        if (_nm === "等高线（计曲线）") return _z >= 9;
        if (_nm === "等高线（首曲线）") return _z >= 11;
        if (_nm === "支流溪流" || /河源细流/.test(_nm)) return _z >= 13;
        if (_nm === "主要河流") return _z >= 11;
        return true;   // 大江大河
    }
    if (t === "polygon") {
        // 河流水面（双线河）：城区级以上才显示，概览级由单线河中心线表达
        if (_nm === "河流水面") return _z >= 11;
        // 居民地街区分级（制图综合·选取）：大建成区市域级可见，中小街区大比例尺显示
        if (_nm === "集中居民地（大型）") return _z >= 11;
        if (_nm === "集中居民地（中型）") return _z >= 13;
        if (_nm === "集中居民地（小型）") return _z >= 15;
        // 湖泊多尺度表达（面状水体制图综合）：各比例尺档位互斥切换，
        // 小比例尺只看大湖/点符号，大比例尺逐步显示小湖，控制载负量
        if (_nm === "湖泊（概览级）" || _nm === "湖泊点符号（概览）") return _z >= 6 && _z < 9;
        if (_nm === "湖泊（市域级）") return _z >= 9 && _z < 11;
        if (_nm === "湖泊（城区级）") return _z >= 11 && _z < 13;
        if (_nm === "湖泊（详图级）") return _z >= 13;
        if (/住宅|公寓|宿舍|商业|零售|酒店|工业|公共|政府|学校|大学|医院|宗教|文化|体育|停车|车库|仓储|交通枢纽|农业|温室/.test(_nm)) return _z >= 13;
        if (/绿地|公园|森林|草地|草甸|用地/.test(_nm)) return _z >= 11;
        return true;   // 政区面/底图/边界始终显示
    }
    // ---- 轨道交通 ----
    if (t === "polyline" && _nm === "轨道交通线路") return _z >= 9;
    if (t === "circleMarker" && _nm === "轨道交通站点") return _z >= 12;
    // ---- 注记 ----
    if (t === "textLabel") {
        if (_nm === "水系注记") return _z >= 12;
        if (_nm === "区县名称标注") return _z >= 9;
        if (_nm === "地标名称" || _nm === "重点地标") return _z >= 11;
        return true;
    }
    // ---- POI/符号 ----
    if (t === "circleMarker") {
        if (_nm === "湖泊点符号（概览）") return _z >= 6 && _z < 9;
        if (_nm === "市级行政中心" || _nm === "区县行政中心" || _nm === "乡镇居民点") return _z >= 8;
        if (_nm === "重点地标") return _z >= 11;
        return _z >= 12;   // 普通POI 城区级才显示
    }
    return true;
};

/**
 * 刷新所有注记图层（缩放级别变化时重渲染，使字号随比例尺自适应）
 */
MapPanel.prototype.refreshLabels = function() {
    if (!this.layerGroups) return;
    // 重置注记去重与避让状态，避免重渲染后标签被跳过
    this._labelPlaced = [];
    this._labelNames = new Set();
    Object.entries(this.layerGroups).forEach(([id, item]) => {
        if (!item.data) return;
        const t = item.data.type;
        // 点符号/注记随比例尺改变大小，缩放时重渲染
        if (t === "textLabel" || t === "circleMarker" || t === "marker" || t === "point") {
            this.map.removeLayer(item.layer);
            this.renderLayer(item.data);
        } else if (t === "polyline" || t === "polygon") {
            // 路网/水系/建筑/绿地LOD：可见性或保留数量变化时重建
            const show = this._lodVisible(item.data, this.map.getZoom());
            const next = this._applyLoadControl(item.data, this.map.getZoom());
            const nextCount = (next.coordinates || next.features || []).length;
            if (show !== item.data._lodVisible || nextCount !== item.data._lodCount) {
                this.map.removeLayer(item.layer);
                this.renderLayer(item.data);
            }
        }
    });
};

/** 符号缩放系数：随比例尺放大而放大（clamp 0.7~2.5） */
MapPanel.prototype._symbolZoomFactor = function() {
    const z = this.map ? this.map.getZoom() : 12;
    return Math.min(2.5, Math.max(0.7, Math.pow(1.08, z - 12)));
};
