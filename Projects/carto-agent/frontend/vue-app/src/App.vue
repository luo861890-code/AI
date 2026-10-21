<template>
  <div class="app-root">
    <!-- 主界面 -->
    <template v-if="appStore.currentView === 'main'">
      <AppHeader />
      <div class="app-body">
        <Toolbar class="left-toolbar" v-show="appStore.showLayerPanel" />
        <LayerPanel v-show="appStore.showLayerPanel" />
        <div class="map-area">
          <LegacyMapPanel />
        </div>
        <ChatPanel v-show="appStore.showChatPanel" />
        <KGPanel v-show="appStore.showKGPanel" />
      </div>

      <StylePanel />
      <SettingsModal v-if="appStore.showSettings" />
      <SessionDrawer v-if="appStore.showSessionDrawer" />
      <AttributeTable v-if="appStore.showAttributeTable" />
      <MetadataModal v-if="appStore.showMetadataModal" />
      <ImportModal v-if="appStore.showImportModal" />
    </template>

    <!-- QGIS编辑界面 -->
    <template v-else>
      <QgisEditor />
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import LayerPanel from '@/components/LayerPanel.vue'
import LegacyMapPanel from '@/components/LegacyMapPanel.vue'
import Toolbar from '@/components/Toolbar.vue'
import KGPanel from '@/components/KGPanel.vue'
import StylePanel from '@/components/StylePanel.vue'
import SettingsModal from '@/components/SettingsModal.vue'
import SessionDrawer from '@/components/SessionDrawer.vue'
import QgisEditor from '@/components/QgisEditor.vue'
import AttributeTable from '@/components/AttributeTable.vue'
import MetadataModal from '@/components/MetadataModal.vue'
import ImportModal from '@/components/ImportModal.vue'
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'
import api from '@/services/api'

const appStore = useAppStore()
const chatStore = useChatStore()

onMounted(async () => {
  await appStore.loadLLMStatus(api)
  await chatStore.loadSessions()
})
</script>

<style>
:root {
  --header-height: 56px;
  --chat-width: 360px;
  --layer-panel-width: 280px;
  --toolbar-width: 56px;
  /* 紫罗兰淡紫色调 - 整体偏浅色，透明度合理下调 */
  --color-primary: #a78bfa;
  --color-primary-dark: #8b5cf6;
  --color-primary-light: #c4b5fd;
  --color-primary-50: #f5f3ff;
  --color-primary-100: #ede9fe;
  --color-primary-200: #ddd6fe;
  --color-primary-300: #c4b5fd;
  --color-accent: #8b5cf6;
  --color-accent-light: #a78bfa;
  --color-bg: #fafafa;
  --color-bg-gradient: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 30%, #fdf4ff 70%, #fff7ed 100%);
  --color-surface: #ffffff;
  --color-surface-hover: #fafafa;
  --color-border: #e5e7eb;
  --color-border-light: #f3f4f6;
  --color-text: #1f2937;
  --color-text-secondary: #6b7280;
  --color-text-tertiary: #9ca3af;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --shadow-sm: 0 1px 3px rgba(139, 92, 246, 0.12);
  --shadow-md: 0 4px 12px -2px rgba(139, 92, 246, 0.15);
  --shadow-lg: 0 10px 30px -5px rgba(139, 92, 246, 0.18);
  --shadow-glow: 0 0 20px rgba(139, 92, 246, 0.18);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  background: var(--color-bg-gradient);
  color: var(--color-text);
  overflow: hidden;
}

.app-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-gradient);
  position: relative;
}

.app-body {
  display: flex;
  flex-direction: row;
  height: calc(100vh - var(--header-height));
  position: relative;
  overflow: hidden;
}

.left-toolbar {
  width: 46px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.map-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}
</style>

<style>
:root {
  --header-height: 56px;
  --chat-width: 360px;
  --layer-panel-width: 280px;
  --toolbar-width: 56px;
  /* 紫罗兰淡紫色调 - 整体偏浅色，透明度合理下调 */
  --color-primary: #a78bfa;
  --color-primary-dark: #8b5cf6;
  --color-primary-light: #c4b5fd;
  --color-primary-50: #f5f3ff;
  --color-primary-100: #ede9fe;
  --color-primary-200: #ddd6fe;
  --color-primary-300: #c4b5fd;
  --color-accent: #8b5cf6;
  --color-accent-light: #a78bfa;
  --color-bg: #fafafa;
  --color-bg-gradient: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 30%, #fdf4ff 70%, #fff7ed 100%);
  --color-surface: #ffffff;
  --color-surface-hover: #fafafa;
  --color-border: #e5e7eb;
  --color-border-light: #f3f4f6;
  --color-text: #1f2937;
  --color-text-secondary: #6b7280;
  --color-text-tertiary: #9ca3af;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --shadow-sm: 0 1px 3px rgba(139, 92, 246, 0.12);
  --shadow-md: 0 4px 12px -2px rgba(139, 92, 246, 0.15);
  --shadow-lg: 0 10px 30px -5px rgba(139, 92, 246, 0.18);
  --shadow-glow: 0 0 20px rgba(139, 92, 246, 0.18);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  background: var(--color-bg-gradient);
  color: var(--color-text);
  overflow: hidden;
}

.app-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-gradient);
  position: relative;
}

.app-body {
  display: flex;
  flex-direction: row;
  height: calc(100vh - var(--header-height));
  position: relative;
  overflow: hidden;
}

.left-toolbar {
  width: 46px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.map-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}
</style>
