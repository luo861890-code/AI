<template>
  <Teleport to="body">
    <div class="drawer-overlay" @click="handleClose"></div>
    <div class="session-drawer">
      <div class="drawer-header">
        <span><i class="fa-solid fa-clock-rotate-left"></i> 历史会话</span>
        <button class="drawer-close-btn" @click="handleClose">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="drawer-body">
        <button class="new-session-btn" @click="handleNewSession">
          <i class="fa-solid fa-plus"></i> 新建会话
        </button>
        <div v-if="chatStore.sessions.length === 0" class="empty-hint">暂无会话</div>
        <div
          v-for="session in chatStore.sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: session.session_id === chatStore.currentSessionId }"
        >
          <div class="session-item-content" @click="handleSwitch(session.session_id)">
            <i class="fa-solid fa-comments session-icon"></i>
            <div class="session-info">
              <span class="session-title">{{ session.title }}</span>
              <span v-if="session.created_at" class="session-time">{{ formatTime(session.created_at) }}</span>
            </div>
          </div>
          <button class="session-delete-btn" @click="handleDelete(session.session_id)" title="删除会话">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'

const appStore = useAppStore()
const chatStore = useChatStore()

function handleClose() {
  appStore.showSessionDrawer = false
}

async function handleNewSession() {
  await chatStore.createSession()
  handleClose()
}

async function handleSwitch(sessionId: string) {
  await chatStore.switchSession(sessionId)
  handleClose()
}

async function handleDelete(sessionId: string) {
  if (!confirm('确定要删除这个会话吗？')) return
  await chatStore.deleteCurrentSession(sessionId)
}

function formatTime(timestamp: number): string {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 500;
}
.session-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 320px;
  height: 100vh;
  background: var(--color-surface);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.1);
  z-index: 501;
  display: flex;
  flex-direction: column;
  animation: slideInRight 0.25s ease-out;
}
@keyframes slideInRight {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--color-border);
  font-weight: 600;
  font-size: 15px;
  color: var(--color-primary);
}
.drawer-close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  transition: all 0.2s;
}
.drawer-close-btn:hover {
  background: var(--color-bg);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.new-session-btn {
  width: 100%;
  padding: 10px;
  border: 2px dashed var(--color-border);
  background: transparent;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-bottom: 10px;
  transition: all 0.2s;
}
.new-session-btn:hover {
  border-color: var(--color-primary);
  background: rgba(124, 58, 237, 0.04);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
  padding: 30px 0;
}

.session-item {
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: all 0.15s;
  margin-bottom: 4px;
}
.session-item:hover {
  background: var(--color-bg);
}
.session-item.active {
  background: rgba(124, 58, 237, 0.08);
}
.session-item-content {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  min-width: 0;
}
.session-icon {
  color: var(--color-text-secondary);
  font-size: 14px;
  flex-shrink: 0;
}
.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.session-title {
  font-size: 13px;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-time {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.session-delete-btn {
  padding: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  opacity: 0;
  transition: all 0.2s;
}
.session-item:hover .session-delete-btn {
  opacity: 1;
}
.session-delete-btn:hover {
  color: var(--color-error);
  background: rgba(239, 68, 68, 0.08);
}
</style>
