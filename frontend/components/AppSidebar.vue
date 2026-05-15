<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-logo">
      <span class="logo-text" v-show="!collapsed">AI Tutor</span>
      <span class="logo-icon" v-show="collapsed">AT</span>
    </div>

    <button class="collapse-btn" @click="$emit('toggle')" :title="collapsed ? '展开' : '收起'">
      <ChevronLeft v-if="!collapsed" :size="16" />
      <ChevronRight v-else :size="16" />
    </button>

    <div class="user-area" @click="$emit('user-click')" v-if="!hideAvatar && !collapsed">
      <div class="user-avatar">
        <img v-if="isImageAvatar(userAvatar)" :src="userAvatar" class="avatar-img" alt="" />
        <User v-else :size="20" />
      </div>
      <span class="user-name">{{ userName || '用户' }}</span>
    </div>

    <slot name="new-chat"></slot>
    <slot name="history"></slot>

    <nav class="nav-container">
      <span class="nav-label" v-show="!collapsed">导航</span>

      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        :title="collapsed ? item.label : ''"
      >
        <component :is="item.icon" :size="20" />
        <span class="nav-item-label" v-show="!collapsed">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  MessageCircle, Sparkles, BookOpen, User, ClipboardCheck,
  ChevronLeft, ChevronRight
} from 'lucide-vue-next'

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  userName: { type: String, default: '' },
  userAvatar: { type: String, default: '' },
  hideAvatar: { type: Boolean, default: false }
})

defineEmits(['toggle', 'user-click'])

const route = useRoute()

const navItems = [
  { path: '/ai-tutor', label: 'AI 问答', icon: MessageCircle },
  { path: '/recommend', label: '智能推荐', icon: Sparkles },
  { path: '/exercises', label: '错题中心', icon: BookOpen },
  { path: '/profile', label: '学习画像', icon: User },
  { path: '/grading', label: 'AI批改', icon: ClipboardCheck }
]

const isActive = (path) => {
  if (path === '/grading') return route.path.startsWith('/grading')
  return route.path === path
}

const isImageAvatar = (avatar) => {
  return avatar && (avatar.startsWith('http') || avatar.startsWith('/') || avatar.startsWith('data:'))
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  background: var(--color-bg-sidebar);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  transition: width 0.25s ease, min-width 0.25s ease;
  overflow: hidden;
  user-select: none;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
  min-width: var(--sidebar-collapsed-width);
  align-items: center;
  padding: 16px 10px;
}

.sidebar-logo {
  width: 100%;
  padding: 4px 0;
}

.collapsed .sidebar-logo {
  text-align: center;
}

.logo-text {
  font-family: var(--font-family);
  font-weight: 900;
  font-size: 23px;
  color: var(--color-text-sidebar);
  letter-spacing: -0.01em;
}

.logo-icon {
  font-family: var(--font-family);
  font-weight: 900;
  font-size: 18px;
  color: var(--color-text-sidebar);
}

.collapse-btn {
  align-self: flex-end;
  background: rgba(250, 242, 224, 0.15);
  border: none;
  color: var(--color-text-sidebar);
  cursor: pointer;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, transform 0.2s;
  flex-shrink: 0;
}

.collapsed .collapse-btn {
  align-self: center;
}

.collapse-btn:hover {
  background: rgba(250, 242, 224, 0.25);
  transform: scale(1.1);
}

.user-area {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 0;
  cursor: pointer;
  border-radius: var(--radius-base);
  transition: background 0.15s;
}

.user-area:hover {
  background: var(--color-bg-sidebar-hover);
}

.user-avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  overflow: hidden;
  background: rgba(250, 242, 224, 0.2);
  display: flex;
  align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--color-text-sidebar);
}

.avatar-img { width: 100%; height: 100%; object-fit: cover; }

.user-name {
  color: var(--color-text-sidebar);
  font-family: var(--font-family);
  font-size: 13px; font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-container {
  width: 100%;
  background: var(--color-bg-main);
  border-radius: var(--radius-lg);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.collapsed .nav-container {
  padding: 8px;
}

.nav-label {
  font-family: var(--font-family);
  font-weight: 900;
  font-size: 14px;
  color: var(--color-text-title);
  padding: 0 6px 4px;
  letter-spacing: 0.4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 10px;
  border-radius: var(--radius-lg);
  color: var(--color-text-body);
  text-decoration: none;
  font-family: var(--font-family);
  font-size: var(--font-base);
  font-weight: 500;
  transition: all 0.2s ease;
  background: var(--color-border);
  min-height: 36px;
}

.collapsed .nav-item {
  justify-content: center;
  padding: 8px;
}

.nav-item:hover { filter: brightness(0.95); }

.nav-item.active {
  background: var(--color-primary);
  color: var(--color-text-white);
  font-weight: 600;
}

.nav-item-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
