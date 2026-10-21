/**
 * 前端全局配置
 * 包含API地址、地图默认参数、主题瓦片地址、知识图谱节点颜色等
 */

const CONFIG = {
    // 后端API基础地址（部署时可通过URL参数 ?api=xxx 或 localStorage 覆盖）
    apiBaseUrl: (() => {
        // 1. 优先从URL参数读取
        const urlParams = new URLSearchParams(window.location.search);
        const apiParam = urlParams.get("api");
        if (apiParam) {
            localStorage.setItem("carto_api_url", apiParam);
            return apiParam;
        }
        // 2. 从localStorage读取
        const stored = localStorage.getItem("carto_api_url");
        if (stored) return stored;
        // 3. 默认本地地址
        return "http://localhost:8080";
    })(),

    // WebSocket地址（用于实时推送，如智能体执行步骤）
    socketUrl: "ws://localhost:8080/ws",

    // 地图默认中心点（武汉市）
    defaultMapCenter: [30.5928, 114.3055],

    // 地图默认缩放级别
    defaultZoom: 12,

    // 地图底图主题配置（瓦片URL与归属信息）
    mapThemes: {
        standard: {
            name: "标准地图",
            url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution: "&copy; OpenStreetMap 贡献者",
            maxZoom: 19,
            subdomains: "abc"
        },
        positron: {
            name: "浅色地图",
            url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attribution: "&copy; CARTO &copy; OpenStreetMap 贡献者",
            maxZoom: 20,
            subdomains: "abcd"
        },
        dark: {
            name: "深色地图",
            url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            attribution: "&copy; CARTO &copy; OpenStreetMap 贡献者",
            maxZoom: 20,
            subdomains: "abcd"
        },
        satellite: {
            name: "卫星地图",
            url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attribution: "&copy; Esri, Maxar, Earthstar Geographics",
            maxZoom: 19,
            subdomains: ""
        },
        plain: {
            name: "制图底图（无瓦片）",
            url: "",
            attribution: "",
            maxZoom: 19
        },
        // ===== 中文底图 =====
        amap_normal: {
            name: "高德地图",
            url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
            attribution: "&copy; 高德地图",
            maxZoom: 20,
            subdomains: "1234"
        },
        amap_satellite: {
            name: "高德卫星",
            url: "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
            attribution: "&copy; 高德地图",
            maxZoom: 20,
            subdomains: "1234"
        },
        tianditu_vec: {
            name: "天地图矢量",
            url: "https://t{s}.tianditu.gov.cn/DataServer?T=vec_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de",
            attribution: "&copy; 天地图",
            maxZoom: 18,
            subdomains: "01234567"
        },
        tianditu_img: {
            name: "天地图影像",
            url: "https://t{s}.tianditu.gov.cn/DataServer?T=img_w&x={x}&y={y}&l={z}&tk=a3bb2eed53ecf1d9a3c852f0ab4d27de",
            attribution: "&copy; 天地图",
            maxZoom: 18,
            subdomains: "01234567"
        },
        tencent_normal: {
            name: "腾讯地图",
            url: "https://rt{s}.map.gtimg.com/realtimerender?z={z}&x={x}&y={-y}&type=vector&style=0",
            attribution: "&copy; 腾讯地图",
            maxZoom: 20,
            subdomains: "0123"
        },
        esri_street_cn: {
            name: "Esri中文街道",
            url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            attribution: "&copy; Esri",
            maxZoom: 19,
            subdomains: ""
        }
    },

    // 知识图谱节点颜色映射（按label分类）
    kgNodeColors: {
        MapType: "#3b82f6",      // 蓝色 - 地图类型
        City: "#22c55e",         // 绿色 - 城市
        Landmark: "#f97316",     // 橙色 - 地标
        Style: "#a855f7",        // 紫色 - 样式
        Tool: "#ec4899",         // 粉色 - 工具
        Constraint: "#ef4444",   // 红色 - 约束条件
        Entity: "#64748b",       // 灰色 - 通用实体
        CartographyRule: "#fbbf24", // 金色 - 制图规则
        StyleRecommendation: "#06b6d4", // 青色 - 样式推荐
        // ===== 新增：DoMapAI框架5类核心本体 =====
        MapElement: "#3b82f6",         // 蓝色 - 地图要素
        MapSymbol: "#a855f7",          // 紫色 - 地图符号
        CartographicData: "#22c55e",   // 绿色 - 制图数据
        MapProjection: "#f97316",      // 橙色 - 地图投影
        InfluencingFactor: "#ef4444"   // 红色 - 影响因素
    },

    // 快捷指令配置
    quickCommands: [
        { label: "武汉交通图", icon: "fa-route", message: "生成一份武汉市交通图" },
        { label: "武汉旅游图", icon: "fa-landmark", message: "生成一份武汉市旅游图" },
        { label: "行政区划图", icon: "fa-map", message: "生成一份武汉市行政区划图" }
    ],

    // API请求超时时间（毫秒）
    requestTimeout: 60000,

    // API请求重试次数
    retryTimes: 2,

    // 聊天消息最大长度
    maxMessageLength: 2000,

    // 图谱默认加载节点数量
    kgDefaultLimit: 100
};
