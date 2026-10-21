<template>
  <div v-if="visible !== false" class="attribute-table-panel">
    <!-- 头部 -->
    <div class="table-header">
      <div class="header-title">
        <i class="fa-solid fa-table"></i>
        <span>属性表 - {{ layerName }}</span>
        <span class="feature-count">{{ featureCount }} 个要素</span>
      </div>
      <div class="header-actions">
        <button class="icon-btn" title="导出CSV" @click="exportCSV">
          <i class="fa-solid fa-file-csv"></i>
        </button>
        <button class="icon-btn" title="关闭" @click="close">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="table-toolbar">
      <div class="search-box">
        <i class="fa-solid fa-magnifying-glass search-icon"></i>
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索属性..."
        />
      </div>
      <div class="toolbar-right">
        <button class="tool-btn" title="添加字段" @click="addField">
          <i class="fa-solid fa-plus"></i>
        </button>
        <button class="tool-btn" title="删除字段" @click="deleteField">
          <i class="fa-solid fa-minus"></i>
        </button>
        <button class="tool-btn" title="字段计算器" @click="fieldCalculator">
          <i class="fa-solid fa-calculator"></i>
        </button>
      </div>
    </div>

    <!-- 表格内容 -->
    <div class="table-container" ref="tableContainerRef">
      <table class="data-table">
        <thead>
          <tr>
            <th class="row-header">#</th>
            <th
              v-for="field in fields"
              :key="field"
              class="field-header"
              @click="sortByField(field)"
            >
              <span>{{ field }}</span>
              <i
                v-if="sortField === field"
                class="fa-solid sort-icon"
                :class="sortAsc ? 'fa-sort-up' : 'fa-sort-down'"
              ></i>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in filteredRows"
            :key="idx"
            class="data-row"
            :class="{ selected: selectedRows.includes(idx) }"
            @click="selectRow(idx, $event)"
          >
            <td class="row-header">{{ idx + 1 }}</td>
            <td v-for="field in fields" :key="field" class="data-cell">
              {{ formatValue(row[field]) }}
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="filteredRows.length === 0" class="empty-state">
        <i class="fa-solid fa-inbox"></i>
        <span>暂无数据</span>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="table-footer">
      <div class="footer-left">
        <span>选中 {{ selectedRows.length }} 行</span>
      </div>
      <div class="footer-right">
        <button class="page-btn" :disabled="currentPage <= 1" @click="prevPage">
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button class="page-btn" :disabled="currentPage >= totalPages" @click="nextPage">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'

const appStore = useAppStore()
const mapStore = useMapStore()

const props = defineProps<{ visible?: boolean }>()
const emit = defineEmits<{ (e: 'row-select', idx: number): void }>()

// 当前图层数据
const currentLayer = computed(() => {
  if (!appStore.attributeTableLayerId) return null
  return mapStore.layerGroups[appStore.attributeTableLayerId] || null
})

const layerName = computed(() => currentLayer.value?.data.name || '未知图层')

// 从图层features中提取字段和行数据
const fields = computed(() => {
  if (!currentLayer.value?.data.features || currentLayer.value.data.features.length === 0) {
    return []
  }
  const firstFeature = currentLayer.value.data.features[0]
  if (firstFeature.properties) {
    return Object.keys(firstFeature.properties)
  }
  return []
})

const rows = computed(() => {
  if (!currentLayer.value?.data.features) {
    return []
  }
  return currentLayer.value.data.features.map((feature: any) => feature.properties || {})
})

const featureCount = computed(() => rows.value.length)

function close() {
  appStore.closeAttributeTable()
}

const searchQuery = ref('')
const sortField = ref<string | null>(null)
const sortAsc = ref(true)
const selectedRows = ref<number[]>([])
const currentPage = ref(1)
const pageSize = 50
const tableContainerRef = ref<HTMLDivElement | null>(null)

const filteredRows = computed(() => {
  let result = [...rows.value]

  // 搜索过滤
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((row) =>
      Object.values(row).some((val) =>
        String(val).toLowerCase().includes(query)
      )
    )
  }

  // 排序
  if (sortField.value) {
    const field = sortField.value
    result.sort((a, b) => {
      const valA = a[field]
      const valB = b[field]
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc.value ? valA - valB : valB - valA
      }
      const strA = String(valA || '')
      const strB = String(valB || '')
      return sortAsc.value ? strA.localeCompare(strB) : strB.localeCompare(strA)
    })
  }

  return result
})

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(filteredRows.value.length / pageSize))
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredRows.value.slice(start, start + pageSize)
})

function sortByField(field: string) {
  if (sortField.value === field) {
    sortAsc.value = !sortAsc.value
  } else {
    sortField.value = field
    sortAsc.value = true
  }
}

function selectRow(idx: number, event: MouseEvent) {
  if (event.ctrlKey || event.metaKey) {
    const index = selectedRows.value.indexOf(idx)
    if (index > -1) {
      selectedRows.value.splice(index, 1)
    } else {
      selectedRows.value.push(idx)
    }
  } else if (event.shiftKey) {
    // Shift多选
    if (selectedRows.value.length > 0) {
      const last = selectedRows.value[selectedRows.value.length - 1]
      const start = Math.min(last, idx)
      const end = Math.max(last, idx)
      selectedRows.value = Array.from({ length: end - start + 1 }, (_, i) => start + i)
    } else {
      selectedRows.value = [idx]
    }
  } else {
    selectedRows.value = [idx]
  }
  emit('row-select', idx)
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(4)
  }
  return String(value)
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

