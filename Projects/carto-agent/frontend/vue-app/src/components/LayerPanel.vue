<template>
  <aside class="layer-panel">
    <!-- 面板头部 -->
    <div class="panel-header">
      <div class="panel-title">
        <i class="fa-solid fa-layer-group"></i>
        <span>图层管理</span>
      </div>
      <div class="panel-actions">
        <button class="icon-btn" title="添加图层组" @click="handleAddGroup">
          <i class="fa-solid fa-folder-plus"></i>
        </button>
        <button class="icon-btn" title="导入数据" @click="handleImportData">
          <i class="fa-solid fa-file-import"></i>
        </button>
        <button class="icon-btn" title="展开全部" @click="expandAll">
          <i class="fa-solid fa-angles-down"></i>
        </button>
      </div>
    </div>

    <!-- 视图切换 -->
    <div class="view-toggle">
      <button 
        class="view-tab" 
        :class="{ active: viewMode === 'type' }"
        @click="viewMode = 'type'"
      >
        <i class="fa-solid fa-shapes"></i>
        <span>按类型</span>
      </button>
      <button 
        class="view-tab" 
        :class="{ active: viewMode === 'group' }"
        @click="viewMode = 'group'"
      >
        <i class="fa-solid fa-folder-tree"></i>
        <span>分组管理</span>
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <i class="fa-solid fa-magnifying-glass search-icon"></i>
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        placeholder="搜索图层..."
      />
    </div>

    <!-- 类型筛选标签（按类型视图） -->
    <div v-if="viewMode === 'type'" class="type-filters">
      <button 
        class="type-tag" 
        :class="{ active: typeFilter === 'all' }"
        @click="typeFilter = 'all'"
      >
        <i class="fa-solid fa-layer-group"></i>
        全部
        <span class="count">{{ allLayers.length }}</span>
      </button>
      <button 
        class="type-tag" 
        :class="{ active: typeFilter === 'point' }"
        @click="typeFilter = 'point'"
      >
        <i class="fa-solid fa-location-dot"></i>
        点状
        <span class="count">{{ pointLayers.length }}</span>
      </button>
      <button 
        class="type-tag" 
        :class="{ active: typeFilter === 'line' }"
        @click="typeFilter = 'line'"
      >
        <i class="fa-solid fa-minus"></i>
        线状
        <span class="count">{{ lineLayers.length }}</span>
      </button>
      <button 
        class="type-tag" 
        :class="{ active: typeFilter === 'polygon' }"
        @click="typeFilter = 'polygon'"
      >
        <i class="fa-regular fa-square"></i>
        面状
        <span class="count">{{ polygonLayers.length }}</span>
      </button>
      <button 
        class="type-tag" 
        :class="{ active: typeFilter === 'other' }"
        @click="typeFilter = 'other'"
      >
        <i class="fa-solid fa-ellipsis"></i>
        其他
        <span class="count">{{ otherLayers.length }}</span>
      </button>
    </div>

    <!-- 图层树 -->
    <!-- quality banner and panel -->
    <div v-if="mapStore.quality" class="quality-banner" :class="{ warn: qualityFail > 0 }" @click="scrollToQuality">
      <i class="fa-solid fa-shield-halved"></i>
      数据质量检测发现 <b>{{ qualityFail }}</b> 项异常
      <button class="quality-recheck" title="重新检测" @click.stop="runQualityCheck">
        <i class="fa-solid fa-rotate"></i>
      </button>
    </div>
    <div v-if="mapStore.quality" class="quality-panel" ref="qualityPanelRef">
      <div class="quality-header">
        <i class="fa-solid fa-shield-halved"></i> 数据质量检测
        <span class="quality-badge" :class="qualityFail > 0 ? 'warn' : 'ok'">
          {{ qualityFail > 0 ? qualityFail + ' 项异常' : '全部通过' }}
        </span>
      </div>
      <div class="quality-items">
        <div
          v-for="(it, qi) in (mapStore.quality.items || [])"
          :key="qi"
          class="quality-item"
          :class="it.passed ? 'ok' : 'err'"
        >
          <span class="quality-ico">{{ it.passed ? '✓' : '✗' }}</span>
          <span class="quality-text">
            {{ it.check }}<b v-if="it.count !== undefined"> {{ it.count }}</b>
          </span>
          <button
            v-if="it.positions && it.positions.length"
            class="quality-locate"
            title="定位问题"
            @click.stop="locateIssue(it.positions[0])"
          >📍</button>
        </div>
      </div>
    </div>

    <div class="layer-tree" ref="treeRef">
      <div v-if="filteredTree.length === 0" class="empty-state">
        <i class="fa-solid fa-map"></i>
        <span>暂无图层</span>
        <span class="empty-hint">通过AI对话生成地图，或导入本地数据</span>
      </div>

      <template v-for="item in filteredTree" :key="item.id">
        <!-- 分组节点 -->
        <div v-if="item.type === 'group'" class="layer-group">
          <div class="group-header" @click="mapStore.toggleGroup(item.id)">
            <i class="fa-solid group-toggle" :class="item.expanded ? 'fa-chevron-down' : 'fa-chevron-right'"></i>
            <i class="fa-solid fa-folder group-icon"></i>
            <span class="group-name">{{ item.name }}</span>
            <span class="group-count">{{ item.children.length }}</span>
          </div>
          <div v-if="item.expanded" class="group-children">
            <div
              v-for="child in item.children"
              :key="child.id"
              class="layer-item"
              :class="{ selected: appStore.selectedLayerId === child.id }"
              @click="selectLayer(child.id)"
              @contextmenu.prevent="showContextMenu($event, child.id)"
            >
              <label class="layer-toggle" @click.stop>
                <input
                  type="checkbox"
                  :checked="child.visible"
                  @change="mapStore.toggleLayer(child.id, ($event.target as HTMLInputElement).checked)"
                />
                <span class="custom-checkbox"></span>
              </label>
              <span class="layer-color" :style="getLayerColorStyle(child.data)"></span>
              <span class="layer-name">{{ child.data.name || '未命名图层' }}</span>
              <span class="layer-type">{{ getLayerTypeLabel(child.data.type) }}</span>
            </div>
          </div>
        </div>

        <!-- 未分组图层 -->
        <div
          v-else
          class="layer-item"
          :class="{ selected: appStore.selectedLayerId === item.id }"
          @click="selectLayer(item.id)"
          @contextmenu.prevent="showContextMenu($event, item.id)"
        >
          <label class="layer-toggle" @click.stop>
            <input
              type="checkbox"
              :checked="item.visible"
              @change="mapStore.toggleLayer(item.id, ($event.target as HTMLInputElement).checked)"
            />
            <span class="custom-checkbox"></span>
          </label>
          <span class="layer-color" :style="getLayerColorStyle(item.data)"></span>
          <span class="layer-name">{{ item.data.name || '未命名图层' }}</span>
          <span class="layer-type">{{ getLayerTypeLabel(item.data.type) }}</span>
        </div>
      </template>
    </div>

    <!-- 选中图层的快速样式控制 -->
    <div v-if="appStore.selectedLayerId && selectedLayerData" class="layer-quick-style">
      <div class="quick-style-header">
        <i class="fa-solid fa-palette"></i>
        <span>快速样式</span>
      </div>
      <div class="quick-style-row">
        <label>颜色</label>
        <input
          type="color"
          :value="selectedLayerData.data.style?.color || '#3388ff'"
          @input="updateStyle('color', ($event.target as HTMLInputElement).value)"
          class="color-picker"
        />
      </div>
      <div class="quick-style-row">
        <label>透明度</label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.1"
          :value="selectedLayerData.data.style?.opacity ?? 1"
          @input="updateStyle('opacity', parseFloat(($event.target as HTMLInputElement).value))"
          class="opacity-slider"
        />
        <span class="opacity-value">{{ Math.round((selectedLayerData.data.style?.opacity ?? 1) * 100) }}%</span>
      </div>
      <div v-if="isLineLayer(selectedLayerData.data.type)" class="quick-style-row">
        <label>线宽</label>
        <input
          type="range"
          min="1"
          max="10"
          step="1"
          :value="selectedLayerData.data.style?.weight || 3"
          @input="updateStyle('weight', parseInt(($event.target as HTMLInputElement).value))"
          class="opacity-slider"
        />
        <span class="opacity-value">{{ selectedLayerData.data.style?.weight || 3 }}px</span>
      </div>
      <button class="open-style-btn" @click="openStylePanel">
        <i class="fa-solid fa-sliders"></i>
        高级样式设置
      </button>
    </div>

    <!-- 右键菜单 -->
    <div
      v-if="contextMenu.visible"
      class="context-menu"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
      <div class="menu-item" @click="zoomToLayer">
        <i class="fa-solid fa-magnifying-glass-plus"></i>
        <span>缩放至图层</span>
      </div>
      <div class="menu-item" @click="moveUp">
        <i class="fa-solid fa-arrow-up"></i>
        <span>上移一层</span>
      </div>
      <div class="menu-item" @click="moveDown">
        <i class="fa-solid fa-arrow-down"></i>
        <span>下移一层</span>
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item" @click="startRename">
        <i class="fa-solid fa-pen"></i>
        <span>重命名</span>
      </div>
      <div class="menu-item" @click="duplicateLayer">
        <i class="fa-solid fa-copy"></i>
        <span>复制图层</span>
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item" @click="openStylePanel">
        <i class="fa-solid fa-palette"></i>
        <span>样式设置</span>
      </div>
      <div class="menu-item" @click="showAttributeTable">
        <i class="fa-solid fa-table"></i>
        <span>属性表</span>
      </div>
      <div class="menu-item" @click="exportLayerGeoJSON">
        <i class="fa-solid fa-file-code"></i>
        <span>导出图层 GeoJSON</span>
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item menu-danger" @click="deleteLayer">
        <i class="fa-solid fa-trash-can"></i>
        <span>删除图层</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import type { MapLayer, LayerType } from '@/types'
