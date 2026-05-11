<template>
  <div class="knowledge-tree">
    <div class="tree-header">
      <div class="header-text">
        <h3>知识树学习进度</h3>
        <p class="header-desc">基于知识图谱 · {{ totalTagCount }} 个知识点标签 · {{ totalTopicCount }} 个专题</p>
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

      <div v-else-if="error" class="error-state">
        <div class="error-card">
          <span class="error-icon">⚠️</span>
          <p>{{ isFallback ? '展示的是离线演示数据，非真实学习进度' : error }}</p>
          <div class="error-actions">
            <button @click="fetchKnowledgeTree">重新加载</button>
            <span v-if="isFallback" class="fallback-badge">离线模式</span>
          </div>
        </div>
        <!-- 离线模式仍然渲染数据但标注清楚 -->
        <div v-if="isFallback" class="topics-list offline-list">
          <div v-for="topic in topics" :key="topic.topic" class="topic-item locked" @click="toggleTopic(topic.topic)">
            <div class="topic-header">
              <div class="topic-icon locked"><span>🔒</span></div>
              <div class="topic-info">
                <span class="topic-name">{{ topic.topic }}</span>
                <span class="topic-status">离线演示</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="topics.length === 0" class="empty-state">
        <span class="empty-icon">🌱</span>
        <p>暂无学习数据，去练习中心做几道题吧</p>
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
              <span v-if="topic.status === 'mastered'">✓</span>
              <span v-else-if="topic.status === 'in_progress'">▶</span>
              <span v-else>🔒</span>
            </div>
            <div class="topic-info">
              <span class="topic-name">{{ topic.topic }}</span>
              <span class="topic-subtitle">
                <template v-if="topic.statistics.topic_count">{{ topic.statistics.topic_count }} 个子专题</template>
                <template v-if="topic.statistics.total_tags">{{ topic.statistics.matched_tags || 0 }}/{{ topic.statistics.total_tags }} 个标签有学习记录</template>
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
            <div class="expand-icon" :class="{ expanded: expandedTopics.includes(topic.topic) }">▼</div>
          </div>

          <!-- 展开区：子专题 + 标签 + 里程碑 -->
          <div v-if="expandedTopics.includes(topic.topic)" class="topic-details">
            <div v-if="topic.description" class="category-desc">📖 {{ topic.description }}</div>

            <!-- 子专题列表 -->
            <div v-if="topic.nodes && topic.nodes.length > 0" class="subtopics-section">
              <h4 class="section-title">
                子专题 ({{ topic.nodes.length }})
                <span class="section-hint">— 基于知识图谱 {{ topic.statistics.total_tags || 0 }} 个知识点标签</span>
              </h4>

              <div v-for="sub in topic.nodes" :key="sub.topic_id" class="subtopic-item" :class="'subtopic-' + sub.status">
                <div class="subtopic-header" @click="toggleSub(sub.topic_id)">
                  <div class="subtopic-status-icon">
                    <span v-if="sub.status === 'mastered'" title="已掌握 (≥80%)">✅</span>
                    <span v-else-if="sub.status === 'learning'" title="学习中 (50%-80%)">📖</span>
                    <span v-else-if="sub.status === 'weak'" title="薄弱 (30%-50%)">⚠️</span>
                    <span v-else title="未解锁 (<30%)">🔒</span>
                  </div>
                  <div class="subtopic-info">
                    <span class="subtopic-name">{{ sub.topic }}</span>
                    <span class="subtopic-desc" v-if="sub.description">{{ sub.description }}</span>
                    <span class="subtopic-tag-count">{{ sub.statistics.matched_tags }}/{{ sub.statistics.total_tags }} 已学习</span>
                  </div>
                  <div class="subtopic-progress">
                    <div class="progress-bar small">
                      <div class="progress-fill" :style="{ width: sub.progress + '%', background: getProgressColor(sub.progress) }"></div>
                    </div>
                    <span class="progress-text">{{ sub.progress_text }}</span>
                  </div>
                  <div class="expand-icon small" :class="{ expanded: expandedSubs.has(sub.topic_id) }">▼</div>
                </div>

                <!-- 标签掌握度 -->
                <div v-if="expandedSubs.has(sub.topic_id) && sub.tags && sub.tags.length > 0" class="subtopic-tags">
                  <div class="tag-grid">
                    <div
                      v-for="tag in sub.tags"
                      :key="tag.name"
                      class="tag-chip"
                      :class="{ 'tag-matched': tag.matched, 'tag-default': !tag.matched }"
                      :title="tag.matched ? '掌握度: ' + Math.round(tag.p_known * 100) + '%' : '尚未学习'"
                    >
                      <span class="tag-dot" :style="{ background: tag.matched ? getProgressColor(tag.p_known * 100) : '#e5e7eb' }"></span>
                      <span class="tag-name">{{ tag.name }}</span>
                      <span v-if="tag.matched" class="tag-pct">{{ Math.round(tag.p_known * 100) }}%</span>
                      <span v-else class="tag-no-data">未学习</span>
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
                  <span class="milestone-icon">{{ m.icon }}</span>
                  <div class="milestone-body">
                    <span class="milestone-name">{{ m.name }}</span>
                    <span class="milestone-gap" v-if="!m.achieved">还差 {{ m.threshold - topic.progress }}%</span>
                    <span class="milestone-done" v-else>已达成 ✓</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="legend" v-if="!loading && !error">
      <div class="legend-item">
        <div class="legend-dot mastered"></div><span>已掌握 (≥80%)</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot in-progress"></div><span>学习中 (30%-80%)</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot locked"></div><span>未解锁 (&lt;30%)</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({ userId: { type: Number, default: null } })

