/**
 * 编辑模式（QGIS/ArcGIS 式矢量编辑，MapPanel.prototype 扩展）
 *
 * 模块职责：
 *  - 编辑会话开关与状态栏标识
 *  - 点/线/面绘制、节点拖拽编辑、要素复制/删除/简化
 *  - 属性编辑、坐标画点
 *  - 撤销/重做（快照机制）与保存回写后端
 *  - leaflet-editable 初始化
 *
 * 依赖：map.js（本模块方法通过 prototype 挂载到 MapPanel）
 */

    /**
     * 初始化 leaflet-editable（几何编辑能力）
     */
MapPanel.prototype._initEditable = function() {
        if (!window.L || !L.Editable) return;
        try {
            if (!this.map.editTools) {
                this.map.editTools = new L.Editable(this.map);
                // 顶点编辑事件统一标记图层为“已修改”
                this.map.on("editable:vertex:dragend editable:vertex:deleted editable:vertex:new",
                    (e) => {
                        const lid = e && e.layer ? e.layer._cartoLayerId : null;
                        if (lid) this._markDirty(lid);
                    });
                // 开始编辑/节点拖动前拍快照（供撤销）
                this.map.on("editable:editing:start editable:vertex:dragstart",
                    (e) => {
                        const lid = e && e.layer ? e.layer._cartoLayerId : null;
                        if (lid) this._pushUndoSnapshot(lid);
                    });
            }
        } catch (e) {
            console.warn("[MapPanel] leaflet-editable 初始化失败:", e);
        }
};

    // ==================== 编辑模式（QGIS/ArcGIS 式几何编辑） ====================
MapPanel.prototype.toggleEditMode = function() {
        if (this.editMode) this.exitEditMode();
        else this.enterEditMode();
};

MapPanel.prototype.enterEditMode = function() {
        if (!this.currentMapId) {
            Utils.showToast("请先生成或打开一张地图", "warning");
            return;
        }
        if (this.editMode) return;
        this.editMode = true;
        this._editDirty = {};       // layerId -> true
        this._undoStack = {};
        this._redoStack = {};
        this._currentEdit = null;   // {layerId, idx, layer}
        this._tempEditLayer = null;
        // 立即弹出编辑面板，保证按钮响应；重渲染异步执行避免卡顿
        const panel = document.getElementById("map-edit-panel");
        if (panel) panel.classList.remove("hidden");
        const btn = document.getElementById("toolbar-edit");
        if (btn) btn.classList.add("active");
        this.map.getContainer().style.cursor = "crosshair";
        this._updateEditStatus();
        try { this._attachAllEditMetadata(); } catch (e) { console.warn("[Edit] 挂载编辑元数据失败:", e); }
        // 编辑模式需全量要素（去除抽稀）：异步执行，任何图层失败不影响其余
        setTimeout(() => {
            try { this._rerenderAllLayers(); } catch (e) { console.warn("[Edit] 全量重渲染失败:", e); }
        }, 0);
        Utils.showToast("编辑模式已开启：点击要素进入编辑，或使用工具栏绘制", "info", 2200);
};

MapPanel.prototype.exitEditMode = function() {
        this._clearEditSelection();
        this.editMode = false;
        this._editDirty = {};
        // 退出编辑后恢复比例尺分级渲染（抽稀）
        this._rerenderAllLayers();
        const panel = document.getElementById("map-edit-panel");
        if (panel) panel.classList.add("hidden");
        const btn = document.getElementById("toolbar-edit");
        if (btn) btn.classList.remove("active");
        this.map.getContainer().style.cursor = "";
        this._updateEditStatus();
};

