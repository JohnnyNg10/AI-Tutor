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
          <span class="badge-emoji">{{ badge.icon || '⭐' }}</span>
          <span v-if="badge.earned && badge.count && badge.count > 1" class="badge-count">{{ badge.count }}</span>
        </div>
        <div class="badge-info">
          <span class="badge-name">{{ badge.name || badge.badge_id }}</span>
          <span class="badge-condition">{{ badge.description }}</span>
        </div>
        <!-- 进行中徽章显示进度 -->
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
      <span>🌟</span>
      <p>还没有获得任何徽章，开始学习吧！</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const loading = ref(false)
const error = ref('')
const badges = ref([])

const defaultIcon = (b) => {
  const t = (b.type || b.name || '').toLowerCase()
  if (t.includes('连击') || t.includes('streak')) return '🔥'
  if (t.includes('复习') || t.includes('review')) return '📝'
  if (t.includes('正确') || t.includes('accuracy')) return '🎯'
  if (t.includes('坚持') || t.includes('daily')) return '📅'
  return '⭐'
}

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
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.badge-header { margin-bottom: 16px; }
.badge-header h3 { font-size: 18px; font-weight: 600; color: #1d1d1f; margin: 0 0 4px; }
.badge-desc { font-size: 12px; color: #86868b; margin: 0; }

.badge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
}

.badge-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 14px 10px; border-radius: 12px;
  background: #f9fafb; border: 1px solid #e5e7eb;
  text-align: center; cursor: help; transition: all 0.2s;
}
.badge-card.earned { background: linear-gradient(135deg, #fef3c7, #fde68a); border-color: #f59e0b; }
.badge-card.locked { opacity: 0.55; filter: grayscale(0.6); }
.badge-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.1); }

.badge-icon-wrap { position: relative; }
.badge-emoji { font-size: 32px; }
.badge-count {
  position: absolute; top: -4px; right: -8px;
  background: #e94560; color: white; font-size: 10px; font-weight: 700;
  width: 18px; height: 18px; border-radius: 50%; display: flex;
  align-items: center; justify-content: center;
}

.badge-info { display: flex; flex-direction: column; gap: 2px; }
.badge-name { font-size: 12px; font-weight: 600; color: #1d1d1f; }
.badge-condition { font-size: 10px; color: #86868b; }
.badge-progress-bar {
  width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden;
}
.badge-progress-fill { height: 100%; background: #3b82f6; border-radius: 2px; transition: width 0.3s; }
.badge-progress-text { font-size: 10px; color: #6b7280; }

.badge-earned-time { font-size: 10px; color: #92400e; }

.badge-loading { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.badge-skeleton {
  height: 100px; border-radius: 12px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

.badge-error, .badge-empty { text-align: center; padding: 20px; color: #86868b; }
.badge-error button { margin-left: 8px; padding: 4px 12px; background: #1d1d1f; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
</style>
