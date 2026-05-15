import { ref, reactive, computed } from 'vue'

export function useGrading() {
  const mode = ref('list') // 'list' | 'upload'
  const step = ref(1) // 1=upload, 2=review, 3=grading, 4=done
  const loading = ref(false)
  const error = ref('')

  const sessionId = ref(null)
  const questionImages = ref([])
  const answerImages = ref([])
  const ocrResults = ref([])
  const currentQuestionIndex = ref(0)
  const correctionStatus = reactive({})

  const report = ref(null)

  const progress = reactive({
    current: 0,
    total: 0,
    status: 'idle',
    etaSeconds: 0
  })

  const questionStatuses = reactive({})

  const hasImages = computed(() =>
    questionImages.value.length > 0 || answerImages.value.length > 0
  )

  const allQuestionsReviewed = computed(() => {
    if (ocrResults.value.length === 0) return false
    return ocrResults.value.every((_, i) => correctionStatus[i])
  })

  function reset() {
    mode.value = 'list'
    step.value = 1
    loading.value = false
    error.value = ''
    sessionId.value = null
    questionImages.value = []
    answerImages.value = []
    ocrResults.value = []
    currentQuestionIndex.value = 0
    Object.keys(correctionStatus).forEach(k => delete correctionStatus[k])
    report.value = null
    progress.current = 0
    progress.total = 0
    progress.status = 'idle'
    progress.etaSeconds = 0
    Object.keys(questionStatuses).forEach(k => delete questionStatuses[k])
  }

  function startNewGrading() {
    reset()
    mode.value = 'upload'
    step.value = 1
  }

  function goToList() {
    reset()
    mode.value = 'list'
  }

  function setOCRResults(results) {
    ocrResults.value = results
    step.value = 2
  }

  function markReviewed(index) {
    correctionStatus[index] = true
  }

  function startGrading() {
    step.value = 3
    progress.status = 'grading'
    progress.total = ocrResults.value.length
    progress.current = 0
  }

  function updateProgress(data) {
    if (data.question_index !== undefined) {
      progress.current = data.question_index + 1
      questionStatuses[data.question_index] = data.status || 'done'
    }
    if (data.eta_seconds !== undefined) {
      progress.etaSeconds = data.eta_seconds
    }
  }

  function completeGrading(result) {
    step.value = 4
    progress.status = 'done'
    report.value = result
    sessionId.value = result.session_id
  }

  function setReport(data) {
    report.value = data
  }

  return {
    mode, step, loading, error,
    sessionId, questionImages, answerImages,
    ocrResults, currentQuestionIndex, correctionStatus,
    progress, questionStatuses, report,
    hasImages, allQuestionsReviewed,
    reset, startNewGrading, goToList,
    setOCRResults, markReviewed,
    startGrading, updateProgress, completeGrading, setReport
  }
}
