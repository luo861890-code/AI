<template>
  <main class="map-panel">
    <!-- 顶部地图信息条：名称/主题/比例尺/经纬网 -->
    <MapTopBar />

    <!-- 地图容器 -->
    <div id="map-container" ref="mapContainerRef"></div>

    <!-- 自然语言修改输入框 -->
    <div class="map-modify-wrapper">
      <input
        v-model="modifyInput"
        type="text"
        class="map-modify-input"
        placeholder="自然语言修改地图，如'把道路改成红色'..."
        @keydown.enter="handleModify"
      />
      <button class="map-modify-btn" @click="handleModify" title="执行修改">
        <i class="fa-solid fa-wand-magic-sparkles"></i>
      </button>
    </div>

    <!-- 图例按钮 -->
    <button
      v-if="legendData || mapStore.sortedLayers.length > 0"
      class="map-legend-btn"
      :class="{ active: appStore.showLegendPanel }"
      title="显示完整图例"
      @click="appStore.toggleLegendPanel()"
    >
      <i class="fa-solid fa-book-open"></i>
      <span>图例</span>
    </button>

    <!-- 完整图例面板 -->
    <MapLegendPanel v-if="appStore.showLegendPanel" :legend-data="legendData" />

    <!-- 行政区划迷你图例 -->
    <MiniLegend v-if="mapStore.mapType === 'administrative'" />

    <!-- 任务参数面板 -->
    <ParamsPanel v-if="appStore.showParamsPanel" />

    <!-- 空间分析面板 -->
    <AnalysisPanel v-if="appStore.showAnalysisPanel" />

    <!-- 编辑模式面板 -->
    <MapEditPanel v-if="appStore.showEditPanel" />

    <!-- 路径规划面板 -->
    <div v-if="appStore.showRoutePanel" class="map-route-panel">
      <div class="route-panel-header">
        <span><i class="fa-solid fa-route"></i> 路径规划</span>
        <button class="route-panel-close" @click="appStore.toggleRoutePanel()">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="route-panel-body">
        <div class="route-field">
          <label>出行方式</label>
          <div class="route-profile-group">
            <button :class="{ active: routeProfile === 'driving' }" @click="routeProfile = 'driving'"><i class="fa-solid fa-car"></i> 驾车</button>
            <button :class="{ active: routeProfile === 'walking' }" @click="routeProfile = 'walking'"><i class="fa-solid fa-person-walking"></i> 步行</button>
            <button :class="{ active: routeProfile === 'cycling' }" @click="routeProfile = 'cycling'"><i class="fa-solid fa-bicycle"></i> 骑行</button>
          </div>
        </div>
        <div class="route-field">
          <label>
            <i class="fa-solid fa-circle-dot route-start-icon"></i> 起点
            <span class="route-hint">（在地图上点击设置）</span>
          </label>
          <div class="route-coord-input">
            <input id="route-start-lat" v-model="routeStartLat" type="number" placeholder="纬度" step="0.0001" class="route-input" @focus="enterRoutePick('start')" />
            <input id="route-start-lng" v-model="routeStartLng" type="number" placeholder="经度" step="0.0001" class="route-input" @focus="enterRoutePick('start')" />
          </div>
        </div>
        <div class="route-field">
          <label>
            <i class="fa-solid fa-location-dot route-end-icon"></i> 终点
            <span class="route-hint">（在地图上点击设置）</span>
          </label>
          <div class="route-coord-input">
            <input id="route-end-lat" v-model="routeEndLat" type="number" placeholder="纬度" step="0.0001" class="route-input" @focus="enterRoutePick('end')" />
            <input id="route-end-lng" v-model="routeEndLng" type="number" placeholder="经度" step="0.0001" class="route-input" @focus="enterRoutePick('end')" />
          </div>
        </div>
        <button class="route-plan-btn" @click="handlePlanRoute">
          <i class="fa-solid fa-route"></i> 开始规划
        </button>
        <div v-if="mapStore.routeData" class="route-result">
          <div class="route-result-stats">
            <div class="route-stat">
              <span class="route-stat-label">距离</span>
              <span class="route-stat-value">{{ (mapStore.routeData.distance / 1000).toFixed(2) }} km</span>
            </div>
            <div class="route-stat">
              <span class="route-stat-label">预计时间</span>
              <span class="route-stat-value">{{ Math.round(mapStore.routeData.duration / 60) }} 分钟</span>
            </div>
          </div>
          <div class="route-steps">
            <div v-for="(step, idx) in mapStore.routeData.steps" :key="idx" class="route-step">
              <span class="route-step-num">{{ idx + 1 }}</span>
              <span class="route-step-text">{{ step.instruction }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 测量工具提示 -->
    <div v-if="measureMode" class="measure-tooltip">
      <i class="fa-solid fa-ruler"></i>
      <span>{{ measureResult }}</span>
    </div>

    <!-- 底部状态栏 -->
    <div class="map-status-bar">
      <div class="map-status-item">
        <i class="fa-solid fa-location-crosshairs"></i>
        <span>{{ statusLat }} · {{ statusLng }}</span>
      </div>
      <div class="map-status-item">
        <i class="fa-solid fa-magnifying-glass"></i>
        <span>缩放 {{ statusZoom }}</span>
      </div>
      <div class="map-status-item">
        <i class="fa-solid fa-layer-group"></i>
        <span>{{ mapStore.sortedLayers.length }} 图层</span>
      </div>
      <div class="map-status-item">
        <span class="status-quality" :class="qualityClass" :title="qualityTitle">
          {{ qualityText }}
        </span>
      </div>
      <div class="map-status-item">
        <span class="status-edit" :class="{ editing: editStore.active }">
          {{ editStore.active ? '编辑中' : '未编辑' }}
        </span>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
/**
 * 地图渲染与编辑组件（编辑界面专用）。
 *
 * 职责边界：
 *  - 主界面（App 的 main 视图）的「做图渲染」已由 LegacyMapPanel.vue 接管
 *    （复用经典 JS MapPanel 做图模块，保证与 8080/app 行政区划图效果一致）；
 *  - 本组件保留给 QgisEditor 编辑界面使用，额外承载 QGIS 式几何编辑
 *    （Leaflet editable）、自然语言修改、图层样式编辑等交互能力。
 */
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { useEditStore } from '@/stores/editStore'
import api from '@/services/api'
import { CONFIG } from '@/config'
import MapTopBar from './MapTopBar.vue'
import MapLegendPanel from './MapLegendPanel.vue'
import MiniLegend from './MiniLegend.vue'
import MapEditPanel from './MapEditPanel.vue'
import ParamsPanel from './ParamsPanel.vue'
import AnalysisPanel from './AnalysisPanel.vue'
import type { MapData, MapLayer, LegendData } from '@/types'

const appStore = useAppStore()
const mapStore = useMapStore()
const editStore = useEditStore()

const mapContainerRef = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let currentBaseLayer: L.TileLayer | null = null
const layerMap = new Map<string, L.Layer>()
// 图层数据索引（用于 LOD 显隐控制与取景）
const layerDataById = new Map<string, MapLayer>()

// 状态
const currentTheme = ref('amap_normal')
const modifyInput = ref('')
const legendData = ref<LegendData | null>(null)
const statusLat = ref('30.5928°')
const statusLng = ref('114.3055°')
const statusZoom = ref('12')

// 路径规划
const routeProfile = ref('driving')
const routeStartLat = ref('')
const routeStartLng = ref('')
const routeEndLat = ref('')
const routeEndLng = ref('')
const routePickMode = ref<'start' | 'end' | null>(null)

// 测量工具
const measureMode = ref<'distance' | 'area' | null>(null)
const measurePoints = ref<[number, number][]>([])
const measureResult = ref('')

// 编辑模式
let vertexMarkers: L.Marker[] = []

const layerEntries = computed(() => {
  return Object.entries(mapStore.layerGroups)
})

const qualityText = computed(() => {
  const q = mapStore.quality
  if (!q) return '质检中…'
  const fail = q.summary?.failed || 0
  return q.summary?.passed_all ? '质检 ✓ 全部通过' : `质检 ⚠ ${fail} 项异常`
})

const qualityClass = computed(() => {
  const q = mapStore.quality
  if (!q) return ''
  return q.summary?.passed_all ? 'ok' : 'warn'
})

const qualityTitle = computed(() => {
  const q = mapStore.quality
  if (!q) return '数据质量检测（点击查看异常）'
  const items = q.items || []
  const failed = items.filter((i: any) => !i.passed)
  return failed.map((i: any) => i.check + (i.message ? ': ' + i.message : '')).join('\n') || '全部通过'
})

// ========== 初始化地图 ==========
onMounted(() => {
  if (!mapContainerRef.value) return

  const [lat, lng] = CONFIG.defaultMapCenter

  // 初始化Leaflet地图
  map = L.map(mapContainerRef.value, {
    center: [lat, lng],
    zoom: CONFIG.defaultZoom,
    zoomControl: false,
    attributionControl: false,
  })

  // 添加缩放控件
  L.control.zoom({ position: 'topright' }).addTo(map)

  // 添加比例尺控件
  L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map)

  // 设置初始底图（制图底图，无瓦片，和carto-agent-1一致）
  setTheme('plain')

  // 监听地图移动
  map.on('move', updateStatusBar)
  map.on('moveend', () => {
    updateScaleDisplay()
  })
  map.on('zoomend', () => {
    updateScaleDisplay()
    applyLod()
  })
  map.on('click', handleMapClick)
  map.on('dblclick', handleMapDblClick)

  // 如果已经有地图数据，直接渲染
  if (mapStore.currentMapData) {
    renderMap(mapStore.currentMapData)
  }

  // ===== 自定义事件监听 =====
  const el = mapContainerRef.value
  const listeners: Array<[string, EventListener]> = [
    ['map-reset-view', () => { map?.setView([lat, lng], CONFIG.defaultZoom) }],
    ['map-clear-layers', () => { mapStore.clearAllLayers(); mapStore.clearRoute() }],
    ['map-zoom-in', () => { map?.zoomIn() }],
    ['map-zoom-out', () => { map?.zoomOut() }],
    ['map-zoom-full', () => { map?.setView([lat, lng], CONFIG.defaultZoom) }],
    ['map-export-image', handleExportImage],
    ['map-refresh-layers', () => { refreshLayersFromStore() }],
    ['map-zoom-to-layer', handleZoomToLayer],
    ['map-locate', (e) => {
      const p = (e as CustomEvent).detail
      if (p && map) {
        map.setView([p.lat, p.lng], Math.max(map.getZoom(), 13))
      }
    }],
    ['map-set-theme', (e) => { const theme = (e as CustomEvent).detail?.theme; if (theme) setTheme(theme) }],
    ['map-set-scale', (e) => { const denom = (e as CustomEvent).detail?.denominator; if (denom) zoomForScale(denom) }],
    ['map-scale-request', () => { updateScaleDisplay() }],
    ['map-apply-data', (e) => {
      const data = (e as CustomEvent).detail?.data
      if (data) {
        renderMap(data)
      }
    }],
    ['map-undo', () => { undoEdit() }],
    ['map-redo', () => { redoEdit() }],
    ['map-reset-north', () => { map?.setView(map.getCenter(), map.getZoom()) }],
    ['map-get-stats', () => {
      // 发送地图统计数据
      const stats = {
        layerCount: mapStore.sortedLayers.length,
        featureCount: 0,
        center: map?.getCenter(),
        zoom: map?.getZoom(),
      }
      window.dispatchEvent(new CustomEvent('map-stats-data', { detail: stats }))
    }],
    ['map-apply-task-params', (e) => {
      const params = (e as CustomEvent).detail
      console.log('应用任务参数', params)
    }],
    ['map-set-projection', (e) => {
      const projection = (e as CustomEvent).detail?.projection
      console.log('设置投影', projection)
    }],
    // 测量工具
    ['map-measure-distance', () => { startMeasure('distance') }],
    ['map-measure-area', () => { startMeasure('area') }],
    ['map-measure-clear', clearMeasure],
  ]
  listeners.forEach(([name, fn]) => el.addEventListener(name, fn))

  // 面板切换时 resize
  watch(
    () => appStore.showChatPanel,
    () => setTimeout(() => map?.invalidateSize(), 300)
  )
  watch(
    () => appStore.showLayerPanel,
    () => setTimeout(() => map?.invalidateSize(), 300)
  )

  // 底图主题变化
  watch(
    () => mapStore.currentTheme,
    (theme) => {
      if (theme && theme !== currentTheme.value) setTheme(theme)
    }
  )

  // 地图数据变化
  watch(
    () => mapStore.currentMapData,
    (data) => {
      if (data && map) renderMap(data)
    }
  )

  // 图层变化实时刷新
  watch(
    () => mapStore.sortedLayers,
    () => {
      if (map) refreshLayersFromStore()
    },
    { deep: true }
  )

  // 编辑模式开关
  watch(
    () => appStore.showEditPanel,
    (show) => {
      if (show) enterEditMode()
      else exitEditMode()
    }
  )

  // 键盘快捷键：Ctrl+Z / Ctrl+Y
  const handleKeydown = (e: KeyboardEvent) => {
    if (!editStore.active) return
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
      e.preventDefault()
      undoEdit()
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
      e.preventDefault()
      redoEdit()
    }
  }
  document.addEventListener('keydown', handleKeydown)

  const handleEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && measureMode.value) {
      clearMeasure()
    }
  }
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  map?.remove()
  map = null
  clearVertexMarkers()
})

