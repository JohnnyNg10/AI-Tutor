<!-- src/pages/RecommendView.vue -->
<template>
  <AppLayout>
    <div class="content">
      <!-- 页头 -->
      <div class="header-row">
        <h1>
          <Sparkles :size="24" />
          个性化推荐
        </h1>
        <div v-if="redisOk !== null" class="redis-badge" :class="redisOk ? 'online' : 'offline'">
          {{ redisOk ? '实时推荐' : '离线模式' }}
        </div>
      </div>

      <p class="sub">基于你的学习画像，AI 为你精心挑选最合适的题目</p>
      <p v-if="error" class="error">{{ error }}</p>

      <!-- Advisor 模式 + 画像快照 -->
      <div v-if="profileSnap.theta" class="advisor-mode-card" :class="advisorModeClass">
        <div class="mode-icon">{{ modeIcon }}</div>
        <div class="mode-body">
          <div class="mode-label">{{ modeName }}</div>
          <div class="mode-reason">{{ advisorInstruction?.reasoning }}</div>
        </div>
        <div class="mode-stats">
          <span>做题 {{ profileSnap.total_questions }}</span>
          <span>薄弱 {{ (profileSnap.weak_kps || []).join('、') || '暂无' }}</span>
        </div>
      </div>

      <!-- 学习目标头部 -->
      <LearningGoalHeader
        v-if="learningGoal && !loading && recommendations.length > 0"
        :goal="learningGoal"
        :completed="currentIndex"
        :total="recommendations.length"
      />

      <!-- 操作栏 -->
      <div class="action-bar">
        <select v-model="limit" class="limit-select">
          <option :value="3">3 题</option>
          <option :value="5">5 题</option>
          <option :value="8">8 题</option>
        </select>
        <button class="refresh-btn" :disabled="loading" @click="loadRecommendations">
          <span v-if="loading">推荐中…</span>
          <span v-else>换一批</span>
        </button>
      </div>

      <!-- 加载骨架屏 -->
      <div v-if="loading" class="skeleton-list">
        <div v-for="i in limit" :key="i" class="skeleton-card"></div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="recommendations.length === 0" class="empty-state">
        <div class="empty-icon"> </div>
        <p>暂无推荐题目</p>
        <p class="empty-sub">先去 AI 提问区做几道题，系统会根据你的水平推荐合适的练习！</p>
        <button class="primary-btn" @click="initAndLoad">初始化画像并推荐</button>
      </div>

      <!-- ===== 答题模式：进度条 ===== -->
      <div v-if="!loading && recommendations.length > 0" class="quiz-progress">
        <div class="qp-info">
          <span class="qp-cur">第 {{ currentIndex + 1 }} 题</span>
          <span class="qp-total">/ {{ recommendations.length }}</span>
          <span class="qp-stats">
            {{ correctCount }} / {{ wrongCount }}
          </span>
        </div>
        <div class="qp-bar-bg">
          <div class="qp-bar-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
      </div>

      <!-- ===== 答题模式：当前题卡片 ===== -->
      <div v-if="!loading && currentQ" class="problem-card quiz-card"
           :class="{ 'is-review': currentQ.is_review }">

        <!-- 卡片头 -->
        <div class="card-header">
          <div class="card-num">#{{ currentIndex + 1 }}</div>
          <div class="card-badges">
            <span v-if="currentQ.is_review" class="badge review">复习</span>
            <span class="badge type-badge">
              {{ isChoice(currentQ) ? '选择题' : '解答题' }}
            </span>
            <span class="badge difficulty" :class="diffClass(currentQ.difficulty)">
              难度 {{ currentQ.difficulty }}
            </span>
          </div>
          <div class="card-score">{{ currentQ.recommendation_reason }}</div>
        </div>

        <!-- 题目内容 -->
        <div class="card-content" v-html="renderMath(currentQ.content)"></div>

        <!-- 知识点 -->
        <div class="card-kps">
          <span v-for="kp in (currentQ.knowledge_points || [])" :key="kp" class="kp-tag">{{ kp }}</span>
        </div>

        <!-- ===== 答题区：未提交 ===== -->
        <template v-if="!currentResult">

          <!-- 提示按钮栏 (L0-L4) -->
          <HintButtonBar
            :question-id="currentQ.id"
            :used-hint-levels="usedHints[currentQ.id] || []"
            @requestHint="(level) => requestHint(currentQ, level)"
          />

          <!-- 选择题 -->
          <div v-if="isChoice(currentQ)" class="card-actions">
            <div class="choice-options">
              <button
                v-for="opt in parseChoices(currentQ.content)"
                :key="opt.key"
                class="choice-btn"
                :class="{ selected: selectedChoice[currentQ.id] === opt.key }"
                @click="selectChoice(currentQ, opt.key)"
              >
                <span class="choice-key">{{ opt.key }}</span>
                <span class="choice-text" v-html="renderMath(opt.text)"></span>
              </button>
            </div>
            <div class="btn-group mt-8">
              <button
                class="act-btn confirm-btn"
                :disabled="!selectedChoice[currentQ.id]"
                @click="submitChoiceAnswer(currentQ)"
              >确认作答</button>
              <button class="act-btn skip-easy" @click="skipQuestion(currentQ, 'too_easy')">太简单，跳过</button>
              <button class="act-btn skip-hard" @click="skipQuestion(currentQ, 'too_hard')">太难了，跳过</button>
            </div>
          </div>

          <!-- 大题 -->
          <div v-else class="card-actions">
            <OCRUploader
              :question-id="currentQ.id"
              @ocrComplete="(text) => { answerMap[currentQ.id] = text }"
            />
            <textarea
              v-model="answerMap[currentQ.id]"
              class="answer-textarea"
              placeholder="请写出你的解题过程和答案…（也可拍照上传手写草稿）"
              rows="5"
            ></textarea>
            <div class="btn-group">
              <button
                class="act-btn ai-grade"
                :disabled="gradingSet.has(currentQ.id) || !answerMap[currentQ.id]"
                @click="submitEssayAnswer(currentQ)"
              >
                <span v-if="gradingSet.has(currentQ.id)">AI批改中…</span>
                <span v-else>提交AI批改</span>
              </button>
              <button class="act-btn skip-easy" @click="skipQuestion(currentQ, 'too_easy')">太简单，跳过</button>
              <button class="act-btn skip-hard" @click="skipQuestion(currentQ, 'too_hard')">太难了，跳过</button>
            </div>
          </div>
        </template>

        <!-- ===== 结果区：已提交 ===== -->
        <template v-else>
          <!-- 答对 -->
          <div v-if="currentResult.isCorrect" class="result-correct">
            <div class="result-icon"> </div>
            <div class="result-correct-msg">答对了！</div>
            <div v-if="currentResult.feedback" class="result-detail"
                 v-html="renderMath(currentResult.feedback)"></div>
            <button class="act-btn next-btn" @click="goNext">
              {{ isLast ? '查看本轮总结' : '下一题' }}
            </button>
          </div>

          <!-- 答错 → RetryPanel (结构化诊断+引导重试) -->
          <div v-else class="result-wrong">
            <div class="result-icon"> </div>
            <div class="result-wrong-msg">
              <span v-if="currentResult.chosenKey">你选了 {{ currentResult.chosenKey }}，</span>答错了
              <span v-if="currentResult.correctKey">（正确答案：{{ currentResult.correctKey }}）</span>
            </div>

            <!-- AI 解析 -->
            <div v-if="currentResult.feedback" class="analysis-card">
              <div class="analysis-title">AI 解析</div>
              <div class="analysis-body" v-html="renderMath(currentResult.feedback)"></div>
            </div>

            <!-- 结构化错因诊断 + 引导重试 -->
            <RetryPanel
              v-if="currentResult.errorDiagnosis"
              :diagnosis="currentResult.errorDiagnosis"
              @retry="retryCurrentQuestion"
              @showAnswer="showFullAnswer"
              @skip="goNext"
            />

            <!-- 诊断加载中 -->
            <div v-else-if="diagnosing" class="diagnosis-loading">AI 正在分析你的问题…</div>

            <!-- 无诊断时也提供跳过按钮 -->
            <button v-if="!currentResult.errorDiagnosis && !diagnosing" class="act-btn next-btn wrong-next" @click="goNext">
              {{ isLast ? '查看本轮总结' : '下一题' }}
            </button>
          </div>
        </template>
      </div>

      <!-- ===== 全部完成总结 ===== -->
      <RoundSummary
        v-if="!loading && recommendations.length > 0 && allDone"
        :summary="roundSummaryData"
        @continue="loadRecommendations"
        @focusWeak="(kp) => loadRecommendations()"
      />
    </div>
    <!-- Hint Popup -->
    <HintPopup
      :visible="hintPopup.visible"
      :loading="hintPopup.loading"
      :level="hintPopup.level"
      :content-html="hintPopup.contentHtml"
      @close="closeHintPopup"
      @reopen=""
    />
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import AppLayout from '../components/AppLayout.vue'
import LearningGoalHeader from '../components/recommend/LearningGoalHeader.vue'
import HintButtonBar from '../components/recommend/HintButtonBar.vue'
import HintPopup from '../components/recommend/HintPopup.vue'
import OCRUploader from '../components/recommend/OCRUploader.vue'
import RetryPanel from '../components/recommend/RetryPanel.vue'
import RoundSummary from '../components/recommend/RoundSummary.vue'
import { advisorAPI, chatAPI } from '../services/apiService'
import katex from 'katex'

