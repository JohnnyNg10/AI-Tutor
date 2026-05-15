<template>
  <div class="card">
    <h2 class="card-title">错因分布</h2>
    <div class="distribution-list" v-if="items.length > 0">
      <div v-for="item in items" :key="item.type" class="distribution-row">
        <div class="bar-container">
          <div
            class="bar-fill"
            :style="{ width: item.percent + '%', background: item.color }"
          ></div>
        </div>
        <span class="bar-label">{{ item.type }}</span>
        <span class="bar-count">{{ item.count }}次</span>
        <span class="bar-pct">({{ item.percent }}%)</span>
      </div>
    </div>
    <div v-else class="empty">暂无错因数据</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  distribution: { type: Object, default: () => ({}) }
})

const errorColors = {
  '概念错误': '#e94560',
  '过程错误': '#f59e0b',
  '计算错误': '#eab308',
  '审题错误': '#3b82f6',
  '格式错误': '#6b7280'
}

const items = computed(() => {
  const dist = props.distribution || {}
  const total = Object.values(dist).reduce((a, b) => a + b, 0)
  return Object.entries(dist)
    .map(([type, count]) => ({
      type,
      count,
      percent: total > 0 ? Math.round((count / total) * 100) : 0,
      color: errorColors[type] || '#6b7280'
    }))
    .sort((a, b) => b.count - a.count)
})
</script>

<style scoped>
.card {
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  padding: 24px;
  box-shadow: var(--shadow-subtle);
}
.card-title {
  font-size: var(--font-md);
  font-weight: 600;
  color: var(--color-text-title);
  margin-bottom: 16px;
}

.distribution-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.bar-container {
  flex: 1;
  height: 24px;
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-base);
  min-width: 4px;
  transition: width 0.4s ease;
}

.bar-label {
  font-size: var(--font-sm);
  color: var(--color-text-body);
  min-width: 60px;
}

.bar-count {
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--color-text-title);
  min-width: 30px;
  text-align: right;
}

.bar-pct {
  font-size: var(--font-xs);
  color: var(--color-text-secondary);
  min-width: 42px;
}

.empty {
  color: var(--color-text-secondary);
  font-size: var(--font-base);
}
</style>