// ========== 底图主题 ==========
function setTheme(themeName: string) {
  const themeConfig = CONFIG.mapThemes[themeName]
  if (!themeConfig || !map) return

  // 移除当前底图
  if (currentBaseLayer) {
    map.removeLayer(currentBaseLayer)
    currentBaseLayer = null
  }

  // 添加新底图（如果有url的话）
  if (themeConfig.url && themeConfig.url.trim() !== '') {
    let tileUrl = themeConfig.url
    let subdomains: string | string[] | undefined

    if (themeConfig.subdomains && themeConfig.subdomains.length > 0) {
      subdomains = themeConfig.subdomains.split('')
    }

    currentBaseLayer = L.tileLayer(tileUrl, {
      maxZoom: themeConfig.maxZoom,
      attribution: themeConfig.attribution,
      subdomains: subdomains,
      crossOrigin: true,
    }).addTo(map)
  }

  currentTheme.value = themeName
  
  // 同步更新store中的底图名称
  if (mapStore.currentTheme !== themeName) {
    mapStore.setTheme(themeName)
  }
}

// ========== 状态栏更新 ==========
function updateStatusBar() {
  if (!map) return
  const center = map.getCenter()
  statusLat.value = center.lat.toFixed(4) + '°'
  statusLng.value = center.lng.toFixed(4) + '°'
  statusZoom.value = map.getZoom().toString()
}

