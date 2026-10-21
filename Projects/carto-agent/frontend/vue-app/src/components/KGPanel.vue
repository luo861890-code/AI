<template>
  <div class="kg-panel">
    <div class="kg-panel-header">
      <span class="kg-panel-title">
        <i class="fa-solid fa-diagram-project"></i> 知识图谱
      </span>
      <div class="kg-panel-actions">
        <button class="kg-action-btn" title="重新布局" @click="handleReheat">
          <i class="fa-solid fa-arrows-rotate"></i>
        </button>
        <button class="kg-action-btn" title="重置缩放" @click="handleResetZoom">
          <i class="fa-solid fa-arrows-to-dot"></i>
        </button>
        <button class="kg-action-btn" title="刷新数据" @click="kgStore.loadGraph()">
          <i class="fa-solid fa-rotate-right"></i>
        </button>
        <button class="kg-action-btn" title="关闭" @click="appStore.toggleKGPanel()">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <!-- 搜索 -->
    <div class="kg-search-wrapper">
      <input
        v-model="searchInput"
        type="text"
        class="kg-search-input"
        placeholder="搜索节点..."
        @input="handleSearch"
      />
    </div>

    <!-- 类型筛选按钮组 -->
    <div class="kg-type-filters">
      <button
        class="type-filter-btn"
        :class="{ active: kgStore.activeFilters.size === 0 }"
        @click="kgStore.clearFilters()"
      >全部</button>
      <button
        v-for="(color, label) in CONFIG.kgNodeColors"
        :key="label"
        class="type-filter-btn"
        :class="{ active: kgStore.activeFilters.has(label) }"
        @click="kgStore.toggleFilter(label)"
      >
        <span class="filter-color-dot" :style="{ background: color }"></span>
        {{ label }}
      </button>
    </div>

    <!-- SVG容器 -->
    <div ref="svgContainerRef" class="kg-svg-container">
      <svg ref="svgRef" width="100%" height="100%"></svg>
    </div>

    <!-- 节点详情面板 -->
    <div v-if="kgStore.selectedNode" class="kg-node-detail">
      <div class="detail-header">
        <span class="detail-color-dot" :style="{ background: getNodeColor(kgStore.selectedNode) }"></span>
        <span class="detail-name">{{ kgStore.selectedNode.name || kgStore.selectedNode.id }}</span>
        <button class="detail-close" @click="kgStore.selectNode(null)">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="detail-section">
        <div class="detail-section-title">基本信息</div>
        <div class="detail-prop">
          <span class="detail-prop-key">ID</span>
          <span class="detail-prop-val">{{ kgStore.selectedNode.id }}</span>
        </div>
        <div class="detail-prop">
          <span class="detail-prop-key">类型</span>
          <span class="detail-prop-val">{{ kgStore.selectedNode.label || '未知' }}</span>
        </div>
        <div class="detail-prop">
          <span class="detail-prop-key">名称</span>
          <span class="detail-prop-val">{{ kgStore.selectedNode.name || '未命名' }}</span>
        </div>
      </div>
      <div v-if="kgStore.selectedNode.properties && Object.keys(kgStore.selectedNode.properties).length" class="detail-section">
        <div class="detail-section-title">属性 ({{ Object.keys(kgStore.selectedNode.properties).length }})</div>
        <div v-for="(value, key) in kgStore.selectedNode.properties" :key="key" class="detail-prop">
          <span class="detail-prop-key">{{ key }}</span>
          <span class="detail-prop-val">{{ String(value) }}</span>
        </div>
      </div>
    </div>

    <!-- 底栏 -->
    <div class="kg-footer">
      <span>{{ kgStore.graphData.nodes.length }} 节点 / {{ kgStore.graphData.links.length }} 关系</span>
      <span class="kg-footer-hint">拖拽节点 | 滚轮缩放</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { useAppStore } from '@/stores/appStore'
import { useKGStore } from '@/stores/kgStore'
import { CONFIG } from '@/config'
import type { KGNode, KGLink } from '@/types'

const appStore = useAppStore()
const kgStore = useKGStore()

const svgRef = ref<SVGSVGElement | null>(null)
const svgContainerRef = ref<HTMLDivElement | null>(null)
const searchInput = ref('')

let svg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let g: d3.Selection<SVGGElement, unknown, null, undefined> | null = null
let simulation: d3.Simulation<KGNode, KGLink> | null = null
let zoom: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let linkGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null
let nodeGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null
let width = 0
let height = 0

onMounted(async () => {
  await nextTick()
  initD3()
  await kgStore.loadGraph()
})

onUnmounted(() => {
  simulation?.stop()
})

watch(
  () => kgStore.graphData,
  () => {
    renderGraph()
  },
  { deep: true }
)

