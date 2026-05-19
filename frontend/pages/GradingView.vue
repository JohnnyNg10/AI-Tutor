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
            :key="item.session_id"
            class="card card-clickable history-card"
          >
            <div class="history-card-main" @click="viewReport(item.session_id)">
              <div class="history-card-header">
                <div class="history-title-row">
                  <ScrollText :size="20" />
                  <span class="history-title">{{ item.title || '未命名批改' }}</span>
                  <span class="history-time">{{ formatTime(item.created_at) }}</span>
                </div>
              </div>
              <div class="history-summary">
                {{ item.question_count || 0 }}题 | 平均分 {{ item.avg_score || 0 }}
              </div>
            </div>
            <div class="history-divider"></div>
            <div class="history-actions">
              <button class="btn-text" @click="viewReport(item.session_id)">查看报告</button>
              <button class="btn-danger" @click="confirmDelete(item)">删除</button>
            </div>
          </div>
        </div>
      </template>

      <!-- ===== UPLOAD MODE per Figma ===== -->
      <template v-if="mode === 'upload'">
        <button class="back-link" @click="goToList">
          <ArrowLeft :size="16" />
          返回列表
        </button>

        <div class="upload-mode-badge">
          <Plus :size="16" />
          <span>新建批改</span>
        </div>

        <div class="steps-container">
          <!-- Step 1: 上传图片 -->
          <div class="figma-step-card">
            <div class="figma-step-head">
              <span class="figma-step-num">1</span>
              <span class="figma-step-title">上传图片</span>
            </div>

            <div class="figma-upload-grid">
              <div
                class="figma-upload-zone"
                @click="triggerUpload"
                @dragover.prevent
                @drop.prevent="handleDrop"
              >
                <input
                  ref="fileInputRef"
                  type="file"
                  accept="image/*"
                  multiple
                  hidden
                  @change="handleFileSelect"
                />
                <Camera :size="28" color="#86868B" />
                <span class="upload-zone-text">点击或拖拽上传</span>
                <span class="upload-zone-hint">支持 JPG / PNG / 手写图片</span>
              </div>

              <!-- Image previews -->
              <div v-if="allImages.length > 0" class="upload-previews">
                <div v-for="(img, i) in allImages" :key="i" class="upload-preview-item">
                  <img :src="img.preview" class="upload-preview-img" alt="" />
                  <button class="upload-preview-remove" @click.stop="removeImage(i)">&times;</button>
                </div>
              </div>
            </div>

            <div class="figma-step-foot">
              <span class="figma-img-count">已上传 {{ allImages.length }} 张图片</span>
              <button
                class="figma-btn-primary"
                :disabled="allImages.length === 0 || uploading"
                @click="handleUploadAndOCR"
              >
                <Loader2 v-if="uploading" :size="16" class="spinning" />
                <span>{{ uploading ? '识别中...' : '下一步：开始识别' }}</span>
                <ArrowRight v-if="!uploading" :size="16" />
              </button>
            </div>
          </div>

          <!-- Step 2: 核对识别结果 — scrollable all-questions view -->
          <div v-if="step >= 2" class="figma-step-card">
            <div class="figma-step-head">
              <span class="figma-step-num">2</span>
              <span class="figma-step-title">核对识别结果</span>
              <span v-if="ocrReady" class="figma-auto-badge">
                <CheckCircle2 :size="14" />
                共 {{ ocrResults.length }} 题
              </span>
            </div>

            <div v-if="ocrReady && ocrResults.length > 0" class="review-scrollable">
              <!-- Each question card -->
              <div
                v-for="(item, qIdx) in ocrResults"
                :key="qIdx"
                class="question-review-card"
              >
                <!-- Card header -->
                <div class="question-card-header">
                  <span class="question-card-num">第{{ qIdx + 1 }}题</span>
                  <span class="question-card-topic" v-if="item.topic">{{ item.topic }}</span>
                  <span
                    v-if="item.merged_from && item.merged_from.length > 1"
                    class="merged-badge"
                  >
                    已合并 {{ item.merged_from.length }} 张图片
                  </span>
                </div>

                <!-- Source image thumbnails -->
                <div class="question-card-images" v-if="item.source_image_indices?.length">
                  <div
                    v-for="srcIdx in item.source_image_indices"
                    :key="srcIdx"
                    class="question-card-thumb"
                    @click="showLightbox(getImagePreview(srcIdx))"
                  >
                    <img
                      v-if="getImagePreview(srcIdx)"
                      :src="getImagePreview(srcIdx)"
                      class="question-card-thumb-img"
                      alt=""
                    />
                    <Camera v-else :size="20" color="#86868B" />
                    <span class="thumb-label">图片 {{ srcIdx + 1 }}</span>
                  </div>
                </div>

                <!-- Question text (rendered math) -->
                <div class="figma-ocr-section">
                  <div class="figma-ocr-label-row">
                    <span class="figma-ocr-label">【题目】</span>
                    <button
                      class="ai-correct-btn"
                      :disabled="correctingText"
                      @click="openCorrectionDialog(qIdx, 'question')"
                    >
                      <Wand2 :size="14" />
                      AI 纠错
                    </button>
                  </div>
                  <div
                    class="figma-ocr-rendered"
                    v-html="renderLatex(item.question_text || item.ocr_text) || '<span class=\'placeholder\'>未识别到题目内容</span>'"
                  ></div>
                </div>

                <!-- Answer text (rendered math) -->
                <div class="figma-ocr-section">
                  <div class="figma-ocr-label-row">
                    <span class="figma-ocr-label">【解题过程】</span>
                    <button
                      class="ai-correct-btn"
                      :disabled="correctingText"
                      @click="openCorrectionDialog(qIdx, 'answer')"
                    >
                      <Wand2 :size="14" />
                      AI 纠错
                    </button>
                  </div>
                  <div
                    class="figma-ocr-rendered"
                    v-html="renderLatex(item.student_answer || item.answer_text) || '<span class=\'placeholder\'>未识别到解题过程</span>'"
                  ></div>
                </div>

                <!-- Merge info -->
                <div v-if="item.merged_from && item.merged_from.length > 1" class="question-card-actions">
                  <span class="merged-detail">
                    AI 自动合并自 {{ item.merged_from.length }} 张图片
                    (图片 {{ item.merged_from.map(i => i + 1).join('、') }})
                  </span>
                </div>
              </div>
            </div>

            <div v-else-if="ocrReady && ocrResults.length === 0" class="figma-empty">
              暂无识别结果，请重新上传
            </div>

            <!-- Confirm button (sticky at bottom) -->
            <div v-if="ocrReady && ocrResults.length > 0" class="figma-confirm-row figma-confirm-sticky">
              <button
                class="figma-btn-primary"
                :disabled="gradingInProgress"
                @click="handleStartGrading"
              >
                <Loader2 v-if="gradingInProgress" :size="16" class="spinning" />
                {{ gradingInProgress ? '批改中...' : `确认无误，开始批改 (${ocrResults.length}题)` }}
              </button>
            </div>
          </div>

          <!-- AI Correction Dialog -->
          <div v-if="correctionDialog.open" class="correction-overlay" @click.self="correctionDialog.open = false">
            <div class="correction-dialog">
              <div class="correction-dialog-header">
                <h4>AI 智能纠错 — 第{{ correctionDialog.qIdx + 1 }}题 {{ correctionDialog.section === 'question' ? '题目' : '解题过程' }}</h4>
                <button class="correction-close" @click="correctionDialog.open = false">&times;</button>
              </div>
              <div class="correction-current">
                <div class="correction-current-label">当前识别内容：</div>
                <div
                  class="correction-current-content"
                  v-html="renderLatex(correctionDialog.currentText) || '(空)'"
                ></div>
              </div>
              <div class="correction-input-row">
                <textarea
                  v-model="correctionDialog.userInput"
                  class="correction-input"
                  rows="3"
                  placeholder="用自然语言描述需要修正的地方，例如：&#10;'第二行的公式应该是 a_n = 2^n - 1 而不是 2n - 1'&#10;'把分母改成 n(n+1)，不是 n+1'"
                ></textarea>
                <button
                  class="figma-btn-primary correction-submit"
                  :disabled="!correctionDialog.userInput.trim() || correctingText"
                  @click="handleCorrectText"
                >
                  <Loader2 v-if="correctingText" :size="14" class="spinning" />
                  {{ correctingText ? '修正中...' : '发送修正' }}
                </button>
              </div>
              <div v-if="correctionDialog.result" class="correction-result">
                <div class="correction-result-label">修正结果：</div>
                <div
                  class="correction-result-content"
                  v-html="renderLatex(correctionDialog.result)"
                ></div>
                <button class="figma-btn-primary" @click="applyCorrection">
                  <CheckCircle2 :size="16" />
                  应用修正
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Lightbox -->
        <div v-if="lightboxImage" class="lightbox-overlay" @click="lightboxImage = ''">
          <img :src="lightboxImage" class="lightbox-image" alt="" @click.stop />
        </div>
      </template>

      <!-- ===== GRADING MODE (loading) ===== -->
      <template v-if="mode === 'grading'">
        <button class="back-link" @click="handleCancelGrading">
          <ArrowLeft :size="16" />
          返回列表
        </button>

        <GradingProgress
          :current="progress.current"
          :total="progress.total"
          :eta-seconds="progress.etaSeconds"
          :question-statuses="questionStatuses"
          @cancel="handleCancelGrading"
          @view-report="handleViewReport"
        />
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
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Plus, ArrowLeft, ArrowRight, CheckCircle2, Camera, ClipboardCheck,
  Lightbulb, ScrollText, Loader2, Wand2
} from 'lucide-vue-next'
import katex from 'katex'
import AppLayout from '../components/AppLayout.vue'
import GradingProgress from '../components/grading/GradingProgress.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { gradingAPI } from '../services/grading-api.js'
import { useGrading } from '../composables/useGrading.js'