function updateScaleDisplay() {
  // 发送比例尺更新事件
  if (map) {
    const zoom = map.getZoom()
    window.dispatchEvent(new CustomEvent('map-scale-update', { detail: { zoom } }))
  }
}

function zoomForScale(denominator: number) {
  // 简单的比例尺转缩放级别
  if (!map) return
  const zoom = Math.log2(50000000 / denominator)
  map.setZoom(zoom)
}

// ========== 地图点击 ==========
function handleMapClick(e: L.LeafletMouseEvent) {
  const { lat, lng } = e.latlng

  // 路径规划选点
  if (routePickMode.value) {
    if (routePickMode.value === 'start') {
      routeStartLat.value = lat.toFixed(4)
      routeStartLng.value = lng.toFixed(4)
    } else {
      routeEndLat.value = lat.toFixed(4)
      routeEndLng.value = lng.toFixed(4)
    }
    routePickMode.value = null
    return
  }

  // 测量模式
  if (measureMode.value) {
    measurePoints.value.push([lat, lng])
    updateMeasureResult()
    return
  }

  // 编辑模式
  if (editStore.active) {
    // 编辑模式点击处理
    return
  }
}

function handleMapDblClick(e: L.LeafletMouseEvent) {
  // 测量模式双击结束
  if (measureMode.value && measurePoints.value.length > 1) {
    updateMeasureResult()
  }
}

// ========== 路径规划 ==========
function enterRoutePick(mode: 'start' | 'end') {
  routePickMode.value = mode
}

async function handlePlanRoute() {
  if (!routeStartLat.value || !routeStartLng.value || !routeEndLat.value || !routeEndLng.value) {
    alert('请先设置起点和终点')
    return
  }

  try {
    const res = await api.planRoute(mapStore.currentMapData?.map_id ?? '', {
      start: [parseFloat(routeStartLng.value), parseFloat(routeStartLat.value)],
      end: [parseFloat(routeEndLng.value), parseFloat(routeEndLat.value)],
      profile: routeProfile.value,
    })
    if (res.success && res.data) {
      mapStore.setRouteData(res.data)
    }
  } catch (e) {
    console.error('路径规划失败', e)
  }
}

// ========== 测量工具 ==========
function startMeasure(mode: 'distance' | 'area') {
  measureMode.value = mode
  measurePoints.value = []
  measureResult.value = mode === 'distance' ? '点击地图添加测量点，双击结束' : '点击地图添加顶点，双击结束'
  setMapCursor('crosshair')
  editStore.setStatus(mode === 'distance' ? '测量距离：点击地图添加测量点，双击结束' : '测量面积：点击地图添加顶点，双击结束')
}

function clearMeasure() {
  measureMode.value = null
  measurePoints.value = []
  measureResult.value = ''
  setMapCursor('')
  editStore.setStatus('')
}

function updateMeasureResult() {
  if (measurePoints.value.length < 2) {
    measureResult.value = measureMode.value === 'distance' ? '点击继续添加点' : '点击继续添加顶点'
    return
  }

  if (measureMode.value === 'distance') {
    let total = 0
    for (let i = 1; i < measurePoints.value.length; i++) {
      const p1 = measurePoints.value[i - 1]
      const p2 = measurePoints.value[i]
      total += map?.distance(p1, p2) || 0
    }
    measureResult.value = `距离：${total < 1000 ? total.toFixed(1) + ' m' : (total / 1000).toFixed(2) + ' km'}`
  } else if (measureMode.value === 'area') {
    // 简单的面积计算（球面多边形）
    const area = calculatePolygonArea(measurePoints.value)
    measureResult.value = `面积：${area < 1000000 ? area.toFixed(0) + ' m²' : (area / 1000000).toFixed(2) + ' km²'}`
  }
}