import api from '@/services/api'

const appStore = useAppStore()
const mapStore = useMapStore()

const searchQuery = ref('')
const treeRef = ref<HTMLDivElement | null>(null)
const qualityPanelRef = ref<HTMLDivElement | null>(null)

const qualityFail = computed(() => {
  const q = mapStore.quality
  return q?.summary?.failed ?? (q?.items?.filter((i: any) => !i.passed).length ?? 0)
})

// 视图模式: 'type' (按类型分类) | 'group' (自定义分组)
const viewMode = ref<'type' | 'group'>('type')

// 类型筛选
const typeFilter = ref<'all' | 'point' | 'line' | 'polygon' | 'other'>('all')

// 右键菜单状态
const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  layerId: '',
})

// 所有图层列表（按z序，最上层的在前）
const allLayers = computed(() => {
  return [...mapStore.sortedLayers].reverse()
})

// 按类型分类的图层
const pointLayers = computed(() => {
  return allLayers.value.filter(item => {
    const t = item.data.type
    return t === 'point' || t === 'marker' || t === 'circleMarker' || t === 'circle'
  })
})

const lineLayers = computed(() => {
  return allLayers.value.filter(item => {
    const t = item.data.type
    return t === 'line' || t === 'polyline'
  })
})

const polygonLayers = computed(() => {
  return allLayers.value.filter(item => {
    const t = item.data.type
    return t === 'polygon' || t === 'area'
  })
})

