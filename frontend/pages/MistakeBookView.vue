<template>
  <AppLayout>
    <div class="content">
      <!-- ===== 复习模式遮罩 ===== -->
      <div v-if="reviewMode" class="review-overlay">
        <div class="review-modal">
          <!-- 进度 -->
          <div class="review-progress">
            <button class="btn-exit-review" @click="exitReview">退出</button>
            <span class="review-idx">{{ reviewIndex + 1 }} / {{ reviewList.length }}</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: reviewProgress + '%' }"></div>
            </div>
            <span class="review-score">{{ reviewCorrectCount }} / {{ reviewWrongCount }}</span>
          </div>

          <!-- 复习完成 -->
          <div v-if="reviewDone" class="review-done">
            <div class="done-icon"> </div>
            <h2>本轮复习完成！</h2>
            <p>共复习 {{ reviewList.length }} 道错题</p>
            <p>答对 <strong>{{ reviewCorrectCount }}</strong> 道 / 答错 <strong>{{ reviewWrongCount }}</strong> 道</p>
            <p v-if="reviewNewMastered > 0" class="done-mastered">新掌握 {{ reviewNewMastered }} 道题</p>
            <button class="btn-primary" @click="exitReview">返回错题本</button>
          </div>

          <!-- 当前题 -->
          <template v-else-if="currentReviewQ">
            <div class="review-question-card">
              <!-- 题目元信息 -->
              <div class="review-meta">
                <span class="badge-type">{{ typeLabel(currentReviewQ.question_type) }}</span>
                <span class="badge-diff" :class="diffClass(currentReviewQ.difficulty)">
                  {{ diffLabel(currentReviewQ.difficulty) }}
                </span>
                <span class="badge-error">错误 {{ currentReviewQ.error_count }} 次</span>
                <span v-if="currentReviewQ.knowledge_points?.length" class="badge-kp">
                  {{ currentReviewQ.knowledge_points.slice(0, 2).join(' / ') }}
                </span>
              </div>

              <!-- 题目内容 -->
              <div class="review-content" v-html="renderMath(currentReviewQ.question_content || '题目内容缺失')"></div>

              <!-- ===== 未作答区 ===== -->
              <template v-if="!reviewResult">

                <!-- 选择题：解析并渲染选项 -->
                <div v-if="isChoice(currentReviewQ)" class="choice-area">
                  <button
                    v-for="opt in parseChoices(currentReviewQ.question_content)"
                    :key="opt.key"
                    class="choice-btn"
                    :class="{ selected: reviewSelectedChoice === opt.key }"
                    @click="reviewSelectedChoice = opt.key"
                  >
                    <span class="choice-key">{{ opt.key }}</span>
                    <span class="choice-text" v-html="renderMath(opt.text)"></span>
                  </button>
                  <div class="review-actions">
                    <button
                      class="btn-confirm"
                      :disabled="!reviewSelectedChoice"
                      @click="submitReviewChoice"
                    >确认作答</button>
                  </div>
                </div>

                <!-- 大题：文本框 + AI 批改 -->
                <div v-else class="essay-area">
                  <textarea
                    v-model="reviewEssayAnswer"
                    class="review-textarea"
                    placeholder="写出解题过程和答案，提交后由AI批改…"
                    rows="5"
                  ></textarea>
                  <div class="review-actions">
                    <button
                      class="btn-ai-grade"
                      :disabled="reviewGrading || !reviewEssayAnswer.trim()"
                      @click="submitReviewEssay"
                    >
                      <span v-if="reviewGrading">AI批改中…</span>
                      <span v-else>提交AI批改</span>
                    </button>
                  </div>
                </div>
              </template>

              <!-- ===== 已作答结果区 ===== -->
              <template v-else>
                <!-- 答对 -->
                <div v-if="reviewResult.isCorrect" class="result-correct">
                  <div class="result-icon"> </div>
                  <div class="result-correct-msg">答对了！已标记为掌握</div>
                  <div v-if="reviewResult.feedback" class="result-detail"
                       v-html="renderMath(reviewResult.feedback)"></div>
                  <div class="review-actions">
                    <button class="btn-next" @click="goReviewNext">
                      {{ isReviewLast ? '查看本轮总结' : '下一题' }}
                    </button>
                  </div>
                </div>

                <!-- 答错 -->
                <div v-else class="result-wrong">
                  <div class="result-icon"> </div>
                  <div class="result-wrong-msg">
                    <span v-if="reviewResult.chosenKey">你选了 {{ reviewResult.chosenKey }}，</span>答错了
                    <span v-if="reviewResult.correctKey">（正确答案：{{ reviewResult.correctKey }}）</span>
                  </div>

                  <!-- 参考答案 -->
                  <div v-if="currentReviewQ.standard_answer" class="analysis-card">
                    <div class="analysis-title">参考答案</div>
                    <div class="analysis-body" v-html="renderMath(currentReviewQ.standard_answer)"></div>
                  </div>

                  <!-- AI 反馈 -->
                  <div v-if="reviewResult.feedback" class="analysis-card">
                    <div class="analysis-title">AI 解析</div>
                    <div class="analysis-body" v-html="renderMath(reviewResult.feedback)"></div>
                  </div>

                  <!-- AI 诊断 -->
                  <div v-if="reviewResult.diagnosis" class="diagnosis-card">
                    <div class="analysis-title">问题所在</div>
                    <div class="analysis-body" v-html="renderMath(reviewResult.diagnosis)"></div>
                  </div>
                  <div v-else-if="reviewDiagnosing" class="diagnosis-loading">AI 正在分析你的问题…</div>

                  <div class="review-actions">
                    <button class="btn-next wrong-next" @click="goReviewNext">
                      {{ isReviewLast ? '查看本轮总结' : '下一题' }}
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </div>
      </div>

      <!-- ===== 正常页面内容 ===== -->
      <div v-show="!reviewMode">
        <!-- 页头 -->
        <div class="header-row">
          <div class="header-text">
            <h1>错题中心</h1>
            <p class="sub">错题复习+知识点归纳</p>
          </div>
        </div>

        <!-- 二级标签页 -->
        <div class="tab-row">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'summary' }"
            @click="activeTab = 'summary'"
          >错题汇总</button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'induction' }"
            @click="activeTab = 'induction'"
          >错题归纳</button>
        </div>

        <!-- ===== 错题汇总 Tab ===== -->
        <template v-if="activeTab === 'summary'">

        <!-- 统计卡片 -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">总错题</div>
          </div>
          <div class="stat-card warn">
            <div class="stat-value">{{ stats.unmastered }}</div>
            <div class="stat-label">待掌握</div>
          </div>
          <div class="stat-card success">
            <div class="stat-value">{{ stats.mastered }}</div>
            <div class="stat-label">已掌握</div>
          </div>
          <div class="stat-card due" v-if="stats.due_for_review > 0">
            <div class="stat-value">{{ stats.due_for_review }}</div>
            <div class="stat-label">待复习</div>
          </div>
        </div>

        <!-- 复习提醒横幅 -->
        <div v-if="dueItems.length > 0" class="due-banner">
          <span class="due-icon"> </span>
          <span>有 <strong>{{ dueItems.length }}</strong> 道错题到期待复习</span>
          <button class="btn-review-due" @click="startReview('due')">立即复习</button>
        </div>

        <!-- 筛选工具栏 -->
        <div class="toolbar">
          <div class="filter-group">
            <button
              v-for="f in filterOptions"
              :key="f.value"
              class="filter-btn"
              :class="{ active: activeFilter === f.value }"
              @click="setFilter(f.value)"
            >
              {{ f.label }}
            </button>
          </div>

          <div class="toolbar-right">
            <select v-model="filterKp" class="kp-select">
              <option value="">全部知识点</option>
              <option v-for="kp in allKnowledgePoints" :key="kp" :value="kp">{{ kp }}</option>
            </select>

            <button
              v-if="filteredItems.length > 0"
              class="btn-start-review"
              @click="startReview('filtered')"
            >
              开始复习 ({{ filteredItems.length }})
            </button>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>加载错题本中...</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="filteredItems.length === 0" class="empty-state">
          <div class="empty-icon"> </div>
          <h3>{{ emptyText }}</h3>
          <p v-if="activeFilter === 'all' && !filterKp">继续做题，答错的题目会自动收录到这里</p>
          <router-link v-if="activeFilter === 'all' && !filterKp" to="/recommend" class="btn-go-practice">
            去做题
          </router-link>
        </div>

        <!-- 错题列表 -->
        <div v-else class="mistake-list">
          <transition-group name="list" tag="div">
            <div
              v-for="item in filteredItems"
              :key="item.id"
              class="mistake-card"
              :class="{ mastered: item.mastered }"
            >
              <div class="card-header">
                <div class="card-meta">
                  <span class="badge-type">{{ typeLabel(item.question_type) }}</span>
                  <span class="badge-diff" :class="diffClass(item.difficulty)">
                    {{ diffLabel(item.difficulty) }}
                  </span>
                  <span v-if="item.knowledge_points?.length" class="badge-kp">
                    {{ item.knowledge_points.slice(0, 2).join(' / ') }}
                  </span>
                  <span class="badge-error">错 {{ item.error_count }} 次</span>
                  <span v-if="item.mastered" class="badge-mastered">已掌握</span>
                  <span v-else-if="isDue(item)" class="badge-due">待复习</span>
                </div>
                <div class="card-actions">
                  <!-- 展开/收起参考答案 -->
                  <button
                    class="btn-icon btn-expand"
                    :title="item._expanded ? '收起' : '展开答案'"
                    @click="item._expanded = !item._expanded"
                  >{{ item._expanded ? '▲' : '▼' }}</button>
                </div>
              </div>

              <div class="card-question" v-html="renderMath(item.question_content || '题目内容缺失')"></div>

              <transition name="fade">
                <div v-if="item._expanded" class="card-answer-block">
                  <div class="answer-label">参考答案</div>
                  <div class="answer-content" v-html="renderMath(item.standard_answer || '暂无标准答案')"></div>
                </div>
              </transition>

              <div class="card-footer">
                <span class="footer-time">
                  首次错误：{{ formatDate(item.first_error_at) }}
                </span>
                <span v-if="item.next_review_at && !item.mastered" class="footer-review">
                  复习时间：{{ formatDate(item.next_review_at) }}
                </span>
                <button class="btn-review-single" @click="startReviewSingle(item)">做题复习</button>
              </div>
            </div>
          </transition-group>
        </div>

        </template>

        <!-- ===== 错题归纳 Tab ===== -->
        <template v-else>
          <div class="induction-view">
            <div v-if="items.length === 0" class="empty-state">
              <div class="empty-icon"> </div>
              <h3>暂无错题归纳</h3>
              <p>继续做题，答错的题目会自动收录并归纳分析</p>
            </div>
            <div v-else class="induction-grid">
              <div
                v-for="group in kpGroups"
                :key="group.name"
                class="induction-card"
              >
                <div class="induction-kp-name">{{ group.name }}</div>
                <div class="induction-count">{{ group.count }} 道错题</div>
                <div class="induction-mini-bar">
                  <div class="mini-bar-fill" :style="{ width: group.masteryRate + '%' }"></div>
                </div>
                <div class="induction-mastery">{{ group.masteryRate }}% 掌握</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { learningToolsAPI, advisorAPI, chatAPI } from '../services/apiService.js'

