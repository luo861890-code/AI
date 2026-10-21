<template>
  <div class="analysis-panel">
    <div class="analysis-header">
      <span><i class="fa-solid fa-chart-line"></i> 空间分析</span>
      <button class="analysis-close" title="关闭" @click="appStore.toggleAnalysisPanel()">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>

    <div class="analysis-tabs">
      <button
        class="analysis-tab"
        :class="{ active: mode === 'buffer' }"
        @click="setMode('buffer')"
      >缓冲区</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'overlay' }"
        @click="setMode('overlay')"
      >叠加分析</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'nearest' }"
        @click="setMode('nearest')"
      >最近邻</button>
    </div>

    <div class="analysis-body">
      <div class="analysis-field">
        <label>源图层</label>
        <select v-model="sourceId" class="analysis-select">
          <option v-for="l in mapStore.sortedLayers" :key="l.id" :value="l.id">
            {{ l.data.name }}（{{ typeLabel(l.data.type) }}）
          </option>
        </select>
      </div>

      <div v-if="mode !== 'buffer'" class="analysis-field">
        <label>目标图层</label>
        <select v-model="targetId" class="analysis-select">
          <option v-for="l in mapStore.sortedLayers" :key="l.id" :value="l.id">
            {{ l.data.name }}（{{ typeLabel(l.data.type) }}）
          </option>
        </select>
      </div>

      <div v-if="mode === 'buffer'" class="analysis-field">
        <label>缓冲距离（km）</label>
        <input v-model.number="bufferKm" type="number" min="0.1" step="0.1" class="analysis-input" />
      </div>

      <button class="analysis-run-btn" :disabled="running" @click="run">
        <div v-if="running" class="analysis-spinner"></div>
        <i v-else class="fa-solid fa-play"></i>
        开始分析
      </button>

      <div v-if="message" class="analysis-message">{{ message }}</div>

      <div v-if="summary.length > 0" class="analysis-summary">
        <div class="analysis-summary-title">结果</div>
        <div v-for="(line, i) in summary" :key="i" class="analysis-summary-line">{{ line }}</div>
        <div v-if="resultLayerId" class="analysis-zoom" @click="zoomToResult">
          <i class="fa-solid fa-magnifying-glass-plus"></i> 缩放至结果图层
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import {
  bufferCoordinates,
  intersectPointPolygon,
  nearestPairs,
  layerPoints,
  layerRings,
} from '@/utils/analysis'
import type { MapLayer } from '@/types'
import type { LatLng } from '@/utils/analysis'

const appStore = useAppStore()
const mapStore = useMapStore()

const mode = ref<'buffer' | 'overlay' | 'nearest'>('buffer')
const sourceId = ref('')
const targetId = ref('')
const bufferKm = ref(1)
const running = ref(false)
const message = ref('')
const summary = ref<string[]>([])
const resultLayerId = ref('')

const sourceLayer = computed(() =>
  sourceId.value ? mapStore.layerGroups[sourceId.value]?.data : null
)
const targetLayer = computed(() =>
  targetId.value ? mapStore.layerGroups[targetId.value]?.data : null
)

function setMode(m: 'buffer' | 'overlay' | 'nearest') {
  mode.value = m
  message.value = ''
  summary.value = []
  resultLayerId.value = ''
}

function typeLabel(type: string): string {
  const labels: Record<string, string> = {
    polyline: '线',
    line: '线',
    polygon: '面',
    area: '面',
    circleMarker: '点',
    marker: '点',
    point: '点',
    textLabel: '标注',
    label: '标注',
    heatmap: '热力',
  }
  return labels[type] || type
}

function addResultLayer(name: string, type: string, coordinates: any, style: Record<string, any>) {
  const id = 'analysis_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7)
  const layer: MapLayer = {
    id,
    type: type as any,
    name,
    coordinates,
    properties: coordinates.map(() => ({})),
    style,
    group: '分析结果',
  }
  const maxOrder = Math.max(0, ...mapStore.sortedLayers.map((l) => l.order))
  mapStore.layerGroups[id] = { visible: true, data: layer, order: maxOrder + 1 }
  return id
}

function run() {
  message.value = ''
  summary.value = []
  resultLayerId.value = ''
  if (!sourceLayer.value) {
    message.value = '请选择源图层'
    return
  }
  running.value = true
  setTimeout(() => {
    try {
      if (mode.value === 'buffer') {
        runBuffer()
      } else if (mode.value === 'overlay') {
        runOverlay()
      } else {
        runNearest()
      }
    } catch (e: any) {
      message.value = '分析失败: ' + e.message
    } finally {
      running.value = false
    }
  }, 30)
}

