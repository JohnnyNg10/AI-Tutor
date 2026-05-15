<template>
  <AppLayout>
    <div class="report-page">
      <div class="report-topbar">
        <router-link to="/grading" class="back-link">
          <ArrowLeft :size="16" />
          返回列表
        </router-link>
        <div class="topbar-actions">
          <button class="btn btn-secondary btn-sm">
            <Download :size="14" />
            导出
          </button>
          <button class="btn btn-secondary btn-sm">
            <Share2 :size="14" />
            分享
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="error">{{ error }}</div>

      <template v-else-if="report">
        <!-- Overview Card -->
        <div class="card overview-card">
          <div class="overview-header">
            <h2>{{ report.title || '批改报告' }}</h2>
            <span class="report-date">{{ formatDate(report.created_at) }}</span>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <Target :size="20" />
              <div class="stat-value">{{ report.avg_score || 0 }}</div>
              <div class="stat-label">平均分</div>
            </div>
            <div class="stat-item">
              <CheckCircle2 :size="20" />
              <div class="stat-value">{{ report.correct_count || 0 }}/{{ report.question_count || 0 }}</div>
              <div class="stat-label">正确</div>
            </div>
            <div class="stat-item">
              <AlertTriangle :size="20" />
              <div class="stat-value">{{ report.weak_kp_count || 0 }}个</div>
              <div class="stat-label">薄弱点</div>
            </div>
            <div class="stat-item">
              <TrendingDown :size="20" />
              <div class="stat-value">{{ report.top_error_type || '-' }}</div>
              <div class="stat-label">主要错误</div>
            </div>
          </div>
        </div>

        <!-- Per-Question Details -->
        <div class="section">
          <h3 class="section-title">逐题批改详情</h3>
          <div class="question-list">
            <QuestionGradingCard
              v-for="(q, i) in report.questions"
              :key="i"
              :index="i"
              :result="q"
            />
          </div>
        </div>

        <!-- Error Distribution -->
        <div class="section" v-if="report.error_distribution">
          <ErrorDistribution :distribution="report.error_distribution" />
        </div>

        <!-- Knowledge Point Performance -->
        <div class="section" v-if="report.kp_mastery">
          <KpPerformanceTable :kp-mastery="report.kp_mastery" />
        </div>

        <!-- AI Suggestions -->
        <div class="card suggestions-card" v-if="report.suggestions?.length">
          <h3 class="section-title">AI 学习建议</h3>
          <div class="suggestions-list">
            <div
              v-for="(s, i) in report.suggestions"
              :key="i"
              class="suggestion-item"
            >
              <Target v-if="i === 0" :size="18" class="sug-icon" />
              <BookOpen v-else-if="i === 1" :size="18" class="sug-icon" />
              <CheckCircle2 v-else :size="18" class="sug-icon" />
              <span>{{ s }}</span>
            </div>
          </div>
          <div class="encouragement" v-if="report.encouragement">
            {{ report.encouragement }}
          </div>
          <router-link to="/recommend" class="btn btn-primary cta-btn">
            开始针对性练习
            <ArrowRight :size="16" />
          </router-link>
        </div>

        <div class="card suggestions-card" v-else>
          <h3 class="section-title">AI 学习建议</h3>
          <div class="suggestions-list">
            <div class="suggestion-item">
              <Target :size="18" class="sug-icon" />
              <span>优先攻克薄弱知识点，建议从掌握度最低的章节开始练习</span>
            </div>
            <div class="suggestion-item">
              <BookOpen :size="18" class="sug-icon" />
              <span>加强练习：多做一些综合应用题，提高跨知识点运用能力</span>
            </div>
            <div class="suggestion-item">
              <CheckCircle2 :size="18" class="sug-icon" />
              <span>已掌握的知识点请定期复习，保持记忆曲线</span>
            </div>
          </div>
          <div class="encouragement">趁热打铁，加油！</div>
          <router-link to="/recommend" class="btn btn-primary cta-btn">
            开始针对性练习
            <ArrowRight :size="16" />
          </router-link>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  ArrowLeft, ArrowRight, Download, Share2,
  Target, CheckCircle2, AlertTriangle, TrendingDown, BookOpen
} from 'lucide-vue-next'
import AppLayout from '../components/AppLayout.vue'
import QuestionGradingCard from '../components/grading/QuestionGradingCard.vue'
import ErrorDistribution from '../components/grading/ErrorDistribution.vue'
import KpPerformanceTable from '../components/grading/KpPerformanceTable.vue'
import { gradingAPI } from '../services/grading-api.js'

const route = useRoute()
const loading = ref(false)
const error = ref('')
const report = ref(null)

async function loadReport() {
  const sessionId = route.params.sessionId
  if (!sessionId) {
    error.value = '缺少批改会话ID'
    return
  }
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
.report-page {
  padding: 32px;
  max-width: var(--max-content-width);
  margin: 0 auto;
  padding-bottom: 80px;
}

.report-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  text-decoration: none;
  font-size: var(--font-base);
}
.back-link:hover { text-decoration: underline; }

.topbar-actions { display: flex; gap: 8px; }
.btn-sm { padding: 6px 14px; font-size: var(--font-sm); }

.loading { display: flex; justify-content: center; padding: 60px 0; }
.error { color: var(--color-error); padding: 16px; }

.overview-card { padding: 24px; margin-bottom: 24px; }

.overview-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20px;
}
.overview-header h2 { font-size: var(--font-xl); font-weight: 700; color: var(--color-text-title); }
.report-date { font-size: var(--font-sm); color: var(--color-text-secondary); }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 16px 8px;
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--color-primary);
}
.stat-value { font-size: var(--font-xxl); font-weight: 700; color: var(--color-text-title); }
.stat-label { font-size: var(--font-xs); color: var(--color-text-secondary); }

.section { margin-bottom: 24px; }

.section-title {
  font-size: var(--font-md);
  font-weight: 600;
  color: var(--color-text-title);
  margin-bottom: 12px;
}

.question-list { display: flex; flex-direction: column; gap: 10px; }

.suggestions-card {
  padding: 24px;
  border-left: 4px solid var(--color-primary);
  margin-top: 24px;
}

.suggestions-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: var(--font-base);
  color: var(--color-text-body);
  line-height: 1.6;
}

.sug-icon { color: var(--color-primary); flex-shrink: 0; margin-top: 2px; }

.encouragement {
  font-size: var(--font-md);
  font-weight: 600;
  color: var(--color-text-title);
  margin-bottom: 16px;
}

.cta-btn {
  display: inline-flex;
  gap: 8px;
}

@media (max-width: 768px) {
  .report-page { padding: 16px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
