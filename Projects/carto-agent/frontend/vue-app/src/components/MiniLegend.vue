<template>
  <div class="map-mini-legend">
    <div class="mini-legend-header" @click="folded = !folded">
      <span class="mini-legend-title">图例</span>
      <button class="mini-legend-fold" title="折叠/展开">{{ folded ? '▸' : '▾' }}</button>
    </div>
    <div v-if="!folded" class="mini-legend-body">
      <div class="mini-legend-item"><span class="mini-line" style="background:#E03131;height:3px;"></span>武汉市域边界</div>
      <div class="mini-legend-item"><span class="mini-line mini-dashdot"></span>区县界（点划线）</div>
      <div class="mini-legend-item"><span class="mini-line" style="background:#B08968;height:2.5px;"></span>湖北周边市界</div>
      <div class="mini-legend-item"><span class="mini-box" style="background:#F5F0E1;opacity:0.85"></span>湖北周边地市</div>
      <div class="mini-legend-item"><span class="mini-box" style="background:#1e90ff;opacity:0.5"></span>湖泊水系</div>
      <div class="mini-legend-item"><span class="mini-sym mini-star">★</span>市级行政中心</div>
      <div class="mini-legend-item"><span class="mini-sym mini-dot" style="background:#D82828;"></span>区县级行政中心</div>
      <div class="mini-legend-item"><span class="mini-sym mini-poi">🏛️</span>重点地标</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const folded = ref(false)
</script>

<style scoped>
.map-mini-legend {
  position: absolute;
  bottom: 44px;
  right: 10px;
  width: 180px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  z-index: 12;
  font-size: 11px;
  color: var(--color-text);
  overflow: hidden;
}

.mini-legend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 10px;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border-bottom: 1px solid var(--color-border);
  font-weight: 600;
}

.mini-legend-fold {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: 10px;
}

.mini-legend-body {
  padding: 6px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.mini-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-line {
  width: 18px;
  height: 2px;
  background: #333;
  display: inline-block;
  flex-shrink: 0;
}

.mini-dashdot {
  background: repeating-linear-gradient(90deg, #333 0 3px, transparent 3px 5px, #333 5px 6px, transparent 6px 8px);
}

.mini-box {
  width: 14px;
  height: 12px;
  display: inline-block;
  border: 1px solid rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
}

.mini-sym {
  width: 18px;
  text-align: center;
  font-size: 10px;
  flex-shrink: 0;
}

.mini-star {
  color: #e03131;
  font-size: 12px;
}

.mini-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin: 0 auto;
}
</style>