function exportCSV() {
  if (!fields.value.length || !rows.value.length) return

  const header = fields.value.join(',')
  const csvRows = rows.value.map((row) =>
    fields.value
      .map((field) => {
        const val = row[field]
        if (typeof val === 'string' && val.includes(',')) {
          return `"${val}"`
        }
        return val ?? ''
      })
      .join(',')
  )
  const csv = [header, ...csvRows].join('\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${layerName.value || 'attributes'}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

function addField() {
  const layer = currentLayer.value?.data
  if (!layer || !layer.features || layer.features.length === 0) {
    alert('当前图层没有要素数据')
    return
  }
  const name = prompt('请输入新字段名（英文/数字，如 area_km2）')
  if (!name || !name.trim()) return
  const field = name.trim()
  layer.features.forEach((f: any) => {
    if (!f.properties) f.properties = {}
    f.properties[field] = null
  })
  searchQuery.value = ''
}

function deleteField() {
  const layer = currentLayer.value?.data
  if (!layer || !layer.features || layer.features.length === 0) return
  const field = prompt('请输入要删除的字段名')
  if (!field || !field.trim()) return
  layer.features.forEach((f: any) => {
    if (f.properties) delete f.properties[field.trim()]
  })
}

function fieldCalculator() {
  const layer = currentLayer.value?.data
  if (!layer || !layer.features || layer.features.length === 0) {
    alert('当前图层没有要素数据')
    return
  }
  const fieldList = fields.value
  const expr = prompt(
    '输入计算表达式（支持字段名和 + - * / % 括号，如 pop / area）\n可用字段: ' + fieldList.join(', ')
  )
  if (!expr) return
  const calculator = buildCalculator(expr, fieldList)
  if (!calculator) {
    alert('表达式无效，请检查语法和字段名')
    return
  }
  const target = prompt('结果写入字段名（可新建）')
  if (!target || !target.trim()) return
  const field = target.trim()
  layer.features.forEach((f: any) => {
    if (!f.properties) f.properties = {}
    try {
      f.properties[field] = calculator(f.properties)
    } catch {
      f.properties[field] = null
    }
  })
}

function buildCalculator(
  expr: string,
  fields: string[]
): ((props: Record<string, any>) => number) | null {
  const sanitized = expr.replace(/([A-Za-z_][A-Za-z0-9_.]*)/g, (m) => {
    if (fields.includes(m)) {
      return `Number(props[${JSON.stringify(m)}] ?? 0)`
    }
    return m
  })
  try {
    // eslint-disable-next-line no-new-func
    return new Function('props', `"use strict"; return (${sanitized})`) as (
      props: Record<string, any>
    ) => number
  } catch {
    return null
  }
}

watch(
  () => appStore.showAttributeTable,
  (val) => {
    if (val) {
      currentPage.value = 1
      selectedRows.value = []
      searchQuery.value = ''
    }
  }
)
</script>

<style scoped>
.attribute-table-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 300px;
  background: #fff;
  border-top: 1px solid var(--color-border);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
  z-index: 50;
  display: flex;
  flex-direction: column;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid var(--color-border);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.header-title i {
  color: var(--color-primary);
}

.feature-count {
  font-size: 11px;
  font-weight: 400;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 10px;
}

.header-actions {
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
  background: rgba(124, 58, 237, 0.1);
  color: var(--color-primary);
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-border);
  background: #fafbfc;
}

.search-box {
  position: relative;
  flex: 1;
  max-width: 300px;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.search-input {
  width: 100%;
  padding: 5px 10px 5px 28px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--color-primary-light);
}

.toolbar-right {
  display: flex;
  gap: 4px;
}

.tool-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.15s;
}

.tool-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: rgba(124, 58, 237, 0.04);
}

.table-container {
  flex: 1;
  overflow: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.data-table thead {
  position: sticky;
  top: 0;
  z-index: 10;
}

.field-header {
  padding: 8px 10px;
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  font-weight: 600;
  color: var(--color-text);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  position: relative;
}

.field-header:hover {
  background: #f1f5f9;
}

.sort-icon {
  margin-left: 4px;
  font-size: 10px;
  color: var(--color-primary);
}

.row-header {
  padding: 6px 10px;
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
  text-align: center;
  font-size: 11px;
  color: var(--color-text-secondary);
  width: 40px;
  position: sticky;
  left: 0;
  z-index: 5;
}

.data-row {
  transition: background 0.1s;
}

.data-row:hover {
  background: rgba(124, 58, 237, 0.04);
}

.data-row.selected {
  background: rgba(124, 58, 237, 0.12);
}

.data-row.selected .row-header {
  background: rgba(124, 58, 237, 0.12);
}

.data-cell {
  padding: 6px 10px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--color-text-secondary);
}

.empty-state i {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.3;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid var(--color-border);
  background: #fafbfc;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  transition: all 0.15s;
}

.page-btn:hover:not(:disabled) {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  font-variant-numeric: tabular-nums;
}
</style>
