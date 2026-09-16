// 家长工作台壳（Admin.vue）SSR 渲染体检：抓「渲染期就炸」的错（少传 prop、未定义的 computed 等）。
// 数据加载都在 onMounted 里，SSR 不会发请求；这时候 kids 为空 → 渲染的是「第一个孩子」建号引导页，
// 所以断言就按这一屏写。
// 注意：只在事件回调里求值的错（例如 isDirty 里漏声明的 shopRef）这条体检抓不到，那类靠
// ../check_undeclared.mjs。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'

const problems = []

async function main() {
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }
  globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
  const Admin = (await import('./src/Admin.vue')).default
  const app = createSSRApp(Admin, { recoveryCode: '' })
  app.config.warnHandler = (m) => problems.push('WARN ' + m)
  app.config.errorHandler = (e) => problems.push('THROW ' + (e && e.message))
  let html = ''
  try {
    html = await renderToString(app)
  } catch (e) {
    problems.push('THROW ' + (e && e.message))
  }
  console.log('Admin：HTML 长度 ' + html.length + '，问题 ' + problems.length + ' 条')
  if (problems.length) console.log(problems.slice(0, 10).join('\n'))
  const need = ['<div class="admin', '第一个孩子', '创建并进入']
  for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
}
main()