MapPanel.prototype.initEditPanel = function() {
        const panel = document.getElementById("map-edit-panel");
        if (!panel || this._editPanelBound) return;
        this._editPanelBound = true;
        const qs = (id) => document.getElementById(id);
        if (panel.querySelector(".edit-panel-close")) {
            panel.querySelector(".edit-panel-close").addEventListener("click", () => this.exitEditMode());
        }
        if (qs("edit-exit-btn")) qs("edit-exit-btn").addEventListener("click", () => this.exitEditMode());
        if (qs("edit-save-btn")) qs("edit-save-btn").addEventListener("click", () => this.saveEdits());
        if (qs("edit-delete-feature")) qs("edit-delete-feature").addEventListener("click", () => this.deleteSelectedFeature());
        panel.querySelectorAll("[data-edit-draw]").forEach((btn) => {
            btn.addEventListener("click", () => this.startDraw(btn.getAttribute("data-edit-draw")));
        });
        if (qs("edit-undo-btn")) qs("edit-undo-btn").addEventListener("click", () => this.undoEdit());
        if (qs("edit-redo-btn")) qs("edit-redo-btn").addEventListener("click", () => this.redoEdit());
        if (qs("edit-copy-btn")) qs("edit-copy-btn").addEventListener("click", () => this.copySelectedFeature());
        if (qs("edit-simplify-btn")) qs("edit-simplify-btn").addEventListener("click", () => this.simplifySelectedFeature());
        if (qs("edit-coord-add")) qs("edit-coord-add").addEventListener("click", () => this.addPointByCoord());
        const attrName = qs("edit-attr-name");
        if (attrName) {
            attrName.addEventListener("change", () => {
                if (!this._currentEdit) return;
                this._updateSelectedAttr({ name: attrName.value.trim() });
            });
        }
        // 键盘快捷键：Ctrl+Z 撤销 / Ctrl+Y 重做（仅编辑模式）
        document.addEventListener("keydown", (e) => {
            if (!this.editMode) return;
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
                e.preventDefault();
                this.undoEdit();
            } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
                e.preventDefault();
                this.redoEdit();
            }
        });
};

    // ---------- 撤销 / 重做（编辑快照机制） ----------
MapPanel.prototype._pushUndoSnapshot = function(layerId) {
        const item = this.layerGroups[layerId];
        if (!item || !item.data) return;
        // 先把 Leaflet 中的最新几何同步回数据，快照才能捕捉节点编辑结果
        const payload = this._buildLayerPayload(item);
        if (payload) {
            if (payload.coordinates) item.data.coordinates = payload.coordinates;
            if (payload.features) item.data.features = payload.features;
        }
        // 合并 1.2s 内的连续微调，避免一次拖拽产生大量快照
        const now = Date.now();
        if (this._lastSnapTime && this._lastSnapTime[layerId] && now - this._lastSnapTime[layerId] < 1200) return;
        this._lastSnapTime = this._lastSnapTime || {};
        this._lastSnapTime[layerId] = now;
        this._undoStack = this._undoStack || {};
        this._redoStack = this._redoStack || {};
        if (!this._undoStack[layerId]) this._undoStack[layerId] = [];
        const snap = JSON.parse(JSON.stringify(item.data));
        this._undoStack[layerId].push(snap);
        if (this._undoStack[layerId].length > 50) this._undoStack[layerId].shift();
        this._redoStack[layerId] = [];
};

MapPanel.prototype._currentEditLayerId = function() {
        return this._currentEdit ? this._currentEdit.layerId : null;
};

MapPanel.prototype._applyLayerSnapshot = function(layerId, snapshot) {
        const item = this.layerGroups[layerId];
        if (!item || !snapshot) return;
        Object.keys(snapshot).forEach((k) => { item.data[k] = snapshot[k]; });
        if (this.currentMapData) {
            const src = (this.currentMapData.layers || []).find((l) => l.id === layerId);
            if (src) Object.keys(snapshot).forEach((k) => { src[k] = snapshot[k]; });
        }
        this._currentEdit = null;   // 图层重建后原选中失效
        this._markDirty(layerId);
        this.rerenderLayer(layerId);
        this._updateEditStatus();
};

MapPanel.prototype.undoEdit = function() {
        const layerId = this._currentEditLayerId() || Object.keys(this._undoStack || {})[0];
        if (!layerId) { Utils.showToast("没有可撤销的操作", "info", 1500); return; }
        const stack = this._undoStack[layerId];
        if (!stack || stack.length === 0) { Utils.showToast("没有可撤销的操作", "info", 1500); return; }
        // 同步当前 Leaflet 几何后再入重做栈
        const item = this.layerGroups[layerId];
        const curPayload = item ? this._buildLayerPayload(item) : null;
        const cur = JSON.parse(JSON.stringify(item ? item.data : {}));
        if (curPayload) {
            if (curPayload.coordinates) cur.coordinates = curPayload.coordinates;
            if (curPayload.features) cur.features = curPayload.features;
        }
        this._redoStack[layerId] = this._redoStack[layerId] || [];
        this._redoStack[layerId].push(cur);
        const target = stack.pop();
        this._applyLayerSnapshot(layerId, target);
        Utils.showToast("已撤销", "info", 1200);
};

