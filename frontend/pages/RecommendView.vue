<!-- src/pages/RecommendView.vue -->
<template>
  <div class="recommend-page" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="user-section" @click="showEditProfile = true">
        <div class="user-avatar-large">
          <img v-if="isImageAvatar(userInfo.avatar)" :src="userInfo.avatar" class="avatar-img" />
          <span v-else>{{ userInfo.avatar }}</span>
        </div>
        <div class="user-info" v-show="!isSidebarCollapsed">
          <span class="user-name">{{ userInfo.name }}</span>
          <span class="user-level">θ={{ profileSnap.theta ?? '-' }} · 掌握度{{ pct(profileSnap.avg_mastery) }}</span>
        </div>
      </div>

      <button class="toggle-btn" @click.stop="toggleSidebar">
        {{ isSidebarCollapsed ? '→' : '←' }}
      </button>

      <div class="quick-nav" v-show="!isSidebarCollapsed">
        <router-link to="/ai-tutor" class="nav-item">
          <span class="nav-icon">💬</span><span>AI 提问</span>
        </router-link>
        <router-link to="/recommend" class="nav-item active">
          <span class="nav-icon">✨</span><span>智能推荐</span>
        </router-link>
        <router-link to="/mistake-book" class="nav-item">
          <span class="nav-icon">📝</span><span>练习中心</span>
        </router-link>
        <router-link to="/profile" class="nav-item">
          <span class="nav-icon">📊</span><span>学习画像</span>
        </router-link>
      </div>

      <div class="sidebar-footer" v-show="!isSidebarCollapsed">
        <button class="logout-btn" @click="logout">
          <span>🚪</span><span>退出登录</span>
        </button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main-content">
      <div class="mobile-header">
        <button class="mobile-menu-btn" @click="toggleSidebar">☰</button>
        <span class="mobile-title">智能推荐</span>
      </div>

      <div class="recommend-container">
        <!-- 页头 -->
        <div class="page-header">
          <div class="header-left">
            <h1>✨ 个性化推荐</h1>
            <p>基于你的学习画像，AI 为你精心挑选最合适的题目</p>
          </div>
          <div class="header-right">
            <div v-if="redisOk !== null" class="redis-badge" :class="redisOk ? 'online' : 'offline'">
              {{ redisOk ? '⚡ 实时推荐' : '📦 离线模式' }}
            </div>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="error" class="error-banner">{{ error }}</div>

        <!-- 继续上次练习横幅 -->
        <div v-if="hasSavedSession" class="continue-banner">
          <span class="continue-icon">📝</span>
          <span>你还有未完成的练习（已做 <strong>{{ savedProgress }}</strong> 题）</span>
          <div class="continue-actions">
            <button class="btn-continue" @click="_initWithSavedSession()">继续上次</button>
            <button class="btn-fresh" @click="_startFresh">重新开始</button>
          </div>
        </div>

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

        <!-- 操作栏 -->
        <div class="action-bar">
          <select v-model="limit" class="limit-select">
            <option :value="3">3 题</option>
            <option :value="5">5 题</option>
            <option :value="8">8 题</option>
          </select>
          <button class="refresh-btn" :disabled="loading" @click="loadRecommendations">
            <span v-if="loading">推荐中…</span>
            <span v-else>🔄 换一批</span>
          </button>
        </div>

        <!-- 加载骨架屏 -->
        <div v-if="loading" class="skeleton-list">
          <div v-for="i in limit" :key="i" class="skeleton-card"></div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="recommendations.length === 0" class="empty-state">
          <div class="empty-icon">📭</div>
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
              ✅ {{ correctCount }} &nbsp; ❌ {{ wrongCount }}
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
                <button class="act-btn skip-easy" @click="skipQuestion(currentQ, 'too_easy')">⏩ 太简单，跳过</button>
                <button class="act-btn skip-hard" @click="skipQuestion(currentQ, 'too_hard')">⏭ 太难了，跳过</button>
              </div>
            </div>

            <!-- 大题 -->
            <div v-else class="card-actions">
              <textarea
                v-model="answerMap[currentQ.id]"
                class="answer-textarea"
                placeholder="请写出你的解题过程和答案…（提交后将由AI批改）"
                rows="5"
              ></textarea>
              <div class="btn-group">
                <button
                  class="act-btn ai-grade"
                  :disabled="gradingSet.has(currentQ.id) || !answerMap[currentQ.id]"
                  @click="submitEssayAnswer(currentQ)"
                >
                  <span v-if="gradingSet.has(currentQ.id)">⏳ AI批改中…</span>
                  <span v-else>🤖 提交AI批改</span>
                </button>
                <button class="act-btn skip-easy" @click="skipQuestion(currentQ, 'too_easy')">⏩ 太简单，跳过</button>
                <button class="act-btn skip-hard" @click="skipQuestion(currentQ, 'too_hard')">⏭ 太难了，跳过</button>
              </div>
            </div>
          </template>

          <!-- ===== 结果区：已提交 ===== -->
          <template v-else>
            <!-- 答对 -->
            <div v-if="currentResult.isCorrect" class="result-correct">
              <div class="result-icon">🎉</div>
              <div class="result-correct-msg">答对了！</div>
              <div v-if="currentResult.feedback" class="result-detail"
                   v-html="renderMath(currentResult.feedback)"></div>
              <button class="act-btn next-btn" @click="goNext">
                {{ isLast ? '查看本轮总结' : '下一题 →' }}
              </button>
            </div>

            <!-- 答错 -->
            <div v-else class="result-wrong">
              <div class="result-icon">😕</div>
              <div class="result-wrong-msg">
                <span v-if="currentResult.chosenKey">你选了 {{ currentResult.chosenKey }}，</span>答错了
                <span v-if="currentResult.correctKey">（正确答案：{{ currentResult.correctKey }}）</span>
              </div>

              <!-- 解析 -->
              <div v-if="currentResult.feedback" class="analysis-card">
                <div class="analysis-title">📖 AI 解析</div>
                <div class="analysis-body" v-html="renderMath(currentResult.feedback)"></div>
              </div>

              <!-- AI 指出问题 -->
              <div v-if="currentResult.diagnosis" class="diagnosis-card">
                <div class="analysis-title">🔍 问题所在</div>
                <div class="analysis-body" v-html="renderMath(currentResult.diagnosis)"></div>
              </div>
              <div v-else-if="diagnosing" class="diagnosis-loading">⏳ AI 正在分析你的问题…</div>

              <button class="act-btn next-btn wrong-next" @click="goNext">
                {{ isLast ? '查看本轮总结' : '下一题 →' }}
              </button>
            </div>
          </template>
        </div>

        <!-- ===== 全部完成总结 ===== -->
        <div v-if="!loading && recommendations.length > 0 && allDone" class="all-done">
          <div class="done-emoji">🏆</div>
          <p class="done-title">本轮完成！</p>
          <div class="done-stats">
            <span class="done-stat correct">✅ 答对 {{ correctCount }} 题</span>
            <span class="done-stat wrong">❌ 答错 {{ wrongCount }} 题</span>
            <span class="done-stat skip">⏭ 跳过 {{ skipCount }} 题</span>
          </div>
          <div class="done-accuracy">正确率 {{ doneAccuracy }}%</div>
          <button class="primary-btn mt-16" @click="loadRecommendations">继续下一批</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { advisorAPI, chatAPI } from '../services/apiService'
