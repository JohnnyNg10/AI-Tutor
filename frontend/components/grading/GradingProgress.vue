<template>
  <div class="grading-progress">
    <div class="progress-center">
      <Loader2 :size="48" class="spinner-icon" />
      <h2 class="progress-title">正在批改中...</h2>
      <p class="progress-desc">{{ statusText }}</p>
      <p class="progress-eta" v-if="etaSeconds > 0">预计还需 {{ etaSeconds }} 秒</p>

      <div class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: percent + '%' }"></div>
      </div>

      <div class="status-list">
        <div
          v-for="i in total"
          :key="i"
          class="status-item"
          :class="statusClass(i - 1)"
        >
          <CheckCircle2 v-if="questionStatuses[i - 1] === 'done'" :size="16" class="text-success" />
          <Loader2 v-else-if="questionStatuses[i - 1] === 'grading'" :size="16" class="spinner-icon-sm" />
          <Circle v-else :size="16" class="text-muted" />
          <span>第{{ i }}题</span>
          <span class="status-label">{{ statusLabel(i - 1) }}</span>
        </div>
      </div>

      <div class="progress-actions">
        <button class="btn btn-secondary" @click="$emit('cancel')">
          <XCircle :size="16" />
          取消批改
        </button>
        <button
          v-if="hasAnyDone"
          class="btn btn-primary"
          @click="$emit('view-report')"
        >
          查看报告
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loader2, CheckCircle2, Circle, XCircle } from 'lucide-vue-next'

const props = defineProps({
  current: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  etaSeconds: { type: Number, default: 0 },
  questionStatuses: { type: Object, default: () => ({}) }
})

defineEmits(['cancel', 'view-report'])

const percent = computed(() =>
  props.total > 0 ? Math.round((props.current / props.total) * 100) : 0
)

const statusText = computed(() =>
  props.total > 0 ? `正在分析第 ${Math.min(props.current + 1, props.total)}/${props.total} 题` : '准备中...'
)

const hasAnyDone = computed(() =>
  Object.values(props.questionStatuses).some(s => s === 'done')
)

function statusClass(index) {
  return props.questionStatuses[index] || 'waiting'
}

function statusLabel(index) {
  const status = props.questionStatuses[index]
  if (status === 'done') return '已完成'
  if (status === 'grading') return '分析中...'
  return '等待中'
}
</script>

<style scoped>
.grading-progress {
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  padding: 48px 32px;
  box-shadow: var(--shadow-subtle);
}

.progress-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.spinner-icon { color: var(--color-primary); animation: spin 1s linear infinite; }
.spinner-icon-sm { color: var(--color-primary); animation: spin 1s linear infinite; }

@keyframes spin {
  to { transform: rotate(360deg); }
}

.progress-title { font-size: var(--font-xl); font-weight: 700; color: var(--color-text-title); }
.progress-desc { font-size: var(--font-base); color: var(--color-text-secondary); }
.progress-eta { font-size: var(--font-sm); color: var(--color-text-secondary); }

.progress-bar-track {
  width: 100%;
  max-width: 400px;
  height: 6px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
  margin: 8px 0;
}

.progress-bar-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.status-list {
  width: 100%;
  max-width: 360px;
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-sm);
  color: var(--color-text-body);
}

.status-label { margin-left: auto; font-size: var(--font-xs); color: var(--color-text-secondary); }

.text-success { color: var(--color-success); }
.text-muted { color: var(--color-text-secondary); }

.progress-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
</style>
