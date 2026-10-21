<template>
  <div class="params-panel">
    <div class="params-panel-header">
      <span><i class="fa-solid fa-sliders"></i> 任务参数</span>
      <button class="params-panel-close" title="关闭" @click="appStore.toggleParamsPanel()">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <div class="params-panel-body">
      <div class="params-field">
        <label>地图</label>
        <div class="params-readonly">{{ mapStore.mapName || '-' }}</div>
      </div>
      <div class="params-row">
        <div class="params-field">
          <label>地图类型</label>
          <div class="params-readonly">{{ mapStore.mapType || '-' }}</div>
        </div>
        <div class="params-field">
          <label>区域</label>
          <div class="params-readonly">{{ mapStore.region || mapStore.mapType === 'administrative' ? '武汉市' : '-' }}</div>
        </div>
      </div>
      <div class="params-row">
        <div class="params-field">
          <label>缩放级别</label>
          <input v-model.number="zoom" type="number" min="3" max="18" />
        </div>
        <div class="params-field">
          <label>图层数</label>
          <div class="params-readonly">{{ mapStore.sortedLayers.length }}</div>
        </div>
      </div>
      <div class="params-field">
        <label>底图主题</label>
        <select v-model="theme">
          <option v-for="(t, key) in CONFIG.mapThemes" :key="key" :value="key">{{ t.name }}</option>
        </select>
      </div>
      <div class="params-row">
        <div class="params-field">
          <label>中心纬度</label>
          <input v-model.number="centerLat" type="number" step="0.0001" />
        </div>
        <div class="params-field">
          <label>中心经度</label>
          <input v-model.number="centerLng" type="number" step="0.0001" />
        </div>
      </div>
      <div class="params-actions">
        <button class="params-btn params-btn-primary" @click="applyParams">应用视图参数</button>
        <button class="params-btn" @click="regenerate">按参数重新生成</button>
      </div>
      <div class="params-hint">
        修改缩放/主题/中心后点“应用”即时生效；点“重新生成”按当前参数重建地图。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'
import { CONFIG } from '@/config'

const appStore = useAppStore()
const mapStore = useMapStore()

const zoom = ref(12)
const theme = ref('standard')
const centerLat = ref(30.5928)
const centerLng = ref(114.3055)

watch(
  () => mapStore.currentMapData,
  (data) => {
    if (!data) return
    zoom.value = data.zoom || 12
    theme.value = data.theme || 'standard'
    if (data.center && data.center.length >= 2) {
      centerLat.value = data.center[0]
      centerLng.value = data.center[1]
    }
  },
  { immediate: true }
)

function dispatchMapData(data: any) {
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent('map-apply-data', { detail: { data } }))
  }
}

async function applyParams() {
  if (!mapStore.currentMapId) {
    alert('请先生成地图')
    return
  }
  try {
    await api.updateTheme(mapStore.currentMapId, theme.value)
    await api.updateView(mapStore.currentMapId, {
      center: [centerLat.value, centerLng.value],
      zoom: zoom.value,
    })
    const resp = await api.getMap(mapStore.currentMapId)
    const data = resp.data || resp
    dispatchMapData(data)
    alert('视图参数已应用')
  } catch (e: any) {
    alert('应用参数失败: ' + e.message)
  }
}

async function regenerate() {
  if (!mapStore.currentMapData) {
    alert('请先生成地图')
    return
  }
  try {
    const mapType = mapStore.mapType || 'basic'
    const region = mapStore.region || '武汉市'
    const resp = await api.generateMap({ map_type: mapType, region, zoom: zoom.value })
    const data = resp.data || resp
    dispatchMapData(data)
    alert('地图已按参数重新生成')
  } catch (e: any) {
    alert('重新生成失败: ' + e.message)
  }
}
</script>

<style scoped>
.params-panel {
  position: absolute;
  top: 48px;
  left: 12px;
  width: 300px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 25;
  overflow: hidden;
}

.params-panel-header {
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

.params-panel-close {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
}

.params-panel-close:hover {
  background: rgba(0, 0, 0, 0.05);
}

.params-panel-body {
  padding: 12px 14px;
  font-size: 12px;
}

.params-field {
  margin-bottom: 10px;
}

.params-row {
  display: flex;
  gap: 10px;
}

.params-row .params-field {
  flex: 1;
}

.params-field label {
  display: block;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.params-field input,
.params-field select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
}

.params-readonly {
  padding: 6px 8px;
  border: 1px dashed var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  background: #fafbfc;
}

.params-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.params-btn {
  flex: 1;
  padding: 8px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.params-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.params-btn-primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-color: transparent;
}

.params-hint {
  margin-top: 10px;
  font-size: 11px;
  color: var(--color-text-tertiary);
  line-height: 1.5;
}
</style>