function calculatePolygonArea(points: [number, number][]): number {
  if (points.length < 3) return 0
  // 简化的平面面积计算（仅用于显示）
  let area = 0
  const R = 6378137
  for (let i = 0; i < points.length; i++) {
    const p1 = points[i]
    const p2 = points[(i + 1) % points.length]
    area += (p2[1] - p1[1]) * (R * Math.PI / 180) * (R * Math.cos(p1[0] * Math.PI / 180) * Math.PI / 180)
  }
  return Math.abs(area / 2)
}

function setMapCursor(cursor: string) {
  if (mapContainerRef.value) {
    mapContainerRef.value.style.cursor = cursor
  }
}

// ========== 图层管理 ==========
function refreshLayersFromStore() {
  if (!map) return

  // 移除所有图层
  layerMap.forEach((layer, id) => {
    map?.removeLayer(layer)
  })
  layerMap.clear()

  // 添加新图层
  mapStore.sortedLayers.forEach((item) => {
    if (item.visible && item.data) {
      addLayer(item.data)
    }
  })

  updateStatusBar()
}

function addLayer(layer: MapLayer) {
  if (!map) return
  layerDataById.set(layer.id, layer)

  try {
    const style = layer.style || {}
    const type = (layer.type || '').toLowerCase()
    
    // 线图层
    if (type === 'polyline' || type === 'line' || type === 'linestring' || 
        type === '线' || type === '线状' || type === '道路' || type === '河流' || type === '边界') {
      addPolylineLayer(layer, style)
      return
    }
    
    // 面图层
    if (type === 'polygon' || type === 'area' || type === 'polygon' || 
        type === '面' || type === '面状' || type === '水体' || type === '湖泊' || type === '建筑') {
      addPolygonLayer(layer, style)
      return
    }
    
    // 点图层
    if (type === 'circlemarker' || type === 'point' || type === 'marker' || type === 'point' || 
        type === '点' || type === '点状' || type === '地标' || type === 'poi') {
      addPointLayer(layer, style)
      return
    }
    
    // 文字标注图层
    if (type === 'textlabel' || type === 'label' || type === 'text' || 
        type === '标注' || type === '注记' || type === '文字' || type === '名称') {
      addTextLabelLayer(layer, style)
      return
    }
    
    // 热力图图层
    if (type === 'heatmap' || type === 'heat' || type === '热力图') {
      addHeatmapLayer(layer, style)
      return
    }
    
    // 尝试用GeoJSON方式渲染
    if (layer.data) {
      addGeoJsonLayer(layer, style)
      return
    }
    
    // 如果有coordinates，尝试根据坐标格式判断
    if (layer.coordinates) {
      const coords = layer.coordinates
      if (Array.isArray(coords) && coords.length > 0) {
        const first = coords[0]
        if (Array.isArray(first)) {
          // 二维数组，可能是线或面
          if (first.length >= 4) {
            // 可能是面（闭合的）
            addPolygonLayer(layer, style)
          } else {
            // 可能是线
            addPolylineLayer(layer, style)
          }
        } else if (typeof first === 'number') {
          // 扁平数组，可能是点或线
          if (coords.length === 2) {
            // 单个点
            addPointLayer(layer, style)
          } else {
            // 多个点，可能是线
            addPolylineLayer(layer, style)
          }
        }
      }
    }
  } catch (e) {
    console.error('添加图层失败', layer.id, layer.name, layer.type, e)
  }
}

// 坐标标准化：智能体生成的是 [lat, lng] 格式，Leaflet 也用 [lat, lng] 格式
// 主要处理扁平数组转二维数组的情况
function normalizeCoords(coordinates: any): [number, number][] | null {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return null
  
  const first = coordinates[0]
  if (first == null) return null
  
  // 扁平数组：[lat1, lng1, lat2, lng2, ...]
  if (typeof first === 'number') {
    if (coordinates.length >= 2 && typeof coordinates[1] === 'number' && !Array.isArray(coordinates[1])) {
      const result: [number, number][] = []
      for (let i = 0; i < coordinates.length; i += 2) {
        if (i + 1 < coordinates.length) {
          // 智能体生成的是 [lat, lng] 格式，Leaflet 也用 [lat, lng]，直接用
          result.push([coordinates[i], coordinates[i + 1]])
        }
      }
      return result.length > 0 ? result : null
    }
    // 单个点
    if (coordinates.length >= 2) {
      return [[coordinates[0], coordinates[1]]]
    }
    return null
  }
  
  // 二维数组：[[lat, lng], [lat, lng], ...]
  if (Array.isArray(first) && first.length >= 2) {
    return coordinates.map((c: number[]) => [c[0], c[1]] as [number, number])
  }
  
  return null
}

// ========== features 型图层支持（carto-agent-1 同款：区县政区/专题面等以 features 存储） ==========
function validLatLng(c: any): c is [number, number] {
  return (
    Array.isArray(c) &&
    c.length >= 2 &&
    typeof c[0] === 'number' &&
    typeof c[1] === 'number' &&
    isFinite(c[0]) &&
    isFinite(c[1]) &&
    c[0] >= -90 &&
    c[0] <= 90 &&
    c[1] >= -180 &&
    c[1] <= 180
  )
}

/** 过滤出有效的 [lat, lng] 坐标对 */
function filterValidCoords(coords: any): [number, number][] {
  if (!Array.isArray(coords)) return []
  return coords.filter((c: any) => validLatLng(c)) as [number, number][]
}

