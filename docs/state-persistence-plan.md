# 前端状态持久化与模块切换体验优化计划

## 一、问题诊断

### 1.1 根本原因

```
模块切换时 Vue 组件被销毁 → 所有 ref()/reactive() 状态丢失 → onMounted 重新请求 API → 从头开始
```

前端使用 Vue 3 + Vue Router 做 SPA 路由切换。当用户从 `/recommend` 切到 `/ai-tutor` 再切回时：
- `RecommendView.vue` 组件 `unmount` → 所有本地状态销毁
- 再次 `mount` → `onMounted()` 调用 `loadRecommendations()` → 全新请求
- 用户之前的做题进度（做到第几题、对了几题、错了几题）全部归零

### 1.2 当前状态一览

| 状态 | 存储方式 | 切换模块后 | 刷新页面后 | 关浏览器后 |
|------|---------|-----------|-----------|-----------|
| 用户登录 token | localStorage | ✅ 保留 | ✅ 保留 | ✅ 保留 |
| 用户基本信息 | localStorage | ✅ 保留 | ✅ 保留 | ✅ 保留 |
| AI Tutor 聊天记录 | localStorage | ✅ 保留 | ✅ 保留 | ✅ 保留 |
| **推荐题目列表** | `ref([])` 组件内存 | ❌ 丢失 | ❌ 丢失 | ❌ 丢失 |
| **当前做到第几题** | `ref(0)` 组件内存 | ❌ 丢失 | ❌ 丢失 | ❌ 丢失 |
| **已做题答案** | `reactive({})` 组件内存 | ❌ 丢失 | ❌ 丢失 | ❌ 丢失 |
| **对/错/跳过计数** | `ref(0)` 组件内存 | ❌ 丢失 | ❌ 丢失 | ❌ 丢失 |
| 已提交的反馈 | 后端 MySQL + Redis | ✅ 保留 | ✅ 保留 | ✅ 保留 |
| Seen Set / Mastery | 后端 Redis | ✅ 保留 | ✅ 保留 | ✅ 保留 |

### 1.3 后端已有的可复用设施

后端有一套完整的 Redis Session 基础设施（`backend/services/session_service.py`），但**前端没有用**：

| 基础设施 | 当前状态 | 可复用性 |
|---------|---------|---------|
| `ai:tutor:session:{sid}` Redis Hash | 存在，用于单题对话 | 可扩展到推荐会话 |
| `session_service.py` CRUD | 完整 | 直接复用 |
| `recommendation_session_id` 字段 | 前端已经发送但每次新建 | 可改为复用 |
| `redis_client.py` 基础操作 | 完整 | 直接复用 |

---

## 二、解决方案设计

### 2.1 方案选型：localStorage + 后端 Session 双层持久化

| 层级 | 负责什么 | 为什么需要 |
|------|---------|-----------|
| **localStorage** | 即时恢复 UI 状态 | 无网络延迟，切换模块瞬间恢复 |
| **Redis Session** | 跨设备/跨浏览器持久化 | 用户换浏览器或清缓存后仍可恢复 |

### 2.2 需要持久化的状态

```
推荐会话状态（RecommendSessionState）:
├── sessionId: string              // 推荐会话 ID，用于关联后端
├── recommendations: Question[]    // 完整的推荐题目列表
├── currentIndex: number           // 当前做到第几题
├── correctCount / wrongCount / skipCount  // 计数
├── answerMap: { [qid]: answer }   // 用户提交的答案
├── submittedSet: string[]         // 已提交的题目 ID 列表
├── isCompleted: boolean           // 是否已完成本轮推荐
├── createdAt: timestamp           // 会话创建时间
└── advisorSnapshot: {             // Advisor 模式快照
      mode, instruction, profileSnap
    }
```

### 2.3 恢复逻辑

```
RecommendView.onMounted():
  1. 检查 localStorage 是否有推荐会话
  2. 如果有，且未完成（isCompleted = false）：
     a. 从 localStorage 恢复所有状态
     b. 可选：向后端验证会话是否仍有效
     c. 用户直接回到之前的做题位置
  3. 如果没有或已完成：
     a. 正常调用 loadRecommendations() 获取新推荐
     b. 创建新的推荐会话状态写入 localStorage
  4. 每次状态变更（答题、翻题）：
     a. 写入 localStorage（同步，即时）
     b. 每 3 道题或页面卸载时同步到 Redis（异步，可靠）
```

---

## 三、实施步骤

### Step 1: 前端 — 创建推荐会话持久化模块

**新建文件**: `frontend/composables/useRecommendSession.js`

```javascript
// 核心功能：
// - saveSession(state)     → localStorage.setItem('ai_tutor_recommend_session', JSON)
// - loadSession()          → 从 localStorage 恢复
// - clearSession()         → 完成或用户主动刷新时清除
// - syncToBackend(state)   → POST /api/advisor/session/sync 同步到 Redis
// - restoreFromBackend()   → GET /api/advisor/session/current 从 Redis 恢复

const SESSION_KEY = 'ai_tutor_recommend_session'

export function useRecommendSession() {
  function saveSession(state) {
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      ...state,
      savedAt: Date.now()
    }))
  }

  function loadSession() {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    try {
      const data = JSON.parse(raw)
      // 24小时过期
      if (Date.now() - data.savedAt > 24 * 60 * 60 * 1000) {
        localStorage.removeItem(SESSION_KEY)
        return null
      }
      return data
    } catch { return null }
  }

  function clearSession() {
    localStorage.removeItem(SESSION_KEY)
  }

  return { saveSession, loadSession, clearSession }
}
```

