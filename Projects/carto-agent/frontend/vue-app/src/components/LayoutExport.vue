<template>
  <Teleport to="body">
    <div v-if="visible" class="layout-export-overlay" @click.self="close">
      <div class="layout-export-panel">
      <!-- 头部 -->
      <div class="panel-header">
        <div class="header-title">
          <i class="fa-solid fa-file-export"></i>
          <span>地图布局导出</span>
        </div>
        <button class="close-btn" @click="close">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <div class="panel-body">
        <!-- 左侧：布局设置 -->
        <div class="settings-panel">
          <!-- 页面设置 -->
          <div class="section">
            <div class="section-title">页面设置</div>
            <div class="setting-row">
              <label>纸张大小</label>
              <select v-model="layout.pageSize" class="select-input">
                <option value="A4">A4 (210×297mm)</option>
                <option value="A3">A3 (297×420mm)</option>
                <option value="A2">A2 (420×594mm)</option>
                <option value="custom">自定义</option>
              </select>
            </div>
            <div class="setting-row">
              <label>方向</label>
              <div class="orientation-group">
                <button
                  :class="{ active: layout.orientation === 'portrait' }"
                  @click="layout.orientation = 'portrait'"
                >
                  <i class="fa-solid fa-mobile-screen"></i>
                  纵向
                </button>
                <button
                  :class="{ active: layout.orientation === 'landscape' }"
                  @click="layout.orientation = 'landscape'"
                >
                  <i class="fa-solid fa-tv"></i>
                  横向
                </button>
              </div>
            </div>
            <div class="setting-row">
              <label>分辨率</label>
              <select v-model="layout.dpi" class="select-input">
                <option :value="96">96 DPI (屏幕)</option>
                <option :value="150">150 DPI (标准)</option>
                <option :value="300">300 DPI (打印)</option>
              </select>
            </div>
          </div>

          <!-- 地图元素 -->
          <div class="section">
            <div class="section-title">地图元素</div>
            <div class="element-list">
              <label class="element-item">
                <input type="checkbox" v-model="layout.showTitle" />
                <span class="element-name">标题</span>
              </label>
              <label class="element-item">
                <input type="checkbox" v-model="layout.showLegend" />
                <span class="element-name">图例</span>
              </label>
              <label class="element-item">
                <input type="checkbox" v-model="layout.showScaleBar" />
                <span class="element-name">比例尺</span>
              </label>
              <label class="element-item">
                <input type="checkbox" v-model="layout.showNorthArrow" />
                <span class="element-name">指北针</span>
              </label>
              <label class="element-item">
                <input type="checkbox" v-model="layout.showGrid" />
                <span class="element-name">经纬网</span>
              </label>
            </div>
          </div>

          <!-- 标题设置 -->
          <div v-if="layout.showTitle" class="section">
            <div class="section-title">标题设置</div>
            <div class="setting-row">
              <label>标题文字</label>
              <input v-model="layout.title" type="text" class="text-input" />
            </div>
            <div class="setting-row">
              <label>字体大小</label>
              <input v-model.number="layout.titleSize" type="range" min="12" max="48" class="slider" />
              <span class="value">{{ layout.titleSize }}px</span>
            </div>
          </div>

          <!-- 图例设置 -->
          <div v-if="layout.showLegend" class="section">
            <div class="section-title">图例设置</div>
            <div class="setting-row">
              <label>位置</label>
              <select v-model="layout.legendPosition" class="select-input">
                <option value="topright">右上角</option>
                <option value="bottomright">右下角</option>
                <option value="topleft">左上角</option>
                <option value="bottomleft">左下角</option>
              </select>
            </div>
            <div class="setting-row">
              <label>标题</label>
              <input v-model="layout.legendTitle" type="text" class="text-input" placeholder="图例" />
            </div>
          </div>

          <!-- 比例尺设置 -->
          <div v-if="layout.showScaleBar" class="section">
            <div class="section-title">比例尺设置</div>
            <div class="setting-row">
              <label>位置</label>
              <select v-model="layout.scaleBarPosition" class="select-input">
                <option value="bottomleft">左下角</option>
                <option value="bottomright">右下角</option>
              </select>
            </div>
            <div class="setting-row">
              <label>单位</label>
              <select v-model="layout.scaleUnit" class="select-input">
                <option value="metric">公制 (km/m)</option>
                <option value="imperial">英制 (mi/ft)</option>
              </select>
            </div>
          </div>
        </div>

        <!-- 右侧：预览 -->
        <div class="preview-panel">
          <div class="preview-title">预览</div>
          <div class="preview-container">
            <div
              class="preview-page"
              :class="layout.orientation"
              :style="previewStyle"
            >
              <!-- 标题 -->
              <div v-if="layout.showTitle" class="preview-title-bar">
                {{ layout.title || '地图标题' }}
              </div>

              <!-- 地图区域 -->
              <div class="preview-map-area">
                <div class="map-placeholder">
                  <i class="fa-solid fa-map"></i>
                  <span>地图区域</span>
                </div>

                <!-- 指北针 -->
                <div v-if="layout.showNorthArrow" class="preview-north-arrow">
                  <i class="fa-solid fa-location-arrow"></i>
                  <span>N</span>
                </div>

                <!-- 图例 -->
                <div v-if="layout.showLegend" class="preview-legend" :class="layout.legendPosition">
                  <div class="legend-title">{{ layout.legendTitle || '图例' }}</div>
                  <div class="legend-item">
                    <span class="legend-color" style="background: #3388ff"></span>
                    <span>要素1</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-color" style="background: #22c55e"></span>
                    <span>要素2</span>
                  </div>
                </div>

                <!-- 比例尺 -->
                <div v-if="layout.showScaleBar" class="preview-scale-bar" :class="layout.scaleBarPosition">
                  <div class="scale-bar-line"></div>
                  <div class="scale-bar-labels">
                    <span>0</span>
                    <span>1 km</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="panel-footer">
        <div class="footer-left">
          <span class="export-info">
            输出尺寸: {{ exportWidth }} × {{ exportHeight }} px
          </span>
        </div>
        <div class="footer-right">
          <button class="btn secondary" @click="close">取消</button>
          <button class="btn primary" @click="exportMap">
            <i class="fa-solid fa-download"></i>
            导出地图
          </button>
        </div>
      </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'