const otherLayers = computed(() => {
  return allLayers.value.filter(item => {
    const t = item.data.type
    return t !== 'point' && t !== 'marker' && t !== 'circleMarker' && t !== 'circle' &&
           t !== 'line' && t !== 'polyline' &&
           t !== 'polygon' && t !== 'area'
  })
})

// 按类型筛选后的图层
const filteredByType = computed(() => {
  let layers = allLayers.value
  
  switch (typeFilter.value) {
    case 'point':
      layers = pointLayers.value
      break
    case 'line':
      layers = lineLayers.value
      break
    case 'polygon':
      layers = polygonLayers.value
      break
    case 'other':
      layers = otherLayers.value
      break
  }
  
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    layers = layers.filter(item => item.data.name?.toLowerCase().includes(query))
  }
  
  return layers
})

// 过滤后的图层树
const filteredTree = computed(() => {
  // 按类型视图 - 直接返回图层列表
  if (viewMode.value === 'type') {
    return filteredByType.value.map(item => ({ type: 'layer', ...item }))
  }
  
  // 分组视图 - 返回分组树
  if (!searchQuery.value.trim()) {
    return mapStore.layerTree
  }
  const query = searchQuery.value.toLowerCase()
  return mapStore.layerTree.filter((item: any) => {
    if (item.type === 'group') {
      return item.name.toLowerCase().includes(query) ||
        item.children.some((c: any) => c.data.name?.toLowerCase().includes(query))
    }
    return item.data.name?.toLowerCase().includes(query)
  })
})

