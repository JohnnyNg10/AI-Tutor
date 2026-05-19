<template>
  <div class="knowledge-tree">
    <div class="tree-header">
      <div class="header-text">
        <h3>知识树学习进度</h3>
        <p class="header-desc">基于知识图谱 · {{ totalNodeCount }} 个知识点 · {{ topics.length }} 个专题</p>
      </div>
      <div class="overall-progress">
        <div class="progress-circle" :style="{ background: getProgressGradient(overallProgress) }">
          <span class="progress-value">{{ Math.round(overallProgress) }}%</span>
        </div>
        <span class="progress-label">总进度</span>
      </div>
    </div>

    <div class="tree-content">
      <div v-if="loading" class="loading">
        <div v-for="i in 3" :key="i" class="skeleton-topic"></div>
      </div>

      <div v-else-if="topics.length === 0 && !error" class="empty-state">
        <Sprout :size="36" class="empty-icon" />
        <p>暂无学习数据，去错题中心做几道题吧</p>
        <router-link to="/mistake-book" class="go-practice-btn">去练习</router-link>
      </div>

      <div v-else class="topics-list">
        <div
          v-for="topic in topics"
          :key="topic.topic"
          class="topic-item"
          :class="getTopicStatusClass(topic.status)"
        >
          <div class="topic-header" @click="toggleTopic(topic.topic)">
            <div class="topic-icon" :class="getTopicStatusClass(topic.status)">
              <Check v-if="topic.status === 'mastered'" :size="16" />
              <Play v-else-if="topic.status === 'in_progress'" :size="16" />
              <Lock v-else :size="16" />
            </div>
            <div class="topic-info">
              <span class="topic-name">{{ topic.topic }}</span>
              <span class="topic-subtitle">
                {{ topic.statistics.total_nodes }} 个知识点 ·
                {{ topic.statistics.mastered_nodes }} 已掌握 ·
                {{ topic.statistics.learning_nodes }} 学习中 ·
                {{ topic.statistics.weak_nodes }} 薄弱
              </span>
            </div>
            <div class="topic-progress">
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: topic.progress + '%', background: getProgressColor(topic.progress) }"
                ></div>
              </div>
              <span class="progress-text">{{ topic.progress_text }}</span>
            </div>
            <div class="expand-icon" :class="{ expanded: expandedTopics.includes(topic.topic) }">
              <ChevronDown :size="12" />
            </div>
          </div>

          <!-- 展开区：知识节点列表 + 里程碑 -->
          <div v-if="expandedTopics.includes(topic.topic)" class="topic-details">
            <!-- 知识节点列表（按层级树状展示） -->
            <div v-if="topic.nodes && topic.nodes.length > 0" class="nodes-section">
              <div class="section-header">
                <h4 class="section-title">知识点详情 ({{ topic.nodes.length }})</h4>
                <span class="section-hint">— 按依赖关系排序，悬停查看诊断说明</span>
              </div>

              <div class="nodes-tree">
                <div
                  v-for="node in sortedNodes(topic.nodes)"
                  :key="node.node_id"
                  class="node-row"
                  :class="'node-' + node.status"
                  :style="{ paddingLeft: (node.position?.level || 0) * 24 + 12 + 'px' }"
                  :title="getNodeTooltip(node)"
                >
                  <!-- 层级连接线 -->
                  <div v-if="(node.position?.level || 0) > 0" class="node-connector">
                    <div class="connector-line"></div>
                    <div class="connector-dot"></div>
                  </div>

                  <!-- 状态图标 -->
                  <div class="node-status-icon">
                    <CheckCircle2 v-if="node.status === 'mastered'" :size="14" color="#10b981" />
                    <BookOpen v-else-if="node.status === 'learning'" :size="14" color="#3b82f6" />
                    <AlertTriangle v-else-if="node.status === 'weak'" :size="14" color="#f59e0b" />
                    <Lock v-else :size="14" color="#9ca3af" />
                  </div>

                  <!-- 节点信息 -->
                  <div class="node-body">
                    <div class="node-name-row">
                      <span class="node-name">{{ node.name }}</span>
                      <span
                        v-if="node.cognitive_level"
                        class="cognitive-badge"
                        :class="'cl-' + node.cognitive_level"
                      >{{ node.cognitive_level }}</span>
                    </div>

                    <!-- 掌握度进度条 -->
                    <div class="node-mastery-row">
                      <div class="node-mastery-bar">
                        <div
                          class="node-mastery-fill"
                          :style="{ width: Math.round(node.p_known * 100) + '%', background: getProgressColor(node.p_known * 100) }"
                        ></div>
                      </div>
                      <span class="node-pct">{{ Math.round(node.p_known * 100) }}%</span>
                    </div>

                    <!-- 前置依赖提示 -->
                    <div v-if="node.prerequisite_names && node.prerequisite_names.length > 0" class="node-prereq-row">
                      <span class="prereq-label">前置:</span>
                      <span class="prereq-names">{{ node.prerequisite_names.join('、') }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 里程碑 -->
            <div v-if="topic.milestones && topic.milestones.length > 0" class="milestones-section">
              <h4 class="section-title">
                学习里程碑
                <span class="section-hint">— 鼠标悬停查看达成条件</span>
              </h4>
              <div class="milestone-list">
                <div
                  v-for="m in topic.milestones"
                  :key="m.key"
                  class="milestone-item"
                  :class="{ achieved: m.achieved }"
                  :title="getMilestoneTooltip(m, topic.progress)"
                >
                  <Trophy v-if="m.achieved" :size="14" class="milestone-icon-achieved" />
                  <Award v-else :size="14" class="milestone-icon-pending" />
                  <div class="milestone-body">
                    <span class="milestone-name">{{ m.name }}</span>
                    <span class="milestone-gap" v-if="!m.achieved">还差 {{ Math.round(m.threshold - topic.progress) }}%</span>
                    <span class="milestone-done" v-else>已达成</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="legend" v-if="!loading">
      <div class="legend-item"><div class="legend-dot mastered"></div><span>已掌握 (≥80%)</span></div>
      <div class="legend-item"><div class="legend-dot learning"></div><span>学习中 (50%-80%)</span></div>
      <div class="legend-item"><div class="legend-dot weak"></div><span>薄弱 (&lt;50%)</span></div>
      <div class="legend-item"><div class="legend-dot locked"></div><span>未解锁 (前置未达标)</span></div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error && !isFallback" class="error-toast">
      <AlertTriangle :size="14" />
      <span>{{ error }}</span>
      <button @click="fetchKnowledgeTree">重试</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Lock, Check, Play, CheckCircle2, BookOpen, AlertTriangle,
  Sprout, Trophy, Award, ChevronDown
} from 'lucide-vue-next'

