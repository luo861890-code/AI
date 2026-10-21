<template>
  <div v-if="quality" class="quality-report">
    <div class="quality-header" @click="expanded = !expanded">
      <div class="quality-title">
        <i class="fa-solid fa-shield-check" :class="qualityClass"></i>
        <span>制图质量校验</span>
      </div>
      <div class="quality-summary">
        <span class="quality-score" :class="qualityClass">{{ score }}分</span>
        <i class="fa-solid" :class="expanded ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
      </div>
    </div>

    <div v-if="expanded" class="quality-body">
      <!-- 总体状态 -->
      <div class="quality-overall" :class="qualityClass">
        <i class="fa-solid" :class="overallIcon"></i>
        <span>{{ overallText }}</span>
      </div>

      <!-- 检查项列表 -->
      <div class="quality-items">
        <div
          v-for="(item, idx) in quality.items"
          :key="idx"
          class="quality-item"
          :class="{ passed: item.passed, failed: !item.passed }"
        >
          <div class="item-status">
            <i v-if="item.passed" class="fa-solid fa-circle-check status-icon success"></i>
            <i v-else class="fa-solid fa-circle-xmark status-icon error"></i>
          </div>
          <div class="item-content">
            <div class="item-name">{{ item.check }}</div>
            <div v-if="item.message" class="item-message">{{ item.message }}</div>
            <div v-if="item.count !== undefined" class="item-count">
              涉及要素: <strong>{{ item.count }}</strong> 个
            </div>
          </div>
        </div>
      </div>

      <!-- 警告信息 -->
      <div v-if="quality.warnings && quality.warnings.length > 0" class="quality-warnings">
        <div class="warnings-title">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>优化建议</span>
        </div>
        <div class="warnings-list">
          <div v-for="(warning, idx) in quality.warnings" :key="idx" class="warning-item">
            <i class="fa-solid fa-lightbulb"></i>
            <span>{{ warning }}</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="quality-actions">
        <button class="action-btn secondary" @click="$emit('optimize')">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
          一键优化
        </button>
        <button class="action-btn primary" @click="$emit('accept')">
          <i class="fa-solid fa-check"></i>
          接受当前结果
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { QualityReport } from '@/types'

const props = defineProps<{
  quality: QualityReport | null
}>()

defineEmits<{
  (e: 'optimize'): void
  (e: 'accept'): void
}>()

const expanded = ref(true)

const score = computed(() => {
  if (!props.quality?.items?.length) return 100
  const passed = props.quality.items.filter((i) => i.passed).length
  const total = props.quality.items.length
  return Math.round((passed / total) * 100)
})

const qualityClass = computed(() => {
  if (score.value >= 90) return 'excellent'
  if (score.value >= 70) return 'good'
  if (score.value >= 50) return 'fair'
  return 'poor'
})

const overallIcon = computed(() => {
  if (score.value >= 90) return 'fa-circle-check'
  if (score.value >= 70) return 'fa-circle-check'
  if (score.value >= 50) return 'fa-triangle-exclamation'
  return 'fa-circle-xmark'
})

const overallText = computed(() => {
  if (score.value >= 90) return '制图质量优秀，符合专业规范'
  if (score.value >= 70) return '制图质量良好，基本符合规范'
  if (score.value >= 50) return '制图质量一般，建议优化'
  return '制图质量较差，需要改进'
})
</script>

<style scoped>
.quality-report {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: #fff;
}

.quality-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f8fafc;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.quality-header:hover {
  background: #f1f5f9;
}

.quality-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.quality-title i {
  font-size: 16px;
}

.quality-title i.excellent {
  color: var(--color-success);
}

.quality-title i.good {
  color: #22c55e;
}

.quality-title i.fair {
  color: var(--color-warning);
}

.quality-title i.poor {
  color: var(--color-error);
}

.quality-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.quality-score {
  font-size: 14px;
  font-weight: 700;
}

.quality-score.excellent {
  color: var(--color-success);
}

.quality-score.good {
  color: #22c55e;
}

.quality-score.fair {
  color: var(--color-warning);
}

.quality-score.poor {
  color: var(--color-error);
}

.quality-body {
  padding: 12px;
  border-top: 1px solid var(--color-border);
}

.quality-overall {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 500;
}

.quality-overall.excellent {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.quality-overall.good {
  background: rgba(34, 197, 94, 0.08);
  color: #16a34a;
}

.quality-overall.fair {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.quality-overall.poor {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.quality-overall i {
  font-size: 18px;
}

.quality-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quality-item {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fafbfc;
}

.quality-item.passed {
  border-left: 3px solid var(--color-success);
}

.quality-item.failed {
  border-left: 3px solid var(--color-error);
}

.item-status {
  flex-shrink: 0;
  padding-top: 1px;
}

.status-icon {
  font-size: 14px;
}

.status-icon.success {
  color: var(--color-success);
}

.status-icon.error {
  color: var(--color-error);
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 2px;
}

.item-message {
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.4;
}

.item-count {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.item-count strong {
  color: var(--color-text);
}

.quality-warnings {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.warnings-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-warning);
  margin-bottom: 8px;
}

.warnings-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.warning-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  background: rgba(245, 158, 11, 0.06);
  border-radius: 4px;
  font-size: 11px;
  color: #92400e;
  line-height: 1.4;
}

.warning-item i {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--color-warning);
}

.quality-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.action-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
}

.action-btn.primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.action-btn.primary:hover {
  opacity: 0.9;
}

.action-btn.secondary {
  background: #fff;
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.action-btn.secondary:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: rgba(124, 58, 237, 0.04);
}
</style>