import { renderMath, isChoice, parseChoices, diffClass, isImageAvatar } from '../composables/useQuestionUtils.js'
import { useRecommendSession } from '../composables/useRecommendSession.js'

const router = useRouter()
const { saveSession, loadSession, clearSession } = useRecommendSession()

// 侧边栏
const isSidebarCollapsed = ref(false)
const toggleSidebar = () => { isSidebarCollapsed.value = !isSidebarCollapsed.value }

// 用户信息
const userInfo = reactive({ name: '学习者', avatar: '👤' })
const loadUserInfo = () => {
  try {
    const saved = localStorage.getItem('user_info')
    if (saved) {
      const d = JSON.parse(saved)
      userInfo.name = d.username || d.name || '学习者'
      if (d.avatar) userInfo.avatar = d.avatar
    }
  } catch {}
}
const logout = () => { if (confirm('确定要退出登录吗？')) router.push('/') }

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

// 计算属性
const advisorModeClass = computed(() => ({
  'mode-scaffold': advisorMode.value === 'MODE_SCAFFOLD',
  'mode-challenge': advisorMode.value === 'MODE_CHALLENGE',
  'mode-encourage': advisorMode.value === 'MODE_ENCOURAGE',
}))
const modeIcon = computed(() => ({
  MODE_SCAFFOLD: '🔧',
  MODE_CHALLENGE: '🚀',
  MODE_ENCOURAGE: '💪',
}[advisorMode.value] || '🤖'))
const modeName = computed(() => ({
  MODE_SCAFFOLD: '脚手架模式 — 分步引导',
  MODE_CHALLENGE: '挑战模式 — 自主探索',
  MODE_ENCOURAGE: '鼓励模式 — 适度引导',
}[advisorMode.value] || '智能模式'))

