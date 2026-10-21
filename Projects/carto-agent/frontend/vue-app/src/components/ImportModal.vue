<template>
  <Teleport to="body">
    <div class="import-overlay" @click.self="appStore.toggleImportModal()">
      <div class="import-dialog">
        <div class="import-header">
          <span><i class="fa-solid fa-file-import"></i> 导入文档到知识图谱</span>
          <button class="import-close" @click="appStore.toggleImportModal()">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="import-body">
          <div class="import-hint">
            <i class="fa-solid fa-circle-info"></i>
            <span>粘贴文档内容，系统将自动抽取实体与关系并添加到知识图谱中。</span>
          </div>
          <div class="import-field">
            <label>文档内容</label>
            <textarea
              v-model="content"
              class="import-textarea"
              placeholder="在此粘贴文档内容..."
              rows="10"
            ></textarea>
          </div>
          <div class="import-field">
            <label>实体标签（可选，逗号分隔）</label>
            <input v-model="labels" type="text" class="import-input" placeholder="如 City, Landmark, MapType" />
          </div>
          <div v-if="result" class="import-result" :class="{ error: result.error }">
            <template v-if="!result.error">
              <div class="import-result-title">
                <i class="fa-solid fa-circle-check"></i> 导入成功
              </div>
              <div class="import-stats">
                <div class="import-stat">
                  <span class="import-stat-num">{{ result.entities || 0 }}</span>
                  <span class="import-stat-label">实体</span>
                </div>
                <div class="import-stat">
                  <span class="import-stat-num">{{ result.relations || 0 }}</span>
                  <span class="import-stat-label">关系</span>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="import-result-title error">
                <i class="fa-solid fa-circle-xmark"></i> 导入失败
              </div>
              <div class="import-error-msg">{{ result.error }}</div>
            </template>
          </div>
        </div>
        <div class="import-footer">
          <button class="btn secondary" @click="appStore.toggleImportModal()">取消</button>
          <button class="btn primary" :disabled="importing" @click="submit">
            <div v-if="importing" class="btn-spinner"></div>
            <i v-else class="fa-solid fa-upload"></i> 导入
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useKGStore } from '@/stores/kgStore'
import api from '@/services/api'

const appStore = useAppStore()
const kgStore = useKGStore()

const content = ref('')
const labels = ref('')
const importing = ref(false)
const result = ref<{ entities?: number; relations?: number; error?: string } | null>(null)

async function submit() {
  const text = content.value.trim()
  if (!text) {
    alert('请输入文档内容')
    return
  }
  const entityLabels = labels.value
    ? labels.value.split(',').map((s) => s.trim()).filter(Boolean)
    : null

  importing.value = true
  result.value = null
  try {
    const resp = await api.importDocument(text, entityLabels)
    const data = resp.data || resp
    result.value = {
      entities: data?.entities?.length ?? 0,
      relations: data?.relations?.length ?? 0,
    }
    await kgStore.loadGraph()
    setTimeout(() => appStore.toggleImportModal(), 2000)
  } catch (e: any) {
    result.value = { error: e.message || '导入失败' }
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.import-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.import-dialog {
  width: 560px;
  max-height: 85vh;
  background: #fff;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.import-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px 18px;
  border-bottom: 1px solid var(--color-border);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
}

.import-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 50%;
  cursor: pointer;
}

.import-close:hover {
  background: var(--color-bg);
}

.import-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}

.import-hint {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 8px;
  font-size: 12px;
  margin-bottom: 14px;
}

.import-field {
  margin-bottom: 14px;
}

.import-field label {
  display: block;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.import-textarea,
.import-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
  resize: vertical;
}

.import-textarea:focus,
.import-input:focus {
  border-color: var(--color-primary-light);
}

.import-result {
  padding: 12px;
  background: #f0fdf4;
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
}

.import-result.error {
  background: #fef2f2;
  border-color: rgba(239, 68, 68, 0.3);
}

.import-result-title {
  color: #15803d;
  font-weight: 600;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.import-result-title.error {
  color: #b91c1c;
}

.import-stats {
  display: flex;
  gap: 20px;
  margin-top: 10px;
}

.import-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.import-stat-num {
  font-size: 20px;
  font-weight: 700;
  color: #15803d;
}

.import-stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.import-error-msg {
  margin-top: 6px;
  font-size: 12px;
  color: #b91c1c;
}

.import-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 18px;
  border-top: 1px solid var(--color-border);
  background: #fafbfc;
}

.btn {
  padding: 8px 18px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn.secondary {
  background: #f1f5f9;
  color: var(--color-text);
}

.btn.primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.btn:disabled {
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
