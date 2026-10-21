<template>
  <aside class="chat-panel">
    <!-- 快捷指令区 -->
    <div class="quick-commands" :class="{ collapsed: quickCommandsCollapsed }">
      <div class="quick-commands-header">
        <span @click="quickCommandsCollapsed = !quickCommandsCollapsed">
          <i class="fa-solid fa-bolt"></i> 快捷指令
        </span>
        <div class="header-actions">
          <button 
            class="task-param-btn" 
            title="地图统计数据"
            @click.stop="showMapStats = !showMapStats; showTaskParams = false"
            :class="{ active: showMapStats }"
          >
            <i class="fa-solid fa-chart-simple"></i>
          </button>
          <button 
            class="task-param-btn" 
            title="任务参数"
            @click.stop="showTaskParams = !showTaskParams; showMapStats = false"
            :class="{ active: showTaskParams }"
          >
            <i class="fa-solid fa-sliders"></i>
          </button>
          <i 
            class="fa-solid collapse-icon" 
            :class="quickCommandsCollapsed ? 'fa-chevron-down' : 'fa-chevron-up'"
            @click="quickCommandsCollapsed = !quickCommandsCollapsed"
          ></i>
        </div>
      </div>
      
      <!-- 地图统计数据面板 -->
      <div v-if="showMapStats && !quickCommandsCollapsed" class="map-stats-panel">
        <div class="panel-title">
          <i class="fa-solid fa-chart-simple"></i> 地图统计数据
        </div>
        
        <!-- 图层统计 -->
        <div class="stats-section">
          <div class="stats-section-title">图层统计</div>
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-num">{{ mapStats.totalLayers }}</span>
              <span class="stat-label">图层总数</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ mapStats.totalFeatures }}</span>
              <span class="stat-label">要素总数</span>
            </div>
          </div>
          <div class="stats-grid three-col">
            <div class="stat-card point">
              <span class="stat-num">{{ mapStats.pointLayers }}</span>
              <span class="stat-label">点状图层</span>
            </div>
            <div class="stat-card line">
              <span class="stat-num">{{ mapStats.lineLayers }}</span>
              <span class="stat-label">线状图层</span>
            </div>
            <div class="stat-card polygon">
              <span class="stat-num">{{ mapStats.polygonLayers }}</span>
              <span class="stat-label">面状图层</span>
            </div>
          </div>
        </div>
        
        <!-- 要素统计 -->
        <div class="stats-section">
          <div class="stats-section-title">要素统计</div>
          <div class="stats-grid three-col">
            <div class="stat-card point">
              <span class="stat-num">{{ mapStats.pointFeatures }}</span>
              <span class="stat-label">点要素</span>
            </div>
            <div class="stat-card line">
              <span class="stat-num">{{ mapStats.lineFeatures }}</span>
              <span class="stat-label">线要素</span>
            </div>
            <div class="stat-card polygon">
              <span class="stat-num">{{ mapStats.polygonFeatures }}</span>
              <span class="stat-label">面要素</span>
            </div>
          </div>
        </div>
        
        <!-- 空间信息 -->
        <div class="stats-section">
          <div class="stats-section-title">空间信息</div>
          <div class="stat-row">
            <span class="stat-row-label">中心点</span>
            <span class="stat-row-value">{{ mapStats.center || '-' }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row-label">投影方式</span>
            <span class="stat-row-value">{{ mapStats.projection || 'Web墨卡托' }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row-label">当前缩放</span>
            <span class="stat-row-value">{{ mapStats.zoom || '-' }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row-label">地图范围</span>
            <span class="stat-row-value">{{ mapStats.bounds || '-' }}</span>
          </div>
        </div>
        
        <!-- 数据来源 -->
        <div class="stats-section">
          <div class="stats-section-title">数据来源</div>
          <div class="stat-row">
            <span class="stat-row-label">底图</span>
            <span class="stat-row-value">{{ mapStats.baseMap || '高德地图' }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row-label">数据来源</span>
            <span class="stat-row-value">{{ mapStats.dataSource || 'OSM / 本地数据' }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-row-label">创建时间</span>
            <span class="stat-row-value">{{ mapStats.createTime || '-' }}</span>
          </div>
        </div>
        
        <!-- 刷新按钮 -->
        <div class="stats-actions">
          <button class="stats-refresh-btn" @click="refreshMapStats">
            <i class="fa-solid fa-rotate-right"></i> 刷新统计
          </button>
        </div>
      </div>
      
      <!-- 任务参数面板 -->
      <div v-if="showTaskParams && !quickCommandsCollapsed" class="task-params-panel">
        <div class="panel-title">
          <i class="fa-solid fa-sliders"></i> 任务参数
        </div>
        
        <!-- 基本信息 -->
        <div class="param-section">
          <div class="param-section-title">基本信息</div>
          <div class="param-edit-item">
            <label class="param-edit-label">地图名称</label>
            <input 
              type="text" 
              class="param-edit-input" 
              v-model="taskParams.mapName" 
              placeholder="输入地图名称"
            />
          </div>
          <div class="param-edit-item">
            <label class="param-edit-label">地图类型</label>
            <select class="param-edit-select" v-model="taskParams.mapType">
              <option value="">请选择</option>
              <option value="administrative">行政区划图</option>
              <option value="traffic">交通地图</option>
              <option value="tourism">旅游地图</option>
              <option value="thematic">专题地图</option>
              <option value="topographic">地形图</option>
            </select>
          </div>
        </div>
        
        <!-- 空间参数 -->
        <div class="param-section">
          <div class="param-section-title">空间参数</div>
          <div class="param-edit-item">
            <label class="param-edit-label">地理范围</label>
            <input 
              type="text" 
              class="param-edit-input" 
              v-model="taskParams.region" 
              placeholder="如：武汉市"
            />
          </div>
          <div class="param-edit-item">
            <label class="param-edit-label">投影方式</label>
            <select class="param-edit-select" v-model="taskParams.projection">
              <option value="Web墨卡托">Web墨卡托</option>
              <option value="WGS84">WGS84经纬度</option>
              <option value="高斯-克吕格">高斯-克吕格</option>
              <option value="UTM">UTM投影</option>
              <option value="兰伯特等角">兰伯特等角</option>
              <option value="阿尔伯斯等积">阿尔伯斯等积</option>
            </select>
          </div>
          <div class="param-edit-item">
            <label class="param-edit-label">目标比例尺</label>
            <input 
              type="text" 
              class="param-edit-input" 
              v-model="taskParams.scale" 
              placeholder="如：1:100000"
            />
          </div>
        </div>
        
        <!-- 样式参数 -->
        <div class="param-section">
          <div class="param-section-title">样式参数</div>
          <div class="param-edit-item">
            <label class="param-edit-label">底图样式</label>
            <select class="param-edit-select" v-model="taskParams.baseMap">
              <option value="高德地图">高德地图</option>
              <option value="高德卫星">高德卫星</option>
              <option value="天地图矢量">天地图矢量</option>
              <option value="天地图影像">天地图影像</option>
              <option value="OSM标准">OSM标准</option>
              <option value="OSM暗色">OSM暗色</option>
              <option value="纯色底图">纯色底图</option>
            </select>
          </div>
          <div class="param-edit-item">
            <label class="param-edit-label">配色方案</label>
            <select class="param-edit-select" v-model="taskParams.colorScheme">
              <option value="默认">默认</option>
              <option value="暖色调">暖色调</option>
              <option value="冷色调">冷色调</option>
              <option value="自然色">自然色</option>
              <option value="单色">单色</option>
            </select>
          </div>
          <div class="param-edit-item">
            <label class="param-edit-label">图层透明度</label>
            <div class="param-slider-wrapper">
              <input 
                type="range" 
                class="param-slider" 
                v-model.number="taskParams.opacityValue" 
                min="0" 
                max="100"
              />
              <span class="param-slider-value">{{ taskParams.opacityValue }}%</span>
            </div>
          </div>
        </div>
        
        <!-- 内容要求 -->
        <div class="param-section">
          <div class="param-section-title">内容要求</div>
          <div class="param-edit-item">
            <label class="param-edit-label">要素类型</label>
            <div class="param-check-group">
              <label class="param-check">
                <input type="checkbox" v-model="taskParams.includePoints" />
                <span>点要素</span>
              </label>
              <label class="param-check">
                <input type="checkbox" v-model="taskParams.includeLines" />
                <span>线要素</span>
              </label>
              <label class="param-check">
                <input type="checkbox" v-model="taskParams.includePolygons" />
                <span>面要素</span>
              </label>
            </div>
          </div>
          <div class="param-edit-item">
            <label class="param-edit-label">显示标注</label>
            <div class="param-check-group">
              <label class="param-check">
                <input type="checkbox" v-model="taskParams.showLabels" />
                <span>显示标注</span>
              </label>
              <label class="param-check">
                <input type="checkbox" v-model="taskParams.showLegend" />
                <span>显示图例</span>
              </label>
            </div>
          </div>
        </div>
        
        <!-- 操作按钮 -->
        <div class="param-actions">
          <button class="param-action-btn" @click="resetTaskParams">
            <i class="fa-solid fa-rotate-left"></i> 重置
          </button>
          <button class="param-action-btn primary" @click="applyTaskParams">
            <i class="fa-solid fa-check"></i> 应用参数
          </button>
        </div>
      </div>
      
      <div v-if="!quickCommandsCollapsed" class="quick-commands-list">
        <button
          v-for="cmd in quickCommands"
          :key="cmd.label"
          class="quick-command-btn"
          @click="handleQuickCommand(cmd)"
        >
          <i class="fa-solid" :class="cmd.icon"></i>
          <span>{{ cmd.label }}</span>
        </button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div ref="messageListRef" class="chat-messages">
      <div v-if="chatStore.messages.length === 0" class="chat-welcome">
        <div class="chat-welcome-icon">
          <i class="fa-solid fa-map-location-dot"></i>
        </div>
        <h2 class="chat-welcome-title">欢迎使用地图制图智能体</h2>
        <p class="chat-welcome-hint">描述你想要的地图效果，我来帮你生成</p>
      </div>

      <div
        v-for="(msg, idx) in chatStore.messages"
        :key="idx"
        class="message"
        :class="`message-${msg.role}`"
      >
        <div class="message-avatar">
          <i class="fa-solid" :class="msg.role === 'user' ? 'fa-user' : 'fa-robot'"></i>
        </div>
        <div class="message-body">
          <div class="message-meta">
            <span class="message-role">{{ msg.role === 'user' ? '我' : '智能体' }}</span>
            <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
          </div>

          <!-- 思考面板 -->
          <div v-if="msg.thinking" class="thinking-panel" :class="{ expanded: expandedThinking[idx] }">
            <div class="thinking-header" @click="toggleThinking(idx)">
              <i class="fa-solid fa-brain"></i>
              <span>思考过程</span>
              <i class="fa-solid thinking-arrow" :class="expandedThinking[idx] ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
            </div>
            <div v-if="expandedThinking[idx]" class="thinking-body">{{ msg.thinking }}</div>
          </div>

          <!-- 步骤面板 -->
          <div v-if="msg.steps && msg.steps.length" class="steps-panel">
            <div
              v-for="(step, si) in msg.steps"
              :key="si"
              class="step-item"
              :class="`step-${step.status || 'pending'}`"
            >
              <i class="fa-solid" :class="stepIcons[step.status] || 'fa-clock'"></i>
              <div class="step-info">
                <span class="step-name">{{ step.name || step.step_id }}</span>
                <span class="step-desc">{{ step.description || '' }}</span>
              </div>
            </div>
          </div>

          <!-- 文本内容（Markdown渲染） -->
          <div class="message-text" v-html="renderMarkdown(msg.content)"></div>

          <!-- 地图链接（支持完整数据或 map_id 引用两种形态） -->
          <div
            v-if="msg.map_data || msg.map_id"
            class="message-map-link"
            @click="handleMapClick(msg)"
          >
            <i class="fa-solid fa-map"></i>
            <span>查看地图: {{ msg.map_data?.name || msg.map_summary?.name || '地图' }}</span>
            <i class="fa-solid fa-arrow-right"></i>
          </div>

          <!-- 质量报告 -->
          <QualityReport
            v-if="msg.quality"
            :quality="msg.quality"
            @optimize="handleOptimize(msg)"
            @accept="handleAccept(msg)"
          />

          <!-- 知识来源卡片 -->
          <div
            v-if="msg.knowledge_sources && (msg.knowledge_sources.rag?.length || msg.knowledge_sources.graphrag?.entities?.length)"
            class="knowledge-sources-card"
          >
            <div class="ks-header"><i class="fa-solid fa-book-open"></i> <span>知识来源</span></div>
            <div v-if="msg.knowledge_sources.rag?.length" class="ks-section">
              <div class="ks-section-title">RAG检索</div>
              <div v-for="(item, ri) in msg.knowledge_sources.rag" :key="ri" class="ks-item ks-rag">
                <span class="ks-badge">RAG</span>
                <span class="ks-title">{{ item.title }}</span>
                <span v-if="item.score" class="ks-score">{{ (item.score * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div v-if="msg.knowledge_sources.graphrag?.entities?.length" class="ks-section">
              <div class="ks-section-title">GraphRAG实体</div>
              <span v-for="(e, ei) in msg.knowledge_sources.graphrag.entities" :key="ei" class="ks-tag ks-graphrag">{{ e }}</span>
            </div>
          </div>

          <!-- GeoToken 数据规模卡片 -->
          <div v-if="msg.geotoken_info" class="geotoken-card">
            <div class="ks-header">
              <i class="fa-solid fa-layer-group"></i>
              <span>数据规模</span>
            </div>
            <div class="geotoken-stats">
              <div class="geotoken-stat">
                <span class="geotoken-num">{{ msg.geotoken_info.layer_count }}</span>
                <span class="geotoken-label">图层</span>
              </div>
              <div class="geotoken-stat">
                <span class="geotoken-num">{{ msg.geotoken_info.total_elements }}</span>
                <span class="geotoken-label">要素</span>
              </div>
              <div v-if="msg.geotoken_info.total_area_km2" class="geotoken-stat">
                <span class="geotoken-num">{{ msg.geotoken_info.total_area_km2.toFixed(1) }}</span>
                <span class="geotoken-label">km²</span>
              </div>
            </div>
            <div v-if="msg.geotoken_info.layer_details && msg.geotoken_info.layer_details.length" class="geotoken-details">
              <div
                v-for="(d, di) in msg.geotoken_info.layer_details"
                :key="di"
                class="geotoken-detail"
              >
                <span class="geotoken-detail-name">{{ d.name }}</span>
                <span class="geotoken-detail-meta">{{ d.type }} · {{ d.element_count }} 要素</span>
              </div>
            </div>
          </div>

          <!-- 模型信息 -->
          <div v-if="msg.provider" class="message-footer">
            <span class="message-model">
              <i class="fa-solid fa-microchip"></i>
              {{ msg.provider }}{{ msg.model ? ' / ' + msg.model : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 流式打字指示器 -->
      <div v-if="chatStore.isSending" class="message message-assistant">
        <div class="message-avatar">
          <i class="fa-solid fa-robot"></i>
        </div>
        <div class="message-body">
          <div class="message-meta">
            <span class="message-role">智能体</span>
          </div>
          <div class="streaming-content">
            <div v-if="chatStore.streamingThinking" class="thinking-panel expanded">
              <div class="thinking-header">
                <i class="fa-solid fa-brain"></i>
                <span>思考过程</span>
              </div>
              <div class="thinking-body">{{ chatStore.streamingThinking }}</div>
            </div>
            <div v-if="chatStore.streamingText" class="message-text" v-html="renderMarkdown(chatStore.streamingText) + '<span class=&quot;streaming-cursor&quot;></span>'"></div>
            <div v-if="!chatStore.streamingText && !chatStore.streamingThinking" class="typing-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入区 -->
    <div class="chat-input-area">
      <div class="chat-input-wrapper">
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="chat-input"
          placeholder="描述你想要的地图效果，我来帮你生成"
          rows="1"
          :maxlength="maxMsgLen"
          @keydown="handleKeydown"
          @input="autoResize"
        ></textarea>
        <button
          class="chat-send-btn"
          :disabled="chatStore.isSending"
          @click="sendMessage"
          title="发送 (Enter)"
        >
          <div v-if="chatStore.isSending" class="btn-spinner"></div>
          <i v-else class="fa-solid fa-paper-plane"></i>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted, reactive } from 'vue'
import { useMapStore } from '@/stores/mapStore'
import { useChatStore } from '@/stores/chatStore'
import { CONFIG } from '@/config'
import api from '@/services/api'
import QualityReport from './QualityReport.vue'
import type { Message } from '@/types'

const chatStore = useChatStore()
const mapStore = useMapStore()

const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const messageListRef = ref<HTMLDivElement | null>(null)
const quickCommandsCollapsed = ref(false)
const showTaskParams = ref(false)
const showMapStats = ref(false)
const maxMsgLen = CONFIG.maxMessageLength
const expandedThinking = reactive<Record<number, boolean>>({})

const quickCommands = CONFIG.quickCommands

// 地图统计数据
const mapStats = reactive({
  // 图层统计
  totalLayers: 0,
  totalFeatures: 0,
  pointLayers: 0,
  lineLayers: 0,
  polygonLayers: 0,
  // 要素统计
  pointFeatures: 0,
  lineFeatures: 0,
  polygonFeatures: 0,
  // 空间信息
  center: '',
  projection: 'Web墨卡托',
  zoom: '',
  bounds: '',
  // 数据来源
  baseMap: '高德地图',
  dataSource: 'OSM / 本地数据',
  createTime: '',
})

// 任务参数（制图要求）
const taskParams = reactive({
  // 基本信息
  mapName: '',
  mapType: '',
  // 空间参数
  region: '',
  projection: 'Web墨卡托',
  scale: '1:100000',
  // 样式参数
  baseMap: '高德地图',
  colorScheme: '默认',
  opacityValue: 100,
  // 内容要求
  includePoints: true,
  includeLines: true,
  includePolygons: true,
  showLabels: true,
  showLegend: true,
})

function refreshMapStats() {
  // 从地图获取最新统计数据
  window.dispatchEvent(new CustomEvent('map-get-stats'))
}

function resetTaskParams() {
  taskParams.mapName = ''
  taskParams.mapType = ''
  taskParams.region = ''
  taskParams.projection = 'Web墨卡托'
  taskParams.scale = '1:100000'
  taskParams.baseMap = '高德地图'
  taskParams.colorScheme = '默认'
  taskParams.opacityValue = 100
  taskParams.includePoints = true
  taskParams.includeLines = true
  taskParams.includePolygons = true
  taskParams.showLabels = true
  taskParams.showLegend = true
}

function applyTaskParams() {
  // 应用任务参数到地图
  window.dispatchEvent(new CustomEvent('map-apply-task-params', { detail: { ...taskParams } }))
  showTaskParams.value = false
}

const stepIcons: Record<string, string> = {
  pending: 'fa-clock',
  running: 'fa-spinner fa-spin',
  success: 'fa-circle-check',
  failed: 'fa-circle-xmark',
}

function toggleThinking(idx: number) {
  expandedThinking[idx] = !expandedThinking[idx]
}

function formatTime(timestamp?: number): string {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function escapeHtml(text: string): string {
  if (text === null || text === undefined) return ''
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = escapeHtml(text)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/`(.+?)`/g, '<code>$1</code>')
  html = html.replace(/```([\s\S]+?)```/g, '<pre><code>$1</code></pre>')
  html = html.replace(/\n/g, '<br>')
  return html
}

function autoResize() {
  const textarea = inputRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || chatStore.isSending) return
  if (text.length > maxMsgLen) return

  inputText.value = ''
  autoResize()
  await chatStore.sendMessage(text)
  scrollToBottom()
}

function handleQuickCommand(cmd: { message: string }) {
  inputText.value = cmd.message
  autoResize()
  sendMessage()
}

async function handleMapClick(msg: Message) {
  if (msg.map_data) {
    mapStore.setMapData(msg.map_data)
    return
  }
  if (msg.map_id) {
    try {
      const res = await api.getMap(msg.map_id)
      if (res.success && res.data) {
        mapStore.setMapData(res.data)
      }
    } catch (e) {
      console.error('加载地图失败', e)
    }
  }
}

function handleOptimize(msg: Message) {
  // 触发优化操作
  const input = inputRef.value
  if (input) {
    inputText.value = '请根据质量报告优化这张地图'
    autoResize()
    input.focus()
  }
}

function handleAccept(msg: Message) {
  // 接受当前结果
  console.log('接受当前结果:', msg)
}

function scrollToBottom() {
  nextTick(() => {
    const el = messageListRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

watch(() => chatStore.streamingText, () => {
  scrollToBottom()
})

// 生成地图后自动渲染到中央地图区域
watch(
  () => chatStore.streamingMap,
  (data) => {
    if (data) {
      mapStore.setMapData(data)
    }
  }
)
</script>

<style scoped>
.chat-panel {
  width: var(--chat-width);
  min-width: var(--chat-width);
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
  position: relative;
  z-index: 10;
}

/* 快捷指令 */
.quick-commands {
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #0ea5e908 0%, #06b6d408 100%);
}
.quick-commands-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-param-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.15s;
}

.task-param-btn:hover {
  background: var(--color-primary-100);
  color: var(--color-primary);
}

.task-param-btn.active {
  background: var(--color-primary);
  color: #fff;
}

.collapse-icon {
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: transform 0.2s;
}

/* 地图统计数据面板 */
.map-stats-panel {
  padding: 12px 14px;
  background: var(--color-primary-50);
  border-bottom: 1px solid var(--color-border-light);
  max-height: 35vh;
  overflow-y: auto;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.stats-section {
  margin-bottom: 14px;
}

.stats-section:last-child {
  margin-bottom: 0;
}

.stats-section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border-light);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 8px;
}

.stats-grid.three-col {
  grid-template-columns: repeat(3, 1fr);
  margin-bottom: 0;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 6px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--color-border-light);
  transition: all 0.15s;
}

.stat-card:hover {
  border-color: var(--color-primary-light);
  box-shadow: 0 2px 8px rgba(167, 139, 250, 0.1);
}

.stat-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
  line-height: 1.2;
}

.stat-card.point .stat-num {
  color: #f59e0b;
}

.stat-card.line .stat-num {
  color: #3b82f6;
}

.stat-card.polygon .stat-num {
  color: #10b981;
}

.stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
  font-size: 12px;
}

.stat-row-label {
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.stat-row-value {
  color: var(--color-text);
  font-weight: 500;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
}

.stats-actions {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}

.stats-refresh-btn {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
}

.stats-refresh-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: var(--color-primary-50);
}

/* 任务参数面板 */
.task-params-panel {
  padding: 12px 14px;
  background: var(--color-primary-50);
  border-bottom: 1px solid var(--color-border-light);
  max-height: 35vh;
  overflow-y: auto;
}

.param-section {
  margin-bottom: 14px;
}

.param-section:last-child {
  margin-bottom: 0;
}

.param-section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border-light);
}

.param-edit-item {
  margin-bottom: 10px;
}

.param-edit-item:last-child {
  margin-bottom: 0;
}

.param-edit-label {
  display: block;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.param-edit-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
  color: var(--color-text);
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.param-edit-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.1);
}

.param-edit-select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
  color: var(--color-text);
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.param-edit-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.1);
}

.param-slider-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.param-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  transition: transform 0.15s;
}