const pct = (v) => v != null ? (v * 100).toFixed(0) + '%' : '-'
const toneClass = (t) => ({ '鼓励型': 'encourage', '激励型': 'motivate', '中性': 'neutral' }[t] || 'neutral')

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
  saveSessionFromCurrentState()
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
      feedback: `${isCorrect ? '✅' : '❌'} 得分 ${score}：${feedback}`,
      diagnosis: null,
    }

    if (isCorrect) {
      correctCount.value++
    } else {
      wrongCount.value++
      _requestDiagnosis(item, null, userAnswer)
    }

    await _doFeedback(item, isCorrect)
    saveSessionFromCurrentState()
  } catch (e) {
    alert(e?.message || 'AI批改失败，请重试')
  } finally {
    const s = new Set(gradingSet.value)
    s.delete(item.id)
    gradingSet.value = s
  }
}

// -------- 答错时向 AI 请求诊断 --------
const _requestDiagnosis = async (item, chosenKey, userAnswer) => {
  diagnosing.value = true
  try {
    const userInput = chosenKey ? `选了 ${chosenKey}` : (userAnswer || '')
    const res = await chatAPI.diagnose({
      questionContent: item.content,
      standardAnswer: item.standard_answer || null,
      userAnswer: userInput,
      knowledgePoints: item.knowledge_points || [],
    })
    const text = res?.diagnosis || ''
    if (currentResult.value && text) {
      currentResult.value = { ...currentResult.value, diagnosis: text }
    }
  } catch { /* 诊断失败不阻塞 */ } finally {
    diagnosing.value = false
  }
}

// -------- 下一题 --------
const goNext = () => {
  currentResult.value = null
  currentIndex.value++
  saveSessionFromCurrentState()
}

// -------- 公共：异步反馈（非阻塞）--------
const pendingFeedbacks = new Set()

const _submitFeedback = (item, payload) => {
  const key = `${item.id}_${Date.now()}`
  pendingFeedbacks.add(key)
  advisorAPI.submitFeedback(payload)
    .then(() => {
      submittedSet.value = new Set([...submittedSet.value, item.id])
      if (submittedSet.value.size === recommendations.value.length) {
        advisorAPI.getProfile().then(prof => {
          const snap = prof?.data || {}
          Object.assign(profileSnap, {
            theta: snap.theta,
            avg_mastery: snap.avg_mastery,
            weak_kps: Object.entries(snap.knowledge_mastery || {})
              .sort((a, b) => a[1] - b[1]).slice(0, 3).map(e => e[0]),
            total_questions: snap.total_questions,
          })
        }).catch(() => {})
      }
    })
    .catch(() => {
      // 静默失败，下次加载时重试
    })
    .finally(() => {
      pendingFeedbacks.delete(key)
    })
}

const _doFeedback = (item, isCorrect) => {
  _submitFeedback(item, {
    questionId: item.id,
    isCorrect,
    hintCount: 0,
    timeSpent: null,
    algorithmVersion: 'advisor-v1',
    recommendationSessionId: `web-${Date.now()}`,
  })
}

