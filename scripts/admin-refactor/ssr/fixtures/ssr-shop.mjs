// 阳光页（AdminShop.vue）SSR 渲染体检：桩数据挂载 → 抓 Vue 警告 / 抛错 / 关键文案。
// 反向对照：把 kidName 改成 currentKidName，重跑应报「警告 2 条」且「小明」缺失。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import AdminShop from './src/components/AdminShop.vue'

const warns = []
const props = {
  rewards: [{ id: 1, name: '看一集动画', price: 30, category: '娱乐' }],
  ranks: [{ id: 1, name: '小星星', min_sunshine: 0, icon: 'star' }],
  penalties: [{ id: 1, amount: 1, reason: '磨蹭', note: '', delta: -1, date: '2026-09-15', kid_id: 'k1' }],
  penaltySummary: { net: -1, count: 1, amount: -1, by_reason: [{ reason: '磨蹭', count: 1, amount: 1 }] },
  penaltyEnabled: true,
  bankData: {
    enabled: true, balance: 12, pocket_balance: 3,
    goal: { name: '去公园', target: 50, reached: false },
    requests: [{ id: 1, amount: 5, status: 'pending', created_at: '2026-09-15 10:00' }],
    ledger: [{ delta: 5, note: '存钱', date: '2026-09-14' }],
  },
  bankRequests: [{ id: 1, kid_id: 'k1', kid_name: '小明', amount: 5, status: 'pending', note: '想买贴纸' }],
  bankGoal: { name: '去公园', target: 50 },
  bankInterest: { enabled: true, cycle: 'weekly', rate: 5, threshold: 20, last_settle: '2026-09-06' },
  bankBusy: false,
  isOwner: true,
  kidName: '小明',
  showToast: () => {},
  withBusy: async (f) => { await f() },
}

async function main() {
  const app = createSSRApp(AdminShop, props)
  app.config.warnHandler = (m) => warns.push(String(m))
  app.config.errorHandler = (e) => warns.push('THROW ' + (e && e.message))
  const html = await renderToString(app)
  const need = ['小明', '阳光银行', '记下扣分', '去公园', '看一集动画', '磨蹭', '撤回', '扣多少']
  console.log('AdminShop：HTML 长度 ' + html.length + '，警告 ' + warns.length + ' 条')
  if (warns.length) console.log(warns.slice(0, 8).join('\n---\n'))
  for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
  console.log('  svg 图标数 ' + (html.match(/<svg/g) || []).length)
  console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
}
main()
