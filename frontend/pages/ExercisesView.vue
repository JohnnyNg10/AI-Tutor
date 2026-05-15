<template>
  <AppLayout>
    <div class="exercises-page">
      <div class="page-title-area">
        <h1>错题中心</h1>
        <p class="page-subtitle">错题复习+知识点归纳</p>
      </div>

      <div class="tab-pills">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-pill"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="error" class="error">{{ error }}</div>

      <!-- 错题本 Tab -->
      <div class="tab-content" v-if="activeTab === 'mistakes'">
        <div class="toolbar">
          <label class="checkbox-label">
            <input type="checkbox" v-model="onlyDue" @change="loadMistakes" />
            仅显示到期复习
          </label>
          <button class="btn btn-primary btn-sm" :disabled="loadingMistakes" @click="loadMistakes">
            {{ loadingMistakes ? '加载中...' : '刷新错题' }}
          </button>
        </div>
        <div v-if="mistakes.length === 0" class="empty-state-text">暂无错题记录</div>
        <div v-else class="card-grid">
          <div v-for="m in mistakes" :key="m.id" class="mistake-card card">
            <div class="card-top">
              <span class="card-id">#{{ m.question_id }}</span>
              <span class="card-badge">错误{{ m.error_count }}次</span>
            </div>
            <p class="card-text">{{ shorten(m.question_content) }}</p>
            <div class="card-meta">
              <span>下次复习：{{ formatTime(m.next_review_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 复习提醒 Tab -->
      <div class="tab-content" v-if="activeTab === 'reminders'">
        <div class="toolbar">
          <label>窗口天数</label>
          <input type="number" min="1" max="30" v-model.number="windowDays" class="input-sm" />
          <button class="btn btn-primary btn-sm" :disabled="loadingReminders" @click="loadReminders">
            {{ loadingReminders ? '加载中...' : '刷新提醒' }}
          </button>
        </div>
        <div class="reminder-group">
          <h4>到期（{{ reminders.due.length }}）</h4>
          <div v-if="reminders.due.length === 0" class="empty-state-text">暂无</div>
          <div v-else class="card-grid">
            <div v-for="d in reminders.due" :key="'d-' + d.id" class="card reminder-card">
              <span class="card-id">#{{ d.question_id }}</span>
              <span class="card-meta">复习时间：{{ formatTime(d.next_review_at) }}</span>
            </div>
          </div>
          <h4>即将到期（{{ reminders.upcoming.length }}）</h4>
          <div v-if="reminders.upcoming.length === 0" class="empty-state-text">暂无</div>
          <div v-else class="card-grid">
            <div v-for="u in reminders.upcoming" :key="'u-' + u.id" class="card reminder-card">
              <span class="card-id">#{{ u.question_id }}</span>
              <span class="card-meta">复习时间：{{ formatTime(u.next_review_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 收藏夹 Tab -->
      <div class="tab-content" v-if="activeTab === 'favorites'">
        <div class="toolbar">
          <label>收藏夹名称</label>
          <input v-model="folderName" placeholder="默认收藏夹" class="input-sm" />
          <button class="btn btn-primary btn-sm" :disabled="loadingFavorites" @click="loadFavorites">
            {{ loadingFavorites ? '加载中...' : '刷新收藏' }}
          </button>
        </div>
        <div v-if="favorites.length === 0" class="empty-state-text">暂无收藏</div>
        <div v-else class="card-grid">
          <div v-for="f in favorites" :key="f.id" class="card favorite-card">
            <div class="card-top">
              <span class="card-id">#{{ f.question_id }}</span>
              <span class="card-meta">{{ f.folder_name }}</span>
            </div>
            <p class="card-text">{{ shorten(f.question_content) }}</p>
            <div class="card-footer">
              <span class="card-tags">{{ (f.tags || []).join(', ') || '-' }}</span>
              <button class="btn-danger btn-sm" @click="removeFavorite(f.id)">删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import { ensureCurrentUserId, exercisesAPI, learningToolsAPI } from '../services/apiService.js'

const activeTab = ref('mistakes')
const tabs = [
  { key: 'mistakes', label: '错题汇总' },
  { key: 'reminders', label: '复习提醒' },
  { key: 'favorites', label: '收藏夹' }
]

const error = ref('')
const userId = ref(null)

const loadingMistakes = ref(false)
const onlyDue = ref(false)
const mistakes = ref([])

const loadingReminders = ref(false)
const windowDays = ref(3)
const reminders = ref({ due: [], upcoming: [] })

const loadingFavorites = ref(false)
const folderName = ref('默认收藏夹')
const favorites = ref([])

const shorten = (text) => text ? String(text).slice(0, 120) : '-'
const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN') : '-'

async function loadMistakes() {
  loadingMistakes.value = true
  try {
    const res = await learningToolsAPI.getMistakes({ userId: userId.value, onlyDue: onlyDue.value, limit: 100 })
    mistakes.value = res?.data?.items || []
  } catch (e) {
    error.value = e?.message || '加载错题失败'
  } finally {
    loadingMistakes.value = false
  }
}

async function loadReminders() {
  loadingReminders.value = true
  try {
    const res = await learningToolsAPI.getReviewReminders({ userId: userId.value, windowDays: windowDays.value })
    reminders.value = res?.data || { due: [], upcoming: [] }
  } catch (e) {
    error.value = e?.message || '加载复习提醒失败'
  } finally {
    loadingReminders.value = false
  }
}

async function loadFavorites() {
  loadingFavorites.value = true
  try {
    const res = await learningToolsAPI.getFavorites({ userId: userId.value, folderName: folderName.value || undefined, limit: 100 })
    favorites.value = res?.data?.items || []
  } catch (e) {
    error.value = e?.message || '加载收藏夹失败'
  } finally {
    loadingFavorites.value = false
  }
}

async function removeFavorite(favoriteId) {
  try {
    await learningToolsAPI.removeFavorite({ userId: userId.value, favoriteId })
    await loadFavorites()
  } catch (e) {
    error.value = e?.message || '删除失败'
  }
}

onMounted(async () => {
  try {
    userId.value = await ensureCurrentUserId()
    await Promise.all([loadMistakes(), loadReminders(), loadFavorites()])
  } catch (e) {
    error.value = e?.message || '初始化失败'
  }
})
</script>

<style scoped>
.exercises-page {
  padding: 32px;
  max-width: var(--max-content-width);
  margin: 0 auto;
}

.page-title-area {
  margin-bottom: 20px;
}

.page-title-area h1 {
  font-family: var(--font-family);
  font-weight: 600;
  font-size: 34px;
  color: var(--color-text-title);
  margin-bottom: 4px;
}

.page-subtitle {
  font-family: var(--font-family);
  font-weight: 400;
  font-size: var(--font-md);
  color: var(--color-text-secondary);
}

.tab-pills {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
}

.tab-pill {
  font-family: var(--font-family);
  font-weight: 500;
  font-size: var(--font-sm);
  padding: 10px 20px;
  border-radius: var(--radius-lg);
  border: none;
  cursor: pointer;
  background: var(--color-primary);
  color: var(--color-text-white);
  transition: all 0.2s;
}

.tab-pill:not(.active) {
  background: var(--color-border);
  color: var(--color-text-body);
}

.tab-pill:hover:not(.active) {
  filter: brightness(0.95);
}

.error { color: var(--color-error); margin-bottom: 12px; font-size: var(--font-sm); }

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  font-size: var(--font-sm);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--color-text-body);
  font-size: var(--font-sm);
}

.input-sm {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-base);
  padding: 6px 10px;
  font-size: var(--font-sm);
  font-family: var(--font-family);
  width: 80px;
}

.btn-sm { padding: 6px 14px; font-size: var(--font-sm); }

.empty-state-text {
  text-align: center;
  padding: 48px 0;
  color: var(--color-text-secondary);
  font-size: var(--font-base);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.mistake-card, .reminder-card, .favorite-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-id {
  font-weight: 600;
  font-size: var(--font-sm);
  color: var(--color-primary);
}

.card-badge {
  font-size: var(--font-xs);
  background: rgba(233, 69, 96, 0.1);
  color: var(--color-error);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.card-text {
  font-size: var(--font-sm);
  color: var(--color-text-body);
  line-height: 1.6;
}

.card-meta {
  font-size: var(--font-xs);
  color: var(--color-text-secondary);
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-tags {
  font-size: var(--font-xs);
  color: var(--color-text-secondary);
}

.reminder-group h4 {
  font-family: var(--font-family);
  font-weight: 600;
  font-size: var(--font-sm);
  color: var(--color-text-title);
  margin: 12px 0 8px;
}
</style>
