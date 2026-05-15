<template>
  <AppLayout>
    <div class="content">
      <div class="header-row">
        <h1>
          <BarChart3 :size="24" />
          学习画像与掌握度
        </h1>
        <button class="btn btn-primary" :disabled="loading" @click="loadAll">
          {{ loading ? '加载中...' : '刷新数据' }}
        </button>
      </div>

      <p class="sub">用户ID：{{ userId || '-' }}</p>
      <p v-if="error" class="error">{{ error }}</p>

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

      <section class="grid-two">
        <div class="card">
          <h2>A/B 统计（Control）</h2>
          <div v-if="abStats.control" class="stats">
            <div>记录数：{{ abStats.control.total_records }}</div>
            <div>正确率：{{ pct(abStats.control.accuracy) }}</div>
            <div>平均难度：{{ safeNum(abStats.control.avg_difficulty) }}</div>
            <div>平均耗时：{{ safeNum(abStats.control.avg_time_spent) }}s</div>
          </div>
          <div v-else class="empty">暂无数据</div>
        </div>

        <div class="card">
          <h2>A/B 统计（Treatment）</h2>
          <div v-if="abStats.treatment" class="stats">
            <div>记录数：{{ abStats.treatment.total_records }}</div>
            <div>正确率：{{ pct(abStats.treatment.accuracy) }}</div>
            <div>平均难度：{{ safeNum(abStats.treatment.avg_difficulty) }}</div>
            <div>平均耗时：{{ safeNum(abStats.treatment.avg_time_spent) }}s</div>
          </div>
          <div v-else class="empty">暂无数据</div>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { BarChart3 } from 'lucide-vue-next'
import AppLayout from '../components/AppLayout.vue'
import { ensureCurrentUserId, exercisesAPI } from '../services/apiService'

const loading = ref(false)
const error = ref('')
const userId = ref(null)

const dashboard = ref({
  radar_dimensions: [],
  ability_curve: [],
  mistake_distribution: {},
})

const abStats = ref({
  control: null,
  treatment: null,
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
    const [dashboardRes, controlRes, treatmentRes] = await Promise.all([
      exercisesAPI.getMasteryDashboard({ userId: userId.value, trendLimit: 30 }),
      exercisesAPI.getAbTestStats({ algorithmVersion: 'control', limit: 1000 }),
      exercisesAPI.getAbTestStats({ algorithmVersion: 'treatment', limit: 1000 }),
    ])

    dashboard.value = dashboardRes?.data || dashboard.value
    abStats.value = {
      control: controlRes?.data || null,
      treatment: treatmentRes?.data || null,
    }
  } catch (e) {
    error.value = e?.message || '加载学习画像失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.content { padding: 32px; max-width: var(--max-content-width); margin: 0 auto; }

.header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.header-row h1 { font-size: var(--font-xxl); font-weight: 700; color: var(--color-text-title); display: flex; align-items: center; gap: 10px; }

.sub { color: var(--color-text-secondary); margin-bottom: 12px; font-size: var(--font-base); }
.error { color: var(--color-error); margin-bottom: 12px; }

.card {
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  padding: 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-subtle);
}
.card h2 { font-size: var(--font-md); font-weight: 600; color: var(--color-text-title); margin-bottom: 12px; }

.empty { color: var(--color-text-secondary); font-size: var(--font-base); }
.grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.ability-chart-wrap {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-bg-white);
  padding: 8px 8px 2px;
  overflow: hidden;
}
.ability-chart { width: 100%; height: 290px; display: block; }

.grid-line { stroke: var(--color-border); stroke-width: 1; }
.grid-line.vertical { stroke-dasharray: 4 4; }
.axis-line { stroke: var(--color-text-secondary); stroke-width: 1.2; }
.axis-label { fill: var(--color-text-secondary); font-size: 11px; }
.y-label { text-anchor: end; }
.x-label { text-anchor: middle; }
.ci-area { fill: rgba(14, 97, 172, 0.16); }
.theta-line { fill: none; stroke: var(--color-primary); stroke-width: 2.2; }
.theta-point { fill: var(--color-primary); stroke: #fff; stroke-width: 1.5; }

.chart-legend {
  display: flex; gap: 18px; flex-wrap: wrap;
  margin: 10px 0 12px;
  color: var(--color-text-body); font-size: 12px;
}
.chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend-line { width: 18px; height: 0; border-top: 2px solid var(--color-primary); }
.legend-area { width: 16px; height: 10px; background: rgba(14, 97, 172, 0.18); border: 1px solid rgba(14, 97, 172, 0.28); }

.curve-list { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.curve-item { border: 1px solid var(--color-border); border-radius: 10px; padding: 10px; }
.curve-head { display: flex; justify-content: space-between; font-size: 13px; color: var(--color-text-body); }
.curve-ci { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }

.progress-row { display: grid; grid-template-columns: 160px 1fr 64px; gap: 10px; align-items: center; margin-bottom: 10px; }
.label { font-size: 13px; color: var(--color-text-body); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-wrap { height: 10px; border-radius: var(--radius-full); background: var(--color-border); overflow: hidden; }
.bar { height: 100%; border-radius: var(--radius-full); }
.bar.green { background: var(--color-success); }
.bar.yellow { background: var(--color-warning); }
.bar.red { background: var(--color-error); }
.value { text-align: right; font-size: 12px; color: var(--color-text-secondary); }

.distribution-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--color-border); font-size: 13px; }
.stats { display: grid; gap: 8px; color: var(--color-text-body); font-size: 14px; }

@media (max-width: 900px) {
  .grid-two { grid-template-columns: 1fr; }
  .ability-chart { height: 240px; }
  .axis-label { font-size: 10px; }
  .curve-list { grid-template-columns: 1fr; }
  .progress-row { grid-template-columns: 1fr; }
}
</style>
