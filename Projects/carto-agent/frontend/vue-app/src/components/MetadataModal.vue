<template>
  <Teleport to="body">
    <div class="metadata-overlay" @click.self="appStore.toggleMetadataModal()">
      <div class="metadata-dialog">
        <div class="metadata-header">
          <span><i class="fa-solid fa-circle-info"></i> 编制说明</span>
          <button class="metadata-close" @click="appStore.toggleMetadataModal()">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="metadata-body">
          <template v-if="metaEntries.length > 0">
            <div v-for="[k, v] in metaEntries" :key="k" class="metadata-line">
              <b>{{ k }}：</b>{{ v }}
            </div>
          </template>
          <template v-else>
            <div class="metadata-line">暂无编制信息</div>
          </template>
          <div class="metadata-divider"></div>
          <div class="metadata-line"><b>地图名称：</b>{{ mapStore.mapName || '未命名地图' }}</div>
          <div class="metadata-line"><b>地图类型：</b>{{ mapStore.mapType || '-' }}</div>
          <div class="metadata-line"><b>区域：</b>{{ mapStore.region || '-' }}</div>
          <div class="metadata-line"><b>投影：</b>Web Mercator (EPSG:3857)</div>
          <div class="metadata-line"><b>坐标系：</b>WGS84</div>
          <div class="metadata-line"><b>图层数：</b>{{ mapStore.sortedLayers.length }}</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'

const appStore = useAppStore()
const mapStore = useMapStore()

const metaEntries = computed(() => {
  const meta = mapStore.metadata
  return meta ? Object.entries(meta) : []
})
</script>

<style scoped>
.metadata-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.metadata-dialog {
  width: 460px;
  max-height: 80vh;
  background: #fff;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.metadata-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-border);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
}

.metadata-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 50%;
  cursor: pointer;
}

.metadata-close:hover {
  background: var(--color-bg);
}

.metadata-body {
  padding: 16px 18px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-text);
}

.metadata-line b {
  color: var(--color-text-secondary);
  font-weight: 600;
}

.metadata-divider {
  height: 1px;
  background: var(--color-border);
  margin: 10px 0;
}
</style>
