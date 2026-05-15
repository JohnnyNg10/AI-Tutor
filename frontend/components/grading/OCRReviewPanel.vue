<template>
  <div class="ocr-review-panel">
    <div class="review-layout">
      <div class="image-pane">
        <img
          v-if="currentImage"
          :src="currentImage"
          class="review-image"
          @click="$emit('zoom', currentImage)"
          alt="原图"
        />
        <div class="image-placeholder" v-else>无图片</div>

        <div class="image-nav" v-if="totalImages > 1">
          <button class="nav-arrow" :disabled="index === 0" @click="$emit('prev')">
            <ChevronLeft :size="16" />
          </button>
          <span class="nav-indicator">
            <span
              v-for="i in totalImages"
              :key="i"
              class="dot"
              :class="{ active: i - 1 === index, reviewed: correctionStatus[i - 1] }"
            ></span>
          </span>
          <button class="nav-arrow" :disabled="index >= totalImages - 1" @click="$emit('next')">
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>

      <div class="text-pane">
        <div class="text-sections">
          <div class="text-section">
            <div class="section-label">题目</div>
            <div
              class="editable-text"
              :class="{ 'low-confidence': hasLowConfidence('question') }"
            >
              <div
                v-for="(segment, si) in questionSegments"
                :key="'q-' + si"
                class="text-segment"
                :class="{ 'confidence-low': segment.confidence === 'low' }"
              >
                <span
                  v-if="segment.confidence === 'low'"
                  class="low-confidence-icon"
                  title="低置信度，请核对"
                >
                  <AlertTriangle :size="14" />
                </span>
                <span v-html="renderLatex(segment.text)"></span>
              </div>
            </div>
            <textarea
              v-model="editedQuestion"
              class="edit-textarea"
              rows="4"
              placeholder="请核对并修改题目文本..."
            ></textarea>
          </div>

          <div class="text-section">
            <div class="section-label">解题过程</div>
            <div
              class="editable-text"
              :class="{ 'low-confidence': hasLowConfidence('answer') }"
            >
              <div
                v-for="(segment, si) in answerSegments"
                :key="'a-' + si"
                class="text-segment"
                :class="{ 'confidence-low': segment.confidence === 'low' }"
              >
                <span
                  v-if="segment.confidence === 'low'"
                  class="low-confidence-icon"
                  title="低置信度，请核对"
                >
                  <AlertTriangle :size="14" />
                </span>
                <span v-html="renderLatex(segment.text)"></span>
              </div>
            </div>
            <textarea
              v-model="editedAnswer"
              class="edit-textarea"
              rows="6"
              placeholder="请核对并修改解题过程文本..."
            ></textarea>
          </div>
        </div>

        <div class="review-footer">
          <span class="review-progress">已完成 {{ reviewedCount }}/{{ totalImages }} 题的校对</span>
          <button class="btn btn-primary" @click="$emit('confirm')">
            确认无误，开始批改
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-vue-next'
import katex from 'katex'

const props = defineProps({
  currentImage: { type: String, default: '' },
  index: { type: Number, default: 0 },
  totalImages: { type: Number, default: 0 },
  correctionStatus: { type: Object, default: () => ({}) },
  segments: { type: Object, default: () => ({ question: [], answer: [] }) }
})

const emit = defineEmits(['prev', 'next', 'zoom', 'confirm'])

const editedQuestion = ref('')
const editedAnswer = ref('')

const questionSegments = computed(() => props.segments?.question || [])
const answerSegments = computed(() => props.segments?.answer || [])

const reviewedCount = computed(() =>
  Object.values(props.correctionStatus).filter(Boolean).length
)

function hasLowConfidence(type) {
  const segs = type === 'question' ? questionSegments.value : answerSegments.value
  return segs.some(s => s.confidence === 'low')
}

function renderLatex(text) {
  if (!text) return ''
  return text.replace(/\$([^$]+)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula, { throwOnError: false, displayMode: false })
    } catch {
      return formula
    }
  })
}

watch(() => props.index, () => {
  const q = questionSegments.value.map(s => s.text).join('')
  const a = answerSegments.value.map(s => s.text).join('')
  editedQuestion.value = q
  editedAnswer.value = a
}, { immediate: true })
</script>

<style scoped>
.ocr-review-panel {
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  padding: 20px;
  box-shadow: var(--shadow-subtle);
}

.review-layout {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 24px;
}

.image-pane {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.review-image {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
  border-radius: var(--radius-base);
  cursor: zoom-in;
  background: var(--color-bg-main);
}

.image-placeholder {
  width: 100%;
  height: 200px;
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
}

.image-nav { display: flex; align-items: center; gap: 8px; }
.nav-arrow {
  border: 1px solid var(--color-border);
  background: var(--color-bg-white);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-text-body);
}
.nav-arrow:disabled { opacity: 0.3; cursor: not-allowed; }

.nav-indicator { display: flex; gap: 4px; }
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border);
}
.dot.active { background: var(--color-primary); }
.dot.reviewed { background: var(--color-success); }

.text-pane { display: flex; flex-direction: column; gap: 16px; }

.section-label {
  font-size: var(--font-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.editable-text {
  font-family: var(--font-mono);
  font-size: var(--font-sm);
  color: var(--color-text-body);
  line-height: 1.8;
  padding: 12px;
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  margin-bottom: 8px;
}

.text-segment { display: inline; }

.confidence-low {
  background: var(--color-ocr-low-confidence-bg);
  border: 1px dashed var(--color-ocr-low-confidence-border);
  border-radius: 4px;
  padding: 1px 3px;
  position: relative;
}

.low-confidence-icon {
  display: inline-flex;
  color: var(--color-warning);
  vertical-align: middle;
  margin-right: 2px;
}

.edit-textarea {
  width: 100%;
  font-family: var(--font-mono);
  font-size: var(--font-sm);
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-base);
  resize: vertical;
  background: var(--color-bg-white);
  color: var(--color-text-body);
  line-height: 1.6;
}
.edit-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
}

.review-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.review-progress {
  font-size: var(--font-sm);
  color: var(--color-text-secondary);
}
</style>
