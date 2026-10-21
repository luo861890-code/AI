<template>
  <div class="map-toolbar">
    <!-- 左侧：导航工具 -->
    <div class="toolbar-group">
      <button class="tool-btn" title="平移" @click="setTool('pan')">
        <i class="fa-solid fa-hand"></i>
      </button>
      <button class="tool-btn" title="框选缩放" @click="setTool('zoom-box')">
        <i class="fa-solid fa-vector-square"></i>
      </button>
      <button class="tool-btn" title="放大" @click="zoomIn">
        <i class="fa-solid fa-magnifying-glass-plus"></i>
      </button>
      <button class="tool-btn" title="缩小" @click="zoomOut">
        <i class="fa-solid fa-magnifying-glass-minus"></i>
      </button>
      <button class="tool-btn" title="回到初始视图" @click="resetView">
        <i class="fa-solid fa-house"></i>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 测量工具 -->
    <div class="toolbar-group">
      <button class="tool-btn" :class="{ active: currentTool === 'measure-distance' }" title="测量距离" @click="startMeasure('distance')">
        <i class="fa-solid fa-ruler"></i>
      </button>
      <button class="tool-btn" :class="{ active: currentTool === 'measure-area' }" title="测量面积" @click="startMeasure('area')">
        <i class="fa-solid fa-shapes"></i>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 选择工具 -->
    <div class="toolbar-group">
      <button class="tool-btn" :class="{ active: currentTool === 'select' }" title="选择要素" @click="setTool('select')">
        <i class="fa-solid fa-pointer"></i>
      </button>
      <button class="tool-btn" title="清除选择" @click="clearSelection">
        <i class="fa-solid fa-eraser"></i>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 绘图工具 -->
    <div class="toolbar-group">
      <button class="tool-btn" :class="{ active: currentTool === 'draw-point' }" title="绘制点" @click="setTool('draw-point')">
        <i class="fa-solid fa-location-dot"></i>
      </button>
      <button class="tool-btn" :class="{ active: currentTool === 'draw-line' }" title="绘制线" @click="setTool('draw-line')">
        <i class="fa-solid fa-minus"></i>
      </button>
      <button class="tool-btn" :class="{ active: currentTool === 'draw-polygon' }" title="绘制面" @click="setTool('draw-polygon')">
        <i class="fa-solid fa-draw-polygon"></i>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 空间分析 -->
    <div class="toolbar-group">
      <div class="tool-dropdown" @click="toggleAnalysisMenu">
        <button class="tool-btn" title="空间分析">
          <i class="fa-solid fa-chart-line"></i>
          <i class="fa-solid fa-caret-down dropdown-arrow"></i>
        </button>
        <div v-if="showAnalysisMenu" class="dropdown-menu">
          <div class="dropdown-item" @click="doBuffer">
            <i class="fa-solid fa-circle-notch"></i>
            <span>缓冲区分析</span>
          </div>
          <div class="dropdown-item" @click="doIntersect">
            <i class="fa-solid fa-layer-group"></i>
            <span>叠加分析</span>
          </div>
          <div class="dropdown-item" @click="doDistance">
            <i class="fa-solid fa-arrows-left-right"></i>
            <span>最近邻分析</span>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-item" @click="openAnalysisPanel">
            <i class="fa-solid fa-sliders"></i>
            <span>更多分析工具...</span>
          </div>
        </div>
      </div>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 导出 -->
    <div class="toolbar-group">
      <div class="tool-dropdown" @click="toggleExportMenu">
        <button class="tool-btn" title="导出地图">
          <i class="fa-solid fa-download"></i>
          <i class="fa-solid fa-caret-down dropdown-arrow"></i>
        </button>
        <div v-if="showExportMenu" class="dropdown-menu dropdown-right">
          <div class="dropdown-item" @click="exportImage('png')">
            <i class="fa-solid fa-image"></i>
            <span>导出为 PNG</span>
          </div>
          <div class="dropdown-item" @click="exportImage('svg')">
            <i class="fa-solid fa-file-vector"></i>
            <span>导出为 SVG</span>
          </div>
          <div class="dropdown-item" @click="exportGeoJSON">
            <i class="fa-solid fa-file-code"></i>
            <span>导出 GeoJSON</span>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-item" @click="exportLayout">
            <i class="fa-solid fa-file-export"></i>
            <span>布局导出...</span>
          </div>
        </div>
      </div>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 编辑 / 标注 / 经纬网 / 参数 / 编制说明 / 导入 / 清除 -->
    <div class="toolbar-group">
      <button class="tool-btn" :class="{ active: appStore.showEditPanel }" title="编辑模式（QGIS/ArcGIS 式几何编辑）" @click="appStore.toggleEditPanel()">
        <i class="fa-solid fa-pen-to-square"></i>
      </button>
      <button class="tool-btn" :class="{ active: appStore.markerMode }" title="在地图上添加标注" @click="appStore.toggleMarkerMode()">
        <i class="fa-solid fa-location-dot"></i>
      </button>
      <button class="tool-btn" :class="{ active: appStore.showGraticule }" title="经纬网" @click="appStore.toggleGraticule()">
        <i class="fa-solid fa-border-all"></i>
      </button>
      <button class="tool-btn" :class="{ active: appStore.showParamsPanel }" title="任务参数（微调智能体规划参数）" @click="appStore.toggleParamsPanel()">
        <i class="fa-solid fa-sliders"></i>
      </button>
      <button class="tool-btn" :class="{ active: appStore.showMetadataModal }" title="编制说明" @click="appStore.toggleMetadataModal()">
        <i class="fa-solid fa-circle-info"></i>
      </button>
      <button class="tool-btn" title="导入文档到知识图谱" @click="appStore.toggleImportModal()">
        <i class="fa-solid fa-file-import"></i>
      </button>
      <button class="tool-btn" title="清除地图" @click="clearMap">
        <i class="fa-solid fa-trash-can"></i>
      </button>
    </div>

    <LayoutExport
      :visible="showLayoutExport"
      :map-title="mapStore.mapName"
      @close="showLayoutExport = false"
      @export="handleLayoutExport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { useEditStore } from '@/stores/editStore'
