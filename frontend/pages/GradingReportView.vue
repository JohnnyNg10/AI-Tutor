<template>
  <AppLayout>
    <div class="report-page">
      <!-- Top Bar per Figma -->
      <div class="report-topbar">
        <div class="topbar-actions">
          <button class="action-link" disabled>导出</button>
          <button class="action-link" disabled>分享</button>
        </div>
        <router-link to="/grading" class="back-link">
          <ArrowLeft :size="16" />
          返回列表
        </router-link>
      </div>

      <div v-if="loading" class="loading"><div class="spinner"></div></div>
      <div v-else-if="error" class="error">{{ error }}</div>

      <template v-else-if="report">
        <!-- Overview Card per Figma -->
        <div class="figma-card">
          <div class="overview-header">
            <h2>{{ report.title || '批改报告' }}</h2>
            <span class="report-date">{{ formatDate(report.created_at) }}</span>
          </div>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value">{{ report.avg_score || 0 }}<span class="stat-unit">分</span></div>
              <div class="stat-label">平均得分</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ correctCount }}/{{ report.question_count || 0 }}</div>
              <div class="stat-label">正确题数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ report.weakest_kps?.length || 0 }}个</div>
              <div class="stat-label">薄弱知识点</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ topErrorType || '-' }}</div>
              <div class="stat-label">主要错误类型</div>
            </div>
          </div>
        </div>

        <!-- Per-Question Details per Figma -->
        <div class="figma-card">
          <h3 class="section-title">逐题批改详情</h3>
          <div class="question-list">
            <div v-for="(q, i) in (report.questions || [])" :key="i" class="q-item">
              <button
                class="q-toggle"
                :class="q.is_correct ? 'q-correct' : 'q-wrong'"
                @click="q._open = !q._open"
              >
                <span>{{ q._open ? '▼' : '▶' }} 第{{ i + 1 }}题</span>
                <span class="q-status">{{ q.is_correct ? '✓ 正确' : '✗ 错误' }}</span>
                <span v-if="q.knowledge_points?.length" class="q-kp">{{ q.knowledge_points[0] }}</span>
              </button>
              <div v-if="q._open" class="q-detail">
                <p><strong>题目：</strong>{{ q.question_text || '（无题目文本）' }}</p>
                <p v-if="q.student_answer"><strong>你的答案：</strong>{{ q.student_answer }}</p>
                <p v-if="q.score !== undefined"><strong>得分：</strong>{{ q.score }}分</p>
                <p v-if="q.error_type"><strong>错误类型：</strong>{{ q.error_type }}</p>
                <p v-if="q.knowledge_points?.length"><strong>知识点：</strong>{{ q.knowledge_points.join('、') }}</p>
                <p v-if="q.error_tags?.length"><strong>标签：</strong>{{ q.error_tags.join('、') }}</p>
                <p v-if="q.grading_result?.improvement_suggestion" class="q-feedback">
                  <strong>AI学习建议：</strong>{{ q.grading_result.improvement_suggestion }}
                </p>
                <div v-if="q.grading_result?.steps?.length" class="q-steps">
                  <p><strong>解题步骤分析：</strong></p>
                  <div v-for="(step, si) in q.grading_result.steps" :key="si" class="q-step">
                    <span class="step-badge" :class="step.status">{{ stepStatusLabel(step.status) }}</span>
                    <span>{{ step.step_content }}</span>
                    <span v-if="step.analysis" class="step-analysis">{{ step.analysis }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Error Distribution per Figma -->
        <div class="figma-card" v-if="errorDistribution.length">
          <h3 class="section-title">错因分布</h3>
          <div class="error-list">
            <div v-for="e in errorDistribution" :key="e.type" class="error-row">
              <span class="error-type">{{ e.type }}</span>
              <span class="error-count">{{ e.count }}次 ({{ e.percentage }}%)</span>
              <div class="error-bar-bg">
                <div class="error-bar-fill" :style="{ width: e.percentage + '%' }"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Knowledge Point Performance per Figma -->
        <div class="figma-card" v-if="kpPerformance.length">
          <h3 class="section-title">知识点表现</h3>
          <div class="kp-list">
            <div v-for="kp in kpPerformance" :key="kp.name" class="kp-row">
              <span class="kp-name">{{ kp.name }}</span>
              <div class="kp-bar-bg">
                <div class="kp-bar-fill" :class="kpClass(kp.rate)" :style="{ width: (kp.rate * 100) + '%' }"></div>
              </div>
              <span class="kp-pct">{{ Math.round(kp.rate * 100) }}%</span>
              <span class="kp-level" :class="'lv-' + kpClass(kp.rate)">
                {{ kpLevelLabel(kp.rate) }}
              </span>
            </div>
          </div>
        </div>

        <!-- AI Study Suggestions per Figma -->
        <div class="figma-card">
          <h3 class="section-title">AI 学习建议</h3>
          <div class="suggestions-list">
            <div v-for="(s, i) in displaySuggestions" :key="i" class="suggestion-item">
              <span>{{ s }}</span>
            </div>
          </div>
          <div class="encouragement">趁热打铁，针对性练习巩固薄弱知识点！</div>
          <router-link to="/recommend" class="figma-btn-primary">
            开始针对性练习
            <ArrowRight :size="16" />
          </router-link>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowRight } from 'lucide-vue-next'
