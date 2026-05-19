<template>
  <AppLayout ref="layoutRef" :hide-avatar="true">
    <template #new-chat>
      <div class="sidebar-new-chat">
        <button class="new-chat-btn" @click="createNewConversation">
          <PlusCircle :size="18" />
          <span>新对话</span>
        </button>
      </div>
    </template>

    <template #history>
      <div class="sidebar-history">
        <div class="history-header">
          <span class="history-title">历史会话</span>
          <span class="history-count">{{ conversations.length }}</span>
        </div>
        <div class="history-list">
          <div
            v-for="conv in sortedConversations"
            :key="conv.id"
            class="history-item"
            :class="{ active: currentConversationId === conv.id, editing: editingId === conv.id }"
            @click="editingId !== conv.id && switchConversation(conv.id)"
          >
            <History :size="16" class="history-icon" />
            <div v-if="editingId === conv.id" class="history-edit-box" @click.stop>
              <input v-model="editingTitle" @keyup.enter="saveRename" @keyup.esc="cancelRename" @blur="saveRename" ref="renameInput" type="text" />
            </div>
            <template v-else>
              <div class="history-content">
                <div class="history-name" :title="conv.title">{{ conv.title }}</div>
                <div class="history-meta">{{ formatTime(conv.updateTime) }} · {{ conv.messages.length }}条</div>
              </div>
              <div class="history-actions">
                <button class="action-btn" @click.stop="startRename(conv)" title="重命名"><Pencil :size="12" /></button>
                <button class="action-btn" @click.stop="deleteConversation(conv.id)" title="删除"><X :size="12" /></button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </template>

    <div class="ai-tutor-content">
      <div class="top-bar">
        <div class="top-bar-spacer"></div>
        <div class="top-bar-avatar" @click="toggleUserOverlay">
          <img v-if="isImageAvatar(userInfo.avatar)" :src="userInfo.avatar" class="avatar-img" alt="" />
          <User v-else :size="20" />
        </div>
      </div>

      <div class="workspace">
        <div class="chat-container" ref="chatContainer">
          <!-- 空状态 -->
          <div v-if="!currentConversation || currentMessages.length === 0" class="welcome-screen">
            <div class="welcome-content">
              <h1 class="welcome-title">今天想练习什么数学题？</h1>
              <p class="welcome-subtitle">试试以下问题吧！</p>
              <div class="suggested-questions">
                <div class="suggestion-cards">
                  <button class="suggestion-card" @click="quickAsk('求等差数列 3, 7, 11... 的前10项和')">
                    <span class="suggestion-title">等差数列求和</span>
                    <span class="suggestion-desc">求等差数列 3, 7, 11... 的前10项和</span>
                  </button>
                  <button class="suggestion-card" @click="quickAsk('解释等比数列通项公式推导')">
                    <span class="suggestion-title">等比数列公式</span>
                    <span class="suggestion-desc">解释等比数列通项公式推导</span>
                  </button>
                  <button class="suggestion-card" @click="quickAsk('用裂项相消法求 1/(n(n+1)) 的前n项和')">
                    <span class="suggestion-title">裂项相消法</span>
                    <span class="suggestion-desc">求 1/(n(n+1)) 的前n项和</span>
                  </button>
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
                <div class="message-avatar ai-avatar"><Sparkles :size="20" /></div>
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
        <div class="input-area">
          <div class="input-inner">
            <div class="input-pill">
              <!-- Image preview mini -->
              <div class="input-toolbar" v-if="previewImage">
                <div class="image-preview-mini">
                  <img :src="previewImage" />
                  <button class="remove-img" @click="clearImage"><X :size="14" /></button>
                </div>
              </div>

              <!-- Hint level pills + textarea + actions in one row -->
              <div class="input-main">
                <div class="hint-level-pills">
                  <button
                    v-for="option in visibleHintPills"
                    :key="option.value"
                    class="hint-pill"
                    :class="{ active: selectedHintLevel === option.value }"
                    type="button"
                    @click="handleHintPillClick(option.value)"
                    :title="option.desc"
                  >
                    {{ option.value }}
                  </button>
                </div>

                <div class="input-separator">|</div>

                <textarea
                  v-model="questionText"
                  placeholder="输入数列题目或上传图片..."
                  rows="1"
                  @keydown.enter.prevent="submitQuestion"
                  ref="textareaRef"
                  @input="autoResize"
                ></textarea>

                <div class="input-actions">
                  <button class="action-btn upload-btn" @click="triggerUpload" title="上传图片">
                    <ImagePlus :size="20" />
                  </button>
                  <input
                    type="file"
                    ref="fileInput"
                    accept="image/*"
                    style="display: none"
                    @change="handleFileChange"
                  />

                  <button
                    class="action-btn send-btn"
                    @click="submitQuestion"
                    :disabled="isLoading || (!questionText && !previewImage)"
                    :class="{ 'has-content': questionText || previewImage }"
                  >
                    <Loader v-if="isLoading" :size="18" class="spinning" />
                    <Send v-else :size="18" />
                  </button>
                </div>
              </div>
            </div>

            <p class="input-hint">Enter 发送，Shift + Enter 换行</p>
          </div>
        </div>
      </div>

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
                <Upload :size="32" />
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
</AppLayout>
</template>

