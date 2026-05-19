<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 品牌标题 -->
    <div class="sidebar-brand">
      <span class="brand-text" v-show="!isCollapsed">AI Tutor</span>
      <span class="brand-icon" v-show="isCollapsed">T</span>
      <button class="collapse-btn" @click="toggleCollapse">
        <ChevronLeft v-if="!isCollapsed" :size="16" />
        <ChevronRight v-else :size="16" />
      </button>
    </div>

    <!-- 新建对话 (slot: shown only when parent provides content, per Figma: hidden by default) -->
    <slot name="new-chat" :collapsed="isCollapsed" />

    <!-- 导航菜单 -->
    <nav class="sidebar-nav">
      <span class="nav-section-title" v-show="!isCollapsed">导航</span>
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item) }"
      >
        <component :is="item.icon" :size="18" class="nav-icon" />
        <span class="nav-label" v-show="!isCollapsed">{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 历史会话 (slot: shown only when parent provides content, per Figma: hidden by default) -->
    <slot name="history" :collapsed="isCollapsed" />

    <!-- 用户区 -->
    <div class="user-area" @click="showDropdown = !showDropdown" ref="userAreaRef">
      <div class="user-avatar" :style="{ backgroundColor: userInfo?.avatarBg || 'var(--color-primary-light)' }">
        <User :size="18" />
      </div>
      <div class="user-info" v-show="!isCollapsed">
        <span class="user-name">{{ userInfo?.name || '学习者' }}</span>
        <span class="user-rank">{{ userInfo?.rank || '探索者 · Lv.2' }}</span>
      </div>
      <ChevronDown v-if="!isCollapsed" :size="14" class="dropdown-arrow" />

      <!-- 用户下拉卡片 -->
      <Teleport to="body">
        <div v-if="showDropdown" class="user-dropdown-overlay" @click="showDropdown = false">
          <div class="user-dropdown-card" @click.stop>
            <div class="dropdown-header">
              <div class="dropdown-avatar">
                <User :size="22" />
              </div>
              <div class="dropdown-user-info">
                <span class="dropdown-name">{{ userInfo?.name || '学习者' }}</span>
                <span class="dropdown-rank-badge">{{ userInfo?.rank || '探索者' }}</span>
              </div>
            </div>
            <div class="dropdown-progress">
              <div class="progress-label">距下一段位</div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (userInfo?.rankProgress || 65) + '%' }"></div>
              </div>
              <span class="progress-pct">{{ userInfo?.rankProgress || 65 }}%</span>
            </div>
            <div class="dropdown-stats">
              <div class="stat-item">
                <span class="stat-value">{{ userInfo?.stats?.answers || 128 }}</span>
                <span class="stat-label">答题数</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ userInfo?.stats?.accuracy || 72 }}%</span>
                <span class="stat-label">正确率</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ userInfo?.stats?.days || 15 }}</span>
                <span class="stat-label">学习天数</span>
              </div>
            </div>
            <div class="dropdown-divider"></div>
            <div class="dropdown-menu">
              <router-link to="/profile" class="dropdown-menu-item" @click="showDropdown = false">
                <BarChart2 :size="16" />
                <span>学习画像</span>
              </router-link>
              <button class="dropdown-menu-item logout" @click="handleLogout">
                <LogOut :size="16" />
                <span>退出登录</span>
              </button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Plus, MessageCircle, Star, ClipboardList, Pencil, BarChart2,
  User, ChevronLeft, ChevronRight, ChevronDown,
  MessageSquare, LogOut
} from 'lucide-vue-next'

const props = defineProps({
  showHistory: { type: Boolean, default: false },
  histories: { type: Array, default: () => [] },
  activeHistoryId: { type: String, default: null },
  userInfo: { type: Object, default: () => ({ name: '学习者', rank: '探索者 · Lv.2' }) },
})

const emit = defineEmits(['new-chat', 'navigate', 'select-history', 'logout', 'toggle'])

const route = useRoute()
const router = useRouter()
const isCollapsed = ref(false)
const showDropdown = ref(false)

// Figma nav order: AI 问答, 智能推荐, 错题中心, 学习画像, AI批改
const navItems = [
  { key: 'ai-tutor', path: '/ai-tutor', label: 'AI 问答', icon: MessageCircle },
  { key: 'recommend', path: '/recommend', label: '智能推荐', icon: Star },
  { key: 'mistake-book', path: '/mistake-book', label: '错题中心', icon: Pencil },
  { key: 'profile', path: '/profile', label: '学习画像', icon: BarChart2 },
  { key: 'grading', path: '/grading', label: 'AI 批改', icon: ClipboardList },
]