const props = defineProps<{
  visible: boolean
  mapTitle?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'export', options: any): void
}>()

const layout = reactive({
  pageSize: 'A4',
  orientation: 'landscape',
  dpi: 150,
  showTitle: true,
  showLegend: true,
  showScaleBar: true,
  showNorthArrow: true,
  showGrid: false,
  title: '',
  titleSize: 24,
  legendPosition: 'topright',
  legendTitle: '图例',
  scaleBarPosition: 'bottomleft',
  scaleUnit: 'metric',
})

const pageSizes: Record<string, { width: number; height: number }> = {
  A4: { width: 210, height: 297 },
  A3: { width: 297, height: 420 },
  A2: { width: 420, height: 594 },
}

const exportWidth = computed(() => {
  const size = pageSizes[layout.pageSize] || { width: 210, height: 297 }
  const px = (layout.orientation === 'landscape' ? size.height : size.width) * (layout.dpi / 25.4)
  return Math.round(px)
})

const exportHeight = computed(() => {
  const size = pageSizes[layout.pageSize] || { width: 210, height: 297 }
  const px = (layout.orientation === 'landscape' ? size.width : size.height) * (layout.dpi / 25.4)
  return Math.round(px)
})

const previewStyle = computed(() => {
  const ratio = exportWidth.value / exportHeight.value
  const maxWidth = 400
  const maxHeight = 500
  let width, height
  if (ratio > maxWidth / maxHeight) {
    width = maxWidth
    height = maxWidth / ratio
  } else {
    height = maxHeight
    width = maxHeight * ratio
  }
  return {
    width: width + 'px',
    height: height + 'px',
  }
})

function close() {
  emit('close')
}

function exportMap() {
  emit('export', { ...layout })
  alert('导出功能开发中...')
}
</script>

<style scoped>
.layout-export-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.layout-export-panel {
  width: 800px;
  max-width: 90vw;
  max-height: 90vh;
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

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.header-title i {
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

.panel-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.settings-panel {
  width: 280px;
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
  padding: 16px;
}

.section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 12px;
}

.setting-row label {
  width: 70px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.select-input,
.text-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
}

.select-input:focus,
.text-input:focus {
  border-color: var(--color-primary-light);
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
  width: 14px;
  height: 14px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
}

.value {
  width: 45px;
  text-align: right;
  font-size: 11px;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.orientation-group {
  flex: 1;
  display: flex;
  gap: 6px;
}

.orientation-group button {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 4px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 6px;
  font-size: 10px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.orientation-group button:hover {
  border-color: var(--color-primary-light);
}

.orientation-group button.active {
  border-color: var(--color-primary);
  background: rgba(124, 58, 237, 0.08);
  color: var(--color-primary);
}

.element-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.element-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text);
  padding: 4px 0;
}

.element-item input {
  accent-color: var(--color-primary);
}

.element-name {
  flex: 1;
}

.preview-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.preview-title {
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
  background: #fff;
}

.preview-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow: auto;
}

.preview-page {
  background: #fff;
  border: 1px solid var(--color-border);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-title-bar {
  padding: 12px;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
}

.preview-map-area {
  flex: 1;
  position: relative;
  background: #e8f4f8;
  margin: 12px;
  border: 1px solid var(--color-border);
}

.map-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-text-secondary);
  opacity: 0.5;
}

.map-placeholder i {
  font-size: 32px;
}

.map-placeholder span {
  font-size: 12px;
}

.preview-north-arrow {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text);
}

.preview-north-arrow i {
  font-size: 16px;
  color: var(--color-error);
}

.preview-legend {
  position: absolute;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 8px;
  font-size: 10px;
}

.preview-legend.topright {
  top: 10px;
  right: 40px;
}

.preview-legend.bottomright {
  bottom: 10px;
  right: 10px;
}

.preview-legend.topleft {
  top: 10px;
  left: 10px;
}

.preview-legend.bottomleft {
  bottom: 10px;
  left: 10px;
}

.legend-title {
  font-weight: 600;
  margin-bottom: 6px;
  text-align: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.preview-scale-bar {
  position: absolute;
  font-size: 9px;
  color: var(--color-text);
}

.preview-scale-bar.bottomleft {
  bottom: 10px;
  left: 10px;
}

.preview-scale-bar.bottomright {
  bottom: 10px;
  right: 10px;
}

.scale-bar-line {
  height: 4px;
  width: 60px;
  background: linear-gradient(to right, #333 0%, #333 50%, #fff 50%, #fff 100%);
  border: 1px solid #333;
}

.scale-bar-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
  width: 60px;
}

.panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-top: 1px solid var(--color-border);
  background: #fafbfc;
}

.export-info {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.footer-right {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s;
}

.btn.primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.btn.primary:hover {
  opacity: 0.9;
}

.btn.secondary {
  background: #fff;
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn.secondary:hover {
  border-color: var(--color-text-secondary);
}
</style>
