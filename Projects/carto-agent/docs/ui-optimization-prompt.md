# CartoAgent UI 美化优化提示词

> 本文件是给代码编写 AI 的详细指令，分为 4 个阶段（P0-P3）。
> 每个阶段可独立执行，按优先级从上到下依次实施。

---

## P0：CSS 架构清理（紧急修复）

### 问题诊断

当前 `frontend/src/css/style.css` 存在严重的规则冲突：
- `.map-name-bar` 被定义了 5 次，每次覆盖前一次的 `position/top/left/font-size/background`
- `#map-container` 被定义了 4 次，`box-shadow` 内图廓规则相互覆盖
- `.map-compass` 被定义了 3 次，尺寸从 44px → 24px
- 后半段"全局UI美化"和"第二三轮优化"的规则直接覆盖前半段的基础定义

### 执行指令

```
请对 frontend/src/css/style.css 进行架构清理：

1. 将文件拆分为 4 个独立文件：
   - css/base.css     → 设计令牌（:root变量）、基础重置、滚动条、字体导入
   - css/layout.css    → 三栏布局（header/chat-panel/map-panel/right-toolbar）、响应式折叠
   - css/map.css       → 地图整饰（图廓/图名/指北针/比例尺/图例/审图落款/注记样式）
   - css/components.css → 弹窗/面板/控件（设置弹窗/图层面板/路径面板/知识图谱/会话抽屉/聊天消息）

2. 对每个选择器，只保留最终生效的规则版本，删除被覆盖的死代码

3. 在 index.html 中按顺序引入 4 个 CSS 文件（base → layout → map → components）

4. 确保 CSS 变量命名统一：当前同时存在 --color-primary 和 --theme-primary 两套变量，
   统一为 --color-primary 系列（保留原有 Aurora Cartograph 令牌体系）

5. 验证：拆分后页面显示效果与当前完全一致，无样式丢失
```

---

## P1：武汉市行政地图视觉升级（核心任务）

### 1.1 区级行政配色

在 `frontend/src/js/map.js` 的 `renderLayer` 方法中，当 `this.currentMapType === "administrative"` 时，
修改 polygon feature 的填充逻辑：

```javascript
// 在 renderLayer 的 features.forEach 分支中，替换 administrative 填充逻辑

// 武汉13区配色表（柔色pastel，每区可区分且整体协调）
const WUHAN_DISTRICT_COLORS = {
    "江岸区": "#FFF3E0",  // 暖橙
    "江汉区": "#E8F5E9",  // 浅绿
    "硚口区": "#E3F2FD",  // 浅蓝
    "汉阳区": "#FCE4EC",  // 浅粉
    "武昌区": "#F3E5F5",  // 淡紫
    "青山区": "#FFF8E1",  // 浅黄
    "洪山区": "#E0F7FA",  // 青色
    "东西湖区": "#F1F8E9", // 黄绿
    "汉南区": "#FFFDE7",  // 淡金
    "蔡甸区": "#ECEFF1",  // 灰蓝
    "江夏区": "#EFEBE9",  // 棕灰
    "黄陂区": "#E8EAF6",  // 靛蓝
    "新洲区": "#FBE9E7"   // 珊瑚
};

// 替换原有 administrative 填充代码
if (this.currentMapType === "administrative") {
    const districtName = feat.properties?.name || feat.properties?.district || "";
    // 匹配区名（支持带/不带"区"字）
    const matchedColor = Object.entries(WUHAN_DISTRICT_COLORS).find(
        ([name]) => districtName.includes(name.replace("区", ""))
    );
    fFill = matchedColor ? matchedColor[1] : "#F5F0E6";
    fFillOpac = 0.55;   // 提高不透明度，让分区可见
    fWeight = 0.8;      // 细边框
    fColor = "#9E9E9E"; // 区界灰色
}
```

### 1.2 底图纸张质感

在 `frontend/src/css/map.css` 中修改：