function isActive(item) {
  if (item.key === 'ai-tutor') return route.path === '/ai-tutor'
  return route.path.startsWith(item.path)
}

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  emit('toggle', isCollapsed.value)
}

const handleLogout = () => {
  showDropdown.value = false
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
  router.push('/login')
  emit('logout')
}
</script>

<style scoped>
.app-sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  background: var(--color-primary);
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 12px;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
  transition: width var(--transition-slow);
  overflow: hidden;
}

.app-sidebar.collapsed {
  width: 64px;
  min-width: 64px;
}

/* 品牌区 */
.sidebar-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.brand-text {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--color-text-white);
  letter-spacing: 0.5px;
}

.brand-icon {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--color-text-white);
  margin: 0 auto;
}

.collapse-btn {
  background: rgba(255,255,255,0.15);
  border: none;
  color: var(--color-text-white);
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: rgba(255,255,255,0.25);
}

/* 导航菜单 — Figma exact: #FAF2E0 card, cornerRadius 20, itemSpacing 8, padding 10 */
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  background: #FAF2E0;
  border-radius: 20px;
}

.nav-section-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  color: #1B1B1B;
  padding: 0 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 10px;
  border-radius: 20px;
  background: #EEEEEE;
  color: #1B1B1B;
  font-size: var(--font-size-base);
  font-weight: 500;
  transition: all var(--transition-fast);
  white-space: nowrap;
  text-decoration: none;
}

.nav-item:hover {
  background: #DDDDDD;
}

.nav-item.active {
  background: #0E61AC;
  color: #FAF2E0;
  font-weight: 600;
}

.nav-icon { flex-shrink: 0; }
.nav-label { overflow: hidden; text-overflow: ellipsis; }

/* 历史会话 */
.history-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-sm);
  margin-bottom: var(--space-sm);
}

.history-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.5);
}

.history-count {
  font-size: var(--font-size-xs);
  color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.15);
  padding: 2px 8px;
  border-radius: 10px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.history-item:hover { background: rgba(255, 255, 255, 0.08); }
.history-item.active { background: rgba(255, 255, 255, 0.15); }

.history-icon {
  color: rgba(255, 255, 255, 0.45);
  flex-shrink: 0;
}

.history-content {
  flex: 1;
  overflow: hidden;
}

.history-name {
  display: block;
  font-size: var(--font-size-sm);
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: var(--font-size-xs);
  color: rgba(255, 255, 255, 0.4);
}

.history-empty {
  text-align: center;
  color: rgba(255, 255, 255, 0.35);
  font-size: var(--font-size-sm);
  padding: var(--space-xl) 0;
}

/* 用户区 */
.user-area {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md);
  margin-top: auto;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
  position: relative;
}

.user-area:hover { background: rgba(255, 255, 255, 0.1); }

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.user-name {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-white);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-rank {
  font-size: var(--font-size-xs);
  color: var(--color-primary-subtle);
}

.dropdown-arrow {
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

/* 下拉卡片 */
.user-dropdown-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: transparent;
}

.user-dropdown-card {
  position: fixed;
  left: calc(var(--sidebar-width) + 8px);
  bottom: 16px;
  width: 280px;
  background: var(--color-bg-white);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-dropdown);
  padding: var(--space-lg);
  z-index: 1000;
}

.dropdown-header {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.dropdown-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
}

.dropdown-user-info {
  display: flex;
  flex-direction: column;
}

.dropdown-name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-title);
}

.dropdown-rank-badge {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--color-success);
  margin-top: 2px;
}

.dropdown-progress {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.dropdown-progress .progress-bar {
  flex: 1;
  height: 4px;
  background: var(--color-bg-divider);
  border-radius: 2px;
  overflow: hidden;
}

.dropdown-progress .progress-fill {
  height: 100%;
  background: var(--color-success);
  border-radius: 2px;
  transition: width var(--transition-slow);
}

.dropdown-stats {
  display: flex;
  gap: var(--space-xl);
  margin-bottom: var(--space-lg);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-title);
}

.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.dropdown-divider {
  height: 1px;
  background: var(--color-bg-divider);
  margin-bottom: var(--space-sm);
}

.dropdown-menu {
  display: flex;
  flex-direction: column;
}

.dropdown-menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  color: var(--color-text-title);
  background: none;
  border: none;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.dropdown-menu-item:hover {
  background: var(--color-bg-hover);
}

.dropdown-menu-item.logout {
  color: var(--color-danger);
}
</style>