function runBuffer() {
  const layer = sourceLayer.value!
  const rings = bufferCoordinates(layer.coordinates, layer.type || '', bufferKm.value || 1)
  if (rings.length === 0) {
    message.value = '源图层没有可缓冲的几何'
    return
  }
  const id = addResultLayer(`缓冲区（${bufferKm.value}km）`, 'polygon', rings, {
    color: '#7c3aed',
    fillColor: '#a78bfa',
    fillOpacity: 0.35,
    weight: 1.5,
  })
  resultLayerId.value = id
  summary.value = [
    `生成 ${rings.length} 个缓冲面`,
    `缓冲距离 ${bufferKm.value} km`,
    '结果已加入“分析结果”图层组',
  ]
}

function runOverlay() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择目标图层'
    return
  }
  const t = targetLayer.value
  const rings = layerRings(t.coordinates, t.type || '')
  if (rings.length === 0) {
    message.value = '目标图层没有面状几何，叠加分析需要目标为面图层'
    return
  }
  const pts = layerPoints(layer.coordinates, layer.type || '')
  if (pts.length === 0) {
    message.value = '源图层没有点状几何，暂支持“点 ∩ 面”叠加'
    return
  }
  const kept = intersectPointPolygon(pts, rings)
  if (kept.length === 0) {
    message.value = '没有点落在目标面内'
    return
  }
  const id = addResultLayer(`叠加结果（${layer.name} ∩ ${t.name}）`, 'circleMarker', kept, {
    color: '#ef4444',
    radius: 7,
    fillOpacity: 0.9,
    weight: 2,
  })
  resultLayerId.value = id
  summary.value = [
    `源点 ${pts.length} 个`,
    `保留 ${kept.length} 个（落在目标面内）`,
    '结果已加入“分析结果”图层组',
  ]
}

function runNearest() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择目标图层'
    return
  }
  const t = targetLayer.value
  const sources = layerPoints(layer.coordinates, layer.type || '')
  const targets = layerPoints(t.coordinates, t.type || '')
  if (sources.length === 0 || targets.length === 0) {
    message.value = '源/目标图层缺少点状几何'
    return
  }
  const pairs = nearestPairs(sources, targets)
  const segments = pairs.map((p) => p.segment)
  const id = addResultLayer(`最近邻连线（${layer.name} → ${t.name}）`, 'polyline', segments, {
    color: '#0ea5e9',
    weight: 2,
    opacity: 0.85,
  })
  resultLayerId.value = id
  const avg = pairs.reduce((s, p) => s + p.distanceKm, 0) / pairs.length
  const max = Math.max(...pairs.map((p) => p.distanceKm))
  summary.value = [
    `源 ${sources.length} 个要素，目标 ${targets.length} 个要素`,
    `平均最近距离 ${avg.toFixed(2)} km`,
    `最大最近距离 ${max.toFixed(2)} km`,
    '结果已加入“分析结果”图层组',
  ]
}

function zoomToResult() {
  if (!resultLayerId.value) return
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent('map-zoom-to-layer', { detail: { layerId: resultLayerId.value } }))
  }
}

watch(
  () => appStore.showAnalysisPanel,
  (show) => {
    if (show && appStore.analysisMode) {
      mode.value = appStore.analysisMode
      appStore.setAnalysisMode(null)
    }
  },
  { immediate: true }
)

watch(
  () => mapStore.currentMapId,
  () => {
    sourceId.value = mapStore.sortedLayers[0]?.id || ''
    targetId.value = mapStore.sortedLayers[1]?.id || mapStore.sortedLayers[0]?.id || ''
  }
)
</script>

<style scoped>
.analysis-panel {
  position: absolute;
  top: 48px;
  left: 12px;
  width: 300px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 26;
  overflow: hidden;
}

.analysis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
}

.analysis-close {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
}

.analysis-close:hover {
  background: rgba(0, 0, 0, 0.05);
}

.analysis-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border);
}

.analysis-tab {
  flex: 1;
  padding: 6px 4px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
}

.analysis-tab.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.analysis-body {
  padding: 12px 14px;
  font-size: 12px;
}

.analysis-field {
  margin-bottom: 10px;
}

.analysis-field label {
  display: block;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.analysis-select,
.analysis-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
}

.analysis-select:focus,
.analysis-input:focus {
  border-color: var(--color-primary-light);
}

.analysis-run-btn {
  width: 100%;
  padding: 9px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.analysis-run-btn:disabled {
  opacity: 0.6;
}

.analysis-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.analysis-message {
  margin-top: 10px;
  padding: 8px 10px;
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  border-radius: 6px;
  font-size: 11px;
}

.analysis-summary {
  margin-top: 10px;
  padding: 10px;
  background: #f8fafc;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.analysis-summary-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 6px;
}

.analysis-summary-line {
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.analysis-zoom {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--color-border);
  font-size: 11px;
  color: var(--color-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
}
</style>
