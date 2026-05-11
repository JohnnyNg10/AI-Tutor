<template>
  <div class="profile-page" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="user-section">
        <div class="user-avatar-large">
          <span>{{ userInfo.avatar }}</span>
        </div>
        <div class="user-info" v-show="!isSidebarCollapsed">
          <span class="user-name">{{ userInfo.name }}</span>
          <span class="user-level">学习画像</span>
        </div>
      </div>

      <button class="toggle-btn" @click.stop="toggleSidebar">
        {{ isSidebarCollapsed ? '→' : '←' }}
      </button>

      <div class="quick-nav" v-show="!isSidebarCollapsed">
        <router-link to="/ai-tutor" class="nav-item">
          <span class="nav-icon">💬</span><span>AI 提问</span>
        </router-link>
        <router-link to="/recommend" class="nav-item">
          <span class="nav-icon">✨</span><span>智能推荐</span>
        </router-link>
        <router-link to="/mistake-book" class="nav-item">
          <span class="nav-icon">📝</span><span>练习中心</span>
        </router-link>
        <router-link to="/profile" class="nav-item active">
          <span class="nav-icon">📊</span><span>学习画像</span>
        </router-link>
      </div>

      <div class="sidebar-footer" v-show="!isSidebarCollapsed">
        <button class="logout-btn" @click="logout">
          <span>🚪</span><span>退出登录</span>
        </button>
      </div>
    </aside>

    <div class="content main-content">
      <div class="header-row">
        <h1>📊 学习画像与掌握度</h1>
        <button class="refresh-btn" :disabled="loading" @click="loadAll">
          {{ loading ? '加载中...' : '刷新数据' }}
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <!-- 骨架屏加载 -->
      <template v-if="loading">
        <div class="skeleton-card"></div>
        <div class="skeleton-card short"></div>
        <div class="skeleton-card short"></div>
      </template>

      <template v-else>
      <section class="card">
        <h2>能力曲线（最近记录）</h2>
        <div v-if="chartData.points.length === 0" class="empty">暂无能力曲线数据</div>
        <div v-else>
          <div class="ability-chart-wrap">
            <svg class="ability-chart" :viewBox="`0 0 ${chartData.width} ${chartData.height}`" preserveAspectRatio="none">
              <line
                v-for="tick in chartData.yTicks"
                :key="`grid-${tick.label}`"
                :x1="chartData.padding.left"
                :x2="chartData.width - chartData.padding.right"
                :y1="tick.y"
                :y2="tick.y"
                class="grid-line"
              />

              <text
                v-for="tick in chartData.yTicks"
                :key="`label-y-${tick.label}`"
                :x="chartData.padding.left - 10"
                :y="tick.y + 4"
                class="axis-label y-label"
              >
                {{ tick.label }}
              </text>

              <line
                v-for="tick in chartData.xTicks"
                :key="`label-x-${tick.index}`"
                :x1="tick.x"
                :x2="tick.x"
                :y1="chartData.padding.top"
                :y2="chartData.height - chartData.padding.bottom"
                class="grid-line vertical"
              />

              <path :d="chartData.areaPath" class="ci-area" />
              <path :d="chartData.linePath" class="theta-line" />

              <circle
                v-for="point in chartData.points"
                :key="`point-${point.index}`"
                :cx="point.x"
                :cy="point.y"
                r="3.5"
                class="theta-point"
              >
                <title>{{ point.tooltip }}</title>
              </circle>

              <line
                :x1="chartData.padding.left"
                :x2="chartData.padding.left"
                :y1="chartData.padding.top"
                :y2="chartData.height - chartData.padding.bottom"
                class="axis-line"
              />
              <line
                :x1="chartData.padding.left"
                :x2="chartData.width - chartData.padding.right"
                :y1="chartData.height - chartData.padding.bottom"
                :y2="chartData.height - chartData.padding.bottom"
                class="axis-line"
              />

              <text
                v-for="tick in chartData.xTicks"
                :key="`x-tick-${tick.index}`"
                :x="tick.x"
                :y="chartData.height - chartData.padding.bottom + 20"
                class="axis-label x-label"
              >
                {{ tick.label }}
              </text>
            </svg>
          </div>

          <div class="chart-legend">
            <span><i class="legend-line"></i>θ 能力值</span>
            <span><i class="legend-area"></i>95% 置信区间</span>
          </div>

          <div class="curve-list">
            <div v-for="(item, idx) in dashboard.ability_curve.slice(-10)" :key="idx" class="curve-item">
              <div class="curve-head">
                <span>{{ formatTime(item.time) }}</span>
                <strong>θ={{ safeNum(item.theta) }}</strong>
              </div>
              <div class="curve-ci">CI: [{{ safeNum(item.theta_ci_lower) }}, {{ safeNum(item.theta_ci_upper) }}]</div>
            </div>
          </div>
        </div>
      </section>

      <section class="grid-two">
        <div class="card">
          <h2>掌握度雷达维度（Top）</h2>
          <div v-if="dashboard.radar_dimensions.length === 0" class="empty">暂无掌握度数据</div>
          <div v-else>
            <div v-for="item in dashboard.radar_dimensions" :key="item.knowledge_point" class="progress-row">
              <div class="label">{{ item.knowledge_point }}</div>
              <div class="bar-wrap">
                <div class="bar" :class="item.color" :style="{ width: `${Math.round((item.mastery || 0) * 100)}%` }"></div>
              </div>
              <div class="value">{{ Math.round((item.mastery || 0) * 100) }}%</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>错题分布（按知识点）</h2>
          <div v-if="distributionList.length === 0" class="empty">暂无错题分布数据</div>
          <div v-else>
            <div v-for="item in distributionList" :key="item.kp" class="distribution-row">
              <span>{{ item.kp }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </div>
      </section>

      <!-- 六维能力雷达图 -->
      <section class="six-dim-section">
        <SixDimRadarChart :user-id="userId" />
      </section>

      <!-- 知识树进度 -->
      <section class="knowledge-tree-section">
        <KnowledgeTree :user-id="userId" />
      </section>

      <!-- 学习徽章墙 -->
      <section class="badge-section">
        <LearningBadgeWall />
      </section>

      <!-- 雷区与攻克成就 -->
      <section class="pitfall-section">
        <PitfallAchievement />
      </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import SixDimRadarChart from '../components/SixDimRadarChart.vue'
import KnowledgeTree from '../components/KnowledgeTree.vue'
import LearningBadgeWall from '../components/LearningBadgeWall.vue'
import PitfallAchievement from '../components/PitfallAchievement.vue'
import { useRouter } from 'vue-router'
import { ensureCurrentUserId } from '../services/apiService'

const router = useRouter()
const isSidebarCollapsed = ref(false)
const toggleSidebar = () => { isSidebarCollapsed.value = !isSidebarCollapsed.value }
const userInfo = ref({ name: '', avatar: '👤' })

const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
  router.push('/login')
}

