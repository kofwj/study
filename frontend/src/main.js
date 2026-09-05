import { createApp } from 'vue'
import App from './App.vue'
import './ui.css'

createApp(App).mount('#app')

// 安卓 WebView 壳（平板 APK）不要 SW：reload 经常空转，更新条点了没反应
const inWebView = /; wv\)/i.test(navigator.userAgent)
if ('serviceWorker' in navigator) {
  if (inWebView) {
    navigator.serviceWorker.getRegistrations().then((rs) => rs.forEach((r) => r.unregister())).catch(() => {})
  } else {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').then((reg) => {
        reg.update().catch(() => {})
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
}