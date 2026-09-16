// 家庭页（AdminKids.vue）SSR 渲染体检：桩数据挂载 → 抓 Vue 警告 / 抛错 / 关键文案。
// 反向对照：把 meAccount 改成 me.account，重跑应报「警告 2 条」+ THROW。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import AdminKids from './src/components/AdminKids.vue'

const warns = []
const props = {
  kids: [
    { id: 'k1', name: '乐乐', account: 'lele', term_id: 'g5s1', gender: '男' },
    { id: 'k2', name: '弟弟', account: 'didi', term_id: 'g3s1', gender: '' },
  ],
  terms: [{ id: 'g5s1', label: '五年级上册' }, { id: 'g3s1', label: '三年级上册' }],
  members: [
    { id: 1, name: '妈妈', account: 'mama', parent_role: 'owner' },
    { id: 2, name: '爸爸', account: 'baba', parent_role: 'member' },
  ],
  invites: [{ code: 'ABC123', used_count: 0 }, { code: 'XYZ789', expired: true }],
  inviteProtect: true,
  isOwner: true,
  meAccount: 'mama',
  showToast: () => {},
}

async function main() {
  const app = createSSRApp(AdminKids, props)
  app.config.warnHandler = (m) => warns.push(String(m))
  app.config.errorHandler = (e) => warns.push('THROW ' + (e && e.message))
  const html = await renderToString(app)
  const need = ['家庭', '孩子账号', '乐乐', 'lele', '五年级上册', '家长成员', '妈妈', '创建者',
    '邀请码', 'ABC123', '已过期', '当前账号 mama', '修改家长密码', '再加一个孩子']
  console.log('AdminKids：HTML 长度 ' + html.length + '，警告 ' + warns.length + ' 条')
  if (warns.length) console.log(warns.slice(0, 8).join('\n---\n'))
  for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
  console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
}
main()