<script setup>
import { sendQuestion } from '../services/tutor-api.js'
import { ref, reactive, nextTick, computed, onMounted, watch, inject } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { PlusCircle, History, Pencil, X, User, Sparkles, ImagePlus, Send, Loader, Upload } from 'lucide-vue-next'
import { marked } from 'marked'
import katex from 'katex'

const router = useRouter()

const toggleUserOverlay = inject('toggleUserOverlay', () => {})

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

// ==================== 导航 ====================

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

const currentHintIndex = computed(() => hintLevelOptions.findIndex(o => o.value === selectedHintLevel.value))

const visibleHintPills = computed(() => {
  const start = Math.min(currentHintIndex.value, hintLevelOptions.length - 3)
  return hintLevelOptions.slice(start, start + 3)
})

const handleHintPillClick = (value) => {
  if (selectedHintLevel.value === value) {
    const idx = hintLevelOptions.findIndex(o => o.value === value)
    const next = (idx + 1) % hintLevelOptions.length
    selectedHintLevel.value = hintLevelOptions[next].value
  } else {
    selectedHintLevel.value = value
  }
}

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

/* ---- 新布局 (Figmm-matched) ---- */
.ai-tutor-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background: var(--color-bg-main);
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 12px 32px;
  flex-shrink: 0;
  position: relative;
}

.top-bar-avatar {
  width: 36px; height: 36px;
  border-radius: 50%; overflow: hidden;
  cursor: pointer;
  background: var(--color-border);
  display: flex;
  align-items: center; justify-content: center;
  color: var(--color-text-secondary);
}
.top-bar-avatar .avatar-img { width: 100%; height: 100%; object-fit: cover; }

/* sidebar slots */
.sidebar-new-chat { padding: 0; }
.sidebar-new-chat .new-chat-btn {
  width: 100%;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 10px;
  background: var(--color-bg-main);
  color: var(--color-text-title);
  border: 1.5px solid transparent;
  border-radius: 12px;
  font-family: var(--font-family);
  font-size: var(--font-base); font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
}
.sidebar-new-chat .new-chat-btn:hover {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(14, 97, 172, 0.12);
  background: #f5f0e0;
}