MapPanel.prototype.redoEdit = function() {
        const layerId = this._currentEditLayerId() || Object.keys(this._redoStack || {})[0];
        if (!layerId) { Utils.showToast("没有可重做的操作", "info", 1500); return; }
        const stack = this._redoStack[layerId];
        if (!stack || stack.length === 0) { Utils.showToast("没有可重做的操作", "info", 1500); return; }
        const item = this.layerGroups[layerId];
        const curPayload = item ? this._buildLayerPayload(item) : null;
        const cur = JSON.parse(JSON.stringify(item ? item.data : {}));
        if (curPayload) {
            if (curPayload.coordinates) cur.coordinates = curPayload.coordinates;
            if (curPayload.features) cur.features = curPayload.features;
        }
        this._undoStack[layerId] = this._undoStack[layerId] || [];
        this._undoStack[layerId].push(cur);
        const target = stack.pop();
        this._applyLayerSnapshot(layerId, target);
        Utils.showToast("已重做", "info", 1200);
};

    // ---------- 属性编辑 ----------
MapPanel.prototype._selectedProps = function() {
        if (!this._currentEdit) return null;
        const item = this.layerGroups[this._currentEdit.layerId];
        if (!item || !item.data) return null;
        const idx = this._currentEdit.idx;
        if (Array.isArray(item.data.features) && item.data.features[idx]) {
            if (!item.data.features[idx].properties) item.data.features[idx].properties = {};
            return item.data.features[idx].properties;
        }
        if (!Array.isArray(item.data.properties)) item.data.properties = [];
        if (!item.data.properties[idx]) item.data.properties[idx] = {};
        return item.data.properties[idx];
};

MapPanel.prototype._updateEditAttrInput = function() {
        const input = document.getElementById("edit-attr-name");
        if (!input) return;
        const props = this._selectedProps();
        if (!props) { input.value = ""; input.disabled = true; return; }
        input.value = props.name || "";
        input.disabled = false;
};

MapPanel.prototype._updateSelectedAttr = function(patches) {
        const props = this._selectedProps();
        if (!props) return;
        Object.assign(props, patches);
        this._markDirty(this._currentEdit.layerId);
        this._updateEditStatus();
};

    // ---------- 复制 / 简化 / 坐标画点 ----------
MapPanel.prototype.copySelectedFeature = function() {
        if (!this._currentEdit) { Utils.showToast("请先点击选中要复制的要素", "warning"); return; }
        const { layerId, idx } = this._currentEdit;
        const item = this.layerGroups[layerId];
        if (!item) return;
        const data = item.data;
        this._pushUndoSnapshot(layerId);
        const offset = (arr) => {
            if (Array.isArray(arr[0])) arr.forEach(p => { p[0] += 0.002; p[1] += 0.002; });
            else { arr[0] += 0.002; arr[1] += 0.002; }
        };
        if (Array.isArray(data.coordinates) && data.coordinates[idx]) {
            const copy = JSON.parse(JSON.stringify(data.coordinates[idx]));
            offset(copy);
            data.coordinates.push(copy);
            if (Array.isArray(data.properties)) {
                data.properties.push(JSON.parse(JSON.stringify(data.properties[idx] || {})));
            }
        } else if (Array.isArray(data.features) && data.features[idx]) {
            const copy = JSON.parse(JSON.stringify(data.features[idx]));
            if (copy.coordinates) offset(copy.coordinates);
            data.features.push(copy);
        } else {
            Utils.showToast("该图层不支持复制", "warning");
            return;
        }
        this._markDirty(layerId);
        this.rerenderLayer(layerId);
        Utils.showToast("已复制要素（记得保存）", "success", 1600);
};

MapPanel.prototype.simplifySelectedFeature = function() {
        if (!this._currentEdit) { Utils.showToast("请先点击选中要简化的要素", "warning"); return; }
        const { layerId, idx } = this._currentEdit;
        const item = this.layerGroups[layerId];
        if (!item) return;
        const data = item.data;
        let coords = null;
        if (Array.isArray(data.coordinates) && data.coordinates[idx]) coords = data.coordinates[idx];
        else if (Array.isArray(data.features) && data.features[idx]) coords = data.features[idx].coordinates;
        if (!Array.isArray(coords) || coords.length < 5) {
            Utils.showToast("当前要素节点太少，无需简化", "info", 1600);
            return;
        }
        this._pushUndoSnapshot(layerId);
        const simp = this._douglasPeucker(coords, 0.0004);   // ~45m 容差
        if (Array.isArray(data.coordinates)) data.coordinates[idx] = simp;
        else if (Array.isArray(data.features)) data.features[idx].coordinates = simp;
        this._markDirty(layerId);
        this.rerenderLayer(layerId);
        Utils.showToast(`已简化：${coords.length} → ${simp.length} 个节点`, "success", 1800);
};

