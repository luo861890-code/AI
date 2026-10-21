<template>
  <div class="map-edit-panel">
    <div class="edit-panel-header">
      <span><i class="fa-solid fa-pen-to-square"></i> 编辑模式</span>
      <button class="edit-panel-close" title="退出编辑" @click="handleExit">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>

    <div class="edit-tools">
      <button
        class="edit-tool-btn"
        :class="{ active: editStore.drawTool === 'point' }"
        title="添加点要素"
        @click="setDraw('point')"
      >
        <i class="fa-solid fa-location-dot"></i> 画点
      </button>
      <button
        class="edit-tool-btn"
        :class="{ active: editStore.drawTool === 'line' }"
        title="添加线要素"
        @click="setDraw('line')"
      >
        <i class="fa-solid fa-minus"></i> 画线
      </button>
      <button
        class="edit-tool-btn"
        :class="{ active: editStore.drawTool === 'polygon' }"
        title="添加面要素"
        @click="setDraw('polygon')"
      >
        <i class="fa-solid fa-draw-polygon"></i> 画面
      </button>
      <button
        v-if="editStore.drawTool === 'line' || editStore.drawTool === 'polygon'"
        class="edit-tool-btn edit-success"
        title="完成绘制"
        @click="dispatch('map-edit-finish-draw')"
      >
        <i class="fa-solid fa-check"></i> 完成({{ editStore.pendingVertices.length }}点)
      </button>
      <button
        v-if="editStore.drawTool === 'line' || editStore.drawTool === 'polygon'"
        class="edit-tool-btn"
        title="取消绘制"
        @click="dispatch('map-edit-cancel-draw')"
      >
        <i class="fa-solid fa-xmark"></i> 取消
      </button>
    </div>

    <div class="edit-tools">
      <button class="edit-tool-btn edit-danger" title="删除当前选中的要素" @click="dispatch('map-edit-delete')">
        <i class="fa-solid fa-trash-can"></i> 删除
      </button>
      <button class="edit-tool-btn" title="撤销 (Ctrl+Z)" @click="dispatch('map-edit-undo')">
        <i class="fa-solid fa-rotate-left"></i> 撤销
      </button>
      <button class="edit-tool-btn" title="重做 (Ctrl+Y)" @click="dispatch('map-edit-redo')">
        <i class="fa-solid fa-rotate-right"></i> 重做
      </button>
      <button class="edit-tool-btn" title="复制选中的要素" @click="dispatch('map-edit-copy')">
        <i class="fa-solid fa-copy"></i> 复制
      </button>
      <button class="edit-tool-btn" title="简化选中要素 (Douglas-Peucker)" @click="dispatch('map-edit-simplify')">
        <i class="fa-solid fa-compress"></i> 简化
      </button>
    </div>

    <div class="edit-attr">
      <label for="edit-attr-name">要素名称</label>
      <input
        id="edit-attr-name"
        type="text"
        :value="attrName"
        placeholder="选中要素后编辑名称"
        :disabled="!editStore.selectedLayerId"
        @change="onAttrChange"
      />
    </div>

    <div class="edit-coord">
      <label for="edit-coord-input">坐标(lat,lng)</label>
      <input
        id="edit-coord-input"
        type="text"
        v-model="coordText"
        placeholder="如 30.5928,114.3055"
        @keydown.enter="addCoord"
      />
      <button class="edit-coord-btn" title="按坐标添加点要素" @click="addCoord">添加</button>
    </div>

    <div class="edit-hint">
      点击要素编辑；拖动节点改形；双击结束画线/画面。
    </div>
    <div class="edit-status" :class="{ dirty: editStore.dirtyIds.length > 0 }">
      {{ editStore.statusText }}
      <span v-if="editStore.dirtyIds.length > 0"> · {{ editStore.dirtyIds.length }} 个图层未保存</span>
    </div>

    <div class="edit-actions">
      <button class="edit-save-btn" @click="dispatch('map-edit-save')">
        <i class="fa-solid fa-floppy-disk"></i> 保存修改
      </button>
      <button class="edit-exit-btn" @click="handleExit">退出</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useEditStore } from '@/stores/editStore'