const loading = ref(false)
const error = ref('')
const isFallback = ref(false)
const overallProgress = ref(0)
const topics = ref([])
const totalTagCount = computed(() => {
  let n = 0
  for (const t of topics.value) {
    for (const sub of (t.nodes || [])) {
      n += sub.tags?.length || 0
    }
  }
  return n
})
const totalTopicCount = computed(() => {
  let n = 0
  for (const t of topics.value) n += (t.nodes || []).length
  return n
})

const expandedTopics = ref([])
const expandedSubs = ref(new Set())

const toggleSub = (subId) => {
  const s = new Set(expandedSubs.value)
  if (s.has(subId)) s.delete(subId)
  else s.add(subId)
  expandedSubs.value = s
}

const getStatusText = (status) => ({
  mastered: '已掌握', in_progress: '学习中', locked: '未解锁', not_started: '未开始'
}[status] || status)

const getTopicStatusClass = (status) => ({
  mastered: status === 'mastered',
  'in-progress': status === 'in_progress',
  locked: status === 'locked' || status === 'not_started'
})

const getProgressColor = (progress) => {
  if (progress >= 80) return '#10b981'
  if (progress >= 50) return '#f59e0b'
  if (progress >= 20) return '#3b82f6'
  return '#9ca3af'
}

const getProgressGradient = (progress) => {
  if (progress >= 80) return 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
  if (progress >= 50) return 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
  if (progress >= 20) return 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
  return 'linear-gradient(135deg, #9ca3af 0%, #6b7280 100%)'
}

const getMilestoneTooltip = (m, progress) => {
  const parts = [`${m.icon} ${m.name}`, `达成条件：${m.description}`]
  if (m.achieved) {
    parts.push('状态：已达成 ✓')
  } else {
    parts.push(`状态：未达成（还差 ${m.threshold - progress}% 即可解锁）`)
    parts.push(`当前进度：${progress}% → 目标：${m.threshold}%`)
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
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (!response.ok) throw new Error('获取知识树进度失败')

    const result = await response.json()

    if (result.success) {
      overallProgress.value = result.overall_progress
      topics.value = result.topics || []
    } else {
      throw new Error(result.message || '获取知识树进度失败')
    }
  } catch (err) {
    console.error('获取知识树进度失败:', err)
    // 不显示离线假数据 —— 改为显示明确的错误状态
    error.value = err.message || '获取知识树进度失败'
    isFallback.value = false
  } finally {
    loading.value = false
  }
}

