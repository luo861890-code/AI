import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MapData, MapLayer, RouteData, LayerStyle } from '@/types'
import api from '@/services/api'

// 样式增量保存防抖
const stylePersistTimers: Record<string, ReturnType<typeof setTimeout>> = {}
const visibilityPersistTimers: Record<string, ReturnType<typeof setTimeout>> = {}

/**
 * 解包后端返回的坐标包装格式 [{"value": [...], "Count": n}, ...]
 * 兼容纯数组格式，统一为纯坐标数组。
 */
export function unwrapCoordinates(coordinates: any): any {
  if (Array.isArray(coordinates) && coordinates.length > 0) {
    const first = coordinates[0]
    if (
      first &&
      typeof first === 'object' &&
      !Array.isArray(first) &&
      Array.isArray(first.value)
    ) {
      return coordinates.map((e: any) => (e && Array.isArray(e.value) ? e.value : e))
    }
  }
  return coordinates
}

/** 深层解包地图数据中的坐标（含 features） */
export function normalizeMapData(data: MapData): MapData {
  const copy: any = JSON.parse(JSON.stringify(data || {}))
  ;(copy.layers || []).forEach((l: any) => {
    if (l.coordinates) l.coordinates = unwrapCoordinates(l.coordinates)
    if (Array.isArray(l.features)) {
      l.features.forEach((f: any) => {
        if (f.coordinates) f.coordinates = unwrapCoordinates(f.coordinates)
      })
    }
  })
  return copy
}