const props = defineProps({ userId: { type: Number, default: null } })

const loading = ref(false)
const error = ref('')
const isFallback = ref(false)
const overallProgress = ref(0)
const topics = ref([])

const totalNodeCount = computed(() => {
  let n = 0
  for (const t of topics.value) n += (t.nodes || []).length
  return n
})

const expandedTopics = ref([])

const sortedNodes = (nodes) => {
  return [...nodes].sort((a, b) => {
    const la = a.position?.level ?? 0
    const lb = b.position?.level ?? 0
    if (la !== lb) return la - lb
    return (a.position?.x ?? 0) - (b.position?.x ?? 0)
  })
}

const getNodeTooltip = (node) => {
  const parts = []
  if (node.cognitive_level) parts.push(`认知层级: ${node.cognitive_level}`)
  if (node.diagnostic_description) parts.push(`诊断: ${node.diagnostic_description}`)
  parts.push(`掌握度: ${Math.round(node.p_known * 100)}%`)
  if (node.prerequisite_names?.length) parts.push(`前置: ${node.prerequisite_names.join('、')}`)
  return parts.join('\n')
}

const getTopicStatusClass = (status) => {
  if (status === 'mastered') return 'mastered'
  if (status === 'in_progress') return 'in-progress'
  return 'locked'
}

const getProgressColor = (progress) => {
  if (progress >= 80) return '#10b981'
  if (progress >= 50) return '#3b82f6'
  if (progress >= 20) return '#f59e0b'
  return '#9ca3af'
}

const getProgressGradient = (progress) => {
  if (progress >= 80) return 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
  if (progress >= 50) return 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
  if (progress >= 20) return 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
  return 'linear-gradient(135deg, #9ca3af 0%, #6b7280 100%)'
}