```css
/* 行政区划图底图：米色纸张质感（替代纯白） */
#map-container,
.leaflet-container {
    background: #FAF8F3;
}

/* 无瓦片模式下的微纹理（SVG noise，极淡） */
#map-container::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3'/%3E%3CfeColorMatrix values='0 0 0 0 0.4 0 0 0 0 0.35 0 0 0 0 0.25 0 0 0 0.03 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 0;
    opacity: 0.5;
}
```

### 1.3 水系渲染优化

在 `frontend/src/js/map.js` 的 `renderLayer` polyline 分支中，增强水系样式：

```javascript
// 水系线（河流/溪流/运河）样式增强
if (/水系|河流|溪流|运河/.test(layerData.name || "")) {
    const waterLineStyle = {
        color: style.color || "#2196F3",
        weight: Math.max(2, style.weight || 3),
        opacity: 0.85,
        lineCap: "round",
        lineJoin: "round"
    };
    // 宽河流（长江/汉江）叠加底层渐变
    if (/长江|汉江/.test(layerData.name || "")) {
        const _wg = L.layerGroup();
        validCoords.forEach(lineCoords => {
            // 底层宽线（浅蓝半透明，模拟水面）
            L.polyline(lineCoords, { color: "#64B5F6", weight: 8, opacity: 0.3 }).addTo(_wg);
            // 主线（深蓝）
            L.polyline(lineCoords, waterLineStyle).addTo(_wg);
        });
        layer = _wg;
    } else {
        lineStyle = waterLineStyle;
    }
}

// 湖泊面填充优化（在 polygon 分支中）
if (/湖泊|水库/.test(layerData.name || "")) {
    lineStyle = {
        color: "#1976D2",
        weight: 1,
        opacity: 0.6
    };
    // 湖泊填充改为浅蓝半透明
    fFill = "#BBDEFB";
    fFillOpac = 0.5;
}
```

### 1.4 边界线符体系

在 `frontend/src/js/map.js` 中替换行政区划图边界兜底样式：

```javascript
// 行政区划图边界三级行政线符体系
if (this.currentMapType === "administrative") {
    const _ln = layerData.name || "";
    if (/市域边界|地级市界|市界/.test(_ln)) {
        // 一级：市域边界 - 深红实线 + 光晕
        lineStyle = { color: "#D32F2F", weight: 3, opacity: 1, dashArray: null };
    } else if (/区县界/.test(_ln)) {
        // 二级：区县界 - 灰色点划线
        lineStyle = { color: "#616161", weight: 1.2, opacity: 0.9, dashArray: "6,3,1,3" };
    } else if (/周边县界/.test(_ln)) {
        // 三级：周边县界 - 浅灰细虚线
        lineStyle = { color: "#9E9E9E", weight: 0.8, opacity: 0.7, dashArray: "3,3" };
    } else if (/省界/.test(_ln)) {
        // 特级：省界 - 黑色粗实线
        lineStyle = { color: "#212121", weight: 1.5, opacity: 0.95, dashArray: null };
    }
}

// 武汉市域边界发光效果增强
if (_isMainBound) {
    const _gg = L.layerGroup();
    // 外层光晕（宽线半透明）
    L.polyline(validCoords[0] || lineCoords, {
        color: "#D32F2F", weight: 12, opacity: 0.12, dashArray: null
    }).addTo(_gg);
    // 中层光晕
    L.polyline(validCoords[0] || lineCoords, {
        color: "#E53935", weight: 7, opacity: 0.2, dashArray: null
    }).addTo(_gg);
    // 主线
    L.polyline(validCoords[0] || lineCoords, lineStyle).addTo(_gg);
    layer = _gg;
}
```

### 1.5 注记字体层级体系

在 `frontend/src/js/map.js` 的 textLabel 渲染分支中，建立三级注记体系：

