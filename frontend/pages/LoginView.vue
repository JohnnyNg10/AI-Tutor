<template>
  <div class="login-page">
    <div class="split-container">
      <!-- 左侧品牌区 -->
      <div class="brand-side">
        <div class="brand-content">
          <div class="brand-icon"><GraduationCap :size="48" /></div>
          <h1 class="brand-title">AI Tutor</h1>
          <p class="brand-slogan">让AI成为你的私人教师</p>
          <p class="brand-sub">随时随地，高效学习</p>
          <div class="brand-features">
            <span>智能解析</span>
            <span>•</span>
            <span>个性推荐</span>
            <span>•</span>
            <span>学习追踪</span>
          </div>
        </div>
      </div>
      
      <!-- 右侧表单区 -->
      <div class="form-side">
        <div class="login-card">
          <div class="card-header">
            <div class="logo-icon"><Bot :size="28" /></div>
            <h2>欢迎回来</h2>
            <p>请登录您的账户</p>
          </div>
          
          <form @submit.prevent="handleLogin">
            <div class="input-group">
              <label>用户名</label>
              <input 
                v-model="form.username" 
                type="text" 
                placeholder="请输入用户名"
                required
              />
            </div>
            <div class="input-group">
              <label>密码</label>
              <input 
                v-model="form.password" 
                type="password" 
                placeholder="请输入密码"
                required
              />
            </div>
            <div class="form-options">
              <label class="remember">
                <input type="checkbox" v-model="rememberMe" />
                <span>记住我</span>
              </label>
              <a href="#" class="forgot">忘记密码？</a>
            </div>
            <button type="submit" class="login-btn">登录</button>
          </form>
          
          <div class="feature-trio">
            <div class="feature-item">
              <div class="feature-icon">📷</div>
              <div class="feature-text">图片识题</div>
            </div>
            <div class="divider"></div>
            <div class="feature-item">
              <div class="feature-icon">🧠</div>
              <div class="feature-text">AI讲解</div>
            </div>
            <div class="divider"></div>
            <div class="feature-item">
              <div class="feature-icon">📊</div>
              <div class="feature-text">学习分析</div>
            </div>
          </div>
          
          <div class="footer">
            <span>还没有账号？</span>
            <router-link to="/register">去注册</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { GraduationCap, Bot } from 'lucide-vue-next'

const form = reactive({
  username: '',
  password: ''
})
const rememberMe = ref(false)
const router = useRouter()

const handleLogin = async () => {
  if (!form.username || !form.password) {
    alert('请填写完整信息')
    return
  }
  
  try {
    // 调用后端登录接口
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: form.username,
        password: form.password
      })
    })
    
    if (!response.ok) {
      const error = await response.json()
      alert(error.detail || '登录失败')
      return
    }
    
    const data = await response.json()
    
    // 保存 token（关键！）
    localStorage.setItem('access_token', data.access_token)
    
    // 保存用户信息（含 user_id，便于新接口直接调用）
    localStorage.setItem('user_info', JSON.stringify({
      id: data?.user?.id,
      username: form.username,
      name: form.username,
      avatar: '👤',
      loginTime: new Date().toISOString()
    }))

    
    // 如果勾选了记住我，可以存到 localStorage，否则存 sessionStorage
    if (rememberMe.value) {
      localStorage.setItem('remember_user', form.username)
    }
    
    // 跳转到 AI 辅导页面
    router.push('/ai-tutor')
    
  } catch (error) {
    console.error('登录错误:', error)
    alert('登录失败，请检查网络连接')
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  margin: 0;
  padding: 0;
}

.split-container {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  height: 100%;
  width: 100%;
  place-items: center;
}

.brand-side {
  background: var(--color-primary);
  height: 80%;
  width: 80%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  box-sizing: border-box;
  border-radius: 24px;
  justify-self: start;
  margin-left: 10%;
}

.brand-content {
  text-align: center;
  color: white;
  max-width: 100%;
  width: 100%;
}

.brand-icon { 
  font-size: 80px; 
  margin-bottom: 20px; 
}

.brand-title { 
  font-size: 48px; 
  font-weight: 700; 
  margin: 0 0 15px 0; 
}

.brand-slogan { 
  font-size: 20px; 
  color: #fff; 
  margin: 0 0 8px 0; 
  font-weight: 500; 
}

.brand-sub { 
  font-size: 16px; 
  color: #86868b; 
  margin: 0 0 30px 0; 
}

.brand-features {
  display: flex;
  justify-content: center;
  gap: 15px;
  font-size: 13px;
  color: #666;
  letter-spacing: 1px;
  flex-wrap: wrap;
}

.form-side {
  background-color: #f5f5f7;
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding-left: 5%;
  box-sizing: border-box;
}

.login-card {
  width: 450px;
  max-width: 90%;
  height: auto;
  max-height: 85vh;
  background: #ffffff;
  border-radius: 24px;
  padding: 40px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-shadow: 0 20px 60px rgba(0,0,0,0.08);
  overflow-y: auto;
}

.card-header { 
  text-align: center; 
  margin-bottom: 30px; 
}

.logo-icon { 
  font-size: 48px; 
  margin-bottom: 15px; 
}

.card-header h2 { 
  font-size: 28px; 
  font-weight: 700; 
  color: #1d1d1f; 
  margin: 0 0 8px 0; 
}

.card-header p { 
  font-size: 15px; 
  color: #86868b; 
  margin: 0; 
}

.input-group { 
  margin-bottom: 20px; 
}

.input-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1d1d1f;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.input-group input {
  width: 100%;
  padding: 14px 16px;
  border: 2px solid #e1e1e1;
  border-radius: 12px;
  font-size: 15px;
  color: #1d1d1f;
  background: #fafafa;
  box-sizing: border-box;
  transition: all 0.3s;
}

.input-group input:focus { 
  outline: none; 
  border-color: #0071e3; 
  background: #fff; 
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,113,227,0.1);
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  font-size: 14px;
}

.remember { 
  display: flex; 
  align-items: center; 
  gap: 6px; 
  cursor: pointer; 
  color: #555; 
}

.forgot { 
  color: #0071e3; 
  text-decoration: none; 
  font-weight: 600; 
}

.login-btn {
  width: 100%;
  padding: 16px;
  background: #1d1d1f;
  color: #ffffff;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 30px;
}

.login-btn:hover { 
  background: #000; 
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.2);
}

.feature-trio {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 20px 0;
  border-top: 1px solid #eee;
  border-bottom: 1px solid #eee;
  margin-bottom: 20px;
}

.feature-item { 
  text-align: center; 
  flex: 1; 
}

.feature-icon { 
  font-size: 24px; 
  margin-bottom: 6px; 
}

.feature-text { 
  font-size: 13px; 
  font-weight: 600; 
  color: #1d1d1f; 
}

.divider { 
  width: 1px; 
  height: 30px; 
  background: #ddd; 
}

.footer { 
  text-align: center; 
  font-size: 14px; 
  color: #86868b; 
  margin-top: 10px; 
}

.footer router-link { 
  color: #0071e3; 
  text-decoration: none; 
  font-weight: 700; 
  margin-left: 4px; 
}

@media (max-width: 968px) {
  .split-container { 
    grid-template-columns: 1fr; 
  }
  .brand-side { 
    display: none; 
  }
  .form-side { 
    padding: 20px; 
    justify-content: center;
  }
  .login-card { 
    width: 100%; 
    max-width: 400px; 
    padding: 30px; 
  }
}
</style>
