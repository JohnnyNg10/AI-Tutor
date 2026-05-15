<template>
  <AppLayout>
    <div class="grading-page">
      <!-- ===== LIST MODE ===== -->
      <template v-if="mode === 'list'">
        <div class="page-header">
          <div class="header-left">
            <h1>AI批改</h1>
            <p class="subtitle">上传试卷，获取详细批改分析</p>
          </div>
          <button class="btn btn-primary" @click="startNewGrading">
            <Plus :size="18" />
            新建批改
          </button>
        </div>

        <div v-if="loading" class="loading">
          <div class="spinner"></div>
        </div>

        <div v-else-if="error" class="error">{{ error }}</div>

        <div v-else-if="historyList.length === 0" class="empty-state">
          <div class="empty-icon">
            <ClipboardCheck :size="64" />
          </div>
          <h2>还没有批改记录</h2>
          <p>拍照上传你的试卷或作业，AI将为你逐题批改分析</p>
          <button class="btn btn-primary" @click="startNewGrading">开始第一次批改</button>
          <div class="format-card">
            <Lightbulb :size="18" />
            <span>支持格式：拍照或上传图片（JPG/PNG），手写内容也可识别</span>
          </div>
        </div>

        <div v-else class="history-list">
          <div
            v-for="item in historyList"
            :key="item.id"
            class="card card-clickable history-card"
            @click="viewReport(item.id)"
          >
            <div class="history-card-header">
              <div class="history-title-row">
                <ScrollText :size="20" />
                <span class="history-title">{{ item.title || '未命名批改' }}</span>
                <span class="history-time">{{ formatTime(item.created_at) }}</span>
              </div>
            </div>
            <div class="history-summary">
              {{ item.question_count || 0 }}题 | 平均分 {{ item.avg_score || 0 }} | {{ item.error_summary || '暂无摘要' }}
            </div>
            <div class="history-divider"></div>
            <div class="history-actions">
              <button class="btn-text" @click.stop="viewReport(item.id)">查看报告</button>
              <button class="btn-danger" @click.stop="confirmDelete(item)">删除</button>
            </div>
          </div>
        </div>
      </template>

      <!-- ===== UPLOAD MODE ===== -->
      <template v-if="mode === 'upload'">
        <router-link to="/grading" class="back-link">
          <ArrowLeft :size="16" />
          返回列表
        </router-link>

        <div class="upload-header">
          <h2>新建批改</h2>
        </div>

        <!-- Step 1: Upload Images -->
        <div class="card step-card" v-if="step >= 1">
          <div class="step-indicator">
            <span class="step-num" :class="{ active: step === 1, done: step > 1 }">1</span>
            <span class="step-title">上传图片</span>
          </div>
          <div class="step-body" v-show="step === 1 || step > 1">
            <div class="upload-columns">
              <div class="upload-col">
                <h3>题目图片</h3>
                <p class="col-hint">上传试卷或作业上的原题，确保文字清晰可读</p>
                <ImageUploader
                  title="点击上传题目图片"
                  hint="支持 JPG / PNG，建议清晰拍摄"
                  :images="questionImages"
                  @add="addQuestionImage"
                  @remove="removeQuestionImage"
                />
              </div>
              <div class="upload-col">
                <h3>解题过程图片</h3>
                <p class="col-hint">上传你的解题草稿或答题纸，AI将识别手写内容</p>
                <ImageUploader
                  title="点击上传解题过程图片"
                  hint="支持 JPG / PNG"
                  :images="answerImages"
                  @add="addAnswerImage"
                  @remove="removeAnswerImage"
                />
              </div>
            </div>
            <div class="step-footer" v-if="step === 1">
              <button
                class="btn btn-primary"
                :disabled="!hasImages"
                @click="handleUploadAndOCR"
              >
                {{ uploading ? '识别中...' : '下一步：开始识别' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Step 2: Review OCR -->
        <div class="card step-card" v-if="step >= 2">
          <div class="step-indicator">
            <span class="step-num" :class="{ active: step === 2, done: step > 2 }">2</span>
            <span class="step-title">核对识别结果</span>
            <CheckCircle2 v-if="step > 2" :size="18" class="text-success" />
          </div>
          <div class="step-body" v-show="step === 2">
            <OCRReviewPanel
              v-if="ocrResults.length > 0"
              :current-image="currentOCRImage"
              :index="currentQuestionIndex"
              :total-images="ocrResults.length"
              :correction-status="correctionStatus"
              :segments="currentOCRSegments"
              @prev="prevQuestion"
              @next="nextQuestion"
              @zoom="showLightbox"
              @confirm="handleStartGrading"
            />
            <div v-else class="empty">暂无识别结果</div>
          </div>
        </div>

        <!-- Step 3: Grading Progress -->
        <div class="card step-card" v-if="step >= 3">
          <div class="step-indicator">
            <span class="step-num" :class="{ active: step === 3, done: step > 3 }">3</span>
            <span class="step-title">批改中...</span>
          </div>
          <div class="step-body" v-show="step === 3">
            <GradingProgress
              :current="progress.current"
              :total="progress.total"
              :eta-seconds="progress.etaSeconds"
              :question-statuses="questionStatuses"
              @cancel="handleCancelGrading"
              @view-report="handleViewPartialReport"
            />
          </div>
          <div class="step-body" v-if="step === 4">
            <div class="done-state">
              <CheckCircle2 :size="64" class="text-success" />
              <h3>批改完成！</h3>
              <button class="btn btn-primary" @click="viewReport(sessionId)">
                查看报告
                <ArrowRight :size="16" />
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- Delete confirm dialog -->
      <ConfirmDialog
        v-if="deleteTarget"
        title="确认删除"
        message="删除后将无法恢复该批改记录"
        confirm-text="确认删除"
        @confirm="handleDelete"
        @cancel="deleteTarget = null"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Plus, ArrowLeft, ArrowRight, CheckCircle2, ClipboardCheck, Lightbulb, ScrollText
} from 'lucide-vue-next'
import AppLayout from '../components/AppLayout.vue'
import ImageUploader from '../components/grading/ImageUploader.vue'
import OCRReviewPanel from '../components/grading/OCRReviewPanel.vue'
import GradingProgress from '../components/grading/GradingProgress.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { gradingAPI } from '../services/grading-api.js'
import { useGrading } from '../composables/useGrading.js'

const route = useRoute()
const router = useRouter()

const {
  mode, step, loading, error,
  sessionId, questionImages, answerImages,
  ocrResults, currentQuestionIndex, correctionStatus,
  progress, questionStatuses,
  hasImages, allQuestionsReviewed,
  reset, startNewGrading: startNew, goToList,
  setOCRResults, markReviewed,
  startGrading: beginGrading, updateProgress, completeGrading
} = useGrading()

const historyList = ref([])
const uploading = ref(false)
const deleteTarget = ref(null)
const lightboxImage = ref('')

const currentOCRImage = computed(() => {
  const r = ocrResults.value[currentQuestionIndex.value]
  return r?.image_preview || ''
})

const currentOCRSegments = computed(() => {
  const r = ocrResults.value[currentQuestionIndex.value]
  return r?.segments || { question: [], answer: [] }
})

function addQuestionImage(img) { questionImages.value.push(img) }
function removeQuestionImage(i) { questionImages.value.splice(i, 1) }
function addAnswerImage(img) { answerImages.value.push(img) }
function removeAnswerImage(i) { answerImages.value.splice(i, 1) }

function prevQuestion() {
  if (currentQuestionIndex.value > 0) {
    markReviewed(currentQuestionIndex.value)
    currentQuestionIndex.value--
  }
}

function nextQuestion() {
  if (currentQuestionIndex.value < ocrResults.value.length - 1) {
    markReviewed(currentQuestionIndex.value)
    currentQuestionIndex.value++
  }
}

function showLightbox(src) {
  lightboxImage.value = src
}

async function handleUploadAndOCR() {
  uploading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    questionImages.value.forEach(img => formData.append('images', img.file))
    answerImages.value.forEach(img => formData.append('images', img.file))
    const res = await gradingAPI.uploadImages(formData)
    const data = res?.data || res
    setOCRResults(data.questions || [])
    sessionId.value = data.session_id
  } catch (e) {
    error.value = e?.message || 'OCR识别失败，请重试'
  } finally {
    uploading.value = false
  }
}

