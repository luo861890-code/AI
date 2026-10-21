/**
 * 地图面板核心逻辑（MapPanel 类）
 *
 * 模块职责：
 *  - Leaflet 地图实例初始化 / 视图与主题管理
 *  - 地图数据渲染（renderMap / renderLayer）
 *  - 图层面板 / 图例 / 样式编辑器 / 元数据 / 质量检测
 *  - 比例尺 / 经纬网 / 路线规划 / 导出 / 状态栏
 *
 * 依赖加载顺序：map.js -> map-lod.js -> map-edit.js -> app.js
 * （lod/edit 通过 MapPanel.prototype 扩展本类方法）
 */


class MapPanel {
    /**
     * 构造函数
     * @param {object} app - 主应用实例
     */
    constructor(app) {
        this.app = app;
        this.map = null;                    // Leaflet地图实例
        this.currentTheme = "plain";        // 当前底图主题（默认无瓦片制图底图）
        this.tileLayer = null;              // 当前瓦片图层
        this.currentMapData = null;         // 当前地图数据
        this.currentMapId = null;           // 当前地图ID
        this.layerGroups = {};              // 图层组 {layer_id: {layer: LeafletLayer, data: layerData, visible: bool}}
        this._layerOrder = [];              // 图层面板显示顺序（用户可调整）
        this._lockedGroups = {};            // 锁定分组的排序（防止误拖乱高等级道路层级）
        this.layerControl = null;           // Leaflet图层控制器
        this.routeLayer = null;             // 路径规划线图层
        this.routeMarkers = [];             // 路径规划标记（起点、终点）
        this.routePointMode = null;         // 路径选点模式: null / "start" / "end"
        this.selectedProfile = "driving";   // 当前选择的出行方式
        this.isModifying = false;           // 修改请求防重复标志
        this.legendControl = null;          // 图例控件(兼容)
        this.legendData = null;             // 图例数据
        this.legendActiveGroup = "全部";   // 图例当前分组
        this.legendSearch = "";           // 图例搜索关键词
        this._labelPlaced = [];           // 全局注记避让（跨图层共享，防重复堆叠）
        this.markerMode = false;          // 标注模式（点击地图添加自定义标注）
        this.elements = {};
    }

    /**
     * 初始化地图
     * @param {string} containerId - 地图容器DOM ID
     */
    /** 构建地图投影 CRS（Web墨卡托默认；高斯-克吕格/等距圆柱用proj4leaflet） */
    _buildCRS(crsKey) {
        if (crsKey === "GaussKruger" && window.L && window.L.Proj) {
            // CGCS2000 高斯-克吕格 3°分带（中央经线114°E），武汉范围
            const projDef = "+proj=tmerc +lat_0=0 +lon_0=114 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs";
            const resolutions = [];
            let _r = 60000;
            for (let i = 0; i < 20; i++) { resolutions.push(_r); _r /= 2; }
            return new L.Proj.CRS("EPSG:4523", projDef, {
                resolutions: resolutions,
                origin: [200000, 3600000],
                bounds: L.bounds([200000, 3000000], [800000, 3600000])
            });
        }
        if (crsKey === "Equirect") return L.CRS.EPSG4326;
        return null;   // Web墨卡托：Leaflet默认
    }

    initMap(containerId = "map-container", crsKey = "WebMercator") {
        // 创建Leaflet地图实例（支持自定义投影CRS）
        const _crs = this._buildCRS(crsKey);
        const opts = {
            center: CONFIG.defaultMapCenter,
            zoom: CONFIG.defaultZoom,
            zoomControl: false,             // 禁用默认缩放控件，使用自定义工具栏
            zoomSnap: 0.05,                 // 0.05级缩放：自定义比例尺跳转误差<1%
            preferCanvas: true,             // Canvas渲染：大路网/水系统量渲染不卡顿
            attributionControl: true
        };
        if (_crs) opts.crs = _crs;
        this.map = L.map(containerId, opts);
        this.mapCrsKey = crsKey;
        this.tileLayer = null;
        const _projSel = document.getElementById("map-proj-select");
        if (_projSel) _projSel.value = crsKey;
        // 非墨卡托投影：关闭在线瓦片底图（在线瓦片为Web墨卡托，其他投影下无法对齐）
        if (crsKey === "WebMercator") {
            this.setTheme(this.currentTheme || "standard");
        } else {
            this.setTheme("plain");
        }
        if (this._uiBound) {
            // 重建地图：仅重建核心控件与底图，UI事件不重复绑定
            L.control.zoom({ position: "bottomright" }).addTo(this.map);
            this.initScaleControl();
            this.bindEvents();
            this.initGraticule();
            this._initEditable();
            this.updateStatusBar();
            return;
        }
        this._uiBound = true;
        // 添加缩放控件到右下角
        L.control.zoom({ position: "bottomright" }).addTo(this.map);
        // 添加标准分段比例尺（黑白分段、km/m标注）
        this.currentMapType = null;
        this.initScaleControl();
        // 自定义比例尺输入（工具栏）
        this._initScaleSetter();
        // 投影切换
        this._initProjSetter();
        // 绑定事件
        this.bindEvents();
        // 初始化工具栏
        this.initToolbar();
        // 初始化图层管理面板
        this.initLayerPanel();
        // 初始化编制说明弹窗（独立按钮）
        this.initMetadataModal();
        // 初始化任务参数侧边栏
        this.initParamsPanel();
        // 初始化图例按钮与面板
        this.initLegendPanel();
        // 初始化自然语言修改输入框
        this.initModifyInput();
        // 初始化路径规划面板
        this.initRoutePanel();
        // 标准制图整饰：经纬网与经纬度注记
        this.initGraticule();
        // 自定义标注工具（答辩演示：标注赏樱点/卫生间）
        this.initMarkerTool();
        // 编辑模式（QGIS/ArcGIS 式几何编辑）
        this._initEditable();
        this.initEditPanel();
        // 更新状态栏
        this.updateStatusBar();
    }

    /** 初始化投影切换下拉 */
    _initProjSetter() {
        const sel = document.getElementById("map-proj-select");
        if (!sel) return;
        sel.addEventListener("change", () => {
            const key = sel.value;
            const names = { WebMercator: "Web墨卡托", GaussKruger: "高斯-克吕格CGCS2000", Equirect: "等距圆柱" };
            if (key === this.mapCrsKey) return;
            this._switchProjection(key);
            Utils.showToast("已切换投影：" + (names[key] || key), "info", 2000);
        });
    }

    /** 切换投影：重建Leaflet地图并重新渲染当前数据（非墨卡托关闭瓦片底图） */
    _switchProjection(crsKey) {
        const data = this.currentMapData;
        const center = this.map.getCenter();
        const zoom = this.map.getZoom();
        // 清理旧地图与图层状态
        try { this.map.remove(); } catch (e) {}
        this.map = null;
        this.tileLayer = null;
        this.layerGroups = {};
        this._labelPlaced = [];
        this._labelNames = new Set();
        this._poiMarkers = [];
        this.graticuleGroup = null;
        this.graticuleLabelGroup = null;
        // 重建地图（新投影）
        this.initMap("map-container", crsKey);
        // 重新渲染当前地图数据并恢复视图
        if (data) {
            this.renderMap(data);
            if (center) this.map.setView([center.lat, center.lng], zoom);
        }
    }

    /** 当前投影名称 */
    _crsName() {
        if (this.mapCrsKey === "GaussKruger") return "高斯-克吕格 CGCS2000 3°分带 (EPSG:4523)";
        if (this.mapCrsKey === "Equirect") return "等距圆柱 (EPSG:4326)";
        return "Web墨卡托 (EPSG:3857)";
    }

    /**
     * 绑定地图事件
     */
    bindEvents() {
        // 地图移动/缩放时更新状态栏
        this.map.on("moveend zoomend", () => {
            this.updateStatusBar();
        });
        // 地图点击时显示坐标或设置路径起终点
        this.map.on("click", (e) => {
            const lat = e.latlng.lat.toFixed(4);
            const lng = e.latlng.lng.toFixed(4);
            // 如果在路径选点模式，设置起终点
            if (this.routePointMode) {
                this.setRoutePoint(this.routePointMode, [e.latlng.lat, e.latlng.lng]);
                this.routePointMode = null;
                this.map.getContainer().style.cursor = "";
            } else if (this.markerMode) {
                // 标注模式：点击地图添加自定义标注点
                this.addCustomMarker(e.latlng.lat, e.latlng.lng);
            } else {
                this.updateStatusBar(lat, lng);
            }
        });
    }

    /**
     * 初始化顶部工具栏
     */
    initToolbar() {
        // 主题切换下拉
        const themeSelect = document.getElementById("map-theme-select");
        if (themeSelect) {
            // 填充主题选项
            themeSelect.innerHTML = "";
            Object.entries(CONFIG.mapThemes).forEach(([key, theme]) => {
                const option = document.createElement("option");
                option.value = key;
                option.textContent = theme.name;
                if (key === this.currentTheme) option.selected = true;
                themeSelect.appendChild(option);
            });
            themeSelect.addEventListener("change", (e) => {
                this.setTheme(e.target.value);
            });
        }
        // 其他工具栏按钮由右侧工具栏触发，在app.js中绑定
    }

    /**
     * 设置底图主题
     * @param {string} theme - 主题名 standard/positron/dark/satellite
     */
    setTheme(theme) {
        const themeConfig = CONFIG.mapThemes[theme];
        if (!themeConfig) {
            Utils.showToast("未知主题: " + theme, "warning");
            return;
        }
        // 移除旧底图
        if (this.tileLayer) {
            this.map.removeLayer(this.tileLayer);
        }
        // 添加新底图（制图底图"plain"无瓦片，关闭第三方底图）
        if (themeConfig.url) {
            this.tileLayer = L.tileLayer(themeConfig.url, {
                attribution: themeConfig.attribution,
                maxZoom: themeConfig.maxZoom,
                subdomains: themeConfig.subdomains || "abc"
            }).addTo(this.map);
            // 瓦片加载失败（网络/被墙）时自动回退到高德矢量底图（国内可直连）
            if (theme !== "amap_normal" && theme !== "tianditu_vec" && theme !== "tianditu_img") {
                let _errCount = 0;
                this.tileLayer.on("tileerror", () => {
                    _errCount += 1;
                    if (_errCount >= 8 && this.currentTheme === theme) {
                        _errCount = 9999;
                        Utils.showToast("当前底图加载失败，已自动切换高德矢量底图", "info");
                        this.setTheme("amap_normal");
                    }
                });
            }
        } else {
            this.tileLayer = null;
        }
        this.currentTheme = theme;
        // 更新下拉选择
        const themeSelect = document.getElementById("map-theme-select");
        if (themeSelect) themeSelect.value = theme;
        // 如果有当前地图，通知后端更新主题
        if (this.currentMapId) {
            API.updateTheme(this.currentMapId, theme).catch(err => {
                console.warn("更新主题到后端失败:", err);
            });
        }
        this.updateStatusBar();
    }

    /**
     * 循环切换底图主题
     */
    cycleTheme() {
        const themes = Object.keys(CONFIG.mapThemes);
        const currentIndex = themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % themes.length;
        this.setTheme(themes[nextIndex]);
        Utils.showToast(`底图: ${CONFIG.mapThemes[themes[nextIndex]].name}`, "info", 1500);
    }

    /**
     * 行政区划图图幅自动取景：适配"武汉全域+周边相邻地市"（规范九-5）
     * 独立成方法，便于 Vue 集成在容器尺寸就绪后再次强制取景，
     * 规避流式渲染过程中容器 0 尺寸导致 fitBounds 失效的问题。
     */
    _fitAdministrativeBounds(mapData) {
        if (!mapData || mapData.map_type !== "administrative" || !this.map) return;
        const bounds = L.latLngBounds([]);
        // 递归收集任意嵌套深度的 [lat, lng] 坐标点，统一扩展进 bounds
        const collect = (c) => {
            if (!Array.isArray(c)) return;
            if (c.length >= 2 && typeof c[0] === "number" && !isNaN(c[0]) && !isNaN(c[1])) {
                bounds.extend([c[0], c[1]]);
            } else {
                c.forEach(collect);
            }
        };
        // 汇总面/线/点/注记图层的坐标（含 features 形式的面状区县数据）
        (mapData.layers || []).forEach(ld => {
            const t = ld.type || "";
            if (t === "polygon" || t === "polyline" || t === "circleMarker" || t === "textLabel" || t === "line") {
                if (ld.coordinates) collect(ld.coordinates);
                if (ld.features && Array.isArray(ld.features)) {
                    ld.features.forEach(f => { if (f.coordinates) collect(f.coordinates); });
                }
            }
        });
        if (bounds.isValid()) {
            // maxZoom 限制：避免过度放大导致周边地市丢失；padding 保证图廓内完整
            this.map.fitBounds(bounds, { padding: [12, 12], maxZoom: 10.5 });
        }
    }

    /**
     * 渲染后端返回的地图数据
     * @param {object} mapData - 地图数据 {map_id, name, center, zoom, theme, layers}
     */
    renderMap(mapData) {
        if (!mapData || !this.map) return;
        // 会话快照自愈：若图层数据是旧版（英文道路名/缺分类），自动拉取后端最新数据
        // （会话消息里持久化的 map_data 不会随后端迁移自动更新）
        if (mapData.map_id && !this._refreshingMap) {
            const stale = (mapData.layers || []).some((l) =>
                /^道路-[a-z_]+$/.test(l.name || "") || !l.group);
            if (stale) {
                this._refreshingMap = mapData.map_id;
                API.getMap(mapData.map_id).then((resp) => {
                    this._refreshingMap = null;
                    if (resp && resp.success && resp.data && resp.data.layers
                        && resp.data.map_id === mapData.map_id) {
                        this.renderMap(resp.data);
                    } else {
                        // 快照对应的地图已被删除：自动加载第一张有效地图
                        this._loadFirstAvailableMap();
                    }
                }).catch(() => {
                    this._refreshingMap = null;
                    this._loadFirstAvailableMap();
                });
            }
        }
        // 切换/刷新地图时退出编辑模式
        if (this.editMode) this.exitEditMode();
        this.currentMapData = mapData;
        this.currentMapId = mapData.map_id;
        // 清除旧图层
        this.clearAllLayers();
        // 重置全局注记避让、名称去重与符号碰撞位置
        this._labelPlaced = [];
        this._labelNames = new Set();
        this._poiMarkers = [];
        this._poiMarkers = [];
        // 更新地图视图（校验center坐标完整性，防止null/undefined导致Leaflet崩溃）
        const center = mapData.center;
        if (center && Array.isArray(center) && center.length === 2
            && center[0] != null && center[1] != null
            && !isNaN(parseFloat(center[0])) && !isNaN(parseFloat(center[1]))) {
            const zoom = mapData.zoom || CONFIG.defaultZoom;
            this.map.setView([parseFloat(center[0]), parseFloat(center[1])], zoom);
        } else {
            // center缺失或无效时使用默认中心
            console.warn("[MapPanel] 地图center坐标缺失或无效，使用默认中心:", center);
            this.map.setView(CONFIG.defaultMapCenter, CONFIG.defaultZoom);
        }
        // 记录当前地图类型：必须在渲染图层之前设置，供 LOD 层级控制与样式兜底判断
        this.currentMapType = mapData.map_type;
        // 更新主题（行政区划图忽略旧数据的"plain"无瓦片主题；非墨卡托投影保持无瓦片）
        if (this.mapCrsKey === "WebMercator"
            && mapData.theme && mapData.theme !== this.currentTheme
            && !(mapData.map_type === "administrative" && mapData.theme === "plain")) {
            this.setTheme(mapData.theme);
        }
        // 渲染所有图层（先按制图叠置顺序排序：面状底图→建筑→水系→铁路→道路→点状符号）
        if (mapData.layers && Array.isArray(mapData.layers)) {
            const roadRank = {
                "高速公路": 90, "国道": 80, "主干道": 80, "省道": 70, "主要道路": 70,
                "次干道": 60, "支路": 50, "社区道路": 40, "服务道路": 30, "其他道路": 20
            };
            const layerZ = (ld) => {
                const t = ld.type || "";
                const n = ld.name || "";
                if (t === "polygon" || t === "area") {
                    if (/陆地/.test(n)) return 0;
                    // 水体面（湖泊/水库）渲染在政区/用地色块之上，覆盖陆地填充
                    if (/水体|湖泊|水库/.test(n)) return 150;
                    if (/用地|绿地|公园|花园|森林|草地|草甸|土地|政区|区划/.test(n)) return 100;
                    if (/建筑|住宅|公寓|宿舍|商业|零售|酒店|工业|公共|政府|学校|大学|医院|宗教|文化|体育|停车|车库|仓储|交通枢纽|农业|温室|居民地|街区/.test(n)) return 200;
                    return 100;
                }
                if (t === "polyline" || t === "line") {
                    // GIS叠加顺序：底图(瓦片) → 水系 → 路网 → 行政边界 → 铁路
                    if (/水系|河流|溪流|运河|湖泊|水库/.test(n)) return 330;   // 水系（底图之上）
                    if (/等高线/.test(n)) return 310;   // 等高线（底图之上、水系/道路之下）
                    // 道路按等级分层：高等级干线渲染在上层（制图规范）
                    const _cls = (ld.properties && ld.properties[0] && ld.properties[0].subtype) || "";
                    const _roadZ = {
                        "motorway": 455, "motorway_link": 452, "trunk": 450, "trunk_link": 447,
                        "primary": 444, "primary_link": 441, "secondary": 436,
                        "secondary_link": 433, "tertiary": 428, "tertiary_link": 425,
                        "residential": 418, "living_street": 415, "service": 410,
                        "unclassified": 405, "other": 400,
                    };
                    if (_roadZ[_cls]) return _roadZ[_cls];
                    const rankKey = Object.keys(roadRank).find(k => n.indexOf(k) >= 0);
                    if (rankKey || n.indexOf("道路-") === 0) return 400;   // 路网（水系之上，含本地道路数据）
                    if (/边界|市域|省界|县界/.test(n)) return 460;            // 行政边界
                    if (/铁路|地铁|轻轨|高铁/.test(n)) return 500;
                    return 300;
                }
                if (t === "textLabel" || t === "label") return 650;
                return 600;
            };
            mapData.layers.sort((a, b) => layerZ(a) - layerZ(b));
            this._layerOrder = mapData.layers.map(l => l.id);
            mapData.layers.forEach(layerData => {
                this.renderLayer(layerData);
            });
        }
        // 行政区划图（标准政区图）：矢量制图底图，湖北省域浅米/武汉市域白底，外部绝对留白
        if (mapData.map_type === "administrative") {
            this.setTheme("plain");
        }
        // 行政区划图：图幅自动适应"武汉全域+周边相邻地市"（规范九-5），
        // 避免窄屏时周边地市显示不全
        this._fitAdministrativeBounds(mapData);
        // 无 UI 模式（Vue 集成）：只保留核心做图渲染，跳过经典 JS 的 UI 面板更新
        if (this._headless) return;
        // 更新图层管理面板
        this.updateLayerPanel();
        // 更新任务参数侧边栏
        this.updateParamsPanel();
        // 编制说明（坐标系/投影/数据来源，规范3.7）
        this.renderMetadata(mapData.metadata);
        // 数据质量检测（拓扑/属性/统计/专题/标注）
        this.checkQuality();
        // 渲染图例
        if (mapData.legend) {
            this.renderLegend(mapData.legend);
        }
        // 数据质量告警提示
        if (mapData.quality && mapData.quality.warnings && mapData.quality.warnings.length) {
            mapData.quality.warnings.forEach(w => Utils.showToast(w, "warning"));
        }
        // 右下角图例（可折叠抽屉）：行政区划图显示；折叠状态由localStorage记忆（默认展开）
        const miniLegendEl = document.getElementById("map-mini-legend");
        if (miniLegendEl) miniLegendEl.classList.toggle("hidden", mapData.map_type !== "administrative");
        this._applyMiniLegendState();
        // 图名版本小字"政区版"（图名右上角，规范四）
        const verTag = document.getElementById("map-version-tag");
        if (verTag) verTag.classList.toggle("hidden", mapData.map_type !== "administrative");
        // 行政区划图：图名固定"武汉市地图"（黑体大号，图廓上方居中，无框；规范四）
        if (mapData.map_type === "administrative") {
            const nameEl = document.getElementById("map-status-name");
            if (nameEl) nameEl.textContent = "武汉市地图";
        }
        // 比例尺：独立控件统一放左下角（随缩放实时更新）
        if (this.currentMapType !== mapData.map_type && this.scaleControl) {
            this.map.removeControl(this.scaleControl);
            this.scaleControl = null;
        }
        this.currentMapType = mapData.map_type;
        if (!this.scaleControl) this.initScaleControl();
        // 审图落款（图廓底边之下，规范八：编制单位/审图号/出版日期）
        const attribution = document.getElementById("map-attribution");
        if (attribution) {
            if (mapData.map_type === "administrative") {
                attribution.innerHTML = "投影：" + this._crsName() +
                    "　编制单位：地图制图智能体 CartoAgent　审图号：鄂S(2022)100号　" +
                    "出版日期：2022-04　资料来源：DataV GeoAtlas 官方行政区划数据（民政部）";
            } else {
                attribution.innerHTML = "编制单位：地图制图智能体 CartoAgent<br>" +
                    "资料来源：官方行政区划数据（DataV/OSM）<br>" +
                    "制图时间：" + new Date().toLocaleDateString("zh-CN");
            }
            attribution.classList.remove("hidden");
        }
        // 更新状态栏
        this.updateStatusBar();
        this.updateMapInfo(mapData.name);
        Utils.showToast(`地图已加载: ${mapData.name || "未命名地图"}`, "success");
    }

