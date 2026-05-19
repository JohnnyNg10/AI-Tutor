<template>
  <div class="pitfall-achievement">
    <div class="pa-header">
      <h3>雷区与攻克成就</h3>
      <p class="pa-desc">识别你的易错题型，见证难题攻克历程</p>
    </div>

    <div v-if="loading" class="pa-loading">
      <div class="pa-skeleton"></div>
      <div class="pa-skeleton"></div>
    </div>

    <div v-else-if="error" class="pa-error">
      <AlertTriangle :size="16" />
      <span>数据加载失败</span>
      <button @click="fetchData">重试</button>
    </div>

    <div v-else-if="!hasData" class="pa-empty">
      <Inbox :size="24" />
      <p>还没有练习数据，无法分析雷区</p>
    </div>

    <div v-else class="pa-grid">
      <div class="pa-col pitfalls-col">
        <h4 class="col-title">易错雷区</h4>
        <div v-if="pitfalls.length === 0" class="col-empty">暂无雷区数据</div>
        <div v-for="p in pitfalls" :key="p.type || p.name" class="pa-card pitfall-card">
          <div class="card-header">
            <span class="card-type">{{ p.type || p.name }}</span>
            <span class="card-count">{{ p.count || p.error_count || 0 }}次</span>
          </div>
          <div v-if="p.suggestion || p.recovery_tip" class="card-tip">
            {{ p.suggestion || p.recovery_tip }}
          </div>
        </div>
      </div>

      <div class="pa-col achievements-col">
        <h4 class="col-title">攻克成就</h4>
        <div v-if="achievements.length === 0" class="col-empty">暂无攻克成就</div>
        <div v-for="a in achievements" :key="a.type || a.name" class="pa-card achievement-card">
          <div class="card-header">
            <span class="card-type">{{ a.type || a.name }}</span>
            <CheckCircle2 v-if="a.achieved" :size="16" class="achieved-icon" />
            <Lock v-else :size="16" class="locked-icon" />
          </div>
          <div v-if="a.description" class="card-tip">{{ a.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { AlertTriangle, Inbox, CheckCircle2, Lock } from 'lucide-vue-next'

const loading = ref(false)
const error = ref('')
const pitfalls = ref([])
const achievements = ref([])

const hasData = computed(() => pitfalls.value.length > 0 || achievements.value.length > 0)

const fetchData = async () => {
  loading.value = true
  error.value = ''
  try {
    const token = localStorage.getItem('access_token')
    const res = await fetch('/api/pitfall-achievement/dual-column', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!res.ok) throw new Error('获取雷区数据失败')
    const data = await res.json()
    if (data.success) {
      const left = data.left_column || data.data?.left_column || {}
      const right = data.right_column || data.data?.right_column || {}
      pitfalls.value = (left.cards || []).map(c => ({
        type: c.title || c.id, name: c.title || c.id,
        count: c.frequency || 0, suggestion: c.suggestion || ''
      }))
      achievements.value = (right.cards || []).map(c => ({
        type: c.title || c.id, name: c.title || c.id,
        achieved: true, description: c.subtitle || ''
      }))
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.pitfall-achievement {
  background: var(--color-bg-white);
  border-radius: var(--radius-xl);
  padding: var(--space-xxl);
  box-shadow: var(--shadow-sm);
}

.pa-header { margin-bottom: var(--space-lg); }
.pa-header h3 { font-size: var(--font-size-lg); font-weight: 600; color: var(--color-text-title); margin: 0 0 var(--space-xs); }
.pa-desc { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin: 0; }

.pa-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-lg); }

.pa-col { display: flex; flex-direction: column; gap: var(--space-sm); }
.col-title {
  font-size: var(--font-size-base); font-weight: 600; margin: 0 0 var(--space-xs);
  padding-bottom: var(--space-sm); border-bottom: 2px solid var(--color-bg-divider);
}
.pitfalls-col .col-title { color: var(--color-danger); border-bottom-color: var(--color-danger-border); }
.achievements-col .col-title { color: var(--color-success); border-bottom-color: var(--color-success-border); }

.pa-card {
  padding: var(--space-md); border-radius: var(--radius-md);
  border: 1px solid var(--color-bg-divider); transition: all var(--transition-fast);
}
.pa-card:hover { box-shadow: var(--shadow-sm); }
.pitfall-card { background: var(--color-danger-bg); border-color: var(--color-danger-border); }
.achievement-card { background: var(--color-success-bg); border-color: var(--color-success-border); }

.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-type { font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-title); }
.card-count { font-size: var(--font-size-xs); font-weight: 700; color: var(--color-danger); }
.achieved-icon { color: var(--color-success); }
.locked-icon { color: var(--color-text-secondary); }

.card-tip { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-top: 6px; line-height: 1.5; }

.col-empty { text-align: center; padding: var(--space-lg); color: var(--color-text-secondary); font-size: var(--font-size-sm); }

.pa-loading { display: grid; gap: var(--space-md); grid-template-columns: 1fr 1fr; }
.pa-skeleton {
  height: 80px; border-radius: var(--radius-md);
  background: linear-gradient(90deg, var(--color-bg-divider) 25%, var(--color-bg-main) 50%, var(--color-bg-divider) 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

.pa-error { display: flex; align-items: center; gap: var(--space-sm); justify-content: center; padding: var(--space-xl); color: var(--color-text-secondary); }
.pa-error button { margin-left: var(--space-sm); padding: var(--space-xs) var(--space-md); background: var(--color-text-title); color: var(--color-bg-white); border: none; border-radius: var(--radius-sm); cursor: pointer; }
.pa-empty { text-align: center; padding: var(--space-xl); color: var(--color-text-secondary); }
.pa-empty p { margin-top: var(--space-sm); }

@media (max-width: 768px) {
  .pa-grid { grid-template-columns: 1fr; }
}
</style>