MapPanel.prototype._douglasPeucker = function(points, eps) {
        if (!Array.isArray(points) || points.length <= 2) return points.map(p => p.slice());
        const first = points[0];
        const last = points[points.length - 1];
        let maxD = 0;
        let idx = 0;
        for (let i = 1; i < points.length - 1; i++) {
            const d = this._pointLineDist(points[i], first, last);
            if (d > maxD) { maxD = d; idx = i; }
        }
        if (maxD > eps) {
            const left = this._douglasPeucker(points.slice(0, idx + 1), eps);
            const right = this._douglasPeucker(points.slice(idx), eps);
            return left.slice(0, -1).concat(right);
        }
        return [first.slice(), last.slice()];
};

MapPanel.prototype._pointLineDist = function(p, a, b) {
        const x = p[0], y = p[1], x1 = a[0], y1 = a[1], x2 = b[0], y2 = b[1];
        const dx = x2 - x1, dy = y2 - y1;
        if (dx === 0 && dy === 0) return Math.hypot(x - x1, y - y1);
        return Math.abs(dy * x - dx * y + x2 * y1 - y2 * x1) / Math.hypot(dx, dy);
};

MapPanel.prototype.addPointByCoord = function() {
        const input = document.getElementById("edit-coord-input");
        if (!input) return;
        const raw = input.value.trim();
        const m = raw.match(/^(-?\d+(?:\.\d+)?)\s*[,，\s]\s*(-?\d+(?:\.\d+)?)$/);
        if (!m) { Utils.showToast("坐标格式：lat,lng（如 30.5928,114.3055）", "warning"); return; }
        const lat = parseFloat(m[1]);
        const lng = parseFloat(m[2]);
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) { Utils.showToast("坐标超出范围", "warning"); return; }
        const candidate = Object.entries(this.layerGroups).find(([, item]) => {
            const t = item.data.type;
            return t === "circleMarker" || t === "marker";
        });
        if (!candidate) { Utils.showToast("没有点状图层可添加", "warning"); return; }
        const [layerId, item] = candidate;
        this._pushUndoSnapshot(layerId);
        item.data.coordinates.push([lat, lng]);
        if (Array.isArray(item.data.properties)) item.data.properties.push({ name: "坐标标注" });
        this._markDirty(layerId);
        this.rerenderLayer(layerId);
        input.value = "";
        Utils.showToast("已按坐标添加点（记得保存）", "success", 1600);
};

MapPanel.prototype._updateEditStatus = function() {
        const el = document.getElementById("edit-status");
        const statusEl = document.getElementById("map-status-edit");
        if (!this.editMode) {
            if (el) el.textContent = "";
            if (statusEl) { statusEl.textContent = "未编辑"; statusEl.classList.remove("editing"); }
            return;
        }
        let txt;
        let sessionTxt = "编辑中";
        if (this._currentEdit) {
            const item = this.layerGroups[this._currentEdit.layerId];
            const name = item ? (item.data.name || "图层") : "图层";
            txt = `正在编辑：${name} · 第 ${this._currentEdit.idx + 1} 个要素`;
            sessionTxt = `编辑中·图层：${name}`;
        } else {
            txt = "未选择要素（点击地图上的要素进入编辑）";
        }
        if (el) el.textContent = txt;
        if (statusEl) { statusEl.textContent = sessionTxt; statusEl.classList.add("editing"); }
};

    /**
     * 给已渲染要素挂载编辑元数据与点击事件（幂等）
     */
