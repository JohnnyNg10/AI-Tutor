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

      <!-- ===== UPLOAD MODE per Figma ===== -->
      <template v-if="mode === 'upload'">
        <router-link to="/grading" class="back-link">
          <ArrowLeft :size="16" />
          返回列表
        </router-link>

        <div class="upload-mode-badge">
          <Plus :size="16" />
          <span>新建批改</span>
        </div>

        <!-- Step 1: 上传图片 -->
        <div class="figma-step-card" v-if="step >= 1">
          <div class="figma-step-head">
            <span class="figma-step-num">1</span>
            <span class="figma-step-title">上传图片</span>
          </div>

          <div class="figma-upload-grid" v-show="step === 1">
            <div class="figma-upload-zone" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
              <input ref="fileInputRef" type="file" accept="image/*" multiple hidden @change="handleFileSelect" />
              <Camera :size="28" />
              <span class="upload-zone-text">点击或拖拽上传</span>
              <span class="upload-zone-hint">支持 JPG / PNG / 手写图片</span>
            </div>
          </div>

          <div class="figma-step-foot" v-if="step === 1">
            <span class="figma-img-count">已上传 {{ allImages.length }} 张图片</span>
            <button
              class="figma-btn-primary"
              :disabled="allImages.length === 0 || uploading"
              @click="handleUploadAndOCR"
            >
              <span>{{ uploading ? '识别中...' : '下一步：开始识别' }}</span>
              <ArrowRight :size="16" />
            </button>
          </div>
        </div>

        <!-- Step 2: 核对识别结果 -->
        <div class="figma-step-card" v-if="step >= 2">
          <div class="figma-step-head">
            <span class="figma-step-num">2</span>
            <span class="figma-step-title">核对识别结果</span>
            <span v-if="step === 2" class="figma-auto-badge">
              <CheckCircle2 :size="14" />
              自动识别完成
            </span>
          </div>

          <div v-show="step === 2">
            <div v-if="ocrResults.length > 0" class="figma-review-wrap">
              <!-- Left: original image -->
              <div class="figma-review-left" @click="showLightbox(currentOCRImage)">
                <img v-if="currentOCRImage" :src="currentOCRImage" class="figma-review-img" alt="" />
                <span class="figma-review-left-label">原始图片（点击放大）</span>
              </div>

              <!-- Right: structured text -->
              <div class="figma-review-right">
                <span class="figma-editable-hint">（可编辑）</span>
                <div class="figma-ocr-section">
                  <span class="figma-ocr-label">【题目】</span>
                  <textarea
                    v-model="currentQText"
                    class="figma-ocr-textarea"
                    rows="3"
                  ></textarea>
                </div>
                <div class="figma-ocr-section">
                  <span class="figma-ocr-label">【解题过程】</span>
                  <textarea
                    v-model="currentAText"
                    class="figma-ocr-textarea"
                    rows="6"
                  ></textarea>
                </div>
              </div>
            </div>

            <!-- Pagination -->
            <div v-if="ocrResults.length > 1" class="figma-pagination">
              <button :disabled="currentQuestionIndex === 0" @click="prevQuestion">←</button>
              <span>{{ currentQuestionIndex + 1 }} / {{ ocrResults.length }}</span>
              <button :disabled="currentQuestionIndex >= ocrResults.length - 1" @click="nextQuestion">→</button>
            </div>

            <div v-if="ocrResults.length === 0" class="figma-empty">暂无识别结果</div>

            <!-- Confirm -->
            <div class="figma-confirm-row">
              <button class="figma-btn-primary" @click="handleStartGrading">
                确认无误，开始批改
              </button>
            </div>
          </div>

          <!-- Step 3: Grading -->
          <div v-if="step === 3" class="figma-grading-progress">
            <GradingProgress
              :current="progress.current"
              :total="progress.total"
              :eta-seconds="progress.etaSeconds"
              :question-statuses="questionStatuses"
              @cancel="handleCancelGrading"
              @view-report="handleViewPartialReport"
            />
          </div>

          <!-- Step 4: Done -->
          <div v-if="step === 4" class="figma-done">
            <CheckCircle2 :size="48" class="figma-done-icon" />
            <span class="figma-done-text">批改完成！</span>
            <button class="figma-btn-primary" @click="viewReport(sessionId)">
              查看报告 <ArrowRight :size="16" />
            </button>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Plus, ArrowLeft, ArrowRight, CheckCircle2, Camera, ClipboardCheck, Lightbulb, ScrollText
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
  reset, startNewGrading, goToList,
  setOCRResults, markReviewed,
  startGrading: beginGrading, updateProgress, completeGrading
} = useGrading()

