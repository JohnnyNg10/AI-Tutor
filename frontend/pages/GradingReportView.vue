<template>
  <AppLayout>
    <div class="report-page">
      <!-- Top Bar per Figma: export/share (right side) + back link (left side) -->
      <div class="report-topbar">
        <div class="topbar-actions">
          <button class="action-link">导出</button>
          <button class="action-link">分享</button>
        </div>
        <router-link to="/grading" class="back-link">
          <ArrowLeft :size="16" />
          返回列表
        </router-link>
      </div>

      <div v-if="loading" class="loading"><div class="spinner"></div></div>
      <div v-else-if="error" class="error">{{ error }}</div>

      <template v-else-if="report">
        <!-- Overview Card -->
        <div class="figma-card">
          <div class="overview-header">
            <h2>{{ report.title || '批改报告' }}</h2>
            <span class="report-date">{{ formatDate(report.created_at) }}</span>
          </div>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value">{{ report.avg_score || 0 }}</div>
              <div class="stat-label">得分率</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ report.correct_count || 0 }}/{{ report.question_count || 0 }}</div>
              <div class="stat-label">正确</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ report.weak_kp_count || 0 }}个</div>
              <div class="stat-label">薄弱点</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ report.top_error_type || '-' }}</div>
              <div class="stat-label">主要错误</div>
            </div>
          </div>
        </div>

        <!-- Per-Question Details -->
        <div class="figma-card">
          <h3 class="section-title">逐题批改详情</h3>
          <div class="question-list">
            <div v-for="(q, i) in (report.questions || [])" :key="i" class="q-item">
              <button class="q-toggle" :class="q.is_correct ? 'q-correct' : 'q-wrong'" @click="q._open = !q._open">
                <span>{{ q._open ? '▼' : '▶' }} 第{{ i + 1 }}题</span>
                <span class="q-status">{{ q.is_correct ? '正确' : '错误' }}</span>
                <span class="q-kp">{{ q.knowledge_points?.[0] || '' }}</span>
              </button>
              <div v-if="q._open" class="q-detail">
                <p><strong>题目：</strong>{{ q.question_content }}</p>
                <p v-if="q.user_answer"><strong>你的答案：</strong>{{ q.user_answer }}</p>
                <p v-if="q.score !== undefined"><strong>评分：</strong>{{ q.score }}分</p>
                <p v-if="q.knowledge_points?.length"><strong>知识点：</strong>{{ q.knowledge_points.join('、') }}</p>
                <p v-if="q.feedback" class="q-feedback"><strong>AI评语：</strong>{{ q.feedback }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Error Distribution -->
        <div class="figma-card" v-if="report.error_distribution?.length">
          <h3 class="section-title">错因分布</h3>
          <div class="error-list">
            <div v-for="e in report.error_distribution" :key="e.type" class="error-row">
              <span class="error-type">{{ e.type }}</span>
              <span class="error-count">{{ e.count }}次 ({{ e.percentage }}%)</span>
              <div class="error-bar-bg"><div class="error-bar-fill" :style="{ width: e.percentage + '%' }"></div></div>
            </div>
          </div>
        </div>

        <!-- Knowledge Point Performance -->
        <div class="figma-card" v-if="report.kp_mastery?.length">
          <h3 class="section-title">知识点表现</h3>
          <div class="kp-list">
            <div v-for="kp in report.kp_mastery" :key="kp.name" class="kp-row">
              <span class="kp-name">{{ kp.name }}</span>
              <div class="kp-bar-bg"><div class="kp-bar-fill" :class="kpClass(kp.level)" :style="{ width: kp.mastery + '%' }"></div></div>
              <span class="kp-pct">{{ kp.mastery }}%</span>
              <span class="kp-level" :class="'lv-' + (kp.level || 'solid')">{{ kp.level_label || kp.level }}</span>
            </div>
          </div>
        </div>

        <!-- AI Suggestions -->
        <div class="figma-card">
          <h3 class="section-title">AI 学习建议</h3>
          <div class="suggestions-list">
            <div v-for="(s, i) in (report.suggestions?.length ? report.suggestions : defaultSuggestions)" :key="i" class="suggestion-item">
              <span>{{ s }}</span>
            </div>
          </div>
          <div class="encouragement">{{ report.encouragement || '趁热打铁，加油！' }}</div>
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
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowRight } from 'lucide-vue-next'
import AppLayout from '../components/AppLayout.vue'
import { gradingAPI } from '../services/grading-api.js'

