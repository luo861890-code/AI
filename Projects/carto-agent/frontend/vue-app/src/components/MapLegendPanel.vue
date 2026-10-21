<template>
  <div class="map-legend-panel">
    <div class="legend-panel-header">
      <span><i class="fa-solid fa-book-open"></i> 地图图例</span>
      <span class="legend-header-actions">
        <button class="legend-icon-btn" title="固定图例" @click="pinned = !pinned">
          <i class="fa-solid fa-thumbtack" :class="{ pinned }"></i>
        </button>
        <button class="legend-icon-btn" title="关闭" @click="appStore.toggleLegendPanel()">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </span>
    </div>

    <div class="legend-panel-body">
      <div class="legend-search-wrapper">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input
          v-model="searchQuery"
          type="text"
          class="legend-search-input"
          placeholder="搜索分类，如 道路 / 水系 / 医院..."
        />
      </div>

      <div v-if="legendData && legendData.items && legendData.items.length" class="legend-ai-section">
        <div class="legend-section-title">AI 图例</div>
        <div class="legend-items">
          <div
            v-for="item in filteredLegendItems"
            :key="item.label"
            class="legend-item"
            @click="zoomToLegendLayer(item.label)"
          >
            <span
              class="legend-symbol"
              :class="{ 'legend-line': item.type === 'line', 'legend-polygon': item.type === 'polygon' }"
              :style="{ background: item.fillColor || item.color || '#999', borderColor: item.color || '#999' }"
            ></span>
            <span class="legend-label">{{ item.label }}</span>
          </div>
        </div>
      </div>

      <div class="legend-section-title">图层</div>
      <div v-if="filteredLayers.length === 0" class="legend-empty">暂无图层</div>
      <div
        v-for="layer in filteredLayers"
        :key="layer.id"
        class="legend-layer-item"
        @click="zoomToLayer(layer.id)"
      >
        <label class="legend-layer-toggle" @click.stop>
          <input
            type="checkbox"
            :checked="layer.visible"
            @change="mapStore.toggleLayer(layer.id, ($event.target as HTMLInputElement).checked)"
          />
          <span class="legend-custom-checkbox"></span>
        </label>
        <span class="legend-layer-symbol" v-html="symbologyHtml(layer.data)"></span>
        <span class="legend-layer-name">{{ layer.data.name }}</span>
        <span class="legend-layer-type">{{ typeLabel(layer.data.type) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import type { MapLayer, LegendData, LegendItem, LayerType } from '@/types'

const props = defineProps<{
  legendData: LegendData | null
}>()

const appStore = useAppStore()
const mapStore = useMapStore()

const searchQuery = ref('')
const pinned = ref(false)

const filteredLayers = computed(() => {
  let layers = mapStore.sortedLayers
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    layers = layers.filter((l) => (l.data.name || '').toLowerCase().includes(q))
  }
  return layers
})

const filteredLegendItems = computed(() => {
  const items = props.legendData?.items || []
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return items
  return items.filter((i: LegendItem) => (i.label || '').toLowerCase().includes(q))
})

function dispatch(name: string, detail?: any) {
  const el = document.getElementById('map-container')
  if (!el) return
  el.dispatchEvent(new CustomEvent(name, detail !== undefined ? { detail } : undefined))
}

function zoomToLayer(layerId: string) {
  dispatch('map-zoom-to-layer', { layerId })
}

function zoomToLegendLayer(label: string) {
  const matched = mapStore.sortedLayers.filter((l) =>
    (l.data.name || '').includes(label) ||
    label.includes(l.data.name || '')
  )
  if (matched.length > 0) {
    zoomToLayer(matched[0].id)
  }
}

function typeLabel(type: LayerType): string {
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
    geojson: 'GeoJSON',
  }
  return labels[type] || type
}

function symbologyHtml(layer: MapLayer) {
  const st = layer.style || {}
  const t = layer.type || ''
  const color = st.color || '#3388ff'
  const fill = st.fillColor || color
  const w = Math.min(parseFloat(String(st.weight)) || 2, 6)
  const dash = st.dashArray || ''
  if (t === 'polyline' || t === 'line') {
    return `<svg width="24" height="10" viewBox="0 0 24 10"><line x1="1" y1="5" x2="23" y2="5" stroke="${color}" stroke-width="${w}" stroke-dasharray="${dash}" stroke-linecap="round"/></svg>`
  }
  if (t === 'polygon' || t === 'area') {
    return `<svg width="24" height="14" viewBox="0 0 24 14"><rect x="2" y="1" width="20" height="12" rx="2" fill="${fill}" fill-opacity="${st.fillOpacity ?? 0.6}" stroke="${color}" stroke-width="${Math.min(w, 3)}"/></svg>`
  }
  if (t === 'textLabel' || t === 'label') {
    return `<span class="legend-font-symbol" style="color:${color}">文</span>`
  }
  if (t === 'heatmap') {
    return `<span class="legend-heat-symbol" style="background:radial-gradient(circle, rgba(252,191,73,.9), rgba(187,55,84,.5), transparent)"></span>`
  }
  return `<span class="legend-dot-symbol" style="background:${color}"></span>`
}
</script>

<style scoped>
.map-legend-panel {
  position: absolute;
  top: 48px;
  right: 10px;
  bottom: 40px;
  width: 260px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 20;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.legend-panel-header {
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

.legend-header-actions {
  display: flex;
  gap: 2px;
}

.legend-icon-btn {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
  font-size: 12px;
}

.legend-icon-btn:hover {
  background: rgba(124, 58, 237, 0.08);
  color: var(--color-primary);
}

.legend-icon-btn .pinned {
  color: var(--color-primary);
  transform: rotate(45deg);
}

.legend-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.legend-search-wrapper {
  position: relative;
  margin-bottom: 8px;
}

.legend-search-wrapper i {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-secondary);
  font-size: 11px;
}

.legend-search-input {
  width: 100%;
  padding: 6px 10px 6px 26px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
}

.legend-search-input:focus {
  border-color: var(--color-primary-light);
}

.legend-ai-section {
  margin-bottom: 10px;
}

.legend-section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 8px 0 6px;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.legend-item:hover {
  background: rgba(124, 58, 237, 0.05);
}

.legend-symbol {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid;
  flex-shrink: 0;
}

.legend-symbol.legend-line {
  height: 3px;
  border: none;
  border-radius: 2px;
}

.legend-symbol.legend-polygon {
  background: rgba(0, 0, 0, 0.1) !important;
}

.legend-empty {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 16px 0;
}

.legend-layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.1s;
}

.legend-layer-item:hover {
  background: rgba(124, 58, 237, 0.05);
}

.legend-layer-toggle input {
  display: none;
}

.legend-custom-checkbox {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--color-border);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  transition: all 0.15s;
}

.legend-layer-toggle input:checked + .legend-custom-checkbox {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.legend-layer-toggle input:checked + .legend-custom-checkbox::after {
  content: '\f00c';
  font-family: 'Font Awesome 6 Free';
  font-weight: 900;
  font-size: 8px;
  color: #fff;
}

.legend-layer-symbol {
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.legend-dot-symbol {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  border: 1px solid rgba(0, 0, 0, 0.15);
}

.legend-font-symbol {
  font-size: 12px;
  font-weight: 600;
}

.legend-heat-symbol {
  width: 18px;
  height: 12px;
  display: inline-block;
}

.legend-layer-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-layer-type {
  font-size: 10px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
}
</style>