/** 将 feature 的 coordinates 转换为 Leaflet 多边形环数组（支持多环/带洞面） */
function polygonRingsFromFeature(coords: any): [number, number][][] {
  if (!Array.isArray(coords) || coords.length === 0) return []
  // 单个环：[[lat,lng], [lat,lng], ...]
  if (validLatLng(coords[0])) {
    const ring = filterValidCoords(coords)
    return ring.length >= 3 ? [ring] : []
  }
  // 多环：[[[lat,lng],...], [[lat,lng],...], ...]
  return coords
    .map((ring: any) => filterValidCoords(ring))
    .filter((ring: [number, number][]) => ring.length >= 3)
}

// 线图层
function addPolylineLayer(layer: MapLayer, style: any) {
  // features 型线图层（专题地图）
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates) return
      const featStyle = feat.style || style
      const coords = filterValidCoords(
        Array.isArray(feat.coordinates[0]) ? feat.coordinates : [feat.coordinates],
      )
      if (coords.length < 2) return
      L.polyline(coords, {
        color: featStyle.color || style.color || '#3388ff',
        weight: featStyle.weight || style.weight || 3,
        opacity: featStyle.opacity !== undefined ? featStyle.opacity : (style.opacity !== undefined ? style.opacity : 1),
        dashArray: featStyle.dashArray || style.dashArray || undefined,
      }).addTo(group)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const line = L.polyline(coords, {
    color: style.color || '#3388ff',
    weight: style.weight || 3,
    opacity: style.opacity !== undefined ? style.opacity : 1,
    dashArray: style.dashArray || undefined,
  }).addTo(map!)
  
  layerMap.set(layer.id, line)
}

// 面图层
function addPolygonLayer(layer: MapLayer, style: any) {
  // features 型面图层（行政区划图：区县政区等 24 个面；carto-agent-1 同款渲染）
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    const isAdmin = mapStore.mapType === 'administrative'
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates) return
      const featStyle = feat.style || style
      const rings = polygonRingsFromFeature(feat.coordinates)
      if (rings.length === 0) return

      let fColor = featStyle.color || style.color || '#3388ff'
      let fFill = featStyle.fillColor || featStyle.color || style.fillColor || style.color || '#3388ff'
      let fWeight = featStyle.weight || style.weight || 1
      let fOpac = featStyle.opacity !== undefined ? featStyle.opacity : (style.opacity !== undefined ? style.opacity : 0.5)
      let fFillOpac = featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : (style.fillOpacity !== undefined ? style.fillOpacity : 0.4)

      // 行政区划图：极浅填色露出底图（与 carto-agent-1 旧前端一致）
      if (isAdmin) {
        fFillOpac = 0.2
        fWeight = 0
        fFill = '#f0f4f8'
      }

      const poly = L.polygon(rings, {
        color: fColor,
        fillColor: fFill,
        weight: fWeight,
        opacity: fOpac,
        fillOpacity: fFillOpac,
      })

      // 悬停交互：边界红色加粗高亮、区块微泛白（carto-agent-1 同款）
      if (isAdmin) {
        poly.on('mouseover', function (this: L.Polygon) {
          this.setStyle({ weight: 3, color: '#FF0000', fillOpacity: 0.12 })
          this.bringToFront()
        })
        poly.on('mouseout', function (this: L.Polygon) {
          this.setStyle({ weight: fWeight, color: fColor, fillOpacity: fFillOpac })
        })
      }
      group.addLayer(poly)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const polygon = L.polygon(coords, {
    color: style.borderColor || style.color || '#3388ff',
    fillColor: style.fillColor || style.color || '#3388ff',
    weight: style.weight || 2,
    opacity: style.opacity !== undefined ? style.opacity : 1,
    fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
  }).addTo(map!)
  
  layerMap.set(layer.id, polygon)
}

// 点图层
function addPointLayer(layer: MapLayer, style: any) {
  // features 型点图层（专题地图点/圆点）
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates) return
      const featStyle = feat.style || style
      if (!validLatLng(feat.coordinates)) return
      const coord = [feat.coordinates[0], feat.coordinates[1]] as [number, number]
      L.circleMarker(coord, {
        radius: featStyle.radius || style.radius || 6,
        color: featStyle.color || style.color || '#3388ff',
        fillColor: featStyle.fillColor || featStyle.color || style.fillColor || style.color || '#3388ff',
        fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : (style.fillOpacity !== undefined ? style.fillOpacity : 0.7),
        weight: featStyle.weight || style.weight || 2,
      }).addTo(group)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  // 多个点
  if (coords.length > 1) {
    const layerGroup = L.layerGroup()
    coords.forEach((coord) => {
      const marker = L.circleMarker(coord, {
        radius: style.radius || 4,
        fillColor: style.color || '#f59e0b',
        color: style.borderColor || '#fff',
        weight: style.weight || 2,
        opacity: style.opacity !== undefined ? style.opacity : 1,
        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.8,
      })
      layerGroup.addLayer(marker)
    })
    layerGroup.addTo(map!)
    layerMap.set(layer.id, layerGroup)
  } else {
    // 单个点
    const marker = L.circleMarker(coords[0], {
      radius: style.radius || 4,
      fillColor: style.color || '#f59e0b',
      color: style.borderColor || '#fff',
      weight: style.weight || 2,
      opacity: style.opacity !== undefined ? style.opacity : 1,
      fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.8,
    }).addTo(map!)
    layerMap.set(layer.id, marker)
  }
}

