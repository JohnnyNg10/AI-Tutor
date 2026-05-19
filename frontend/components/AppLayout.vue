<template>
  <div class="app-layout">
    <AppSidebar
      :user-name="userName"
      :user-avatar="userAvatar"
      @toggle="onSidebarToggle"
      @user-click="toggleUserOverlay"
    >
      <template v-if="$slots['new-chat']" #new-chat>
        <slot name="new-chat"></slot>
      </template>
      <template v-if="$slots['history']" #history>
        <slot name="history"></slot>
      </template>
    </AppSidebar>
    <main class="main-content" :style="{ marginLeft: sidebarCollapsed ? '64px' : 'var(--sidebar-width)' }">
      <slot />
    </main>

    <!-- Shared User Dropdown Overlay -->
    <Teleport to="body">
      <div class="user-overlay-backdrop" v-if="showUserOverlay" @click="showUserOverlay = false"></div>
      <div class="user-overlay" v-if="showUserOverlay" @click.stop>
        <div class="overlay-header">
          <div class="overlay-avatar">
            <img v-if="isImageAvatar(userAvatar)" :src="userAvatar" alt="" />
            <User v-else :size="24" />
          </div>
          <div class="overlay-user-info">
            <span class="overlay-name">{{ userName || '学习者' }}</span>
            <span class="overlay-rank">探索者 · Lv.2</span>
          </div>
        </div>

        <div class="overlay-rank-progress">
          <div class="progress-labels">
            <span class="progress-label">距下一段位</span>
            <span class="progress-pct">65%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: 65%"></div>
          </div>
        </div>

        <div class="overlay-stats">
          <div class="stat">
            <span class="stat-value">128</span>
            <span class="stat-label">答题数</span>
          </div>
          <div class="stat">
            <span class="stat-value">72%</span>
            <span class="stat-label">正确率</span>
          </div>
          <div class="stat">
            <span class="stat-value">15</span>
            <span class="stat-label">学习天数</span>
          </div>
        </div>

        <div class="overlay-divider"></div>

        <button class="overlay-menu-item" @click="goProfile">
          <User :size="16" />
          <span>学习画像</span>
          <ChevronRight :size="16" class="menu-arrow" />
        </button>
        <button class="overlay-menu-item logout" @click="handleLogout">
          <LogOut :size="16" />
          <span>退出登录</span>
          <ChevronRight :size="16" class="menu-arrow" />
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import { useRouter } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import { User, ChevronRight, LogOut } from 'lucide-vue-next'

defineProps({
  hideAvatar: { type: Boolean, default: false }
})

const router = useRouter()
const sidebarCollapsed = ref(false)

const userName = ref('')
const userAvatar = ref('')

const showUserOverlay = ref(false)

const onSidebarToggle = (collapsed) => {
  sidebarCollapsed.value = collapsed
}

const toggleUserOverlay = () => {
  showUserOverlay.value = !showUserOverlay.value
}

const goProfile = () => {
  showUserOverlay.value = false
  router.push('/profile')
}

const handleLogout = () => {
  showUserOverlay.value = false
  if (confirm('确定要退出登录吗？本地数据将被清除。')) {
    localStorage.clear()
    location.reload()
  }
}

const isImageAvatar = (avatar) => {
  return avatar && (avatar.startsWith('data:') || avatar.startsWith('blob:') || avatar.startsWith('http'))
}

onMounted(() => {
  try {
    const raw = localStorage.getItem('user_info')
    if (raw) {
      const info = JSON.parse(raw)
      userName.value = info.name || info.username || ''
      userAvatar.value = info.avatar || ''
    }
  } catch {}
})

provide('toggleUserOverlay', toggleUserOverlay)
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--color-bg-main);
  min-width: 0;
  transition: margin-left var(--transition-slow);
}

/* ---- User Dropdown Overlay ---- */
.user-overlay-backdrop {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 998;
}

.user-overlay {
  position: fixed;
  top: 60px;
  right: 32px;
  width: 280px;
  background: white;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-dropdown);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  z-index: 999;
}

.overlay-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.overlay-avatar {
  width: 44px; height: 44px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-bg-main);
  display: flex;
  align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--color-text-secondary);
}

.overlay-avatar img { width: 100%; height: 100%; object-fit: cover; }

.overlay-user-info { display: flex; flex-direction: column; gap: 2px; flex: 1; }

.overlay-name {
  font-family: var(--font-family);
  font-size: 15px; font-weight: 600;
  color: var(--color-text-title);
}

.overlay-rank {
  font-family: var(--font-family);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.overlay-rank-progress { display: flex; flex-direction: column; gap: 6px; }

.progress-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-label { font-size: 12px; color: var(--color-text-secondary); }
.progress-pct { font-size: 12px; font-weight: 600; color: var(--color-text-title); }

.progress-track {
  width: 100%; height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill { height: 100%; background: #52C41A; border-radius: 2px; }

.overlay-stats { display: flex; justify-content: space-between; }

.stat { display: flex; flex-direction: column; align-items: center; gap: 2px; }

.stat-value {
  font-family: var(--font-family);
  font-size: 18px; font-weight: 700;
  color: var(--color-text-title);
}

.stat-label { font-size: 11px; color: var(--color-text-secondary); }

.overlay-divider {
  width: 100%; height: 1px;
  background: var(--color-border);
}

.overlay-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 4px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--color-text-title);
  cursor: pointer;
  transition: background 0.15s;
}

.overlay-menu-item:hover { background: rgba(0, 0, 0, 0.04); }

.overlay-menu-item.logout { color: #EB4D4B; }
.overlay-menu-item.logout:hover { background: rgba(235, 77, 75, 0.06); }

.menu-arrow { margin-left: auto; color: var(--color-text-secondary); }
</style>