// 当前选中的图层数据
const selectedLayerData = computed(() => {
  if (!appStore.selectedLayerId) return null
  return mapStore.layerGroups[appStore.selectedLayerId] || null
})

// 获取图层颜色样式
function getLayerColorStyle(layer: MapLayer) {
  const style = layer.style || {}
  const color = style.color || style.fillColor || '#3388ff'
  const isPolygon = layer.type === 'polygon' || layer.type === 'area'
  return {
    background: isPolygon ? style.fillColor || color + '40' : color,
    borderColor: color,
    borderRadius: layer.type === 'point' || layer.type === 'marker' || layer.type === 'circleMarker' ? '50%' : '2px',
    borderStyle: style.dashArray ? 'dashed' : 'solid',
  }
}

// 获取图层类型标签
function getLayerTypeLabel(type: LayerType): string {
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

// 判断是否为线图层
function isLineLayer(type: LayerType): boolean {
  return type === 'polyline' || type === 'line'
}

// 选中图层
function selectLayer(layerId: string) {
  appStore.setSelectedLayer(layerId)
  hideContextMenu()
}

// 显示右键菜单
function showContextMenu(event: MouseEvent, layerId: string) {
  contextMenu.value = {
    visible: true,
    x: event.offsetX,
    y: event.offsetY,
    layerId,
  }
  appStore.setSelectedLayer(layerId)
}

// 隐藏右键菜单
function hideContextMenu() {
  contextMenu.value.visible = false
}

// 点击外部关闭右键菜单
function handleClickOutside() {
  hideContextMenu()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// 右键菜单操作
function zoomToLayer() {
  // 触发地图缩放至图层事件
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-zoom-to-layer', { detail: { layerId: contextMenu.value.layerId } }))
  }
  hideContextMenu()
}

function moveUp() {
  mapStore.moveLayerUp(contextMenu.value.layerId)
  refreshMapRender()
  hideContextMenu()
}

function moveDown() {
  mapStore.moveLayerDown(contextMenu.value.layerId)
  refreshMapRender()
  hideContextMenu()
}

function startRename() {
  const layer = mapStore.layerGroups[contextMenu.value.layerId]
  if (layer) {
    const newName = prompt('请输入新的图层名称:', layer.data.name)
    if (newName && newName.trim()) {
      mapStore.renameLayer(contextMenu.value.layerId, newName.trim())
    }
  }
  hideContextMenu()
}

function duplicateLayer() {
  const layerId = contextMenu.value.layerId
  const item = mapStore.layerGroups[layerId]
  if (!item) return
  const copy: MapLayer = JSON.parse(JSON.stringify(item.data))
  copy.id = 'copy_' + Date.now()
  copy.name = (copy.name || '未命名图层') + ' 副本'
  const maxOrder = Math.max(0, ...mapStore.sortedLayers.map((l) => l.order))
  mapStore.layerGroups[copy.id] = { visible: true, data: copy, order: maxOrder + 1 }
  hideContextMenu()
}

function deleteLayer() {
  if (confirm('确定要删除该图层吗？')) {
    mapStore.removeLayer(contextMenu.value.layerId)
    if (appStore.selectedLayerId === contextMenu.value.layerId) {
      appStore.setSelectedLayer(null)
    }
    refreshMapRender()
  }
  hideContextMenu()
}

function openStylePanel() {
  appStore.toggleStylePanel()
  hideContextMenu()
}

function showAttributeTable() {
  appStore.openAttributeTable(contextMenu.value.layerId)
  hideContextMenu()
}

// 更新样式
function updateStyle(key: keyof any, value: any) {
  if (appStore.selectedLayerId) {
    mapStore.updateLayerStyle(appStore.selectedLayerId, { [key]: value })
    refreshMapRender()
  }
}

// 刷新地图渲染
function refreshMapRender() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-refresh-layers'))
  }
}