.param-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.param-slider-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
  min-width: 36px;
  text-align: right;
}

.param-check-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.param-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text);
  cursor: pointer;
}

.param-check input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.param-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}

.param-action-btn {
  flex: 1;
  padding: 7px 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.15s;
}

.param-action-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: var(--color-primary-50);
}

.param-action-btn.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.param-action-btn.primary:hover {
  background: var(--color-primary-dark);
  border-color: var(--color-primary-dark);
  color: #fff;
}

.quick-commands-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 10px;
}
.quick-command-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.12) 0%, rgba(139, 92, 246, 0.08) 100%);
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 18px;
  font-size: 12px;
  color: var(--color-primary);
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}
/* 按钮装饰 - 顶部高光 */
.quick-command-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.35), transparent);
  border-radius: 18px 18px 0 0;
  pointer-events: none;
}
.quick-command-btn:hover {
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.2) 0%, rgba(139, 92, 246, 0.15) 100%);
  border-color: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.2);
}

/* 消息列表 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-welcome {
  text-align: center;
  padding: 40px 20px;
  position: relative;
}
.chat-welcome-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a78bfa, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 28px;
  position: relative;
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
}
/* 欢迎图标装饰 - 外圈光晕 */
.chat-welcome-icon::before {
  content: '';
  position: absolute;
  top: -8px;
  left: -8px;
  right: -8px;
  bottom: -8px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.18) 0%, transparent 70%);
  z-index: -1;
}
/* 欢迎图标装饰 - 旋转线条 */
.chat-welcome-icon::after {
  content: '';
  position: absolute;
  top: -12px;
  left: -12px;
  right: -12px;
  bottom: -12px;
  border-radius: 50%;
  border: 2px dashed rgba(139, 92, 246, 0.25);
  animation: rotate 20s linear infinite;
  z-index: -1;
}
@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.chat-welcome-title {
  font-size: 18px;
  color: var(--color-text);
  margin-bottom: 8px;
  font-weight: 600;
}
.chat-welcome-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* 消息气泡 */
.message {
  display: flex;
  gap: 10px;
  max-width: 100%;
}
.message-user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.message-assistant .message-avatar {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #4f46e5;
}
.message-user .message-avatar {
  background: linear-gradient(135deg, #a78bfa, #8b5cf6);
  color: #fff;
}

.message-body {
  max-width: calc(100% - 42px);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-user .message-body {
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.message-role {
  font-weight: 600;
}

.message-text {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
.message-assistant .message-text {
  background: #f1f5f9;
  color: var(--color-text);
  border-top-left-radius: 2px;
}
.message-user .message-text {
  background: linear-gradient(135deg, #a78bfa, #8b5cf6);
  color: #fff;
  border-top-right-radius: 2px;
}

.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  margin: 4px 0;
}

/* 思考面板 */
.thinking-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-secondary);
  background: #f8fafc;
  user-select: none;
}
.thinking-body {
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  background: #fafafa;
  max-height: 200px;
  overflow-y: auto;
}

/* 步骤面板 */
.steps-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: #f8fafc;
  border-left: 3px solid var(--color-border);
}
.step-success {
  border-left-color: var(--color-success);
}
.step-running {
  border-left-color: var(--color-warning);
}
.step-failed {
  border-left-color: var(--color-error);
}
.step-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.step-name {
  font-weight: 600;
  color: var(--color-text);
}
.step-desc {
  color: var(--color-text-secondary);
  font-size: 11px;
}

/* 地图链接 */
.message-map-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: #2563eb;
  cursor: pointer;
  transition: all 0.2s;
}
.message-map-link:hover {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
}