import { useMapStore } from '@/stores/mapStore'

const appStore = useAppStore()
const editStore = useEditStore()
const mapStore = useMapStore()

const coordText = ref('')

const attrName = computed(() => {
  const layerId = editStore.selectedLayerId
  const idx = editStore.selectedIndex
  if (!layerId || idx === null) return ''
  const layer = mapStore.layerGroups[layerId]?.data
  const props = layer?.properties?.[idx]
  return props?.name || layer?.name || ''
})

function dispatch(name: string, detail?: any) {
  const el = document.getElementById('map-container')
  if (!el) return
  el.dispatchEvent(new CustomEvent(name, detail !== undefined ? { detail } : undefined))
}

function setDraw(tool: 'point' | 'line' | 'polygon') {
  editStore.setDrawTool(editStore.drawTool === tool ? null : tool)
  dispatch('map-edit-draw', { tool: editStore.drawTool })
}

function onAttrChange(e: Event) {
  const name = (e.target as HTMLInputElement).value.trim()
  dispatch('map-edit-attr', { name })
}

function addCoord() {
  const text = coordText.value.trim()
  const m = text.match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/)
  if (!m) return
  const lat = parseFloat(m[1])
  const lng = parseFloat(m[2])
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return
  dispatch('map-edit-coord', { lat, lng })
  coordText.value = ''
}

function handleExit() {
  dispatch('map-edit-exit')
  appStore.toggleEditPanel()
}
</script>

<style scoped>
.map-edit-panel {
  position: absolute;
  top: 90px;
  left: 12px;
  width: 320px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 30;
  padding: 10px;
  font-size: 12px;
}

.edit-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0 8px;
  border-bottom: 1px solid var(--color-border);
  font-weight: 600;
  color: var(--color-primary);
}

.edit-panel-close {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
}

.edit-panel-close:hover {
  background: rgba(0, 0, 0, 0.05);
}

.edit-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 0 4px;
}

.edit-tool-btn {
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text);
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}

.edit-tool-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: rgba(124, 58, 237, 0.04);
}

.edit-tool-btn.active {
  background: rgba(124, 58, 237, 0.12);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.edit-tool-btn.edit-danger {
  color: var(--color-error);
}

.edit-tool-btn.edit-danger:hover {
  background: rgba(239, 68, 68, 0.08);
  border-color: var(--color-error);
}

.edit-tool-btn.edit-success {
  color: var(--color-success);
  border-color: rgba(16, 185, 129, 0.4);
}

.edit-attr,
.edit-coord {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.edit-attr label,
.edit-coord label {
  width: 74px;
  color: var(--color-text-secondary);
  font-size: 11px;
  flex-shrink: 0;
}

.edit-attr input,
.edit-coord input {
  flex: 1;
  padding: 5px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  min-width: 0;
}

.edit-attr input:focus,
.edit-coord input:focus {
  border-color: var(--color-primary-light);
}

.edit-coord-btn {
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-primary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
}

.edit-coord-btn:hover {
  border-color: var(--color-primary);
}

.edit-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  padding: 4px 0;
}

.edit-status {
  padding: 6px 8px;
  border-radius: 6px;
  background: #f8fafc;
  color: var(--color-text-secondary);
  font-size: 11px;
  margin: 4px 0;
}

.edit-status.dirty {
  color: var(--color-warning);
}

.edit-actions {
  display: flex;
  gap: 8px;
  padding-top: 6px;
}

.edit-save-btn,
.edit-exit-btn {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.edit-save-btn {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.edit-exit-btn {
  background: #f1f5f9;
  color: var(--color-text);
}
</style>