const getMilestoneTooltip = (m, progress) => {
  const parts = [`${m.name}`, `达成条件：${m.description}`]
  if (m.achieved) {
    parts.push('状态：已达成')
  } else {
    parts.push(`状态：未达成（还差 ${Math.round(m.threshold - progress)}% 即可解锁）`)
    parts.push(`当前进度：${Math.round(progress)}% → 目标：${m.threshold}%`)
  }
  return parts.join('\n')
}

const toggleTopic = (topicName) => {
  const idx = expandedTopics.value.indexOf(topicName)
  if (idx > -1) expandedTopics.value.splice(idx, 1)
  else expandedTopics.value.push(topicName)
}

const fetchKnowledgeTree = async () => {
  loading.value = true
  error.value = ''
  isFallback.value = false

  try {
    const token = localStorage.getItem('access_token')
    const response = await fetch('/api/knowledge-tree/progress', {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (!response.ok) throw new Error('获取知识树进度失败')

    const result = await response.json()

    if (result.success) {
      overallProgress.value = result.overall_progress
      topics.value = result.topics || []
      // 自动展开第一个进行中的专题
      if (expandedTopics.value.length === 0) {
        const active = result.topics?.find(t => t.status === 'in_progress')
        if (active) expandedTopics.value = [active.topic]
      }
    } else {
      throw new Error(result.message || '获取知识树进度失败')
    }
  } catch (err) {
    console.error('获取知识树进度失败:', err)
    error.value = err.message || '获取知识树进度失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => { fetchKnowledgeTree() })
</script>

<style scoped>
.knowledge-tree {
  --kt-mastered: #10b981;
  --kt-learning: #3b82f6;
  --kt-weak: #f59e0b;
  --kt-locked: #9ca3af;
  background: var(--color-bg-white, #fff);
  border-radius: var(--radius-xl, 16px);
  padding: var(--space-xxl, 24px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,.08));
}

.tree-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: var(--space-xl, 20px); gap: var(--space-lg, 16px);
}
.header-text { flex: 1; }
.header-text h3 {
  font-size: var(--font-size-xl, 18px); font-weight: 600;
  color: var(--color-text-title, #1d1d1f); margin: 0 0 var(--space-xs, 4px);
}
.header-desc {
  font-size: var(--font-size-xs, 12px); color: var(--color-text-secondary, #86868b);
  margin: 0;
}

.overall-progress {
  display: flex; flex-direction: column; align-items: center;
  gap: var(--space-xs, 4px); flex-shrink: 0;
}
.progress-circle {
  width: 60px; height: 60px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 600;
}
.progress-value { font-size: var(--font-size-lg, 16px); }
.progress-label { font-size: var(--font-size-xs, 12px); color: var(--color-text-secondary, #86868b); }

/* Skeleton */
.skeleton-topic {
  height: 64px; background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%; border-radius: 12px;
  animation: shimmer 1.4s infinite; margin-bottom: 10px;
}
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

/* Empty */
.empty-state { text-align: center; padding: 40px; }
.empty-icon { color: var(--color-text-secondary, #9ca3af); }
.empty-state p { color: #888; margin: 8px 0 16px; }
.go-practice-btn {
  display: inline-block; padding: 8px 20px; background: #0071e3; color: #fff;
  border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600;
}

/* Topic list */
.topics-list { display: flex; flex-direction: column; gap: 12px; }

.topic-item {
  border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; transition: all 0.2s;
}
.topic-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.topic-item.mastered { border-color: #10b981; background: rgba(16,185,129,.03); }
.topic-item.in-progress { border-color: #3b82f6; background: rgba(59,130,246,.03); }
.topic-item.locked { opacity: 0.8; }

.topic-header {
  display: flex; align-items: center; gap: 12px;
  padding: 16px; cursor: pointer; transition: background 0.2s;
}
.topic-header:hover { background: rgba(0,0,0,.02); }

.topic-icon {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.topic-icon.mastered { background: #10b981; color: white; }
.topic-icon.in-progress { background: #3b82f6; color: white; }
.topic-icon.locked { background: #e5e7eb; color: #9ca3af; }

.topic-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.topic-name { font-size: 15px; font-weight: 500; color: #1d1d1f; }
.topic-subtitle { font-size: 11px; color: #86868b; }

.topic-progress {
  display: flex; flex-direction: column; align-items: flex-end; gap: 4px; min-width: 100px;
}
.progress-bar { width: 80px; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.3s ease; }
.progress-text { font-size: 11px; color: #86868b; }

.expand-icon { color: #9ca3af; transition: transform 0.2s; }
.expand-icon.expanded { transform: rotate(180deg); }

/* Topic details */
.topic-details { padding: 0 16px 16px; border-top: 1px solid #f3f4f6; }

.section-header { display: flex; align-items: baseline; gap: 6px; }
.section-title { font-size: 13px; font-weight: 600; color: #374151; margin: 16px 0 10px; }
.section-hint { font-weight: 400; color: #9ca3af; font-size: 11px; }

/* Knowledge node tree */
.nodes-section { margin-bottom: 8px; }
.nodes-tree { display: flex; flex-direction: column; }

.node-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 12px; border-radius: 8px;
  border-left: 3px solid transparent; transition: all 0.15s;
  position: relative; cursor: help;
}
.node-row:hover { background: #f9fafb; }
.node-row.node-mastered { border-left-color: #10b981; }
.node-row.node-learning { border-left-color: #3b82f6; }
.node-row.node-weak { border-left-color: #f59e0b; }
.node-row.node-locked { border-left-color: #e5e7eb; opacity: 0.65; }

.node-connector {
  position: absolute; left: 0; top: 0; bottom: 0;
  display: flex; align-items: center; width: 20px;
}
.connector-line { width: 2px; height: 50%; background: #e5e7eb; position: absolute; top: 0; left: 6px; }
.connector-dot { width: 6px; height: 6px; border-radius: 50%; background: #d1d5db; position: absolute; left: 4px; top: 8px; }

.node-status-icon { flex-shrink: 0; width: 20px; padding-top: 2px; }

.node-body { flex: 1; min-width: 0; }

.node-name-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.node-name { font-size: 13px; font-weight: 500; color: #1d1d1f; }

.cognitive-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 8px;
  font-weight: 500; flex-shrink: 0;
}
.cl-了解 { background: #f0fdf4; color: #166534; }
.cl-理解 { background: #eff6ff; color: #1e40af; }
.cl-掌握 { background: #fef3c7; color: #92400e; }
.cl-运用 { background: #fce7f3; color: #9d174d; }
.cl-综合运用 { background: #f3e8ff; color: #6b21a8; }

.node-mastery-row { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.node-mastery-bar { width: 80px; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; }
.node-mastery-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.node-pct { font-size: 11px; color: #86868b; min-width: 32px; }

.node-prereq-row { display: flex; align-items: baseline; gap: 4px; }
.prereq-label { font-size: 10px; color: #9ca3af; flex-shrink: 0; }
.prereq-names {
  font-size: 10px; color: #9ca3af;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* Milestones */
.milestone-list { display: flex; flex-wrap: wrap; gap: 8px; }

.milestone-item {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 12px; background: #f3f4f6;
  font-size: 12px; color: #9ca3af; cursor: help; transition: all 0.2s;
}
.milestone-item.achieved {
  background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e;
}
.milestone-item:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,.1); }

.milestone-icon-achieved { color: var(--color-success, #10b981); flex-shrink: 0; }
.milestone-icon-pending { color: var(--color-text-secondary, #9ca3af); flex-shrink: 0; }
.milestone-body { display: flex; flex-direction: column; gap: 1px; }
.milestone-name { font-weight: 500; }
.milestone-gap { font-size: 10px; color: #ef4444; }
.milestone-done { font-size: 10px; color: #059669; }

/* Legend */
.legend {
  display: flex; justify-content: center; gap: 24px; margin-top: 20px;
  padding-top: 16px; border-top: 1px solid #e5e7eb; flex-wrap: wrap;
}
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #86868b; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.legend-dot.mastered { background: #10b981; }
.legend-dot.learning { background: #3b82f6; }
.legend-dot.weak { background: #f59e0b; }
.legend-dot.locked { background: #9ca3af; }

/* Error toast */
.error-toast {
  display: flex; align-items: center; gap: 8px;
  margin-top: 16px; padding: 10px 16px;
  background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 10px; color: #b91c1c; font-size: 13px;
}
.error-toast button {
  margin-left: auto; padding: 4px 12px;
  background: #1d1d1f; color: #fff; border: none;
  border-radius: 6px; cursor: pointer; font-size: 12px;
}

.loading { display: flex; flex-direction: column; gap: 12px; padding: 20px 0; }

@media (max-width: 768px) {
  .tree-header { flex-direction: column; }
  .milestone-list { flex-direction: column; }
  .legend { gap: 12px; }
}
</style>