// 添加图层组
function handleAddGroup() {
  const name = prompt('请输入图层组名称:', '新建图层组')
  if (name && name.trim()) {
    mapStore.addLayerGroup(name.trim())
  }
}

// 导入数据
function handleImportData() {
  appStore.toggleImportModal()
}

// 展开全部
function expandAll() {
  Object.keys(mapStore.layerGroups_meta).forEach((groupId) => {
    if (!mapStore.layerGroups_meta[groupId].expanded) {
      mapStore.toggleGroup(groupId)
    }
  })
}

function scrollToQuality() {
  qualityPanelRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

async function runQualityCheck() {
  if (!mapStore.currentMapId) return
  try {
    const resp = await api.getMapQuality(mapStore.currentMapId)
    mapStore.setQuality(resp.data || resp)
  } catch (e: any) {
    alert('质检失败: ' + e.message)
  }
}

function locateIssue(pos: [number, number]) {
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent('map-locate', { detail: { lat: pos[0], lng: pos[1] } }))
  }
}

function exportLayerGeoJSON() {
  const layerId = contextMenu.value.layerId
  const item = mapStore.layerGroups[layerId]
  if (!item) return
  const layer = item.data
  const features: any[] = []
  const props = layer.properties || []
  const coords = layer.coordinates || []
  if (layer.features && Array.isArray(layer.features)) {
    layer.features.forEach((f: any) => features.push(f))
  } else {
    coords.forEach((c: any, i: number) => {
      const t = layer.type || ''
      if (t === 'polygon' || t === 'area') {
        if (Array.isArray(c[0])) {
          features.push({
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [c.map((p: number[]) => [p[1], p[0]])] },
            properties: props[i] || {},
          })
        }
      } else if (t === 'polyline' || t === 'line') {
        if (Array.isArray(c[0])) {
          features.push({
            type: 'Feature',
            geometry: { type: 'LineString', coordinates: c.map((p: number[]) => [p[1], p[0]]) },
            properties: props[i] || {},
          })
        }
      } else {
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [c[1], c[0]] },
          properties: props[i] || {},
        })
      }
    })
  }
  const blob = new Blob([JSON.stringify({ type: 'FeatureCollection', features }, null, 2)], {
    type: 'application/geo+json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = (layer.name || 'layer') + '.geojson'
  a.click()
  URL.revokeObjectURL(url)
  hideContextMenu()
}
</script>

<style scoped>
.layer-panel {
  width: 280px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  position: relative;
  z-index: 10;
}

/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.panel-title i {
  color: var(--color-primary);
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.icon-btn {
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
  font-size: 13px;
  transition: all 0.15s;
}

.icon-btn:hover {
  background: rgba(139, 92, 246, 0.1);
  color: var(--color-primary);
}

/* 视图切换 */
.view-toggle {
  display: flex;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
  gap: 4px;
}

.view-tab {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  transition: all 0.2s;
}

.view-tab:hover {
  background: rgba(139, 92, 246, 0.05);
  border-color: var(--color-primary-light);
}

.view-tab.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.view-tab i {
  font-size: 12px;
}

/* 搜索框 */
.search-box {
  position: relative;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}

.search-icon {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.search-input {
  width: 100%;
  padding: 6px 10px 6px 28px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: var(--color-bg);
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--color-primary-light);
  background: #fff;
}

/* 类型筛选标签 */
.type-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.type-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 16px;
  cursor: pointer;
  font-size: 11px;
  color: var(--color-text-secondary);
  transition: all 0.2s;
}

.type-tag:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.type-tag.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.type-tag .count {
  background: rgba(0, 0, 0, 0.1);
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 10px;
}

.type-tag.active .count {
  background: rgba(255, 255, 255, 0.25);
}

/* 图层树 */
.layer-tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--color-text-secondary);
  text-align: center;
}

.empty-state i {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.3;
}

.empty-state span {
  font-size: 13px;
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 11px !important;
  opacity: 0.7;
  margin-top: 4px;
}

/* 分组 */
.layer-group {
  margin-bottom: 2px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  background: rgba(139, 92, 246, 0.04);
  user-select: none;
  transition: background 0.15s;
}

