import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')

// PWA：注册 service worker，检测到新版本自动提示刷新
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then((reg) => {
      // 每 30 分钟主动检查一次更新
      setInterval(() => { try { reg.update() } catch {} }, 30 * 60 * 1000)
      reg.addEventListener('updatefound', () => {
        const w = reg.installing
        if (!w) return
        w.addEventListener('statechange', () => {
          if (w.state === 'activated' && navigator.serviceWorker.controller) {
            window.dispatchEvent(new CustomEvent('sw-update'))
          }
        })
      })
    }).catch(() => {})
  })
}