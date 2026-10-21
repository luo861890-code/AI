<template>
  <div v-if="appStore.showStylePanel" class="style-panel-overlay" @click.self="closePanel">
    <div class="style-panel">
      <!-- 面板头部 -->
      <div class="panel-header">
        <div class="panel-title">
          <i class="fa-solid fa-palette"></i>
          <span>样式编辑器</span>
        </div>
        <button class="close-btn" @click="closePanel">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- 当前图层信息 -->
      <div v-if="selectedLayer" class="layer-info">
        <span class="layer-color-dot" :style="getLayerColorStyle()"></span>
        <span class="layer-name">{{ selectedLayer.data.name || '未命名图层' }}</span>
        <span class="layer-type-badge">{{ getLayerTypeLabel(selectedLayer.data.type) }}</span>
      </div>

      <!-- 渲染模式选择 -->
      <div class="style-section">
        <div class="section-title">渲染模式</div>
        <div class="render-modes">
          <button
            v-for="mode in renderModes"
            :key="mode.value"
            class="mode-btn"
            :class="{ active: currentRenderMode === mode.value }"
            @click="currentRenderMode = mode.value"
          >
            <i :class="mode.icon"></i>
            <span>{{ mode.label }}</span>
          </button>
        </div>
      </div>

      <!-- 单点样式 -->
      <div v-if="currentRenderMode === 'single'" class="style-section">
        <div class="section-title">基本样式</div>
        
        <div class="style-row">
          <label>填充颜色</label>
          <div class="color-input-group">
            <input type="color" v-model="styleForm.fillColor" @input="applyStyle" class="color-picker" />
            <input type="text" v-model="styleForm.fillColor" @input="applyStyle" class="color-text" />
          </div>
        </div>

        <div class="style-row">
          <label>边框颜色</label>
          <div class="color-input-group">
            <input type="color" v-model="styleForm.color" @input="applyStyle" class="color-picker" />
            <input type="text" v-model="styleForm.color" @input="applyStyle" class="color-text" />
          </div>
        </div>

        <div class="style-row">
          <label>填充透明度</label>
          <div class="slider-group">
            <input type="range" min="0" max="1" step="0.05" v-model.number="styleForm.fillOpacity" @input="applyStyle" class="slider" />
            <span class="slider-value">{{ Math.round(styleForm.fillOpacity * 100) }}%</span>
          </div>
        </div>

        <div v-if="isLineOrPoint" class="style-row">
          <label>边框宽度</label>
          <div class="slider-group">
            <input type="range" min="0" max="20" step="1" v-model.number="styleForm.weight" @input="applyStyle" class="slider" />
            <span class="slider-value">{{ styleForm.weight }}px</span>
          </div>
        </div>

        <div v-if="isLineLayer" class="style-row">
          <label>线条样式</label>
          <select v-model="styleForm.dashArray" @change="applyStyle" class="select-input">
            <option :value="null">实线</option>
            <option value="5,5">虚线</option>
            <option value="10,5">长虚线</option>
            <option value="2,2">点线</option>
            <option value="10,5,2,5">点划线</option>
          </select>
        </div>

        <div v-if="isPointLayer" class="style-row">
          <label>点半径</label>
          <div class="slider-group">
            <input type="range" min="1" max="30" step="1" v-model.number="styleForm.radius" @input="applyStyle" class="slider" />
            <span class="slider-value">{{ styleForm.radius }}px</span>
          </div>
        </div>
      </div>

      <!-- 分类渲染 -->
      <div v-if="currentRenderMode === 'categorized'" class="style-section">
        <div class="section-title">分类渲染</div>
        <div class="section-hint">根据属性字段对要素进行分类着色</div>
        
        <div class="style-row">
          <label>分类字段</label>
          <select v-model="categoryField" class="select-input">
            <option value="">选择字段...</option>
            <option v-for="field in availableFields" :key="field" :value="field">{{ field }}</option>
          </select>
        </div>

        <div class="style-row">
          <label>配色方案</label>
          <div class="color-schemes">
            <button
              v-for="scheme in colorSchemes"
              :key="scheme.name"
              class="scheme-btn"
              :class="{ active: selectedScheme === scheme.name }"
              @click="selectScheme(scheme)"
              :title="scheme.name"
            >
              <div class="scheme-colors">
                <span v-for="(color, i) in scheme.colors.slice(0, 5)" :key="i" :style="{ background: color }"></span>
              </div>
            </button>
          </div>
        </div>

        <button class="apply-btn" @click="applyCategorized">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
          生成分类样式
        </button>
      </div>

      <!-- 渐变渲染 -->
      <div v-if="currentRenderMode === 'graduated'" class="style-section">
        <div class="section-title">渐变渲染</div>
        <div class="section-hint">根据数值字段生成渐变色彩</div>
        
        <div class="style-row">
          <label>数值字段</label>
          <select v-model="graduatedField" class="select-input">
            <option value="">选择字段...</option>
            <option v-for="field in numericFields" :key="field" :value="field">{{ field }}</option>
          </select>
        </div>

        <div class="style-row">
          <label>渐变方式</label>
          <select v-model="graduatedMode" class="select-input">
            <option value="equal">等间隔</option>
            <option value="quantile">分位数</option>
            <option value="jenks">自然断点</option>
          </select>
        </div>

        <div class="style-row">
          <label>分级数量</label>
          <div class="slider-group">
            <input type="range" min="3" max="10" step="1" v-model.number="classCount" class="slider" />
            <span class="slider-value">{{ classCount }} 级</span>
          </div>
        </div>

        <div class="style-row">
          <label>色带</label>
          <div class="color-ramps">
            <button
              v-for="ramp in colorRamps"
              :key="ramp.name"
              class="ramp-btn"
              :class="{ active: selectedRamp === ramp.name }"
              @click="selectedRamp = ramp.name"
              :title="ramp.name"
            >
              <div class="ramp-gradient" :style="{ background: ramp.gradient }"></div>
            </button>
          </div>
        </div>

        <button class="apply-btn" @click="applyGraduated">
          <i class="fa-solid fa-chart-column"></i>
          生成渐变样式
        </button>
      </div>

      <!-- 标注设置 -->
      <div class="style-section">
        <div class="section-title">
          <label class="toggle-label">
            <input type="checkbox" v-model="labelEnabled" @change="toggleLabels" />
            <span class="toggle-switch"></span>
            标注
          </label>
        </div>

        <div v-if="labelEnabled" class="label-settings">
          <div class="style-row">
            <label>标注字段</label>
            <select v-model="labelField" @change="applyLabels" class="select-input">
              <option value="">选择字段...</option>
              <option v-for="field in availableFields" :key="field" :value="field">{{ field }}</option>
            </select>
          </div>

          <div class="style-row">
            <label>字体大小</label>
            <div class="slider-group">
              <input type="range" min="8" max="24" step="1" v-model.number="labelFontSize" @input="applyLabels" class="slider" />
              <span class="slider-value">{{ labelFontSize }}px</span>
            </div>
          </div>

          <div class="style-row">
            <label>字体颜色</label>
            <div class="color-input-group">
              <input type="color" v-model="labelColor" @input="applyLabels" class="color-picker" />
              <input type="text" v-model="labelColor" @input="applyLabels" class="color-text" />
            </div>
          </div>

          <div class="style-row">
            <label>标注位置</label>
            <select v-model="labelPosition" @change="applyLabels" class="select-input">
              <option value="top">上方</option>
              <option value="center">居中</option>
              <option value="bottom">下方</option>
              <option value="left">左侧</option>
              <option value="right">右侧</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 样式预设 -->
      <div class="style-section">
        <div class="section-title">样式预设</div>
        <div class="preset-grid">
          <button
            v-for="preset in layerPresets"
            :key="preset.name"
            class="preset-btn"
            @click="applyPreset(preset)"
            :title="preset.name"
          >
            <div class="preset-preview" :style="preset.previewStyle"></div>
            <span class="preset-name">{{ preset.name }}</span>
          </button>
        </div>
      </div>

      <!-- 底部操作 -->
      <div v-if="styleMessage" class="style-message">
        <i class="fa-solid fa-circle-info"></i>
        {{ styleMessage }}
      </div>

      <div class="panel-footer">
        <button class="reset-btn" @click="resetStyle">
          <i class="fa-solid fa-rotate-left"></i>
          重置
        </button>
        <button class="save-btn" @click="saveStyle">
          <i class="fa-solid fa-check"></i>
          应用并关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import type { MapLayer, LayerType, LayerStyle } from '@/types'