const route = useRoute()
const router = useRouter()

const {
  mode, step, loading, error,
  sessionId, questionImages, answerImages,
  ocrResults, correctionStatus,
  progress, questionStatuses,
  reset, startNewGrading, goToList,
  setOCRResults, markReviewed,
  startGrading: beginGrading, updateProgress, completeGrading
} = useGrading()

const historyList = ref([])
const uploading = ref(false)
const gradingInProgress = ref(false)
const correctingText = ref(false)
const deleteTarget = ref(null)
const lightboxImage = ref('')
const fileInputRef = ref(null)

// All uploaded images (single merged upload zone per Figma)
const allImages = computed(() => [...questionImages.value, ...answerImages.value])

// Get preview URL for an image by its original upload index
function getImagePreview(uploadIndex) {
  return allImages.value[uploadIndex]?.preview || ''
}

// AI Correction dialog state
const correctionDialog = reactive({
  open: false,
  qIdx: 0,
  section: 'question', // 'question' | 'answer'
  currentText: '',
  userInput: '',
  result: '',
})

// OCR data is ready for review
const ocrReady = computed(() => ocrResults.value.length > 0)

// Render LaTeX + plain text to HTML using KaTeX
function renderLatex(text) {
  if (!text) return ''
  try {
    // Split into tokens: $$...$$ blocks, $...$ inline, and plain text
    const parts = []
    let remaining = text
    let match

    // First handle $$...$$ display math (block)
    const displayRegex = /\$\$([\s\S]*?)\$\$/g
    let lastIndex = 0
    while ((match = displayRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ type: 'text', content: escapeHTML(remaining.slice(lastIndex, match.index)) })
      }
      try {
        const html = katex.renderToString(match[1].trim(), { throwOnError: false, displayMode: true })
        parts.push({ type: 'math', content: html })
      } catch {
        parts.push({ type: 'text', content: escapeHTML(match[0]) })
      }
      lastIndex = displayRegex.lastIndex
    }
    remaining = remaining.slice(lastIndex)

    // Then handle $...$ inline math in remaining text
    const inlineRegex = /\$([^$]+)\$/g
    lastIndex = 0
    let result = ''
    while ((match = inlineRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        result += escapeHTML(remaining.slice(lastIndex, match.index))
      }
      try {
        result += katex.renderToString(match[1].trim(), { throwOnError: false, displayMode: false })
      } catch {
        result += escapeHTML(match[0])
      }
      lastIndex = inlineRegex.lastIndex
    }
    result += escapeHTML(remaining.slice(lastIndex))

    // Combine display math parts with inline result
    let final = ''
    for (const p of parts) {
      final += p.content
    }
    final += result
    return final || escapeHTML(text)
  } catch {
    return escapeHTML(text)
  }
}