/* 知识来源卡片 */
.knowledge-sources-card {
  background: #f8fafc;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: 12px;
}
.ks-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 8px;
}
.ks-section {
  margin-top: 6px;
}
.ks-section-title {
  color: var(--color-text-secondary);
  font-size: 11px;
  margin-bottom: 4px;
}
.ks-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
}
.ks-badge {
  background: #dbeafe;
  color: #2563eb;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}
.ks-title {
  color: var(--color-text);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ks-score {
  color: var(--color-text-secondary);
  font-size: 11px;
}
.ks-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 10px;
  font-size: 11px;
  margin: 2px 4px 2px 0;
}

/* GeoToken 卡片 */
.geotoken-card {
  background: #f8fafc;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: 12px;
}

.geotoken-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.geotoken-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.geotoken-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
}

.geotoken-label {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.geotoken-details {
  display: flex;
  flex-direction: column;
  gap: 3px;
  border-top: 1px dashed var(--color-border);
  padding-top: 6px;
}

.geotoken-detail {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}

.geotoken-detail-name {
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.geotoken-detail-meta {
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

/* 模型信息 */
.message-footer {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.message-model {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: #f1f5f9;
  border-radius: var(--radius-md);
  border-top-left-radius: 2px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary-light);
  animation: bounce 1.4s infinite ease-in-out both;
}
.dot:nth-child(1) {
  animation-delay: -0.32s;
}
.dot:nth-child(2) {
  animation-delay: -0.16s;
}
@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
  }
  40% {
    transform: scale(1);
  }
}

/* 流式光标 */
:deep(.streaming-cursor) {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.8s infinite;
}
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

/* 输入区 */
.chat-input-area {
  padding: 10px 12px;
  border-top: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
}
.chat-input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  transition: border-color 0.2s;
}
.chat-input-wrapper:focus-within {
  border-color: var(--color-primary-light);
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
}
.chat-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  max-height: 120px;
  font-family: inherit;
  color: var(--color-text);
}
.chat-input::placeholder {
  color: var(--color-text-secondary);
}
.chat-send-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: linear-gradient(135deg, #a78bfa, #8b5cf6);
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
}
.chat-send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
