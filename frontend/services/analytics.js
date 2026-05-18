/**
 * 数据埋点 SDK — 统一事件追踪
 *
 * 设计原则：
 * - 全量采集，按需聚合：前端无感埋点全量上报
 * - 批量发送：60s 或 20 条触发 flush，减少请求频率
 * - 自动上下文：session_id / user_id / timestamp / device_type 自动注入
 */

const API_PREFIX = '/api'
const FLUSH_INTERVAL_MS = 60000
const FLUSH_BATCH_SIZE = 20
const HEARTBEAT_INTERVAL_MS = 60000

// ── 会话管理 ────────────────────────────────────────────
let sessionId = generateId()
let sessionStartTs = Date.now()
let questionsDoneThisSession = 0
let flushTimer = null
let heartbeatTimer = null
let eventBuffer = []

function generateId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function resetSession() {
  sessionId = generateId()
  sessionStartTs = Date.now()
  questionsDoneThisSession = 0
}

// ── 设备检测 ────────────────────────────────────────────
function detectDevice() {
  const ua = navigator.userAgent
  if (/Mobi|Android|iPhone/i.test(ua)) return 'mobile'
  if (/iPad|Tablet/i.test(ua)) return 'tablet'
  return 'desktop'
}

const deviceType = detectDevice()

// ── 上下文注入 ──────────────────────────────────────────
function enrichPayload(name, data) {
  const token = localStorage.getItem('access_token')
  return {
    event_name: name,
    session_id: sessionId,
    timestamp: new Date().toISOString(),
    session_elapsed_ms: Date.now() - sessionStartTs,
    device_type: deviceType,
    user_agent: navigator.userAgent.slice(0, 200),
    page_url: window.location.href,
    data,
    _token: token,
  }
}

// ── 批量发送 ────────────────────────────────────────────
async function flush() {
  if (eventBuffer.length === 0) return
  const batch = eventBuffer.splice(0)
  try {
    const token = localStorage.getItem('access_token')
    await fetch(`${API_PREFIX}/analytics/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ events: batch }),
      // 不阻塞页面卸载
      keepalive: true,
    })
  } catch {
    // 静默失败，避免影响主流程；失败事件放回缓冲区
    eventBuffer.unshift(...batch)
  }
}

function scheduleFlush() {
  if (flushTimer) return
  flushTimer = setInterval(flush, FLUSH_INTERVAL_MS)
}

// ── 公开 API ────────────────────────────────────────────

/**
 * 统一埋点入口
 * @param {string} name - 事件名（见设计文档 17 类事件）
 * @param {object} data - 事件载荷
 */
export function trackEvent(name, data = {}) {
  const payload = enrichPayload(name, data)
  eventBuffer.push(payload)

  if (eventBuffer.length >= FLUSH_BATCH_SIZE) {
    flush()
  }
}

/**
 * 更新会话内答题计数（由 RecommendView 等页面调用）
 */
export function incrementQuestionsDone() {
  questionsDoneThisSession++
}

// ── 自动采集：页面可见性变化 ─────────────────────────────
function setupVisibilityTracking() {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      trackEvent('session_heartbeat', {
        current_page: window.location.pathname,
        questions_done_this_session: questionsDoneThisSession,
        active_duration_ms: Date.now() - sessionStartTs,
        visibility: 'hidden',
      })
    } else {
      // 页面恢复可见，检查是否需要新会话（>30min 离线视为新会话）
      // 心跳不重置会话，仅记录
    }
  })
}

// ── 自动采集：页面离开 ──────────────────────────────────
function setupUnloadTracking() {
  const endSession = () => {
    trackEvent('session_end', {
      session_duration_ms: Date.now() - sessionStartTs,
      questions_completed: questionsDoneThisSession,
    })
    flush()
  }

  document.addEventListener('beforeunload', endSession)
  document.addEventListener('pagehide', endSession)
}

// ── 心跳 ────────────────────────────────────────────────
function startHeartbeat() {
  heartbeatTimer = setInterval(() => {
    trackEvent('session_heartbeat', {
      current_page: window.location.pathname,
      questions_done_this_session: questionsDoneThisSession,
      active_duration_ms: Date.now() - sessionStartTs,
    })
  }, HEARTBEAT_INTERVAL_MS)
}

// ── 路由变化监听（自动页面浏览埋点） ─────────────────────
export function setupRouterTracking(router) {
  router.afterEach((to) => {
    trackEvent('page_view', {
      page: to.path,
      page_name: to.name || to.path,
    })
  })
}

// ── 初始化 ──────────────────────────────────────────────
export function initAnalytics(router) {
  scheduleFlush()
  startHeartbeat()
  setupVisibilityTracking()
  setupUnloadTracking()

  if (router) {
    setupRouterTracking(router)
  }

  trackEvent('session_start', {
    device_type: deviceType,
    last_session_gap_hours: null,
    entry_source: document.referrer || 'direct',
  })
}

// ── 便捷埋点方法（按设计文档 17 类事件） ─────────────────

export const analytics = {
  // 答题生命周期
  questionImpression(data) {
    trackEvent('question_impression', data)
  },
  questionEngage(data) {
    trackEvent('question_engage', data)
  },
  answerSubmit(data) {
    incrementQuestionsDone()
    trackEvent('answer_submit', data)
  },
  answerRetry(data) {
    trackEvent('answer_retry', data)
  },
  questionComplete(data) {
    trackEvent('question_complete', data)
  },

  // 求助行为
  hintRequest(data) {
    trackEvent('hint_request', data)
  },
  hintDismiss(data) {
    trackEvent('hint_dismiss', data)
  },
  hintChain(data) {
    trackEvent('hint_chain', data)
  },

  // 方案学习
  solutionView(data) {
    trackEvent('solution_view', data)
  },
  solutionEngage(data) {
    trackEvent('solution_engage', data)
  },

  // 决策与导航
  questionSkip(data) {
    trackEvent('question_skip', data)
  },
  knowledgeNodeClick(data) {
    trackEvent('knowledge_node_click', data)
  },
  reviewScheduleAction(data) {
    trackEvent('review_schedule_action', data)
  },

  // 情绪感知
  emotionSignal(data) {
    trackEvent('emotion_signal', data)
  },
}

export default analytics