function escapeHTML(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>')
}

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
  questionImages.value.push({ file, preview: url })
}

function removeImage(index) {
  const img = questionImages.value[index]
  if (img) {
    URL.revokeObjectURL(img.preview)
    questionImages.value.splice(index, 1)
  }
}

function showLightbox(src) {
  if (src) lightboxImage.value = src
}

// === AI Correction Dialog ===
function openCorrectionDialog(qIdx, section) {
  const item = ocrResults.value[qIdx]
  if (!item) return
  const text = section === 'question'
    ? (item.question_text || item.ocr_text || '')
    : (item.student_answer || item.answer_text || '')
  correctionDialog.open = true
  correctionDialog.qIdx = qIdx
  correctionDialog.section = section
  correctionDialog.currentText = text
  correctionDialog.userInput = ''
  correctionDialog.result = ''
}

async function handleCorrectText() {
  if (!correctionDialog.userInput.trim()) return
  correctingText.value = true
  correctionDialog.result = ''
  try {
    const res = await gradingAPI.correctText(
      correctionDialog.currentText,
      correctionDialog.userInput.trim()
    )
    correctionDialog.result = res?.corrected_text || res?.data?.corrected_text || ''
  } catch (e) {
    correctionDialog.result = '修正请求失败：' + (e?.message || '未知错误')
  } finally {
    correctingText.value = false
  }
}