```javascript
// 注记三级字体体系
const labelCategory = (prop, layerName) => {
    const name = prop.name || "";
    const ln = layerName || "";
    // 一级：区名注记（黑体，14-16px）
    if (/区名|区县名称/.test(ln) || /区$/.test(name)) {
        return { font: "black", baseSize: 15, color: "#1a1a1a", weight: 700 };
    }
    // 二级：水系注记（宋体斜体，12-13px，蓝色）
    if (/水系|河流|湖泊|江|河|湖/.test(ln) || /江|河|湖|水/.test(name)) {
        return { font: "song", baseSize: 13, color: "#1565C0", weight: 400, italic: true };
    }
    // 三级：POI/地标注记（仿宋，11-12px）
    if (/POI|地标|景点/.test(ln)) {
        return { font: "normal", baseSize: 11, color: "#424242", weight: 500 };
    }
    // 默认：普通注记
    return { font: "normal", baseSize: 12, color: "#333333", weight: 600 };
};

// 在 coords.forEach 中使用
const cat = labelCategory(prop, layerData.name);
const itemFontSize = Math.max(cat.baseSize - 2, Math.round(
    cat.baseSize * Math.min(1.6, Math.max(0.85, zoomFactor))
));
```

### 1.6 图例样式升级

在 `frontend/src/css/map.css` 中升级图例样式：

```css
/* 右下角图例：现代制图风格 */
.map-mini-legend {
    position: absolute;
    right: 18px;
    bottom: 128px;
    z-index: 701;
    width: 190px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(0, 0, 0, 0.15);
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    overflow: hidden;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.mini-legend-header {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(245, 158, 11, 0.04));
}

.mini-legend-title {
    font-weight: 600;
    font-size: 12px;
    color: #1e1b2e;
    letter-spacing: 1px;
}

.mini-legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11.5px;
    color: #333;
    padding: 4px 0;
}

/* 图例符号样式升级 */
.mini-line {
    border-radius: 2px;
}
.mini-box {
    border-radius: 3px;
    opacity: 0.7;
}
```

---

## P2：交互与动效增强

### 2.1 区划悬停增强

```javascript
// 在 renderLayer 的 polygon feature 分支中，增强行政区的悬停交互
if (this.currentMapType === "administrative") {
    const originalStyle = {
        color: poly.options.color,
        weight: poly.options.weight,
        fillOpacity: poly.options.fillOpacity,
        fillColor: poly.options.fillColor
    };

    poly.on("mouseover", function(e) {
        // 边框高亮
        this.setStyle({
            weight: 2.5,
            color: "#6366f1",
            fillOpacity: 0.75,
            fillColor: this.options.fillColor
        });
        this.bringToFront();

        // 显示区信息 Tooltip
        const districtName = feat.properties?.name || "未知区域";
        const area = feat.properties?.area || "";
        const population = feat.properties?.population || "";
        let info = `<strong style="font-size:13px;">${districtName}</strong>`;
        if (area) info += `<br><span style="color:#666;">面积: ${area}</span>`;
        if (population) info += `<br><span style="color:#666;">人口: ${population}</span>`;
        this.bindTooltip(info, {
            sticky: true,
            direction: "top",
            className: "district-tooltip",
            opacity: 0.95
        });
    });

    poly.on("mouseout", function() {
        this.setStyle(originalStyle);
    });
}
```

```css
/* 区划信息弹窗样式 */
.district-tooltip .leaflet-tooltip-content {
    padding: 8px 12px;
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}
.leaflet-tooltip.district-tooltip {
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    padding: 4px 8px;
}
```

### 2.2 图层逐级淡入

```javascript
// 在 renderMap 方法中，替换直接渲染为带动画的逐级渲染
// 替换 mapData.layers.forEach(layerData => { this.renderLayer(layerData); });

const RENDER_DELAY = 120; // ms，每层间隔
mapData.layers.forEach((layerData, idx) => {
    setTimeout(() => {
        const layer = this.renderLayer(layerData);
        if (layer) {
            // Canvas 元素淡入
            const el = layer.getContainer ? layer.getContainer() : null;
            if (el) {
                el.style.opacity = '0';
                el.style.transition = 'opacity 0.4s ease';
                requestAnimationFrame(() => { el.style.opacity = '1'; });
            }
        }
    }, idx * RENDER_DELAY);
});
```