export const useMapStore = defineStore('map', () => {
  const currentMapData = ref<MapData | null>(null)
  const currentMapId = ref<string | null>(null)
  const currentTheme = ref('amap_normal')
  const layerGroups = ref<Record<string, { visible: boolean; data: MapLayer; group?: string; order: number }>>({})
  const layerGroups_meta = ref<Record<string, { name: string; expanded: boolean; order: number }>>({})
  const routeData = ref<RouteData | null>(null)
  const mapName = ref('')
  const mapType = ref('')
  const region = ref('')
  const metadata = ref<Record<string, string> | null>(null)
  const quality = ref<any | null>(null)

  /** 按排序后的图层列表 */
  const sortedLayers = computed(() => {
    return Object.entries(layerGroups.value)
      .map(([id, item]) => ({ id, ...item }))
      .sort((a, b) => a.order - b.order)
  })

  /** 分组图层树 */
  const layerTree = computed(() => {
    const groups: Record<string, any[]> = {}
    const ungrouped: any[] = []
    
    sortedLayers.value.forEach((item) => {
      if (item.group && layerGroups_meta.value[item.group]) {
        if (!groups[item.group]) groups[item.group] = []
        groups[item.group].push(item)
      } else {
        ungrouped.push(item)
      }
    })

    const result: any[] = []
    
    // 先添加分组
    Object.entries(layerGroups_meta.value)
      .sort((a, b) => a[1].order - b[1].order)
      .forEach(([groupId, group]) => {
        result.push({
          type: 'group',
          id: groupId,
          name: group.name,
          expanded: group.expanded,
          children: groups[groupId] || [],
        })
      })
    
    // 再添加未分组的
    ungrouped.forEach((item) => {
      result.push({ type: 'layer', ...item })
    })

    return result
  })

  function setMapData(data: MapData) {
    const normalized = normalizeMapData(data)
    currentMapData.value = normalized
    currentMapId.value = normalized.map_id || null
    mapName.value = normalized.name || ''
    mapType.value = normalized.map_type || ''
    region.value = (normalized.metadata && (normalized.metadata['区域'] || normalized.metadata['region'])) || ''
    metadata.value = normalized.metadata || null
    quality.value = normalized.quality || null
    if (normalized.theme) {
      currentTheme.value = normalized.theme
    }
    layerGroups.value = {}
    layerGroups_meta.value = {}
    if (normalized.layers) {
      normalized.layers.forEach((layer, index) => {
        layerGroups.value[layer.id] = { 
          visible: true, 
          data: layer,
          order: index
        }
      })
    }
  }

  function clearAllLayers() {
    layerGroups.value = {}
    layerGroups_meta.value = {}
    currentMapData.value = null
    currentMapId.value = null
    routeData.value = null
    mapName.value = ''
    mapType.value = ''
    region.value = ''
    metadata.value = null
    quality.value = null
  }

  function setTheme(theme: string) {
    currentTheme.value = theme
  }

  function setRouteData(data: RouteData) {
    routeData.value = data
  }

  function clearRoute() {
    routeData.value = null
  }

  function toggleLayer(layerId: string, visible: boolean) {
    if (layerGroups.value[layerId]) {
      layerGroups.value[layerId].visible = visible
    }
    if (currentMapId.value) {
      const mapId = currentMapId.value
      const timer = visibilityPersistTimers[layerId]
      if (timer) clearTimeout(timer)
      visibilityPersistTimers[layerId] = setTimeout(() => {
        api.setLayerVisible(mapId, layerId, visible).catch(() => {})
      }, 200)
    }
  }

  /** 上移图层 */
  function moveLayerUp(layerId: string) {
    const layers = sortedLayers.value
    const idx = layers.findIndex(l => l.id === layerId)
    if (idx > 0) {
      const currentOrder = layerGroups.value[layerId].order
      const prevId = layers[idx - 1].id
      const prevOrder = layerGroups.value[prevId].order
      layerGroups.value[layerId].order = prevOrder
      layerGroups.value[prevId].order = currentOrder
    }
  }

  /** 下移图层 */
  function moveLayerDown(layerId: string) {
    const layers = sortedLayers.value
    const idx = layers.findIndex(l => l.id === layerId)
    if (idx >= 0 && idx < layers.length - 1) {
      const currentOrder = layerGroups.value[layerId].order
      const nextId = layers[idx + 1].id
      const nextOrder = layerGroups.value[nextId].order
      layerGroups.value[layerId].order = nextOrder
      layerGroups.value[nextId].order = currentOrder
    }
  }

  /** 移到顶层 */
  function moveLayerToTop(layerId: string) {
    const maxOrder = Math.max(...Object.values(layerGroups.value).map(l => l.order))
    layerGroups.value[layerId].order = maxOrder + 1
  }

  /** 移到底层 */
  function moveLayerToBottom(layerId: string) {
    const minOrder = Math.min(...Object.values(layerGroups.value).map(l => l.order))
    layerGroups.value[layerId].order = minOrder - 1
  }

  /** 更新图层样式 */
  function updateLayerStyle(layerId: string, style: Partial<LayerStyle>) {
    if (layerGroups.value[layerId]) {
      layerGroups.value[layerId].data.style = {
        ...layerGroups.value[layerId].data.style,
        ...style,
      }
    }
    if (currentMapId.value) {
      const mapId = currentMapId.value
      const timer = stylePersistTimers[layerId]
      if (timer) clearTimeout(timer)
      stylePersistTimers[layerId] = setTimeout(() => {
        api.patchLayer(mapId, layerId, { style }).catch(() => {})
      }, 350)
    }
  }

  /** 重命名图层 */
  function renameLayer(layerId: string, newName: string) {
    if (layerGroups.value[layerId]) {
      layerGroups.value[layerId].data.name = newName
    }
    if (currentMapId.value) {
      api.patchLayer(currentMapId.value, layerId, { name: newName }).catch(() => {})
    }
  }

  function setQuality(report: any | null) {
    quality.value = report
  }

  /** 删除图层 */
  function removeLayer(layerId: string) {
    delete layerGroups.value[layerId]
  }

  /** 添加图层分组 */
  function addLayerGroup(name: string) {
    const groupId = 'group_' + Date.now()
    const maxOrder = Object.values(layerGroups_meta.value).length > 0
      ? Math.max(...Object.values(layerGroups_meta.value).map(g => g.order))
      : 0
    layerGroups_meta.value[groupId] = {
      name,
      expanded: true,
      order: maxOrder + 1,
    }
    return groupId
  }

  /** 切换分组展开状态 */
  function toggleGroup(groupId: string) {
    if (layerGroups_meta.value[groupId]) {
      layerGroups_meta.value[groupId].expanded = !layerGroups_meta.value[groupId].expanded
    }
  }

  /** 将图层移入分组 */
  function moveLayerToGroup(layerId: string, groupId: string | null) {
    if (layerGroups.value[layerId]) {
      layerGroups.value[layerId].group = groupId || undefined
    }
  }

  /** 设置图层透明度 */
  function setLayerOpacity(layerId: string, opacity: number) {
    if (layerGroups.value[layerId]) {
      layerGroups.value[layerId].data.style = {
        ...layerGroups.value[layerId].data.style,
        opacity,
      }
    }
  }

  return {
    currentMapData,
    currentMapId,
    currentTheme,
    layerGroups,
    layerGroups_meta,
    routeData,
    mapName,
    mapType,
    region,
    metadata,
    quality,
    sortedLayers,
    layerTree,
    setMapData,
    setQuality,
    clearAllLayers,
    setTheme,
    setRouteData,
    clearRoute,
    toggleLayer,
    moveLayerUp,
    moveLayerDown,
    moveLayerToTop,
    moveLayerToBottom,
    updateLayerStyle,
    renameLayer,
    removeLayer,
    addLayerGroup,
    toggleGroup,
    moveLayerToGroup,
    setLayerOpacity,
  }
})
