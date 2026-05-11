const SESSION_KEY = 'ai_tutor_recommend_session'
const MAX_AGE_MS = 24 * 60 * 60 * 1000 // 24 hours

export function useRecommendSession() {
  function saveSession(state) {
    try {
      const payload = {
        recommendations: state.recommendations || [],
        currentIndex: state.currentIndex ?? 0,
        correctCount: state.correctCount ?? 0,
        wrongCount: state.wrongCount ?? 0,
        skipCount: state.skipCount ?? 0,
        answerMap: state.answerMap ?? {},
        selectedChoice: state.selectedChoice ?? {},
        submittedSet: Array.from(state.submittedSet || []),
        isCompleted: state.isCompleted ?? false,
        advisorMode: state.advisorMode ?? '',
        advisorInstruction: state.advisorInstruction ?? null,
        profileSnap: state.profileSnap ?? {},
        limit: state.limit ?? 5,
        savedAt: Date.now(),
      }
      localStorage.setItem(SESSION_KEY, JSON.stringify(payload))
    } catch (e) {
      console.warn('保存推荐会话失败:', e)
    }
  }

  function loadSession() {
    try {
      const raw = localStorage.getItem(SESSION_KEY)
      if (!raw) return null
      const data = JSON.parse(raw)
      if (Date.now() - data.savedAt > MAX_AGE_MS) {
        localStorage.removeItem(SESSION_KEY)
        return null
      }
      if (data.isCompleted) return null
      if (!data.recommendations || data.recommendations.length === 0) return null
      return data
    } catch {
      return null
    }
  }

  function clearSession() {
    localStorage.removeItem(SESSION_KEY)
  }

  return { saveSession, loadSession, clearSession }
}


// --------------- 复习模式持久化 ---------------

const REVIEW_KEY = 'ai_tutor_review_session'

export function useReviewSession() {
  function saveReview(state) {
    try {
      const payload = {
        reviewList: state.reviewList || [],
        reviewIndex: state.reviewIndex ?? 0,
        reviewCorrectCount: state.reviewCorrectCount ?? 0,
        reviewWrongCount: state.reviewWrongCount ?? 0,
        reviewNewMastered: state.reviewNewMastered ?? 0,
        isReviewDone: state.isReviewDone ?? false,
        savedAt: Date.now(),
      }
      localStorage.setItem(REVIEW_KEY, JSON.stringify(payload))
    } catch (e) {
      console.warn('保存复习会话失败:', e)
    }
  }

  function loadReview() {
    try {
      const raw = localStorage.getItem(REVIEW_KEY)
      if (!raw) return null
      const data = JSON.parse(raw)
      if (Date.now() - data.savedAt > MAX_AGE_MS) {
        localStorage.removeItem(REVIEW_KEY)
        return null
      }
      if (data.isReviewDone) return null
      if (!data.reviewList || data.reviewList.length === 0) return null
      return data
    } catch {
      return null
    }
  }

  function clearReview() {
    localStorage.removeItem(REVIEW_KEY)
  }

  return { saveReview, loadReview, clearReview }
}