const loading = ref(false)
const activeTab = ref('summary') // 'summary' | 'induction'
const items = ref([])
const kpGroups = computed(() => {
  const map = {}
  for (const item of items.value) {
    const kps = item.knowledge_points || ['未分类']
    for (const kp of kps) {
      if (!map[kp]) map[kp] = { name: kp, count: 0, mastered: 0 }
      map[kp].count++
      if (item.mastered) map[kp].mastered++
    }
  }
  return Object.values(map).map(g => ({
    ...g,
    masteryRate: g.count > 0 ? Math.round((g.mastered / g.count) * 100) : 0
  })).sort((a, b) => b.count - a.count)
})
const stats = reactive({ total: 0, unmastered: 0, mastered: 0, due_for_review: 0 })
const dueItems = ref([])

const activeFilter = ref('all')
const filterKp = ref('')

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '待掌握', value: 'unmastered' },
  { label: '已掌握', value: 'mastered' },
  { label: '待复习', value: 'due' },
]

// ---------------------------------------------------------------------------
// 复习模式状态
// ---------------------------------------------------------------------------
const reviewMode = ref(false)
const reviewList = ref([])
const reviewIndex = ref(0)
const reviewDone = ref(false)
const reviewCorrectCount = ref(0)
const reviewWrongCount = ref(0)
const reviewNewMastered = ref(0)

