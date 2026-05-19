// API 服务层，用于与后端通信

const API_PREFIX = '/api'

const getAuthToken = () => localStorage.getItem('access_token')


const getStoredUserInfo = () => {
  try {
    const raw = localStorage.getItem('user_info')
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const persistUserInfo = (patch = {}) => {
  const current = getStoredUserInfo()
  const next = { ...current, ...patch }
  localStorage.setItem('user_info', JSON.stringify(next))
  return next
}

const buildQuery = (params = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.forEach((v) => query.append(key, String(v)))
    } else {
      query.append(key, String(value))
    }
  })
  const str = query.toString()
  return str ? `?${str}` : ''
}

export async function request(endpoint, options = {}) {
  const token = getAuthToken()
  const headers = { ...(options.headers || {}) }
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData

  if (!isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_PREFIX}${endpoint}`, {
    ...options,
    headers,
  })

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { message: text }
    }
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || `请求失败(${response.status})`)
  }

  return data
}

export const ensureCurrentUserId = async () => {
  const userInfo = getStoredUserInfo()
  if (userInfo?.id) return Number(userInfo.id)

  const me = await request('/auth/me')
  if (!me?.id) {
    throw new Error('无法从登录态获取用户ID，请重新登录')
  }
  persistUserInfo({
    id: me.id,
    username: me.username,
    name: userInfo.name || me.username,
    avatar: userInfo.avatar || '👤',
  })
  return Number(me.id)
}

export const authAPI = {
  register: (userData) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),

  login: (credentials) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),

  getCurrentUser: () => request('/auth/me'),
}

export const profileAPI = {
  getProfile: async (userId) => {
    const id = userId || (await ensureCurrentUserId())
    return request(`/profile/${buildQuery({ user_id: id })}`)
  },
}

export const exercisesAPI = {
  getRecommendations: async ({ userId, limit = 5, algorithmVersion } = {}) => {
    const id = userId || (await ensureCurrentUserId())
    return request(`/exercises/recommend${buildQuery({ user_id: id, limit, algorithm_version: algorithmVersion })}`)
  },

  submitRecommendedAnswer: async ({
    userId,
    questionId,
    answer,
    isCorrect,
    algorithmVersion,
    recommendationSessionId,
  }) => {
    const id = userId || (await ensureCurrentUserId())
    return request(
      `/records/recommended/${questionId}/submit${buildQuery({
        user_id: id,
        answer,
        is_correct: isCorrect,
        algorithm_version: algorithmVersion,
        recommendation_session_id: recommendationSessionId,
      })}`,
      { method: 'POST' }
    )
  },

  getMasteryDashboard: async ({ userId, trendLimit = 30 } = {}) => {
    const id = userId || (await ensureCurrentUserId())
    return request(`/exercises/mastery/dashboard${buildQuery({ user_id: id, trend_limit: trendLimit })}`)
  },

  getAbTestStats: ({ algorithmVersion, limit = 1000 }) =>
    request(`/exercises/ab-test/stats${buildQuery({ algorithm_version: algorithmVersion, limit })}`),
}

export const learningToolsAPI = {
  /** 获取错题本列表 */
  getMistakes: ({ mastered, onlyDue, knowledgePoint, days, limit = 100 } = {}) =>
    request(
      `/learning-tools/mistakes${buildQuery({
        mastered,
        only_due: onlyDue,
        knowledge_point: knowledgePoint,
        days,
        limit,
      })}`
    ),

  /** 获取错题本统计摘要（总数/未掌握/到期复习） */
  getMistakeStats: () => request('/learning-tools/mistakes/stats'),

  /** 标记错题为已掌握 */
  markMastered: (mistakeId) =>
    request(`/learning-tools/mistakes/${mistakeId}/master`, { method: 'PATCH' }),

  /** 取消已掌握标记，重新加入待复习 */
  unmarkMastered: (mistakeId) =>
    request(`/learning-tools/mistakes/${mistakeId}/unmaster`, { method: 'PATCH' }),

  /** 获取复习提醒（到期+即将到期） */
  getReviewReminders: ({ windowDays = 3 } = {}) =>
    request(`/learning-tools/mistakes/review-reminders${buildQuery({ window_days: windowDays })}`),

  /** 获取收藏夹列表 */
  getFavorites: ({ folderName, limit = 50 } = {}) =>
    request(`/learning-tools/favorites${buildQuery({ folder_name: folderName, limit })}`),

  /** 新增/更新收藏 */
  addFavorite: ({ questionId, folderName = '默认收藏夹', note, tags = [] } = {}) =>
    request(
      `/learning-tools/favorites${buildQuery({
        question_id: questionId,
        folder_name: folderName,
        note,
        tags,
      })}`,
      { method: 'POST' }
    ),

  /** 删除收藏 */
  removeFavorite: (favoriteId) =>
    request(`/learning-tools/favorites/${favoriteId}`, { method: 'DELETE' }),
}

export const advisorAPI = {
  /** 初始化/重建画像（首次使用或强制重建 Redis 缓存） */
  initProfile: () => request('/advisor/init'),

  /** 获取 Advisor 推荐题目 */
  getRecommendations: ({ limit = 5 } = {}) =>
    request(`/advisor/recommend${buildQuery({ limit })}`),

  /** 提交答题反馈（更新画像 + Redis） */
  submitFeedback: ({ questionId, isCorrect, hintCount = 0, timeSpent, skipReason, algorithmVersion = 'advisor-v1', recommendationSessionId } = {}) =>
    request('/advisor/feedback', {
      method: 'POST',
      body: JSON.stringify({
        question_id: questionId,
        is_correct: isCorrect,
        hint_count: hintCount,
        time_spent: timeSpent ?? null,
        skip_reason: skipReason ?? null,
        algorithm_version: algorithmVersion,
        recommendation_session_id: recommendationSessionId ?? null,
      }),
    }),

  /** 获取带缓存的快速画像 */
  getProfile: () => request('/advisor/profile'),

  /** Redis 健康检查 */
  redisHealth: () => request('/advisor/redis/health'),
}

export const chatAPI = {
  /** 大模型批改大题（非流式） */
  gradeAnswer: ({ questionContent, standardAnswer, userAnswer, knowledgePoints } = {}) =>
    request('/chat/grade-answer', {
      method: 'POST',
      body: JSON.stringify({
        question_content: questionContent,
        standard_answer: standardAnswer ?? null,
        user_answer: userAnswer,
        knowledge_points: knowledgePoints ?? [],
      }),
    }),

  /** 答错后诊断：AI 指出问题所在和正确思路 */
  diagnose: ({ questionContent, standardAnswer, userAnswer, knowledgePoints } = {}) =>
    request('/chat/diagnose', {
      method: 'POST',
      body: JSON.stringify({
        question_content: questionContent,
        standard_answer: standardAnswer ?? null,
        user_answer: userAnswer,
        knowledge_points: knowledgePoints ?? [],
      }),
    }),

  /** 生成分级提示 (L1-L4)，调用 Instructor 引擎 */
  generateHint: ({ hintLevel, questionContent, knowledgePoints = [], studentMessage = '' } = {}) =>
    request('/llm/generate-hint', {
      method: 'POST',
      body: JSON.stringify({
        hint_level: hintLevel,
        question_content: questionContent,
        knowledge_points: knowledgePoints,
        student_message: studentMessage || undefined,
      }),
    }),
}

export const errorDiagnosisAPI = {
  /** 结构化错因诊断（五维分析） */
  diagnose: ({ questionId, userAnswerSteps, finalAnswer, timeSpent } = {}) =>
    request('/error-classification/diagnose', {
      method: 'POST',
      body: JSON.stringify({
        question_id: questionId,
        user_answer_steps: userAnswerSteps ?? [],
        final_answer: finalAnswer ?? '',
        time_spent: timeSpent ?? null,
      }),
    }),
}

export const ocrAPI = {
  /** OCR 手写答案识别，上传图片返回识别文本 */
  parse: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/ocr/parse', {
      method: 'POST',
      body: formData,
    })
  },
}

export const knowledgeTreeAPI = {
  /** 获取指定专题的知识树（含用户掌握度状态） */
  getTopic: (topicName) =>
    request(`/knowledge-tree/topic/${encodeURIComponent(topicName)}`),

  /** 获取单个知识节点详情（跨专题） */
  getNode: (nodeId) =>
    request(`/knowledge-tree/node/${encodeURIComponent(nodeId)}`),

  /** 获取所有专题列表 */
  getTopics: () => request('/knowledge-tree/topics'),
}

export default {
  auth: authAPI,
  profile: profileAPI,
  exercises: exercisesAPI,
  learningTools: learningToolsAPI,
  advisor: advisorAPI,
  chat: chatAPI,
  errorDiagnosis: errorDiagnosisAPI,
  ocr: ocrAPI,
  knowledgeTree: knowledgeTreeAPI,
  ensureCurrentUserId,
}