    /**
     * 渲染单个图层
     * @param {object} layerData - 图层数据 {id, type, name, coordinates, style, popup}
     */
    renderHeatmap(layer) {
        if (typeof L.heatLayer === 'undefined') {
            console.warn('leaflet.heat 插件未加载，使用圆形标记替代热力图');
            const group = L.layerGroup();
            const coords = layer.coordinates || [];
            const style = layer.style || {};
            const colorScheme = style.color_scheme || ['#000004', '#320a5e', '#781c6d', '#bb3754', '#ed6925', '#fcbf49', '#fcffa4'];
            coords.forEach(pt => {
                if (pt && pt.length >= 3 && pt[0] != null && pt[1] != null) {
                    const intensity = pt[2] || 0.5;
                    const colorIdx = Math.min(Math.floor(intensity * colorScheme.length), colorScheme.length - 1);
                    L.circleMarker([pt[0], pt[1]], {
                        radius: 8 + intensity * 12,
                        fillColor: colorScheme[colorIdx],
                        color: colorScheme[colorIdx],
                        fillOpacity: intensity * 0.6,
                        weight: 0
                    }).addTo(group);
                }
            });
            return group;
        }
        const coords = (layer.coordinates || []).filter(pt => pt && pt[0] != null && pt[1] != null);
        const style = layer.style || {};
        return L.heatLayer(coords, {
            radius: style.radius || 35,
            blur: style.blur || 25,
            maxZoom: style.maxZoom || 17,
            minOpacity: style.minOpacity || 0.3,
            gradient: this._buildHeatGradient(style.color_scheme)
        });
    }

    _buildHeatGradient(colors) {
        if (!colors || !Array.isArray(colors)) return { 0.0: '#000004', 0.3: '#320a5e', 0.6: '#bb3754', 1.0: '#fcffa4' };
        const gradient = {};
        colors.forEach((color, i) => {
            gradient[i / (colors.length - 1)] = color;
        });
        return gradient;
    }

    /**
     * 水系要素成套矢量符号（统一蓝色）
     * @param {string} kind - spring/confluence/to_lake/to_sea
     * @param {string} color - 符号主色
     */
    _waterSymbolSvg(kind, color) {
        const c = color || "#0369a1";
        const light = "#e0f2fe";
        if (kind === "spring") {
            // 河源：水滴形
            return '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">' +
                '<path d="M16 4 C21 11, 26 14.5, 26 20 A10 10 0 0 1 6 20 C 6 14.5, 11 11, 16 4 Z" ' +
                'fill="' + light + '" stroke="' + c + '" stroke-width="2"/>' +
                '<path d="M16 8 C19 12.5, 22 14.8, 22 18 A6 6 0 0 1 10 18 C 10 14.8, 13 12.5, 16 8 Z" ' +
                'fill="' + c + '" opacity="0.85"/></svg>';
        }
        if (kind === "to_lake" || kind === "to_sea") {
            // 入湖口/入海口：双波浪环
            return '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">' +
                '<circle cx="16" cy="16" r="14" fill="' + light + '" stroke="' + c + '" stroke-width="2"/>' +
                '<path d="M7 13 Q9.8 10.5, 12.6 13 T 18.2 13 T 23.8 13" fill="none" stroke="' + c + '" ' +
                'stroke-width="2" stroke-linecap="round"/>' +
                '<path d="M7 19 Q9.8 16.5, 12.6 19 T 18.2 19 T 23.8 19" fill="none" stroke="' + c + '" ' +
                'stroke-width="1.5" stroke-linecap="round" opacity="0.7"/></svg>';
        }
        // 汇入口：Y形汇流符号（支流汇入主河，与水涯线在曲率最大处相交）
        return '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">' +
            '<circle cx="16" cy="16" r="14" fill="' + light + '" stroke="' + c + '" stroke-width="2"/>' +
            '<path d="M16 6 L16 16 L8.5 21.5" fill="none" stroke="' + c + '" stroke-width="2.4" ' +
            'stroke-linecap="round" stroke-linejoin="round"/>' +
            '<path d="M16 16 L23.5 21.5" fill="none" stroke="' + c + '" stroke-width="2.4" ' +
            'stroke-linecap="round" stroke-linejoin="round"/>' +
            '<circle cx="16" cy="16" r="2.6" fill="' + c + '"/></svg>';
    }