// 当前题答题状态
const reviewResult = ref(null)       // { isCorrect, feedback, chosenKey, correctKey, diagnosis }
const reviewSelectedChoice = ref('') // 选择题当前选中项
const reviewEssayAnswer = ref('')    // 大题作答文本
const reviewGrading = ref(false)     // AI 批改中
const reviewDiagnosing = ref(false)  // AI 诊断中

const reviewProgress = computed(() =>
  reviewList.value.length ? (reviewIndex.value / reviewList.value.length) * 100 : 0
)
const currentReviewQ = computed(() => reviewList.value[reviewIndex.value] ?? null)
const isReviewLast = computed(() => reviewIndex.value >= reviewList.value.length - 1)

// ---------------------------------------------------------------------------
// KaTeX 渲染（与 RecommendView 保持一致）
// ---------------------------------------------------------------------------
const renderMath = (text) => {
  if (!text) return ''
  let content = String(text)
  const mathBlocks = []

  content = content
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, f) => `$$${f}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, f) => `$${f}$`)

  content = content.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), { throwOnError: false, displayMode: true })
      const token = `@@MATH${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch { return `<span class="latex-error">${formula}</span>` }
  })

  content = content.replace(/\$([^\n$]+?)\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), { throwOnError: false, displayMode: false })
      const token = `@@MATH${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch { return `<span class="latex-error">${formula}</span>` }
  })

  content = content
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  content = content.replace(/@@MATH(\d+)@@/g, (_, i) => mathBlocks[Number(i)] || '')
  return content
}

// ---------------------------------------------------------------------------
// 题型判断 & 选择题解析
// ---------------------------------------------------------------------------
const isChoice = (item) =>
  ['single_choice', 'multiple_choice', 'choice'].includes(
    (item.question_type || '').toLowerCase()
  )

const parseChoices = (content) => {
  if (!content) return []
  const splitReg = /(?:^|\n)\s*[（(]?A[）)．.\s]/
  const splitIdx = content.search(splitReg)
  const optionStr = splitIdx >= 0 ? content.slice(splitIdx) : content

  const parts = optionStr.split(/\n?\s*[（(]?([B-D])[）)．.\s]/)
  const opts = []

  if (parts.length >= 3) {
    const firstMatch = optionStr.match(/[（(]?A[）)．.\s]\s*(.+?)(?=\s*[（(]?B[）)．.\s]|$)/s)
    if (firstMatch) opts.push({ key: 'A', text: firstMatch[1].trim() })
    for (let i = 1; i + 1 < parts.length; i += 2) {
      opts.push({ key: parts[i], text: parts[i + 1].trim() })
    }
  }

  if (opts.length < 2) {
    const lines = content.split('\n')
    for (const line of lines) {
      const m = line.trim().match(/^[（(]?([A-D])[）)．.\s]\s*(.+)/)
      if (m) opts.push({ key: m[1], text: m[2].trim() })
    }
  }
  return opts
}

// ---------------------------------------------------------------------------
// 计算属性
// ---------------------------------------------------------------------------
const allKnowledgePoints = computed(() => {
  const set = new Set()
  items.value.forEach((item) => {
    ;(item.knowledge_points || []).forEach((kp) => set.add(kp))
  })
  return [...set].sort()
})

const filteredItems = computed(() => {
  let list = items.value

  if (activeFilter.value === 'unmastered') {
    list = list.filter((i) => !i.mastered)
  } else if (activeFilter.value === 'mastered') {
    list = list.filter((i) => i.mastered)
  } else if (activeFilter.value === 'due') {
    const now = new Date()
    list = list.filter((i) => !i.mastered && i.next_review_at && new Date(i.next_review_at) <= now)
  }

  if (filterKp.value) {
    list = list.filter((i) => (i.knowledge_points || []).includes(filterKp.value))
  }

  return list
})

const emptyText = computed(() => {
  if (activeFilter.value === 'due') return '暂无到期待复习的错题'
  if (activeFilter.value === 'mastered') return '暂无已掌握的错题'
  if (activeFilter.value === 'unmastered') return '太棒了！所有错题均已掌握'
  if (filterKp.value) return `"${filterKp.value}" 知识点下暂无错题`
  return '错题本为空'
})

// ---------------------------------------------------------------------------
// 工具函数
// ---------------------------------------------------------------------------
const isDue = (item) => {
  if (!item.next_review_at || item.mastered) return false
  return new Date(item.next_review_at) <= new Date()
}

const typeLabel = (t) => {
  const map = { single_choice: '单选', multiple_choice: '多选', fill_blank: '填空', essay: '大题', choice: '选择' }
  return map[t] || (t || '未知题型')
}

const diffLabel = (d) => {
  const map = { 1: '简单', 2: '中等', 3: '困难' }
  return map[d] || (d ? `难度${d}` : '未知')
}

const diffClass = (d) => {
  if (d === 1) return 'diff-easy'
  if (d === 2) return 'diff-medium'
  if (d === 3) return 'diff-hard'
  return ''
}

const formatDate = (isoStr) => {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  const now = new Date()
  const diff = Math.floor((now - d) / 86400000)
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff}天前`
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------
const loadStats = async () => {
  try {
    const res = await learningToolsAPI.getMistakeStats()
    if (res?.success) Object.assign(stats, res.data)
  } catch {}
}

