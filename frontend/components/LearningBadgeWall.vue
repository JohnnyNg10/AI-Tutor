<template>
  <div class="badge-wall">
    <div class="badge-header">
      <h3>学习徽章</h3>
      <p class="badge-desc">持续学习，解锁更多成就徽章</p>
    </div>

    <div v-if="loading" class="badge-loading">
      <div v-for="i in 4" :key="i" class="badge-skeleton"></div>
    </div>

    <div v-else-if="error" class="badge-error">
      <AlertTriangle :size="16" />
      <span>徽章数据加载失败</span>
      <button @click="fetchBadges">重试</button>
    </div>

    <div v-else class="badge-grid">
      <div
        v-for="badge in badges"
        :key="badge.id || badge.type"
        class="badge-card"
        :class="{ earned: badge.earned, locked: !badge.earned }"
        :title="badgeTooltip(badge)"
      >
        <div class="badge-icon-wrap">
          <Trophy v-if="badge.earned" :size="28" class="badge-icon earned-icon" />
          <Lock v-else :size="28" class="badge-icon locked-icon" />
          <span v-if="badge.earned && badge.count && badge.count > 1" class="badge-count">{{ badge.count }}</span>
        </div>
        <div class="badge-info">
          <span class="badge-name">{{ badge.name || badge.badge_id }}</span>
          <span class="badge-condition">{{ badge.description }}</span>
        </div>
        <div v-if="!badge.earned && badge.progress" class="badge-progress-bar">
          <div class="badge-progress-fill" :style="{ width: badge.progress.percentage + '%' }"></div>
        </div>
        <div v-if="!badge.earned && badge.progress" class="badge-progress-text">
          {{ badge.progress.current }}/{{ badge.progress.target }}
        </div>
        <div v-if="badge.earned && badge.earned_at" class="badge-earned-time">
          {{ formatTime(badge.earned_at) }}
        </div>
      </div>
    </div>

    <div v-if="!loading && !error && badges.length === 0" class="badge-empty">
      <Sparkles :size="24" />
      <p>还没有获得任何徽章，开始学习吧！</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Trophy, Lock, AlertTriangle, Sparkles } from 'lucide-vue-next'

const loading = ref(false)
const error = ref('')
const badges = ref([])

const badgeTooltip = (b) => {
  if (b.earned) {
    const earnedDate = b.earned_at ? new Date(b.earned_at).toLocaleDateString('zh-CN') : ''
    return `${b.name || b.type}: 已获得${earnedDate ? ' (' + earnedDate + ')' : ''}`
  }
  return `${b.name || b.type}: ${b.description || '尚未达成'}`
}

const formatTime = (t) => {
  if (!t) return ''
  const d = new Date(t)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const fetchBadges = async () => {
  loading.value = true
  error.value = ''
  try {
    const token = localStorage.getItem('access_token')
    const res = await fetch('/api/learning-badges/my-badges', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!res.ok) throw new Error('获取徽章失败')
    const data = await res.json()
    if (data.success) {
      // 合并已获得和进行中的徽章
      const earned = (data.earned_badges || []).map(b => ({ ...b, earned: true }))
      const progress = (data.in_progress || []).map(b => ({ ...b, earned: false }))
      badges.value = [...earned, ...progress]
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(fetchBadges)
</script>

<style scoped>
.badge-wall {
  background: var(--color-bg-white);
  border-radius: var(--radius-xl);
  padding: var(--space-xxl);
  box-shadow: var(--shadow-sm);
}

.badge-header { margin-bottom: var(--space-lg); }
.badge-header h3 { font-size: var(--font-size-lg); font-weight: 600; color: var(--color-text-title); margin: 0 0 var(--space-xs); }
.badge-desc { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin: 0; }

.badge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: var(--space-sm); }

.badge-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: var(--space-lg) var(--space-sm); border-radius: var(--radius-md);
  background: var(--color-bg-main); border: 1px solid var(--color-bg-divider);
  text-align: center; cursor: help; transition: all var(--transition-fast);
}
.badge-card.earned { background: var(--color-warning-bg); border-color: var(--color-warning); }
.badge-card.locked { opacity: 0.55; }
.badge-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }

.badge-icon-wrap { position: relative; }
.badge-icon.earned-icon { color: var(--color-warning); }
.badge-icon.locked-icon { color: var(--color-text-secondary); }
.badge-count {
  position: absolute; top: -4px; right: -8px;
  background: var(--color-danger); color: var(--color-bg-white); font-size: var(--font-size-xs); font-weight: 700;
  width: 18px; height: 18px; border-radius: var(--radius-full); display: flex;
  align-items: center; justify-content: center;
}

.badge-info { display: flex; flex-direction: column; gap: 2px; }
.badge-name { font-size: var(--font-size-xs); font-weight: 600; color: var(--color-text-title); }
.badge-condition { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.badge-progress-bar { width: 100%; height: 4px; background: var(--color-bg-divider); border-radius: 2px; overflow: hidden; }
.badge-progress-fill { height: 100%; background: var(--color-primary); border-radius: 2px; transition: width var(--transition-base); }
.badge-progress-text { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.badge-earned-time { font-size: var(--font-size-xs); color: #92400e; }

.badge-loading { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-sm); }
.badge-skeleton {
  height: 100px; border-radius: var(--radius-md);
  background: linear-gradient(90deg, var(--color-bg-divider) 25%, var(--color-bg-main) 50%, var(--color-bg-divider) 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

.badge-error { display: flex; align-items: center; gap: var(--space-sm); justify-content: center; padding: var(--space-xl); color: var(--color-text-secondary); }
.badge-error button { margin-left: var(--space-sm); padding: var(--space-xs) var(--space-md); background: var(--color-text-title); color: var(--color-bg-white); border: none; border-radius: var(--radius-sm); cursor: pointer; }
.badge-empty { text-align: center; padding: var(--space-xl); color: var(--color-text-secondary); }
.badge-empty p { margin-top: var(--space-sm); }
</style>