const appStore = useAppStore()
const mapStore = useMapStore()

// 渲染模式
const currentRenderMode = ref<string>('single')

const renderModes = [
  { value: 'single', label: '单点', icon: 'fa-solid fa-circle' },
  { value: 'categorized', label: '分类', icon: 'fa-solid fa-shapes' },
  { value: 'graduated', label: '渐变', icon: 'fa-solid fa-chart-simple' },
]

// 样式表单
const styleForm = reactive({
  color: '#3388ff',
  fillColor: '#3388ff40',
  weight: 3,
  opacity: 1,
  fillOpacity: 0.3,
  dashArray: null as string | null,
  radius: 6,
})

// 标注设置
const labelEnabled = ref(false)
const labelField = ref('')
const labelFontSize = ref(12)
const labelColor = ref('#1a1a1a')
const labelPosition = ref('top')

// 分类渲染
const categoryField = ref('')
const selectedScheme = ref('')

// 渐变渲染
const graduatedField = ref('')
const graduatedMode = ref('equal')
const classCount = ref(5)
const selectedRamp = ref('')

// 当前选中图层
const selectedLayer = computed(() => {
  if (!appStore.selectedLayerId) return null
  return mapStore.layerGroups[appStore.selectedLayerId] || null
})

// 可用字段
const availableFields = computed(() => {
  if (!selectedLayer.value?.data.properties?.length) return []
  const props = selectedLayer.value.data.properties[0]
  return Object.keys(props || {})
})

