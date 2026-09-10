import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { execSync } from 'child_process'
import { existsSync, readFileSync, writeFileSync } from 'fs'
import { resolve } from 'path'

function findFile(name) {
  for (const p of [resolve(process.cwd(), name), resolve(process.cwd(), '..', name)]) {
    if (existsSync(p)) return p
  }
  return ''
}
function appVersion() {
  const p = findFile('VERSION')
  if (!p) return 'dev'
  try { return readFileSync(p, 'utf8').trim() || 'dev' } catch { return 'dev' }
}
function appRevision() {
  const env = (process.env.APP_REVISION || process.env.GIT_SHA || '').trim()
  if (env) return env.slice(0, 12)
  const p = findFile('REVISION')
  if (p) {
    try { return readFileSync(p, 'utf8').trim().slice(0, 12) || 'dev' } catch {}
  }
  try {
    return execSync('git rev-parse --short=7 HEAD', {
      cwd: resolve(process.cwd(), '..'),
      stdio: ['ignore', 'pipe', 'ignore'],
    }).toString().trim().slice(0, 12)
  } catch {
    return 'dev'
  }
}

// 每次构建在 sw.js 里打一个时间戳，让浏览器检测到新版本并提示刷新
function stampSW() {
  return {
    name: 'stamp-sw',
    closeBundle() {
      const p = resolve(process.cwd(), 'dist/sw.js')
      if (!existsSync(p)) return
      const src = readFileSync(p, 'utf8')
      if (src.includes('__BUILD__')) {
        writeFileSync(p, src.replace('__BUILD__', String(Date.now())))
      }
    }
  }
}

export default defineConfig({
  plugins: [vue(), stampSW()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion()),
    __APP_REVISION__: JSON.stringify(appRevision()),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})