async function handleStartGrading() {
  beginGrading()
  error.value = ''
  try {
    const res = await gradingAPI.submitCorrections({
      session_id: sessionId.value,
      questions: ocrResults.value.map((_, i) => ({
        index: i,
        corrected_text: '',
        corrected_answer: ''
      }))
    })
    const data = res?.data || res

    if (data.event === 'complete') {
      completeGrading(data)
    } else {
      updateProgress(data)
    }
  } catch (e) {
    error.value = e?.message || '批改失败，请重试'
    step.value = 2
  }
}

async function handleCancelGrading() {
  try {
    await gradingAPI.cancelGrading(sessionId.value)
  } catch {}
  goToList()
}

function handleViewPartialReport() {
  router.push(`/grading/report/${sessionId.value}`)
}

function viewReport(id) {
  router.push(`/grading/report/${id}`)
}

function confirmDelete(item) {
  deleteTarget.value = item
}

async function handleDelete() {
  if (!deleteTarget.value) return
  try {
    await gradingAPI.deleteSession(deleteTarget.value.id)
    historyList.value = historyList.value.filter(h => h.id !== deleteTarget.value.id)
  } catch (e) {
    error.value = e?.message || '删除失败'
  }
  deleteTarget.value = null
}

async function loadHistory() {
  loading.value = true
  error.value = ''
  try {
    const res = await gradingAPI.getHistory(1, 20)
    historyList.value = res?.data?.items || res?.items || []
  } catch (e) {
    error.value = e?.message || '加载历史记录失败'
  } finally {
    loading.value = false
  }
}