// 文字标注图层
function addTextLabelLayer(layer: MapLayer, style: any) {
  // features 型注记图层
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates || !validLatLng(feat.coordinates)) return
      const featStyle = feat.style || style
      const text = feat.properties?.name || feat.name || ''
      if (!text) return
      const coord = [feat.coordinates[0], feat.coordinates[1]] as [number, number]
      L.marker(coord, {
        icon: L.divIcon({
          className: 'text-label-icon',
          html: `<div style="
            color: ${featStyle.color || style.color || '#1a1a1a'};
            font-size: ${featStyle.fontSize || style.fontSize || 13}px;
            font-weight: ${featStyle.fontWeight || style.fontWeight || 'normal'};
            text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff;
            white-space: nowrap;
            text-align: center;
          ">${text}</div>`,
          iconSize: [100, 20],
          iconAnchor: [50, 10],
        }),
        interactive: false,
      }).addTo(group)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const layerGroup = L.layerGroup()
  
  coords.forEach((coord, idx) => {
    const text = layer.properties?.[idx]?.name || layer.name || ''
    if (!text) return
    
    const marker = L.marker(coord, {
      icon: L.divIcon({
        className: 'text-label-icon',
        html: `<div style="
          color: ${style.color || '#1a1a1a'};
          font-size: ${style.fontSize || 13}px;
          font-weight: ${style.fontWeight || 'normal'};
          text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff;
          white-space: nowrap;
          text-align: center;
        ">${text}</div>`,
        iconSize: [100, 20],
        iconAnchor: [50, 10],
      }),
      interactive: false,
    })
    layerGroup.addLayer(marker)
  })
  
  layerGroup.addTo(map!)
  layerMap.set(layer.id, layerGroup)
}

// 热力图图层（简化版，用circleMarker模拟）
function addHeatmapLayer(layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const layerGroup = L.layerGroup()
  
  coords.forEach((coord) => {
    const marker = L.circleMarker(coord, {
      radius: style.radius || 25,
      fillColor: '#ff6b6b',
      color: 'transparent',
      weight: 0,
      fillOpacity: 0.15,
    })
    layerGroup.addLayer(marker)
  })
  
  layerGroup.addTo(map!)
  layerMap.set(layer.id, layerGroup)
}

// GeoJSON图层
function addGeoJsonLayer(layer: MapLayer, style: any) {
  const geoJsonLayer = L.geoJSON(layer.data as any, {
    style: (feature) => {
      return {
        color: style.borderColor || style.color || '#3388ff',
        fillColor: style.fillColor || style.color || '#3388ff',
        weight: style.weight || 2,
        opacity: style.opacity !== undefined ? style.opacity : 1,
        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
      }
    },
    pointToLayer: (feature, latlng) => {
      return L.circleMarker(latlng, {
        radius: style.radius || 4,
        fillColor: style.color || '#3388ff',
        color: style.borderColor || style.color || '#3388ff',
        weight: style.weight || 1,
        opacity: style.opacity !== undefined ? style.opacity : 1,
        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.8,
      })
    },
  }).addTo(map!)
  
  layerMap.set(layer.id, geoJsonLayer)
}

function getLayerStyle(layer: MapLayer, feature: any): L.PathOptions {
  return {
    color: layer.style?.borderColor || layer.style?.color || '#3388ff',
    fillColor: layer.style?.color || '#3388ff',
    weight: layer.style?.weight || 2,
    opacity: layer.style?.opacity || 1,
    fillOpacity: layer.style?.fillOpacity || 0.3,
  }
}

