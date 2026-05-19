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
  background: #fff; border-radius: 16px; padding: 32px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.progress-center { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.spinner-icon { color: #0E61AC; animation: spin 1s linear infinite; }
.spinner-icon-sm { color: #0E61AC; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.progress-title { font-size: 18px; font-weight: 700; color: #1B1B1B; }
.progress-desc { font-size: 14px; color: #86868B; }
.progress-eta { font-size: 13px; color: #86868B; }
.progress-bar-track {
  width: 100%; max-width: 400px; height: 6px; background: #EEEEEE;
  border-radius: 3px; overflow: hidden; margin: 8px 0;
}
.progress-bar-fill { height: 100%; background: #0E61AC; border-radius: 3px; transition: width 0.3s ease; }
.status-list {
  width: 100%; max-width: 360px; background: #FAF2E0; border-radius: 12px;
  padding: 16px; display: flex; flex-direction: column; gap: 8px; margin-top: 8px;
}
.status-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #0E61AC; }
.status-label { margin-left: auto; font-size: 12px; color: #86868B; }
.status-item.waiting { color: #86868B; }
.status-item.waiting .status-label { color: #86868B; }
.progress-actions { display: flex; gap: 12px; margin-top: 16px; }
.btn-secondary {
  background: none; border: none; color: #86868B; font-size: 14px; cursor: pointer;
  font-family: var(--font-family); transition: color 0.15s;
}
.btn-secondary:hover { color: #dc2626; }
.btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  background: #0E61AC; color: #FAF2E0; border: none; border-radius: 10px;
  padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer;
  transition: opacity 0.2s; font-family: var(--font-family);
}
.btn-primary:hover { opacity: 0.85; }
</style>