const loadDue = async () => {
  try {
    const res = await learningToolsAPI.getReviewReminders({ windowDays: 0 })
    if (res?.success) dueItems.value = res.data.due || []
  } catch {}
}

const loadMistakes = async () => {
  loading.value = true
  try {
    const res = await learningToolsAPI.getMistakes({ limit: 200 })
    if (res?.success) {
      items.value = (res.data.items || []).map((i) => ({ ...i, _expanded: false }))
    }
  } catch (e) {
    console.error('加载错题本失败', e)
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// 复习模式控制
// ---------------------------------------------------------------------------
const _startReview = (list) => {
  if (!list.length) return
  reviewList.value = list.sort(() => Math.random() - 0.5)
  reviewIndex.value = 0
  reviewDone.value = false
  reviewCorrectCount.value = 0
  reviewWrongCount.value = 0
  reviewNewMastered.value = 0
  _resetCurrentAnswer()
  reviewMode.value = true
}

const startReview = (mode) => {
  if (mode === 'due') {
    _startReview(items.value.filter((i) => !i.mastered && isDue(i)))
  } else {
    _startReview([...filteredItems.value])
  }
}

const startReviewSingle = (item) => {
  _startReview([item])
}

const _resetCurrentAnswer = () => {
  reviewResult.value = null
  reviewSelectedChoice.value = ''
  reviewEssayAnswer.value = ''
  reviewGrading.value = false
  reviewDiagnosing.value = false
}

// ---------------------------------------------------------------------------
// 选择题提交
// ---------------------------------------------------------------------------
const submitReviewChoice = async () => {
  const item = currentReviewQ.value
  if (!item || !reviewSelectedChoice.value) return

  const chosen = reviewSelectedChoice.value
  const stdRaw = (item.standard_answer || '').toUpperCase().replace(/[,，\s]/g, '')
  const isCorrect = stdRaw ? stdRaw.includes(chosen) : false

  reviewResult.value = {
    isCorrect,
    chosenKey: chosen,
    correctKey: stdRaw || null,
    feedback: isCorrect
      ? `正确答案是 ${stdRaw}，你答对了！`
      : `正确答案是 ${stdRaw || '未知'}。`,
    diagnosis: null,
  }

  if (isCorrect) {
    reviewCorrectCount.value++
    await _markMasteredIfNew(item)
  } else {
    reviewWrongCount.value++
    _requestReviewDiagnosis(item, chosen, null)
  }

  await _doFeedback(item, isCorrect)
}

// ---------------------------------------------------------------------------
// 大题 AI 批改提交
// ---------------------------------------------------------------------------
const submitReviewEssay = async () => {
  const item = currentReviewQ.value
  const userAnswer = reviewEssayAnswer.value.trim()
  if (!item || !userAnswer) return

  reviewGrading.value = true
  try {
    const res = await chatAPI.gradeAnswer({
      questionContent: item.question_content,
      standardAnswer: item.standard_answer || null,
      userAnswer,
      knowledgePoints: item.knowledge_points || [],
    })

    const isCorrect = !!res?.is_correct
    const score = res?.score ?? (isCorrect ? 100 : 0)
    const feedback = res?.feedback || (isCorrect ? '解答正确！' : '解答有误。')

    reviewResult.value = {
      isCorrect,
      chosenKey: null,
      correctKey: null,
      feedback: `${isCorrect ? '' : ''} 得分 ${score}：${feedback}`,
      diagnosis: null,
    }

    if (isCorrect) {
      reviewCorrectCount.value++
      await _markMasteredIfNew(item)
    } else {
      reviewWrongCount.value++
      _requestReviewDiagnosis(item, null, userAnswer)
    }

    await _doFeedback(item, isCorrect)
  } catch (e) {
    alert(e?.message || 'AI批改失败，请重试')
  } finally {
    reviewGrading.value = false
  }
}

// ---------------------------------------------------------------------------
// AI 诊断（答错后异步）
// ---------------------------------------------------------------------------
const _requestReviewDiagnosis = async (item, chosenKey, userAnswer) => {
  reviewDiagnosing.value = true
  try {
    const userInput = chosenKey ? `选了 ${chosenKey}` : (userAnswer || '')
    const res = await chatAPI.diagnose({
      questionContent: item.question_content,
      standardAnswer: item.standard_answer || null,
      userAnswer: userInput,
      knowledgePoints: item.knowledge_points || [],
    })
    const text = res?.diagnosis || ''
    if (reviewResult.value && text) {
      reviewResult.value = { ...reviewResult.value, diagnosis: text }
    }
  } catch { /* 诊断失败不阻塞 */ } finally {
    reviewDiagnosing.value = false
  }
}

// ---------------------------------------------------------------------------
// 答对时自动标记掌握
// ---------------------------------------------------------------------------
const _markMasteredIfNew = async (item) => {
  if (item.mastered) return
  try {
    await learningToolsAPI.markMastered(item.id)
    const orig = items.value.find((i) => i.id === item.id)
    if (orig) {
      orig.mastered = true
      orig.mastered_at = new Date().toISOString()
    }
    stats.mastered += 1
    stats.unmastered = Math.max(0, stats.unmastered - 1)
    reviewNewMastered.value++
  } catch {}
}

// ---------------------------------------------------------------------------
// 写入 advisor 画像
// ---------------------------------------------------------------------------
const _doFeedback = async (item, isCorrect) => {
  try {
    await advisorAPI.submitFeedback({
      questionId: item.question_id ?? item.id,
      isCorrect,
      hintCount: 0,
      timeSpent: null,
      algorithmVersion: 'advisor-v1',
      recommendationSessionId: `review-${Date.now()}`,
    })
  } catch {}
}

// ---------------------------------------------------------------------------
// 下一题 / 结束
// ---------------------------------------------------------------------------
const goReviewNext = () => {
  if (isReviewLast.value) {
    reviewDone.value = true
  } else {
    reviewIndex.value++
    _resetCurrentAnswer()
  }
}

const exitReview = () => {
  reviewMode.value = false
  reviewDone.value = false
  _resetCurrentAnswer()
}

// ---------------------------------------------------------------------------
// 导航
// ---------------------------------------------------------------------------
const setFilter = (val) => { activeFilter.value = val }

// ---------------------------------------------------------------------------
// 初始化
// ---------------------------------------------------------------------------
onMounted(async () => {
  await Promise.all([loadStats(), loadMistakes(), loadDue()])
})
</script>

<style scoped>
/* === Palette: #0E61AC (blue) + #FAF2E0 (cream) + #FFFFFF (white) + #1B1B1B/#86868B (text) === */

.content { padding: 32px; max-width: var(--max-content-width); margin: 0 auto; }

.header-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.header-text h1 { font-size: var(--font-xxl); font-weight: 700; color: #1B1B1B; margin-bottom: 4px; }
.sub { color: #86868B; margin-bottom: 0; font-size: var(--font-base); }
.error { color: var(--color-error); margin-bottom: 12px; }

/* === Tab row === */
.tab-row { display: flex; gap: 10px; margin-bottom: 20px; }
.tab-btn {
  padding: 10px 20px; border-radius: 20px; border: none;
  font-size: var(--font-base); font-weight: 500; font-family: var(--font-family);
  background: #0E61AC; color: #FAF2E0;
  cursor: pointer; transition: opacity 0.2s;
}
.tab-btn:hover { opacity: 0.85; }

/* === Stats === */
.stats-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.stat-card {
  background: #fff; border-radius: 12px; padding: 12px 20px; text-align: center;
  box-shadow: 0 1px 4px rgba(0,0,0,.05); min-width: 70px;
  border-top: 3px solid #0E61AC;
}
.stat-value { font-size: 24px; font-weight: 700; color: #1B1B1B; }
.stat-label { font-size: 12px; color: #86868B; margin-top: 2px; }

/* === Due banner === */
.due-banner {
  display: flex; align-items: center; gap: 10px;
  background: #fff; border: 1px solid #EEEEEE; border-radius: 12px;
  padding: 12px 16px; margin-bottom: 16px; font-size: 14px; color: #1B1B1B;
}
.btn-review-due {
  margin-left: auto; background: #0E61AC; color: #fff; border: none;
  border-radius: 20px; padding: 6px 16px; cursor: pointer; font-weight: 600; font-size: 13px;
  transition: opacity 0.2s;
}
.btn-review-due:hover { opacity: 0.85; }

/* === Toolbar === */
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.filter-group { display: flex; gap: 6px; flex-wrap: wrap; }
.filter-btn {
  background: #fff; border: 1px solid #EEEEEE; border-radius: 20px;
  padding: 6px 14px; font-size: 13px; cursor: pointer; transition: all 0.2s; color: #86868B;
}
.filter-btn.active { background: #0E61AC; color: #fff; border-color: #0E61AC; }
.filter-btn:hover:not(.active) { border-color: #0E61AC; color: #0E61AC; }
.toolbar-right { display: flex; gap: 8px; align-items: center; }
.kp-select {
  border: 1px solid #EEEEEE; border-radius: 8px; padding: 6px 10px;
  font-size: 13px; color: #1B1B1B; background: #fff; cursor: pointer; outline: none;
}
.kp-select:focus { border-color: #0E61AC; }
.btn-start-review {
  background: #0E61AC; color: #fff; border: none; border-radius: 20px;
  padding: 7px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.2s;
}
.btn-start-review:hover { opacity: 0.85; }

/* === Loading / Empty === */
.loading-state { text-align: center; padding: 60px 20px; color: #86868B; }
.spinner {
  width: 40px; height: 40px; border: 3px solid #EEEEEE;
  border-top-color: #0E61AC; border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { text-align: center; padding: 60px 20px; color: #86868B; }
.empty-state h3 { color: #1B1B1B; margin-bottom: 8px; }
.btn-go-practice {
  display: inline-block; margin-top: 12px; background: #0E61AC; color: #fff;
  text-decoration: none; border-radius: 20px; padding: 8px 20px;
  font-size: 14px; font-weight: 600; transition: opacity 0.2s;
}
.btn-go-practice:hover { opacity: 0.85; }

/* === Mistake cards === */
.mistake-list { display: flex; flex-direction: column; gap: 12px; }
.mistake-card {
  background: #fff; border-radius: 16px; padding: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05); transition: box-shadow 0.2s;
}
.mistake-card.mastered { opacity: 0.75; }
.mistake-card:hover { box-shadow: 0 2px 12px rgba(14,97,172,.1); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
.card-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge-type, .badge-diff, .badge-kp, .badge-error, .badge-mastered, .badge-due {
  font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 500;
}
.badge-type { background: rgba(14,97,172,.08); color: #0E61AC; }
.badge-kp { background: #EEEEEE; color: #86868B; }
.badge-error { background: rgba(14,97,172,.06); color: #0E61AC; }
.badge-mastered { background: rgba(14,97,172,.08); color: #0E61AC; }
.badge-due { background: #FAF2E0; color: #0E61AC; }
.diff-easy { background: rgba(14,97,172,.06); color: #0E61AC; }
.diff-medium { background: rgba(14,97,172,.10); color: #0E61AC; }
.diff-hard { background: rgba(14,97,172,.14); color: #0E61AC; }
.card-actions { display: flex; gap: 6px; }
.btn-icon {
  width: 28px; height: 28px; border-radius: 8px; border: 1px solid #EEEEEE;
  background: #fff; cursor: pointer; font-size: 13px;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.btn-expand:hover { background: rgba(14,97,172,.08); }
.card-question { font-size: 14px; line-height: 1.7; color: #1B1B1B; margin-bottom: 8px; overflow-x: auto; }
.card-answer-block {
  background: #FAF2E0; border-radius: 8px; padding: 12px; margin-bottom: 8px;
}
.answer-label { font-size: 12px; color: #0E61AC; font-weight: 600; margin-bottom: 6px; }
.answer-content { font-size: 14px; line-height: 1.7; color: #1B1B1B; overflow-x: auto; }
.card-footer { display: flex; gap: 16px; font-size: 12px; color: #86868B; flex-wrap: wrap; align-items: center; }
.btn-review-single {
  margin-left: auto; background: #0E61AC; color: #fff; border: none;
  border-radius: 20px; padding: 6px 16px; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: opacity 0.2s;
}
.btn-review-single:hover { opacity: 0.85; }

/* === Review overlay === */
.review-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center; z-index: 200; padding: 20px;
}
.review-modal {
  background: #fff; border-radius: 16px; padding: 28px;
  width: 100%; max-width: 680px; max-height: 88vh; overflow-y: auto;
}
.review-progress { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; font-size: 13px; color: #86868B; }
.btn-exit-review {
  background: none; border: 1px solid #EEEEEE; border-radius: 8px;
  padding: 4px 12px; font-size: 12px; cursor: pointer; color: #86868B; flex-shrink: 0; transition: all 0.2s;
}
.btn-exit-review:hover { border-color: #0E61AC; color: #0E61AC; }
.review-idx { flex-shrink: 0; font-weight: 600; color: #1B1B1B; }
.progress-bar { flex: 1; height: 6px; background: #EEEEEE; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: #0E61AC; border-radius: 3px; transition: width 0.4s; }
.review-score { flex-shrink: 0; font-size: 12px; color: #86868B; }
.review-question-card { display: flex; flex-direction: column; gap: 14px; }
.review-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.review-content {
  font-size: 15px; line-height: 1.8; color: #1B1B1B; padding: 16px;
  background: #FAF2E0; border-radius: 12px; overflow-x: auto;
}
/* Choice */
.choice-area { display: flex; flex-direction: column; gap: 8px; }
.choice-btn {
  display: flex; align-items: flex-start; gap: 10px; padding: 10px 14px;
  border: 1.5px solid #EEEEEE; border-radius: 12px; background: #fff;
  cursor: pointer; text-align: left; transition: all 0.18s; font-size: 14px; color: #1B1B1B;
}
.choice-btn:hover { border-color: #0E61AC; background: rgba(14,97,172,.04); }
.choice-btn.selected { border-color: #0E61AC; background: rgba(14,97,172,.08); font-weight: 600; }
.choice-key {
  flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
  background: #EEEEEE; display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #86868B;
}
.choice-btn.selected .choice-key { background: #0E61AC; color: #fff; }
.choice-text { flex: 1; line-height: 1.6; }
/* Essay */
.essay-area { display: flex; flex-direction: column; gap: 8px; }
.review-textarea {
  width: 100%; border: 1.5px solid #EEEEEE; border-radius: 12px; padding: 10px 12px;
  font-size: 14px; resize: vertical; outline: none; transition: border-color 0.2s;
  font-family: inherit; box-sizing: border-box;
}
.review-textarea:focus { border-color: #0E61AC; }
.review-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 4px; }
.btn-confirm {
  background: #0E61AC; color: #fff; border: none; border-radius: 20px;
  padding: 10px 28px; font-size: 14px; cursor: pointer; transition: opacity 0.2s;
}
.btn-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-confirm:not(:disabled):hover { opacity: 0.85; }
.btn-ai-grade {
  background: #0E61AC; color: #fff; border: none; border-radius: 20px;
  padding: 10px 24px; font-size: 14px; cursor: pointer; transition: opacity 0.2s;
}
.btn-ai-grade:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-ai-grade:not(:disabled):hover { opacity: 0.85; }
.btn-next {
  background: #0E61AC; color: #fff; border: none; border-radius: 20px;
  padding: 10px 28px; font-size: 14px; cursor: pointer; transition: opacity 0.2s;
}
.btn-next:hover { opacity: 0.85; }
/* Result area */
.result-correct, .result-wrong { display: flex; flex-direction: column; gap: 10px; }
.result-icon { font-size: 36px; text-align: center; }
.result-correct-msg { text-align: center; font-size: 16px; font-weight: 600; color: #0E61AC; }
.result-wrong-msg { text-align: center; font-size: 15px; font-weight: 600; color: #1B1B1B; }
.result-detail {
  font-size: 14px; line-height: 1.7; color: #1B1B1B;
  background: #FAF2E0; border-radius: 8px; padding: 10px 12px;
}
.analysis-card, .diagnosis-card {
  background: rgba(14,97,172,.04); border-radius: 8px; padding: 12px;
}
.analysis-title { font-size: 12px; color: #0E61AC; font-weight: 600; margin-bottom: 6px; }
.analysis-body { font-size: 14px; line-height: 1.7; color: #1B1B1B; overflow-x: auto; }
.diagnosis-loading { font-size: 13px; color: #86868B; text-align: center; padding: 8px; }
/* Review done */
.review-done { text-align: center; padding: 20px 0; }
.done-icon { font-size: 60px; margin-bottom: 12px; }
.review-done h2 { margin: 0 0 8px; color: #1B1B1B; }
.review-done p { color: #86868B; margin: 4px 0; font-size: 14px; }
.done-mastered { color: #0E61AC !important; font-weight: 600; }
.btn-primary {
  margin-top: 20px; background: #0E61AC; color: #fff; border: none;
  border-radius: 20px; padding: 10px 28px; font-size: 14px; font-weight: 600;
  cursor: pointer; transition: opacity 0.2s;
}
.btn-primary:hover { opacity: 0.85; }

/* === Induction view === */
.induction-view { padding: 12px 0; }
.induction-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.induction-card {
  background: #fff; border-radius: 16px; padding: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05); display: flex; flex-direction: column; gap: 6px;
}
.induction-kp-name { font-size: var(--font-base); font-weight: 600; color: #1B1B1B; }
.induction-count { font-size: var(--font-sm); color: #86868B; }
.induction-mini-bar { height: 6px; background: #EEEEEE; border-radius: 3px; overflow: hidden; }
.mini-bar-fill { height: 100%; background: #0E61AC; border-radius: 3px; transition: width var(--transition-slow); }
.induction-mastery { font-size: var(--font-xs); color: #0E61AC; font-weight: 600; }

/* === Transitions === */
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s, transform 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(-6px); }
.list-enter-active { transition: all 0.3s; }
.list-leave-active { transition: all 0.2s; }
.list-enter-from { opacity: 0; transform: translateY(10px); }
.list-leave-to { opacity: 0; transform: translateX(-10px); }

/* === Responsive === */
@media (max-width: 768px) {
  .content { padding: 16px; }
  .stats-row { justify-content: space-between; }
  .toolbar { flex-direction: column; align-items: flex-start; }
  .toolbar-right { width: 100%; }
  .kp-select { flex: 1; }
  .review-modal { padding: 20px 16px; }
}
</style>
