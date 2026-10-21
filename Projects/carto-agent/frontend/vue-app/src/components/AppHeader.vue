<template>
  <header class="app-header">
    <div class="header-left">
      <div class="header-logo">
        <i class="fa-solid fa-map-location-dot"></i>
      </div>
      <span class="header-title">地图制图智能体</span>
      <span class="header-subtitle">CartoAgent</span>
    </div>

    <div class="header-center">
      <div class="llm-status">
        <span
          class="status-dot"
          :class="{
            online: appStore.currentProvider,
            offline: !appStore.currentProvider,
          }"
        ></span>
        <span class="status-text">
          {{ statusText }}
        </span>
      </div>
    </div>

    <div class="header-right">
      <button 
        class="header-btn editor-toggle-btn" 
        :title="appStore.currentView === 'main' ? '进入地图编辑模式' : '返回主界面'"
        @click="appStore.toggleView()"
      >
        <i class="fa-solid fa-pen-ruler"></i>
        <span>{{ appStore.currentView === 'main' ? '地图编辑' : '返回' }}</span>
      </button>
      <button class="header-icon-btn" title="新会话" @click="handleNewSession">
        <i class="fa-solid fa-plus"></i>
      </button>
      <button class="header-icon-btn" title="历史记录" @click="appStore.toggleSessionDrawer()">
        <i class="fa-solid fa-clock-rotate-left"></i>
      </button>
      <button class="header-icon-btn" title="下载地图" @click="handleDownload">
        <i class="fa-solid fa-download"></i>
      </button>
      <div class="header-divider"></div>
      <!-- 底图切换 -->
      <div class="header-dropdown" @click.stop>
        <button class="header-icon-btn" title="底图主题" @click="showThemeMenu = !showThemeMenu">
          <i class="fa-solid fa-palette"></i>
        </button>
        <div v-if="showThemeMenu" class="header-dropdown-menu theme-menu">
          <div
            v-for="(theme, key) in mapThemes"
            :key="key"
            class="header-dropdown-item"
            :class="{ active: mapStore.currentTheme === key }"
            @click="setTheme(key)"
          >
            <span class="theme-preview" :style="{ background: getThemePreviewColor(key) }"></span>
            <span>{{ theme.name }}</span>
            <i v-if="mapStore.currentTheme === key" class="fa-solid fa-check check-icon"></i>
          </div>
        </div>
      </div>
      <button 
        class="header-icon-btn" 
        :class="{ active: appStore.showLayerPanel }" 
        title="图层面板" 
        @click="appStore.toggleLayerPanel()"
      >
        <i class="fa-solid fa-layer-group"></i>
      </button>
      <button 
        class="header-icon-btn" 
        :class="{ active: appStore.showChatPanel }" 
        title="AI助手" 
        @click="appStore.toggleChatPanel()"
      >
        <i class="fa-solid fa-comments"></i>
      </button>
      <button 
        class="header-icon-btn" 
        :class="{ active: appStore.showKGPanel }" 
        title="知识图谱" 
        @click="appStore.toggleKGPanel()"
      >
        <i class="fa-solid fa-diagram-project"></i>
      </button>
      <button class="header-icon-btn" title="设置" @click="appStore.toggleSettings()">
        <i class="fa-solid fa-gear"></i>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'
import { useMapStore } from '@/stores/mapStore'
import { CONFIG } from '@/config'

const appStore = useAppStore()
const chatStore = useChatStore()
const mapStore = useMapStore()

const showThemeMenu = ref(false)

const mapThemes = computed(() => CONFIG.mapThemes)

function setTheme(theme: string) {
  mapStore.setTheme(theme)
  showThemeMenu.value = false
}

function getThemePreviewColor(key: string): string {
  const colorMap: Record<string, string> = {
    standard: '#7eb5d6',
    positron: '#f5f5f5',
    dark: '#263238',
    satellite: '#3a5a3a',
    plain: '#FAF8F3',
    amap_normal: '#e8f4de',
    amap_satellite: '#4a6741',
    tianditu_vec: '#f0e6d2',
    tianditu_img: '#5a7a5a',
    tencent_normal: '#e0f0ff',
    esri_street_cn: '#f5f0e6',
  }
  return colorMap[key] || '#ccc'
}

const statusText = computed(() => {
  const displayNames: Record<string, string> = {
    deepseek: 'DeepSeek',
    qwen: '通义千问',
    openai: 'OpenAI',
    zhipu: '智谱GLM',
    ollama: 'Ollama',
    moonshot: 'Kimi',
    baidu: '文心一言',
  }
  // 默认显示DeepSeek（后端已配置）
  const provider = appStore.currentProvider || 'deepseek'
  const model = appStore.currentModel || 'deepseek-chat'
  const name = displayNames[provider] || provider
  let text = name
  if (model) text += ` / ${model}`
  return text
})

async function handleNewSession() {
  await chatStore.createSession()
}

function handleDownload() {
  window.dispatchEvent(new CustomEvent('map-open-export'))
}
</script>

<style scoped>
.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  /* 紫罗兰淡紫色渐变 - 整体偏浅色 */
  background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 50%, #7c3aed 100%);
  color: #fff;
  position: relative;
  z-index: 100;
  box-shadow: 0 2px 12px rgba(139, 92, 246, 0.3);
  overflow: hidden;
}

.app-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    /* 装饰性光晕 */
    radial-gradient(circle at 20% 50%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.1) 0%, transparent 40%),
    /* 细线条装饰 - 斜向条纹 */
    repeating-linear-gradient(
      -45deg,
      transparent,
      transparent 20px,
      rgba(255, 255, 255, 0.04) 20px,
      rgba(255, 255, 255, 0.04) 21px
    ),
    /* 点阵装饰 */
    radial-gradient(circle at 10px 10px, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 100% 100%, 100% 100%, 100% 100%, 20px 20px;
  pointer-events: none;
}

/* 底部装饰线条 */
.app-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(255, 255, 255, 0.35) 20%, 
    rgba(255, 255, 255, 0.55) 50%, 
    rgba(255, 255, 255, 0.35) 80%, 
    transparent 100%);
  pointer-events: none;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  backdrop-filter: blur(4px);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.header-subtitle {
  font-size: 11px;
  opacity: 0.7;
  font-weight: 400;
  letter-spacing: 1px;
  padding: 2px 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
}

.header-center {
  display: flex;
  align-items: center;
}

.llm-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 20px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}
.status-dot.loading {
  background: #fbbf24;
  animation: pulse 1.5s infinite;
}
.status-dot.online {
  background: #4ade80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
}
.status-dot.offline {
  background: #ef4444;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.status-text {
  font-size: 12px;
  opacity: 0.9;
}

.header-right {
  display: flex;
  gap: 4px;
}

.header-icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}
.header-icon-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: translateY(-1px);
}

.header-icon-btn.active {
  background: rgba(255, 255, 255, 0.3);
  color: #fff;
}

.header-divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  margin: 0 8px;
}

.header-dropdown {
  position: relative;
}

.header-dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 6px;
  min-width: 160px;
  z-index: 1000;
}

.header-dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text);
  transition: background 0.15s;
}

.header-dropdown-item:hover {
  background: var(--color-bg);
}

.header-dropdown-item.active {
  background: rgba(167, 139, 250, 0.1);
  color: var(--color-primary);
}

.theme-preview {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid var(--color-border);
  flex-shrink: 0;
}

.check-icon {
  margin-left: auto;
  font-size: 12px;
}

.editor-toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  height: 36px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  margin-right: 8px;
}

.editor-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: translateY(-1px);
}
</style>