function handleZoomToLayer(e: Event) {
  const layerId = (e as CustomEvent).detail?.layerId
  if (!layerId || !map) return

  const layer = layerMap.get(layerId)
  if (layer) {
    const bounds = (layer as any).getBounds?.()
    if (bounds) {
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }
}

// ========== 渲染地图数据 ==========
function renderMap(mapData: MapData) {
  if (!map || !mapData) return

  // 设置中心和缩放
  if (mapData.center && mapData.center.length >= 2) {
    map.setView([mapData.center[0], mapData.center[1]], mapData.zoom || CONFIG.defaultZoom)
  }

  // 设置底图：行政区划图与 carto-agent-1 一致，强制制图底图（无瓦片）
  if (mapData.map_type === 'administrative') {
    setTheme('plain')
  } else if (mapData.theme && mapData.theme !== currentTheme.value) {
    setTheme(mapData.theme)
  }

  // 直接从mapData渲染图层
  if (mapData.layers && mapData.layers.length > 0) {
    // 先清除现有图层
    layerMap.forEach((layer, id) => {
      map?.removeLayer(layer)
    })
    layerMap.clear()

    // 按图层顺序排序（面在下，线在中，点和文字在上）
    const sortedLayers = [...mapData.layers].sort((a, b) => layerZ(a) - layerZ(b))
    
    // 添加新图层
    sortedLayers.forEach((layer) => {
      addLayer(layer)
    })
    // LOD 载负量控制（与 carto-agent-1 map-lod.js 一致）
    applyLod()
  }

  updateStatusBar()

  // 自动取景：行政区划图按"武汉全域+周边地市"取景（maxZoom 10.5，与 carto-agent-1 一致）
  if (mapData.map_type === 'administrative') {
    fitAdminBounds(mapData)
  } else if (mapData.layers && mapData.layers.length > 0) {
    const layers = mapData.layers
    setTimeout(() => fitToLayers(layers), 100)
  }
}

// ========== LOD 载负量控制（移植自 carto-agent-1 frontend/src/js/map-lod.js） ==========
const ROAD_LEVEL: Record<string, number> = {
  motorway: 0, motorway_link: 1,
  trunk: 1, trunk_link: 2,
  primary: 2, primary_link: 3,
  secondary: 3, secondary_link: 4,
  tertiary: 4, tertiary_link: 5,
  residential: 5, living_street: 5, service: 5, unclassified: 5, other: 5,
}

function roadLevel(layer: MapLayer): number {
  const nm = layer.name || ''
  // 优先使用后端标注的道路等级（metadata.raw_class）
  const raw = (layer.metadata as any)?.raw_class
  if (raw && ROAD_LEVEL[raw] !== undefined) return ROAD_LEVEL[raw]
  if (nm.indexOf('道路-') === 0) {
    const l = nm.replace('道路-', '').split('_')[0]
    if (ROAD_LEVEL[l] !== undefined) return ROAD_LEVEL[l]
    // 中文道路名映射
    if (/高速公路|高速互通/.test(nm)) return 0
    if (/城市干线主干道|主干道连接|主干道衔接/.test(nm)) return 1
    if (/城市主干道/.test(nm)) return 2
    if (/城市次干道|次干道连接/.test(nm)) return 3
    if (/三级道路/.test(nm)) return 4
    return 5
  }
  if (/高速公路/.test(nm)) return 0
  if (/国道|主干道/.test(nm)) return 1
  if (/省道|主要道路/.test(nm)) return 2
  if (/次干道/.test(nm)) return 3
  if (/三级道路/.test(nm)) return 4
  return 5
}

/** 按比例尺分级显隐（五档：概览/市域/城区/街区/详图），与 carto-agent-1 map-lod.js 完全一致 */
function lodVisible(layer: MapLayer, zoom: number): boolean {
  const _z = zoom
  const _nm = layer.name || ''
  const t = layer.type || ''
  // ---- 道路分级 ----
  if ((t === 'polyline' || t === 'line') &&
      (_nm.indexOf('道路-') === 0 || /高速|国道|主干道|省道|次干道|支路|社区道路|服务道路|其他道路|三级道路/.test(_nm))) {
    const level = roadLevel(layer)
    let maxShow = 5
    if (_z < 9) maxShow = 0
    else if (_z < 11) maxShow = 1
    else if (_z < 13) maxShow = 3
    else if (_z < 15) maxShow = 4
    return level <= maxShow
  }
  // ---- 水系 ----
  if (t === 'polyline' || t === 'line') {
    if (_nm === '河流中心线（主要）') return _z >= 9
    if (_nm === '河流中心线（支流）') return _z >= 12
    if (_nm === '等高线（计曲线）') return _z >= 9
    if (_nm === '等高线（首曲线）') return _z >= 11
    if (_nm === '支流溪流' || /河源细流/.test(_nm)) return _z >= 13
    if (_nm === '主要河流') return _z >= 11
    return true
  }
  // ---- 面要素 ----
  if (t === 'polygon' || t === 'area') {
    if (_nm === '河流水面') return _z >= 11
    if (_nm === '集中居民地（大型）') return _z >= 11
    if (_nm === '集中居民地（中型）') return _z >= 13
    if (_nm === '集中居民地（小型）') return _z >= 15
    if (_nm === '湖泊（概览级）' || _nm === '湖泊点符号（概览）') return _z >= 6 && _z < 9
    if (_nm === '湖泊（市域级）') return _z >= 9 && _z < 11
    if (_nm === '湖泊（城区级）') return _z >= 11 && _z < 13
    if (_nm === '湖泊（详图级）') return _z >= 13
    if (/住宅|公寓|宿舍|商业|零售|酒店|工业|公共|政府|学校|大学|医院|宗教|文化|体育|停车|车库|仓储|交通枢纽|农业|温室/.test(_nm)) return _z >= 13
    if (/绿地|公园|森林|草地|草甸|用地/.test(_nm)) return _z >= 11
    return true
  }
  // ---- 注记 ----
  if (t === 'textLabel' || t === 'label') {
    if (_nm === '水系注记') return _z >= 12
    if (_nm === '区县名称标注') return _z >= 9
    if (_nm === '地标名称' || _nm === '重点地标') return _z >= 11
    return true
  }
  // ---- POI/符号 ----
  if (t === 'circleMarker' || t === 'point' || t === 'marker') {
    if (_nm === '湖泊点符号（概览）') return _z >= 6 && _z < 9
    if (_nm === '市级行政中心' || _nm === '区县行政中心' || _nm === '乡镇居民点') return _z >= 8
    if (_nm === '重点地标') return _z >= 11
    return _z >= 12
  }
  return true
}

/** 缩放变化时按 LOD 规则显隐图层 */
function applyLod() {
  if (!map) return
  const zoom = map.getZoom()
  layerMap.forEach((layer, id) => {
    const data = layerDataById.get(id)
    if (!data) return
    const visible = data.visible !== false && lodVisible(data, zoom)
    const onMap = map!.hasLayer(layer)
    if (visible && !onMap) layer.addTo(map!)
    if (!visible && onMap) map!.removeLayer(layer)
  })
}

/** 行政区划图取景：武汉全域 + 周边相邻地市（与 carto-agent-1 规范九-5 一致） */
function fitAdminBounds(mapData: MapData) {
  if (!map) return
  const bounds = L.latLngBounds([])
  const collect = (c: any) => {
    if (!Array.isArray(c)) return
    if (c.length >= 2 && typeof c[0] === 'number' && !isNaN(c[0]) && !isNaN(c[1])) {
      bounds.extend([c[0], c[1]])
    } else {
      c.forEach(collect)
    }
  }
  ;(mapData.layers || []).forEach((ld) => {
    const t = ld.type || ''
    if (['polygon', 'polyline', 'circleMarker', 'textLabel', 'line'].includes(t)) {
      if (ld.coordinates) collect(ld.coordinates)
      if (ld.features && Array.isArray(ld.features)) {
        ld.features.forEach((f: any) => { if (f.coordinates) collect(f.coordinates) })
      }
    }
  })
  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [12, 12], maxZoom: 10.5 })
  }
}

// 图层Z轴顺序（和carto-agent-1保持一致）
function layerZ(layer: MapLayer): number {
  const t = layer.type || ''
  const n = layer.name || ''
  if (t === 'polygon' || t === 'area') {
    if (/水体|湖泊|水库/.test(n)) return 150
    if (/建筑|住宅|商业/.test(n)) return 200
    return 100
  }
  if (t === 'polyline' || t === 'line') {
    if (/水系|河流/.test(n)) return 330
    if (/边界|市域|省界|县界/.test(n)) return 460
    if (/铁路|地铁|轻轨|高铁/.test(n)) return 500
    return 400
  }
  if (t === 'textLabel' || t === 'label') return 650
  return 600
}

function fitToLayers(layers: MapLayer[]) {
  if (!map || layers.length === 0) return

  let bounds: L.LatLngBounds | null = null

  layers.forEach((layer) => {
    const layerObj = layerMap.get(layer.id)
    if (layerObj) {
      const layerBounds = (layerObj as any).getBounds?.()
      if (layerBounds) {
        if (bounds) {
          bounds.extend(layerBounds)
        } else {
          bounds = layerBounds
        }
      }
    }
  })

  if (bounds) {
    map.fitBounds(bounds, { padding: [50, 50] })
  }
}

// ========== 编辑模式 ==========
function enterEditMode() {
  editStore.setActive(true)
}

function exitEditMode() {
  editStore.setActive(false)
  clearVertexMarkers()
}

