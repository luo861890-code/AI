/**
 * 知识图谱状态管理 (Pinia)
 * 管理知识图谱数据、选中节点、搜索关键词和过滤条件
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { KGGraphData, KGNode } from '@/types'
import { CONFIG } from '@/config'
import api from '@/services/api'

export const useKGStore = defineStore('kg', () => {
  /** 知识图谱数据 */
  const graphData = ref<KGGraphData>({ nodes: [], links: [] })

  /** 选中节点 */
  const selectedNode = ref<KGNode | null>(null)

  /** 搜索关键词 */
  const searchKeyword = ref('')

  /** 激活的过滤标签集合 */
  const activeFilters = ref<Set<string>>(new Set())

  /** 是否正在加载 */
  const loading = ref(false)

  // ========== Actions ==========

  /** 加载知识图谱数据 */
  async function loadGraph(limit?: number) {
    loading.value = true
    try {
      graphData.value = await api.getKGGraph(limit ?? CONFIG.kgDefaultLimit)
    } catch (error) {
      console.error('加载知识图谱失败:', error)
      graphData.value = { nodes: [], links: [] }
    } finally {
      loading.value = false
    }
  }

  /** 选中节点 */
  function selectNode(node: KGNode | null) {
    selectedNode.value = node
  }

  /** 设置搜索关键词 */
  function setSearch(keyword: string) {
    searchKeyword.value = keyword
  }

  /** 切换过滤标签 */
  function toggleFilter(label: string) {
    const next = new Set(activeFilters.value)
    if (next.has(label)) {
      next.delete(label)
    } else {
      next.add(label)
    }
    activeFilters.value = next
  }

  /** 清空所有过滤标签 */
  function clearFilters() {
    activeFilters.value = new Set()
  }

  return {
    // State
    graphData,
    selectedNode,
    searchKeyword,
    activeFilters,
    loading,
    // Actions
    loadGraph,
    selectNode,
    setSearch,
    toggleFilter,
    clearFilters,
  }
})