// 数值字段
const numericFields = computed(() => {
  if (!selectedLayer.value?.data.properties?.length) return []
  const props = selectedLayer.value.data.properties[0] || {}
  return Object.keys(props).filter((key) => typeof props[key] === 'number')
})

// 图层类型判断
const isLineLayer = computed(() => {
  const t = selectedLayer.value?.data.type
  return t === 'polyline' || t === 'line'
})

const isPointLayer = computed(() => {
  const t = selectedLayer.value?.data.type
  return t === 'circleMarker' || t === 'point' || t === 'marker'
})

const isPolygonLayer = computed(() => {
  const t = selectedLayer.value?.data.type
  return t === 'polygon' || t === 'area'
})

const isLineOrPoint = computed(() => isLineLayer.value || isPointLayer.value)

// 配色方案
const colorSchemes = [
  { name: '默认', colors: ['#3388ff', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'] },
  { name: '柔和', colors: ['#93c5fd', '#86efac', '#fcd34d', '#fca5a5', '#c4b5fd'] },
  { name: '深色', colors: ['#1e40af', '#166534', '#92400e', '#991b1b', '#5b21b6'] },
  { name: 'Pastel', colors: ['#dbeafe', '#dcfce7', '#fef3c7', '#fee2e2', '#ede9fe'] },
  { name: 'Earth', colors: ['#78716c', '#a16207', '#166534', '#0369a1', '#7c2d12'] },
  { name: 'Ocean', colors: ['#0c4a6e', '#0369a1', '#0ea5e9', '#38bdf8', '#7dd3fc'] },
]

// 色带
const colorRamps = [
  { name: '蓝绿', gradient: 'linear-gradient(to right, #f0f9ff, #0ea5e9, #0c4a6e)' },
  { name: '绿黄红', gradient: 'linear-gradient(to right, #166534, #fcd34d, #991b1b)' },
  { name: '紫红', gradient: 'linear-gradient(to right, #fdf2f8, #ec4899, #831843)' },
  { name: '橙红', gradient: 'linear-gradient(to right, #fff7ed, #f97316, #7c2d12)' },
  { name: '蓝紫', gradient: 'linear-gradient(to right, #eff6ff, #8b5cf6, #4c1d95)' },
  { name: '灰度', gradient: 'linear-gradient(to right, #f8fafc, #64748b, #0f172a)' },
]

const rampColorStops: Record<string, string[]> = {
  蓝绿: ['#f0f9ff', '#7dd3fc', '#0ea5e9', '#0369a1', '#0c4a6e'],
  绿黄红: ['#166534', '#84cc16', '#fcd34d', '#f97316', '#991b1b'],
  紫红: ['#fdf2f8', '#f9a8d4', '#ec4899', '#be185d', '#831843'],
  橙红: ['#fff7ed', '#fdba74', '#f97316', '#c2410c', '#7c2d12'],
  蓝紫: ['#eff6ff', '#c4b5fd', '#8b5cf6', '#6d28d9', '#4c1d95'],
  灰度: ['#f8fafc', '#cbd5e1', '#94a3b8', '#475569', '#0f172a'],
}

const styleMessage = ref('')

// 样式预设
const layerPresets = computed(() => {
  const type = selectedLayer.value?.data.type
  if (isPolygonLayer.value) {
    return [
      { name: '水体', previewStyle: { background: '#60a5fa', borderColor: '#2563eb' } },
      { name: '绿地', previewStyle: { background: '#86efac', borderColor: '#22c55e' } },
      { name: '建筑', previewStyle: { background: '#fcd34d', borderColor: '#f59e0b' } },
      { name: '边界', previewStyle: { background: 'transparent', borderColor: '#64748b', borderStyle: 'dashed' } },
    ]
  }
  if (isLineLayer.value) {
    return [
      { name: '道路', previewStyle: { background: '#64748b', height: '3px' } },
      { name: '铁路', previewStyle: { background: '#475569', height: '4px', backgroundImage: 'repeating-linear-gradient(90deg, #475569 0, #475569 8px, transparent 8px, transparent 12px)' } },
      { name: '河流', previewStyle: { background: '#60a5fa', height: '4px' } },
      { name: '边界', previewStyle: { background: '#64748b', height: '2px', backgroundImage: 'repeating-linear-gradient(90deg, #64748b 0, #64748b 5px, transparent 5px, transparent 8px)' } },
    ]
  }
  return [
    { name: '默认点', previewStyle: { background: '#3388ff', borderRadius: '50%' } },
    { name: 'POI', previewStyle: { background: '#ef4444', borderRadius: '50%' } },
    { name: '学校', previewStyle: { background: '#f59e0b', borderRadius: '50%' } },
    { name: '医院', previewStyle: { background: '#22c55e', borderRadius: '50%' } },
  ]
})

// 监听选中图层变化，初始化样式
watch(selectedLayer, (layer) => {
  if (layer) {
    const style = layer.data.style || {}
    styleForm.color = style.color || '#3388ff'
    styleForm.fillColor = style.fillColor || style.color || '#3388ff40'
    styleForm.weight = style.weight || 3
    styleForm.opacity = style.opacity ?? 1
    styleForm.fillOpacity = style.fillOpacity ?? 0.3
    styleForm.dashArray = style.dashArray || null
    styleForm.radius = style.radius || 6
    labelEnabled.value = style.labelsEnabled || false
    labelFontSize.value = style.labelFontSize || 12
    labelColor.value = style.labelColor || '#1a1a1a'
    labelPosition.value = style.labelPosition || 'top'
  }
}, { immediate: true })

function getLayerColorStyle() {
  const style = selectedLayer.value?.data.style || {}
  return {
    background: style.fillColor || style.color || '#3388ff',
    borderColor: style.color || '#3388ff',
  }
}

function getLayerTypeLabel(type: LayerType): string {
  const labels: Record<string, string> = {
    polyline: '线图层',
    line: '线图层',
    polygon: '面图层',
    area: '面图层',
    circleMarker: '点图层',
    marker: '点图层',
    point: '点图层',
    textLabel: '标注图层',
    label: '标注图层',
    heatmap: '热力图',
  }
  return labels[type] || type
}

function applyStyle() {
  if (!appStore.selectedLayerId) return
  const layer = mapStore.layerGroups[appStore.selectedLayerId]
  if (layer?.data.style?.featureColors) {
    const { featureColors, ...rest } = layer.data.style
    layer.data.style = rest
  }
  mapStore.updateLayerStyle(appStore.selectedLayerId, { ...styleForm })
  refreshMap()
}

function applyPreset(preset: any) {
  if (!appStore.selectedLayerId) return
  
  // 根据预设名称应用对应的样式
  const presetStyles: Record<string, any> = {
    '水体': { fillColor: '#60a5fa', color: '#2563eb', fillOpacity: 0.6, weight: 2 },
    '绿地': { fillColor: '#86efac', color: '#22c55e', fillOpacity: 0.6, weight: 1 },
    '建筑': { fillColor: '#fcd34d', color: '#f59e0b', fillOpacity: 0.8, weight: 1 },
    '边界': { fillColor: 'transparent', color: '#64748b', fillOpacity: 0, weight: 2, dashArray: '5,5' },
    '道路': { color: '#64748b', weight: 3, opacity: 0.9 },
    '铁路': { color: '#475569', weight: 4, dashArray: '8,4' },
    '河流': { color: '#60a5fa', weight: 4, opacity: 0.8 },
    '默认点': { color: '#3388ff', radius: 6, weight: 2 },
    'POI': { color: '#ef4444', radius: 5, weight: 2 },
    '学校': { color: '#f59e0b', radius: 7, weight: 2 },
    '医院': { color: '#22c55e', radius: 6, weight: 2 },
  }
  
  const style = presetStyles[preset.name]
  if (style) {
    // 更新样式表单
    Object.assign(styleForm, style)
    const layer = mapStore.layerGroups[appStore.selectedLayerId!]
    if (layer?.data.style?.featureColors) {
      const { featureColors, ...rest } = layer.data.style
      layer.data.style = rest
    }
    // 应用到图层
    mapStore.updateLayerStyle(appStore.selectedLayerId!, style)
    refreshMap()
  }
}

function selectScheme(scheme: any) {
  selectedScheme.value = scheme.name
}

function applyCategorized() {
  if (!categoryField.value) {
    alert('请选择分类字段')
    return
  }
  const props = selectedLayer.value?.data.properties || []
  if (props.length === 0) {
    styleMessage.value = '该图层没有属性数据，无法分类渲染'
    return
  }
  const values = props.map((p: any) => String(p[categoryField.value] ?? ''))
  const uniq = [...new Set(values)]
  const scheme = colorSchemes.find((s) => s.name === selectedScheme.value) || colorSchemes[0]
  const colorMap: Record<string, string> = {}
  uniq.forEach((v, i) => {
    colorMap[v] = scheme.colors[i % scheme.colors.length]
  })
  const featureColors = values.map((v) => colorMap[v])
  mapStore.updateLayerStyle(appStore.selectedLayerId!, { featureColors })
  styleMessage.value = `已按「${categoryField.value}」生成 ${uniq.length} 个分类的颜色样式`
  refreshMap()
}

function applyGraduated() {
  if (!graduatedField.value) {
    alert('请选择数值字段')
    return
  }
  const props = selectedLayer.value?.data.properties || []
  if (props.length === 0) {
    styleMessage.value = '该图层没有属性数据，无法渐变渲染'
    return
  }
  const field = graduatedField.value
  const values = props.map((p: any) => Number(p[field])).filter((v: number) => !isNaN(v))
  if (values.length === 0) {
    styleMessage.value = `字段「${field}」没有数值`
    return
  }
  const count = classCount.value
  let breaks: number[]
  if (graduatedMode.value === 'quantile') {
    breaks = quantileBreaks(values, count)
  } else if (graduatedMode.value === 'jenks') {
    breaks = jenksBreaks(values, count)
  } else {
    const min = Math.min(...values)
    const max = Math.max(...values)
    const step = (max - min) / count
    breaks = Array.from({ length: count }, (_, i) => min + step * (i + 1))
  }
  const colors = rampColorsFor(count)
  const featureColors = props.map((p: any) => {
    const v = Number(p[field])
    if (isNaN(v)) return colors[0]
    for (let i = 0; i < breaks.length; i++) {
      if (v <= breaks[i]) return colors[i]
    }
    return colors[colors.length - 1]
  })
  mapStore.updateLayerStyle(appStore.selectedLayerId!, { featureColors })
  const modeName = graduatedMode.value === 'equal' ? '等间隔' : graduatedMode.value === 'quantile' ? '分位数' : '自然断点'
  styleMessage.value = `已按「${field}」生成 ${count} 级${modeName}渐变样式`
  refreshMap()
}

function lerpColor(c1: string, c2: string, t: number): string {
  const parse = (c: string) => {
    const m = c.replace('#', '')
    return [parseInt(m.substring(0, 2), 16), parseInt(m.substring(2, 4), 16), parseInt(m.substring(4, 6), 16)]
  }
  const a = parse(c1)
  const b = parse(c2)
  const mix = a.map((v: number, i: number) => Math.round(v + (b[i] - v) * t))
  return '#' + mix.map((v: number) => v.toString(16).padStart(2, '0')).join('')
}

function rampColorsFor(count: number): string[] {
  const name = selectedRamp.value || '蓝绿'
  const stops = rampColorStops[name] || rampColorStops['蓝绿']
  const colors: string[] = []
  for (let i = 0; i < count; i++) {
    const pos = count === 1 ? 0 : i / (count - 1)
    const seg = pos * (stops.length - 1)
    const idx = Math.min(stops.length - 2, Math.floor(seg))
    colors.push(lerpColor(stops[idx], stops[idx + 1], seg - idx))
  }
  return colors
}

function quantileBreaks(values: number[], count: number): number[] {
  const sorted = [...values].sort((a, b) => a - b)
  return Array.from({ length: count }, (_, i) =>
    sorted[Math.min(sorted.length - 1, Math.max(0, Math.round(((i + 1) * sorted.length) / count) - 1))]
  )
}

function jenksBreaks(values: number[], count: number): number[] {
  const sorted = [...values].sort((a, b) => a - b)
  if (count <= 1) return [sorted[sorted.length - 1]]
  const n = sorted.length
  let centers = Array.from({ length: count }, (_, i) => sorted[Math.floor(((i + 0.5) * n) / count)])
  for (let iter = 0; iter < 60; iter++) {
    const clusters: number[][] = Array.from({ length: count }, () => [])
    sorted.forEach((v) => {
      let bi = 0
      let bd = Infinity
      centers.forEach((c, ci) => {
        const d = Math.abs(v - c)
        if (d < bd) {
          bd = d
          bi = ci
        }
      })
      clusters[bi].push(v)
    })
    const next = clusters.map((c) => (c.length ? c.reduce((a, b) => a + b, 0) / c.length : 0))
    if (next.every((c, i) => Math.abs(c - centers[i]) < 1e-9)) {
      centers = next
      break
    }
    centers = next
  }
  return centers.map((c) => sorted.reduce((acc, v) => (Math.abs(v - c) < Math.abs(acc - c) ? v : acc), sorted[0]))
}

function toggleLabels() {
  if (!appStore.selectedLayerId) return
  mapStore.updateLayerStyle(appStore.selectedLayerId, {
    labelsEnabled: labelEnabled.value,
    labelFontSize: labelFontSize.value,
    labelColor: labelColor.value,
    labelPosition: labelPosition.value,
  })
  refreshMap()
}

function applyLabels() {
  if (!appStore.selectedLayerId || !labelEnabled.value) return
  mapStore.updateLayerStyle(appStore.selectedLayerId, {
    labelsEnabled: true,
    labelFontSize: labelFontSize.value,
    labelColor: labelColor.value,
    labelPosition: labelPosition.value,
  })
  refreshMap()
}

function resetStyle() {
  if (selectedLayer.value) {
    const original = mapStore.currentMapData?.layers?.find(
      (l) => l.id === appStore.selectedLayerId
    )
    if (original?.style) {
      const style = original.style
      styleForm.color = style.color || '#3388ff'
      styleForm.fillColor = style.fillColor || style.color || '#3388ff40'
      styleForm.weight = style.weight || 3
      styleForm.fillOpacity = style.fillOpacity ?? 0.3
      applyStyle()
    }
  }
}

function saveStyle() {
  applyStyle()
  closePanel()
}

function closePanel() {
  appStore.toggleStylePanel()
}

function refreshMap() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-refresh-layers'))
  }
}
</script>