import api from '@/services/api'
import { CONFIG } from '@/config'
import LayoutExport from './LayoutExport.vue'

const appStore = useAppStore()
const mapStore = useMapStore()
const editStore = useEditStore()

const currentTool = ref('pan')
const showAnalysisMenu = ref(false)
const showThemeMenu = ref(false)
const showExportMenu = ref(false)
const showLayoutExport = ref(false)

window.addEventListener('map-open-export', () => {
  showExportMenu.value = true
})

function setTool(tool: string) {
  currentTool.value = tool
  if (tool === 'draw-point' || tool === 'draw-line' || tool === 'draw-polygon') {
    const mapTool = tool === 'draw-point' ? 'point' : tool === 'draw-line' ? 'line' : 'polygon'
    appStore.showEditPanel = true
    editStore.setDrawTool(mapTool)
  }
  // 关闭所有下拉菜单
  showAnalysisMenu.value = false
  showThemeMenu.value = false
  showExportMenu.value = false
}

function zoomIn() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-zoom-in'))
  }
}

function zoomOut() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-zoom-out'))
  }
}

function resetView() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-reset-view'))
  }
}

function clearSelection() {
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-edit-clear-selection'))
}

function startMeasure(mode: 'distance' | 'area') {
  currentTool.value = mode === 'distance' ? 'measure-distance' : 'measure-area'
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-measure-start', { detail: { mode } }))
}

function clearMap() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-clear-layers'))
  }
}

function toggleAnalysisMenu() {
  showAnalysisMenu.value = !showAnalysisMenu.value
  showThemeMenu.value = false
  showExportMenu.value = false
}

function toggleThemeMenu() {
  showThemeMenu.value = !showThemeMenu.value
  showAnalysisMenu.value = false
  showExportMenu.value = false
}

function toggleExportMenu() {
  showExportMenu.value = !showExportMenu.value
  showAnalysisMenu.value = false
  showThemeMenu.value = false
}

function setTheme(theme: string) {
  mapStore.setTheme(theme)
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-set-theme', { detail: { theme } }))
  }
  showThemeMenu.value = false
}