// 状态
const loading = ref(false)
const error = ref('')
const redisOk = ref(null)
const limit = ref(5)

const recommendations = ref([])
const answerMap = reactive({})
const selectedChoice = reactive({})   // 选择题当前选中项
const submittedSet = ref(new Set())
const gradingSet = ref(new Set())     // 正在 AI 批改中的题目 id

// ===== 答题模式状态 =====
const currentIndex = ref(0)           // 当前题目索引
const currentResult = ref(null)       // { isCorrect, feedback, chosenKey, correctKey, diagnosis }
const diagnosing = ref(false)         // 正在 AI 分析问题所在

const currentQ = computed(() => recommendations.value[currentIndex.value] ?? null)
const isLast = computed(() => currentIndex.value >= recommendations.value.length - 1)
const allDone = computed(() => currentIndex.value >= recommendations.value.length)

const correctCount = ref(0)
const wrongCount = ref(0)
const skipCount = ref(0)

const progressPct = computed(() => {
  if (!recommendations.value.length) return 0
  return Math.round((currentIndex.value / recommendations.value.length) * 100)
})
const doneAccuracy = computed(() => {
  const total = correctCount.value + wrongCount.value
  if (!total) return 0
  return Math.round(correctCount.value / total * 100)
})

const profileSnap = reactive({
  theta: null,
  avg_mastery: null,
  weak_kps: [],
  total_questions: 0,
})
const advisorMode = ref('')
const advisorInstruction = ref(null)
const learningGoal = ref(null)

