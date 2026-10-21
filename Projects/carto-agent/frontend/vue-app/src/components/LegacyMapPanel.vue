<template>
  <div class="legacy-map-panel">
    <div ref="mapEl" class="legacy-map-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useMapStore } from '@/stores/mapStore'
import { useAppStore } from '@/stores/appStore'
import type { MapData } from '@/types'

/**
 * 经典 JS 做图模块（MapPanel）集成层。
 *
 * 背景：后端生成的行政区划图等制图逻辑原先由经典前端（8080/app）的 MapPanel 类
 * 负责渲染。本组件用 window 上动态加载的 MapPanel（见 public/legacy/map*.js）
 * 取代原 Vue 侧的 MapCanvas.vue，仅复用其「做图渲染」能力，图层面板/图例/状态栏
 * 等经典 UI 仍由 Vue 侧组件接管（对应 MapPanel 的 headless 模式）。
 */

/** MapPanel 实例的最小类型描述（完整类定义见 public/legacy/map.js） */
interface MapPanelInstance {
  _headless: boolean
  map: any // Leaflet L.Map 实例
  mapCrsKey: string
  currentTheme: string
  currentMapType: string | null
  tileLayer: any
  layerGroups: Record<string, any>
  _layerOrder: string[]
  _lockedGroups: Record<string, any>
  _labelPlaced: any[]
  _labelNames: Set<string>
  _poiMarkers: any[]
  layerControl: any
  refreshLabels(): void
  renderMap(data: MapData): void
  _fitAdministrativeBounds(data: MapData): void
}

const mapStore = useMapStore()
const appStore = useAppStore()
const mapEl = ref<HTMLDivElement | null>(null)

/** 经典 JS MapPanel 实例；由 setupPanel 创建，onBeforeUnmount 销毁 */
let panel: MapPanelInstance | null = null

/** 渲染地图数据，并保证容器尺寸正确后再取景 */
function renderMapData(data: MapData) {
  if (!panel?.map) return
  // 校准容器尺寸：Vue 挂载/流式渲染初期容器可能为 0，直接 renderMap 会导致
  // 行政图 fitBounds 取景失效（地图停在默认中心，周边地市不可见）
  panel.map.invalidateSize()
  panel.renderMap(data)
  // 流式渲染会多次触发 renderMap，布局仍可能抖动；下一帧再强制取景一次，
  // 确保行政图最终视图正确（显示完整"武汉全域 + 周边地市"范围）
  requestAnimationFrame(() => {
    if (panel?.map && panel._fitAdministrativeBounds) {
      panel.map.invalidateSize()
      panel._fitAdministrativeBounds(data)
    }
  })
}

/** 创建经典 JS MapPanel 实例，仅初始化做图渲染所需状态（headless 模式） */
function setupPanel() {
  const w = window as any
  const MP = w.MapPanel
  const L = w.L
  const CONFIG = w.CONFIG
  if (!MP || !L || !CONFIG) {
    console.error('[LegacyMapPanel] 经典 JS 做图模块未加载', { MP: !!MP, L: !!L, CONFIG: !!CONFIG })
    return
  }

  panel = new MP(null) as MapPanelInstance
  // headless 模式：跳过经典前端的图层面板/图例/状态栏等 UI 更新（这些由 Vue 接管）
  panel._headless = true

  // 创建 Leaflet 地图实例（Canvas 渲染 + 0.05 级缩放，禁用默认缩放控件）
  panel.map = L.map(mapEl.value, {
    center: CONFIG.defaultMapCenter,
    zoom: CONFIG.defaultZoom,
    zoomControl: false,
    zoomSnap: 0.05,
    preferCanvas: true,
    attributionControl: true,
  })

  // 初始化做图渲染所需的核心状态（等价于 MapPanel 构造器的字段初始化）
  panel.mapCrsKey = 'WebMercator'
  panel.currentTheme = 'plain'
  panel.currentMapType = null
  panel.tileLayer = null
  panel.layerGroups = {}
  panel._layerOrder = []
  panel._lockedGroups = {}
  panel._labelPlaced = []
  panel._labelNames = new Set()
  panel._poiMarkers = []
  panel.layerControl = null

  // 缩放结束重新应用载负量 LOD（等价于经典前端 initGraticule 中的 zoomend -> refreshLabels）
  panel.map.on('zoomend', () => panel?.refreshLabels())

  // 暴露实例到 window，便于浏览器调试/验证
  ;(window as any).__mapPanel = panel
}

onMounted(async () => {
  setupPanel()
  // 等待 Vue 首轮布局完成再渲染，确保地图容器尺寸正确
  await nextTick()
  if (mapStore.currentMapData) {
    renderMapData(mapStore.currentMapData)
  }
})

// 地图数据变化（智能体生成新地图 / 切换会话）时重新渲染
watch(
  () => mapStore.currentMapData,
  (data) => {
    if (data) renderMapData(data)
  },
)

// 面板显隐导致地图容器尺寸变化，延迟重算尺寸（等布局稳定）
watch(
  [() => appStore.showChatPanel, () => appStore.showLayerPanel],
  () => setTimeout(() => panel?.map?.invalidateSize(), 300),
)

onBeforeUnmount(() => {
  panel?.map?.remove()
  panel = null
})
</script>

<style scoped>
.legacy-map-panel {
  width: 100%;
  height: 100%;
  position: relative;
}
.legacy-map-container {
  width: 100%;
  height: 100%;
}
</style>