MapPanel.prototype._attachEditMetadata = function(layerId, layer) {
        if (!layer) return;
        const setType = (l) => {
            if (l instanceof L.Polygon) l._cartoGeomType = "polygon";
            else if (l instanceof L.Polyline) l._cartoGeomType = "polyline";
            else if (l instanceof L.CircleMarker || l instanceof L.Marker) l._cartoGeomType = "point";
            else l._cartoGeomType = "polyline";
        };
        const attach = (l, idx) => {
            if (!l || typeof l.on !== "function" || l._cartoLayerId) return;
            l._cartoLayerId = layerId;
            l._cartoFeatureIdx = idx;
            setType(l);
            l.on("click", (e) => {
                if (this.editMode) {
                    L.DomEvent.stopPropagation(e);
                    this._selectEditFeature(layerId, idx, l);
                }
            });
        };
        if (layer.eachLayer) {
            let idx = 0;
            layer.eachLayer((l) => { attach(l, idx); idx += 1; });
        } else if (layer._layers) {
            let idx = 0;
            Object.values(layer._layers).forEach((l) => { attach(l, idx); idx += 1; });
        } else {
            attach(layer, 0);
        }
};

MapPanel.prototype._attachAllEditMetadata = function() {
        Object.entries(this.layerGroups).forEach(([layerId, item]) => {
            try { this._attachEditMetadata(layerId, item.layer); }
            catch (e) { console.warn("[Edit] 图层元数据挂载失败:", layerId, e); }
        });
};

MapPanel.prototype._selectEditFeature = function(layerId, idx, leafletLayer) {
        this._clearEditSelection();
        this._currentEdit = { layerId, idx, layer: leafletLayer };
        // 高亮
        if (leafletLayer.setStyle) {
            leafletLayer.setStyle({ color: "#ff6b00", weight: 4, opacity: 1 });
        }
        if (leafletLayer.bringToFront) leafletLayer.bringToFront();
        // 编辑前拍快照（供撤销）
        this._pushUndoSnapshot(layerId);
        this._updateEditAttrInput();
        // 启用几何编辑
        try {
            if (leafletLayer instanceof L.Polyline || leafletLayer instanceof L.Polygon) {
                if (!this.map.editTools || !L.Editable) {
                    Utils.showToast("几何编辑组件未加载（网络问题），仅支持拖动点要素", "warning", 3000);
                } else if (!leafletLayer.editEnabled()) {
                    leafletLayer.enableEdit();
                }
            } else if (leafletLayer instanceof L.Marker) {
                leafletLayer.dragging.enable();
                leafletLayer.on("dragstart", () => this._pushUndoSnapshot(layerId));
            } else if (leafletLayer instanceof L.CircleMarker) {
                // circleMarker 不可拖动：临时替换为可拖动 marker，拖动时同步回原要素
                const latlng = leafletLayer.getLatLng();
                if (this._tempEditLayer) this.map.removeLayer(this._tempEditLayer);
                this._tempEditLayer = L.marker(latlng, { draggable: true }).addTo(this.map);
                this._tempEditLayer.on("dragstart", () => this._pushUndoSnapshot(layerId));
                this._tempEditLayer.on("dragend", () => {
                    const ll = this._tempEditLayer.getLatLng();
                    if (this._currentEdit && this._currentEdit.layer.setLatLng) {
                        this._currentEdit.layer.setLatLng(ll);
                    }
                    this._markDirty(layerId);
                });
            }
        } catch (e) {
            console.warn("[Edit] 启用编辑失败:", e);
        }
        this._updateEditStatus();
};

MapPanel.prototype._clearEditSelection = function() {
        if (this._currentEdit) {
            const l = this._currentEdit.layer;
            const item = this.layerGroups[this._currentEdit.layerId];
            const st = item ? (item.data.style || {}) : {};
            if (l && l.setStyle) {
                try {
                    l.setStyle({
                        color: st.color || "#3388ff",
                        weight: st.weight || 3,
                        opacity: st.opacity !== undefined ? st.opacity : 1
                    });
                } catch (e) { /* ignore */ }
            }
            if (l && l.editEnabled && l.editEnabled()) {
                try { l.disableEdit(); } catch (e) { /* ignore */ }
            }
        }
        if (this._tempEditLayer) {
            this.map.removeLayer(this._tempEditLayer);
            this._tempEditLayer = null;
        }
        this._currentEdit = null;
        this._updateEditStatus();
        const attrInput = document.getElementById("edit-attr-name");
        if (attrInput) { attrInput.value = ""; attrInput.disabled = true; }
};

MapPanel.prototype._markDirty = function(layerId) {
        if (layerId) this._editDirty[layerId] = true;
};

    /**
     * 绘制新要素（点/线/面），完成后追加到当前选中图层
     */