// 提示系统
const usedHints = reactive({})       // { questionId: [1, 2, ...] }
const hintCache = reactive({})       // { `${questionId}_${level}`: "hint text" }

// Hint popup state
const hintPopup = reactive({
  visible: false,
  loading: false,
  level: 1,
  contentHtml: '',
})

// 错因诊断缓存
const errorDiagnosisResults = reactive({})  // { questionId: ErrorDiagnosisResult }

// 本轮统计
const roundErrorTypes = reactive({}) // { error_type: count }
const roundMasteryChanges = reactive([])  // [{ kp_name, before, after, change }]

// 计算属性
const advisorModeClass = computed(() => ({
  'mode-scaffold': advisorMode.value === 'MODE_SCAFFOLD',
  'mode-challenge': advisorMode.value === 'MODE_CHALLENGE',
  'mode-encourage': advisorMode.value === 'MODE_ENCOURAGE',
}))
const modeIcon = computed(() => ({
  MODE_SCAFFOLD: ' ',
  MODE_CHALLENGE: ' ',
  MODE_ENCOURAGE: ' ',
}[advisorMode.value] || ' '))
const modeName = computed(() => ({
  MODE_SCAFFOLD: '脚手架模式 — 分步引导',
  MODE_CHALLENGE: '挑战模式 — 自主探索',
  MODE_ENCOURAGE: '鼓励模式 — 适度引导',
}[advisorMode.value] || '智能模式'))

const roundSummaryData = computed(() => {
  const total = correctCount.value + wrongCount.value
  return {
    correct_count: correctCount.value,
    wrong_count: wrongCount.value,
    skipped_count: skipCount.value,
    accuracy: total ? Math.round(correctCount.value / total * 100) : 0,
    mastery_changes: roundMasteryChanges.filter(mc => Math.abs(mc.change) > 0.01),
    error_distribution: { ...roundErrorTypes },
    weakest_kp: learningGoal.value?.focus_knowledge_points?.[0] || null,
    next_suggestion: correctCount.value > wrongCount.value
      ? '继续保持！建议挑战更高难度的题目。'
      : '建议重点复习薄弱知识点后再来挑战。',
  }
})

const pct = (v) => v != null ? (v * 100).toFixed(0) + '%' : '-'
const diffClass = (d) => d <= 1 ? 'easy' : d <= 2 ? 'medium' : d <= 3 ? 'hard' : 'expert'

