/**
 * 全局应用状态管理 (Pinia)
 * 管理面板显示/隐藏、设置面板、当前LLM提供者/模型等全局状态
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '@/services/api'

export const useAppStore = defineStore('app', () => {
  /** 图层面板是否显示（左侧） */
  const showLayerPanel = ref(true)

  /** AI聊天面板是否显示（右侧） */
  const showChatPanel = ref(true)

  /** 知识图谱面板是否显示 */
  const showKGPanel = ref(false)

  /** 样式编辑面板是否显示 */
  const showStylePanel = ref(false)

  /** 空间分析面板是否显示 */
  const showAnalysisPanel = ref(false)

  const analysisMode = ref<'buffer' | 'overlay' | 'nearest' | null>(null)

  /** 设置面板是否显示 */
  const showSettings = ref(false)

  /** 会话抽屉是否显示 */
  const showSessionDrawer = ref(false)

  /** 路径规划面板是否显示 */
  const showRoutePanel = ref(false)

  const showParamsPanel = ref(false)

  const showMetadataModal = ref(false)

  const showImportModal = ref(false)

  const showEditPanel = ref(false)

  const editDrawTool = ref<'point' | 'line' | 'polygon' | null>(null)

  const showLegendPanel = ref(false)

  const showGraticule = ref(false)

  const markerMode = ref(false)

  /** 当前选中的图层ID */
  const selectedLayerId = ref<string | null>(null)

  /** 当前视图模式: 'main' | 'editor' */
  const currentView = ref<'main' | 'editor'>('main')

  /** 属性表面板是否显示 */
  const showAttributeTable = ref(false)

  /** 当前属性表的图层ID */
  const attributeTableLayerId = ref<string | null>(null)

  /** LLM提供者状态 */
  const providerStatus = ref<{
    current_provider?: string
    current_model?: string
    providers?: Array<{ id: string; name: string; models: string[]; configured?: boolean }>
  }>({})

  /** 当前LLM提供者 */
  const currentProvider = ref('deepseek')

  /** 当前LLM模型 */
  const currentModel = ref('deepseek-chat')

  // ========== Actions ==========

  /** 切换图层面板 */
  function toggleLayerPanel() {
    showLayerPanel.value = !showLayerPanel.value
  }

  /** 切换聊天面板 */
  function toggleChatPanel() {
    showChatPanel.value = !showChatPanel.value
    // 互斥：如果聊天面板打开，关闭知识图谱面板
    if (showChatPanel.value) {
      showKGPanel.value = false
    }
  }

  /** 切换知识图谱面板 */
  function toggleKGPanel() {
    showKGPanel.value = !showKGPanel.value
    // 互斥：如果知识图谱面板打开，关闭聊天面板
    if (showKGPanel.value) {
      showChatPanel.value = false
    }
  }

  /** 切换样式面板 */
  function toggleStylePanel() {
    showStylePanel.value = !showStylePanel.value
  }

  /** 切换空间分析面板 */
  function toggleAnalysisPanel() {
    showAnalysisPanel.value = !showAnalysisPanel.value
  }

  function setAnalysisMode(mode: 'buffer' | 'overlay' | 'nearest' | null) {
    analysisMode.value = mode
    if (mode) showAnalysisPanel.value = true
  }

  /** 设置当前选中图层 */
  function setSelectedLayer(layerId: string | null) {
    selectedLayerId.value = layerId
  }

  /** 打开/关闭设置面板 */
  function toggleSettings() {
    showSettings.value = !showSettings.value
  }

  /** 打开/关闭会话抽屉 */
  function toggleSessionDrawer() {
    showSessionDrawer.value = !showSessionDrawer.value
  }

  /** 切换路径规划面板 */
  function toggleRoutePanel() {
    showRoutePanel.value = !showRoutePanel.value
  }

  function toggleParamsPanel() {
    showParamsPanel.value = !showParamsPanel.value
  }

  function toggleMetadataModal() {
    showMetadataModal.value = !showMetadataModal.value
  }

  function toggleImportModal() {
    showImportModal.value = !showImportModal.value
  }

  function toggleEditPanel() {
    showEditPanel.value = !showEditPanel.value
    if (!showEditPanel.value) {
      editDrawTool.value = null
    }
  }

  function setEditDrawTool(tool: 'point' | 'line' | 'polygon' | null) {
    editDrawTool.value = tool
  }

  function toggleLegendPanel() {
    showLegendPanel.value = !showLegendPanel.value
  }

  function toggleGraticule() {
    showGraticule.value = !showGraticule.value
  }

  function toggleMarkerMode() {
    markerMode.value = !markerMode.value
  }

  /** 切换到主界面 */
  function switchToMainView() {
    currentView.value = 'main'
  }

  /** 切换到编辑界面 */
  function switchToEditorView() {
    currentView.value = 'editor'
  }

  /** 切换视图 */
  function toggleView() {
    currentView.value = currentView.value === 'main' ? 'editor' : 'main'
  }

  /** 打开属性表 */
  function openAttributeTable(layerId: string) {
    attributeTableLayerId.value = layerId
    showAttributeTable.value = true
  }

  /** 关闭属性表 */
  function closeAttributeTable() {
    showAttributeTable.value = false
    attributeTableLayerId.value = null
  }

  /** 切换属性表 */
  function toggleAttributeTable() {
    showAttributeTable.value = !showAttributeTable.value
  }

  /** 加载LLM状态（兼容旧接口） */
  async function loadLLMStatus(apiService: any) {
    try {
      const result = await apiService.getProviders()
      const data = result.data || result
      if (data) {
        providerStatus.value = data
        if (data.current) {
          currentProvider.value = data.current
        }
        if (data.current_model) {
          currentModel.value = data.current_model
        }
        // 如果没有current，尝试从providers中找active的
        if (!currentProvider.value && data.providers) {
          const active = data.providers.find((p: any) => p.active)
          if (active) {
            currentProvider.value = active.id
            currentModel.value = active.model || active.models?.[0] || ''
          }
        }
      }
    } catch (error) {
      console.error('加载LLM状态失败:', error)
      // 加载失败时，使用默认值，确保显示正常
      if (!currentProvider.value) {
        currentProvider.value = 'deepseek'
        currentModel.value = 'deepseek-chat'
      }
    }
    
    // 最终兜底：如果还是没有，设置默认值
    if (!currentProvider.value) {
      currentProvider.value = 'deepseek'
      currentModel.value = 'deepseek-chat'
    }
  }

  /** 加载当前提供者/模型 */
  async function loadProviders() {
    try {
      const providers = await api.getProviders()
      if (providers && providers.length > 0) {
        const active = providers.find((p: any) => p.active)
        if (active) {
          currentProvider.value = active.name || ''
          currentModel.value = active.current_model || active.models?.[0]?.name || ''
        }
      }
    } catch (error) {
      console.error('加载提供者信息失败:', error)
    }
  }

  /** 切换提供者 */
  async function switchProvider(provider: string, model: string) {
    try {
      await api.switchProvider(provider, model)
      currentProvider.value = provider
      currentModel.value = model
    } catch (error) {
      console.error('切换提供者失败:', error)
    }
  }

  return {
    // State
    showLayerPanel,
    showChatPanel,
    showKGPanel,
    showStylePanel,
    showAnalysisPanel,
    analysisMode,
    showSettings,
    showSessionDrawer,
    showRoutePanel,
    showParamsPanel,
    showMetadataModal,
    showImportModal,
    showEditPanel,
    editDrawTool,
    showLegendPanel,
    showGraticule,
    markerMode,
    selectedLayerId,
    currentProvider,
    currentModel,
    providerStatus,
    currentView,
    showAttributeTable,
    attributeTableLayerId,
    // Actions
    toggleLayerPanel,
    toggleChatPanel,
    toggleKGPanel,
    toggleStylePanel,
    toggleAnalysisPanel,
    setAnalysisMode,
    toggleSettings,
    toggleSessionDrawer,
    toggleRoutePanel,
    toggleParamsPanel,
    toggleMetadataModal,
    toggleImportModal,
    toggleEditPanel,
    setEditDrawTool,
    toggleLegendPanel,
    toggleGraticule,
    toggleMarkerMode,
    setSelectedLayer,
    switchToMainView,
    switchToEditorView,
    toggleView,
    openAttributeTable,
    closeAttributeTable,
    toggleAttributeTable,
    loadLLMStatus,
    loadProviders,
    switchProvider,
  }
})
