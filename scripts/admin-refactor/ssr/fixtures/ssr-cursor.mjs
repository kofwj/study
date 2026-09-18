// 已学到页（AdminCursor.vue）SSR 渲染体检：桩数据挂载 → 抓 Vue 警告 / 抛错 / 关键文案 / 开关状态。
// 反向对照：把 kidName 改回 currentKidName，重跑应报「警告 1 条」+「乐乐」缺失。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import AdminCursor from './src/components/AdminCursor.vue'

const warns = []
const props = {
  cursors: { '语文': 't1' },
  progressLock: true,
  hiddenSubjects: ['英语'],
  spriteCfg: { enabled: true, base_enabled: false },
  subjects: [{ id: '语文', name: '语文' }, { id: '数学', name: '数学' }, { id: '英语', name: '英语' }],
  tasks: [
    { id: 't1', subject_id: '语文', unit_id: 'u1', title: '背诵第一课' },
    { id: 't2', subject_id: '数学', unit_id: 'u1', title: '口算 20 题' },
    { id: 't3', subject_id: '英语', unit_id: 'u2', title: '单词 10 个' },
  ],
  daily: [{ subject_id: '语文' }],
  termUnits: [{ id: 'u1' }, { id: 'u2' }],
  tasksBySubject: {
    '语文': [{ id: 't1', title: '背诵第一课' }],
    '数学': [{ id: 't2', title: '口算 20 题' }],
    '英语': [{ id: 't3', title: '单词 10 个' }],
  },
  kidName: '乐乐',
}

async function main() {
  const app = createSSRApp(AdminCursor, props)
  app.config.warnHandler = (m) => warns.push(String(m))
  app.config.errorHandler = (e) => warns.push('THROW ' + (e && e.message))
  const html = await renderToString(app)
  const need = ['已学到哪一课', '语文', '数学', '从头开始', '背诵第一课', '孩子端显示学科',
    '进度锁', '只让打「当前单元」', '图鉴与基地', '阳光图鉴', '秘密基地', '乐乐']
  console.log('AdminCursor：HTML 长度 ' + html.length + '，警告 ' + warns.length + ' 条')
  if (warns.length) console.log(warns.slice(0, 8).join('\n---\n'))
  for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
  // 开关状态：显示学科 3 个（语文开 / 数学开 / 英语关）+ 进度锁开 + 阳光图鉴开 + 秘密基地关
  // 这里以前数的是「.toggle 文字按钮」，换成 AdminSwitch 之后那两行永远 0/0、看着通过其实什么都没验，
  // 所以改成数真的开关：role="switch" 的个数 + aria-checked 的真假。对不上就打「缺失」→ run_ssr.sh 会红。
  const swCount = (html.match(/role="switch"/g) || []).length
  const swOn = (html.match(/aria-checked="true"/g) || []).length
  const swOff = (html.match(/aria-checked="false"/g) || []).length
  const swOk = swCount === 6 && swOn === 4 && swOff === 2
  console.log('  ' + (swOk ? 'OK   ' : '缺失 ') + '开关：' + swCount + ' 个 / on ' + swOn + ' / off ' + swOff + '（期望 6 / 4 / 2）')
  console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
}
main()