const loading = ref(false)
const error = ref('')
const userId = ref(null)

const dashboard = ref({
  radar_dimensions: [],
  ability_curve: [],
  mistake_distribution: {},
})



const distributionList = computed(() => {
  const raw = dashboard.value?.mistake_distribution || {}
  return Object.entries(raw)
    .map(([kp, count]) => ({ kp, count: Number(count) || 0 }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12)
})

const chartData = computed(() => {
  const width = 820
  const height = 300
  const padding = { top: 20, right: 20, bottom: 38, left: 52 }

  const source = (dashboard.value?.ability_curve || [])
    .map((item, index) => {
      const theta = Number(item?.theta)
      const lower = Number(item?.theta_ci_lower)
      const upper = Number(item?.theta_ci_upper)
      const parsedTime = item?.time ? new Date(item.time) : null
      return {
        index,
        time: item?.time,
        displayTime: parsedTime && !Number.isNaN(parsedTime.getTime())
          ? parsedTime.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
          : '-',
        theta,
        lower: Number.isFinite(lower) ? lower : theta,
        upper: Number.isFinite(upper) ? upper : theta,
      }
    })
    .filter((item) => Number.isFinite(item.theta))

  if (source.length === 0) {
    return {
      width,
      height,
      padding,
      points: [],
      yTicks: [],
      xTicks: [],
      linePath: '',
      areaPath: '',
    }
  }

  const allValues = source.flatMap((item) => [item.theta, item.lower, item.upper]).filter(Number.isFinite)
  let minY = Math.min(...allValues)
  let maxY = Math.max(...allValues)

  if (minY === maxY) {
    minY -= 0.5
    maxY += 0.5
  }

  const extra = (maxY - minY) * 0.12
  minY -= extra
  maxY += extra

  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const xStep = source.length > 1 ? plotWidth / (source.length - 1) : 0

  const toX = (idx) => (source.length === 1 ? padding.left + plotWidth / 2 : padding.left + idx * xStep)
  const toY = (value) => {
    const ratio = (value - minY) / (maxY - minY)
    return padding.top + (1 - ratio) * plotHeight
  }

  const points = source.map((item, idx) => {
    const x = toX(idx)
    const y = toY(item.theta)
    return {
      ...item,
      x,
      y,
      lowerY: toY(item.lower),
      upperY: toY(item.upper),
      tooltip: `${item.displayTime} | θ=${item.theta.toFixed(2)} | CI=[${item.lower.toFixed(2)}, ${item.upper.toFixed(2)}]`,
    }
  })

  const linePath = points
    .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ')

  const upperPath = points
    .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.upperY.toFixed(2)}`)
    .join(' ')
  const lowerPath = [...points]
    .reverse()
    .map((point) => `L ${point.x.toFixed(2)} ${point.lowerY.toFixed(2)}`)
    .join(' ')
  const areaPath = `${upperPath} ${lowerPath} Z`

  const yTicks = Array.from({ length: 5 }, (_, idx) => {
    const value = maxY - ((maxY - minY) * idx) / 4
    return { y: toY(value), label: value.toFixed(2) }
  })

  const xTickCount = Math.min(5, points.length)
  const xTickIndexes = Array.from({ length: xTickCount }, (_, idx) => {
    if (xTickCount === 1) return 0
    return Math.round((idx * (points.length - 1)) / (xTickCount - 1))
  })

  const xTicks = [...new Set(xTickIndexes)].map((idx) => ({
    index: idx,
    x: points[idx].x,
    label: points[idx].displayTime,
  }))

  return {
    width,
    height,
    padding,
    points,
    yTicks,
    xTicks,
    linePath,
    areaPath,
  }
})

const safeNum = (v) => (typeof v === 'number' ? v.toFixed(2) : '-')
const pct = (v) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '-')
const formatTime = (t) => (t ? new Date(t).toLocaleString() : '-')


const loadAll = async () => {
  loading.value = true
  error.value = ''
  try {
    userId.value = await ensureCurrentUserId()
    const stored = localStorage.getItem('user_info')
    if (stored) {
      const info = JSON.parse(stored)
      userInfo.value.name = info.username || info.name || '用户'
      userInfo.value.avatar = info.avatar || '👤'
    }

    const token = localStorage.getItem('access_token')
    const headers = { 'Authorization': `Bearer ${token}` }

    // 获取掌握度可视化数据
    try {
      const masteryRes = await fetch('/api/mastery/visualization', { headers }).then(r => r.json())
      if (masteryRes.success && masteryRes.mastery_levels?.length) {
        dashboard.value.radar_dimensions = masteryRes.mastery_levels.map(m => ({
          knowledge_point: m.knowledge_point_name,
          mastery: m.p_known,
          color: m.p_known >= 0.8 ? 'green' : m.p_known >= 0.5 ? 'yellow' : 'red'
        }))
      }
    } catch {}

    // 获取画像数据（当前快照 + 历史曲线）
    try {
      const advisorRes = await fetch('/api/advisor/profile', { headers }).then(r => r.json())
      if (advisorRes.success && advisorRes.data) {
        const d = advisorRes.data
        dashboard.value.ability_curve = [{
          time: new Date().toISOString(),
          theta: d.theta || 0,
          theta_ci_lower: Math.max(0, (d.theta || 0) - 1.96 * (d.theta_se || 0.7)),
          theta_ci_upper: (d.theta || 0) + 1.96 * (d.theta_se || 0.7)
        }]
        if (d.knowledge_mastery) {
          dashboard.value.mistake_distribution = d.knowledge_mastery
        }
      }
    } catch {}

    // 获取能力历史曲线
    try {
      const histRes = await fetch('/api/six-dim-ability/history?days=30', { headers }).then(r => r.json())
      if (histRes.success && histRes.history?.length) {
        dashboard.value.ability_curve = histRes.history.map(h => ({
          time: h.time || h.timestamp || h.created_at,
          theta: h.theta ?? h.logical_reasoning ?? 0,
          theta_ci_lower: Math.max(0, (h.theta || h.logical_reasoning || 0) - 1),
          theta_ci_upper: (h.theta || h.logical_reasoning || 0) + 1
        }))
      }
    } catch {}
  } catch (e) {
    error.value = e?.message || '加载学习画像失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
/* ===== 布局 ===== */
.profile-page {
  display: flex;
  min-height: 100vh;
  background: #f5f7fb;
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 240px;
  height: 100vh;
  background: linear-gradient(160deg, #1e3a5f 0%, #2563eb 100%);
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  z-index: 100;
  transition: width 0.3s ease;
  overflow: hidden;
}

.profile-page.sidebar-collapsed .sidebar { width: 64px; }
.profile-page.sidebar-collapsed .main-content { margin-left: 64px; }

.main-content { margin-left: 240px; flex: 1; transition: margin-left 0.3s ease; }

.user-section {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.15);
}

.user-avatar-large {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.user-info { display: flex; flex-direction: column; overflow: hidden; }
.user-name { color: white; font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-level { color: rgba(255,255,255,0.65); font-size: 12px; margin-top: 2px; }

.toggle-btn {
  align-self: flex-end;
  background: rgba(255,255,255,0.15);
  border: none;
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.quick-nav { display: flex; flex-direction: column; gap: 4px; flex: 1; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  color: rgba(255,255,255,0.8);
  text-decoration: none;
  font-size: 14px;
  transition: background 0.2s;
  white-space: nowrap;
}

.nav-item:hover { background: rgba(255,255,255,0.15); color: white; }
.nav-item.active { background: rgba(255,255,255,0.25); color: white; font-weight: 600; }
.nav-icon { font-size: 18px; width: 24px; text-align: center; flex-shrink: 0; }

.sidebar-footer { margin-top: auto; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.15); }

.logout-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: rgba(255,255,255,0.1);
  border: none;
  border-radius: 10px;
  color: rgba(255,255,255,0.85);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}
.logout-btn:hover { background: rgba(255,255,255,0.2); }

/* ===== 内容区 ===== */
.content { padding: 28px; max-width: 1100px; margin: 0 auto; }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.sub { color: #666; margin-bottom: 12px; }
.error { color: #d93025; margin-bottom: 12px; }

/* ====== 骨架屏 ====== */
.skeleton-card {
  height: 140px; border-radius: 14px; margin-bottom: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite;
}
.skeleton-card.short { height: 80px; }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
.refresh-btn { border: none; background: #1d4ed8; color: #fff; padding: 8px 14px; border-radius: 8px; cursor: pointer; }
.refresh-btn:disabled { opacity: .65; cursor: not-allowed; }
.card { background: #fff; border: 1px solid #e9edf2; border-radius: 14px; padding: 16px; margin-bottom: 16px; }
.card h2 { font-size: 16px; margin-bottom: 12px; }
.empty { color: #888; font-size: 14px; }
.grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.ability-chart-wrap {
  width: 100%;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  background: linear-gradient(180deg, #f9fbff 0%, #ffffff 100%);
  padding: 8px 8px 2px;
  overflow: hidden;
}
.ability-chart {
  width: 100%;
  height: 290px;
  display: block;
}
.grid-line {
  stroke: #e8edf5;
  stroke-width: 1;
}
.grid-line.vertical {
  stroke-dasharray: 4 4;
}
.axis-line {
  stroke: #cdd6e3;
  stroke-width: 1.2;
}
.axis-label {
  fill: #7b8794;
  font-size: 11px;
}
.y-label {
  text-anchor: end;
}
.x-label {
  text-anchor: middle;
}
.ci-area {
  fill: rgba(37, 99, 235, 0.16);
}
.theta-line {
  fill: none;
  stroke: #2563eb;
  stroke-width: 2.2;
}
.theta-point {
  fill: #2563eb;
  stroke: #ffffff;
  stroke-width: 1.5;
}
.chart-legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin: 10px 0 12px;
  color: #4b5563;
  font-size: 12px;
}
.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend-line {
  width: 18px;
  height: 0;
  border-top: 2px solid #2563eb;
}
.legend-area {
  width: 16px;
  height: 10px;
  background: rgba(37, 99, 235, 0.18);
  border: 1px solid rgba(37, 99, 235, 0.28);
}
.curve-list { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.curve-item { border: 1px solid #eef1f5; border-radius: 10px; padding: 10px; }
.curve-head { display: flex; justify-content: space-between; font-size: 13px; color: #444; }
.curve-ci { font-size: 12px; color: #6b7280; margin-top: 4px; }
.progress-row { display: grid; grid-template-columns: 160px 1fr 64px; gap: 10px; align-items: center; margin-bottom: 10px; }
.label { font-size: 13px; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-wrap { height: 10px; border-radius: 999px; background: #edf1f5; overflow: hidden; }
.bar { height: 100%; border-radius: 999px; }
.bar.green { background: #16a34a; }
.bar.yellow { background: #f59e0b; }

/* 六维能力雷达图区域 */
.six-dim-section {
  margin-top: 24px;
}

.six-dim-section :deep(.six-dim-radar) {
  margin: 0;
}

/* 知识树区域 */
.knowledge-tree-section {
  margin-top: 24px;
}

.knowledge-tree-section :deep(.knowledge-tree) {
  margin: 0;
}
.badge-section, .pitfall-section {
  margin-top: 24px;
}
.bar.red { background: #ef4444; }
.value { text-align: right; font-size: 12px; color: #6b7280; }
.distribution-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #eef1f5; font-size: 13px; }
.stats { display: grid; gap: 8px; color: #374151; font-size: 14px; }

@media (max-width: 900px) {
  .sidebar { width: 64px; }
  .main-content { margin-left: 64px; }
  .user-info, .quick-nav span:last-child, .logout-btn span:last-child, .user-level { display: none; }
  .grid-two { grid-template-columns: 1fr; }
  .ability-chart { height: 240px; }
  .axis-label { font-size: 10px; }
  .curve-list { grid-template-columns: 1fr; }
  .progress-row { grid-template-columns: 1fr; }
}
</style>