import AppLayout from '../components/AppLayout.vue'
import { gradingAPI } from '../services/grading-api.js'

const route = useRoute()
const loading = ref(false)
const error = ref('')
const report = ref(null)

const correctCount = computed(() => {
  const qs = report.value?.questions || []
  return qs.filter(q => q.is_correct).length
})

const topErrorType = computed(() => {
  const dist = report.value?.error_distribution
  if (!dist || typeof dist !== 'object') return null
  const entries = Object.entries(dist)
  if (!entries.length) return null
  entries.sort((a, b) => b[1] - a[1])
  const typeMap = {
    CONCEPT_ERROR: '概念错误', PROCESS_ERROR: '过程错误',
    CALCULATION_ERROR: '计算错误', READING_ERROR: '审题错误', FORMAT_ERROR: '格式错误'
  }
  return typeMap[entries[0][0]] || entries[0][0]
})

const errorDistribution = computed(() => {
  const dist = report.value?.error_distribution
  if (!dist || typeof dist !== 'object') return []
  const typeMap = {
    CONCEPT_ERROR: '概念错误', PROCESS_ERROR: '过程错误',
    CALCULATION_ERROR: '计算错误', READING_ERROR: '审题错误', FORMAT_ERROR: '格式错误'
  }
  const entries = Object.entries(dist)
  const total = entries.reduce((s, [, c]) => s + c, 0)
  return entries.map(([type, count]) => ({
    type: typeMap[type] || type,
    count,
    percentage: total > 0 ? Math.round((count / total) * 100) : 0
  }))
})

const kpPerformance = computed(() => {
  // Combine weakest + strongest KPs with rates
  const weakest = report.value?.weakest_kps || []
  const strongest = report.value?.strongest_kps || []
  const all = [...weakest, ...strongest]
  // Deduplicate by name
  const seen = new Set()
  return all.filter(kp => {
    if (seen.has(kp.name)) return false
    seen.add(kp.name)
    return true
  })
})

const displaySuggestions = computed(() => {
  // Collect AI improvement suggestions from grading results
  const qs = report.value?.questions || []
  const suggestions = qs
    .map(q => q.grading_result?.improvement_suggestion)
    .filter(Boolean)
  if (suggestions.length) return suggestions
  return [
    '优先攻克薄弱知识点，建议从掌握度最低的章节开始练习',
    '加强练习：多做一些综合应用题，提高跨知识点运用能力',
    '已掌握的知识点请定期复习，保持记忆曲线',
  ]
})

function kpClass(rate) {
  if (rate >= 0.8) return 'kp-mastered'
  if (rate >= 0.5) return 'kp-solid'
  return 'kp-weak'
}

function kpLevelLabel(rate) {
  if (rate >= 0.8) return '精通'
  if (rate >= 0.5) return '稳固'
  return '薄弱'
}

function stepStatusLabel(status) {
  if (status === 'correct') return '✓ 正确'
  if (status === 'incorrect') return '✗ 错误'
  if (status === 'partially_correct') return '△ 部分正确'
  return status
}

async function loadReport() {
  const sessionId = route.params.sessionId
  if (!sessionId) { error.value = '缺少批改会话ID'; return }
  loading.value = true
  error.value = ''
  try {
    const res = await gradingAPI.getReport(sessionId)
    const data = res?.data || res
    report.value = data
    // Initialize expansion state
    if (report.value?.questions) {
      report.value.questions.forEach(q => { q._open = false })
    }
  } catch (e) {
    error.value = e?.message || '加载报告失败'
  } finally {
    loading.value = false
  }
}

function formatDate(t) {
  if (!t) return '-'
  return new Date(t).toLocaleDateString('zh-CN')
}

onMounted(loadReport)
</script>

<style scoped>
.report-page { padding: 32px; max-width: 1000px; margin: 0 auto; padding-bottom: 80px; }

