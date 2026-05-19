import { request } from './apiService.js'

export const gradingAPI = {
  uploadImages(formData) {
    return request('/grading/upload', {
      method: 'POST',
      body: formData
    })
  },

  submitCorrections(data) {
    return request('/grading/correct', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  getResult(sessionId) {
    return request(`/grading/result/${sessionId}`)
  },

  getReport(sessionId) {
    return request(`/grading/report/${sessionId}`)
  },

  getHistory(page = 1, size = 10) {
    return request(`/grading/history?page=${page}&size=${size}`)
  },

  deleteSession(sessionId) {
    return request(`/grading/${sessionId}`, { method: 'DELETE' })
  },

  getTrend() {
    return request('/grading/trend')
  },

  cancelGrading(sessionId) {
    return request(`/grading/cancel/${sessionId}`, { method: 'POST' })
  },

  correctText(currentText, userPrompt) {
    return request('/grading/correct-text', {
      method: 'POST',
      body: JSON.stringify({ current_text: currentText, user_prompt: userPrompt })
    })
  }
}