.group-header:hover {
  background: rgba(139, 92, 246, 0.08);
}

.group-toggle {
  font-size: 10px;
  color: var(--color-text-secondary);
  width: 12px;
}

.group-icon {
  color: #f59e0b;
  font-size: 12px;
}

.group-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-count {
  font-size: 10px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 1px 6px;
  border-radius: 10px;
}

.group-children {
  padding-left: 12px;
}

/* 图层项 */
.layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
  border-left: 2px solid transparent;
}

.layer-item:hover {
  background: var(--color-bg);
}

.layer-item.selected {
  background: rgba(139, 92, 246, 0.08);
  border-left-color: var(--color-primary);
}

.layer-toggle {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.layer-toggle input {
  display: none;
}

.custom-checkbox {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--color-border);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  background: #fff;
}

.layer-toggle input:checked + .custom-checkbox {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.layer-toggle input:checked + .custom-checkbox::after {
  content: '\f00c';
  font-family: 'Font Awesome 6 Free';
  font-weight: 900;
  font-size: 8px;
  color: #fff;
}

.layer-color {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border: 1.5px solid;
}

.layer-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text);
}

.layer-type {
  font-size: 10px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

/* 快速样式 */
.layer-quick-style {
  border-top: 1px solid var(--color-border);
  padding: 10px 12px;
  background: #fafbfc;
}

.quick-style-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 10px;
}

.quick-style-header i {
  color: var(--color-primary);
}

.quick-style-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.quick-style-row label {
  width: 40px;
  flex-shrink: 0;
}

.color-picker {
  width: 30px;
  height: 24px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  padding: 0;
  background: none;
}

.opacity-slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border);
  border-radius: 2px;
  outline: none;
}

.opacity-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.opacity-value {
  width: 36px;
  text-align: right;
  font-size: 11px;
  color: var(--color-text);
}

.open-style-btn {
  width: 100%;
  padding: 6px;
  margin-top: 6px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
}

.open-style-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: rgba(139, 92, 246, 0.05);
}

/* 右键菜单 */
.context-menu {
  position: absolute;
  z-index: 1000;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  min-width: 140px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  font-size: 12px;
  color: var(--color-text);
  cursor: pointer;
  transition: background 0.1s;
}

.menu-item:hover {
  background: var(--color-bg);
}

.menu-item i {
  width: 14px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.menu-item.menu-danger {
  color: var(--color-error);
}

.menu-item.menu-danger i {
  color: var(--color-error);
}

.menu-item.menu-danger:hover {
  background: rgba(239, 68, 68, 0.08);
}

.menu-divider {
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}

/* 滚动条美化 */
/* 质检区域 */
.quality-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin: 8px 10px 0;
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
}

.quality-banner:not(.warn) {
  display: none;
}

.quality-banner b {
  margin: 0 2px;
}

.quality-recheck {
  margin-left: auto;
  border: none;
  background: transparent;
  color: #b45309;
  cursor: pointer;
  font-size: 12px;
}

.quality-panel {
  margin: 8px 10px 0;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.quality-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 10px;
  background: #f8fafc;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text);
}

.quality-badge {
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
}

.quality-badge.ok {
  background: rgba(16, 185, 129, 0.12);
  color: #15803d;
}

.quality-badge.warn {
  background: rgba(245, 158, 11, 0.15);
  color: #b45309;
}

.quality-items {
  padding: 4px 0;
  max-height: 160px;
  overflow-y: auto;
}

.quality-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  border-left: 2px solid transparent;
}

.quality-item.ok {
  border-left-color: var(--color-success);
}

.quality-item.err {
  border-left-color: var(--color-error);
  background: rgba(239, 68, 68, 0.03);
}

.quality-ico {
  width: 14px;
  text-align: center;
  flex-shrink: 0;
}

.quality-item.ok .quality-ico {
  color: var(--color-success);
}

.quality-item.err .quality-ico {
  color: var(--color-error);
}

.quality-text {
  flex: 1;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quality-locate {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  flex-shrink: 0;
}

.layer-tree::-webkit-scrollbar {
  width: 6px;
}

.layer-tree::-webkit-scrollbar-track {
  background: transparent;
}

.layer-tree::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}

.layer-tree::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-secondary);
}
</style>