function applyCorrection() {
  if (!correctionDialog.result) return
  const item = ocrResults.value[correctionDialog.qIdx]
  if (!item) return
  if (correctionDialog.section === 'question') {
    item.question_text = correctionDialog.result
  } else {
    item.student_answer = correctionDialog.result
  }
  correctionDialog.open = false
  markReviewed(correctionDialog.qIdx)
}

async function handleUploadAndOCR() {
  uploading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    questionImages.value.forEach(img => formData.append('files', img.file))
    const res = await gradingAPI.uploadImages(formData)
    const data = res?.data || res

    // Backend returns grouped ocr_results with merged_from, source_image_indices, etc.
    const rawResults = data.ocr_results || data.questions || []
    // Keep raw OCR data for potential split, and add image previews
    const mappedResults = rawResults.map((r, i) => ({
      ...r,
      question_text: r.question_text || r.ocr_text || '',
      student_answer: r.student_answer || r.answer_text || '',
      // Store raw individual results for split functionality
      _raw_ocr: [],
    }))
    setOCRResults(mappedResults)
    sessionId.value = data.session_id
  } catch (e) {
    error.value = e?.message || 'OCR识别失败，请重试'
  } finally {
    uploading.value = false
  }
}

async function handleStartGrading() {
  gradingInProgress.value = true
  error.value = ''

  // Build corrections payload directly from all OCR results + user edits
  const corrections = ocrResults.value.map((r, i) => ({
    index: i,
    question_text: r.question_text || r.ocr_text || '',
    student_answer: r.student_answer || r.answer_text || '',
    ocr_text: r.ocr_text || '',
  }))

  try {
    const res = await gradingAPI.submitCorrections({
      session_id: sessionId.value,
      corrections
    })
    const data = res?.data || res

    // Backend returns synchronous result with summary
    // Show loading state, then navigate to report
    const totalQuestions = corrections.length

    // Initialize progress for visual feedback
    mode.value = 'grading'
    progress.total = totalQuestions
    progress.current = totalQuestions
    progress.status = 'done'

    // Mark all questions as done for the progress UI
    for (let i = 0; i < totalQuestions; i++) {
      questionStatuses[i] = 'done'
    }

    // Brief delay so user sees the completion animation
    await new Promise(r => setTimeout(r, 1200))

    // Navigate to report page
    router.push(`/grading/report/${sessionId.value}`)
  } catch (e) {
    error.value = e?.message || '批改失败，请重试'
    gradingInProgress.value = false
  }
}

async function handleCancelGrading() {
  try {
    if (sessionId.value) {
      await gradingAPI.cancelGrading(sessionId.value)
    }
  } catch {}
  goToList()
}