MapPanel.prototype.startDraw = function(type) {
        if (!this.editMode) { Utils.showToast("请先开启编辑模式", "warning"); return; }
        if (!this.map.editTools) {
            Utils.showToast("绘图组件未加载（需联网加载 leaflet-editable）", "error");
            return;
        }
        let handler = null;
        try {
            if (type === "point") handler = this.map.editTools.startMarker();
            else if (type === "line") handler = this.map.editTools.startPolyline();
            else if (type === "polygon") handler = this.map.editTools.startPolygon();
        } catch (e) {
            Utils.showToast("开始绘制失败: " + e.message, "error");
            return;
        }
        Utils.showToast(type === "point" ? "点击地图放置点" : "在地图上绘制（双击结束）", "info", 2000);
        if (handler) handler.on("editable:created", (e) => this._onDrawn(type, e.layer));
};

MapPanel.prototype._onDrawn = function(type, layer) {
        let targetLayerId = this._currentEdit ? this._currentEdit.layerId : null;
        if (!targetLayerId) {
            const candidate = Object.entries(this.layerGroups).find(([, item]) => {
                const t = item.data.type;
                return t === "polyline" || t === "polygon" || t === "circleMarker" || t === "marker";
            });
            if (candidate) targetLayerId = candidate[0];
        }
        if (!targetLayerId) {
            Utils.showToast("没有可追加的图层，请先点击选中一个要素", "warning");
            this.map.removeLayer(layer);
            return;
        }
        const item = this.layerGroups[targetLayerId];
        if (!item) { this.map.removeLayer(layer); return; }
        const data = item.data;
        const geom = this._leafletGeomToData(type, layer);
        if (!geom) {
            Utils.showToast("绘制数据解析失败", "error");
            this.map.removeLayer(layer);
            return;
        }
        if (!Array.isArray(data.coordinates)) data.coordinates = [];
        if (!Array.isArray(data.properties)) data.properties = [];
        this._pushUndoSnapshot(targetLayerId);
        const label = type === "point" ? "新建点要素" : (type === "line" ? "新建线要素" : "新建面要素");
        data.coordinates.push(geom);
        data.properties.push({ name: label });
        this._markDirty(targetLayerId);
        this.rerenderLayer(targetLayerId);
        Utils.showToast("已添加要素（记得保存）", "success", 1800);
};

MapPanel.prototype.deleteSelectedFeature = function() {
        if (!this._currentEdit) {
            Utils.showToast("请先点击选中要删除的要素", "warning");
            return;
        }
        const { layerId, idx, layer } = this._currentEdit;
        const item = this.layerGroups[layerId];
        if (!item) { this._clearEditSelection(); return; }
        try {
            if (layer.editEnabled && layer.editEnabled()) layer.disableEdit();
            if (item.layer.eachLayer) item.layer.removeLayer(layer);
            else this.map.removeLayer(layer);
        } catch (e) { /* ignore */ }
        const data = item.data;
        this._pushUndoSnapshot(layerId);
        if (Array.isArray(data.coordinates)) data.coordinates.splice(idx, 1);
        if (Array.isArray(data.properties)) data.properties.splice(idx, 1);
        if (Array.isArray(data.features)) data.features.splice(idx, 1);
        this._markDirty(layerId);
        this._currentEdit = null;
        this.rerenderLayer(layerId);
        Utils.showToast("已删除要素（记得保存）", "success", 1800);
        this._updateEditStatus();
};

MapPanel.prototype.rerenderLayer = function(layerId) {
        const old = this.layerGroups[layerId];
        if (old && old.layer) this.map.removeLayer(old.layer);
        delete this.layerGroups[layerId];
        if (!this.currentMapData) return;
        const data = (this.currentMapData.layers || []).find((l) => l.id === layerId);
        if (data) {
            this.renderLayer(data);
            // 重渲染后重新挂载编辑元数据（否则新要素无法点击选中/编辑）
            if (this.editMode) {
                const item = this.layerGroups[layerId];
                if (item) this._attachEditMetadata(layerId, item.layer);
            }
        }
};

