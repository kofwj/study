import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')

// PWA：注册 service worker（离线缓存）
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}