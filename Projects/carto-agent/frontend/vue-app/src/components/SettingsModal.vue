<template>
  <Teleport to="body">
    <div class="modal-overlay" @click="handleClose"></div>
    <div class="modal-dialog">
      <div class="modal-header">
        <span class="modal-title">
          <i class="fa-solid fa-gear"></i> 系统设置
        </span>
        <button class="modal-close-btn" @click="handleClose">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="modal-body">
        <!-- LLM设置 -->
        <div class="settings-section">
          <div class="settings-section-title">大语言模型</div>
          <div class="settings-field">
            <label>LLM提供者</label>
            <select v-model="selectedProvider" class="settings-select" @change="onProviderChange">
              <option v-for="p in providersList" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="settings-field">
            <label>模型</label>
            <select v-model="selectedModel" class="settings-select">
              <option v-for="m in currentModels" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
        </div>

        <!-- API Key管理 -->
        <div class="settings-section">
          <div class="settings-section-title">
            <i class="fa-solid fa-key"></i> API 密钥管理
          </div>
          <div v-for="keyProvider in keyProviders" :key="keyProvider" class="settings-field">
            <label>
              {{ providerNames[keyProvider] }}
              <span class="api-key-status" :class="apiKeyStatus[keyProvider] ? 'configured' : 'not-configured'">
                <i :class="apiKeyStatus[keyProvider] ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'"></i>
                {{ apiKeyStatus[keyProvider] ? '已配置' : '未配置' }}
              </span>
            </label>
            <div class="api-key-input-wrapper">
              <input
                :ref="(el: any) => { apiKeyInputs[keyProvider] = el }"
                type="password"
                class="api-key-input"
                :placeholder="apiKeyStatus[keyProvider] ? '已配置（输入新 Key 可替换）' : `输入 ${providerNames[keyProvider]} API Key...`"
              />
              <button class="api-key-save-btn" @click="saveApiKey(keyProvider)">
                <i class="fa-solid fa-floppy-disk"></i> 保存
              </button>
            </div>
            <div v-if="maskedKeys[keyProvider]" class="field-hint">
              当前已配置：{{ maskedKeys[keyProvider] }}
            </div>
          </div>
        </div>

        <!-- 底图主题 -->
        <div class="settings-section">
          <div class="settings-section-title">地图底图主题</div>
          <div class="settings-themes">
            <button
              v-for="(theme, key) in CONFIG.mapThemes"
              :key="key"
              class="theme-option-btn"
              :class="{ active: key === mapStore.currentTheme }"
              @click="handleThemeChange(key as string)"
            >{{ theme.name }}</button>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" @click="handleClose">取消</button>
        <button class="btn btn-primary" @click="handleSave">
          <i class="fa-solid fa-check"></i> 保存
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'
import { CONFIG } from '@/config'
import type { LLMProvider } from '@/types'

const appStore = useAppStore()
const mapStore = useMapStore()

const keyProviders = ['deepseek', 'qwen', 'openai', 'zhipu', 'ollama', 'moonshot', 'baidu']
const providerNames: Record<string, string> = {
  deepseek: 'DeepSeek',
  qwen: '通义千问',
  openai: 'OpenAI',
  zhipu: '智谱GLM',
  ollama: 'Ollama（本地）',
  moonshot: '月之暗面 Kimi',
  baidu: '百度文心一言',
}

// 预设的常用模型列表
const defaultProviderModels: Record<string, string[]> = {
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  qwen: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1'],
  zhipu: ['glm-4-plus', 'glm-4', 'glm-4-flash', 'glm-4-air'],
  ollama: ['qwen3:8b', 'qwen2.5:7b', 'llama3:8b', 'mistral:7b'],
  moonshot: ['kimi-latest', 'moonshot-v1-8k', 'moonshot-v1-32k'],
  baidu: ['ernie-4.0', 'ernie-4.0-turbo', 'ernie-3.5'],
}

const selectedProvider = ref('deepseek')
const selectedModel = ref('deepseek-chat')
// 初始化为默认的常用选项列表，确保即使API调用失败也能正常显示
const providersList = ref<LLMProvider[]>(
  Object.keys(defaultProviderModels).map((id) => ({
    id,
    name: providerNames[id] || id,
    models: defaultProviderModels[id] || [],
    configured: false,
    active: false,
  })) as LLMProvider[]
)
// 初始化API Key状态，默认都是未配置
const apiKeyStatus = ref<Record<string, boolean>>({
  deepseek: false,
  qwen: false,
  openai: false,
  zhipu: false,
  ollama: false,
  moonshot: false,
  baidu: false,
})
const apiKeyInputs = ref<Record<string, HTMLInputElement | null>>({})
const maskedKeys = ref<Record<string, string>>({})

const currentModels = computed(() => {
  const provider = providersList.value.find((p) => p.id === selectedProvider.value)
  return provider?.models || []
})