// -------- 数学公式渲染 --------
const renderMath = (text) => {
  if (!text) return ''
  let content = String(text)
  const mathBlocks = []

  // 兼容 \[...\] 和 \(...\) 语法
  content = content
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, f) => `$$${f}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, f) => `$${f}$`)

  // 块级公式 $$...$$
  content = content.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), { throwOnError: false, displayMode: true })
      const token = `@@MATH${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch { return `<span class="latex-error">${formula}</span>` }
  })

  // 行内公式 $...$
  content = content.replace(/\$([^\n$]+?)\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), { throwOnError: false, displayMode: false })
      const token = `@@MATH${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch { return `<span class="latex-error">${formula}</span>` }
  })

  // 普通文本转义（避免 XSS），再恢复 token
  content = content
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  content = content.replace(/@@MATH(\d+)@@/g, (_, i) => mathBlocks[Number(i)] || '')
  return content
}

// -------- 题型判断 --------
const isChoice = (item) =>
  ['single_choice', 'multiple_choice', 'choice'].includes((item.question_type || '').toLowerCase())

/**
 * 从题目 content 里解析选项，支持：
 *   "A. xxx  B. xxx  C. xxx  D. xxx"
 *   "A）xxx\nB）xxx"
 *   "（A）xxx  （B）xxx"
 */
const parseChoices = (content) => {
  if (!content) return []
  // 先把题干与选项分开：找到第一个 A. / A） / （A） 的位置
  const splitReg = /(?:^|\n)\s*[（(]?A[）)．.\s]/
  const splitIdx = content.search(splitReg)
  const optionStr = splitIdx >= 0 ? content.slice(splitIdx) : content

  // 按 B/C/D 边界切割（允许选项文字含任何字符，包括公式）
  const parts = optionStr.split(/\n?\s*[（(]?([B-D])[）)．.\s]/)
  const opts = []

  if (parts.length >= 3) {
    // parts[0] = A 选项内容，parts[1] = 'B', parts[2] = B 选项内容, ...
    const firstMatch = optionStr.match(/[（(]?A[）)．.\s]\s*(.+?)(?=\s*[（(]?B[）)．.\s]|$)/s)
    if (firstMatch) opts.push({ key: 'A', text: firstMatch[1].trim() })
    for (let i = 1; i + 1 < parts.length; i += 2) {
      opts.push({ key: parts[i], text: parts[i + 1].trim() })
    }
  }

  // fallback：按行解析
  if (opts.length < 2) {
    const lines = content.split('\n')
    for (const line of lines) {
      const m = line.trim().match(/^[（(]?([A-D])[）)．.\s]\s*(.+)/)
      if (m) opts.push({ key: m[1], text: m[2].trim() })
    }
  }
  return opts
}

const selectChoice = (item, key) => {
  selectedChoice[item.id] = key
}

// -------- 选择题提交 --------
const submitChoiceAnswer = async (item) => {
  const chosen = selectedChoice[item.id]
  if (!chosen) return

  const stdRaw = (item.standard_answer || '').toUpperCase().replace(/[,，\s]/g, '')
  let isCorrect
  if (stdRaw) {
    isCorrect = stdRaw.includes(chosen)
  } else {
    isCorrect = confirm(`你选了 ${chosen}，你认为答对了吗？\n\n确定=答对，取消=答错`)
  }

  currentResult.value = {
    isCorrect,
    chosenKey: chosen,
    correctKey: stdRaw || null,
    feedback: isCorrect
      ? `正确答案是 ${stdRaw}，你答对了！`
      : `正确答案是 ${stdRaw || '未知'}。`,
    diagnosis: null,
  }

  if (isCorrect) {
    correctCount.value++
  } else {
    wrongCount.value++
    // 答错：异步请求 AI 给出解析和问题诊断
    _requestDiagnosis(item, chosen, null)
  }

  await _doFeedback(item, isCorrect)
}

// -------- 大题 AI 批改提交 --------
const submitEssayAnswer = async (item) => {
  const userAnswer = (answerMap[item.id] || '').trim()
  if (!userAnswer) return

  gradingSet.value = new Set([...gradingSet.value, item.id])
  try {
    const res = await chatAPI.gradeAnswer({
      questionContent: item.content,
      standardAnswer: item.standard_answer || null,
      userAnswer,
      knowledgePoints: item.knowledge_points || [],
    })

    const isCorrect = !!res?.is_correct
    const score = res?.score ?? (isCorrect ? 100 : 0)
    const feedback = res?.feedback || (isCorrect ? '解答正确！' : '解答有误。')

    currentResult.value = {
      isCorrect,
      chosenKey: null,
      correctKey: null,
      feedback: `${isCorrect ? '' : ''} 得分 ${score}：${feedback}`,
      diagnosis: null,
    }

    if (isCorrect) {
      correctCount.value++
    } else {
      wrongCount.value++
      _requestDiagnosis(item, null, userAnswer)
    }

    await _doFeedback(item, isCorrect)
  } catch (e) {
    alert(e?.message || 'AI批改失败，请重试')
  } finally {
    const s = new Set(gradingSet.value)
    s.delete(item.id)
    gradingSet.value = s
  }
}

// -------- 答错时向 AI 请求结构化诊断 --------
const _requestDiagnosis = async (item, chosenKey, userAnswer) => {
  diagnosing.value = true
  try {
    const userInput = chosenKey ? `选了 ${chosenKey}` : (userAnswer || '')
    const token = localStorage.getItem('access_token')

    // 使用新的结构化诊断 API
    const res = await fetch('/api/error-classification/diagnose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        question_text: item.content,
        standard_answer: item.standard_answer || '',
        student_answer: userInput,
        knowledge_points: item.knowledge_points || [],
        user_mastery: profileSnap.knowledge_mastery || {},
        hint_levels_used: (usedHints[item.id] || []).length,
      })
    })

    if (res.ok) {
      const data = await res.json()
      if (data.success && data.diagnosis) {
        errorDiagnosisResults[item.id] = data.diagnosis
        if (currentResult.value) {
          currentResult.value = { ...currentResult.value, errorDiagnosis: data.diagnosis }
        }
        // 统计错因类型
        const et = data.diagnosis.primary_error_type
        roundErrorTypes[et] = (roundErrorTypes[et] || 0) + 1
        return
      }
    }

    // 降级：使用旧 API
    const oldRes = await chatAPI.diagnose({
      questionContent: item.content,
      standardAnswer: item.standard_answer || null,
      userAnswer: userInput,
      knowledgePoints: item.knowledge_points || [],
    })
    const text = oldRes?.diagnosis || ''
    if (currentResult.value && text) {
      currentResult.value = { ...currentResult.value, diagnosis: text }
    }
  } catch { /* 诊断失败不阻塞 */ } finally {
    diagnosing.value = false
  }
}

// -------- L0-L4 提示请求 --------
const levelLabels = { 1: '方向', 2: '公式', 3: '步骤', 4: '解析' }
const requestHint = async (item, level) => {
  const cacheKey = `${item.id}_${level}`

  // 打开 popup
  hintPopup.visible = true
  hintPopup.level = level
  hintPopup.loading = true
  hintPopup.contentHtml = ''

  if (hintCache[cacheKey]) {
    hintPopup.loading = false
    hintPopup.contentHtml = renderMath(hintCache[cacheKey])
    if (!usedHints[item.id]) usedHints[item.id] = []
    if (!usedHints[item.id].includes(level)) usedHints[item.id].push(level)
    return
  }

  try {
    const res = await chatAPI.generateHint({
      hintLevel: level,
      questionContent: item.content,
      knowledgePoints: item.knowledge_points || [],
    })
    const text = res?.content || res?.hint || ''
    hintCache[cacheKey] = text
    hintPopup.contentHtml = renderMath(text)
    if (!usedHints[item.id]) usedHints[item.id] = []
    if (!usedHints[item.id].includes(level)) usedHints[item.id].push(level)
  } catch {
    hintPopup.contentHtml = '<p style="color:#86868B">提示生成失败，请重试</p>'
  } finally {
    hintPopup.loading = false
  }
}

const closeHintPopup = () => {
  hintPopup.visible = false
  hintPopup.contentHtml = ''
}

// -------- 重试当前题 --------
const retryCurrentQuestion = () => {
  const item = currentQ.value
  if (!item) return
  currentResult.value = null
  selectedChoice[item.id] = null
  answerMap[item.id] = ''
}

// -------- 查看完整解析 --------
const showFullAnswer = async () => {
  const item = currentQ.value
  if (!item) return
  try {
    const res = await chatAPI.generateHint({
      questionContent: item.content,
      standardAnswer: item.standard_answer || '',
      hintLevel: 4,
      knowledgePoints: item.knowledge_points || [],
    })
    const text = res?.hint || res?.content || item.standard_answer || '暂无解析'
    currentResult.value = { ...currentResult.value, feedback: (currentResult.value?.feedback || '') + '\n\n【完整解析】\n' + text }
  } catch { /* 失败静默 */ }
}

// -------- 下一题 --------
const goNext = () => {
  currentResult.value = null
  currentIndex.value++
}

// -------- 公共：把结果写入画像 --------
const _doFeedback = async (item, isCorrect) => {
  try {
    await advisorAPI.submitFeedback({
      questionId: item.id,
      isCorrect,
      hintCount: 0,
      timeSpent: null,
      algorithmVersion: 'advisor-v1',
      recommendationSessionId: `web-${Date.now()}`,
    })
    submittedSet.value = new Set([...submittedSet.value, item.id])

    // 若全部完成，刷新画像快照
    if (submittedSet.value.size === recommendations.value.length) {
      try {
        const prof = await advisorAPI.getProfile()
        const snap = prof?.data || {}
        Object.assign(profileSnap, {
          theta: snap.theta,
          avg_mastery: snap.avg_mastery,
          weak_kps: Object.entries(snap.knowledge_mastery || {})
            .sort((a, b) => a[1] - b[1]).slice(0, 3).map(e => e[0]),
          total_questions: snap.total_questions,
        })
      } catch {}
    }
  } catch (e) {
    alert(e?.message || '提交失败，请重试')
  }
}

// -------- 跳过 --------
const skipQuestion = async (item, skipReason) => {
  try {
    await advisorAPI.submitFeedback({
      questionId: item.id,
      isCorrect: skipReason === 'too_easy',
      skipReason,
      algorithmVersion: 'advisor-v1',
    })
    submittedSet.value = new Set([...submittedSet.value, item.id])
    skipCount.value++
    currentResult.value = null
    currentIndex.value++
  } catch (e) {
    alert(e?.message || '跳过提交失败')
  }
}

// -------- 检查 Redis --------
const checkRedis = async () => {
  try {
    const res = await advisorAPI.redisHealth()
    redisOk.value = res?.redis_available ?? false
  } catch {
    redisOk.value = false
  }
}

// -------- 加载推荐 --------
const loadRecommendations = async () => {
  loading.value = true
  error.value = ''
  submittedSet.value = new Set()
  // 重置答题模式
  currentIndex.value = 0
  currentResult.value = null
  diagnosing.value = false
  correctCount.value = 0
  wrongCount.value = 0
  skipCount.value = 0
  try {
    const res = await advisorAPI.getRecommendations({ limit: limit.value })
    const data = res?.data || {}
    recommendations.value = data.recommendations || []
    advisorMode.value = data.advisor_mode || ''
    advisorInstruction.value = data.advisor_instruction || null
    learningGoal.value = data.learning_goal || null
    const snap = data.profile_snapshot || {}
    Object.assign(profileSnap, snap)
    // 重置本轮统计
    Object.keys(roundErrorTypes).forEach(k => delete roundErrorTypes[k])
    roundMasteryChanges.splice(0)
  } catch (e) {
    error.value = e?.message || '获取推荐失败，请重试'
    recommendations.value = []
  } finally {
    loading.value = false
  }
}

// -------- 初始化画像再推荐 --------
const initAndLoad = async () => {
  loading.value = true
  error.value = ''
  try {
    await advisorAPI.initProfile()
    await loadRecommendations()
  } catch (e) {
    error.value = e?.message || '初始化失败'
    loading.value = false
  }
}

onMounted(async () => {
  await checkRedis()
  await loadRecommendations()
})
</script>

<style scoped>
/* === Base (from design system) === */
.content { padding: 32px; max-width: var(--max-content-width); margin: 0 auto; }

.header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
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

.btn {
  border: none; border-radius: var(--radius-base); padding: 8px 16px;
  background: var(--color-primary); color: #fff; cursor: pointer;
  font-size: 13px; font-family: var(--font-family); transition: all 0.2s;
}
.btn:hover { background: var(--color-primary-hover); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* === Page-specific: Redis badge === */
.redis-badge { padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.redis-badge.online { background: #e6f4ea; color: #137333; }
.redis-badge.offline { background: #fce8e6; color: #c5221f; }

/* === Page-specific: Advisor mode === */
.advisor-mode-card { display: flex; align-items: center; gap: 16px; padding: 16px 20px; border-radius: 14px; margin-bottom: 20px; border: 1.5px solid transparent; }
.advisor-mode-card.mode-scaffold { background: #fff8e1; border-color: #ffc107; }
.advisor-mode-card.mode-challenge { background: #e8f5e9; border-color: #4caf50; }
.advisor-mode-card.mode-encourage { background: #e3f2fd; border-color: #2196f3; }
.mode-icon { font-size: 28px; flex-shrink: 0; }
.mode-body { flex: 1; }
.mode-label { font-size: 15px; font-weight: 700; color: #1d1d1f; margin-bottom: 4px; }
.mode-reason { font-size: 13px; color: #555; line-height: 1.5; }
.mode-stats { display: flex; flex-direction: column; gap: 4px; text-align: right; font-size: 12px; color: #666; flex-shrink: 0; }

/* === Page-specific: Action bar === */
.action-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
.limit-select { border: 1px solid #d0d7e2; border-radius: 8px; padding: 8px 12px; font-size: 13px; cursor: pointer; background: white; }
.refresh-btn { padding: 8px 20px; border: none; border-radius: 10px; background: #0071e3; color: white; font-size: 14px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.refresh-btn:disabled { background: #aac7f0; cursor: not-allowed; }
.refresh-btn:hover:not(:disabled) { background: #005bb5; }

/* === Page-specific: Skeleton === */
.skeleton-list { display: flex; flex-direction: column; gap: 16px; }
.skeleton-card { height: 180px; background: linear-gradient(90deg,#f0f0f0 25%,#e8e8e8 50%,#f0f0f0 75%); background-size: 200% 100%; border-radius: 16px; animation: shimmer 1.4s infinite; }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* === Page-specific: Empty state === */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-state p { font-size: 16px; color: #555; margin-bottom: 8px; }
.empty-sub { font-size: 14px; color: #999; margin-bottom: 24px; }
.primary-btn { padding: 12px 28px; background: #0071e3; color: white; border: none; border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.primary-btn:hover { background: #005bb5; }

/* === Page-specific: Quiz progress === */
.quiz-progress { margin-bottom: 18px; }
.qp-info { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.qp-cur { font-size: 18px; font-weight: 700; color: #1d1d1f; }
.qp-total { font-size: 14px; color: #86868b; }
.qp-stats { margin-left: auto; font-size: 13px; color: #555; }
.qp-bar-bg { width: 100%; height: 8px; background: #e0e0e0; border-radius: 999px; overflow: hidden; }
.qp-bar-fill { height: 100%; background: linear-gradient(90deg, #0071e3, #34c759); border-radius: 999px; transition: width 0.4s ease; }

/* === Page-specific: Quiz card === */
.quiz-card { background: white; border-radius: 18px; padding: 28px; border: 1.5px solid #e5e5e5; box-shadow: 0 4px 24px rgba(0,0,0,.06); }
.quiz-card.is-review { border-color: #ff9800; background: #fffdf5; }

.card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.card-num { width: 34px; height: 34px; background: #f0f7ff; color: #0071e3; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; }
.card-badges { display: flex; gap: 6px; flex-wrap: wrap; flex: 1; }
.badge { padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.badge.review { background: #fff3e0; color: #e65100; }
.badge.type-badge { background: #e8f5e9; color: #2e7d32; }
.badge.difficulty.easy { background: #e8f5e9; color: #2e7d32; }
.badge.difficulty.medium { background: #e3f2fd; color: #1565c0; }
.badge.difficulty.hard { background: #fff8e1; color: #f57f17; }
.badge.difficulty.expert { background: #fce4ec; color: #ad1457; }
.card-score { font-size: 12px; color: #86868b; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.card-content { font-size: 16px; color: #1d1d1f; line-height: 1.8; margin-bottom: 14px; word-break: break-word; }
.card-content .katex-display { margin: 10px 0; overflow-x: auto; }
.card-content .katex { font-size: 1.08em; }
.latex-error { color: #c0392b; font-style: italic; }
.card-kps { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.kp-tag { padding: 3px 9px; background: #f5f5f7; border-radius: 6px; font-size: 12px; color: #555; }

/* === Page-specific: Answer area === */
.card-actions { display: flex; flex-direction: column; gap: 10px; }
.btn-group { display: flex; flex-wrap: wrap; gap: 8px; }
.act-btn { padding: 10px 20px; border: none; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.confirm-btn { background: #0071e3; color: white; }
.confirm-btn:hover:not(:disabled) { background: #005bb5; }
.confirm-btn:disabled { background: #aac7f0; cursor: not-allowed; }
.act-btn.skip-easy { background: #e8eaf6; color: #3949ab; font-size: 13px; padding: 8px 14px; }
.act-btn.skip-easy:hover { background: #c5cae9; }
.act-btn.skip-hard { background: #f3e5f5; color: #6a1b9a; font-size: 13px; padding: 8px 14px; }
.act-btn.skip-hard:hover { background: #e1bee7; }
.mt-8 { margin-top: 8px; }

/* Choice */
.choice-options { display: flex; flex-direction: column; gap: 10px; }
.choice-btn { display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; border: 1.5px solid #e0e0e0; border-radius: 12px; background: #fafafa; cursor: pointer; font-size: 15px; text-align: left; transition: 0.2s; width: 100%; }
.choice-btn:hover { border-color: #0071e3; background: #f0f7ff; }
.choice-btn.selected { border-color: #0071e3; background: #e3f2fd; }
.choice-key { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #e0e0e0; color: #333; font-weight: 700; font-size: 14px; flex-shrink: 0; }
.choice-btn.selected .choice-key { background: #0071e3; color: white; }
.choice-text { flex: 1; line-height: 1.6; }

/* Essay textarea */
.answer-textarea { width: 100%; padding: 12px 14px; border: 1.5px solid #d0d7e2; border-radius: 12px; font-size: 15px; line-height: 1.8; resize: vertical; outline: none; transition: 0.2s; font-family: inherit; box-sizing: border-box; }
.answer-textarea:focus { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.12); }
.act-btn.ai-grade { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
.act-btn.ai-grade:hover:not(:disabled) { opacity: 0.9; }
.act-btn.ai-grade:disabled { background: #c5b8e8; cursor: not-allowed; }

/* === Page-specific: Result area === */
.result-correct, .result-wrong { padding: 20px; border-radius: 14px; margin-top: 4px; }
.result-correct { background: #e8f5e9; border: 1.5px solid #81c784; }
.result-wrong { background: #fff8f8; border: 1.5px solid #ef9a9a; }
.result-icon { font-size: 36px; text-align: center; margin-bottom: 8px; }
.result-correct-msg { font-size: 18px; font-weight: 700; color: #2e7d32; text-align: center; margin-bottom: 12px; }
.result-wrong-msg { font-size: 16px; font-weight: 700; color: #c62828; text-align: center; margin-bottom: 14px; }
.result-detail { font-size: 14px; color: #444; line-height: 1.7; margin-bottom: 14px; text-align: center; }

.analysis-card, .diagnosis-card { background: white; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; border: 1px solid #e0e0e0; }
.analysis-title { font-size: 13px; font-weight: 700; color: #555; margin-bottom: 8px; }
.analysis-body { font-size: 14px; color: #333; line-height: 1.8; }
.diagnosis-loading { font-size: 13px; color: #888; padding: 8px 0; }

.next-btn { background: #0071e3; color: white; display: block; width: 100%; text-align: center; margin-top: 14px; padding: 12px; font-size: 15px; }
.next-btn:hover { background: #005bb5; }
.next-btn.wrong-next { background: #555; }
.next-btn.wrong-next:hover { background: #333; }

/* === Page-specific: Summary === */
.all-done { text-align: center; padding: 40px 20px; background: white; border-radius: 18px; border: 1.5px dashed #0071e3; margin-top: 20px; }
.done-emoji { font-size: 48px; margin-bottom: 12px; }
.done-title { font-size: 22px; font-weight: 700; color: #1d1d1f; margin-bottom: 16px; }
.done-stats { display: flex; justify-content: center; gap: 24px; margin-bottom: 12px; }
.done-stat { font-size: 15px; font-weight: 600; padding: 6px 14px; border-radius: 999px; }
.done-stat.correct { background: #e8f5e9; color: #2e7d32; }
.done-stat.wrong { background: #fce4ec; color: #c62828; }
.done-stat.skip { background: #f3f4f6; color: #555; }
.done-accuracy { font-size: 28px; font-weight: 800; color: #0071e3; margin-bottom: 20px; }
.mt-16 { margin-top: 16px; }

/* === Responsive === */
@media (max-width: 640px) {
  .btn-group { flex-direction: column; }
  .act-btn { text-align: center; }
  .advisor-mode-card { flex-direction: column; align-items: flex-start; }
  .mode-stats { text-align: left; }
  .done-stats { flex-direction: column; align-items: center; gap: 8px; }
}
</style>