function clearVertexMarkers() {
  vertexMarkers.forEach((m) => m.remove())
  vertexMarkers = []
}

function undoEdit() {
  // 撤销编辑
  console.log('undo edit')
}

function redoEdit() {
  // 重做编辑
  console.log('redo edit')
}

// ========== 导出图片 ==========
function handleExportImage() {
  if (!map) return
  alert('导出功能开发中...')
}

// ========== 自然语言修改 ==========
async function handleModify() {
  if (!modifyInput.value.trim()) return

  try {
    const res = await api.modifyMap(
      mapStore.currentMapData?.map_id ?? '',
      modifyInput.value,
    )

    if (res.success && res.data) {
      if (res.data.mapData) {
        renderMap(res.data.mapData)
      }
    }
  } catch (e) {
    console.error('修改地图失败', e)
  }

  modifyInput.value = ''
}
</script>

<style scoped>
.map-panel {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

#map-container {
  width: 100%;
  height: calc(100% - 44px);
  position: absolute;
  top: 44px;
  left: 0;
  background: #FAF8F3;
  /* 内图廓框线（与 carto-agent-1 行政区划图一致：灰-白-灰三层描边） */
  box-shadow: inset 0 0 0 2px #6b7280, inset 0 0 0 5px #ffffff, inset 0 0 0 6px #9ca3af;
}

/* 自然语言修改输入框 */
.map-modify-wrapper {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1000;
  background: white;
  padding: 8px 12px;
  border-radius: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.map-modify-input {
  width: 320px;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.map-modify-input:focus {
  border-color: var(--color-primary, #a78bfa);
}

.map-modify-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary, #a78bfa), var(--color-primary-dark, #8b5cf6));
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s, box-shadow 0.2s;
}

.map-modify-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(167, 139, 250, 0.4);
}

/* 图例按钮 */
.map-legend-btn {
  position: absolute;
  top: 60px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  z-index: 1000;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.map-legend-btn:hover {
  border-color: var(--color-primary, #a78bfa);
  color: var(--color-primary, #a78bfa);
}

.map-legend-btn.active {
  background: var(--color-primary-50, #f5f3ff);
  border-color: var(--color-primary, #a78bfa);
  color: var(--color-primary, #a78bfa);
}

.map-legend-btn i {
  font-size: 14px;
}

/* 路径规划面板 */
.map-route-panel {
  position: absolute;
  top: 60px;
  right: 12px;
  width: 280px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  overflow: hidden;
}

.route-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--color-primary, #a78bfa), var(--color-primary-dark, #8b5cf6));
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.route-panel-close {
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  font-size: 16px;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.route-panel-close:hover {
  opacity: 1;
}

.route-panel-body {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.route-field {
  margin-bottom: 14px;
}

.route-field label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
  font-weight: 500;
}

.route-hint {
  font-weight: 400;
  color: #9ca3af;
  font-size: 11px;
}

.route-profile-group {
  display: flex;
  gap: 6px;
}

.route-profile-group button {
  flex: 1;
  padding: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 12px;
  color: #6b7280;
  transition: all 0.2s;
}

.route-profile-group button:hover {
  border-color: var(--color-primary, #a78bfa);
}

.route-profile-group button.active {
  background: var(--color-primary-50, #f5f3ff);
  border-color: var(--color-primary, #a78bfa);
  color: var(--color-primary, #a78bfa);
}

.route-coord-input {
  display: flex;
  gap: 8px;
}

.route-input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.route-input:focus {
  border-color: var(--color-primary, #a78bfa);
}

.route-start-icon {
  color: #22c55e;
}

.route-end-icon {
  color: #ef4444;
}

.route-plan-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--color-primary, #a78bfa), var(--color-primary-dark, #8b5cf6));
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-top: 8px;
}

.route-plan-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(167, 139, 250, 0.4);
}

.route-result {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f3f4f6;
}

.route-result-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.route-stat {
  text-align: center;
}

.route-stat-label {
  display: block;
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 2px;
}

.route-stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.route-steps {
  max-height: 200px;
  overflow-y: auto;
}

.route-step {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  font-size: 12px;
  color: #4b5563;
  border-bottom: 1px solid #f9fafb;
}

.route-step:last-child {
  border-bottom: none;
}

.route-step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary-100, #ede9fe);
  color: var(--color-primary, #a78bfa);
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 测量工具提示 */
.measure-tooltip {
  position: absolute;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: white;
  border-radius: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}

.measure-tooltip i {
  color: var(--color-primary, #a78bfa);
}

/* 底部状态栏 */
.map-status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 20px;
  font-size: 11px;
  color: #6b7280;
  z-index: 1000;
}

.map-status-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.map-status-item i {
  font-size: 11px;
  color: #9ca3af;
}

.status-quality {
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.status-quality.ok {
  background: #dcfce7;
  color: #16a34a;
}

.status-quality.warn {
  background: #fef3c7;
  color: #d97706;
}

.status-edit {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  background: #f3f4f6;
  color: #6b7280;
}

.status-edit.editing {
  background: #dbeafe;
  color: #2563eb;
}

/* Leaflet控件样式覆盖 */
:deep(.leaflet-control-zoom) {
  border: 1px solid #e5e7eb !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
  overflow: hidden;
}

:deep(.leaflet-control-zoom a) {
  width: 30px !important;
  height: 30px !important;
  line-height: 30px !important;
  font-size: 16px !important;
  color: #6b7280 !important;
  background: white !important;
  border-bottom: 1px solid #f3f4f6 !important;
}

:deep(.leaflet-control-zoom a:hover) {
  background: var(--color-primary-50, #f5f3ff) !important;
  color: var(--color-primary, #a78bfa) !important;
}

:deep(.leaflet-control-zoom a:last-child) {
  border-bottom: none !important;
}

:deep(.leaflet-control-scale-line) {
  border: 1px solid #6b7280 !important;
  border-top: none !important;
  color: #6b7280 !important;
  font-size: 11px !important;
  padding: 2px 6px !important;
  background: rgba(255, 255, 255, 0.9) !important;
}
</style>
