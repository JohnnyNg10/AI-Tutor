<template>
  <div class="ai-tutor-page" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <!-- 左侧边栏 -->
    <aside class="sidebar">
      <div class="user-section" @click="showEditProfile = true">
        <div class="user-avatar-large">
          <img v-if="isImageAvatar(userInfo.avatar)" :src="userInfo.avatar" class="avatar-img" />
          <span v-else>{{ userInfo.avatar }}</span>
        </div>
        <div class="user-info" v-show="!isSidebarCollapsed">
          <span class="user-name">{{ userInfo.name }}</span>
          <span class="edit-hint">✏️ 点击编辑</span>
        </div>
      </div>
      
      <button class="toggle-btn" @click.stop="toggleSidebar">
        {{ isSidebarCollapsed ? '→' : '←' }}
      </button>

      <!-- 新建会话按钮 -->
      <div class="new-chat-section" v-show="!isSidebarCollapsed">
        <button class="new-chat-btn" @click="createNewConversation">
          <span>➕</span>
          <span>新建对话</span>
        </button>
      </div>

      <nav class="nav-menu">
        <!-- 快速导航 -->
        <div class="quick-nav" v-show="!isSidebarCollapsed">
          <div class="nav-header">
            <span class="nav-title">🧭 发现</span>
          </div>
          <router-link to="/ai-tutor" class="nav-item active">
            <span class="nav-icon">💬</span>
            <span>AI 提问</span>
          </router-link>
          <router-link to="/recommend" class="nav-item">
            <span class="nav-icon">✨</span>
            <span>数列推荐</span>
          </router-link>
          <router-link to="/mistake-book" class="nav-item">
            <span class="nav-icon">📝</span>
            <span>练习中心</span>
          </router-link>
          <router-link to="/profile" class="nav-item">
            <span class="nav-icon">📊</span>
            <span>学习画像</span>
          </router-link>
        </div>


        <!-- 历史会话列表 -->
        <div class="history-section" v-show="!isSidebarCollapsed">
          <div class="history-header">
            <span class="history-title">💬 历史会话</span>
            <span class="history-count">{{ conversations.length }}</span>
          </div>
          
          <div class="history-list">
            <div 
              v-for="conv in sortedConversations" 
              :key="conv.id"
              class="history-item"
              :class="{ 
                'active': currentConversationId === conv.id, 
                'editing': editingId === conv.id 
              }"
              @click="editingId !== conv.id && switchConversation(conv.id)"
            >
              <div class="history-icon">💭</div>
              
              <!-- 重命名输入框 -->
              <div v-if="editingId === conv.id" class="history-edit-box" @click.stop>
                <input 
                  v-model="editingTitle" 
                  @keyup.enter="saveRename"
                  @keyup.esc="cancelRename"
                  @blur="saveRename"
                  ref="renameInput"
                  type="text"
                />
              </div>
              
              <!-- 正常显示 -->
              <template v-else>
                <div class="history-content">
                  <div class="history-name" :title="conv.title">{{ conv.title }}</div>
                  <div class="history-meta">
                    {{ formatTime(conv.updateTime) }} · {{ conv.messages.length }}条
                  </div>
                </div>
                <div class="history-actions">
                  <button class="action-btn edit-btn" @click.stop="startRename(conv)" title="重命名">
                    ✏️
                  </button>
                  <button class="action-btn delete-btn" @click.stop="deleteConversation(conv.id)" title="删除">
                    ✕
                  </button>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 折叠状态 -->
        <div v-show="isSidebarCollapsed" class="collapsed-icons">
          <div 
            v-for="conv in conversations.slice(0, 3)" 
            :key="conv.id"
            class="collapsed-history-item"
            :class="{ 'active': currentConversationId === conv.id }"
            @click="switchConversation(conv.id)"
            :title="conv.title"
          >
            💭
          </div>
          <div v-if="conversations.length > 3" class="collapsed-more">...</div>
        </div>
      </nav>

      <div class="sidebar-footer" v-show="!isSidebarCollapsed">
        <button class="logout-btn" @click="logout">
          <span>🚪</span>
          <span>退出登录</span>
        </button>
      </div>
    </aside>
    
    <!-- 中间主内容区 -->
    <main class="main-content">
      <div class="mobile-header">
        <button class="mobile-menu-btn" @click="toggleSidebar">☰</button>
        <span class="mobile-title">AI Tutor</span>
        <button class="mobile-new-btn" @click="createNewConversation">➕</button>
      </div>

      <div class="workspace">
        <div class="chat-container" ref="chatContainer">
          <!-- 空状态 -->
          <div v-if="!currentConversation || currentMessages.length === 0" class="welcome-screen">
            <div class="welcome-content">
              <div class="welcome-icon">🎓</div>
              <h1 class="welcome-title">AI Tutor</h1>
              <p class="welcome-subtitle">{{ currentConversation?.title || '开始新的学习之旅' }}</p>
              <div class="suggested-questions">
                <p class="suggest-hint">试试这样问我：</p>
                <div class="question-chips">
                  <button class="chip" @click="quickAsk('求等差数列 3, 7, 11... 的前10项和')">求等差数列前10项和</button>
                  <button class="chip" @click="quickAsk('解释等比数列通项公式')">解释等比数列通项公式</button>
                  <button class="chip" @click="quickAsk('用裂项相消法求 1/(n(n+1)) 的前n项和')">裂项相消法求和</button>
                </div>
              </div>
            </div>
          </div>

          <!-- 消息列表 -->
          <div v-else class="messages-list">
            <div 
              v-for="(msg, index) in currentMessages" 
              :key="index"
              :id="'msg-' + index"
              class="message-item"
            >
              <!-- 用户消息 -->
              <div v-if="msg.role === 'user'" class="message user-message">
                <div class="message-avatar user-avatar">
                  <img v-if="isImageAvatar(userInfo.avatar)" :src="userInfo.avatar" class="avatar-img-small" />
                  <span v-else>{{ userInfo.avatar }}</span>
                </div>
                <div class="message-content user-content">
                  <div class="message-header">
                    <span class="sender">{{ userInfo.name }}</span>
                    <span class="time">{{ msg.time }}</span>
                  </div>
                  <div class="message-body">{{ msg.content }}</div>
                  <img v-if="msg.image" :src="msg.image" class="message-image" />
                </div>
              </div>

              <!-- AI消息 -->
              <div v-else class="message ai-message">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                  <div class="message-header">
                    <span class="sender">AI Tutor</span>
                  </div>
                  <div class="message-body" v-if="msg.loading">
                    <div class="thinking-indicator">
                      <div class="dot-flashing"></div>
                      <span>正在思考...</span>
                    </div>
                  </div>
                  <div class="message-body markdown-body" v-else v-html="renderContent(msg.content)"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-wrapper">
          <div class="input-inner">
            <div class="input-card">
              <div class="input-toolbar" v-if="previewImage">
                <div class="image-preview-mini">
                  <img :src="previewImage" />
                  <span class="remove-img" @click="clearImage">✕</span>
                </div>
              </div>
              
              <div class="hint-level-toolbar">
                <span class="hint-level-label">提示等级</span>
                <button
                  v-for="option in hintLevelOptions"
                  :key="option.value"
                  class="hint-level-btn"
                  :class="{ active: selectedHintLevel === option.value }"
                  type="button"
                  @click="selectedHintLevel = option.value"
                  :title="option.desc"
                >
                  {{ option.value }} · {{ option.label }}
                </button>
              </div>

              <div class="input-main">
                <textarea 
                  v-model="questionText"
                  placeholder="输入数列题目或上传图片..."
                  rows="1"
                  @keydown.enter.prevent="submitQuestion"
                  ref="textareaRef"
                  @input="autoResize"
                ></textarea>
                
                <div class="input-actions">
                  <button class="action-icon upload-btn" @click="triggerUpload" title="上传图片">
                    📷
                  </button>
                  <input 
                    type="file" 
                    ref="fileInput"
                    accept="image/*"
                    style="display: none"
                    @change="handleFileChange"
                  />
                  
                  <button 
                    class="send-btn" 
                    @click="submitQuestion"
                    :disabled="isLoading || (!questionText && !previewImage)"
                    :class="{ 'active': questionText || previewImage }"
                  >
                    <span v-if="isLoading">⏳</span>
                    <span v-else>➤</span>
                  </button>
                </div>
              </div>
              
              <div class="input-footer-bar">
                <span class="hint">Enter 发送，Shift + Enter 换行</span>
                <span class="session-hint" v-if="currentConversation">
                  {{ currentConversation.title }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 右侧消息导航 -->
    <aside class="memory-panel" v-show="!isMemoryCollapsed">
      <div class="memory-header">
        <h3>消息导航</h3>
        <button class="close-btn" @click="isMemoryCollapsed = true">✕</button>
      </div>
      
      <div class="memory-list" v-if="currentMessages.length > 0">
        <div 
          v-for="(msg, index) in currentMessages.filter(m => m.role === 'user')" 
          :key="index"
          class="memory-item"
          @click="scrollToMessage(index)"
        >
          <div class="memory-number">#{{ Math.floor(index/2) + 1 }}</div>
          <div class="memory-content">
            <div class="memory-question">{{ truncate(msg.content, 20) || '[图片]' }}</div>
            <div class="memory-time">{{ msg.time }}</div>
          </div>
        </div>
      </div>
      
      <div class="memory-empty" v-else>
        <p>还没有消息</p>
        <p class="sub">在下方输入框开始提问</p>
      </div>

      <div class="memory-footer">
        <button class="clear-btn" @click="clearCurrentConversation" v-if="currentMessages.length > 0">
          🗑️ 清空当前会话
        </button>
      </div>
    </aside>

    <button 
      class="memory-toggle-btn" 
      v-show="isMemoryCollapsed" 
      @click="isMemoryCollapsed = false"
    >
      📋
    </button>

    <!-- 用户信息编辑弹窗 -->
    <div class="modal-overlay" v-if="showEditProfile" @click="showEditProfile = false">
      <div class="modal-content" @click.stop>
        <h3>编辑个人信息</h3>
        
        <div class="avatar-section">
          <div class="current-avatar">
            <img v-if="isImageAvatar(tempUserInfo.avatar)" :src="tempUserInfo.avatar" class="avatar-preview" />
            <span v-else class="avatar-preview-text">{{ tempUserInfo.avatar }}</span>
          </div>
          
          <div class="avatar-tabs">
            <button 
              class="tab-btn" 
              :class="{ active: avatarTab === 'emoji' }"
              @click="avatarTab = 'emoji'"
            >
              Emoji
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: avatarTab === 'upload' }"
              @click="avatarTab = 'upload'"
            >
              上传图片
            </button>
          </div>

          <div v-if="avatarTab === 'emoji'" class="avatar-selector">
            <div 
              v-for="emoji in avatarOptions" 
              :key="emoji"
              class="avatar-option"
              :class="{ 'selected': tempUserInfo.avatar === emoji }"
              @click="tempUserInfo.avatar = emoji"
            >
              {{ emoji }}
            </div>
          </div>

          <div v-else class="upload-section">
            <div class="upload-area" @click="triggerAvatarUpload">
              <input 
                type="file" 
                ref="avatarFileInput"
                accept="image/*"
                style="display: none"
                @change="handleAvatarChange"
              />
              <div v-if="!tempUserInfo.avatarPreview" class="upload-placeholder">
                <span class="upload-icon">📤</span>
                <span>点击上传头像</span>
              </div>
              <img v-else :src="tempUserInfo.avatarPreview" class="avatar-preview-upload" />
            </div>
          </div>
        </div>

        <div class="input-group">
          <label>昵称</label>
          <input v-model="tempUserInfo.name" type="text" maxlength="10" />
          <small class="input-hint">修改后仅在本机生效</small>
        </div>
        
        <div class="modal-actions">
          <button class="btn-secondary" @click="showEditProfile = false">取消</button>
          <button class="btn-primary" @click="saveUserInfo">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// ========== 第1步：导入API（新增）==========