.sidebar-history {
  width: 100%;
  background: var(--color-bg-main);
  border-radius: var(--radius-lg);
  padding: 10px;
  display: flex; flex-direction: column; gap: 4px;
  flex: 1; min-height: 0; overflow: hidden;
}
.sidebar-history .history-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 4px 6px;
}
.sidebar-history .history-title {
  font-family: var(--font-family);
  font-weight: 600; font-size: var(--font-sm); color: var(--color-text-title);
}
.sidebar-history .history-count {
  font-size: 11px; color: var(--color-text-secondary);
  background: var(--color-border); padding: 2px 6px; border-radius: 10px;
}
.sidebar-history .history-list {
  flex: 1; overflow-y: auto;
  display: flex; flex-direction: column; gap: 2px; min-height: 0;
}
.sidebar-history .history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: var(--radius-base);
  cursor: pointer; transition: background 0.15s; font-size: 13px;
}
.sidebar-history .history-item:hover { background: rgba(14, 97, 172, 0.06); }
.sidebar-history .history-item.active { background: rgba(14, 97, 172, 0.12); color: var(--color-primary); font-weight: 500; }
.sidebar-history .history-icon { color: var(--color-text-secondary); flex-shrink: 0; }
.sidebar-history .history-content { flex: 1; min-width: 0; }
.sidebar-history .history-name {
  font-size: 13px; color: var(--color-text-body);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sidebar-history .history-meta { font-size: 11px; color: var(--color-text-secondary); margin-top: 1px; }
.sidebar-history .history-actions {
  display: flex; gap: 2px; opacity: 0; transition: opacity 0.2s;
}
.sidebar-history .history-item:hover .history-actions { opacity: 1; }
.sidebar-history .history-edit-box input {
  width: 100%; border: 1px solid var(--color-primary); border-radius: 4px;
  padding: 4px 6px; font-size: 13px; background: white; outline: none;
}
.sidebar-history .action-btn {
  width: 22px; height: 22px; border: none; background: transparent;
  cursor: pointer; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  color: var(--color-text-secondary); transition: all 0.15s;
}
.sidebar-history .action-btn:hover { background: rgba(0,0,0,0.08); color: var(--color-error); }

/* ---- 旧样式保留 ---- */
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

/* ===== Main Content ===== */
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

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-title);
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.welcome-subtitle {
  font-size: 16px;
  color: var(--color-text-secondary);
  margin: 0 0 40px 0;
}

.suggested-questions { text-align: center; }

.suggestion-cards {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
}

.suggestion-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  background: var(--color-primary);
  border: none;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 200px;
  max-width: 260px;
}

.suggestion-card:hover {
  filter: brightness(0.9);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(14, 97, 172, 0.3);
}

.suggestion-title {
  font-family: var(--font-family);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-bg-main);
}

.suggestion-desc {
  font-family: var(--font-family);
  font-size: 13px;
  color: var(--color-bg-main);
  opacity: 0.85;
  line-height: 1.4;
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

.input-area {
  flex-shrink: 0;
  padding: 16px 32px 24px;
  width: 100%;
}

.input-inner {
  width: 100%;
  max-width: 680px;
  margin-left: auto;
  margin-right: auto;
}

.input-pill {
  background: var(--color-text-white);
  border: 1px solid var(--color-border);
  border-radius: 28px;
  padding: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.input-toolbar {
  padding: 4px 8px 0;
}

.image-preview-mini {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--color-bg-main);
  padding: 4px 8px 4px 8px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.image-preview-mini img {
  height: 36px;
  border-radius: 4px;
}

.remove-img {
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  padding: 0;
}

.remove-img:hover {
  background: var(--color-error);
  color: white;
}

.input-main {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.hint-level-pills {
  display: flex;
  gap: 4px;
  padding: 4px;
  flex-shrink: 0;
}

.hint-pill {
  width: 32px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 16px;
  font-family: var(--font-family);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hint-pill:hover {
  background: rgba(0, 113, 227, 0.08);
  color: var(--color-primary);
}

.hint-pill.active {
  background: var(--color-primary);
  color: white;
}

.input-separator {
  color: var(--color-border);
  font-size: 16px;
  flex-shrink: 0;
  margin: 0 2px;
}

.input-main textarea {
  flex: 1;
  border: none;
  background: transparent;
  font-family: var(--font-family);
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  max-height: 200px;
  min-height: 24px;
  padding: 0 4px;
  outline: none;
  color: var(--color-text-title);
  min-width: 0;
}

.input-main textarea::placeholder {
  color: var(--color-text-secondary);
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
  color: var(--color-text-secondary);
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-border);
  color: var(--color-text-secondary);
}

.send-btn.has-content {
  background: var(--color-primary);
  color: white;
}

.send-btn.has-content:hover {
  filter: brightness(0.9);
}

.send-btn:disabled {
  cursor: not-allowed;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.input-hint {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}

.ai-avatar {
  background: var(--color-primary-light);
  color: var(--color-primary);
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
