<template>
  <div class="card">
    <h2 class="card-title">知识点表现</h2>
    <div class="kp-list" v-if="items.length > 0">
      <div v-for="item in items" :key="item.name" class="kp-row">
        <span class="kp-name">{{ item.name }}</span>
        <div class="kp-bar-track">
          <div
            class="kp-bar-fill"
            :style="{ width: item.mastery + '%', background: item.color }"
          ></div>
        </div>
        <span class="kp-pct">{{ item.mastery }}%</span>
        <span class="kp-level" :style="{ color: item.color }">
          <Circle :size="8" :fill="item.color" />
          {{ item.level }}
        </span>
      </div>
    </div>
    <div v-else class="empty">暂无知识点数据</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Circle } from 'lucide-vue-next'

const props = defineProps({
  kpMastery: { type: Object, default: () => ({}) }
})

function getLevel(pct) {
  if (pct >= 80) return { level: '精通', color: 'var(--color-mastery-excellent)' }
  if (pct >= 60) return { level: '稳固', color: 'var(--color-mastery-excellent)' }
  if (pct >= 40) return { level: '需巩固', color: 'var(--color-mastery-consolidate)' }
  return { level: '薄弱', color: 'var(--color-mastery-weak)' }
}

const items = computed(() => {
  const mastery = props.kpMastery || {}
  return Object.entries(mastery)
    .map(([name, value]) => {
      const pct = Math.round((Number(value) || 0) * 100)
      const { level, color } = getLevel(pct)
      return { name, mastery: pct, level, color }
    })
    .sort((a, b) => b.mastery - a.mastery)
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

.kp-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.kp-name {
  font-size: var(--font-sm);
  color: var(--color-text-body);
  min-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kp-bar-track {
  flex: 1;
  height: 10px;
  background: var(--color-bg-main);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.kp-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.4s ease;
}

.kp-pct {
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--color-text-title);
  min-width: 40px;
  text-align: right;
}

.kp-level {
  font-size: var(--font-xs);
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 56px;
}

.empty {
  color: var(--color-text-secondary);
  font-size: var(--font-base);
}
</style>