import { sendQuestion } from '../services/tutor-api.js'

import { ref, reactive, nextTick, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import katex from 'katex'

const router = useRouter()

// ==================== Markdown + LaTeX 渲染 ====================
const renderContent = (text) => {
  if (!text) return ''

  let content = String(text)
  const codeBlocks = []
  const mathBlocks = []

  // 1) 保护代码块，避免误处理
  content = content.replace(/```[\s\S]*?```/g, (match) => {
    const token = `@@CODEBLOCK${codeBlocks.length}@@`
    codeBlocks.push(match)
    return token
  })

  // 2) 兼容 \(...\) / \[...\] 语法
  content = content
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, formula) => `$$${formula}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, formula) => `$${formula}$`)

  // 3) 渲染块级公式
  content = content.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), {
        throwOnError: false,
        displayMode: true
      })
      const token = `@@MATHBLOCK${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch {
      return `<div class="latex-error">${formula}</div>`
    }
  })

  // 4) 渲染行内公式
  content = content.replace(/\$([^\n$]+?)\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), {
        throwOnError: false,
        displayMode: false
      })
      const token = `@@MATHINLINE${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch {
      return `<span class="latex-error">${formula}</span>`
    }
  })

  // 5) Markdown 转 HTML
  let html = marked.parse(content, { breaks: true })

  // 6) 恢复公式与代码块
  html = html.replace(/@@MATH(?:BLOCK|INLINE)(\d+)@@/g, (_, index) => {
    return mathBlocks[Number(index)] || ''
  })

  html = html.replace(/@@CODEBLOCK(\d+)@@/g, (_, index) => {
    return codeBlocks[Number(index)] || ''
  })

  return html
}

// ==================== 侧边栏状态 ====================
const isSidebarCollapsed = ref(false)
const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

// ==================== 会话管理 ====================
const STORAGE_KEY = 'ai_tutor_conversations'
const USER_KEY = 'user_info'

const conversations = ref([])
const currentConversationId = ref(null)
const editingId = ref(null)
const editingTitle = ref('')
const renameInput = ref(null)

const currentConversation = computed(() => {
  return conversations.value.find(c => c.id === currentConversationId.value)
})

const currentMessages = computed(() => {
  return currentConversation.value?.messages || []
})

const sortedConversations = computed(() => {
  return [...conversations.value].sort((a, b) => b.updateTime - a.updateTime)
})

const loadConversations = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      conversations.value = JSON.parse(saved)
      if (conversations.value.length > 0) {
        const sorted = [...conversations.value].sort((a, b) => b.updateTime - a.updateTime)
        currentConversationId.value = sorted[0].id
      } else {
        createNewConversation()
      }
    } else {
      createNewConversation()
    }
  } catch (e) {
    console.error('加载会话失败:', e)
    createNewConversation()
  }
}

const saveConversations = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
  } catch (e) {
    console.error('保存会话失败:', e)
  }
}

const createNewConversation = () => {
  const newConv = {
    id: 'conv_' + Date.now(),
    title: '新会话 ' + (conversations.value.length + 1),
    messages: [],
    createTime: Date.now(),
    updateTime: Date.now()
  }
  conversations.value.push(newConv)
  currentConversationId.value = newConv.id
  saveConversations()
  nextTick(() => scrollToBottom())
}

const switchConversation = (convId) => {
  if (editingId.value) return
  currentConversationId.value = convId
  nextTick(() => scrollToBottom())
}

const deleteConversation = (convId) => {
  if (!confirm('确定要删除这个会话吗？')) return
  const index = conversations.value.findIndex(c => c.id === convId)
  if (index === -1) return
  
  conversations.value.splice(index, 1)
  if (currentConversationId.value === convId) {
    if (conversations.value.length > 0) {
      const sorted = [...conversations.value].sort((a, b) => b.updateTime - a.updateTime)
      currentConversationId.value = sorted[0].id
    } else {
      createNewConversation()
    }
  }
  saveConversations()
}

// 重命名功能
const startRename = (conv) => {
  editingId.value = conv.id
  editingTitle.value = conv.title
  nextTick(() => {
    renameInput.value?.focus()
    renameInput.value?.select()
  })
}

const saveRename = () => {
  if (!editingId.value) return
  const conv = conversations.value.find(c => c.id === editingId.value)
  if (conv && editingTitle.value.trim()) {
    conv.title = editingTitle.value.trim()
    conv.updateTime = Date.now()
    saveConversations()
  }
  editingId.value = null
  editingTitle.value = ''
}

const cancelRename = () => {
  editingId.value = null
  editingTitle.value = ''
}

const clearCurrentConversation = () => {
  if (!confirm('确定要清空当前会话的所有消息吗？')) return
  if (currentConversation.value) {
    currentConversation.value.messages = []
    currentConversation.value.title = '新会话'
    currentConversation.value.updateTime = Date.now()
    saveConversations()
  }
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date
  
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000)
    return minutes < 1 ? '刚刚' : `${minutes}分钟前`
  }
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  }
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

// ==================== 用户信息 ====================
const userInfo = reactive({
  name: '学习者',
  avatar: '👤'
})

const tempUserInfo = reactive({ 
  name: userInfo.name, 
  avatar: userInfo.avatar,
  avatarPreview: null 
})

const loadUserInfo = () => {
  try {
    const saved = localStorage.getItem(USER_KEY)
    if (saved) {
      const data = JSON.parse(saved)
      userInfo.name = data.username || data.name || '学习者'
      if (data.avatar) userInfo.avatar = data.avatar
      tempUserInfo.name = userInfo.name
      tempUserInfo.avatar = userInfo.avatar
    }
  } catch (e) {
    console.error('加载用户信息失败:', e)
  }
}

const showEditProfile = ref(false)
const avatarTab = ref('emoji')
const avatarOptions = ['👤', '👨‍🎓', '👩‍🎓', '🧑‍💻', '👨‍🏫', '👩‍🏫', '🦁', '🐯', '🦊', '🐼', '🤖', '👽']

const isImageAvatar = (avatar) => {
  return avatar && (avatar.startsWith('data:') || avatar.startsWith('blob:') || avatar.startsWith('http'))
}

const saveUserInfo = () => {
  userInfo.name = tempUserInfo.name || '学习者'
  userInfo.avatar = tempUserInfo.avatarPreview || tempUserInfo.avatar
  
  localStorage.setItem(USER_KEY, JSON.stringify({
    username: userInfo.name,
    name: userInfo.name,
    avatar: userInfo.avatar
  }))
  
  showEditProfile.value = false
}

// ==================== 【修改后的退出登录】====================
const logout = () => {
  if (confirm('确定要退出登录吗？')) {
    // 清除登录凭证（关键！）
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    localStorage.removeItem('remember_user')
    
    // 跳转到登录页
    router.push('/login')
  }
}

// ==================== 消息输入（已对接后端）====================
const questionText = ref('')
const previewImage = ref(null)
const fileInput = ref(null)
const textareaRef = ref(null)
const isLoading = ref(false)
const isMemoryCollapsed = ref(false)

const hintLevelOptions = [
  { value: 'L0', label: '自主', desc: '仅批改/追问，不直接完整解答' },
  { value: 'L1', label: '方向', desc: '给出解题方向，不展开细节' },
  { value: 'L2', label: '公式', desc: '给出相关公式和定理提示' },
  { value: 'L3', label: '步骤', desc: '给出关键步骤，保留最后结论' },
  { value: 'L4', label: '答案', desc: '给出完整解答与结论' }
]
const selectedHintLevel = ref('L0')

const autoResize = () => {
  const textarea = textareaRef.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
  }
}

const quickAsk = (text) => {
  questionText.value = text
  nextTick(() => autoResize())
}

const triggerUpload = () => {
  fileInput.value.click()
}

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      previewImage.value = e.target.result
    }
    reader.readAsDataURL(file)
  }
}

const clearImage = () => {
  previewImage.value = null
  if (fileInput.value) fileInput.value.value = ''
}

// ========== 第2步：修改提交函数（核心改动）==========
const submitQuestion = async () => {
  if ((!questionText.value.trim() && !previewImage.value) || isLoading.value) return
  
  if (!currentConversation.value) createNewConversation()
  
  isLoading.value = true
  const now = new Date()
  const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  const question = questionText.value
  const imageBase64 = previewImage.value
  
  if (currentMessages.value.length === 0 && question && currentConversation.value.title.startsWith('新会话')) {
    currentConversation.value.title = question.substring(0, 20) + (question.length > 20 ? '...' : '')
  }
  
  currentConversation.value.messages.push({
    role: 'user',
    content: question || '[图片]',
    image: imageBase64,
    time: timeStr
  })
  
  const aiMessage = ref({
    role: 'ai',
    content: '',
    loading: true,
    time: timeStr
  })
  currentConversation.value.messages.push(aiMessage.value)
  
  currentConversation.value.updateTime = Date.now()
  saveConversations()
  
  questionText.value = ''
  previewImage.value = null
  if (fileInput.value) fileInput.value.value = ''
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
  
  nextTick(() => scrollToBottom())
  
  try {
    const onChunk = (chunk, fullText) => {
      aiMessage.value.content = fullText
      aiMessage.value.loading = false
      saveConversations()
      nextTick(() => scrollToBottom())
    }
    
    const response = await sendQuestion(question, imageBase64, onChunk, selectedHintLevel.value)
    
    aiMessage.value.loading = false
    saveConversations()
    
  } catch (error) {
    console.error('请求失败:', error)
    aiMessage.value.content = `❌ 请求失败：${error.message || '无法连接到后端'}\n\n可能原因：\n1. 后端没启动（运行：uvicorn main:app --reload --port 8000）\n2. 后端端口不是8000（检查前端baseURL）\n3. 后端报错了（看后端终端）`
    aiMessage.value.loading = false
    saveConversations()
    nextTick(() => scrollToBottom())
  } finally {
    isLoading.value = false
  }
}

// ==================== 头像上传 ====================
const avatarFileInput = ref(null)
const triggerAvatarUpload = () => {
  avatarFileInput.value.click()
}

const handleAvatarChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      tempUserInfo.avatarPreview = e.target.result
    }
    reader.readAsDataURL(file)
  }
}

// ==================== 滚动控制 ====================
const scrollToMessage = (index) => {
  const element = document.getElementById('msg-' + index)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const scrollToBottom = () => {
  const container = document.querySelector('.chat-container')
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

const truncate = (text, length) => {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadConversations()
  loadUserInfo()
})

watch(currentMessages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })
</script>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.ai-tutor-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  background-color: #ffffff;
  position: fixed;
  top: 0;
  left: 0;
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  min-width: 260px;
  height: 100%;
  background-color: #f9f9f9;
  border-right: 1px solid #e5e5e5;
  display: flex;
  flex-direction: column;
  padding: 20px 12px;
  position: relative;
  transition: all 0.3s ease;
}

.ai-tutor-page.sidebar-collapsed .sidebar {
  width: 60px;
  min-width: 60px;
  padding: 20px 8px;
}

.user-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.user-section:hover { background-color: #f0f0f0; }

.user-avatar-large {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img { width: 100%; height: 100%; object-fit: cover; }

.user-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.edit-hint { font-size: 11px; color: #999; margin-top: 2px; }

.toggle-btn {
  position: absolute;
  right: -12px;
  top: 80px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: white;
  border: 1px solid #e0e0e0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #666;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  z-index: 10;
}

.new-chat-section { margin-bottom: 16px; }

.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #1d1d1f;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.new-chat-btn:hover {
  background: #000;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.quick-nav {
  margin-bottom: 16px;
  border-bottom: 1px solid #e5e5e5;
  padding-bottom: 16px;
}

.nav-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px;
  margin-bottom: 12px;
}

.nav-title {
  font-size: 12px;
  font-weight: 700;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  text-decoration: none;
  color: #666;
  font-size: 14px;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.nav-item:hover {
  background-color: #f0f0f0;
  color: #1d1d1f;
}

.nav-item.active {
  background-color: #e8e8e8;
  color: #1d1d1f;
  font-weight: 600;
}

.nav-icon {
  font-size: 18px;
}

.history-section {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px;
  margin-bottom: 12px;
}

.history-title {
  font-size: 12px;
  font-weight: 700;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.history-count {
  font-size: 11px;
  color: #999;
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 10px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  border: 1px solid transparent;
}

.history-item:hover { background: #f0f0f0; }
.history-item.active { background: #e8e8e8; border-color: #d0d0d0; }
.history-item.editing { background: #f0f7ff; border-color: #0071e3; }

.history-icon { font-size: 16px; flex-shrink: 0; }

.history-content {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

.history-name {
  font-size: 13px;
  font-weight: 600;
  color: #1d1d1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.history-meta {
  font-size: 11px;
  color: #999;
}

.history-edit-box {
  flex: 1;
  min-width: 0;
}

.history-edit-box input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #0071e3;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}

.history-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.history-item:hover .history-actions { opacity: 1; }

.action-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.2s;
}

.edit-btn { color: #0071e3; }
.edit-btn:hover { background: #e3f2fd; }

.delete-btn { color: #999; }
.delete-btn:hover { background: #ffebee; color: #c62828; }

.collapsed-icons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-top: 20px;
}

.collapsed-history-item {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.2s;
}

.collapsed-history-item:hover { background: #f0f0f0; }
.collapsed-history-item.active { background: #e8e8e8; }
.collapsed-more { font-size: 12px; color: #999; padding: 4px; }

.nav-menu {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid #e5e5e5;
}

.logout-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: none;
  background: transparent;
  color: #666;
  font-size: 14px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}

.logout-btn:hover { background: #ffebee; color: #c62828; }

.main-content {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background-color: #ffffff;
}

.mobile-header {
  display: none;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e5e5;
  background: white;
  align-items: center;
  justify-content: space-between;
}

.mobile-menu-btn, .mobile-new-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.mobile-menu-btn:hover, .mobile-new-btn:hover { background: #f5f5f5; }

.mobile-title { font-size: 16px; font-weight: 600; }

.workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 40px 20px;
  width: 100%;
}

.welcome-screen,
.messages-list {
  width: 100%;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.welcome-screen {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-content { text-align: center; width: 100%; }

.welcome-icon { font-size: 64px; margin-bottom: 20px; }

.welcome-title {
  font-size: 36px;
  font-weight: 700;
  color: #1d1d1f;
  margin: 0 0 8px 0;
  letter-spacing: -1px;
}

.welcome-subtitle {
  font-size: 16px;
  color: #86868b;
  margin: 0 0 40px 0;
}

.suggested-questions { text-align: center; }

.suggest-hint { font-size: 13px; color: #999; margin-bottom: 12px; }

.question-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.chip {
  padding: 8px 16px;
  background: #f5f5f7;
  border: 1px solid #e1e1e1;
  border-radius: 20px;
  font-size: 14px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover {
  background: #e8e8e8;
  border-color: #d0d0d0;
  transform: translateY(-1px);
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 20px;
}

.message-item {
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-margin-top: 100px;
}

.message {
  display: flex;
  gap: 16px;
  width: 100%;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  overflow: hidden;
}

.user-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.avatar-img-small { width: 100%; height: 100%; object-fit: cover; }

.message-content {
  flex: 1;
  background: #f9f9f9;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #e5e5e5;
  min-width: 0;
  word-wrap: break-word;
  max-width: calc(600px - 52px);
  box-sizing: border-box;
}

.user-content {
  background: #f0f7ff;
  border-color: #d0e3ff;
}

.message-image {
  max-width: 100%;
  max-height: 200px;
  border-radius: 8px;
  margin-top: 10px;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 13px;
}

.sender { font-weight: 600; color: #1d1d1f; }
.time { color: #999; }

.message-body {
  line-height: 1.8;
  color: #444;
  font-size: 15px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #666;
  padding: 10px 0;
}

.dot-flashing {
  position: relative;
  width: 6px;
  height: 6px;
  border-radius: 5px;
  background-color: #999;
  animation: dot-flashing 1s infinite linear alternate;
  animation-delay: 0.5s;
}

.dot-flashing::before, .dot-flashing::after {
  content: "";
  position: absolute;
  top: 0;
  width: 6px;
  height: 6px;
  border-radius: 5px;
  background-color: #999;
}

.dot-flashing::before { left: -10px; animation: dot-flashing 1s infinite alternate; animation-delay: 0s; }
.dot-flashing::after { left: 10px; animation: dot-flashing 1s infinite alternate; animation-delay: 1s; }

@keyframes dot-flashing {
  0% { background-color: #999; }
  50%, 100% { background-color: #e0e0e0; }
}

.input-wrapper {
  border-top: 1px solid #e5e5e5;
  background: #ffffff;
  padding: 20px;
  width: 100%;
}

.input-inner {
  width: 100%;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.input-card {
  background: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  padding: 16px 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.05);
}

.input-toolbar { margin-bottom: 12px; }

.hint-level-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.hint-level-label {
  font-size: 12px;
  color: #666;
  font-weight: 600;
  margin-right: 2px;
}

.hint-level-btn {
  border: 1px solid #d9d9d9;
  background: #fff;
  color: #555;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.hint-level-btn:hover {
  border-color: #0071e3;
  color: #0071e3;
}

.hint-level-btn.active {
  background: #e8f2ff;
  border-color: #0071e3;
  color: #005bb5;
  font-weight: 600;
}

.image-preview-mini {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: white;
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.image-preview-mini img { height: 40px; border-radius: 4px; }

.remove-img {
  cursor: pointer;
  color: #999;
  font-size: 12px;
  padding: 4px;
}

.remove-img:hover { color: #ff4d4f; }

.input-main {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  width: 100%;
}

textarea {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  max-height: 200px;
  min-height: 24px;
  padding: 0;
  outline: none;
  color: #1d1d1f;
  width: 100%;
  min-width: 0;
}

textarea::placeholder { color: #999; }

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.action-icon {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s;
}

.action-icon:hover { background: #e8e8e8; }

.send-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: #e0e0e0;
  color: white;
  border-radius: 8px;
  cursor: not-allowed;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.send-btn.active {
  background: #1d1d1f;
  cursor: pointer;
}

.send-btn.active:hover { background: #000; transform: scale(1.05); }

.input-footer-bar {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint { font-size: 12px; color: #bbb; }

.session-hint {
  font-size: 12px;
  color: #0071e3;
  font-weight: 500;
}

.memory-panel {
  width: 220px;
  min-width: 220px;
  height: 100%;
  background-color: #fafafa;
  border-left: 1px solid #e5e5e5;
  display: flex;
  flex-direction: column;
  padding: 20px 12px;
  position: relative;
  overflow: hidden;
}

.memory-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e5e5;
}

.memory-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: #999;
  padding: 4px;
}

.close-btn:hover { color: #666; }

.memory-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memory-item {
  padding: 10px 12px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e5e5e5;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.memory-item:hover {
  background: #f0f7ff;
  border-color: #4a90e2;
  transform: translateX(-2px);
}

.memory-number {
  font-size: 11px;
  color: #0071e3;
  font-weight: 600;
  min-width: 24px;
}

.memory-content { flex: 1; overflow: hidden; }

.memory-question {
  font-size: 13px;
  color: #1d1d1f;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.memory-time { font-size: 11px; color: #999; }

.memory-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
  text-align: center;
  padding: 20px;
}

.memory-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #e5e5e5;
}

.clear-btn {
  width: 100%;
  padding: 8px;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: #ffebee;
  color: #c62828;
  border-color: #ffcdd2;
}

.memory-toggle-btn {
  position: fixed;
  right: 20px;
  bottom: 100px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #0071e3;
  color: white;
  border: none;
  box-shadow: 0 2px 8px rgba(0,113,227,0.3);
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  transition: all 0.2s;
}

.memory-toggle-btn:hover { transform: scale(1.1); background: #005bb5; }

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 28px;
  border-radius: 16px;
  width: 90%;
  max-width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  max-height: 90vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #1d1d1f;
}

.avatar-section { margin-bottom: 20px; }

.current-avatar {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  overflow: hidden;
  border: 3px solid #f0f0f0;
}

.avatar-preview { width: 100%; height: 100%; object-fit: cover; }
.avatar-preview-text { font-size: 40px; }

.avatar-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  justify-content: center;
}

.tab-btn {
  padding: 6px 16px;
  border: 1px solid #e0e0e0;
  background: white;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: #0071e3;
  color: white;
  border-color: #0071e3;
}

.avatar-selector {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-bottom: 20px;
}

.avatar-option {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background: #f5f5f7;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.avatar-option:hover { background: #e8e8e8; transform: scale(1.1); }
.avatar-option.selected { border-color: #0071e3; background: #f0f7ff; }

.upload-section { margin-bottom: 20px; }

.upload-area {
  width: 100%;
  height: 120px;
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
}

.upload-area:hover { border-color: #0071e3; background: #f0f7ff; }

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #666;
}

.upload-icon { font-size: 32px; }
.avatar-preview-upload { width: 100%; height: 100%; object-fit: contain; border-radius: 8px; }

.modal-content .input-group { margin-bottom: 20px; }

.modal-content .input-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #666;
  font-weight: 500;
}

.modal-content .input-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.modal-content .input-group input:focus {
  outline: none;
  border-color: #0071e3;
}

.input-hint {
  display: block;
  margin-top: 6px;
  color: #999;
  font-size: 12px;
}

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn-secondary, .btn-primary {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-secondary { background: #f0f0f0; color: #666; }
.btn-secondary:hover { background: #e0e0e0; }

.btn-primary { background: #0071e3; color: white; }
.btn-primary:hover { background: #005bb5; }

@media (max-width: 1200px) {
  .memory-panel {
    position: fixed;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 90;
    box-shadow: -2px 0 8px rgba(0,0,0,0.1);
  }
}

@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(0);
    box-shadow: 2px 0 8px rgba(0,0,0,0.1);
  }
  
  .ai-tutor-page.sidebar-collapsed .sidebar {
    transform: translateX(-100%);
    width: 260px;
  }
  
  .mobile-header { display: flex; }
  .toggle-btn { display: none; }
}

@media (max-width: 768px) {
  .welcome-screen, .messages-list, .input-inner {
    max-width: 100%;
    padding: 0 10px;
  }
  
  .message-content { max-width: 100%; }
  .memory-panel { width: 280px; }
  .chat-container { padding: 20px 10px; }
  .input-wrapper { padding: 12px 10px; }
}

/* ==================== Markdown + LaTeX 样式 ==================== */
.markdown-body {
  line-height: 1.8;
  color: #333;
}

.markdown-body h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 20px 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #667eea;
}

.markdown-body p {
  margin: 12px 0;
}

.markdown-body ul, .markdown-body ol {
  margin: 12px 0;
  padding-left: 24px;
}

.markdown-body li {
  margin: 6px 0;
}

.markdown-body code {
  background-color: #f4f4f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.markdown-body pre {
  background-color: #f4f4f5;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-body pre code {
  background: none;
  padding: 0;
}

.markdown-body blockquote {
  border-left: 4px solid #667eea;
  padding-left: 16px;
  margin: 12px 0;
  color: #666;
}

.markdown-body .katex-display {
  margin: 16px 0;
  overflow-x: auto;
}

.markdown-body .katex {
  font-size: 1.1em;
}

.markdown-body .latex-error {
  color: #e74c3c;
  background-color: #fdf2f2;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
}
</style>