async function loadSettingsData() {
  try {
    const data = await api.getProviders()
    const result = data.data || data
    const apiProviders = result.providers || result.available || []
    
    // 转换API返回格式：model（单数）→ models（复数数组）
    let list = apiProviders.map((p: any) => ({
      id: p.id,
      name: p.name,
      configured: p.configured || false,
      active: p.active || false,
      models: p.models?.length
        ? p.models
        : defaultProviderModels[p.id] || (p.model ? [p.model] : []),
    })) as LLMProvider[]
    
    // 如果API返回为空，使用默认的常用选项列表
    if (list.length === 0) {
      list = Object.keys(defaultProviderModels).map((id) => ({
        id,
        name: providerNames[id] || id,
        models: defaultProviderModels[id] || [],
        configured: false,
        active: false,
      })) as LLMProvider[]
    }
    
    // 确保所有常用选项都在列表中（即使API没有返回）
    const existingIds = new Set(list.map((p: any) => p.id))
    Object.keys(defaultProviderModels).forEach((id) => {
      if (!existingIds.has(id)) {
        list.push({
          id,
          name: providerNames[id] || id,
          models: defaultProviderModels[id] || [],
          configured: false,
          active: false,
        } as LLMProvider)
      }
    })
    
    providersList.value = list
    
    // 设置当前选中的提供者
    if (result.current) {
      selectedProvider.value = result.current
    } else if (!selectedProvider.value && list.length > 0) {
      selectedProvider.value = list[0].id
    }
    
    // 设置当前选中的模型
    if (result.current_model) {
      selectedModel.value = result.current_model
    }
    
    // 更新API Key状态
    list.forEach((p) => {
      apiKeyStatus.value[p.id] = p.configured || false
      maskedKeys.value[p.id] = p.masked_key || ''
    })
  } catch (e) {
    console.error('加载设置失败:', e)
  }
}

function onProviderChange() {
  const provider = providersList.value.find((p) => p.id === selectedProvider.value)
  if (provider?.models?.length) {
    selectedModel.value = provider.models[0]
  }
}

function handleThemeChange(key: string) {
  mapStore.setTheme(key)
}

async function saveApiKey(provider: string) {
  const input = apiKeyInputs.value[provider]
  if (!input || !input.value.trim()) {
    alert('请输入API Key')
    return
  }
  try {
    await api.updateApiKey(provider, input.value.trim())
    apiKeyStatus.value[provider] = true
    input.value = ''
    alert('API Key 已保存')
  } catch (e: any) {
    alert('保存失败: ' + e.message)
  }
}

async function handleSave() {
  try {
    await api.switchProvider(selectedProvider.value, selectedModel.value)
    appStore.currentProvider = selectedProvider.value
    appStore.currentModel = selectedModel.value
    appStore.showSettings = false
  } catch (e: any) {
    alert('保存设置失败: ' + e.message)
  }
}

function handleClose() {
  appStore.showSettings = false
}

onMounted(() => {
  selectedProvider.value = appStore.currentProvider
  selectedModel.value = appStore.currentModel
  loadSettingsData()
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.modal-dialog {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 520px;
  max-height: 85vh;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 1001;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}
.modal-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-primary);
}
.modal-close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--color-text-secondary);
  transition: all 0.2s;
}
.modal-close-btn:hover {
  background: var(--color-bg);
  color: var(--color-text);
}
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--color-border);
}

.settings-section {
  margin-bottom: 20px;
}
.settings-section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--color-text);
}
.settings-field {
  margin-bottom: 12px;
}
.settings-field label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.settings-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  outline: none;
}
.settings-select:focus {
  border-color: var(--color-primary-light);
}

.api-key-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
}
.api-key-status.configured {
  background: #dcfce7;
  color: #15803d;
}
.api-key-status.not-configured {
  background: #fee2e2;
  color: #b91c1c;
}
.api-key-input-wrapper {
  display: flex;
  gap: 6px;
}
.api-key-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
}
.api-key-input:focus {
  border-color: var(--color-primary-light);
}
.api-key-save-btn {
  padding: 8px 14px;
  border: none;
  background: var(--color-primary);
  color: #fff;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.api-key-save-btn:hover {
  background: var(--color-primary-dark);
}

.field-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-success);
}

.settings-themes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.theme-option-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  color: var(--color-text);
  transition: all 0.2s;
}
.theme-option-btn:hover {
  border-color: var(--color-primary-light);
  background: rgba(124, 58, 237, 0.04);
}
.theme-option-btn.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.btn {
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}
.btn-secondary {
  background: var(--color-bg);
  color: var(--color-text);
}
.btn-secondary:hover {
  background: var(--color-border);
}
.btn-primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-primary:hover {
  opacity: 0.9;
}
</style>
