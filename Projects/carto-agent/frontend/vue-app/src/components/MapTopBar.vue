<template>
  <div class="map-top-bar">
    <span class="map-top-title">
      {{ mapStore.mapName || '未加载地图' }}
      <span v-if="mapStore.mapType === 'administrative'" class="map-version-tag">行政区版</span>
    </span>

    <span class="map-top-spacer"></span>

    <span class="map-top-ctrl-group">
      <label class="scale-setter-label">底图</label>
      <select
        class="map-theme-select"
        :value="mapStore.currentTheme"
        @change="onThemeChange"
      >
        <option v-for="(theme, key) in CONFIG.mapThemes" :key="key" :value="key">
          {{ theme.name }}
        </option>
      </select>
    </span>

    <span class="map-top-ctrl-group">
      <label class="scale-setter-label">比例尺</label>
      <input
        class="map-scale-input"
        :value="scaleText"
        placeholder="1:100000"
        inputmode="numeric"
        @keydown.enter="onScaleEnter"
        @blur="syncFromMap"
      />
    </span>

    <span class="map-top-ctrl-group">
      <label class="scale-setter-label">投影</label>
      <select
        class="map-theme-select"
        :value="currentProjection"
        @change="onProjectionChange"
      >
        <option v-for="proj in projections" :key="proj.value" :value="proj.value">
          {{ proj.name }}
        </option>
      </select>
    </span>

    <button
      class="map-top-btn"
      title="撤回上一步"
      @click="handleUndo"
    >
      <i class="fa-solid fa-rotate-left"></i>
    </button>

    <button
      class="map-top-btn"
      title="恢复"
      @click="handleRedo"
    >
      <i class="fa-solid fa-rotate-right"></i>
    </button>

    <button
      class="map-top-btn"
      title="清除地图"
      @click="handleClear"
    >
      <i class="fa-solid fa-trash-can"></i>
    </button>

    <button
      class="map-top-btn compass-btn"
      title="重置北方向"
      @click="handleResetNorth"
    >
      <span class="compass-n">北</span>
    </button>

    <button
      class="map-top-btn"
      :class="{ active: appStore.showGraticule }"
      title="经纬网"
      @click="appStore.toggleGraticule()"
    >
      <i class="fa-solid fa-border-all"></i>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { CONFIG } from '@/config'

const appStore = useAppStore()
const mapStore = useMapStore()

const scaleText = ref('')

const projections = [
  { name: 'Web墨卡托', value: 'webmercator' },
  { name: 'WGS84经纬度', value: 'wgs84' },
  { name: '高斯-克吕格', value: 'gauss' },
  { name: 'UTM投影', value: 'utm' },
  { name: '兰伯特等角', value: 'lambert' },
  { name: '阿尔伯斯等积', value: 'albers' },
]

const currentProjection = ref('webmercator')

function dispatch(name: string, detail?: any) {
  const el = document.getElementById('map-container')
  if (!el) return
  el.dispatchEvent(new CustomEvent(name, detail !== undefined ? { detail } : undefined))
}

function onThemeChange(e: Event) {
  const theme = (e.target as HTMLSelectElement).value
  dispatch('map-set-theme', { theme })
}

function onProjectionChange(e: Event) {
  const projection = (e.target as HTMLSelectElement).value
  currentProjection.value = projection
  dispatch('map-set-projection', { projection })
}

function handleUndo() {
  dispatch('map-undo')
}

function handleRedo() {
  dispatch('map-redo')
}

function handleClear() {
  if (confirm('确定要清除地图上的所有图层吗？')) {
    dispatch('map-clear-layers')
  }
}

function handleResetNorth() {
  dispatch('map-reset-north')
}

function onScaleEnter(e: Event) {
  const input = e.target as HTMLInputElement
  const digits = input.value.replace(/[^\d]/g, '')
  const denominator = parseInt(digits, 10)
  if (!denominator || denominator < 1000) {
    input.value = scaleText.value
    return
  }
  dispatch('map-set-scale', { denominator })
  input.blur()
}

function syncFromMap() {
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent('map-scale-request'))
  }
}

function handleScaleUpdate(e: Event) {
  const denominator = (e as CustomEvent).detail?.denominator
  if (denominator) {
    scaleText.value = '1:' + Number(denominator).toLocaleString('en-US').replace(/,/g, ' ')
  }
}

onMounted(() => {
  const el = document.getElementById('map-container')
  el?.addEventListener('map-scale-update', handleScaleUpdate as EventListener)
})

onUnmounted(() => {
  const el = document.getElementById('map-container')
  el?.removeEventListener('map-scale-update', handleScaleUpdate as EventListener)
})
</script>

<style scoped>
.map-top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
  z-index: 8;
  font-size: 12px;
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.06);
}

.map-top-title {
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.map-version-tag {
  font-size: 10px;
  font-weight: 500;
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
  border: 1px solid rgba(124, 58, 237, 0.25);
  padding: 1px 7px;
  border-radius: 10px;
  white-space: nowrap;
}

.map-top-spacer {
  flex: 1;
}

.map-top-ctrl-group {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.scale-setter-label {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.map-theme-select,
.map-scale-input {
  padding: 4px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  background: #fff;
  color: var(--color-text);
  outline: none;
  max-width: 150px;
}

.map-theme-select:focus,
.map-scale-input:focus {
  border-color: var(--color-primary-light);
}

.map-top-btn {
  width: 30px;
  height: 30px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  transition: all 0.15s;
}

.map-top-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.map-top-btn.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.compass-btn {
  font-weight: 700;
  font-size: 12px;
  color: #dc2626;
}

.compass-btn:hover {
  border-color: #dc2626;
  color: #dc2626;
}

.compass-n {
  font-family: 'SimHei', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 700;
}
</style>