/* Top Bar per Figma */
.report-topbar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px;
}
.back-link { display: inline-flex; align-items: center; gap: 4px; color: #0E61AC; text-decoration: none; font-size: 14px; }
.back-link:hover { opacity: 0.8; }
.topbar-actions { display: flex; gap: 12px; }
.action-link { background: none; border: none; color: #86868B; font-size: 14px; cursor: pointer; font-family: var(--font-family); }
.action-link:disabled { opacity: 0.4; cursor: default; }

.loading { display: flex; justify-content: center; padding: 80px 0; }
.error { color: var(--color-error); padding: 16px; }

/* Cards per Figma */
.figma-card {
  background: #fff; border-radius: 16px; padding: 24px; margin-bottom: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.section-title { font-size: 16px; font-weight: 600; color: #1B1B1B; margin-bottom: 16px; }

/* Overview per Figma */
.overview-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 20px; }
.overview-header h2 { font-size: 18px; font-weight: 700; color: #1B1B1B; }
.report-date { font-size: 13px; color: #86868B; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card {
  background: #FAF2E0; border-radius: 12px; padding: 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.stat-value { font-size: 22px; font-weight: 700; color: #0E61AC; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 2px; }
.stat-label { font-size: 12px; color: #86868B; }

/* Question details per Figma */
.question-list { display: flex; flex-direction: column; gap: 8px; }
.q-item { border-bottom: 1px solid #EEEEEE; padding-bottom: 8px; }
.q-toggle {
  width: 100%; text-align: left; background: none; border: none; padding: 8px 0;
  font-size: 14px; cursor: pointer; display: flex; gap: 12px; align-items: center;
  font-family: var(--font-family); transition: color 0.15s;
}
.q-toggle:hover { opacity: 0.8; }
.q-correct { color: #0E61AC; }
.q-wrong { color: #dc2626; }
.q-status { font-weight: 600; font-size: 13px; }
.q-kp { color: #86868B; font-size: 13px; }
.q-detail {
  padding: 16px; background: #FAF2E0; border-radius: 8px; margin-top: 4px;
  font-size: 13px; line-height: 1.7; color: #454545;
}
.q-detail p { margin-bottom: 6px; }
.q-feedback { color: #0E61AC; }
.q-steps { margin-top: 8px; border-top: 1px solid #EEEEEE; padding-top: 8px; }
.q-step {
  display: flex; gap: 8px; align-items: flex-start; padding: 4px 0;
  font-size: 13px; color: #454545;
}
.step-badge {
  font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
  white-space: nowrap;
}
.step-badge.correct { background: #d1fae5; color: #065f46; }
.step-badge.incorrect { background: #fee2e2; color: #991b1b; }
.step-badge.partially_correct { background: #fef3c7; color: #92400e; }
.step-analysis { color: #86868B; font-size: 12px; flex: 1; }

/* Error Distribution per Figma */
.error-list { display: flex; flex-direction: column; gap: 10px; }
.error-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.error-type { width: 80px; color: #1B1B1B; flex-shrink: 0; }
.error-count { width: 90px; color: #86868B; font-size: 12px; flex-shrink: 0; }
.error-bar-bg { flex: 1; height: 8px; background: #EEEEEE; border-radius: 4px; overflow: hidden; }
.error-bar-fill { height: 100%; background: #0E61AC; border-radius: 4px; transition: width 0.5s; }

/* KP Performance per Figma */
.kp-list { display: flex; flex-direction: column; gap: 10px; }
.kp-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.kp-name { width: 120px; color: #1B1B1B; flex-shrink: 0; }
.kp-bar-bg { flex: 1; height: 8px; background: #EEEEEE; border-radius: 4px; overflow: hidden; }
.kp-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
.kp-mastered { background: #10b981; }
.kp-solid { background: #0E61AC; }
.kp-weak { background: #dc2626; }
.kp-pct { width: 40px; text-align: right; color: #86868B; font-size: 12px; flex-shrink: 0; }
.kp-level { width: 50px; text-align: right; font-size: 12px; flex-shrink: 0; }
.lv-kp-mastered { color: #10b981; }
.lv-kp-solid { color: #0E61AC; }
.lv-kp-weak { color: #dc2626; }

/* Suggestions per Figma */
.suggestions-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.suggestion-item {
  font-size: 14px; color: #454545; line-height: 1.6; padding-left: 12px;
  border-left: 2px solid #0E61AC;
}
.encouragement { font-size: 16px; font-weight: 600; color: #1B1B1B; margin-bottom: 16px; }
.figma-btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  background: #0E61AC; color: #FAF2E0; border: none; border-radius: 10px;
  padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer;
  transition: opacity 0.2s; font-family: var(--font-family); text-decoration: none;
}
.figma-btn-primary:hover { opacity: 0.85; }

@media (max-width: 768px) {
  .report-page { padding: 16px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
