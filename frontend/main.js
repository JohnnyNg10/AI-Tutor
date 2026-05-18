import './styles/design-tokens.css'
import { createApp } from 'vue'
import App from './App.vue'
import router, { setupAuthSessionMonitor } from './router'
import { initAnalytics } from './services/analytics'

const app = createApp(App)
app.use(router)
setupAuthSessionMonitor(router)
initAnalytics(router)
app.mount('#app')