onMounted(() => { fetchKnowledgeTree() })
</script>

<style scoped>
.knowledge-tree {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
}

.header-text { flex: 1; }
.header-text h3 { font-size: 20px; font-weight: 600; color: #1d1d1f; margin: 0 0 4px; }
.header-desc { font-size: 12px; color: #86868b; margin: 0; line-height: 1.5; }

.overall-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.progress-circle {
  width: 60px; height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center; justify-content: center;
  color: white; font-weight: 600;
}
.progress-value { font-size: 18px; line-height: 1; }
.progress-label { font-size: 12px; color: #86868b; }

/* Skeleton */
.skeleton-topic {
  height: 64px; background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%; border-radius: 12px;
  animation: shimmer 1.4s infinite; margin-bottom: 10px;
}
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

/* Error */
.error-state { text-align: center; padding: 20px 0; }
.error-card {
  display: inline-flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 24px; background: #fff8f8; border: 1px solid #fecaca;
  border-radius: 12px; color: #b91c1c; max-width: 400px;
}
.error-icon { font-size: 28px; }
.error-card p { margin: 0; font-size: 14px; }
.error-actions { display: flex; gap: 8px; align-items: center; }
.error-actions button {
  padding: 6px 16px; background: #1d1d1f; color: white;
  border: none; border-radius: 8px; cursor: pointer; font-size: 13px;
}
.fallback-badge {
  font-size: 11px; background: #fde68a; color: #92400e;
  padding: 2px 8px; border-radius: 10px;
}
.offline-list { opacity: 0.5; pointer-events: none; margin-top: 16px; }

/* Empty */
.empty-state { text-align: center; padding: 40px; }
.empty-icon { font-size: 48px; }
.empty-state p { color: #888; margin: 8px 0 16px; }
.go-practice-btn {
  display: inline-block; padding: 8px 20px; background: #0071e3; color: #fff;
  border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600;
}

/* Topics */
.topics-list { display: flex; flex-direction: column; gap: 12px; }

.topic-item {
  border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden;
  transition: all 0.2s;
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
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
.topic-icon.mastered { background: #10b981; color: white; }
.topic-icon.in-progress { background: #3b82f6; color: white; }
.topic-icon.locked { background: #e5e7eb; color: #9ca3af; }

.topic-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.topic-name { font-size: 15px; font-weight: 500; color: #1d1d1f; }
.topic-subtitle { font-size: 11px; color: #86868b; }

.topic-progress {
  display: flex; flex-direction: column; align-items: flex-end;
  gap: 4px; min-width: 100px;
}
.progress-bar { width: 80px; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.3s ease; }
.progress-text { font-size: 11px; color: #86868b; }

.expand-icon { font-size: 12px; color: #9ca3af; transition: transform 0.2s; }
.expand-icon.expanded { transform: rotate(180deg); }

/* Topic Details */
.topic-details { padding: 0 16px 16px; border-top: 1px solid #f3f4f6; }

.section-title { font-size: 13px; font-weight: 600; color: #374151; margin: 16px 0 10px; }
.section-hint { font-weight: 400; color: #9ca3af; font-size: 11px; }

/* Nodes */
.nodes-list { display: flex; flex-direction: column; gap: 6px; }

.node-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px; background: #fafafa;
  border-left: 3px solid transparent; transition: all 0.2s;
}
.node-item:hover { background: #f0f0f0; }
.node-item.node-mastered { border-left-color: #10b981; }
.node-item.node-learning { border-left-color: #3b82f6; }
.node-item.node-weak { border-left-color: #f59e0b; }
.node-item.node-locked { border-left-color: #e5e7eb; opacity: 0.7; }

.node-status-icon { font-size: 16px; width: 24px; text-align: center; flex-shrink: 0; }

.node-body { flex: 1; min-width: 0; }
.node-name { font-size: 13px; font-weight: 500; color: #1d1d1f; margin-bottom: 4px; }

.node-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.node-mastery-bar { width: 60px; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; }
.node-mastery-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.node-pct { font-size: 11px; color: #86868b; min-width: 32px; }
.node-prereq {
  font-size: 10px; color: #9ca3af; cursor: help;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px;
}

/* Category description */
.category-desc { font-size: 13px; color: #6b7280; margin-bottom: 12px; padding: 8px 12px; background: #f9fafb; border-radius: 8px; line-height: 1.6; }

/* Sub-topics */
.subtopics-section { display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }

.subtopic-item { border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; transition: all 0.2s; }
.subtopic-item:hover { box-shadow: 0 1px 4px rgba(0,0,0,.04); }
.subtopic-item.subtopic-mastered { border-color: #a7f3d0; background: rgba(16,185,129,.02); }
.subtopic-item.subtopic-learning { border-color: #93c5fd; }
.subtopic-item.subtopic-weak { border-color: #fcd34d; }
.subtopic-item.subtopic-locked { opacity: 0.7; }

.subtopic-header {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; cursor: pointer; transition: background 0.15s;
}
.subtopic-header:hover { background: rgba(0,0,0,.015); }

.subtopic-status-icon { font-size: 14px; width: 22px; text-align: center; flex-shrink: 0; }
.subtopic-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.subtopic-name { font-size: 13px; font-weight: 500; color: #1d1d1f; }
.subtopic-desc { font-size: 11px; color: #86868b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.subtopic-tag-count { font-size: 10px; color: #9ca3af; }

.subtopic-progress {
  display: flex; flex-direction: column; align-items: flex-end; gap: 3px; min-width: 80px;
}
.progress-bar.small { width: 60px; height: 4px; }
.expand-icon.small { font-size: 10px; }

/* Tag chips */
.subtopic-tags { padding: 8px 12px 12px 44px; border-top: 1px solid #f3f4f6; }

.tag-grid { display: flex; flex-wrap: wrap; gap: 5px; }

.tag-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: 12px; font-size: 11px;
  cursor: help; transition: all 0.15s;
}
.tag-chip.tag-matched { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; }
.tag-chip.tag-default { background: #f9fafb; border: 1px solid #e5e7eb; color: #9ca3af; }
.tag-chip:hover { transform: translateY(-1px); }

.tag-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.tag-name { max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-pct { font-weight: 600; font-size: 10px; }
.tag-no-data { font-size: 10px; color: #d1d5db; }

/* Milestones */
.milestone-list { display: flex; flex-wrap: wrap; gap: 8px; }

.milestone-item {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 12px; background: #f3f4f6;
  font-size: 12px; color: #9ca3af; cursor: help; transition: all 0.2s;
}
.milestone-item.achieved { background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e; }
.milestone-item:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,.1); }

.milestone-icon { font-size: 14px; }
.milestone-body { display: flex; flex-direction: column; gap: 1px; }
.milestone-name { font-weight: 500; }
.milestone-gap { font-size: 10px; color: #ef4444; }
.milestone-done { font-size: 10px; color: #059669; }

/* Legend */
.legend { display: flex; justify-content: center; gap: 20px; margin-top: 20px; padding-top: 16px; border-top: 1px solid #e5e7eb; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #86868b; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.legend-dot.mastered { background: #10b981; }
.legend-dot.in-progress { background: #3b82f6; }
.legend-dot.locked { background: #9ca3af; }

/* Loading state */
.loading { display: flex; flex-direction: column; gap: 12px; padding: 20px 0; }

@media (max-width: 768px) {
  .tree-header { flex-direction: column; }
  .milestone-list { flex-direction: column; }
}
</style>