<style scoped>
.style-panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.style-panel {
  width: 420px;
  max-height: 85vh;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #7c3aed08 0%, #6d28d908 100%);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.panel-title i {
  color: var(--color-primary);
}

.close-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--color-text);
}

.layer-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
  background: #fafbfc;
}

.layer-color-dot {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 2px solid;
}

.layer-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.layer-type-badge {
  font-size: 11px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 10px;
}

.style-section {
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-border);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-hint {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  margin-top: -6px;
}

.style-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.style-row:last-child {
  margin-bottom: 0;
}

.style-row label {
  width: 70px;
  font-size: 12px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.color-input-group {
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;
}

.color-picker {
  width: 32px;
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  cursor: pointer;
  padding: 2px;
  background: none;
}

.color-text {
  flex: 1;
  padding: 5px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  font-family: monospace;
  outline: none;
}

.color-text:focus {
  border-color: var(--color-primary-light);
}

.slider-group {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border);
  border-radius: 2px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.slider-value {
  width: 45px;
  font-size: 11px;
  color: var(--color-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.select-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
  cursor: pointer;
}

.select-input:focus {
  border-color: var(--color-primary-light);
}

/* 渲染模式按钮 */
.render-modes {
  display: flex;
  gap: 6px;
}

.mode-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.mode-btn:hover {
  border-color: var(--color-primary-light);
  background: rgba(124, 58, 237, 0.04);
}

.mode-btn.active {
  border-color: var(--color-primary);
  background: rgba(124, 58, 237, 0.08);
  color: var(--color-primary);
}

.mode-btn i {
  font-size: 16px;
}

/* 配色方案 */
.color-schemes {
  flex: 1;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.scheme-btn {
  padding: 2px;
  border: 2px solid var(--color-border);
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.scheme-btn:hover {
  border-color: var(--color-primary-light);
}

.scheme-btn.active {
  border-color: var(--color-primary);
}

.scheme-colors {
  display: flex;
  height: 20px;
  border-radius: 3px;
  overflow: hidden;
}

.scheme-colors span {
  width: 16px;
  height: 100%;
}

/* 色带 */
.color-ramps {
  flex: 1;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ramp-btn {
  padding: 2px;
  border: 2px solid var(--color-border);
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.ramp-btn:hover {
  border-color: var(--color-primary-light);
}

.ramp-btn.active {
  border-color: var(--color-primary);
}

.ramp-gradient {
  width: 60px;
  height: 20px;
  border-radius: 3px;
}

/* 样式预设 */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 6px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.preset-btn:hover {
  border-color: var(--color-primary-light);
  background: rgba(124, 58, 237, 0.04);
}

.preset-preview {
  width: 32px;
  height: 32px;
  border: 2px solid;
  border-radius: 4px;
}

.preset-name {
  font-size: 10px;
  color: var(--color-text-secondary);
}

/* 标注开关 */
.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  text-transform: none;
  letter-spacing: normal;
}

.toggle-label input {
  display: none;
}

.toggle-switch {
  width: 36px;
  height: 20px;
  background: var(--color-border);
  border-radius: 10px;
  position: relative;
  transition: background 0.2s;
}

.toggle-switch::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.toggle-label input:checked + .toggle-switch {
  background: var(--color-primary);
}

.toggle-label input:checked + .toggle-switch::after {
  transform: translateX(16px);
}

.label-settings {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

/* 应用按钮 */
.apply-btn {
  width: 100%;
  padding: 10px;
  margin-top: 12px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.apply-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

/* 底部操作 */
.style-message {
  margin: 10px 20px 0;
  padding: 8px 12px;
  background: rgba(6, 182, 212, 0.08);
  color: #0e7490;
  border: 1px solid rgba(6, 182, 212, 0.25);
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-footer {
  display: flex;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--color-border);
  background: #fafbfc;
}

.reset-btn {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
}

.reset-btn:hover {
  border-color: var(--color-text-secondary);
  color: var(--color-text);
}

.save-btn {
  flex: 2;
  padding: 10px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
}

.save-btn:hover {
  opacity: 0.9;
}
</style>