    renderLayer(layerData) {
        if (!layerData || !layerData.type) return;
        // 载负量控制：按比例尺抽稀大图层要素（编辑模式不抽稀，避免保存丢要素）
        const _renderZoom = this.map ? this.map.getZoom() : 12;
        const _origData = layerData;
        layerData = this._applyLoadControl(layerData, _renderZoom);
        layerData._lodVisible = this._lodVisible(layerData, _renderZoom);
        layerData._lodCount = (layerData.coordinates || layerData.features || []).length;
        _origData._lodCount = layerData._lodCount;
        // 校验坐标数据是否存在且非空（支持coordinates/data/features三种数据源）
        if (!layerData.coordinates && !layerData.data && !layerData.features) {
            console.warn("[MapPanel] 图层缺少坐标数据，跳过:", layerData.name || layerData.id);
            return;
        }
        const style = layerData.style || {};
        let layer = null;
        // 辅助函数：验证单个坐标点 [lat, lng] 是否有效
        const isValidPoint = (pt) => Array.isArray(pt) && pt.length >= 2
            && pt[0] != null && pt[1] != null
            && !isNaN(parseFloat(pt[0])) && !isNaN(parseFloat(pt[1]));
        // 辅助函数：过滤坐标列表中的无效点
        const filterValidCoords = (coords) => {
            if (!Array.isArray(coords)) return [];
            return coords.filter(c => {
                if (Array.isArray(c) && c.length === 2 && !Array.isArray(c[0])) {
                    return isValidPoint(c);
                } else if (Array.isArray(c) && Array.isArray(c[0])) {
                    return isValidPoint(c[0]) || c.some(p => isValidPoint(p));
                }
                return false;
            });
        };
        // 预处理：带features数组的图层（专题地图的circle/polygon类型）
        if (layerData.features && Array.isArray(layerData.features) && layerData.features.length > 0) {
            const featGroup = L.layerGroup();
            layerData.features.forEach(feat => {
                if (!feat.coordinates) return;
                const featStyle = feat.style || style;
                if (feat.type === "polygon") {
                    const coords = filterValidCoords(
                        Array.isArray(feat.coordinates[0]) ? feat.coordinates : [feat.coordinates]
                    );
                    if (coords.length > 0) {
                        // 行政区划图：面完全透明（兜底旧地图数据），露出瓦片底图
                        let fColor = featStyle.color || "#3388ff";
                        let fFill = featStyle.fillColor || featStyle.color || "#3388ff";
                        let fWeight = featStyle.weight || 1;
                        let fOpac = featStyle.opacity !== undefined ? featStyle.opacity : 0.5;
                        let fFillOpac = featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.4;
                        if (this.currentMapType === "administrative") {
                            fFillOpac = 0.2; fWeight = 0; fFill = "#f0f4f8";  // 极浅纹理：露出底图且不空心
                        }
                        const poly = L.polygon(coords, {
                            color: fColor, fillColor: fFill, weight: fWeight,
                            opacity: fOpac, fillOpacity: fFillOpac
                        });
                        // 悬浮交互：鼠标移入该区，边界高亮为红色加粗、区块微泛白，移出复原
                        if (this.currentMapType === "administrative") {
                            poly.on("mouseover", function() {
                                this.setStyle({ weight: 3, color: "#FF0000", fillOpacity: 0.12 });
                                this.bringToFront();
                            });
                            poly.on("mouseout", function() {
                                this.setStyle({ weight: fWeight, color: fColor, fillOpacity: fFillOpac });
                            });
                        }
                        poly.addTo(featGroup);
                    }
                } else if (feat.type === "point" || feat.type === "circle") {
                    if (isValidPoint(feat.coordinates)) {
                        L.circleMarker(
                            [parseFloat(feat.coordinates[0]), parseFloat(feat.coordinates[1])],
                            {
                                radius: featStyle.radius || 6,
                                color: featStyle.color || "#3388ff",
                                fillColor: featStyle.fillColor || featStyle.color || "#3388ff",
                                fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.7,
                                weight: featStyle.weight || 2
                            }
                        ).addTo(featGroup);
                    }
                }
            });
            layer = featGroup;
        } else {
        switch (layerData.type) {
            case "heatmap":
                layer = this.renderHeatmap(layerData);
                break;
            case "polyline":
            case "line":
                // 线图层 - 过滤无效坐标点
                {
                    const validCoords = filterValidCoords(layerData.coordinates);
                    if (validCoords.length === 0) {
                        console.warn("[MapPanel] 线图层无有效坐标，跳过:", layerData.name);
                        return;
                    }
                    const lineProps = layerData.properties || [];
                    let lineStyle = {
                        color: style.color || "#3388ff",
                        weight: style.weight || 3,
                        opacity: style.opacity !== undefined ? style.opacity : 1,
                        dashArray: style.dashArray || null
                    };
                    // 行政区划图边界样式兜底（兼容旧地图数据）：市界红粗实线/区县界灰虚线/周边县界灰细虚线
                    if (this.currentMapType === "administrative") {
                        const _ln = layerData.name || "";
                        if (/市域边界|地级市界|市界/.test(_ln)) lineStyle = { color: "#E03131", weight: 3, opacity: 0.9, dashArray: null };
                        else if (/区县界/.test(_ln)) lineStyle = { color: "#8A8A8A", weight: 1.2, opacity: 0.9, dashArray: "6,4" };
                        else if (/周边县界/.test(_ln)) lineStyle = { color: "#999999", weight: 0.9, opacity: 0.85, dashArray: "1,4" };
                        else if (/省界/.test(_ln)) lineStyle = { color: "#000000", weight: 1.2, opacity: 0.9, dashArray: "1,4" };
                    }
                    // 武汉市域边界：叠加发光晕影（底层宽半透明红线 + 主线）
                    const _isMainBound = this.currentMapType === "administrative"
                        && /市域边界|地级市界|市界/.test(layerData.name || "");
                    // 多条线段时绑定弹窗显示道路名称
                    if (validCoords.length === 1) {
                        if (_isMainBound) {
                            const _gg = L.layerGroup();
                            L.polyline(validCoords[0], { color: "#E03131", weight: 8, opacity: 0.12, dashArray: null }).addTo(_gg);
                            L.polyline(validCoords[0], lineStyle).addTo(_gg);
                            layer = _gg;
                        } else {
                            layer = L.polyline(validCoords[0], lineStyle);
                        }
                    } else {
                        const group = L.layerGroup();
                        validCoords.forEach((lineCoords, idx) => {
                            if (_isMainBound) {
                                L.polyline(lineCoords, { color: "#E03131", weight: 8, opacity: 0.12, dashArray: null }).addTo(group);
                            }
                            const line = L.polyline(lineCoords, lineStyle);
                            const prop = lineProps[idx] || {};
                            if (prop.name || prop.subtype) {
                                let popupHtml = '<div style="font-size:13px;"><strong>' +
                                    Utils.escapeHtml(prop.name || layerData.name || '') + '</strong>';
                                if (prop.subtype) {
                                    const roadTypeLabels = {
                                        'motorway': '高速公路', 'trunk': '主干道', 'primary': '主要道路',
                                        'secondary': '次干道', 'tertiary': '支路',
                                        'residential': '社区道路', 'service': '服务道路',
                                        'rail': '铁路', 'subway': '地铁', 'light_rail': '轻轨',
                                        'high_speed': '高速铁路',
                                        'river': '河流', 'stream': '溪流', 'canal': '运河',
                                    };
                                    const label = roadTypeLabels[prop.subtype] || prop.subtype;
                                    popupHtml += '<br><span style="color:#666;">等级: ' + Utils.escapeHtml(label) + '</span>';
                                }
                                popupHtml += '</div>';
                                line.bindPopup(popupHtml);
                            }
                            line.addTo(group);
                        });
                        layer = group;
                    }
                }
                break;
            case "textLabel":
            case "label":
                // 文字标注图层（行政区划/水系注记：支持沿要素方向旋转与避让）
                {
                    const coords = layerData.coordinates;
                    if (!Array.isArray(coords) || coords.length === 0) {
                        console.warn("[MapPanel] 文字标注图层无坐标，跳过:", layerData.name);
                        return;
                    }
                    const group = L.layerGroup();
                    const props = layerData.properties || [];
                    const fontSize = style.fontSize || 13;
                    // 注记数量上限（载负量控制）：单图层最多渲染300个标签，避免渲染撑爆
                    const MAX_LABELS = 300;
                    let _placedCount = 0;
                    const placed = this._labelPlaced;  // 全局避让：跨图层共享，同一名称只显示一次
                    const getFontSize = (idx) => {
                        const p = props[idx] || {};
                        return (p && p.fontSize) ? p.fontSize : fontSize;
                    };
                    coords.forEach((pt, idx) => {
                        if (_placedCount >= MAX_LABELS) return;
                        if (!isValidPoint(pt)) return;
                        const prop = props[idx] || {};
                        const label = prop.name || layerData.name || "";
                        if (!label) return;
                        // 过滤非地名注记：纯英文/数字的长文本（歌词等污染）不渲染
                        if (/^[A-Za-z0-9\s.,'\"-]{15,}$/.test(label)) return;
                        // 名称去重：同一地理名称整图只渲染一处标签
                        if (this._labelNames && this._labelNames.has(label)) return;
                        if (!this._labelNames) this._labelNames = new Set();
                        this._labelNames.add(label);
                        const labelColor = style.color || "#1a1a1a";
                        // 字号随缩放级别自适应：基准zoom=12，每+1级字号×1.1，限制0.85~1.6倍且最小11px
                        const zoomFactor = Math.pow(1.1, this.map.getZoom() - 12);
                        const itemFontSize = Math.max(11, Math.round(getFontSize(idx) * Math.min(1.6, Math.max(0.85, zoomFactor))));
                        let rot = (prop.rotation !== undefined) ? prop.rotation : (style.rotation || 0);
                        // 字头朝上：旋转角归一化到[-90,90]，避免文字倒置
                        rot = ((rot + 90) % 180 + 180) % 180 - 90;
                        const labelFont = style.font || "normal";
                        let fontCss = "";
                        if (labelFont === "black") fontCss = "font-family:'SimHei','Microsoft YaHei',sans-serif;font-weight:700;";
                        else if (labelFont === "song") fontCss = "font-family:'SimSun','宋体','NSimSun',serif;";
                        else if (labelFont === "bold") fontCss = "font-weight:700;";
                        else if (labelFont === "italic") fontCss = "font-style:italic;";
                        const isCentered = style.center === true;
                        const cp = this.map.latLngToContainerPoint([parseFloat(pt[0]), parseFloat(pt[1])]);
                        // 文本碰撞检测（防重叠）：中心区县名注记与红点/已放置注记冲突时，
                        // 先缩小字号（最小9px），仍冲突再轻微错开(右下4px)，保证可读
                        let labelFs = itemFontSize;
                        let labelW = label.length * labelFs * 0.95 + 16;
                        let labelH = labelFs + 10;
                        let ox = 0, oy = 0;
                        if (isCentered) {
                            const hit = (w, h) => {
                                const h1 = placed.some(p2 =>
                                    !(cp.x + ox + w < p2.x || cp.x + ox > p2.x + p2.w ||
                                      cp.y + oy + h < p2.y || cp.y + oy > p2.y + p2.h));
                                const h2 = (this._poiMarkers || []).some(pm =>
                                    !(cp.x + ox + w < pm.x || cp.x + ox > pm.x + pm.w ||
                                      cp.y + oy + h < pm.y || cp.y + oy > pm.y + pm.h));
                                return h1 || h2;
                            };
                            while (labelFs > 9 && hit(labelW, labelH)) {
                                labelFs -= 1;
                                labelW = label.length * labelFs * 0.95 + 16;
                                labelH = labelFs + 10;
                            }
                            if (hit(labelW, labelH)) { ox = 4; oy = 4; }
                            placed.push({ x: cp.x + ox, y: cp.y + oy, w: labelW, h: labelH });
                            _placedCount += 1;
                        } else {
                            for (let attempt = 0; attempt < 4; attempt++) {
                                const cand = { x: cp.x + ox, y: cp.y + oy, w: labelW, h: labelH };
                                const h1 = placed.some(p2 =>
                                    !(cand.x + cand.w < p2.x || cand.x > p2.x + p2.w ||
                                      cand.y + cand.h < p2.y || cand.y > p2.y + p2.h));
                                if (!h1) { placed.push(cand); _placedCount += 1; break; }
                                if (attempt === 0) { ox += labelW * 0.7; }
                                else if (attempt === 1) { ox = 0; oy += labelH * 1.3; }
                                else if (attempt === 2) { ox = -labelW * 0.7; oy = 0; }
                                else { ox = 0; oy = 0; placed.push(cand); }
                            }
                        }
                        const icon = L.divIcon({
                            className: "map-text-label",
                            html: '<span class="map-text-label-box" style="' + fontCss + 'font-size:' + labelFs +
                                "px;border-color:" + labelColor + ";color:" + labelColor +
                                ";transform:translate(" + ox + "px," + oy + "px) rotate(" + rot + "deg);\">" +
                                Utils.escapeHtml(label) + "</span>",
                            iconSize: isCentered ? [labelW, labelH] : null,
                            iconAnchor: isCentered ? [labelW / 2, labelH / 2] : [0, 0]
                        });
                        const m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                        m.bindPopup('<div style="font-size:13px;"><strong>' + Utils.escapeHtml(label) + "</strong></div>");
                        m.addTo(group);
                    });
                    layer = group;
                }
                break;
            case "circleMarker":
                // 圆形/象形标记图层（POI按分类使用整套象形符号）
                {
                    const coords = layerData.coordinates;
                    if (!Array.isArray(coords) || coords.length === 0) {
                        console.warn("[MapPanel] 圆形标记图层无坐标，跳过:", layerData.name);
                        return;
                    }
                    const group = L.layerGroup();
                    const props = layerData.properties || [];
                    const usePictoIcon = !!(style.icon);
                    const zf = this._symbolZoomFactor();
                    const badgeSize = Math.max(26, Math.round((style.radius || 6) * 4.2 * zf));
                    coords.forEach((pt, idx) => {
                        if (isValidPoint(pt)) {
                            // 符号防重叠：与已渲染符号屏幕距离过近时缩小尺寸（POI防堆积）
                            let _dupFactor = 1;
                            try {
                                const _sp = this.map.latLngToContainerPoint([parseFloat(pt[0]), parseFloat(pt[1])]);
                                if (this._poiMarkers && this._poiMarkers.length) {
                                    for (const pm of this._poiMarkers) {
                                        if (Math.abs(pm.x - _sp.x) < pm.w * 0.85 && Math.abs(pm.y - _sp.y) < pm.h * 0.85) {
                                            _dupFactor = 0.55;
                                            break;
                                        }
                                    }
                                }
                            } catch (e) {}
                            const _effSize = Math.max(14, Math.round(badgeSize * _dupFactor));
                            let m;
                            if (usePictoIcon) {
                                const waterKind = (style.kind === "spring" || style.kind === "confluence" || style.kind === "to_lake" || style.kind === "to_sea") ? style.kind : null;
                                // 市级行政中心：红色五角星★（规范三-1，正红#D82828）
                                if (style.kind === "admin_city") {
                                    const asize = Math.max(26, Math.round((style.radius || 8) * 3.4 * zf));
                                    const icon = L.divIcon({
                                        className: "admin-city-symbol",
                                        html: '<span class="admin-city-star" style="color:' + (style.color || "#D82828") + ';font-size:' + asize + 'px;">★</span>',
                                        iconSize: [asize, asize],
                                        iconAnchor: [asize / 2, asize / 2],
                                        popupAnchor: [0, -asize / 2]
                                    });
                                    m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                                } else if (waterKind) {
                                    const wsvg = this._waterSymbolSvg(waterKind, style.color || "#0369a1");
                                    const wsize = Math.max(30, Math.round((style.radius || 6) * 5));
                                    const icon = L.divIcon({
                                        className: "poi-marker water-symbol",
                                        html: wsvg,
                                        iconSize: [wsize, wsize],
                                        iconAnchor: [wsize / 2, wsize / 2],
                                        popupAnchor: [0, -wsize / 2]
                                    });
                                    m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                                } else {
                                // 象形符号徽章：白色圆底 + 分类色环 + 成套矢量图标(iconClass)/emoji（百度/高德风格）
                                const iconInner = style.iconClass
                                    ? '<i class="fa-solid ' + style.iconClass + '"></i>'
                                    : (style.icon || "\ud83d\udccd");
                                const icon = L.divIcon({
                                    className: "poi-marker",
                                    html: '<span class="poi-marker-badge" style="border-color:' +
                                        (style.color || "#f59e0b") + ";width:" + _effSize + "px;height:" + _effSize +
                                        "px;font-size:" + Math.round(_effSize * 0.5) + 'px;">' +
                                        iconInner + "</span>",
                                    iconSize: [_effSize, _effSize],
                                    iconAnchor: [_effSize / 2, _effSize / 2],
                                    popupAnchor: [0, -_effSize / 2]
                                });
                                m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                                }
                            } else {
                                m = L.circleMarker([parseFloat(pt[0]), parseFloat(pt[1])], {
                                    radius: (style.radius || 6) * zf,
                                    color: style.color || "#f59e0b",
                                    fillColor: style.fillColor || style.color || "#f59e0b",
                                    fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.7,
                                    weight: style.weight || 2
                                });
                            }
                            const prop = props[idx] || {};
                            const poiName = prop.name || layerData.name || "";
                            // 记录符号屏幕位置（供区名注记碰撞检测防重叠）
                            try {
                                if (!this._poiMarkers) this._poiMarkers = [];
                                const _spt = this.map.latLngToContainerPoint([parseFloat(pt[0]), parseFloat(pt[1])]);
                                this._poiMarkers.push({ x: _spt.x, y: _spt.y, w: _effSize, h: _effSize, name: poiName });
                            } catch (e) {}
                            const popupHtml = '<div style="font-size:13px;min-width:170px;">' +
                                (style.icon ? '<span style="font-size:18px;">' + style.icon + '</span> ' : '') +
                                '<strong>' + Utils.escapeHtml(poiName) + '</strong>' +
                                (prop.category ? '<br><span style="color:#666;">类型: ' + Utils.escapeHtml(prop.category) + '</span>' : '') +
                                (prop.target ? '<br><span style="color:#0369a1;">汇入: ' + Utils.escapeHtml(prop.target) + '</span>' : '') +
                                (prop.kind === "to_lake" ? '<br><span style="color:#0369a1;">河流入湖口</span>' : '') +
                                (prop.kind === "spring" ? '<br><span style="color:#0369a1;">河源</span>' : '') +
                                (poiName ? '<br><button class="wiki-btn" type="button">📖 百科介绍</button>' : '') +
                                '</div>';
                            m.bindPopup(popupHtml);
                            // 悬停显示名称（重点地标/行政中心/水系符号等）
                            if (poiName) {
                                m.bindTooltip(poiName, { sticky: true, direction: "top", opacity: 0.92 });
                            }
                            if (poiName) {
                                // 点击"百科介绍"：从后端加载建筑简介与图片（点击后显示）
                                m.on("popupopen", (e) => {
                                    const box = e.popup.getElement();
                                    const btn = box ? box.querySelector(".wiki-btn") : null;
                                    if (!btn || btn.dataset.bound) return;
                                    btn.dataset.bound = "1";
                                    btn.addEventListener("click", async () => {
                                        btn.innerHTML = "⏳ 加载百科...";
                                        btn.disabled = true;
                                        try {
                                            const resp = await fetch(CONFIG.apiBaseUrl + "/api/maps/wiki?name=" + encodeURIComponent(poiName));
                                            const json = await resp.json();
                                            const d = json.data || {};
                                            const holder = document.createElement("div");
                                            holder.className = "wiki-box";
                                            let wikiHtml = "";
                                            if (d.image) {
                                                wikiHtml += "<img class=\"wiki-img\" src=\"" + d.image +
                                                    "\" onerror=\"this.style.display='none'\" alt=\"百科图片\">";
                                            }
                                            wikiHtml += "<div class=\"wiki-text\">" + Utils.escapeHtml(d.extract || "暂无百科简介") + "</div>";
                                            if (d.source) wikiHtml += "<div class=\"wiki-src\">来源：" + Utils.escapeHtml(d.source) + "</div>";
                                            holder.innerHTML = wikiHtml;
                                            btn.replaceWith(holder);
                                        } catch (err) {
                                            btn.innerHTML = "百科加载失败";
                                        }
                                    });
                                });
                            }
                            m.addTo(group);
                        }
                    });
                    layer = group;
                }
                break;
            case "marker":
            case "point":
                // 点标记图层 - 支持多个标记点
                {
                    const coords = layerData.coordinates;
                    if (!Array.isArray(coords) || coords.length === 0) {
                        console.warn("[MapPanel] 点图层无坐标，跳过:", layerData.name);
                        return;
                    }
                    const props = layerData.properties || [];
                    // 单个点用L.marker，多个点用LayerGroup
                    if (coords.length === 1) {
                        const latlng = Array.isArray(coords[0]) ? coords[0] : coords;
                        if (!isValidPoint(latlng)) return;
                        layer = L.marker([parseFloat(latlng[0]), parseFloat(latlng[1])]);
                        const prop = props[0] || {};
                        if (prop.name || layerData.popup) {
                            layer.bindPopup(layerData.popup || '<strong>' + Utils.escapeHtml(prop.name || '') + '</strong>');
                        }
                    } else {
                        const group = L.layerGroup();
                        coords.forEach((pt, idx) => {
                            if (isValidPoint(pt)) {
                                const m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])]);
                                const prop = props[idx] || {};
                                if (prop.name) {
                                    m.bindPopup('<div style="font-size:13px;"><strong>' + Utils.escapeHtml(prop.name) + '</strong></div>');
                                }
                                m.addTo(group);
                            }
                        });
                        layer = group;
                    }
                }
                break;
            case "polygon":
            case "area":
                // 多边形图层 - 支持多个独立多边形和fillColor填充
                {
                    const validCoords = filterValidCoords(layerData.coordinates);
                    if (validCoords.length === 0) {
                        console.warn("[MapPanel] 多边形图层无有效坐标，跳过:", layerData.name);
                        return;
                    }
                    const polyStyle = {
                        color: style.color || "#3388ff",
                        fillColor: style.fillColor || style.color || "#3388ff",
                        weight: style.weight || 2,
                        opacity: style.opacity !== undefined ? style.opacity : 1,
                        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
                        dashArray: style.dashArray || null
                    };
                    const props = layerData.properties || [];
                    const buildPolyPopup = (prop, layerName) => {
                        let html = '<div style="font-size:13px;min-width:120px;">';
                        html += '<strong>' + Utils.escapeHtml(prop.name || layerName || '') + '</strong>';
                        if (prop.subtype) {
                            const subtypeLabels = {
                                'residential': '住宅', 'apartments': '公寓', 'commercial': '商业',
                                'industrial': '工业', 'public': '公共', 'school': '学校',
                                'university': '大学', 'hospital': '医院', 'religious': '宗教',
                                'parking': '停车', 'warehouse': '仓储', 'default': '其他',
                                'park': '公园', 'garden': '花园', 'forest': '森林',
                                'grass': '草地', 'meadow': '草甸',
                            };
                            const label = subtypeLabels[prop.subtype] || prop.subtype;
                            html += '<br><span style="color:#666;">类型: ' + Utils.escapeHtml(label) + '</span>';
                        }
                        if (prop.category) {
                            html += '<br><span style="color:#666;">分类: ' + Utils.escapeHtml(prop.category) + '</span>';
                        }
                        html += '</div>';
                        return html;
                    };
                    if (validCoords.length === 1) {
                        layer = L.polygon(validCoords[0], polyStyle);
                        const prop = props[0] || {};
                        if (prop.name || prop.subtype) {
                            layer.bindPopup(buildPolyPopup(prop, layerData.name));
                        }
                    } else {
                        // 多个独立多边形
                        const group = L.layerGroup();
                        validCoords.forEach((polyCoords, idx) => {
                            const poly = L.polygon(polyCoords, polyStyle);
                            const prop = props[idx] || {};
                            if (prop.name || prop.subtype) {
                                poly.bindPopup(buildPolyPopup(prop, layerData.name));
                            }
                            poly.addTo(group);
                        });
                        layer = group;
                    }
                }
                break;
            case "circle":
                // 圆形图层
                {
                    const coords = layerData.coordinates;
                    if (!isValidPoint(coords)) {
                        console.warn("[MapPanel] 圆形图层坐标无效，跳过:", layerData.name);
                        return;
                    }
                    layer = L.circle([parseFloat(coords[0]), parseFloat(coords[1])], {
                        radius: layerData.radius || 500,
                        color: style.color || "#3388ff",
                        weight: style.weight || 2,
                        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.2
                    });
                }
                break;
            case "geojson":
                // GeoJSON图层
                layer = L.geoJSON(layerData.coordinates || layerData.data, {
                    style: () => ({
                        color: style.color || "#3388ff",
                        weight: style.weight || 2,
                        opacity: style.opacity !== undefined ? style.opacity : 1,
                        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.2
                    }),
                    pointToLayer: (feature, latlng) => {
                        return L.marker(latlng);
                    }
                });
                break;
            default:
                // 处理带features数组的图层（专题地图）
                if (layerData.features && Array.isArray(layerData.features) && layerData.features.length > 0) {
                    const group = L.layerGroup();
                    layerData.features.forEach(feat => {
                        if (!feat.coordinates) return;
                        const featStyle = feat.style || style;
                        if (feat.type === "polygon") {
                            const coords = filterValidCoords(
                                Array.isArray(feat.coordinates[0]) ? feat.coordinates : [feat.coordinates]
                            );
                            if (coords.length > 0) {
                                L.polygon(coords, {
                                    color: featStyle.color || "#3388ff",
                                    fillColor: featStyle.fillColor || featStyle.color || "#3388ff",
                                    weight: featStyle.weight || 1,
                                    opacity: featStyle.opacity !== undefined ? featStyle.opacity : 0.5,
                                    fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.4
                                }).addTo(group);
                            }
                        } else if (feat.type === "point" || feat.type === "circle") {
                            if (isValidPoint(feat.coordinates)) {
                                L.circleMarker(
                                    [parseFloat(feat.coordinates[0]), parseFloat(feat.coordinates[1])],
                                    {
                                        radius: featStyle.radius || 6,
                                        color: featStyle.color || "#3388ff",
                                        fillColor: featStyle.fillColor || featStyle.color || "#3388ff",
                                        fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.7,
                                        weight: featStyle.weight || 2
                                    }
                                ).addTo(group);
                            }
                        }
                    });
                    layer = group;
                } else {
                    console.warn("未知图层类型:", layerData.type);
                    return;
                }
         }
        } // end of else (features preprocessing)
        if (!layer) return;
        // 添加弹窗（如果有）
        if (layerData.popup && layerData.type !== "marker") {
            layer.bindPopup(layerData.popup);
        }
        // 添加tooltip
        if (layerData.name) {
            layer.bindTooltip(layerData.name, { sticky: true });
        }
        // 图层 LOD（层级细节控制）：路网/水系/注记/POI 按缩放分级
        // 持久化可见性（QGIS式隐藏图层）+ LOD 缩放显隐
        const _lodShown = layerData._lodVisible && layerData.visible !== false;
        // 添加到地图
        if (_lodShown) layer.addTo(this.map);
        // 存储图层引用
        this.layerGroups[layerData.id] = {
            layer: layer,
            data: _origData,       // 始终保存全量数据（编辑/保存用），渲染层为抽稀副本
            visible: _lodShown
        };
        // 编辑模式下为新渲染要素挂载编辑元数据
        if (this.editMode) this._attachEditMetadata(layerData.id, layer);
    }

    /**
     * 清除所有图层
     */
    clearAllLayers() {
        Object.values(this.layerGroups).forEach(item => {
            if (item.layer) {
                this.map.removeLayer(item.layer);
            }
        });
        this.layerGroups = {};
        // 清除自动检测的桥梁/渡口符号
        if (this._bridgeGroup) {
            this.map.removeLayer(this._bridgeGroup);
            this._bridgeGroup = null;
        }
        // 清除图面整饰（常驻图例框/编制说明）
        const miniLegendEl = document.getElementById("map-mini-legend");
        if (miniLegendEl) miniLegendEl.classList.add("hidden");
        const attributionEl = document.getElementById("map-attribution");
        if (attributionEl) attributionEl.classList.add("hidden");
        // 清除编制说明弹窗
        const metaBody = document.getElementById("map-metadata-body");
        if (metaBody) metaBody.innerHTML = "";
        const metaModal = document.getElementById("map-metadata-modal");
        if (metaModal) metaModal.classList.add("hidden");
        const metaBtn = document.getElementById("toolbar-metadata");
        if (metaBtn) metaBtn.classList.remove("active");
        // 清除质量检测面板
        const qualityPanel = document.getElementById("map-quality-panel");
        if (qualityPanel) qualityPanel.classList.add("hidden");
        const qualityBanner = document.getElementById("map-quality-banner");
        if (qualityBanner) qualityBanner.classList.add("hidden");
        const qualityChip = document.getElementById("map-status-quality");
        if (qualityChip) {
            qualityChip.textContent = "质检中…";
            qualityChip.className = "status-quality";
            qualityChip.onclick = null;
        }
        if (this._qualityMarker) { this.map.removeLayer(this._qualityMarker); this._qualityMarker = null; }
        // 清除图例
        this.legendData = null;
        const legendPanel = document.getElementById("map-legend-panel");
        const legendBtn = document.getElementById("map-legend-btn");
        if (legendPanel) legendPanel.classList.add("hidden");
        if (legendBtn) { legendBtn.classList.remove("active"); legendBtn.style.display = "none"; }
        this.updateLayerPanel();
    }

    /**
     * 初始化图例按钮与面板
     */
    initLegendPanel() {
        const btn = document.getElementById("map-legend-btn");
        const panel = document.getElementById("map-legend-panel");
        const closeBtn = panel ? panel.querySelector(".legend-panel-close") : null;
        const pinBtn = document.getElementById("legend-pin-btn");
        const searchInput = document.getElementById("legend-search-input");
        this.legendPinned = false;
        if (btn && panel) {
            btn.addEventListener("click", () => {
                const willHide = !this.legendPinned && !panel.classList.contains("hidden");
                if (willHide) {
                    panel.classList.add("hidden");
                    btn.classList.remove("active");
                } else {
                    panel.classList.remove("hidden");
                    btn.classList.add("active");
                    this.renderLegendPanel();
                }
            });
        }
        if (pinBtn && panel) {
            pinBtn.addEventListener("click", () => {
                this.legendPinned = !this.legendPinned;
                pinBtn.classList.toggle("active", this.legendPinned);
                pinBtn.title = this.legendPinned ? "取消固定" : "固定图例";
            });
        }
        if (closeBtn && panel) {
            closeBtn.addEventListener("click", () => {
                panel.classList.add("hidden");
                if (btn) btn.classList.remove("active");
                this.legendPinned = false;
                if (pinBtn) pinBtn.classList.remove("active");
            });
        }
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                this.legendSearch = searchInput.value.trim();
                this.renderLegendPanel();
            });
        }
        // 右下角图例折叠抽屉：点击标题栏/折叠按钮切换展开/折叠，localStorage记忆状态
        this._initMiniLegendFold();
    }

    /** 初始化右下角图例折叠抽屉（标题栏 + ▼/▶ 按钮） */
    _initMiniLegendFold() {
        const legend = document.getElementById("map-mini-legend");
        const header = document.getElementById("mini-legend-header");
        const foldBtn = document.getElementById("mini-legend-fold");
        if (!legend || !header) return;
        const toggle = () => {
            const collapsed = legend.classList.toggle("collapsed");
            if (foldBtn) foldBtn.textContent = collapsed ? "▶" : "▼";
            try { localStorage.setItem("carto_mini_legend_collapsed", collapsed ? "1" : "0"); } catch (e) {}
        };
        header.addEventListener("click", toggle);
        if (foldBtn) foldBtn.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
    }

    /** 应用图例折叠状态（localStorage记忆；无记录时默认展开） */
    _applyMiniLegendState() {
        const legend = document.getElementById("map-mini-legend");
        const foldBtn = document.getElementById("mini-legend-fold");
        if (!legend) return;
        let collapsed = false;
        try { collapsed = localStorage.getItem("carto_mini_legend_collapsed") === "1"; } catch (e) {}
        legend.classList.toggle("collapsed", collapsed);
        if (foldBtn) foldBtn.textContent = collapsed ? "▶" : "▼";
    }

    /**
     * 渲染整套图例（按钮 + 分组面板 + 搜索 + 图层联动）
     * @param {object} legendData - 图例数据 {title, items: [...]}
     */
    renderLegend(legendData) {
        this.legendData = legendData || null;
        this.legendActiveGroup = "全部";
        this.legendSearch = "";
        const btn = document.getElementById("map-legend-btn");
        const searchInput = document.getElementById("legend-search-input");
        if (searchInput) searchInput.value = "";
        if (btn) {
            btn.style.display = (legendData && legendData.items && legendData.items.length) ? "" : "none";
        }
        if (legendData) this.renderLegendPanel();
    }

    /**
     * 渲染图例面板内容（分组标签 + 条目列表）
     */
    renderLegendPanel() {
        const panel = document.getElementById("map-legend-panel");
        const tabsEl = document.getElementById("legend-group-tabs");
        const itemsEl = document.getElementById("legend-items");
        if (!panel || !tabsEl || !itemsEl || !this.legendData) return;
        const items = this.legendData.items || [];
        const groups = ["全部"];
        items.forEach(it => {
            const g = it.group || "其他";
            if (groups.indexOf(g) < 0) groups.push(g);
        });
        tabsEl.innerHTML = "";
        groups.forEach(g => {
            const count = g === "全部" ? items.length : items.filter(it => (it.group || "其他") === g).length;
            const tab = document.createElement("button");
            tab.className = "legend-tab" + (g === this.legendActiveGroup ? " active" : "");
            tab.innerHTML = Utils.escapeHtml(g) + '<span class="legend-tab-count">' + count + "</span>";
            tab.addEventListener("click", () => { this.legendActiveGroup = g; this.renderLegendPanel(); });
            tabsEl.appendChild(tab);
        });
        const keyword = (this.legendSearch || "").trim().toLowerCase();
        const filtered = items.filter(it => {
            const inGroup = this.legendActiveGroup === "全部" || (it.group || "其他") === this.legendActiveGroup;
            const label = (it.label || "").toLowerCase();
            const group = (it.group || "").toLowerCase();
            return inGroup && (!keyword || label.indexOf(keyword) >= 0 || group.indexOf(keyword) >= 0);
        });
        itemsEl.innerHTML = "";
        if (filtered.length === 0) {
            itemsEl.innerHTML = '<div style="color:#94a3b8;font-size:12px;padding:14px;">没有匹配的图例项</div>';
            return;
        }
        filtered.forEach(item => {
            const row = document.createElement("div");
            const matched = this._findLayersByLabel(item.label);
            const anyVisible = matched.some(id => this.layerGroups[id] && this.layerGroups[id].visible);
            row.className = "legend-item" + (matched.length > 0 && !anyVisible ? " legend-item-off" : "");
            row.innerHTML =
                '<span class="legend-symbol">' + this._legendSymbolHtml(item) + "</span>" +
                '<span class="legend-item-label">' + Utils.escapeHtml(item.label || "") + "</span>" +
                '<span class="legend-eye">' + (matched.length > 0 ? (anyVisible ? "\ud83d\udc41" : "\ud83d\udeab") : "") + "</span>";
            if (matched.length > 0) {
                row.title = "点击" + (anyVisible ? "隐藏" : "显示") + "对应图层";
                row.addEventListener("click", () => {
                    matched.forEach(id => { if (this.layerGroups[id]) this.toggleLayer(id, !anyVisible); });
                    this.renderLegendPanel();
                });
            } else {
                row.style.cursor = "default";
            }
            itemsEl.appendChild(row);
        });
    }

    /**
     * 图例条目符号HTML
     */
    _legendSymbolHtml(item) {
        if (item.type === "line") {
            const dash = item.dashArray
                ? "border-top:2px dashed " + (item.color || "#333") + ";"
                : "background:" + (item.color || "#333") + ";";
            const h = Math.max(2, Math.min(item.weight || 3, 6));
            return '<span style="display:inline-block;width:24px;height:' + h + "px;" + dash + ';border-radius:1px;"></span>';
        }
        if (item.type === "polygon") {
            return '<span style="display:inline-block;width:16px;height:16px;background:' +
                (item.fillColor || item.color || "#ccc") + ";border:1px solid " +
                (item.color || "#999") + ";border-radius:2px;opacity:" + (item.fillOpacity || 0.5) + ';"></span>';
        }
        if (item.iconClass) {
            return '<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;color:' +
                (item.color || "#0369a1") + ';font-size:17px;"><i class="fa-solid ' + item.iconClass + '"></i></span>';
        }
        if (item.icon) {
            return '<span style="font-size:17px;line-height:1;">' + item.icon + "</span>";
        }
        return '<span style="display:inline-block;width:13px;height:13px;background:' +
            (item.color || "#f59e0b") + ';border-radius:50%;border:1px solid rgba(0,0,0,0.2);"></span>';
    }

    /**
     * 根据图例标签匹配对应图层（忽略外层/内层后缀）
     */
    _findLayersByLabel(label) {
        if (!label) return [];
        const base = String(label).replace(/\(外层\)|\(内层\)/g, "").trim();
        return Object.keys(this.layerGroups).filter(id => {
            const name = (this.layerGroups[id].data.name || "").replace(/\(外层\)|\(内层\)/g, "").trim();
            return name === base || name === label;
        });
    }

    /**
     * 自定义标注工具（点击地图放置标注点，答辩演示：标注赏樱点/卫生间等）
     */
    initMarkerTool() {
        const btn = document.getElementById("toolbar-marker");
        if (!btn) return;
        btn.addEventListener("click", () => {
            this.markerMode = !this.markerMode;
            this.updateMarkerBtn();
            this.map.getContainer().style.cursor = this.markerMode ? "crosshair" : "";
            if (this.markerMode) {
                Utils.showToast("标注模式：请在地图上点击放置标注点", "info");
            }
        });
    }

    updateMarkerBtn() {
        const btn = document.getElementById("toolbar-marker");
        if (btn) btn.classList.toggle("active", this.markerMode);
    }

    /**
     * 标准分段比例尺（黑白交替分段条 + km/m 标注）
     */
    /**
     * 计算当前画面比例尺（整个画面宽度对应的比例尺，随缩放实时更新）
     * @returns {{denom:number, meters:number, label:string}}
     */
    /** 圆整到 1/2/5×10^n 的"整"数值 */
    _niceScale(m) {
        if (m <= 0) return 200000;
        const pow = Math.pow(10, Math.floor(Math.log10(m)));
        const n = m / pow;
        if (n <= 1) return pow;
        if (n <= 2) return 2 * pow;
        if (n <= 5) return 5 * pow;
        return 10 * pow;
    }

    /**
     * 计算比例尺数据：数字比例尺与线段比例尺严格一致。
     * 以"画面每像素对应实地距离"为基准选择主分划总长(meters)，
     * 再按比例尺条宽度反推数字比例尺分母(denom)，保证 1:xxx 与条上 0~xxxkm 完全匹配。
     * @param {number} barW - 比例尺条宽度(px)，与CSS一致
     */
    _computeScaleData(barW) {
        const size = this.map.getSize();
        const y = size.y / 2;
        const maxMeters = size.x > 0 ? this.map.distance(
            this.map.containerPointToLatLng([0, y]),
            this.map.containerPointToLatLng([size.x, y])
        ) : 0;
        const mPerPx = size.x > 0 ? maxMeters / size.x : 0;
        // 数字比例尺：画面1px对应mPerPx米 → 分母 = mPerPx / 0.0002646(96dpi时1px=0.2646mm)。
        // 直接由画面真实比例换算，不再被线段取整反推，保证数字与实际图面严格一致。
        const _rawDenom = mPerPx > 0 ? Math.max(1000, mPerPx / 0.0002646) : 0;
        // 取整粒度自适应：小分母(大比例尺)取整到100，大分母取整到1000，保证精度
        const _step = _rawDenom < 50000 ? 100 : 1000;
        const denom = _rawDenom ? Math.round(_rawDenom / _step) * _step : 0;
        // 线段比例尺：整条barW px表示 barW*mPerPx 米（与画面比例严格一致）；
        // 主分划(4段)总长精确为 barW*4/5*mPerPx，仅末端标签按制图惯例取整。
        const meters = barW * (4 / 5) * mPerPx;
        const labelMeters = this._niceScale(meters);
        return { denom, meters, label: labelMeters >= 1000 ? (labelMeters / 1000) + " km" : labelMeters + " m" };
    }

    /** 更新右下角比例尺控件（非行政区划图使用） */
    _updateScaleControl() {
        if (!this.scaleControl) return;
        const d = this._computeScaleData(180);
        const c = this.scaleControl._container;
        if (!c) return;
        // 数字比例尺：直接以 1:xxx 形式显示（取代线段比例尺条）
        const num = c.querySelector(".map-scale-num");
        if (num) num.textContent = d.denom ? "1:" + d.denom.toLocaleString("en-US").replace(/,/g, " ") : "1:1 440 000";
    }

    /** 更新图例框内比例尺（行政区划图：数字+线段比例尺随缩放实时变化） */
    _updateMiniScale() {
        const num = document.getElementById("mini-scale-num");
        const bar = document.getElementById("mini-scale-bar");
        const labels = document.getElementById("mini-scale-labels");
        if (!num || !bar || !labels) return;
        const d = this._computeScaleData(140);
        num.textContent = d.denom ? "1:" + d.denom.toLocaleString("en-US").replace(/,/g, " ") : "1:1 440 000";
        bar.innerHTML = "";
        for (let i = 0; i < 5; i++) {
            const seg = document.createElement("span");
            seg.className = "map-scale-seg" + (i === 0 ? " sub" : (i % 2 === 1 ? " dark" : ""));
            bar.appendChild(seg);
        }
        labels.innerHTML = "<span></span><span>0</span><span></span><span></span><span>" + d.label + "</span>";
    }

    /** 同步工具栏比例尺输入框（输入框未被聚焦时回显当前比例尺） */
    _syncScaleInput(denom) {
        const input = document.getElementById("map-scale-input");
        if (!input || document.activeElement === input) return;
        if (denom) input.value = "1:" + denom.toLocaleString("en-US").replace(/,/g, " ");
    }

    /** 自定义比例尺：输入 1:xxx 回车后跳转到对应缩放级别 */
    _initScaleSetter() {
        const input = document.getElementById("map-scale-input");
        if (!input) return;
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const digits = String(input.value || "").replace(/[^0-9]/g, "");
                const target = parseInt(digits, 10);
                if (!target || target < 1000) {
                    Utils.showToast("请输入有效比例尺，如 1:100000", "warning");
                    return;
                }
                const z = this._zoomForScale(target);
                // 失焦让回显显示跳转后的实际比例尺（zoom为整数，实际值可能与输入略有出入）
                input.blur();
                const _d = this._computeScaleData(180);
                const _actual = (_d && _d.denom) ? _d.denom : target;
                Utils.showToast("已跳转，当前实际比例尺 1:" + _actual.toLocaleString("en-US").replace(/,/g, " "),
                                "info", 2200);
            }
        });
    }

    /**
     * 根据目标比例尺分母计算目标缩放级别（公式法，一次到位）
     * 原理：mPerPx ∝ 2^(-zoom)，由当前mPerPx与目标mPerPx比值直接算出zoom差
     */
    _zoomForScale(targetDenom) {
        const size = this.map.getSize();
        const y = size.y / 2;
        const mPerPxNow = size.x > 0 ? this.map.distance(
            this.map.containerPointToLatLng([0, y]),
            this.map.containerPointToLatLng([size.x, y])
        ) / size.x : 0;
        const mPerPxTarget = targetDenom * 0.0002646;
        if (!mPerPxNow || !mPerPxTarget) return null;
        const z = this.map.getZoom() + Math.log2(mPerPxNow / mPerPxTarget);
        // 0.05 步长吸附（与 zoomSnap=0.05 一致），保证比例尺与输入几乎一致（误差<1%）
        const clamped = Math.min(19, Math.max(1, Math.round(z * 20) / 20));
        this.map.setZoom(clamped);
        return clamped;
    }

    initScaleControl() {
        const panel = this;
        const ScaleControl = L.Control.extend({
            options: { position: "bottomleft" },
            onAdd: function() {
                const container = L.DomUtil.create("div", "map-scale");
                container.innerHTML = '<div class="map-scale-num"></div>';
                this._container = container;
                this._update = function() { panel._updateScaleControl(); };
                this._map.on("zoomend moveend", this._update);
                this._update();
                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);
                return container;
            }
        });
        this.scaleControl = new ScaleControl();
        this.scaleControl.addTo(this.map);
    }

    /**
     * 编制说明（坐标系/投影/数据来源，规范3.7）
     */
    renderMetadata(meta) {
        // 编制说明移入独立弹窗（工具栏"编制说明"按钮打开），不再占用图层管理面板
        const el = document.getElementById("map-metadata-body");
        if (!el) return;
        if (!meta) {
            el.innerHTML = '<div class="map-metadata-title">编制说明</div><div class="map-metadata-line">暂无编制信息</div>';
            return;
        }
        // 投影标注动态化：显示当前实际使用的投影（切换投影后自动更新）
        const meta2 = Object.assign({}, meta);
        if (meta2["投影"]) meta2["投影"] = this._crsName();
        el.innerHTML = '<div class="map-metadata-title">编制说明</div>' +
            Object.entries(meta2).map(([k, v]) =>
                '<div class="map-metadata-line"><b>' + Utils.escapeHtml(k) + "：</b>" +
                Utils.escapeHtml(v) + "</div>").join("");
    }

    /**
     * 从地图数据中查找武汉市域边界多边形坐标
     * @param {object} mapData - 完整地图数据
     * @returns {Array|null} Leaflet格式坐标数组 [[lat, lng], ...] 或 null
     */
    _findWuhanBoundaryPolygon(mapData) {
        // 从生成的图层数据中查找武汉市域边界多边形的坐标
        for (const layer of (mapData.layers || [])) {
            const name = (layer.name || '').toLowerCase();
            if (name.includes('市域边界') || name.includes('市界') || name.includes('wuhan_boundary')) {
                const feats = layer.features || layer.data?.features || [];
                for (const feat of feats) {
                    const geom = feat.geometry || {};
                    if (geom.type === 'Polygon' && geom.coordinates?.length > 0) {
                        // Leaflet用[lat,lng]格式
                        const ring = geom.coordinates[0];
                        return ring.map(c => [c[1], c[0]]);
                    }
                    if (geom.type === 'MultiPolygon' && geom.coordinates?.length > 0) {
                        return geom.coordinates[0][0].map(c => [c[1], c[0]]);
                    }
                }
            }
        }
        return null;
    }

    renderQuality(report) {
        const container = document.getElementById("map-quality-panel");
        if (!container) return;
        const summary = report.summary || {};
        const items = report.items || [];
        const fail = summary.failed || 0;
        // 主界面状态栏质检指示（异常清晰可见，点击打开图层面板并定位质检区）
        const chip = document.getElementById("map-status-quality");
        if (chip) {
            chip.textContent = summary.passed_all ? "质检 ✓ 全部通过" : `质检 ⚠ ${fail} 项异常`;
            chip.className = "status-quality " + (summary.passed_all ? "ok" : "warn");
            chip.style.cursor = "pointer";
            chip.onclick = () => {
                this.toggleLayerPanel(true);
                container.scrollIntoView({ behavior: "smooth", block: "nearest" });
            };
        }
        // 图层管理面板顶部红色横幅（有异常时醒目提示）
        const banner = document.getElementById("map-quality-banner");
        if (banner) {
            if (fail > 0) {
                banner.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>
                    数据质量检测发现 <b>${fail}</b> 项异常
                    <span class="quality-banner-count">${summary.total_checks || 0} 项检查</span>`;
                banner.classList.remove("hidden");
                banner.onclick = () => container.scrollIntoView({ behavior: "smooth", block: "nearest" });
            } else {
                banner.classList.add("hidden");
                banner.onclick = null;
            }
        }
        let html = '<div class="quality-header' + (fail > 0 ? " has-errors" : "") + '">' +
            '<i class="fa-solid fa-shield-halved"></i> 数据质量检测' +
            (summary.passed_all
                ? ' <span class="quality-badge ok">全部通过</span>'
                : ' <span class="quality-badge warn">' + fail + ' 项异常</span>') +
            '<button class="quality-recheck" title="重新检测"><i class="fa-solid fa-rotate"></i></button>' +
            '</div>';
        html += '<div class="quality-items">';
        items.forEach((it) => {
            html += '<div class="quality-item ' + (it.passed ? "ok" : "err") + '" data-idx="' + it.check + '">' +
                '<span class="quality-ico">' + (it.passed ? "✓" : "✗") + "</span>" +
                '<span class="quality-text">' + Utils.escapeHtml(it.check) +
                (it.count ? ' <b>' + it.count + "</b>" : "") + "</span>" +
                (it.positions && it.positions.length
                    ? '<button class="quality-locate" data-idx="' + it.check + '" title="定位问题">📍</button>'
                    : "") +
                "</div>";
            if (!it.passed && it.message) {
                html += '<div class="quality-msg" data-msg-idx="' + it.check + '">' +
                    Utils.escapeHtml(it.message) + "</div>";
            }
        });
        html += "</div>";
        container.innerHTML = html;
        container.classList.remove("hidden");
        container.querySelectorAll(".quality-locate").forEach(btn => {
            btn.addEventListener("click", (ev) => {
                ev.stopPropagation();
                const it = items.find(x => x.check === btn.dataset.idx);
                if (it && it.positions && it.positions.length) {
                    this.map.setView(it.positions[0], Math.max(this.map.getZoom(), 13));
                    if (this._qualityMarker) this.map.removeLayer(this._qualityMarker);
                    this._qualityMarker = L.circleMarker(it.positions[0], {
                        radius: 14, color: "#dc2626", fillColor: "#dc2626", fillOpacity: 0.55
                    }).addTo(this.map);
                    this._qualityMarker.bindPopup("<strong>" + Utils.escapeHtml(it.check) + "</strong>").openPopup();
                }
            });
        });
        container.querySelectorAll(".quality-item").forEach(div => {
            div.addEventListener("click", () => {
                const msg = container.querySelector('[data-msg-idx="' + div.dataset.idx + '"]');
                if (msg) msg.classList.toggle("show");
            });
        });
        const recheck = container.querySelector(".quality-recheck");
        if (recheck) recheck.addEventListener("click", () => this.checkQuality());
    }

    /**
     * 经纬网与经纬度注记（标准地图整饰）
     */
    initGraticule() {
        this.graticuleGroup = L.layerGroup().addTo(this.map);
        this.graticuleLabelGroup = L.layerGroup().addTo(this.map);
        this._updateGraticule = this._updateGraticule.bind(this);
        this.map.on("moveend zoomend", this._updateGraticule);
        // 比例尺回显：缩放/平移后更新工具栏比例尺输入框
        this.map.on("moveend zoomend", () => {
            const _d = this._computeScaleData(140);
            this._syncScaleInput(_d ? _d.denom : 0);
        });
        // 缩放级别变化时刷新注记（字号随比例尺自适应）
        this.map.on("zoomend", () => this.refreshLabels());
        this._updateGraticule();
    }

    _updateGraticule() {
        if (!this.graticuleGroup) return;
        this.graticuleGroup.clearLayers();
        this.graticuleLabelGroup.clearLayers();
        const bounds = this.map.getBounds();
        const zoom = this.map.getZoom();
        const step = zoom <= 7 ? 2 : zoom <= 9 ? 1 : zoom <= 11 ? 0.5 :
                     zoom <= 13 ? 0.2 : zoom <= 15 ? 0.1 : 0.05;
        const south = Math.floor(bounds.getSouth() / step) * step;
        const north = Math.ceil(bounds.getNorth() / step) * step;
        const west = Math.floor(bounds.getWest() / step) * step;
        const east = Math.ceil(bounds.getEast() / step) * step;
        const lineStyle = { color: "#94a3b8", weight: 0.6, opacity: 0.35, interactive: false };
        // 经纬度度分格式（规范：114°30′）
        const fmtDMS = (deg) => {
            const d = Math.abs(deg);
            const dd = Math.floor(d);
            const m = Math.round((d - dd) * 60);
            return dd + "\u00b0" + (m < 10 ? "0" + m : m) + "\u2032";
        };
        // 纬线 + 左边缘纬度注记（度分）
        for (let lat = south; lat <= north + 1e-9; lat += step) {
            const v = Math.round(lat * 100) / 100;
            L.polyline([[v, west], [v, east]], lineStyle).addTo(this.graticuleGroup);
            const label = (Math.abs(v) < 0.01 ? "0\u00b0" : fmtDMS(v) + (v >= 0 ? "N" : "S"));
            this._addGraticuleLabel([v, west], label);
        }
        // 经线 + 底部经度注记（度分）
        for (let lng = west; lng <= east + 1e-9; lng += step) {
            const v = Math.round(lng * 100) / 100;
            L.polyline([[south, v], [north, v]], lineStyle).addTo(this.graticuleGroup);
            const label = (Math.abs(v) < 0.01 ? "0\u00b0" : fmtDMS(v) + (v >= 0 ? "E" : "W"));
            this._addGraticuleLabel([south, v], label);
        }
    }

    _addGraticuleLabel(latlng, text) {
        const icon = L.divIcon({
            className: "graticule-label",
            html: '<span class="graticule-label-text">' + text + "</span>",
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        L.marker(latlng, { icon: icon, interactive: false }).addTo(this.graticuleLabelGroup);
    }

    /**
     * 初始化图层管理面板
     */
    initLayerPanel() {
        const panel = document.getElementById("map-layer-panel");
        if (!panel) return;
        this._layerPanelPinned = localStorage.getItem("carto.layerPanel.pinned") === "1";
        this._layerPanelPos = null;
        this._collapsedGroups = {};
        try {
            this._collapsedGroups = JSON.parse(localStorage.getItem("carto.layerPanel.collapsed") || "{}");
        } catch (e) { this._collapsedGroups = {}; }
        this._layerSearch = "";
        // 关闭按钮
        const closeBtn = panel.querySelector(".layer-panel-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.toggleLayerPanel(false));
        }
        // 固定/取消固定（固定到左侧智能体区域上半部分）
        const pinBtn = document.getElementById("layer-panel-pin");
        if (pinBtn) {
            pinBtn.addEventListener("click", () => {
                this._layerPanelPinned = !this._layerPanelPinned;
                localStorage.setItem("carto.layerPanel.pinned", this._layerPanelPinned ? "1" : "0");
                panel.classList.toggle("pinned", this._layerPanelPinned);
                if (!this._layerPanelPinned && this._layerPanelPos) {
                    panel.style.left = this._layerPanelPos.left + "px";
                    panel.style.top = this._layerPanelPos.top + "px";
                    panel.style.right = "auto";
                }
                pinBtn.classList.toggle("active", this._layerPanelPinned);
            });
        }
        // 拖拽移动（固定状态下不可拖）
        const header = panel.querySelector(".layer-panel-header");
        if (header) {
            header.addEventListener("mousedown", (e) => {
                if (this._layerPanelPinned) return;
                if (e.target.closest("button")) return;
                e.preventDefault();
                const rect = panel.getBoundingClientRect();
                const offX = e.clientX - rect.left;
                const offY = e.clientY - rect.top;
                panel.classList.add("dragging");
                const move = (ev) => {
                    panel.style.left = Math.max(4, ev.clientX - offX) + "px";
                    panel.style.top = Math.max(4, ev.clientY - offY) + "px";
                    panel.style.right = "auto";
                    panel.style.bottom = "auto";
                };
                const up = () => {
                    document.removeEventListener("mousemove", move);
                    document.removeEventListener("mouseup", up);
                    panel.classList.remove("dragging");
                    this._layerPanelPos = { left: parseInt(panel.style.left) || 0, top: parseInt(panel.style.top) || 0 };
                    try {
                        localStorage.setItem("carto.layerPanel.pos", JSON.stringify(this._layerPanelPos));
                    } catch (err) { /* ignore */ }
                };
                document.addEventListener("mousemove", move);
                document.addEventListener("mouseup", up);
            });
        }
        // 搜索过滤
        const searchInput = document.getElementById("layer-search-input");
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                this._layerSearch = (searchInput.value || "").trim().toLowerCase();
                this.updateLayerPanel();
            });
        }
        // 恢复位置/固定状态
        panel.classList.toggle("pinned", this._layerPanelPinned);
        if (pinBtn) pinBtn.classList.toggle("active", this._layerPanelPinned);
        if (!this._layerPanelPinned) {
            try {
                const pos = JSON.parse(localStorage.getItem("carto.layerPanel.pos") || "null");
                if (pos && typeof pos.left === "number") {
                    this._layerPanelPos = pos;
                    panel.style.left = pos.left + "px";
                    panel.style.top = pos.top + "px";
                    panel.style.right = "auto";
                }
            } catch (e) { /* ignore */ }
        }
    }

    /**
     * 切换图层管理面板显示
     * @param {boolean|null} show - 是否显示，null为切换
     */
    toggleLayerPanel(show = null) {
        const panel = document.getElementById("map-layer-panel");
        if (!panel) return;
        if (show === null) {
            panel.classList.toggle("hidden");
        } else {
            panel.classList.toggle("hidden", !show);
        }
    }

    /** 加载地图列表中的第一张有效地图（会话快照过期/删除时兜底） */
    async _loadFirstAvailableMap() {
        if (this._loadingFirstMap) return;
        this._loadingFirstMap = true;
        try {
            const resp = await API.listMaps();
            const maps = (resp && resp.data) || [];
            for (const m of maps) {
                const r = await API.getMap(m.map_id);
                if (r && r.success && r.data && r.data.layers) {
                    this._loadingFirstMap = false;
                    this.renderMap(r.data);
                    Utils.showToast("已加载地图: " + (r.data.name || ""), "info", 2000);
                    return;
                }
            }
        } catch (e) {
            console.warn("[MapPanel] 自动加载第一张地图失败:", e);
        }
        this._loadingFirstMap = false;
    }

    /**
     * 初始化编制说明弹窗（独立工具栏按钮，不占用图层管理面板）
     */
    initMetadataModal() {
        const btn = document.getElementById("toolbar-metadata");
        const modal = document.getElementById("map-metadata-modal");
        const closeBtn = document.getElementById("map-metadata-close");
        if (!btn || !modal) return;
        const open = () => {
            // 内容兜底：若尚未渲染（如直接打开），从当前地图数据生成
            const body = document.getElementById("map-metadata-body");
            if (body && !body.textContent.trim() && this.currentMapData) {
                this.renderMetadata(this.currentMapData.metadata);
            }
            modal.classList.remove("hidden");
            btn.classList.add("active");
        };
        const close = () => {
            modal.classList.add("hidden");
            btn.classList.remove("active");
        };
        btn.addEventListener("click", () => {
            if (modal.classList.contains("hidden")) open(); else close();
        });
        if (closeBtn) closeBtn.addEventListener("click", close);
        modal.addEventListener("click", (e) => {
            if (e.target === modal) close();
        });
    }

    /**
     * 任务参数侧边栏：展示/微调智能体规划出的制图参数（申请书2.4参数侧边栏）
     *  - 展示：地图名称/类型/区域/缩放/主题/中心/图层数
     *  - 微调：缩放、主题、中心坐标；"应用"即时生效，"重新生成"按参数重建
     */
    initParamsPanel() {
        const panel = document.getElementById("map-params-panel");
        const btn = document.getElementById("toolbar-params");
        if (!panel) return;
        const closeBtn = panel.querySelector(".params-panel-close");
        if (closeBtn) closeBtn.addEventListener("click", () => {
            panel.classList.add("hidden");
            if (btn) btn.classList.remove("active");
        });
        if (btn) btn.addEventListener("click", () => {
            panel.classList.toggle("hidden");
            btn.classList.toggle("active");
            this.updateParamsPanel();
        });
        const applyBtn = document.getElementById("params-apply");
        if (applyBtn) applyBtn.addEventListener("click", () => this._applyParams());
        const regenBtn = document.getElementById("params-regenerate");
        if (regenBtn) regenBtn.addEventListener("click", () => this._regenerateByParams());
    }

    updateParamsPanel() {
        const md = this.currentMapData;
        if (!md) return;
        const set = (id, v) => {
            const el = document.getElementById(id);
            if (el) el.value = v;
        };
        const setText = (id, v) => {
            const el = document.getElementById(id);
            if (el) el.textContent = v;
        };
        setText("params-map-name", md.name || "-");
        setText("params-map-type", md.map_type || "-");
        setText("params-region", md.region || "武汉市");
        setText("params-layer-count", (md.layers || []).length + " 层");
        set("params-zoom", md.zoom || 12);
        set("params-theme", md.theme || "plain");
        if (md.center && Array.isArray(md.center) && md.center.length === 2) {
            set("params-center-lat", md.center[0]);
            set("params-center-lng", md.center[1]);
        }
    }

    /** 应用参数侧边栏中的视图参数（缩放/主题/中心） */
    async _applyParams() {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        const zoom = parseInt(document.getElementById("params-zoom").value) || 12;
        const theme = document.getElementById("params-theme").value;
        const lat = parseFloat(document.getElementById("params-center-lat").value);
        const lng = parseFloat(document.getElementById("params-center-lng").value);
        try {
            await API.updateTheme(this.currentMapId, theme);
            await API.updateView(this.currentMapId, { center: [lat, lng], zoom });
            const resp = await API.getMap(this.currentMapId);
            if (resp.success && resp.data) {
                this.renderMap(resp.data);
                Utils.showToast("视图参数已应用", "success", 1500);
            }
        } catch (e) {
            Utils.showToast("应用参数失败: " + e.message, "error");
        }
    }

    /** 按参数侧边栏当前参数重新生成地图 */
    async _regenerateByParams() {
        if (!this.currentMapData) { Utils.showToast("请先生成地图", "warning"); return; }
        const zoom = parseInt(document.getElementById("params-zoom").value) || 12;
        const mapType = this.currentMapData.map_type || "basic";
        const region = this.currentMapData.region || "武汉市";
        Utils.showToast("正在按参数重新生成...", "info", 2000);
        try {
            const resp = await API.generateMap({ map_type: mapType, region, zoom });
            if (resp.success && resp.data) {
                this.renderMap(resp.data);
                Utils.showToast("地图已按参数重新生成", "success", 1800);
            } else {
                Utils.showToast(resp.message || "重新生成失败", "error");
            }
        } catch (e) {
            Utils.showToast("重新生成失败: " + e.message, "error");
        }
    }

    /**
     * 更新图层管理面板内容
     */
    /** 通用类型图标（无样式信息时的兜底） */
    _typeIcon(t) {
        if (t === "polyline" || t === "line") return '<i class="fa-solid fa-minus layer-type-icon"></i>';
        if (t === "polygon" || t === "area") return '<i class="fa-solid fa-square layer-type-icon"></i>';
        if (t === "circleMarker" || t === "marker" || t === "point") return '<i class="fa-solid fa-location-dot layer-type-icon"></i>';
        if (t === "textLabel" || t === "label") return '<i class="fa-solid fa-font layer-type-icon"></i>';
        return '<i class="fa-solid fa-layer-group layer-type-icon"></i>';
    }

    /**
     * 图层符号图标：按图层实际样式生成小图例（与地图上渲染一致）
     *   - 线要素（道路/市界/河流）：按颜色/线宽/虚线画一条线
     *   - 面要素（湖泊/居民地/底图）：按填充色+边框画方块
     *   - 点要素（POI/行政中心）：按颜色画实心圆
     *   - 注记：按颜色显示"文"字
     */
    _symbologyIcon(layerData) {
        const st = (layerData && layerData.style) || {};
        const t = (layerData && layerData.type) || "";
        const color = st.color || "#3388ff";
        const fill = st.fillColor || color;
        const w = Math.min(parseFloat(st.weight) || 2, 6);
        const op = st.opacity !== undefined ? st.opacity : 1;
        const fillOp = st.fillOpacity !== undefined ? st.fillOpacity : 0.6;
        const dash = st.dashArray || "";
        if (t === "polyline" || t === "line") {
            return `<svg class="layer-symbol" width="24" height="16" viewBox="0 0 24 16">
                <line x1="1" y1="8" x2="23" y2="8" stroke="${color}" stroke-width="${w}"
                      stroke-opacity="${op}" stroke-dasharray="${dash}" stroke-linecap="round"/></svg>`;
        }
        if (t === "polygon" || t === "area") {
            return `<svg class="layer-symbol" width="24" height="16" viewBox="0 0 24 16">
                <rect x="3" y="2" width="18" height="12" rx="2" fill="${fill}" fill-opacity="${fillOp}"
                      stroke="${color}" stroke-width="${Math.min(w, 3)}" stroke-opacity="${op}"/></svg>`;
        }
        if (t === "circleMarker" || t === "marker" || t === "point") {
            const radius = Math.min(parseFloat((st.radius) || 6), 8);
            return `<svg class="layer-symbol" width="24" height="16" viewBox="0 0 24 16">
                <circle cx="12" cy="8" r="${Math.max(4, radius * 0.8)}" fill="${fill}" fill-opacity="${fillOp}"
                        stroke="${color}" stroke-width="1.5" stroke-opacity="${op}"/></svg>`;
        }
        if (t === "textLabel" || t === "label") {
            return `<svg class="layer-symbol" width="24" height="16" viewBox="0 0 24 16">
                <text x="12" y="12.5" font-size="12" text-anchor="middle" fill="${color}"
                      font-family="sans-serif" font-weight="700">文</text></svg>`;
        }
        return this._typeIcon(t);
    }

    updateLayerPanel() {
        const container = document.getElementById("map-layer-list");
        if (!container) return;
        container.innerHTML = "";
        const layerEntries = Object.entries(this.layerGroups);
        if (layerEntries.length === 0) {
            container.innerHTML = '<div class="empty-hint">暂无图层</div>';
            return;
        }
        const countBadge = document.getElementById("layer-panel-count");
        if (countBadge) countBadge.textContent = layerEntries.length + " 层";
        // 图层分类（按制图叠置顺序：底图→行政区→水系→湖泊→居民地→等高线→道路→交通→POI→注记→其他）
        const CATS = [
            { key: "base", name: "底图", test: (n) => /陆地底图|省域|周边地市|市域底图|湖北省/.test(n) },
            { key: "admin", name: "行政区划", test: (n) => /政区|区县|边界|界$|行政中心|区划/.test(n) },
            { key: "water", name: "水系", test: (n) => /河流|水系|河道|中心线|大江|水面/.test(n) },
            { key: "lake", name: "湖泊", test: (n) => /湖泊/.test(n) },
            { key: "builtup", name: "居民地", test: (n) => /居民地/.test(n) },
            { key: "contour", name: "等高线", test: (n) => /等高线/.test(n) },
            { key: "road", name: "道路", test: (n) => n.indexOf("道路-") === 0 || /高速|国道|省道|主干道|次干道|支路|街巷/.test(n) },
            { key: "rail", name: "轨道/铁路", test: (n) => /轨道|铁路|地铁|轻轨/.test(n) },
            { key: "poi", name: "POI/符号", test: (n, t) => t === "circleMarker" || t === "marker" || t === "point" || t === "circle" },
            { key: "label", name: "注记/标注", test: (n, t) => t === "textLabel" || t === "label" || /注记|标注|地标名称/.test(n) },
            { key: "other", name: "其他", test: () => true },
        ];

        // 按用户调整顺序排序（默认沿用制图叠置顺序）
        const orderMap = new Map((this._layerOrder || []).map((id, i) => [id, i]));
        const ordered = layerEntries.slice().sort((a, b) => {
            const ia = orderMap.has(a[0]) ? orderMap.get(a[0]) : 1e9;
            const ib = orderMap.has(b[0]) ? orderMap.get(b[0]) : 1e9;
            return ia - ib;
        });

        const groups = CATS.map((c) => ({ ...c, items: [] }));
        const GROUP_MAP = {
            "底图": "base", "行政区划": "admin", "水系": "water", "湖泊": "lake",
            "居民地": "builtup", "等高线": "contour", "道路": "road",
            "轨道/铁路": "rail", "POI/符号": "poi", "注记/标注": "label", "其他": "other",
        };
        ordered.forEach(([layerId, item]) => {
            const n = item.data.name || "";
            const t = item.data.type || "";
            // 搜索过滤
            if (this._layerSearch && n.toLowerCase().indexOf(this._layerSearch) < 0) {
                return;
            }
            // 优先使用后端持久化的 group 分类（QGIS式图层分组）
            const gKey = GROUP_MAP[item.data.group];
            const g = (gKey && groups.find((grp) => grp.key === gKey))
                || groups.find((grp) => grp.test(n, t))
                || groups[groups.length - 1];
            g.items.push([layerId, item]);
        });

        // 道路子分组与等级排序（高速路网 → 城市主干道 → 城区道路 → 其他道路，高等级在上）
        const ROAD_SUBGROUP_ORDER = ["高速路网", "城市主干道", "城区道路", "其他道路"];
        const ROAD_CLASS_RANK = {
            motorway: 0, motorway_link: 1, trunk: 2, trunk_link: 3, primary: 4,
            primary_link: 5, secondary: 6, secondary_link: 7, tertiary: 8,
            tertiary_link: 9, residential: 10, living_street: 11, service: 12,
            unclassified: 13, other: 14,
        };
        const roadGroup = groups.find((x) => x.key === "road");
        if (roadGroup) {
            roadGroup.items.sort((a, b) => {
                const sa = ROAD_SUBGROUP_ORDER.indexOf(a[1].data.subgroup);
                const sb = ROAD_SUBGROUP_ORDER.indexOf(b[1].data.subgroup);
                if (sa !== sb) return (sa < 0 ? 99 : sa) - (sb < 0 ? 99 : sb);
                const ca = ROAD_CLASS_RANK[a[1].data.metadata && a[1].data.metadata.raw_class
                    || (a[1].data.properties && a[1].data.properties[0] && a[1].data.properties[0].subtype)] ?? 99;
                const cb = ROAD_CLASS_RANK[b[1].data.metadata && b[1].data.metadata.raw_class
                    || (b[1].data.properties && b[1].data.properties[0] && b[1].data.properties[0].subtype)] ?? 99;
                return ca - cb;
            });
        }

        groups.forEach((g) => {
            if (!g.items.length) return;
            const groupEl = document.createElement("div");
            groupEl.className = "layer-group";
            const locked = !!this._lockedGroups[g.key];
            const visibleCount = g.items.filter(([, it]) => it.visible).length;
            const collapsed = !!this._collapsedGroups[g.key];
            groupEl.innerHTML = `
                <div class="layer-group-header">
                    <button class="layer-group-collapse" title="${collapsed ? "展开" : "折叠"}">
                        <i class="fa-solid ${collapsed ? "fa-chevron-right" : "fa-chevron-down"}"></i>
                    </button>
                    <span class="layer-group-name">${Utils.escapeHtml(g.name)}
                        <span class="layer-group-count">${g.items.length}</span>
                    </span>
                    <span class="layer-group-actions">
                        <button class="layer-group-lock" title="${locked ? "解锁排序" : "锁定排序（防止误调整层级）"}">
                            <i class="fa-solid ${locked ? "fa-lock" : "fa-lock-open"}"></i>
                        </button>
                        <button class="layer-group-toggle" title="显示/隐藏本组">${visibleCount === g.items.length ? "全隐" : "全显"}</button>
                    </span>
                </div>
                <div class="layer-group-body"></div>
            `;
            const body = groupEl.querySelector(".layer-group-body");
            if (collapsed) body.style.display = "none";
            // 折叠/展开分组
            groupEl.querySelector(".layer-group-collapse").addEventListener("click", () => {
                this._collapsedGroups[g.key] = !this._collapsedGroups[g.key];
                try {
                    localStorage.setItem("carto.layerPanel.collapsed", JSON.stringify(this._collapsedGroups));
                } catch (e) { /* ignore */ }
                this.updateLayerPanel();
            });
            let lastSubgroup = null;
            g.items.forEach(([layerId, item]) => {
                // 子分组标题（道路等按 subgroup 细分）
                const sg = item.data.subgroup;
                if (sg && sg !== lastSubgroup) {
                    const sgEl = document.createElement("div");
                    sgEl.className = "layer-subgroup-header";
                    sgEl.textContent = sg;
                    body.appendChild(sgEl);
                    lastSubgroup = sg;
                }
                const div = document.createElement("div");
                div.className = "layer-item" + (item.visible ? "" : " off");
                const style = item.data.style || {};
                const color = style.fillColor || style.color || "#3388ff";
                const weight = style.weight ? `线宽 ${style.weight}` : "";
                const op = style.opacity !== undefined ? `不透明度 ${Math.round(style.opacity * 100)}%` : "";
                const cnt = (item.data.coordinates ? item.data.coordinates.length
                    : (item.data.features ? item.data.features.length : 0));
                const desc = item.data.metadata && item.data.metadata.description
                    ? item.data.metadata.description : "";
                div.innerHTML = `
                    <div class="layer-item-header">
                        <label class="layer-toggle" title="${Utils.escapeHtml((item.data.name || "") + (desc ? "（" + desc + "）" : ""))}">
                            <input type="checkbox" ${item.visible ? "checked" : ""} data-layer-id="${layerId}">
                            ${this._symbologyIcon(item.data)}
                            <span class="layer-color-dot" style="background:${color}"></span>
                            <span class="layer-name">${Utils.escapeHtml(item.data.name || "未命名图层")}</span>
                        </label>
                        <div class="layer-item-actions">
                            <button class="layer-act-btn" data-act="up" title="上移" ${locked ? "disabled" : ""}><i class="fa-solid fa-arrow-up"></i></button>
                            <button class="layer-act-btn" data-act="down" title="下移" ${locked ? "disabled" : ""}><i class="fa-solid fa-arrow-down"></i></button>
                            <button class="layer-act-btn" data-act="table" title="数据表格"><i class="fa-solid fa-table"></i></button>
                            <button class="layer-act-btn" data-act="export" title="导出GeoJSON"><i class="fa-solid fa-download"></i></button>
                            <button class="layer-act-btn" data-act="style" title="编辑样式"><i class="fa-solid fa-sliders"></i></button>
                        </div>
                    </div>
                    <div class="layer-item-type">
                        ${this._symbologyIcon(item.data)}${Utils.escapeHtml(item.data.type || "")}${cnt ? ` · ${cnt} 要素` : ""}
                        ${weight ? ` · ${weight}` : ""}${op ? ` · ${op}` : ""}
                    </div>
                `;
                div.querySelector("input[type=checkbox]").addEventListener("change", (e) => {
                    this.toggleLayer(layerId, e.target.checked);
                    this.updateLayerPanel();
                });
                div.querySelectorAll(".layer-act-btn").forEach((btn) => {
                    btn.addEventListener("click", () => {
                        const act = btn.dataset.act;
                        if (act === "up") this.reorderLayer(layerId, -1);
                        else if (act === "down") this.reorderLayer(layerId, 1);
                        else if (act === "table") this.showLayerData(layerId);
                        else if (act === "export") this.exportLayer(layerId);
                        else if (act === "style") this.showLayerStyleEditor(layerId);
                    });
                });
                body.appendChild(div);
            });
            // 组内全显/全隐
            groupEl.querySelector(".layer-group-toggle").addEventListener("click", () => {
                const allVisible = g.items.every(([, it]) => it.visible);
                g.items.forEach(([id]) => {
                    if (this.layerGroups[id] && this.layerGroups[id].visible === allVisible) {
                        this.toggleLayer(id, !allVisible);
                    }
                });
                this.updateLayerPanel();
            });
            // 锁定/解锁分组排序
            groupEl.querySelector(".layer-group-lock").addEventListener("click", () => {
                this._lockedGroups[g.key] = !this._lockedGroups[g.key];
                this.updateLayerPanel();
            });
            container.appendChild(groupEl);
        });
    }

    /**
     * 调整图层顺序（上移/下移），并重新按序叠加
     * @param {string} layerId - 图层ID
     * @param {number} dir - -1上移 / 1下移
     */
    reorderLayer(layerId, dir) {
        if (!this._layerOrder || !this.layerGroups[layerId]) return;
        // 分组锁定：防止误调整高等级道路等关键层级
        const _GM = {
            "底图": "base", "行政区划": "admin", "水系": "water", "湖泊": "lake",
            "居民地": "builtup", "等高线": "contour", "道路": "road",
            "轨道/铁路": "rail", "POI/符号": "poi", "注记/标注": "label", "其他": "other",
        };
        const _gk = _GM[this.layerGroups[layerId].data.group];
        if (this._lockedGroups[_gk]) {
            Utils.showToast("该分组已锁定排序，先解锁再调整", "warning", 2200);
            return;
        }
        const i = this._layerOrder.indexOf(layerId);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= this._layerOrder.length) {
            Utils.showToast("已到边界", "info", 1200);
            return;
        }
        const tmp = this._layerOrder[i];
        this._layerOrder[i] = this._layerOrder[j];
        this._layerOrder[j] = tmp;
        // 按新顺序重新叠加（同 pane 内后添加者在上）
        this._layerOrder.forEach((id) => {
            const item = this.layerGroups[id];
            if (item && item.layer && item.visible) this.map.removeLayer(item.layer);
        });
        this._layerOrder.forEach((id) => {
            const item = this.layerGroups[id];
            if (item && item.layer && item.visible) item.layer.addTo(this.map);
        });
        this.updateLayerPanel();
    }

    /**
     * 查看图层数据表格（属性表）
     * @param {string} layerId - 图层ID
     */
    showLayerData(layerId) {
        const item = this.layerGroups[layerId];
        if (!item) return;
        const layer = item.data;
        const modal = document.getElementById("layer-data-modal");
        const title = document.getElementById("layer-data-title");
        const meta = document.getElementById("layer-data-meta");
        const thead = modal.querySelector("thead");
        const tbody = modal.querySelector("tbody");
        if (!modal) return;

        title.textContent = (layer.name || "图层") + " · 数据表格";
        const coords = layer.coordinates || [];
        const props = layer.properties || [];
        const feats = layer.features || [];
        const n = Math.max(coords.length, feats.length);

        // 动态列：通用属性 + 图层自带属性键
        const propKeys = new Set(["name", "subtype", "ele", "area_km2", "index", "category", "waterway", "level", "value"]);
        const allProps = (props && props.length) ? props : feats.map(f => f.properties || {});
        allProps.forEach(p => {
            Object.keys(p || {}).forEach(k => propKeys.add(k));
        });
        const columns = ["#", ...Array.from(propKeys), "要素点数", "操作"];
        thead.innerHTML = `<tr>${columns.map(c => `<th>${Utils.escapeHtml(c)}</th>`).join("")}</tr>`;
        const isPoint = layer.type === "circleMarker" || layer.type === "marker" || layer.type === "point";

        const rows = [];
        for (let i = 0; i < n; i++) {
            const p = (props && props[i]) || (feats[i] && feats[i].properties) || {};
            const count = coords[i] ? (Array.isArray(coords[i][0]) ? coords[i].length : 1) : 0;
            const cells = columns.map((c) => {
                if (c === "#") return `<td>${i + 1}</td>`;
                if (c === "要素点数") return `<td>${count}</td>`;
                if (c === "操作") return `<td><button class="table-del-row" data-row="${i}" title="删除该要素">🗑</button></td>`;
                const v = p[c];
                const val = v === undefined || v === null ? "" : String(v);
                return `<td class="cell-editable" contenteditable="true" data-row="${i}" data-col="${Utils.escapeHtml(c)}"
                            title="双击编辑属性">${Utils.escapeHtml(val)}</td>`;
            });
            rows.push(`<tr>${cells.join("")}</tr>`);
        }
        const addBtn = isPoint
            ? `<button id="table-add-point" class="table-add-point">＋ 添加点要素</button>` : "";
        meta.innerHTML = `共 ${n} 条记录 · 类型 ${Utils.escapeHtml(layer.type || "-")} ·
            <span class="table-edit-hint">（双击单元格编辑，自动保存）</span> ${addBtn}`;
        tbody.innerHTML = rows.join("") || '<tr><td colspan="99" class="empty-hint">暂无数据</td></tr>';

        tbody.querySelectorAll(".cell-editable").forEach((cell) => {
            cell.addEventListener("blur", () => this._saveTableEdit(layerId, cell));
            cell.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    cell.blur();
                }
            });
        });
        tbody.querySelectorAll(".table-del-row").forEach((btn) => {
            btn.addEventListener("click", () => this._deleteTableRow(layerId, Number(btn.dataset.row)));
        });
        const addBtnEl = document.getElementById("table-add-point");
        if (addBtnEl) addBtnEl.addEventListener("click", () => this._addTablePoint(layerId));
        modal.classList.remove("hidden");
        const closeBtn = document.getElementById("layer-data-close");
        closeBtn.onclick = () => modal.classList.add("hidden");
        modal.addEventListener("click", (e) => {
            if (e.target === modal) modal.classList.add("hidden");
        });
    }

    /** 属性表单元格编辑保存（QGIS/ArcGIS 属性表） */
    _saveTableEdit(layerId, cell) {
        const item = this.layerGroups[layerId];
        if (!item || !this.currentMapId) return;
        const row = Number(cell.dataset.row);
        const col = cell.dataset.col;
        let raw = (cell.textContent || "").trim();
        if (raw !== "" && !isNaN(Number(raw))) raw = Number(raw);
        const props = (item.data.properties || []).slice().map(p => ({ ...p }));
        if (!props[row]) props[row] = {};
        props[row][col] = raw;
        item.data.properties = props;
        API.updateLayerGeometry(this.currentMapId, layerId, { properties: props })
            .then(() => Utils.showToast(`属性已保存: ${col} = ${String(raw).slice(0, 30)}`, "success", 1500))
            .catch((e) => Utils.showToast("属性保存失败: " + e.message, "error"));
    }

    /** 属性表删除一行（QGIS/ArcGIS 属性表） */
    _deleteTableRow(layerId, row) {
        const item = this.layerGroups[layerId];
        if (!item || !this.currentMapId) return;
        if (!window.confirm("确定删除该要素？")) return;
        const coords = (item.data.coordinates || []).slice();
        const props = (item.data.properties || []).slice();
        const feats = (item.data.features || []).slice();
        if (row < coords.length) coords.splice(row, 1);
        if (row < props.length) props.splice(row, 1);
        if (row < feats.length) feats.splice(row, 1);
        const payload = {};
        if (item.data.coordinates) payload.coordinates = coords;
        if (item.data.properties) payload.properties = props;
        if (item.data.features) payload.features = feats;
        API.updateLayerGeometry(this.currentMapId, layerId, payload).then(() => {
            item.data.coordinates = coords;
            item.data.properties = props;
            item.data.features = feats;
            this.map.removeLayer(item.layer);
            this.renderLayer(Object.assign({}, item.data, { _lodVisible: true }));
            this.showLayerData(layerId);
            Utils.showToast("要素已删除", "success", 1500);
        }).catch((e) => Utils.showToast("删除失败: " + e.message, "error"));
    }

    /** 属性表添加点要素（QGIS/ArcGIS 属性表） */
    _addTablePoint(layerId) {
        const item = this.layerGroups[layerId];
        if (!item || !this.currentMapId) return;
        const lat = prompt("纬度 (lat):", "30.5928");
        if (lat === null) return;
        const lng = prompt("经度 (lng):", "114.3055");
        if (lng === null) return;
        const name = prompt("名称:", "新标注") || "新标注";
        const coords = (item.data.coordinates || []).slice();
        const props = (item.data.properties || []).slice();
        coords.push([parseFloat(lat), parseFloat(lng)]);
        props.push({ name });
        const payload = {};
        if (item.data.coordinates) payload.coordinates = coords;
        if (item.data.properties) payload.properties = props;
        API.updateLayerGeometry(this.currentMapId, layerId, payload).then(() => {
            item.data.coordinates = coords;
            item.data.properties = props;
            this.map.removeLayer(item.layer);
            this.renderLayer(Object.assign({}, item.data, { _lodVisible: true }));
            this.showLayerData(layerId);
            Utils.showToast("已添加点要素", "success", 1500);
        }).catch((e) => Utils.showToast("添加失败: " + e.message, "error"));
    }

    /**
     * 导出单个图层为 GeoJSON 文件
     * @param {string} layerId - 图层ID
     */
    exportLayer(layerId) {
        const item = this.layerGroups[layerId];
        if (!item) return;
        const layer = item.data;
        const features = [];
        const coords = layer.coordinates || [];
        const props = layer.properties || [];
        const feats = layer.features || [];
        const toLngLat = (p) => [Number(p[1]), Number(p[0])];

        if (coords.length) {
            coords.forEach((c, i) => {
                const prop = (props && props[i]) || {};
                let geometry = null;
                if (layer.type === "polygon" || layer.type === "area") {
                    const rings = Array.isArray(c) && Array.isArray(c[0]) && Array.isArray(c[0][0])
                        ? c.map(r => r.map(toLngLat)) : [c.map(toLngLat)];
                    geometry = { type: "Polygon", coordinates: rings };
                } else if (layer.type === "polyline" || layer.type === "line") {
                    geometry = { type: "LineString", coordinates: c.map(toLngLat) };
                } else {
                    geometry = { type: "Point", coordinates: toLngLat(c) };
                }
                features.push({ type: "Feature", properties: prop, geometry });
            });
        } else if (feats.length) {
            feats.forEach(f => {
                if (f.geometry) features.push({ type: "Feature", properties: f.properties || {}, geometry: f.geometry });
            });
        }
        const fc = {
            type: "FeatureCollection",
            name: layer.name || "图层",
            features,
            properties: { layer_id: layerId, source: "carto-agent" },
        };
        const blob = new Blob([JSON.stringify(fc)], { type: "application/geo+json;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `图层_${(layer.name || "layer").replace(/[\\/:*?"<>|]/g, "_")}.geojson`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            URL.revokeObjectURL(a.href);
            a.remove();
        }, 200);
        Utils.showToast(`已导出图层: ${layer.name || ""}（${features.length} 要素）`, "success", 2500);
    }

    /**
     * 切换图层可见性
     * @param {string} layerId - 图层ID
     * @param {boolean} visible - 是否可见
     */
    toggleLayer(layerId, visible) {
        const item = this.layerGroups[layerId];
        if (!item) return;
        if (visible) {
            item.layer.addTo(this.map);
        } else {
            this.map.removeLayer(item.layer);
        }
        item.visible = visible;
        // 持久化可见性（QGIS式隐藏状态写入地图数据）
        if (this.currentMapId) {
            API.setLayerVisible(this.currentMapId, layerId, visible).catch(() => {
                // 网络失败仅提示，不影响当前会话
                Utils.showToast("可见性保存失败（离线状态仅本次生效）", "warning", 2000);
            });
        }
    }

    /**
     * 显示图层样式编辑器
     * @param {string} layerId - 图层ID
     */
    showLayerStyleEditor(layerId) {
        const item = this.layerGroups[layerId];
        if (!item) return;
        const style = item.data.style || {};
        const isPoly = item.data.type === "polygon" || item.data.type === "area";
        const editor = document.getElementById("map-style-editor");
        if (!editor) return;
        // 样式模板（QGIS 式一键套用）
        const TEMPLATES = {
            "": { name: "自定义" },
            "highway": { name: "高速公路", color: "#F97316", weight: 4, opacity: 1, dash: "" },
            "arterial": { name: "城市主干道", color: "#EA580C", weight: 3, opacity: 1, dash: "" },
            "street": { name: "街区道路", color: "#B9C4D0", weight: 1.2, opacity: 0.85, dash: "" },
            "water": { name: "水系", color: "#2f7fd0", weight: 2, opacity: 0.9, dash: "6,4" },
            "lake": { name: "湖泊", color: "#1d5fa8", fillColor: "#4a90d9", fillOpacity: 0.55, weight: 1.2, opacity: 0.9, dash: "" },
        };
        editor.innerHTML = `
            <div class="style-editor-header">
                <span><i class="fa-solid fa-sliders"></i> 图层样式: ${Utils.escapeHtml(item.data.name || "")}</span>
                <button class="style-editor-close"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="style-editor-body">
                <div class="style-field style-field-template">
                    <label>样式模板（一键套用）</label>
                    <select id="style-template">
                        ${Object.entries(TEMPLATES).map(([k, v]) =>
                            `<option value="${k}">${Utils.escapeHtml(v.name)}</option>`).join("")}
                    </select>
                </div>
                <div class="style-preview" id="style-preview" title="样式预览"></div>
                <div class="style-section">
                    <div class="style-section-title">色彩</div>
                    <div class="style-field">
                        <label>线条颜色</label>
                        <input type="color" id="style-color" value="${style.color || "#3388ff"}">
                    </div>
                    ${isPoly ? `
                    <div class="style-field">
                        <label>填充颜色</label>
                        <input type="color" id="style-fillColor" value="${style.fillColor || "#4a90d9"}">
                    </div>` : ""}
                </div>
                <div class="style-section">
                    <div class="style-section-title">线宽与虚实</div>
                    <div class="style-field">
                        <label>线宽: <span id="weight-value">${style.weight || 3}</span> px</label>
                        <input type="range" id="style-weight" min="1" max="12" value="${style.weight || 3}">
                    </div>
                    <div class="style-field">
                        <label>线型</label>
                        <select id="style-dashArray">
                            <option value="" ${!style.dashArray ? "selected" : ""}>实线</option>
                            <option value="5,5" ${style.dashArray === "5,5" ? "selected" : ""}>短虚线</option>
                            <option value="10,5" ${style.dashArray === "10,5" ? "selected" : ""}>长虚线</option>
                            <option value="5,10" ${style.dashArray === "5,10" ? "selected" : ""}>点线</option>
                        </select>
                    </div>
                </div>
                <div class="style-section">
                    <div class="style-section-title">不透明度（值越大越清晰）</div>
                    <div class="style-field">
                        <label>线条不透明度: <span id="opacity-value">${(style.opacity !== undefined ? style.opacity : 1).toFixed(2)}</span></label>
                        <input type="range" id="style-opacity" min="0" max="1" step="0.05" value="${style.opacity !== undefined ? style.opacity : 1}">
                    </div>
                    ${isPoly ? `
                    <div class="style-field">
                        <label>填充不透明度: <span id="fill-value">${(style.fillOpacity !== undefined ? style.fillOpacity : 0.55).toFixed(2)}</span></label>
                        <input type="range" id="style-fillOpacity" min="0" max="1" step="0.05" value="${style.fillOpacity !== undefined ? style.fillOpacity : 0.55}">
                    </div>` : ""}
                </div>
                <div class="style-field style-field-group-apply">
                    <label class="style-group-apply-label">
                        <input type="checkbox" id="style-group-apply"> 同时应用到同组图层（如全部道路）
                    </label>
                </div>
                <button class="style-apply-btn" id="style-apply-btn"><i class="fa-solid fa-check"></i> 应用样式</button>
            </div>
        `;
        editor.classList.remove("hidden");

        const $ = (id) => document.getElementById(id);
        const previewEl = $("style-preview");
        const refreshPreview = () => {
            const color = $("style-color").value;
            const weight = parseInt($("style-weight").value) || 1;
            const op = parseFloat($("style-opacity").value) || 1;
            const dash = $("style-dashArray").value || "none";
            const fill = isPoly ? ($("style-fillColor") ? $("style-fillColor").value : "#4a90d9") : "none";
            const fillOp = isPoly ? (parseFloat($("style-fillOpacity").value) || 0) : 0;
            previewEl.innerHTML = `<svg width="100%" height="54" viewBox="0 0 260 54" preserveAspectRatio="xMidYMid meet">
                ${isPoly
                    ? `<rect x="24" y="7" width="212" height="40" rx="5" fill="${fill}" fill-opacity="${fillOp}"
                         stroke="${color}" stroke-width="${weight}" stroke-opacity="${op}" stroke-dasharray="${dash}"/>`
                    : `<line x1="12" y1="27" x2="248" y2="27" stroke="${color}" stroke-width="${weight}"
                         stroke-opacity="${op}" stroke-dasharray="${dash}" stroke-linecap="round"/>`}
            </svg>`;
        };
        // 实时显示数值
        const weightInput = $("style-weight");
        const weightValue = $("weight-value");
        weightInput.addEventListener("input", (e) => {
            weightValue.textContent = e.target.value;
            refreshPreview();
        });
        const opacityInput = $("style-opacity");
        const opacityValue = $("opacity-value");
        opacityInput.addEventListener("input", (e) => {
            opacityValue.textContent = parseFloat(e.target.value).toFixed(2);
            refreshPreview();
        });
        if (isPoly) {
            const fillInput = $("style-fillOpacity");
            const fillValue = $("fill-value");
            fillInput.addEventListener("input", (e) => {
                fillValue.textContent = parseFloat(e.target.value).toFixed(2);
                refreshPreview();
            });
            $("style-fillColor").addEventListener("input", refreshPreview);
        }
        $("style-color").addEventListener("input", refreshPreview);
        $("style-dashArray").addEventListener("change", refreshPreview);
        // 模板套用
        $("style-template").addEventListener("change", (e) => {
            const t = TEMPLATES[e.target.value];
            if (!t || !t.color) return;
            $("style-color").value = t.color;
            if (isPoly && t.fillColor) $("style-fillColor").value = t.fillColor;
            $("style-weight").value = t.weight;
            $("style-opacity").value = t.opacity;
            weightValue.textContent = t.weight;
            opacityValue.textContent = t.opacity.toFixed(2);
            $("style-dashArray").value = t.dash || "";
            if (isPoly && t.fillOpacity !== undefined) {
                $("style-fillOpacity").value = t.fillOpacity;
                $("fill-value").textContent = t.fillOpacity.toFixed(2);
            }
            refreshPreview();
        });
        refreshPreview();
        // 关闭按钮
        editor.querySelector(".style-editor-close").addEventListener("click", () => {
            editor.classList.add("hidden");
        });
        // ===== 实时预览地图图层 =====
        const previewStyle = () => {
            const item = this.layerGroups[layerId];
            if (!item || !item.layer) return;
            const previewStyleData = {
                color: $("style-color").value,
                weight: parseInt($("style-weight").value) || 1,
                opacity: parseFloat($("style-opacity").value) || 1,
                fillOpacity: isPoly ? (parseFloat($("style-fillOpacity").value) || 0) : undefined,
                dashArray: $("style-dashArray").value || null
            };
            try {
                if (item.layer.setStyle) {
                    item.layer.setStyle(previewStyleData);
                } else if (item.layer.eachLayer) {
                    item.layer.eachLayer(sub => { if (sub.setStyle) sub.setStyle(previewStyleData); });
                }
            } catch (e) { /* 预览失败忽略 */ }
        };
        // 绑定实时预览事件
        ["style-color", "style-weight", "style-opacity", "style-dashArray"].forEach(id => {
            const el = $(id);
            if (el) {
                el.addEventListener("input", previewStyle);
            }
        });
        // 应用样式按钮
        $("style-apply-btn").addEventListener("click", () => {
            const newStyle = {
                color: $("style-color").value,
                weight: parseInt($("style-weight").value),
                opacity: parseFloat($("style-opacity").value),
                dashArray: $("style-dashArray").value || null
            };
            if (isPoly) {
                newStyle.fillColor = $("style-fillColor").value;
                newStyle.fillOpacity = parseFloat($("style-fillOpacity").value);
            }
            const applyGroup = $("style-group-apply") && $("style-group-apply").checked;
            if (applyGroup) {
                const sameGroup = Object.entries(this.layerGroups)
                    .filter(([, it]) => it.data.group === item.data.group)
                    .map(([id]) => id);
                this.updateLayersStyle(sameGroup, newStyle);
            } else {
                this.updateLayerStyle(layerId, newStyle);
            }
            editor.classList.add("hidden");
        });
    }

    /**
     * 批量更新图层样式（同组图层统一样式）
     */
    async updateLayersStyle(layerIds, style) {
        if (!this.currentMapId || !layerIds || !layerIds.length) return;
        try {
            let last = null;
            for (const id of layerIds) {
                last = await API.updateLayerStyle(this.currentMapId, id, style);
            }
            if (last && last.success && last.data) {
                Utils.showToast(`已更新 ${layerIds.length} 个图层样式`, "success", 1800);
                this.renderMap(last.data);
            } else {
                Utils.showToast((last && last.message) || "样式更新失败", "error");
            }
        } catch (e) {
            Utils.showToast("样式更新失败: " + e.message, "error");
        }
    }

    /**
     * 初始化自然语言修改输入框
     */
    initModifyInput() {
        const input = document.getElementById("map-modify-input");
        const btn = document.getElementById("map-modify-btn");
        if (!input || !btn) return;
        // 发送修改指令
        const sendModify = async () => {
            const instruction = input.value.trim();
            if (!instruction) return;
            if (!this.currentMapId) {
                Utils.showToast("请先生成地图", "warning");
                return;
            }
            // 防重复提交
            if (this.isModifying) {
                Utils.showToast("正在执行修改，请稍候", "warning");
                return;
            }
            this.isModifying = true;
            btn.disabled = true;
            btn.innerHTML = '<div class="btn-spinner"></div>';
            try {
                const result = await API.modifyMap(this.currentMapId, instruction);
                // 解包 ApiResponse -> 修改结果
                const inner = (result && result.data && typeof result.data === "object")
                    ? result.data : result;
                if (inner && inner.success === false) {
                    Utils.showToast(inner.response || "无法理解修改指令", "error");
                    return;
                }
                const md = (inner && inner.map_data) || (result && result.map_data);
                if (md) {
                    this.renderMap(md);
                }
                Utils.showToast((inner && inner.response) || "修改指令已执行", "success");
                if (md) input.value = "";
            } catch (error) {
                Utils.showToast("修改失败: " + error.message, "error");
            } finally {
                this.isModifying = false;
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i>';
            }
        };
        btn.addEventListener("click", sendModify);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendModify();
        });
    }

    /**
     * 重置视图到默认或地图数据指定的视图
     */
    resetView() {
        if (this.currentMapData && this.currentMapData.center) {
            this.map.setView(this.currentMapData.center, this.currentMapData.zoom || CONFIG.defaultZoom);
        } else {
            this.map.setView(CONFIG.defaultMapCenter, CONFIG.defaultZoom);
        }
        Utils.showToast("视图已重置", "info", 1500);
    }

    /**
     * 切换全屏
     */
    toggleFullscreen() {
        const mapContainer = document.getElementById("map-panel");
        if (!mapContainer) return;
        if (!document.fullscreenElement) {
            mapContainer.requestFullscreen().catch(err => {
                Utils.showToast("全屏失败: " + err.message, "error");
            });
        } else {
            document.exitFullscreen();
        }
    }

    /**
     * 显示导出菜单
     */
    showExportMenu() {
        if (!this.currentMapId) {
            Utils.showToast("请先生成地图", "warning");
            return;
        }
        // 创建导出菜单
        const menu = document.createElement("div");
        menu.className = "export-menu";
        menu.innerHTML = `
            <div class="export-menu-overlay"></div>
            <div class="export-menu-dialog">
                <div class="export-menu-header">
                    <span>导出地图</span>
                    <button class="export-menu-close"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="export-menu-body">
                    <button class="export-option" data-format="geojson">
                        <i class="fa-solid fa-file-code"></i>
                        <div>
                            <span class="export-option-name">GeoJSON</span>
                            <span class="export-option-desc">矢量数据格式</span>
                        </div>
                    </button>
                    <button class="export-option" data-format="png">
                        <i class="fa-solid fa-image"></i>
                        <div>
                            <span class="export-option-name">PNG图片</span>
                            <span class="export-option-desc">栅格图片格式</span>
                        </div>
                    </button>
                    <button class="export-option" data-format="svg">
                        <i class="fa-solid fa-bezier-curve"></i>
                        <div>
                            <span class="export-option-name">SVG矢量图</span>
                            <span class="export-option-desc">可缩放矢量图形</span>
                        </div>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(menu);
        // 关闭菜单
        const closeMenu = () => menu.remove();
        menu.querySelector(".export-menu-overlay").addEventListener("click", closeMenu);
        menu.querySelector(".export-menu-close").addEventListener("click", closeMenu);
        // 导出选项点击
        menu.querySelectorAll(".export-option").forEach(btn => {
            btn.addEventListener("click", async () => {
                const format = btn.dataset.format;
                closeMenu();
                await this.exportMap(format);
            });
        });
    }

    /**
     * 更新状态栏
     * @param {string|null} lat - 纬度
     * @param {string|null} lng - 经度
     */
    updateStatusBar(lat = null, lng = null) {
        if (!this.map) return;
        const center = this.map.getCenter();
        const zoom = this.map.getZoom();
        const latEl = document.getElementById("map-status-lat");
        const lngEl = document.getElementById("map-status-lng");
        const zoomEl = document.getElementById("map-status-zoom");
        // 坐标合理性保护：非Web墨卡托投影逆算或异常值时，回退到后端已知中心（武汉30°N/114°E）
        let _lat = lat !== null && lat !== undefined ? lat : center.lat;
        let _lng = lng !== null && lng !== undefined ? lng : center.lng;
        if (!(Math.abs(_lat) <= 90 && Math.abs(_lng) <= 180)) {
            const _c = this.currentMapData && this.currentMapData.center;
            if (_c && _c.length >= 2) { _lat = _c[0]; _lng = _c[1]; }
        }
        if (latEl) latEl.textContent = Number(_lat).toFixed(4) + "°";
        if (lngEl) lngEl.textContent = Number(_lng).toFixed(4) + "°";
        if (zoomEl) zoomEl.textContent = "缩放 " + Number(zoom).toFixed(2);
    }

    /**
     * 更新地图信息显示
     * @param {string} name - 地图名称
     */
    updateMapInfo(name) {
        const nameEl = document.getElementById("map-status-name");
        if (nameEl) nameEl.textContent = name || "未命名地图";
        const layerCountEl = document.getElementById("map-status-layers");
        if (layerCountEl) layerCountEl.textContent = Object.keys(this.layerGroups).length + " 个图层";
    }

    /**
     * 设置地图视图
     * @param {array} center - 中心点 [lat, lng]
     * @param {number} zoom - 缩放级别
     */
    setView(center, zoom) {
        if (this.map && center) {
            this.map.setView(center, zoom || this.map.getZoom());
        }
    }

    // ==================== 路径规划 ====================
    /**
     * 初始化路径规划面板
     */
    initRoutePanel() {
        const panel = document.getElementById("map-route-panel");
        if (!panel) return;
        // 关闭按钮
        const closeBtn = panel.querySelector(".route-panel-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.toggleRoutePanel(false));
        }
        // 出行方式选择
        panel.querySelectorAll(".route-profile-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                panel.querySelectorAll(".route-profile-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.selectedProfile = btn.dataset.profile;
            });
        });
        // 起点输入框 - 点击时进入选点模式
        const startLat = document.getElementById("route-start-lat");
        const startLng = document.getElementById("route-start-lng");
        if (startLat && startLng) {
            const enterStartMode = () => {
                this.routePointMode = "start";
                this.map.getContainer().style.cursor = "crosshair";
                Utils.showToast("请在地图上点击起点", "info", 2000);
            };
            startLat.addEventListener("focus", enterStartMode);
            startLng.addEventListener("focus", enterStartMode);
        }
        // 终点输入框 - 点击时进入选点模式
        const endLat = document.getElementById("route-end-lat");
        const endLng = document.getElementById("route-end-lng");
        if (endLat && endLng) {
            const enterEndMode = () => {
                this.routePointMode = "end";
                this.map.getContainer().style.cursor = "crosshair";
                Utils.showToast("请在地图上点击终点", "info", 2000);
            };
            endLat.addEventListener("focus", enterEndMode);
            endLng.addEventListener("focus", enterEndMode);
        }
        // 规划按钮
        const planBtn = document.getElementById("route-plan-btn");
        if (planBtn) {
            planBtn.addEventListener("click", () => this.planRoute());
        }
    }

    /**
     * 切换路径规划面板显示
     * @param {boolean|null} show - 是否显示
     */
    toggleRoutePanel(show = null) {
        const panel = document.getElementById("map-route-panel");
        if (!panel) return;
        if (show === null) {
            panel.classList.toggle("hidden");
        } else {
            panel.classList.toggle("hidden", !show);
        }
    }

    /**
     * 设置路径起终点坐标
     * @param {string} type - "start" 或 "end"
     * @param {array} coords - [lat, lng]
     */
    setRoutePoint(type, coords) {
        const latEl = document.getElementById(`route-${type}-lat`);
        const lngEl = document.getElementById(`route-${type}-lng`);
        if (latEl) latEl.value = coords[0].toFixed(6);
        if (lngEl) lngEl.value = coords[1].toFixed(6);
        // 更新地图上的标记
        this.updateRouteMarkers();
        Utils.showToast(`${type === "start" ? "起点" : "终点"}已设置`, "success", 1500);
    }

    /**
     * 更新路径起终点标记
     */
    updateRouteMarkers() {
        // 清除旧标记
        this.routeMarkers.forEach(m => this.map.removeLayer(m));
        this.routeMarkers = [];
        const startLat = parseFloat(document.getElementById("route-start-lat")?.value);
        const startLng = parseFloat(document.getElementById("route-start-lng")?.value);
        const endLat = parseFloat(document.getElementById("route-end-lat")?.value);
        const endLng = parseFloat(document.getElementById("route-end-lng")?.value);
        // 起点标记
        if (!isNaN(startLat) && !isNaN(startLng)) {
            const startMarker = L.marker([startLat, startLng], {
                icon: L.divIcon({
                    html: '<div style="width:16px;height:16px;background:#22c55e;border:2px solid #fff;border-radius:50%;box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                })
            }).bindPopup("起点");
            startMarker.addTo(this.map);
            this.routeMarkers.push(startMarker);
        }
        // 终点标记
        if (!isNaN(endLat) && !isNaN(endLng)) {
            const endMarker = L.marker([endLat, endLng], {
                icon: L.divIcon({
                    html: '<div style="width:16px;height:16px;background:#ef4444;border:2px solid #fff;border-radius:50%;box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                })
            }).bindPopup("终点");
            endMarker.addTo(this.map);
            this.routeMarkers.push(endMarker);
        }
    }

    /**
     * 在地图上渲染路径
     * @param {object} routeData - 路径数据
     */
    renderRoute(routeData) {
        // 清除旧路径
        this.clearRoute();
        if (!routeData.coordinates || routeData.coordinates.length === 0) return;
        // 绘制路径线
        this.routeLayer = L.polyline(routeData.coordinates, {
            color: "#3b82f6",
            weight: 5,
            opacity: 0.8,
            lineJoin: "round",
            lineCap: "round"
        }).addTo(this.map);
        // 添加路径弹窗
        const distance = (routeData.distance / 1000).toFixed(2);
        const duration = Math.round(routeData.duration / 60);
        this.routeLayer.bindPopup(`
            <div style="font-size:13px;">
                <strong>${routeData.profile_name || routeData.profile}</strong><br>
                距离: ${distance} km<br>
                预计时间: ${duration} 分钟
            </div>
        `);
        // 调整地图视图以显示完整路径
        this.map.fitBounds(this.routeLayer.getBounds(), { padding: [50, 50] });
    }

    /**
     * 显示路径规划结果信息
     * @param {object} routeData - 路径数据
     */
    showRouteResult(routeData) {
        const resultEl = document.getElementById("route-result");
        if (!resultEl) return;
        const distance = (routeData.distance / 1000).toFixed(2);
        const duration = Math.round(routeData.duration / 60);
        const sourceLabel = routeData.source === "osrm" ? "OSRM实时路径" : "直线估算";
        const steps = routeData.steps || [];
        let stepsHtml = "";
        if (steps.length > 0) {
            stepsHtml = `
                <div class="route-steps">
                    <div class="route-steps-title">导航步骤</div>
                    ${steps.map((step, i) => `
                        <div class="route-step">
                            <span class="route-step-num">${i + 1}</span>
                            <span class="route-step-text">${Utils.escapeHtml(step.instruction || "继续")}</span>
                            <span class="route-step-dist">${(step.distance / 1000).toFixed(2)}km</span>
                        </div>
                    `).join("")}
                </div>
            `;
        }
        resultEl.innerHTML = `
            <div class="route-result-header">
                <i class="fa-solid fa-${routeData.profile === 'driving' ? 'car' : routeData.profile === 'walking' ? 'person-walking' : 'bicycle'}"></i>
                <span>${routeData.profile_name || routeData.profile}</span>
                <span class="route-source">${sourceLabel}</span>
            </div>
            <div class="route-result-stats">
                <div class="route-stat">
                    <span class="route-stat-label">距离</span>
                    <span class="route-stat-value">${distance} km</span>
                </div>
                <div class="route-stat">
                    <span class="route-stat-label">预计时间</span>
                    <span class="route-stat-value">${duration} 分钟</span>
                </div>
                <div class="route-stat">
                    <span class="route-stat-label">坐标点数</span>
                    <span class="route-stat-value">${routeData.coordinates.length}</span>
                </div>
            </div>
            ${stepsHtml}
            <button class="route-clear-btn" onclick="window.app.mapPanel.clearRoute()">
                <i class="fa-solid fa-trash"></i> 清除路径
            </button>
        `;
        resultEl.classList.remove("hidden");
    }

    /**
     * 清除路径规划和标记
     */
    clearRoute() {
        // 清除路径线
        if (this.routeLayer) {
            this.map.removeLayer(this.routeLayer);
            this.routeLayer = null;
        }
        // 清除标记
        this.routeMarkers.forEach(m => this.map.removeLayer(m));
        this.routeMarkers = [];
        // 隐藏结果面板
        const resultEl = document.getElementById("route-result");
        if (resultEl) resultEl.classList.add("hidden");
    }

    /**
     * 自定义标注：点击地图放置标注点（答辩演示：标注赏樱点/卫生间等）
     */
    async addCustomMarker(lat, lng) {
        if (!this.currentMapId) {
            Utils.showToast("请先生成地图", "warning");
            this.markerMode = false;
            this.updateMarkerBtn();
            return;
        }
        const name = window.prompt("标注名称（如：赏樱点、卫生间）：", "标注点");
        if (!name || !name.trim()) {
            this.markerMode = false;
            this.updateMarkerBtn();
            this.map.getContainer().style.cursor = "";
            return;
        }
        try {
            const resp = await fetch(CONFIG.apiBaseUrl + "/api/maps/" + this.currentMapId + "/marker", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name.trim(), lat: lat, lng: lng })
            });
            const json = await resp.json();
            if (json.success && json.data) {
                Utils.showToast("已添加标注: " + name, "success");
                this.renderMap(json.data);
            } else {
                Utils.showToast(json.message || "标注添加失败", "error");
            }
        } catch (e) {
            Utils.showToast("标注添加失败: " + e.message, "error");
        } finally {
            this.markerMode = false;
            this.updateMarkerBtn();
            this.map.getContainer().style.cursor = "";
        }
    }

    /**
     * 数据质量检测（五类：拓扑/属性/统计/专题/标注）
     */
    async checkQuality() {
        if (!this.currentMapId) return;
        const container = document.getElementById("map-quality-panel");
        if (!container) return;
        try {
            const resp = await fetch(CONFIG.apiBaseUrl + "/api/maps/" + this.currentMapId + "/quality");
            const json = await resp.json();
            this.renderQuality(json.data || {});
            // 跨要素检查：将检测到的"道路跨水"桥位渲染为桥梁/渡口符号
            this._renderBridgeMarkers(json.data || {});
        } catch (e) {
            container.innerHTML = '<div class="quality-empty">质量检测服务不可用</div>';
            container.classList.remove("hidden");
            const chip = document.getElementById("map-status-quality");
            if (chip) {
                chip.textContent = "质检不可用";
                chip.className = "status-quality warn";
            }
        }
    }

    /**
     * 渲染桥梁/渡口符号：依据质量检测"道路跨水"项的位置自动上图
     * （制图综合·跨要素关系：道路跨河必须表达桥梁/渡口）
     */
    _renderBridgeMarkers(report) {
        if (!this._bridgeGroup) this._bridgeGroup = L.layerGroup();
        else this._bridgeGroup.clearLayers();
        if (!this._bridgeGroup._map) this._bridgeGroup.addTo(this.map);
        const items = (report && report.items) || [];
        const cross = items.find((it) => (it.check || "").indexOf("道路跨水") === 0);
        if (!cross || !cross.positions || !cross.positions.length) return;
        cross.positions.forEach((pos) => {
            if (!Array.isArray(pos) || pos.length < 2) return;
            L.marker([pos[0], pos[1]], {
                icon: L.divIcon({
                    html: '<div style="width:18px;height:18px;font-size:14px;text-align:center;line-height:17px;background:#ffffff;border:1.5px solid #475569;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.35);">🌉</div>',
                    iconSize: [18, 18],
                    iconAnchor: [9, 9],
                    className: ""
                }),
                zIndexOffset: 900,
                interactive: true
            }).bindTooltip("桥梁/渡口（自动检测）", { sticky: true, opacity: 0.92 })
              .addTo(this._bridgeGroup);
        });
    }

    /**
     * 更新图层样式（颜色/线宽/透明度/虚线），保存到后端并重渲染
     */
    async updateLayerStyle(layerId, style) {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        try {
            const resp = await API.updateLayerStyle(this.currentMapId, layerId, style);
            if (resp.success && resp.data) {
                Utils.showToast("样式已更新", "success", 1600);
                this.renderMap(resp.data);
            } else {
                Utils.showToast(resp.message || "样式更新失败", "error");
            }
        } catch (e) {
            Utils.showToast("样式更新失败: " + e.message, "error");
        }
    }

    /**
     * 导出地图（GeoJSON/SVG/PNG）并触发浏览器下载
     * @param {string} format - geojson / svg / png
     */
    async exportMap(format) {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        Utils.showToast("正在导出 " + format.toUpperCase() + " ...", "info", 1800);
        try {
            const resp = await API.exportMap(this.currentMapId, format);
            if (!resp.success) {
                Utils.showToast(resp.message || "导出失败", "error");
                return;
            }
            const data = resp.data;
            const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
            const fname = ((this.currentMapData && this.currentMapData.name) || "map") + "-" + stamp + "." + format;
            let blob;
            if (format === "png") {
                const b64 = String(data).replace(/^data:[^;]*;base64,/, "");
                const bin = atob(b64);
                const arr = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                blob = new Blob([arr], { type: "image/png" });
            } else {
                blob = new Blob([data], { type: format === "geojson" ? "application/geo+json" : "image/svg+xml" });
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = fname;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            Utils.showToast("已导出 " + fname, "success");
        } catch (e) {
            Utils.showToast("导出失败: " + e.message, "error");
        }
    }

    /**
     * 规划路径：读取起终点输入，调用后端路由服务并渲染结果
     */
    async planRoute() {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        const startLat = parseFloat(document.getElementById("route-start-lat")?.value);
        const startLng = parseFloat(document.getElementById("route-start-lng")?.value);
        const endLat = parseFloat(document.getElementById("route-end-lat")?.value);
        const endLng = parseFloat(document.getElementById("route-end-lng")?.value);
        if (isNaN(startLat) || isNaN(startLng) || isNaN(endLat) || isNaN(endLng)) {
            Utils.showToast("请先设置起点和终点坐标", "warning");
            return;
        }
        Utils.showToast("正在规划路径...", "info", 1800);
        try {
            const resp = await API.planRoute(this.currentMapId, {
                start: [startLat, startLng],
                end: [endLat, endLng],
                profile: this.selectedProfile || "driving"
            });
            if (resp.success && resp.data) {
                this.renderRoute(resp.data);
                this.showRouteResult(resp.data);
            } else {
                Utils.showToast(resp.message || "路径规划失败", "error");
            }
        } catch (e) {
            Utils.showToast("路径规划失败: " + e.message, "error");
        }
    }
}
