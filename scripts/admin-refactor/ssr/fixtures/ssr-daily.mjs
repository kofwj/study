// 每日打卡弹窗（DailyDialog.vue）SSR 渲染体检 —— 只能覆盖「关着」的空态，这点先说明白：
//   · 这个组件不是 props 驱动（靠 defineExpose 的 open(task) 打开），SSR 的 renderToString 每次都会
//     重建实例，驱动不出「开着」的渲染（@vue/server-renderer 里没有 setRef）。
//   · 所以它的价值是：确认模块能加载、SFC 能编译、import 的 store/音效没在 SSR 下炸。
//   · 「开着」的样子（P4-b 的按钮层级：去做＝主、打卡＝次）由真机走查 + 临时样张页看，不靠这个桩。
// 注意：store.js → sounds.js 在模块级用了 localStorage / Audio，必须先打桩，所以组件用动态 import。
globalThis.localStorage = {
  getItem: () => null, setItem: () => {}, removeItem: () => {}, clear: () => {},
}
globalThis.Audio = class {
  constructor() { this.volume = 0 }
  addEventListener() {}
  play() { return Promise.resolve() }
}

async function main() {
  const { default: DailyDialog } = await import('./src/components/DailyDialog.vue')
  const { createSSRApp } = await import('vue')
  const { renderToString } = await import('vue/server-renderer')

  const warns = []
  const app = createSSRApp(DailyDialog, {})
  app.config.warnHandler = (m) => warns.push(String(m))
  app.config.errorHandler = (e) => warns.push('THROW ' + (e && e.message))
  let html = ''
  try {
    html = await renderToString(app)
  } catch (e) {
    html = 'THROW ' + (e && e.message)
  }
  console.log('DailyDialog[关着]：HTML ' + html.length + '，警告 ' + warns.length + ' 条')
  if (warns.length) console.log(warns.slice(0, 6).join('\n---\n'))
  console.log('  ' + (html.includes('THROW') ? '有问题 ' : 'OK   ') + '没有抛错')
  console.log('  关着时不渲染弹窗内容 ' + (html.includes('打卡') ? '（错）' : 'OK'))
  console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
}
main()