const historyList = ref([])
const uploading = ref(false)
const deleteTarget = ref(null)
const lightboxImage = ref('')
const fileInputRef = ref(null)

// Single merged upload area (Figma: all images in one zone, AI auto-separates)
const allImages = computed(() => [...questionImages.value, ...answerImages.value])

// Editable OCR text for current question
const currentQText = ref('')
const currentAText = ref('')

// Watch current OCR result to populate editable fields
watch([currentQuestionIndex, () => ocrResults.value.length], () => {
  const r = ocrResults.value[currentQuestionIndex.value]
  if (r) {
    currentQText.value = r.segments?.question?.join('\n') || r.question_text || ''
    currentAText.value = r.segments?.answer?.join('\n') || r.answer_text || ''
  }
}, { immediate: true })

function triggerUpload() { fileInputRef.value?.click() }

function handleFileSelect(e) {
  const files = Array.from(e.target.files || [])
  files.forEach(f => addImage(f))
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function handleDrop(e) {
  const files = Array.from(e.dataTransfer?.files || [])
  files.forEach(f => addImage(f))
}

function addImage(file) {
  if (!file.type.startsWith('image/')) return
  const url = URL.createObjectURL(file)
  const img = { file, preview: url }
  questionImages.value.push(img)
  // Reset file input so same file can be re-selected
}

function removeAllImages() {
  questionImages.value.forEach(img => URL.revokeObjectURL(img.preview))
  questionImages.value = []
  answerImages.value = []
}

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
.grading-page { padding: 32px; margin: 0 auto; max-width: 1000px; }

/* === LIST MODE === */
.page-header {
  display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px;
}
.header-left h1 { font-size: var(--font-xxl); font-weight: 700; color: var(--color-text-title); margin-bottom: 4px; }
.subtitle { font-size: var(--font-base); color: var(--color-text-secondary); }
.loading { display: flex; justify-content: center; padding: 60px 0; }
.error { color: var(--color-error); padding: 16px; }
.empty-state { text-align: center; padding: 60px 0; display: flex; flex-direction: column; align-items: center; gap: 16px; }
.empty-icon { color: #86868B4D; margin-bottom: 8px; }
.empty-state h2 { font-size: var(--font-lg); font-weight: 600; color: var(--color-text-title); }
.empty-state p { color: var(--color-text-secondary); font-size: var(--font-base); }
.format-card {
  display: flex; align-items: center; gap: 8px; padding: 12px 20px;
  background: #fff; border-radius: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.05);
  color: var(--color-text-secondary); font-size: var(--font-sm); margin-top: 16px;
}
.history-list { display: flex; flex-direction: column; gap: 12px; }
.history-card { padding: 16px; }
.history-card-header { margin-bottom: 8px; }
.history-title-row { display: flex; align-items: center; gap: 8px; color: var(--color-text-body); }
.history-title { font-weight: 600; font-size: var(--font-base); flex: 1; }
.history-time { font-size: var(--font-xs); color: var(--color-text-secondary); }
.history-summary { font-size: var(--font-sm); color: var(--color-text-secondary); margin-bottom: 8px; }
.history-divider { height: 1px; background: var(--color-border); margin-bottom: 8px; }
.history-actions { display: flex; gap: 8px; }

/* === UPLOAD MODE (Figma exact) === */
.back-link { display: inline-flex; align-items: center; gap: 4px; color: #0E61AC; text-decoration: none; font-size: var(--font-base); margin-bottom: 16px; }
.back-link:hover { opacity: 0.8; }

.upload-mode-badge {
  display: inline-flex; align-items: center; gap: 6px; background: #0E61AC; color: #FAF2E0;
  padding: 10px 16px; border-radius: 10px; font-size: var(--font-base); font-weight: 600;
  margin-bottom: 24px; box-shadow: 0 4px 12px rgba(14,97,172,.25);
}

/* Step card */
.figma-step-card {
  background: #fff; border-radius: 16px; padding: 20px; margin-bottom: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
}

.figma-step-head {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid #EEEEEE;
}

.figma-step-num {
  width: 24px; height: 24px; border-radius: 50%; background: #0E61AC; color: #FAF2E0;
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0;
}

.figma-step-title { font-weight: 600; font-size: var(--font-md); color: #1B1B1B; }

.figma-auto-badge {
  display: inline-flex; align-items: center; gap: 4px; margin-left: auto;
  color: #0E61AC; font-size: 12px; font-weight: 500;
}

/* Upload zone (Figma: cream card with camera icon, padding 55px) */
.figma-upload-grid { margin-bottom: 16px; }

.figma-upload-zone {
  background: #FAF2E0; border: 2px dashed #E9D4C1; border-radius: 12px;
  padding: 55px 32px; display: flex; flex-direction: column; align-items: center; gap: 12px;
  cursor: pointer; transition: border-color 0.2s, background 0.2s;
}
.figma-upload-zone:hover { border-color: #0E61AC; background: #f5ede0; }
.upload-zone-text { font-size: 15px; font-weight: 500; color: #1B1B1B; }
.upload-zone-hint { font-size: 12px; color: #86868B; }

/* Step footer */
.figma-step-foot {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: 16px; border-top: 1px solid #EEEEEE;
}
.figma-img-count { font-size: 13px; color: #86868B; }

.figma-btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  background: #0E61AC; color: #FAF2E0; border: none; border-radius: 10px;
  padding: 10px 16px; font-size: 14px; font-weight: 600; cursor: pointer;
  transition: opacity 0.2s; font-family: var(--font-family);
}
.figma-btn-primary:hover:not(:disabled) { opacity: 0.85; }
.figma-btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

/* Step 2 Review (Figma: left image + right structured text) */
.figma-review-wrap {
  display: flex; gap: 16px; margin-bottom: 16px;
}

.figma-review-left {
  width: 280px; flex-shrink: 0; background: #FAF2E0; border-radius: 12px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 20px; cursor: pointer; transition: opacity 0.2s; min-height: 200px;
  position: relative; overflow: hidden;
}
.figma-review-left:hover { opacity: 0.85; }
.figma-review-img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px; }
.figma-review-left-label { font-size: 11px; color: #86868B; margin-top: 8px; }

.figma-review-right {
  flex: 1; background: #FAF2E0; border-radius: 12px; padding: 20px;
  display: flex; flex-direction: column; gap: 12px; min-width: 0;
}
.figma-editable-hint { font-size: 11px; color: #86868B; }
.figma-ocr-section { display: flex; flex-direction: column; gap: 6px; }
.figma-ocr-label { font-size: 13px; font-weight: 600; color: #0E61AC; }
.figma-ocr-textarea {
  width: 100%; border: 1px solid #EEEEEE; border-radius: 8px; padding: 10px 12px;
  font-size: 13px; font-family: var(--font-family); color: #454545; line-height: 1.7;
  resize: vertical; outline: none; box-sizing: border-box; background: #fff;
}
.figma-ocr-textarea:focus { border-color: #0E61AC; }

/* Pagination */
.figma-pagination {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 10px 0; margin-bottom: 12px; font-size: 14px; color: #1B1B1B;
}
.figma-pagination button {
  width: 28px; height: 28px; border: 1px solid #EEEEEE; border-radius: 8px;
  background: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: #86868B; font-size: 14px; transition: all 0.15s;
}
.figma-pagination button:hover:not(:disabled) { border-color: #0E61AC; color: #0E61AC; }
.figma-pagination button:disabled { opacity: 0.3; cursor: default; }

.figma-confirm-row { display: flex; justify-content: center; padding-top: 16px; }

.figma-empty { text-align: center; padding: 40px 0; color: #86868B; font-size: 14px; }

/* Grading progress / Done */
.figma-grading-progress { padding: 16px 0; }
.figma-done { text-align: center; padding: 32px 0; display: flex; flex-direction: column; align-items: center; gap: 16px; }
.figma-done-icon { color: #0E61AC; }
.figma-done-text { font-size: var(--font-xl); font-weight: 700; color: #1B1B1B; }

@media (max-width: 768px) {
  .grading-page { padding: 16px; }
  .page-header { flex-direction: column; gap: 12px; }
  .figma-review-wrap { flex-direction: column; }
  .figma-review-left { width: 100%; min-height: 160px; }
}
</style>
