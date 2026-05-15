<template>
  <div class="question-card">
    <div class="card-header" @click="expanded = !expanded">
      <div class="header-left">
        <ChevronDown
          :size="16"
          class="chevron"
          :class="{ expanded }"
        />
        <span class="question-number">第{{ index + 1 }}题</span>
        <CheckCircle2 v-if="result.is_correct" :size="18" class="text-success" />
        <XCircle v-else :size="18" class="text-error" />
        <span class="question-title">{{ result.question_text?.slice(0, 40) || '-' }}</span>
      </div>
      <div class="header-right">
        <span class="kp-label" v-if="result.knowledge_points?.[0]">
          {{ result.knowledge_points[0] }}
        </span>
        <span class="expand-hint">{{ expanded ? '收起' : '展开' }}</span>
      </div>
    </div>

    <div class="card-body" v-if="expanded">
      <div class="body-section">
        <h4>题目</h4>
        <p class="question-text">{{ result.question_text || '-' }}</p>
      </div>

      <div class="body-section">
        <h4>你的答案</h4>
        <p class="answer-text">{{ result.student_answer || '-' }}</p>
      </div>

      <div class="body-section" v-if="result.steps?.length">
        <h4>步骤分析</h4>
        <div class="step-list">
          <div
            v-for="step in result.steps"
            :key="step.step_number"
            class="step-item"
            :class="step.status"
          >
            <CheckCircle2 v-if="step.status === 'correct'" :size="16" class="text-success" />
            <XCircle v-else-if="step.status === 'incorrect'" :size="16" class="text-error" />
            <AlertTriangle v-else :size="16" class="text-warning" />
            <div class="step-content">
              <span class="step-num">步骤{{ step.step_number }}</span>
              <span>{{ step.step_content }}</span>
              <span v-if="step.analysis" class="step-analysis">{{ step.analysis }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="score-bar">
        <div class="score-fill" :style="{ width: result.score + '%' }" :class="scoreClass"></div>
        <span class="score-text">{{ result.score }}分</span>
      </div>

      <div class="tags-row" v-if="result.error_type">
        <span class="tag error-tag" :style="{ background: errorTypeColor + '18', color: errorTypeColor }">
          {{ result.error_type }}
        </span>
        <span
          v-for="tag in result.error_tags"
          :key="tag"
          class="tag sub-tag"
        >{{ tag }}</span>
      </div>

      <div class="tags-row" v-if="result.knowledge_points?.length">
        <span
          v-for="kp in result.knowledge_points"
          :key="kp"
          class="tag kp-tag"
        >{{ kp }}</span>
      </div>

      <div class="body-section ai-comment" v-if="result.ai_comment">
        <h4>
          <Bot :size="16" />
          AI 评语
        </h4>
        <p>{{ result.ai_comment }}</p>
      </div>

      <div
        v-if="!result.is_correct && result.correct_answer"
        class="body-section correct-highlight"
      >
        <h4>正确做法</h4>
        <p>{{ result.correct_answer }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ChevronDown, CheckCircle2, XCircle, AlertTriangle, Bot } from 'lucide-vue-next'

const props = defineProps({
  index: { type: Number, default: 0 },
  result: { type: Object, required: true }
})

const expanded = ref(props.index === 0)

const scoreClass = computed(() => {
  if (props.result.score >= 80) return 'high'
  if (props.result.score >= 60) return 'mid'
  return 'low'
})

const errorTypeColor = computed(() => {
  const colors = {
    '概念错误': 'var(--color-tag-concept)',
    '过程错误': 'var(--color-tag-process)',
    '计算错误': 'var(--color-tag-calculation)',
    '审题错误': 'var(--color-tag-reading)',
    '格式错误': 'var(--color-tag-format)'
  }
  return colors[props.result.error_type] || 'var(--color-text-secondary)'
})
</script>

<style scoped>
.question-card {
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-subtle);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  cursor: pointer;
  transition: background 0.15s;
}
.card-header:hover { background: var(--color-bg-main); }

.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 10px; }

.chevron { transition: transform 0.2s; color: var(--color-text-secondary); }
.chevron.expanded { transform: rotate(180deg); }

.question-number { font-weight: 600; font-size: var(--font-base); color: var(--color-text-title); }
.question-title { font-size: var(--font-sm); color: var(--color-text-secondary); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.kp-label {
  font-size: var(--font-xs);
  color: var(--color-primary);
  background: var(--color-primary-light);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}
.expand-hint { font-size: var(--font-xs); color: var(--color-text-secondary); }

.text-success { color: var(--color-success); }
.text-error { color: var(--color-error); }
.text-warning { color: var(--color-warning); }

.card-body { padding: 0 20px 20px; display: flex; flex-direction: column; gap: 16px; }

.body-section h4 {
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--color-text-title);
  margin-bottom: 6px;
}

.question-text, .answer-text {
  font-size: var(--font-base);
  color: var(--color-text-body);
  line-height: 1.7;
}

.step-list { display: flex; flex-direction: column; gap: 8px; }
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-base);
  font-size: var(--font-sm);
}
.step-item.correct { background: var(--color-step-correct-bg); border-left: 3px solid var(--color-success); }
.step-item.incorrect { background: var(--color-step-error-bg); border-left: 3px solid var(--color-error); }
.step-item.partially_correct { background: rgba(245, 158, 11, 0.08); border-left: 3px solid var(--color-warning); }

.step-content { display: flex; flex-direction: column; gap: 2px; }
.step-num { font-weight: 600; font-size: var(--font-xs); color: var(--color-text-secondary); }
.step-analysis { font-size: var(--font-xs); color: var(--color-text-secondary); font-style: italic; }

.score-bar {
  height: 28px;
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
}

.score-fill { height: 100%; border-radius: var(--radius-base); transition: width 0.5s ease; }
.score-fill.high { background: var(--color-success); }
.score-fill.mid { background: var(--color-warning); }
.score-fill.low { background: var(--color-error); }

.score-text {
  position: absolute;
  right: 10px;
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--color-text-title);
}

.tags-row { display: flex; flex-wrap: wrap; gap: 6px; }

.tag {
  font-size: var(--font-xs);
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.error-tag { }
.sub-tag { background: var(--color-bg-main); color: var(--color-text-body); }
.kp-tag { background: var(--color-primary-light); color: var(--color-primary); }

.ai-comment {
  background: var(--color-bg-main);
  border-radius: var(--radius-base);
  padding: 12px;
}
.ai-comment h4 { display: flex; align-items: center; gap: 6px; }
.ai-comment p { font-size: var(--font-sm); color: var(--color-text-body); line-height: 1.6; }

.correct-highlight {
  background: var(--color-step-correct-bg);
  border-left: 3px solid var(--color-success);
  border-radius: 0 var(--radius-base) var(--radius-base) 0;
  padding: 12px;
}
.correct-highlight p { font-size: var(--font-sm); color: var(--color-text-body); }
</style>
