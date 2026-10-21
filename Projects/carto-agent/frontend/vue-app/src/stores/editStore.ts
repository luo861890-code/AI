import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MapLayer } from '@/types'

/**
 * 矢量编辑状态（QGIS/ArcGIS 式）
 * 负责绘制的待定点、选中要素、脏图层、撤销/重做快照
 */
export const useEditStore = defineStore('edit', () => {
  /** 是否处于编辑模式 */
  const active = ref(false)

  /** 当前绘制工具：point / line / polygon / null */
  const drawTool = ref<'point' | 'line' | 'polygon' | null>(null)

  /** 线/面绘制过程中的待定点 [lat, lng] */
  const pendingVertices = ref<[number, number][]>([])

  /** 选中图层 */
  const selectedLayerId = ref<string | null>(null)

  /** 选中要素在 coordinates 中的下标 */
  const selectedIndex = ref<number | null>(null)

  /** 有未保存修改的图层 */
  const dirtyIds = ref<string[]>([])

  /** 撤销/重做快照栈（按图层） */
  const undoStack = ref<Record<string, MapLayer[]>>({})
  const redoStack = ref<Record<string, MapLayer[]>>({})

  /** 编辑状态提示 */
  const statusText = ref('未选择要素')

  function setActive(value: boolean) {
    active.value = value
    if (!value) {
      drawTool.value = null
      pendingVertices.value = []
      selectedLayerId.value = null
      selectedIndex.value = null
      statusText.value = '未选择要素'
    }
  }

  function setDrawTool(tool: 'point' | 'line' | 'polygon' | null) {
    drawTool.value = tool
    pendingVertices.value = []
  }

  function addPendingVertex(latlng: [number, number]) {
    pendingVertices.value = [...pendingVertices.value, latlng]
  }

  function clearPending() {
    pendingVertices.value = []
  }

  function setSelected(layerId: string | null, index: number | null) {
    selectedLayerId.value = layerId
    selectedIndex.value = index
    statusText.value = layerId && index !== null ? `已选择要素 #${index + 1}` : '未选择要素'
  }

  function markDirty(layerId: string) {
    if (layerId && !dirtyIds.value.includes(layerId)) {
      dirtyIds.value = [...dirtyIds.value, layerId]
    }
  }

  function clearDirty() {
    dirtyIds.value = []
  }

  function pushUndo(layerId: string, snapshot: MapLayer) {
    const stack = undoStack.value[layerId] || []
    stack.push(JSON.parse(JSON.stringify(snapshot)))
    if (stack.length > 50) stack.shift()
    undoStack.value = { ...undoStack.value, [layerId]: stack }
    redoStack.value = { ...redoStack.value, [layerId]: [] }
  }

  function popUndo(layerId: string): MapLayer | null {
    const stack = undoStack.value[layerId]
    if (!stack || stack.length === 0) return null
    const snapshot = stack.pop()
    undoStack.value = { ...undoStack.value, [layerId]: stack }
    return snapshot || null
  }

  function pushRedo(layerId: string, snapshot: MapLayer) {
    const stack = redoStack.value[layerId] || []
    stack.push(JSON.parse(JSON.stringify(snapshot)))
    redoStack.value = { ...redoStack.value, [layerId]: stack }
  }

  function popRedo(layerId: string): MapLayer | null {
    const stack = redoStack.value[layerId]
    if (!stack || stack.length === 0) return null
    const snapshot = stack.pop()
    redoStack.value = { ...redoStack.value, [layerId]: stack }
    return snapshot || null
  }

  function setStatus(text: string) {
    statusText.value = text
  }

  return {
    active,
    drawTool,
    pendingVertices,
    selectedLayerId,
    selectedIndex,
    dirtyIds,
    undoStack,
    redoStack,
    statusText,
    setActive,
    setDrawTool,
    addPendingVertex,
    clearPending,
    setSelected,
    markDirty,
    clearDirty,
    pushUndo,
    popUndo,
    pushRedo,
    popRedo,
    setStatus,
  }
})