function initD3() {
  if (!svgRef.value || !svgContainerRef.value) return

  width = svgContainerRef.value.clientWidth
  height = svgContainerRef.value.clientHeight

  svg = d3.select(svgRef.value)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')

  // 箭头标记
  const defs = svg.append('defs')
  Object.entries(CONFIG.kgNodeColors).forEach(([label, color]) => {
    defs.append('marker')
      .attr('id', `arrow-${label}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', color)
  })
  defs.append('marker')
    .attr('id', 'arrow-default')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#999')

  g = svg.append('g')
  linkGroup = g.append('g').attr('class', 'links')
  nodeGroup = g.append('g').attr('class', 'nodes')

  // 缩放行为
  zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g?.attr('transform', event.transform.toString())
    })
  svg.call(zoom)

  // 力导向仿真
  simulation = d3.forceSimulation<KGNode>()
    .force('link', d3.forceLink<KGNode, KGLink>()
      .id((d: KGNode) => d.id)
      .distance(() => 80)
      .strength(() => 0.3)
    )
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide<KGNode>().radius((d: KGNode) => getNodeRadius(d) + 5))
    .on('tick', tick)

  // 窗口大小监听
  window.addEventListener('resize', handleResize)
}

function renderGraph() {
  if (!simulation || !linkGroup || !nodeGroup) return
  const nodes = kgStore.graphData.nodes
  const links = kgStore.graphData.links

  simulation.nodes(nodes)
  simulation.force<d3.ForceLink<KGNode, KGLink>>('link')?.links(links)

  // 连线
  linkGroup.selectAll('line')
    .data(links, (d: any) => {
      const s = typeof d.source === 'object' ? d.source.id : d.source
      const t = typeof d.target === 'object' ? d.target.id : d.target
      return s + '-' + t
    })
    .join(
      (enter) => enter.append('line')
        .attr('class', 'graph-link')
        .attr('stroke', '#94a3b8')
        .attr('stroke-opacity', 0.5)
        .attr('stroke-width', (d: any) => Math.sqrt(d.value || 1)),
      (update) => update,
      (exit) => exit.remove()
    )

  // 节点
  nodeGroup.selectAll('g.graph-node')
    .data(nodes, (d: any) => d.id)
    .join(
      (enter) => {
        const nodeEnter = enter.append('g')
          .attr('class', 'graph-node')
          .call(d3.drag<SVGGElement, KGNode>()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded)
          )

        nodeEnter.append('circle')
          .attr('class', 'node-circle')
          .attr('r', (d: KGNode) => getNodeRadius(d))
          .attr('fill', (d: KGNode) => getNodeColor(d))
          .attr('stroke', '#fff')
          .attr('stroke-width', 2)

        nodeEnter.append('text')
          .attr('class', 'node-label')
          .attr('dy', (d: KGNode) => getNodeRadius(d) + 14)
          .attr('text-anchor', 'middle')
          .text((d: KGNode) => truncateText(d.name || d.id, 10))
          .attr('font-size', '10px')
          .attr('fill', '#475569')

        nodeEnter
          .on('mouseover', handleMouseOver)
          .on('mouseout', handleMouseOut)
          .on('click', handleNodeClick)

        return nodeEnter
      },
      (update) => update,
      (exit) => exit.remove()
    )

  simulation.alpha(0.5).restart()
  applySearchHighlight()
}

function tick() {
  linkGroup?.selectAll('line')
    .attr('x1', (d: any) => d.source.x)
    .attr('y1', (d: any) => d.source.y)
    .attr('x2', (d: any) => d.target.x)
    .attr('y2', (d: any) => d.target.y)

  nodeGroup?.selectAll('g.graph-node')
    .attr('transform', (d: any) => {
      const r = getNodeRadius(d)
      d.x = Math.max(r, Math.min(width - r, d.x))
      d.y = Math.max(r, Math.min(height - r, d.y))
      return `translate(${d.x}, ${d.y})`
    })
}

function getNodeRadius(d: KGNode): number {
  if (d.radius) return d.radius
  const baseSize = 12
  const connections = d.connections || d.degree || 0
  return Math.max(8, Math.min(25, baseSize + connections * 1.5))
}

function getNodeColor(d: KGNode): string {
  return CONFIG.kgNodeColors[d.label] || '#64748b'
}

function truncateText(text: string, maxLen = 10): string {
  if (!text) return ''
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text
}

// 拖拽
function dragStarted(event: d3.D3DragEvent<SVGGElement, KGNode, KGNode>, d: KGNode) {
  if (!event.active) simulation?.alphaTarget(0.3).restart()
  d.fx = d.x
  d.fy = d.y
}

function dragged(event: d3.D3DragEvent<SVGGElement, KGNode, KGNode>, d: KGNode) {
  d.fx = event.x
  d.fy = event.y
}

function dragEnded(event: d3.D3DragEvent<SVGGElement, KGNode, KGNode>, d: KGNode) {
  if (!event.active) simulation?.alphaTarget(0)
  d.fx = null
  d.fy = null
}

// 鼠标事件
function handleMouseOver(event: MouseEvent, d: KGNode) {
  d3.select(event.currentTarget as SVGGElement).select('circle')
    .transition().duration(200)
    .attr('r', getNodeRadius(d) * 1.3)
    .attr('stroke-width', 3)
}

function handleMouseOut(event: MouseEvent, d: KGNode) {
  d3.select(event.currentTarget as SVGGElement).select('circle')
    .transition().duration(200)
    .attr('r', getNodeRadius(d))
    .attr('stroke-width', 2)
}

function handleNodeClick(event: MouseEvent, d: KGNode) {
  event.stopPropagation()
  kgStore.selectNode(d)
}

// 搜索
function handleSearch() {
  kgStore.setSearch(searchInput.value.trim().toLowerCase())
  applySearchHighlight()
}

function applySearchHighlight() {
  if (!nodeGroup) return
  const keyword = searchInput.value.trim().toLowerCase()
  nodeGroup.selectAll('g.graph-node')
    .classed('node-highlighted', (d: any) => {
      if (!keyword) return false
      const name = (d.name || d.id || '').toLowerCase()
      return name.includes(keyword)
    })
    .classed('node-dimmed', (d: any) => {
      if (!keyword) return false
      const name = (d.name || d.id || '').toLowerCase()
      return !name.includes(keyword)
    })
}

// 工具栏按钮
function handleReheat() {
  simulation?.alpha(1).restart()
}

function handleResetZoom() {
  svg?.transition().duration(500).call(zoom!.transform, d3.zoomIdentity)
}

function handleResize() {
  if (!svgContainerRef.value || !svgRef.value) return
  width = svgContainerRef.value.clientWidth
  height = svgContainerRef.value.clientHeight
  d3.select(svgRef.value).attr('viewBox', `0 0 ${width} ${height}`)
  simulation?.force('center', d3.forceCenter(width / 2, height / 2))
  simulation?.alpha(0.3).restart()
}
</script>

<style scoped>
.kg-panel {
  position: absolute;
  top: 0;
  right: var(--toolbar-width);
  bottom: 0;
  width: 420px;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  z-index: 30;
  border-left: 1px solid var(--color-border);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.08);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.kg-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #7c3aed08, #6d28d908);
}
.kg-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.kg-panel-actions {
  display: flex;
  gap: 2px;
}
.kg-action-btn {
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--color-text-secondary);
  transition: all 0.15s;
}
.kg-action-btn:hover {
  background: var(--color-bg);
  color: var(--color-primary);
}

.kg-search-wrapper {
  padding: 8px 14px;
}
.kg-search-input {
  width: 100%;
  padding: 7px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  outline: none;
}
.kg-search-input:focus {
  border-color: var(--color-primary-light);
}

.kg-type-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0 14px 8px;
}
.type-filter-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 14px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--color-text-secondary);
}
.type-filter-btn:hover {
  border-color: var(--color-primary-light);
}
.type-filter-btn.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.filter-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.kg-svg-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.kg-svg-container svg {
  display: block;
}

/* 节点状态 */
:deep(.node-highlighted circle) {
  stroke: #7c3aed !important;
  stroke-width: 3 !important;
  filter: drop-shadow(0 0 6px rgba(124, 58, 237, 0.5));
}
:deep(.node-dimmed) {
  opacity: 0.25;
}
:deep(.node-circle) {
  cursor: pointer;
  transition: all 0.2s;
}

/* 节点详情 */
.kg-node-detail {
  position: absolute;
  bottom: 36px;
  left: 10px;
  right: 10px;
  max-height: 40%;
  background: rgba(255, 255, 255, 0.98);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow-y: auto;
  padding: 12px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.detail-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}
.detail-name {
  font-size: 14px;
  font-weight: 600;
  flex: 1;
}
.detail-close {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.detail-section {
  margin-bottom: 10px;
}
.detail-section-title {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-weight: 600;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.detail-prop {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
  border-bottom: 1px dashed var(--color-border);
}
.detail-prop-key {
  color: var(--color-text-secondary);
}
.detail-prop-val {
  color: var(--color-text);
  text-align: right;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kg-footer {
  display: flex;
  justify-content: space-between;
  padding: 6px 14px;
  font-size: 11px;
  color: var(--color-text-secondary);
  border-top: 1px solid var(--color-border);
}
</style>