// -------- 跳过（即时切换 + 后台提交）--------
const skipQuestion = (item, skipReason) => {
  _submitFeedback(item, {
    questionId: item.id,
    isCorrect: skipReason === 'too_easy',
    skipReason,
    algorithmVersion: 'advisor-v1',
  })
  submittedSet.value = new Set([...submittedSet.value, item.id])
  skipCount.value++
  currentResult.value = null
  currentIndex.value++
  saveSessionFromCurrentState()
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
    const snap = data.profile_snapshot || {}
    Object.assign(profileSnap, snap)
  } catch (e) {
    error.value = e?.message || '获取推荐失败，请重试'
    recommendations.value = []
  } finally {
    loading.value = false
    if (recommendations.value.length > 0) {
      clearSession()
      saveSessionFromCurrentState()
    }
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

// ---------------------------------------------------------------------------
// 会话持久化
// ---------------------------------------------------------------------------
const saveSessionFromCurrentState = () => {
  saveSession({
    recommendations: recommendations.value,
    currentIndex: currentIndex.value,
    correctCount: correctCount.value,
    wrongCount: wrongCount.value,
    skipCount: skipCount.value,
    answerMap: answerMap,
    selectedChoice: selectedChoice,
    submittedSet: submittedSet.value,
    isCompleted: allDone.value,
    advisorMode: advisorMode.value,
    advisorInstruction: advisorInstruction.value,
    profileSnap: profileSnap,
    limit: limit.value,
  })
}

const _applySavedState = (s) => {
  recommendations.value = s.recommendations || []
  currentIndex.value = s.currentIndex ?? 0
  correctCount.value = s.correctCount ?? 0
  wrongCount.value = s.wrongCount ?? 0
  skipCount.value = s.skipCount ?? 0
  Object.assign(answerMap, s.answerMap || {})
  Object.assign(selectedChoice, s.selectedChoice || {})
  submittedSet.value = new Set(s.submittedSet || [])
  advisorMode.value = s.advisorMode || ''
  advisorInstruction.value = s.advisorInstruction || null
  Object.assign(profileSnap, s.profileSnap || {})
  limit.value = s.limit || 5
  loading.value = false
}

// 是否有未完成的上次练习
const hasSavedSession = ref(false)
const savedProgress = computed(() => {
  const s = loadSession()
  return s ? s.correctCount + s.wrongCount + s.skipCount : 0
})

// 用户编辑画像弹窗
const showEditProfile = ref(false)

const _initWithSavedSession = () => {
  const saved = loadSession()
  if (saved) {
    _applySavedState(saved)
  }
  hasSavedSession.value = false
}

const _startFresh = () => {
  clearSession()
  hasSavedSession.value = false
  loadRecommendations()
}

onMounted(async () => {
  loadUserInfo()
  await checkRedis()

  const saved = loadSession()
  if (saved && !saved.isCompleted && saved.recommendations.length > 0) {
    hasSavedSession.value = true
    // pre-load the snapshot so sidebar shows proper data
    Object.assign(profileSnap, saved.profileSnap || {})
    advisorMode.value = saved.advisorMode || ''
    advisorInstruction.value = saved.advisorInstruction || null
    loading.value = false
  } else {
    await loadRecommendations()
  }
})

onUnmounted(() => {
  if (!allDone.value && recommendations.value.length > 0) {
    saveSessionFromCurrentState()
  }
})
</script>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.recommend-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: #f5f5f7;
  position: fixed;
  top: 0; left: 0;
}