function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  const now = Date.now()
  const diff = now - d.getTime()
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return d.toLocaleDateString('zh-CN')
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.grading-page { padding: 32px; max-width: var(--max-content-width); margin: 0 auto; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}
.header-left h1 {
  font-size: var(--font-xxl);
  font-weight: 700;
  color: var(--color-text-title);
  margin-bottom: 4px;
}
.subtitle { font-size: var(--font-base); color: var(--color-text-secondary); }

.loading { display: flex; justify-content: center; padding: 60px 0; }
.error { color: var(--color-error); padding: 16px; }

.empty-state {
  text-align: center;
  padding: 60px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.empty-icon { color: #86868B4D; margin-bottom: 8px; }
.empty-state h2 { font-size: var(--font-lg); font-weight: 600; color: var(--color-text-title); }
.empty-state p { color: var(--color-text-secondary); font-size: var(--font-base); }

.format-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
  margin-top: 16px;
}

.history-list { display: flex; flex-direction: column; gap: 12px; }

.history-card { padding: 16px; }
.history-card-header { margin-bottom: 8px; }
.history-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-body);
}
.history-title { font-weight: 600; font-size: var(--font-base); flex: 1; }
.history-time { font-size: var(--font-xs); color: var(--color-text-secondary); }
.history-summary { font-size: var(--font-sm); color: var(--color-text-secondary); margin-bottom: 8px; }
.history-divider { height: 1px; background: var(--color-border); margin-bottom: 8px; }
.history-actions { display: flex; gap: 8px; }

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  text-decoration: none;
  font-size: var(--font-base);
  margin-bottom: 16px;
}
.back-link:hover { text-decoration: underline; }

.upload-header h2 { font-size: var(--font-xl); font-weight: 700; color: var(--color-text-title); margin-bottom: 20px; }

.step-card { padding: 20px; margin-bottom: 16px; }

.step-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-border);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-sm);
  font-weight: 700;
}
.step-num.active { background: var(--color-primary); color: #fff; }
.step-num.done { background: var(--color-success); color: #fff; }

.step-title { font-weight: 600; font-size: var(--font-md); color: var(--color-text-title); }

.upload-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 16px; }
.upload-col h3 { font-size: var(--font-base); font-weight: 600; color: var(--color-text-title); margin-bottom: 4px; }
.col-hint { font-size: var(--font-xs); color: var(--color-text-secondary); margin-bottom: 10px; }

.step-footer { display: flex; justify-content: flex-end; padding-top: 16px; border-top: 1px solid var(--color-border); }

.done-state {
  text-align: center;
  padding: 40px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.done-state h3 { font-size: var(--font-xl); font-weight: 700; color: var(--color-text-title); }

.text-success { color: var(--color-success); }

@media (max-width: 768px) {
  .grading-page { padding: 16px; }
  .upload-columns { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; gap: 12px; }
}
</style>
