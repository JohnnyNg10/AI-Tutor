import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../pages/LoginView.vue'

const AUTH_TOKEN_KEY = 'access_token'
const PUBLIC_PATHS = new Set(['/login', '/register'])

let logoutTimer = null
let expiryCheckTimer = null
let monitorStarted = false

const clearAuthStorage = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
}

const decodeJwtPayload = (token) => {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64 + '='.repeat((4 - (base64.length % 4 || 4)) % 4)
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

const getTokenExpireAtMs = (token) => {
  const payload = decodeJwtPayload(token)
  const exp = payload?.exp
  if (!exp) return null
  return Number(exp) * 1000
}

const isTokenExpired = (token) => {
  if (!token) return true
  const expAt = getTokenExpireAtMs(token)
  if (!expAt) return true
  return Date.now() >= expAt
}

const ensureLoggedOut = (router) => {
  clearAuthStorage()
  if (!PUBLIC_PATHS.has(router.currentRoute.value.path)) {
    router.replace('/login')
  }
}

const scheduleAutoLogout = (router) => {
  if (logoutTimer) {
    clearTimeout(logoutTimer)
    logoutTimer = null
  }

  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (!token) return

  const expireAt = getTokenExpireAtMs(token)
  if (!expireAt || Date.now() >= expireAt) {
    ensureLoggedOut(router)
    return
  }

  const delay = Math.max(0, expireAt - Date.now())
  logoutTimer = setTimeout(() => {
    ensureLoggedOut(router)
  }, delay)
}

export const setupAuthSessionMonitor = (router) => {
  if (monitorStarted) return
  monitorStarted = true

  scheduleAutoLogout(router)

  expiryCheckTimer = setInterval(() => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    if (token && isTokenExpired(token)) {
      ensureLoggedOut(router)
    }
  }, 30000)

  window.addEventListener('storage', (event) => {
    if (event.key === AUTH_TOKEN_KEY) {
      scheduleAutoLogout(router)
    }
  })

  window.addEventListener('beforeunload', () => {
    if (logoutTimer) clearTimeout(logoutTimer)
    if (expiryCheckTimer) clearInterval(expiryCheckTimer)
  })
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/login'  // 根路径重定向到登录页
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../pages/RegisterView.vue')
    },
    {
      path: '/ai-tutor',
      name: 'ai-tutor',
      component: () => import('../pages/AiTutorView.vue'),
      meta: { requiresAuth: true }  // 需要登录
    },
    {
      path: '/recommend',
      name: 'recommend',
      component: () => import('../pages/RecommendView.vue'),
      meta: { requiresAuth: true }  // 需要登录
    },
    {
      path: '/exercises',
      name: 'exercises',
      component: () => import('../pages/ExercisesView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../pages/ProfileView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/mistake-book',
      name: 'mistake-book',
      component: () => import('../pages/MistakeBookView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/grading',
      name: 'grading',
      component: () => import('../pages/GradingView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/grading/report/:sessionId',
      name: 'grading-report',
      component: () => import('../pages/GradingReportView.vue'),
      meta: { requiresAuth: true }
    }
  ]
})

// 路由守卫：检查登录状态 + token 是否过期
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  const isAuthenticated = !!token && !isTokenExpired(token)

  if (token && !isAuthenticated) {
    clearAuthStorage()
  }

  if (isAuthenticated) {
    scheduleAutoLogout(router)
  }

  // 如果访问需要登录的页面但没有有效 token，跳转到登录页
  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  }
  // 如果已登录但访问登录/注册页，跳转到 ai-tutor
  else if ((to.path === '/login' || to.path === '/register') && isAuthenticated) {
    next('/ai-tutor')
  }
  // 其他情况正常放行
  else {
    next()
  }
})

export default router
