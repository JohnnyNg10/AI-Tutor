import axios from 'axios'

// 使用相对路径，通过 Vite 代理转发到后端
const apiClient = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 从 localStorage 获取 token
const getStoredToken = () => {
  return localStorage.getItem('access_token')
}

const setStoredToken = (token) => {
  localStorage.setItem('access_token', token)
}

const getOrCreateToken = async () => {
  // 先检查本地存储的 token
  let token = getStoredToken()
  if (token) {
    console.log('使用本地存储的token')
    return token
  }
  
  // 使用固定测试账号，避免每次刷新都注册新用户
  const username = 'demo_user'
  const password = 'demo123456'
  
  try {
    // 1. 尝试注册（如果已存在会返回400，忽略即可）
    try {
      await apiClient.post('/auth/register', {
        username: username,
        password: password
      }, { timeout: 10000 })
      console.log('注册成功:', username)
    } catch (e) {
      if (e.response?.status === 400) {
        console.log('用户已存在，直接登录:', username)
      } else {
        console.log('注册请求失败:', e.message)
      }
    }
    
    // 2. 登录拿 token
    const res = await apiClient.post('/auth/login', {
      username: username,
      password: password
    }, { timeout: 10000 })
    
    token = res.data.access_token
    setStoredToken(token)
    localStorage.setItem('current_username', username)
    console.log('登录成功，token已保存')
    return token
  } catch (e) {
    console.error('获取token失败:', e.response?.data?.detail || e.message)
    return null
  }
}

export const sendQuestion = async (question, imageBase64 = null, onChunk = null, hintLevel = 'L0') => {
  const token = await getOrCreateToken()
  
  if (!token) {
    console.error('没有token，无法请求')
    return { answer: '登录失败，请刷新重试' }
  }
  
  // 创建 FormData（用于文件上传）
  const formData = new FormData()
  
  // 确保 question 是字符串且不为空
  const safeQuestion = (question || '').toString().trim()
  if (!safeQuestion && !imageBase64) {
    return { answer: '请输入问题或上传图片' }
  }
  
  formData.append('question', safeQuestion || ' ')

  const normalizedHintLevel = (hintLevel || 'L0').toUpperCase().trim()
  const safeHintLevel = ['L0', 'L1', 'L2', 'L3', 'L4'].includes(normalizedHintLevel)
    ? normalizedHintLevel
    : 'L0'
  formData.append('hint_level', safeHintLevel)
  
  console.log('发送请求:', { question: safeQuestion, hasImage: !!imageBase64, hintLevel: safeHintLevel })
  
  if (imageBase64) {
    try {
      const arr = imageBase64.split(',')
      if (arr.length < 2) {
        throw new Error('Invalid base64 string')
      }
      const mimeMatch = arr[0].match(/:(.*?);/)
      if (!mimeMatch) {
        throw new Error('Cannot extract mime type from base64')
      }
      const mime = mimeMatch[1]
      const bstr = atob(arr[1])
      const u8arr = new Uint8Array(bstr.length)
      for (let i = 0; i < bstr.length; i++) u8arr[i] = bstr.charCodeAt(i)
      formData.append('image', new File([u8arr], 'upload.png', { type: mime }))
      console.log('图片已添加到 FormData')
    } catch (e) {
      console.error('图片处理失败:', e)
      return { answer: `图片处理失败: ${e.message}` }
    }
  }

  // ✅ 关键：不要设置 Content-Type，让浏览器自动处理 multipart/form-data
  try {
    const response = await fetch('/api/chat/ask-stream', {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`
        // 注意：不要加 'Content-Type': 'multipart/form-data'
        // 浏览器会自动设置，并加上 boundary
      },
      body: formData
    })
    
    console.log('响应状态:', response.status)
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('请求失败:', response.status, errorText)

      if (response.status === 401 || errorText.includes('Could not validate credentials')) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user_info')
        return { answer: '登录状态已失效，请重新登录。' }
      }

      return { answer: `请求失败: ${response.status} - ${errorText}` }
    }


    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let fullText = ''
    let buffer = ''

    const processEvent = (eventText) => {
      if (!eventText) return false

      const dataLines = eventText
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.replace(/^data:\s?/, ''))

      if (dataLines.length === 0) return false

      const text = dataLines.join('\n')
      if (text === '[DONE]') return true

      fullText += text
      if (onChunk) onChunk(text, fullText)
      return false
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      let boundaryIndex = buffer.indexOf('\n\n')
      while (boundaryIndex !== -1) {
        const eventText = buffer.slice(0, boundaryIndex)
        buffer = buffer.slice(boundaryIndex + 2)

        const shouldStop = processEvent(eventText)
        if (shouldStop) {
          await reader.cancel()
          return { answer: fullText }
        }

        boundaryIndex = buffer.indexOf('\n\n')
      }
    }

    if (buffer.trim()) {
      processEvent(buffer.trim())
    }

    return { answer: fullText }
  } catch (e) {
    console.error('请求异常:', e)
    return { answer: `请求异常: ${e.message}` }
  }
}