### Step 2: 前端 — 改造 RecommendView.vue

**修改文件**: `frontend/pages/RecommendView.vue`

当前 `onMounted` 逻辑：
```javascript
onMounted(async () => {
  loadUserInfo()
  await checkRedis()
  await loadRecommendations()  // 每次都全新加载
})
```

改造后：
```javascript
onMounted(async () => {
  loadUserInfo()
  await checkRedis()

  const { loadSession } = useRecommendSession()
  const saved = loadSession()

  if (saved && !saved.isCompleted && saved.recommendations.length > 0) {
    // 恢复之前的推荐会话
    restoreFromSession(saved)
    // 可选：静默检查后端是否有新推荐
  } else {
    // 正常加载新推荐
    await loadRecommendations()
    // 创建新会话
    saveSessionFromCurrentState()
  }
})

// 在每个状态变更点调用 saveSessionFromCurrentState()：
// - goNext()       → 翻题后
// - submitChoiceAnswer()  → 提交后
// - submitEssayAnswer()   → 提交后
// - handleSkip()   → 跳过
```

### Step 3: 后端 — 新增推荐会话同步 API

**新建文件** 或扩展: `backend/api/advisor.py`

```
PUT  /api/advisor/recommend-session   — 同步推荐会话状态到 Redis
GET  /api/advisor/recommend-session   — 获取当前活跃的推荐会话
DELETE /api/advisor/recommend-session — 完成时清除
```

Redis 数据结构：
```
Key:   ai:tutor:recommend-session:{user_id}
Type:  Hash
TTL:   24 hours
Fields:
  - session_id: string
  - current_index: int
  - correct_count: int
  - wrong_count: int
  - skip_count: int
  - recommendations: JSON string (最多存 20 题)
  - answer_map: JSON string
  - submitted_set: JSON string
  - is_completed: "0"|"1"
  - updated_at: ISO timestamp
```

### Step 4: 后端 — 扩展推荐 API 支持会话恢复

修改 `GET /api/advisor/recommend`：
- 新增可选参数 `session_id` 
- 如果传入 `session_id` 且会话中还有未完成的题目，返回会话中的题目列表而不是全新推荐

### Step 5: 前端 — 添加"继续上次练习"提示

在 RecommendView 顶部添加横幅：
```
┌─────────────────────────────────────────────┐
│ 📝 你还有未完成的练习（已做 2/5 题）         │
│ [继续上次练习]  [开始新练习]                 │
└─────────────────────────────────────────────┘
```

### Step 6: 前端 — onUnmounted 时保存状态

```javascript
onUnmounted(() => {
  // 组件销毁前保存当前状态
  if (!allDone.value && recommendations.value.length > 0) {
    saveSessionFromCurrentState()
  }
})
```

---

## 四、不需要改动的地方

以下机制已经正常运作，**不需要修改**：

- ✅ 答题反馈提交 → Redis Seen Set + Review ZSet + Mastery Hash → 这些是永久持久化的
- ✅ AI Tutor 聊天记录 → localStorage `ai_tutor_conversations` → 已经持久化
- ✅ 用户画像 → Redis `ai:tutor:profile:{uid}` → 30 分钟 TTL + MySQL 降级
- ✅ 登录状态 → localStorage `access_token` → JWT 24h 有效期
- ✅ 知识图谱、成就、错题本等 → MySQL 持久化

---

## 五、验收标准

- [ ] 从推荐页切到 AI Tutor 聊天，再切回来，推荐进度完整保留（做到第几题、对错统计）
- [ ] 刷新浏览器页面，推荐进度恢复
- [ ] 完成一轮推荐后（5 题全做完），再次进入推荐页自动加载新推荐
- [ ] 异常情况（localStorage 满了、Redis 挂了）有降级处理，不会白屏
- [ ] 切换模块时没有闪烁和加载等待（数据从 localStorage 即时恢复，不触发 API 请求）

---

## 六、实施优先级

| 步骤 | 内容 | 工作量 | 优先级 |
|------|------|--------|--------|
| Step 1 | 创建 useRecommendSession composable | 0.5h | 🔴 必须先做 |
| Step 2 | 改造 RecommendView.vue 状态管理 | 1-2h | 🔴 核心 |
| Step 5 | 继续练习提示横幅 | 0.5h | 🟡 UX 重要 |
| Step 6 | onUnmounted 保存 | 0.5h | 🟡 可靠保证 |
| Step 3 | 后端 Session 同步 API | 1h | 🟢 锦上添花 |
| Step 4 | 扩展推荐 API 支持会话恢复 | 1h | 🟢 锦上添花 |

**建议先做 Step 1+2+5+6（纯前端，2-3 小时可完成），即可解决 90% 的体验问题。** Step 3+4 在需要跨设备/跨浏览器的场景下再补。