MapPanel.prototype._rerenderAllLayers = function() {
        if (!this.currentMapData) return;
        Object.keys(this.layerGroups).forEach((layerId) => {
            try {
                const item = this.layerGroups[layerId];
                if (item && item.layer) this.map.removeLayer(item.layer);
                delete this.layerGroups[layerId];
            } catch (e) { /* ignore */ }
        });
        (this.currentMapData.layers || []).forEach((data) => {
            try { this.renderLayer(data); }
            catch (e) { console.warn("[Edit] 图层重渲染失败:", data && data.name, e); }
        });
        if (this.editMode) {
            // 全量重渲染后统一挂载编辑元数据
            Object.keys(this.layerGroups).forEach((layerId) => {
                const item = this.layerGroups[layerId];
                if (item) this._attachEditMetadata(layerId, item.layer);
            });
        }
};

MapPanel.prototype._leafletChildren = function(layer) {
        const out = [];
        if (layer && layer.eachLayer) layer.eachLayer((l) => out.push(l));
        else if (layer && layer._layers) Object.values(layer._layers).forEach((l) => out.push(l));
        else if (layer) out.push(layer);
        return out;
};

    /**
     * 将 Leaflet 几何转换为系统坐标数据
     * point/marker/circleMarker -> [lat,lng]；line/polyline -> [[lat,lng],...]；polygon -> 环 [[lat,lng],...]
     */
MapPanel.prototype._leafletGeomToData = function(type, layer) {
        try {
            if (type === "point" || type === "marker" || type === "circleMarker") {
                const ll = layer.getLatLng ? layer.getLatLng() : null;
                return ll ? [ll.lat, ll.lng] : null;
            }
            if (type === "line" || type === "polyline") {
                const ls = layer.getLatLngs();
                if (Array.isArray(ls) && ls.length && Array.isArray(ls[0])) {
                    return ls[0].map((p) => [p.lat, p.lng]);
                }
                return (ls || []).map((p) => [p.lat, p.lng]);
            }
            if (type === "polygon") {
                const rings = layer.getLatLngs();
                const ring = (Array.isArray(rings) && rings.length && Array.isArray(rings[0])) ? rings[0] : rings;
                return (ring || []).map((p) => [p.lat, p.lng]);
            }
        } catch (e) {
            console.warn("[Edit] 几何解析失败:", e);
        }
        return null;
};

MapPanel.prototype._buildLayerPayload = function(item) {
        const data = item.data;
        if (data.type === "textLabel") return null;  // 注记暂不支持几何编辑
        const payload = { properties: data.properties, style: data.style };
        const children = this._leafletChildren(item.layer);
        if (Array.isArray(data.features) && data.features.length > 0) {
            // features 型图层：逐要素重建坐标
            const feats = JSON.parse(JSON.stringify(data.features));
            children.forEach((child, idx) => {
                const f = feats[idx];
                if (!f) return;
                const gtype = f.type === "polygon" ? "polygon" : (f.type === "point" ? "point" : "polyline");
                const geom = this._leafletGeomToData(gtype, child);
                if (geom) f.coordinates = geom;
            });
            payload.features = feats;
            return payload;
        }
        // coordinates 型图层
        const coords = [];
        children.forEach((child) => {
            const gtype = child._cartoGeomType || data.type;
            const c = this._leafletGeomToData(gtype, child);
            if (c) coords.push(c);
        });
        payload.coordinates = coords;
        return payload;
};

/**
 * 保存所有修改：重建图层几何并回写后端，成功后重新拉取地图
 */
MapPanel.prototype.saveEdits = async function() {
    if (!this.currentMapId) { Utils.showToast("没有可保存的地图", "warning"); return; }
    const dirtyIds = Object.keys(this._editDirty || {});
    if (dirtyIds.length === 0) {
        Utils.showToast("没有需要保存的修改", "info", 1800);
        return;
    }
    Utils.showToast("正在保存...", "info", 1500);
    let ok = 0;
    for (const layerId of dirtyIds) {
        const item = this.layerGroups[layerId];
        if (!item) continue;
        const payload = this._buildLayerPayload(item);
        if (!payload) continue;
        try {
            const resp = await API.updateLayerGeometry(this.currentMapId, layerId, payload);
            if (resp.success) {
                ok += 1;
                delete this._editDirty[layerId];
            } else {
                Utils.showToast("保存失败: " + (resp.message || ""), "error");
            }
        } catch (e) {
            Utils.showToast("保存失败: " + e.message, "error");
        }
    }
    if (ok > 0) {
        try {
            const resp = await API.getMap(this.currentMapId);
            if (resp.success && resp.data) this.renderMap(resp.data);
        } catch (e) { /* ignore */ }
        Utils.showToast(`已保存 ${ok} 个图层的修改`, "success");
    }
};