function doBuffer() {
  appStore.setAnalysisMode('buffer')
  showAnalysisMenu.value = false
}

function doIntersect() {
  appStore.setAnalysisMode('overlay')
  showAnalysisMenu.value = false
}

function doDistance() {
  appStore.setAnalysisMode('nearest')
  showAnalysisMenu.value = false
}

function openAnalysisPanel() {
  appStore.toggleAnalysisPanel()
  showAnalysisMenu.value = false
}

function exportImage(format: string) {
  if (format === 'png') {
    const mapEl = document.getElementById('map-container')
    mapEl?.dispatchEvent(new CustomEvent('map-export-image'))
  } else {
    exportMapFile(format, format === 'svg' ? 'svg' : 'png', format === 'svg' ? 'image/svg+xml' : 'image/png')
  }
  showExportMenu.value = false
}

async function exportMapFile(format: string, ext: string, mime: string) {
  if (!mapStore.currentMapId) {
    alert('请先生成地图')
    return
  }
  try {
    const resp = await api.exportMap(mapStore.currentMapId, format)
    const data = resp.data || resp
    const filename = `map-${Date.now()}.${ext}`
    if (format === 'png' && typeof data === 'string' && data.startsWith('data:')) {
      const link = document.createElement('a')
      link.href = data
      link.download = filename
      link.click()
      return
    }
    const blob = new Blob([String(data)], { type: mime })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert('导出失败: ' + e.message)
  }
}

async function exportGeoJSON() {
  await exportMapFile('geojson', 'geojson', 'application/geo+json')
  showExportMenu.value = false
}

function exportLayout() {
  showLayoutExport.value = true
  showExportMenu.value = false
}

async function handleLayoutExport(options: any) {
  await exportMapFile('png', 'png', 'image/png')
}

function getThemePreviewColor(themeKey: string): string {
  const colors: Record<string, string> = {
    standard: '#a8d5ff',
    positron: '#f5f5f5',
    dark: '#2d3748',
    satellite: '#4a5568',
    plain: '#FAF8F3',
    amap_normal: '#e8f4f8',
    amap_satellite: '#3d4f5f',
    tianditu_vec: '#f0e6d2',
    tianditu_img: '#4a5568',
    tencent_normal: '#e8f4f8',
    esri_street_cn: '#f0e6d2',
  }
  return colors[themeKey] || '#eee'
}
</script>

<style scoped>
.map-toolbar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 6px 3px;
  background: var(--color-surface);
  height: 100%;
  overflow-y: auto;
  user-select: none;
}

.toolbar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.toolbar-divider {
  width: 22px;
  height: 1px;
  background: var(--color-border);
  margin: 3px 0;
}

.toolbar-spacer {
  flex: 1;
}

.tool-btn {
  width: 34px;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.15s;
  position: relative;
}

.tool-btn:hover {
  background: var(--color-bg);
  color: var(--color-primary);
}

.tool-btn.active {
  background: rgba(124, 58, 237, 0.1);
  color: var(--color-primary);
}

.dropdown-arrow {
  position: absolute;
  bottom: 3px;
  right: 3px;
  font-size: 8px;
  color: var(--color-text-secondary);
}

/* 下拉菜单 */
.tool-dropdown {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 6px;
  min-width: 180px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 4px 0;
  z-index: 100;
}

.dropdown-menu.dropdown-right {
  left: auto;
  right: 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  font-size: 13px;
  color: var(--color-text);
  cursor: pointer;
  transition: background 0.1s;
}

.dropdown-item:hover {
  background: var(--color-bg);
}

.dropdown-item.active {
  color: var(--color-primary);
  background: rgba(124, 58, 237, 0.06);
}

.dropdown-item i {
  width: 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.dropdown-item.active i {
  color: var(--color-primary);
}

.dropdown-item span {
  flex: 1;
}

.check-icon {
  color: var(--color-primary) !important;
}

.theme-preview {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid var(--color-border);
}

.dropdown-divider {
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}

/* tooltip */
.tool-btn::after {
  content: attr(title);
  position: absolute;
  bottom: -32px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-text);
  color: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  z-index: 100;
}

.tool-btn:hover::after {
  opacity: 1;
}
</style>