/* ====== 侧边栏 ====== */
.sidebar {
  width: 260px;
  min-width: 260px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e5e5e5;
  display: flex;
  flex-direction: column;
  padding: 20px 12px;
  position: relative;
  transition: all 0.3s ease;
  overflow: hidden;
}
.recommend-page.sidebar-collapsed .sidebar { width: 60px; min-width: 60px; padding: 20px 8px; }
.user-section { display: flex; align-items: center; gap: 12px; padding: 12px; margin-bottom: 16px; border-radius: 12px; cursor: pointer; transition: 0.2s; }
.user-section:hover { background: #f0f0f0; }
.user-avatar-large { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg,#667eea,#764ba2); display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; overflow: hidden; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.user-info { display: flex; flex-direction: column; overflow: hidden; flex: 1; }
.user-name { font-size: 14px; font-weight: 600; color: #1d1d1f; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-level { font-size: 11px; color: #007aff; margin-top: 2px; }
.toggle-btn { position: absolute; right: -12px; top: 80px; width: 24px; height: 24px; border-radius: 50%; background: white; border: 1px solid #e0e0e0; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #666; box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 10; }
.quick-nav { margin-bottom: 16px; border-bottom: 1px solid #e5e5e5; padding-bottom: 16px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: 8px; text-decoration: none; color: #666; font-size: 14px; transition: 0.2s; margin-bottom: 4px; }
.nav-item:hover { background: #f0f0f0; color: #1d1d1f; }
.nav-item.active { background: #e8e8e8; color: #1d1d1f; font-weight: 600; }
.nav-icon { font-size: 18px; }
.sidebar-footer { margin-top: auto; padding-top: 16px; border-top: 1px solid #e5e5e5; }
.logout-btn { width: 100%; display: flex; align-items: center; gap: 8px; padding: 10px; border: none; background: transparent; color: #666; font-size: 14px; cursor: pointer; border-radius: 8px; transition: 0.2s; }
.logout-btn:hover { background: #ffebee; color: #c62828; }

/* ====== 主内容 ====== */
.main-content { flex: 1; height: 100%; overflow-y: auto; background: #f5f5f7; }
.mobile-header { display: none; padding: 12px 16px; border-bottom: 1px solid #e5e5e5; background: white; align-items: center; gap: 12px; }
.mobile-menu-btn { background: none; border: none; font-size: 20px; cursor: pointer; padding: 4px; }
.mobile-title { font-size: 16px; font-weight: 600; flex: 1; text-align: center; }

.recommend-container { max-width: 860px; margin: 0 auto; padding: 32px 20px 60px; }

/* ====== 页头 ====== */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h1 { font-size: 26px; font-weight: 700; color: #1d1d1f; margin-bottom: 6px; }
.page-header p { font-size: 14px; color: #86868b; }
.redis-badge { padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.redis-badge.online { background: #e6f4ea; color: #137333; }
.redis-badge.offline { background: #fce8e6; color: #c5221f; }

/* ====== 错误 ====== */
.error-banner { background: #fff0f0; border: 1px solid #ffcdd2; color: #b71c1c; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; font-size: 14px; }

/* ====== 继续练习横幅 ====== */
.continue-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(135deg, #e3f2fd, #f3e5f5);
  border: 1.5px solid #90caf9;
  border-radius: 12px;
  padding: 14px 18px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #1a237e;
  flex-wrap: wrap;
}
.continue-icon { font-size: 24px; }
.continue-actions { display: flex; gap: 8px; margin-left: auto; }
.btn-continue {
  background: linear-gradient(135deg, #0071e3, #005bb5);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-continue:hover { opacity: 0.88; }
.btn-fresh {
  background: #fff;
  color: #555;
  border: 1px solid #d0d7e2;
  border-radius: 8px;
  padding: 8px 18px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-fresh:hover { background: #f5f5f7; }

/* ====== Advisor 模式 ====== */
.advisor-mode-card { display: flex; align-items: center; gap: 16px; padding: 16px 20px; border-radius: 14px; margin-bottom: 20px; border: 1.5px solid transparent; }
.advisor-mode-card.mode-scaffold { background: #fff8e1; border-color: #ffc107; }
.advisor-mode-card.mode-challenge { background: #e8f5e9; border-color: #4caf50; }
.advisor-mode-card.mode-encourage { background: #e3f2fd; border-color: #2196f3; }
.mode-icon { font-size: 28px; flex-shrink: 0; }
.mode-body { flex: 1; }
.mode-label { font-size: 15px; font-weight: 700; color: #1d1d1f; margin-bottom: 4px; }
.mode-reason { font-size: 13px; color: #555; line-height: 1.5; }
.mode-stats { display: flex; flex-direction: column; gap: 4px; text-align: right; font-size: 12px; color: #666; flex-shrink: 0; }

/* ====== 操作栏 ====== */
.action-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
.limit-select { border: 1px solid #d0d7e2; border-radius: 8px; padding: 8px 12px; font-size: 13px; cursor: pointer; background: white; }
.refresh-btn { padding: 8px 20px; border: none; border-radius: 10px; background: #0071e3; color: white; font-size: 14px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.refresh-btn:disabled { background: #aac7f0; cursor: not-allowed; }
.refresh-btn:hover:not(:disabled) { background: #005bb5; }

/* ====== 骨架屏 ====== */
.skeleton-list { display: flex; flex-direction: column; gap: 16px; }
.skeleton-card { height: 180px; background: linear-gradient(90deg,#f0f0f0 25%,#e8e8e8 50%,#f0f0f0 75%); background-size: 200% 100%; border-radius: 16px; animation: shimmer 1.4s infinite; }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* ====== 空状态 ====== */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-state p { font-size: 16px; color: #555; margin-bottom: 8px; }
.empty-sub { font-size: 14px; color: #999; margin-bottom: 24px; }
.primary-btn { padding: 12px 28px; background: #0071e3; color: white; border: none; border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.primary-btn:hover { background: #005bb5; }

/* ====== 答题进度条 ====== */
.quiz-progress { margin-bottom: 18px; }
.qp-info { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.qp-cur { font-size: 18px; font-weight: 700; color: #1d1d1f; }
.qp-total { font-size: 14px; color: #86868b; }
.qp-stats { margin-left: auto; font-size: 13px; color: #555; }
.qp-bar-bg { width: 100%; height: 8px; background: #e0e0e0; border-radius: 999px; overflow: hidden; }
.qp-bar-fill { height: 100%; background: linear-gradient(90deg, #0071e3, #34c759); border-radius: 999px; transition: width 0.4s ease; }

/* ====== 题目卡片 ====== */
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

/* ====== 答题区 ====== */
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

/* 选择题 */
.choice-options { display: flex; flex-direction: column; gap: 10px; }
.choice-btn { display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; border: 1.5px solid #e0e0e0; border-radius: 12px; background: #fafafa; cursor: pointer; font-size: 15px; text-align: left; transition: 0.2s; width: 100%; }
.choice-btn:hover { border-color: #0071e3; background: #f0f7ff; }
.choice-btn.selected { border-color: #0071e3; background: #e3f2fd; }
.choice-key { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #e0e0e0; color: #333; font-weight: 700; font-size: 14px; flex-shrink: 0; }
.choice-btn.selected .choice-key { background: #0071e3; color: white; }
.choice-text { flex: 1; line-height: 1.6; }

/* 大题文本框 */
.answer-textarea { width: 100%; padding: 12px 14px; border: 1.5px solid #d0d7e2; border-radius: 12px; font-size: 15px; line-height: 1.8; resize: vertical; outline: none; transition: 0.2s; font-family: inherit; box-sizing: border-box; }
.answer-textarea:focus { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.12); }
.act-btn.ai-grade { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
.act-btn.ai-grade:hover:not(:disabled) { opacity: 0.9; }
.act-btn.ai-grade:disabled { background: #c5b8e8; cursor: not-allowed; }

/* ====== 结果区 ====== */
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

/* ====== 总结 ====== */
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

/* ====== 响应式 ====== */
@media (max-width: 1024px) {
  .sidebar { position: fixed; left: 0; top: 0; bottom: 0; z-index: 100; box-shadow: 2px 0 8px rgba(0,0,0,.1); }
  .recommend-page.sidebar-collapsed .sidebar { transform: translateX(-100%); }
  .mobile-header { display: flex; }
}
@media (max-width: 640px) {
  .btn-group { flex-direction: column; }
  .act-btn { text-align: center; }
  .advisor-mode-card { flex-direction: column; align-items: flex-start; }
  .mode-stats { text-align: left; }
  .done-stats { flex-direction: column; align-items: center; gap: 8px; }
}
</style>