### 2.3 图例图层开关

```javascript
// 在 initLegendPanel 或 updateLayerPanel 方法中，为每个图例项添加可见性开关
// 在图例项 HTML 中添加 checkbox：
// <label class="legend-item-toggle">
//   <input type="checkbox" checked data-layer-id="layer_xxx">
//   <span class="legend-symbol">...</span>
//   <span class="legend-label">道路</span>
// </label>

// 事件绑定
document.querySelectorAll('.legend-item-toggle input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', (e) => {
        const layerId = e.target.dataset.layerId;
        const layerGroup = this.layerGroups[layerId];
        if (layerGroup) {
            if (e.target.checked) {
                layerGroup.layer.addTo(this.map);
            } else {
                this.map.removeLayer(layerGroup.layer);
            }
            layerGroup.visible = e.target.checked;
        }
    });
});
```

---

## P3：长远架构演进建议

### 3.1 前端框架迁移
```
建议将前端从当前纯 Vanilla JS 迁移至 Vue 3 + Vite：
- map.js（4000+行）拆分为 composables：useMap.ts / useLayer.ts / useLegend.ts / useExport.ts
- style.css 拆分为 CSS Modules 或使用 Tailwind CSS + 自定义设计令牌
- 图层面板/设置弹窗/路径面板独立为 SFC 组件
- 保留 Leaflet 作为地图引擎（或评估迁移到 MapLibre GL JS）
```

### 3.2 地图引擎评估
```
评估从 Leaflet 迁移到 MapLibre GL JS 的可行性：
- 优势：矢量瓦片渲染（更清晰）、3D 地形支持、WebGL 性能更好、原生样式描述（Mapbox Style Spec）
- 劣势：需要重构所有地图渲染逻辑、proj4leaflet 兼容性需验证
- 建议：新建分支做 PoC，对比渲染效果和性能后再决定
```

### 3.3 暗色主题支持
```css
/* 在 base.css 中增加暗色主题令牌 */
:root[data-theme="dark"] {
    --color-bg: #0f172a;
    --color-surface: rgba(30, 41, 59, 0.85);
    --color-surface-solid: #1e293b;
    --color-text: #f1f5f9;
    --color-text-secondary: #94a3b8;
    --color-border: rgba(99, 102, 241, 0.2);
    /* 地图整饰暗色 */
    --map-bg: #1a1a2e;
    --map-title-color: #e2e8f0;
    --map-note-color: #cbd5e1;
    --map-border-color: #475569;
}
```

### 3.4 导出功能增强
```javascript
// 高分辨率地图导出
// 使用 leaflet-image 或 html2canvas + Canvas 倍率
async exportMapHD(format = 'png', scale = 2) {
    // 1. 创建离屏 Canvas，尺寸 = 地图容器 × scale
    // 2. 使用 leaflet-image 插件渲染地图到 Canvas
    // 3. 叠加图名/图例/比例尺/指北针等整饰元素
    // 4. 导出为 PNG（或 SVG 矢量格式）
}
```

---

## 实施检查清单

- [ ] P0: CSS 拆分为 4 个文件，无规则冲突
- [ ] P0: 页面显示效果与拆分前完全一致
- [ ] P1: 武汉13区有差异化柔色填充
- [ ] P1: 底图为米色纸张质感（非纯白）
- [ ] P1: 水系使用渐变蓝带渲染
- [ ] P1: 边界三级线符体系生效
- [ ] P1: 注记三级字体层级正确
- [ ] P1: 图例样式与现代UI风格协调
- [ ] P2: 区划悬停显示区名/面积/人口
- [ ] P2: 图层逐级淡入动画
- [ ] P2: 图例支持图层可见性开关
- [ ] P3: 暗色主题令牌定义完成
- [ ] P3: 高分辨率导出功能验证
