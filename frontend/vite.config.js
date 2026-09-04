import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync, writeFileSync } from 'fs'
import { resolve } from 'path'

// 每次构建在 sw.js 里打一个时间戳，让浏览器检测到新版本并提示刷新
function stampSW() {
  return {
    name: 'stamp-sw',
    closeBundle() {
      const p = resolve(process.cwd(), 'dist/sw.js')
      const src = readFileSync(p, 'utf8')
      if (src.includes('__BUILD__')) {
        writeFileSync(p, src.replace('__BUILD__', String(Date.now())))
      }
    }
  }
}

export default defineConfig({
  plugins: [vue(), stampSW()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})