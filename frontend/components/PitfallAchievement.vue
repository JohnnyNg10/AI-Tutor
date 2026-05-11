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
      <span>数据加载失败</span>
      <button @click="fetchData">重试</button>
    </div>

    <div v-else-if="!hasData" class="pa-empty">
      <span>📭</span>
      <p>还没有练习数据，无法分析雷区</p>
    </div>

    <div v-else class="pa-grid">
      <!-- 雷区列 -->
      <div class="pa-col pitfalls-col">
        <h4 class="col-title">⚠️ 易错雷区</h4>
        <div v-if="pitfalls.length === 0" class="col-empty">暂无雷区数据</div>
        <div
          v-for="p in pitfalls"
          :key="p.type || p.name"
          class="pa-card pitfall-card"
        >
          <div class="card-header">
            <span class="card-type">{{ p.type || p.name }}</span>
            <span class="card-count">{{ p.count || p.error_count || 0 }}次</span>
          </div>
          <div v-if="p.suggestion || p.recovery_tip" class="card-tip">
            💡 {{ p.suggestion || p.recovery_tip }}
          </div>
        </div>
      </div>

      <!-- 成就列 -->
      <div class="pa-col achievements-col">
        <h4 class="col-title">🏆 攻克成就</h4>
        <div v-if="achievements.length === 0" class="col-empty">暂无攻克成就</div>
        <div
          v-for="a in achievements"
          :key="a.type || a.name"
          class="pa-card achievement-card"
        >
          <div class="card-header">
            <span class="card-type">{{ a.type || a.name }}</span>
            <span class="card-status">{{ a.achieved ? '✅' : '🔒' }}</span>
          </div>
          <div v-if="a.description" class="card-tip">{{ a.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

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
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.pa-header { margin-bottom: 16px; }
.pa-header h3 { font-size: 18px; font-weight: 600; color: #1d1d1f; margin: 0 0 4px; }
.pa-desc { font-size: 12px; color: #86868b; margin: 0; }

.pa-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.pa-col { display: flex; flex-direction: column; gap: 8px; }
.col-title {
  font-size: 14px; font-weight: 600; margin: 0 0 4px;
  padding-bottom: 8px; border-bottom: 2px solid #e5e7eb;
}
.pitfalls-col .col-title { color: #dc2626; border-bottom-color: #fca5a5; }
.achievements-col .col-title { color: #059669; border-bottom-color: #6ee7b7; }

.pa-card {
  padding: 12px 14px; border-radius: 10px;
  border: 1px solid #e5e7eb; transition: all 0.2s;
}
.pa-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.pitfall-card { background: #fef2f2; border-color: #fecaca; }
.achievement-card { background: #f0fdf4; border-color: #bbf7d0; }

.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-type { font-size: 13px; font-weight: 600; color: #1d1d1f; }
.card-count { font-size: 12px; font-weight: 700; color: #dc2626; }
.card-status { font-size: 14px; }

.card-tip { font-size: 11px; color: #6b7280; margin-top: 6px; line-height: 1.5; }

.col-empty { text-align: center; padding: 16px; color: #9ca3af; font-size: 13px; }

.pa-loading { display: grid; gap: 12px; grid-template-columns: 1fr 1fr; }
.pa-skeleton {
  height: 80px; border-radius: 12px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

.pa-error, .pa-empty { text-align: center; padding: 20px; color: #86868b; }
.pa-error button { margin-left: 8px; padding: 4px 12px; background: #1d1d1f; color: #fff; border: none; border-radius: 6px; cursor: pointer; }

@media (max-width: 768px) {
  .pa-grid { grid-template-columns: 1fr; }
}
</style>