const route = useRoute()
const loading = ref(false)
const error = ref('')
const report = ref(null)

const defaultSuggestions = [
  '优先攻克薄弱知识点，建议从掌握度最低的章节开始练习',
  '加强练习：多做一些综合应用题，提高跨知识点运用能力',
  '已掌握的知识点请定期复习，保持记忆曲线',
]

function kpClass(level) {
  if (level === 'mastered' || level === '精通') return 'kp-mastered'
  if (level === 'weak' || level === '薄弱') return 'kp-weak'
  return 'kp-solid'
}

async function loadReport() {
  const sessionId = route.params.sessionId
  if (!sessionId) { error.value = '缺少批改会话ID'; return }
  loading.value = true
  error.value = ''
  try {
    const res = await gradingAPI.getReport(sessionId)
    report.value = res?.data || res
    if (!report.value.questions?.length) {
      const detailRes = await gradingAPI.getResult(sessionId)
      const detail = detailRes?.data || detailRes
      report.value = { ...report.value, questions: detail.questions || [] }
    }
    // Initialize expansion state
    if (report.value.questions) {
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

/* Top Bar */
.report-topbar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px;
}
.back-link { display: inline-flex; align-items: center; gap: 4px; color: #0E61AC; text-decoration: none; font-size: 14px; }
.back-link:hover { opacity: 0.8; }
.topbar-actions { display: flex; gap: 12px; }
.action-link { background: none; border: none; color: #86868B; font-size: 14px; cursor: pointer; font-family: var(--font-family); }
.action-link:hover { color: #0E61AC; }

.loading { display: flex; justify-content: center; padding: 80px 0; }
.error { color: var(--color-error); padding: 16px; }

/* Cards */
.figma-card {
  background: #fff; border-radius: 16px; padding: 24px; margin-bottom: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.section-title { font-size: 16px; font-weight: 600; color: #1B1B1B; margin-bottom: 16px; }

/* Overview */
.overview-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 20px; }
.overview-header h2 { font-size: 18px; font-weight: 700; color: #1B1B1B; }
.report-date { font-size: 13px; color: #86868B; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card {
  background: #FAF2E0; border-radius: 12px; padding: 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.stat-value { font-size: 24px; font-weight: 700; color: #0E61AC; }
.stat-label { font-size: 12px; color: #86868B; }

/* Questions */
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
.q-status { font-weight: 600; }
.q-kp { color: #86868B; font-size: 13px; }
.q-detail { padding: 12px; background: #FAF2E0; border-radius: 8px; margin-top: 4px; font-size: 13px; line-height: 1.7; color: #454545; }
.q-detail p { margin-bottom: 4px; }
.q-feedback { color: #1B1B1B; }

/* Error Distribution */
.error-list { display: flex; flex-direction: column; gap: 10px; }
.error-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.error-type { width: 80px; color: #1B1B1B; flex-shrink: 0; }
.error-count { width: 90px; color: #86868B; font-size: 12px; flex-shrink: 0; }
.error-bar-bg { flex: 1; height: 8px; background: #EEEEEE; border-radius: 4px; overflow: hidden; }
.error-bar-fill { height: 100%; background: #0E61AC; border-radius: 4px; transition: width 0.5s; }

/* KP Performance */
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
.lv-mastered, .lv-精通 { color: #10b981; }
.lv-solid, .lv-稳固 { color: #0E61AC; }
.lv-weak, .lv-薄弱, .lv-需巩固 { color: #dc2626; }

/* Suggestions */
.suggestions-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.suggestion-item { font-size: 14px; color: #454545; line-height: 1.6; padding-left: 12px; border-left: 2px solid #0E61AC; }
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