function handleViewReport() {
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
    await gradingAPI.deleteSession(deleteTarget.value.session_id)
    historyList.value = historyList.value.filter(
      h => h.session_id !== deleteTarget.value.session_id
    )
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
.empty-state {
  text-align: center; padding: 60px 0; display: flex; flex-direction: column; align-items: center; gap: 16px;
}
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
.history-card-main { cursor: pointer; }
.history-card-header { margin-bottom: 8px; }
.history-title-row { display: flex; align-items: center; gap: 8px; color: var(--color-text-body); }
.history-title { font-weight: 600; font-size: var(--font-base); flex: 1; }
.history-time { font-size: var(--font-xs); color: var(--color-text-secondary); }
.history-summary { font-size: var(--font-sm); color: var(--color-text-secondary); margin-bottom: 8px; }
.history-divider { height: 1px; background: var(--color-border); margin-bottom: 8px; }
.history-actions { display: flex; gap: 8px; }

.btn { display: inline-flex; align-items: center; gap: 6px; border: none; border-radius: 10px; padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: var(--font-family); transition: opacity 0.2s; }
.btn-primary { background: #0E61AC; color: #FAF2E0; }
.btn-primary:hover:not(:disabled) { opacity: 0.85; }
.btn-text { background: none; border: none; color: #0E61AC; cursor: pointer; font-size: 14px; font-family: var(--font-family); }
.btn-text:hover { opacity: 0.7; }
.btn-danger { background: none; border: none; color: #dc2626; cursor: pointer; font-size: 14px; font-family: var(--font-family); }
.btn-danger:hover { opacity: 0.7; }

/* === UPLOAD MODE (Figma alignment) === */
.back-link {
  display: inline-flex; align-items: center; gap: 4px; color: #0E61AC;
  background: none; border: none; cursor: pointer; font-size: var(--font-base);
  margin-bottom: 16px; padding: 0; font-family: var(--font-family);
}
.back-link:hover { opacity: 0.8; }

.upload-mode-badge {
  display: inline-flex; align-items: center; gap: 6px; background: #0E61AC; color: #FAF2E0;
  padding: 10px 16px; border-radius: 10px; font-size: var(--font-base); font-weight: 600;
  margin-bottom: 24px; box-shadow: 0 4px 12px rgba(14,97,172,.25);
}

.steps-container { display: flex; flex-direction: column; gap: 24px; }

/* Step card */
.figma-step-card {
  background: #fff; border-radius: 16px; padding: 20px;
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

/* Upload zone */
.figma-upload-grid { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }

.figma-upload-zone {
  background: #FAF2E0; border: 2px dashed #E9D4C1; border-radius: 12px;
  padding: 55px 32px; display: flex; flex-direction: column; align-items: center; gap: 12px;
  cursor: pointer; transition: border-color 0.2s, background 0.2s;
}
.figma-upload-zone:hover { border-color: #0E61AC; background: #f5ede0; }
.upload-zone-text { font-size: 15px; font-weight: 500; color: #1B1B1B; }
.upload-zone-hint { font-size: 12px; color: #86868B; }

/* Upload previews */
.upload-previews { display: flex; gap: 8px; flex-wrap: wrap; }
.upload-preview-item {
  position: relative; width: 80px; height: 80px; border-radius: 8px;
  overflow: hidden; border: 1px solid #EEEEEE;
}
.upload-preview-img { width: 100%; height: 100%; object-fit: cover; }
.upload-preview-remove {
  position: absolute; top: 2px; right: 2px;
  width: 18px; height: 18px; border-radius: 50%; background: rgba(0,0,0,.5);
  color: #fff; border: none; cursor: pointer; font-size: 12px; line-height: 1;
  display: flex; align-items: center; justify-content: center;
}

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
.figma-ocr-label-row { display: flex; align-items: center; justify-content: space-between; }
.figma-ocr-label { font-size: 13px; font-weight: 600; color: #0E61AC; }

/* AI Correct Button */
.ai-correct-btn {
  display: inline-flex; align-items: center; gap: 4px;
  background: none; border: 1px solid #0E61AC; border-radius: 6px;
  color: #0E61AC; padding: 4px 10px; font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; font-family: var(--font-family);
}
.ai-correct-btn:hover:not(:disabled) { background: #0E61AC; color: #FAF2E0; }
.ai-correct-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Rendered OCR content (read-only math display) */
.figma-ocr-rendered {
  min-height: 60px; background: #fff; border: 1px solid #EEEEEE;
  border-radius: 8px; padding: 12px 14px; font-size: 14px;
  line-height: 1.8; color: #1B1B1B;
}
.figma-ocr-rendered .placeholder { color: #86868B; font-style: italic; }
.figma-ocr-rendered :deep(.katex-display) { margin: 8px 0; overflow-x: auto; }
.figma-ocr-rendered :deep(.katex) { font-size: 1.05em; }
.figma-ocr-rendered :deep(.latex-error) { color: #dc2626; background: #fef2f2; padding: 2px 4px; border-radius: 3px; }

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

/* === Scrollable Review Layout === */
.review-scrollable {
  display: flex; flex-direction: column; gap: 16px;
  max-height: 65vh; overflow-y: auto; padding-right: 4px;
  margin-bottom: 20px;
}
.review-scrollable::-webkit-scrollbar { width: 6px; }
.review-scrollable::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }

.question-review-card {
  background: #FAF2E0; border-radius: 12px; padding: 20px;
  display: flex; flex-direction: column; gap: 12px;
  border: 1px solid #f0e4cc;
}

.question-card-header { display: flex; align-items: center; gap: 10px; }
.question-card-num {
  font-size: 15px; font-weight: 700; color: #0E61AC;
  background: #fff; border-radius: 8px; padding: 4px 12px;
}
.question-card-topic { font-size: 12px; color: #86868B; }
.merged-badge {
  font-size: 11px; background: #dbeafe; color: #1e40af;
  padding: 2px 8px; border-radius: 4px; font-weight: 500;
}

/* Image thumbnails row */
.question-card-images { display: flex; gap: 8px; flex-wrap: wrap; }
.question-card-thumb {
  width: 80px; height: 80px; border-radius: 8px; overflow: hidden;
  border: 1px solid #e5e7eb; background: #fff; cursor: pointer;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  transition: border-color 0.15s;
}
.question-card-thumb:hover { border-color: #0E61AC; }
.question-card-thumb-img { width: 100%; height: 60px; object-fit: cover; }
.thumb-label { font-size: 10px; color: #86868B; margin-top: 2px; }

/* Merge / Split actions */
.question-card-actions {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: 8px; border-top: 1px dashed #e5d5b0;
}
.merged-detail { font-size: 12px; color: #86868B; }
.split-btn {
  display: inline-flex; align-items: center; gap: 4px;
  background: none; border: 1px solid #f59e0b; border-radius: 6px;
  color: #d97706; padding: 4px 10px; font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; font-family: var(--font-family);
}
.split-btn:hover { background: #fef3c7; }

/* Sticky confirm button */
.figma-confirm-sticky {
  position: sticky; bottom: 0; background: linear-gradient(180deg, transparent, #fff 30%);
  margin-top: 0; padding-top: 24px;
}

/* Lightbox */
.lightbox-overlay {
  position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,.7);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.lightbox-image { max-width: 90vw; max-height: 90vh; border-radius: 12px; cursor: default; }

/* AI Correction Dialog */
.correction-overlay {
  position: fixed; inset: 0; z-index: 9998; background: rgba(0,0,0,.4);
  display: flex; align-items: center; justify-content: center;
}
.correction-dialog {
  background: #fff; border-radius: 16px; padding: 24px; width: 600px;
  max-width: 90vw; max-height: 85vh; overflow-y: auto; display: flex;
  flex-direction: column; gap: 16px; box-shadow: 0 8px 32px rgba(0,0,0,.15);
}
.correction-dialog-header { display: flex; align-items: center; justify-content: space-between; }
.correction-dialog-header h4 { font-size: 16px; font-weight: 600; color: #1B1B1B; }
.correction-close {
  background: none; border: none; font-size: 22px; color: #86868B;
  cursor: pointer; line-height: 1; padding: 0;
}
.correction-current { display: flex; flex-direction: column; gap: 6px; }
.correction-current-label { font-size: 12px; color: #86868B; }
.correction-current-content {
  background: #FAF2E0; border-radius: 8px; padding: 12px; font-size: 13px;
  line-height: 1.8; color: #454545; max-height: 150px; overflow-y: auto;
}
.correction-current-content :deep(.katex-display) { margin: 6px 0; overflow-x: auto; }
.correction-current-content :deep(.katex) { font-size: 1em; }

.correction-input-row { display: flex; flex-direction: column; gap: 8px; }
.correction-input {
  width: 100%; border: 1px solid #EEEEEE; border-radius: 8px; padding: 10px 12px;
  font-size: 13px; font-family: var(--font-family); color: #454545; line-height: 1.6;
  resize: vertical; outline: none; box-sizing: border-box;
}
.correction-input:focus { border-color: #0E61AC; }
.correction-submit { align-self: flex-end; }

.correction-result { display: flex; flex-direction: column; gap: 8px; }
.correction-result-label { font-size: 12px; font-weight: 500; color: #10b981; }
.correction-result-content {
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
  padding: 12px; font-size: 13px; line-height: 1.8; color: #1B1B1B;
}
.correction-result-content :deep(.katex-display) { margin: 6px 0; overflow-x: auto; }
.correction-result-content :deep(.katex) { font-size: 1em; }

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.card {
  background: #fff; border-radius: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.05);
}

@media (max-width: 768px) {
  .grading-page { padding: 16px; }
  .page-header { flex-direction: column; gap: 12px; }
  .figma-review-wrap { flex-direction: column; }
  .figma-review-left { width: 100%; min-height: 160px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
