// 总览页（AdminInsights.vue）SSR 渲染体检：B4「全家共同目标」三种状态 + 抓 Vue 警告/抛错。
// 反向对照：把 goal 的 metric_label 去掉（或改坏模板），重跑应报「警告」+ 缺失。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import AdminInsights from './src/components/AdminInsights.vue'

const weekly = {
  days: [], weeks: [], by_subject: [], kids: [], mastered_by_kid: [],
  net: 0, checkins: 0, penalty_net: 0, insight: null, family_insight: null,
}
const base = {
  weekly,
  insightKids: [],
  daily: [],
  dailyHist: {},
  fitnessGoals: {},
  reviewCount: 0,
  pendingRedeem: 0,
  isMultiKid: true,
  selectedKid: '',
  kidName: '乐乐',
  parentName: '妈妈',
  weeklyGoal: 50,
  weeklyGoalBusy: false,
  subjectName: () => '语文',
}
const goal = (over) => ({
  goal: Object.assign({
    id: 1, metric: 'cards', metric_label: '完成卡数', unit: '张', target: 20, reward: 5,
    status: 'active', started_at: '2026-09-14', ends_at: '2026-09-20', reached_at: null,
  }, over.goal || {}),
  progress: Object.assign({ value: 12, target: 20, remaining: 8 }, over.progress || {}),
  by_kid: over.by_kid || [{ kid_id: 'k1', name: '乐乐', value: 7 }, { kid_id: 'k2', name: '弟弟', value: 5 }],
})

// P4-a「本周英语」：每个孩子一句（后端拼好，前端只渲染）
const weeklyWithWords = Object.assign({}, weekly, {
  kids: [
    { id: 'k1', name: '乐乐', earned: 30, spent: 10, streak: 3, current: true,
      completed: 12, completed_last: 9,
      insight: { type: 'review_due', text: '有 2 个薄弱点该复习了', action: '今日复习' },
      words: { days: 4, words: 58, rate: 78, today_wrote: 20, goal: 10, goal_done: true,
               sentence: '这周练了 4 天，首轮正确率 78%；今天写了 20/10 词（达标）' } },
    { id: 'k2', name: '弟弟', earned: 20, spent: 0, streak: 1, current: false,
      completed: 6, completed_last: 6, insight: null,
      words: { days: 0, words: 0, rate: null, today_wrote: 0, goal: 10, goal_done: false,
               sentence: '这周还没练过英语；今天还没练' } },
  ],
})
// 老后端（没有 words 字段）与「读不到」都不许崩
const weeklyNoWords = Object.assign({}, weekly, {
  kids: [{ id: 'k1', name: '乐乐', earned: 30, spent: 10, streak: 3, current: true,
           completed: 12, completed_last: 9, insight: null }],
})

const warns = []
async function render(props) {
  warns.length = 0
  const app = createSSRApp(AdminInsights, props)
  app.config.warnHandler = (m) => warns.push(String(m))
  app.config.errorHandler = (e) => warns.push('THROW ' + (e && e.message))
  try {
    return await renderToString(app)
  } catch (e) {
    return 'THROW ' + (e && e.message)
  }
}

async function main() {
  const cases = [
    ['无目标', Object.assign({}, base, { familyToday: { today: '2026-09-16', kids: [], family_goal: null } }),
      ['全家共同目标', '还没有共同目标', '完成卡数（张）', '运动次数（次）', '签到天数（天）']],
    // 真实「没有目标」的形状：后端给的是 { goal: null, progress: null, by_kid: [] }（外层对象为真）
    ['无目标(真实形状)', Object.assign({}, base, { familyToday: { today: '2026-09-16', kids: [], family_goal: { goal: null, progress: null, by_kid: [] } } }),
      ['全家共同目标', '还没有共同目标', '完成卡数（张）']],
    ['进行中', Object.assign({}, base, { familyToday: { today: '2026-09-16', kids: [], family_goal: goal({}) } }),
      ['完成卡数 12/20 张', '全家还差 8 张', '每娃贡献：乐乐 7 · 弟弟 5', '关掉目标']],
    ['已达标', Object.assign({}, base, { familyToday: { today: '2026-09-16', kids: [], family_goal: goal({ goal: { status: 'reached', reached_at: '2026-09-18' }, progress: { value: 20, target: 20, remaining: 0 } }) } }),
      ['已达成本周目标，每人 +5 阳光', '（2026-09-18）', '完成卡数 20/20 张']],
    ['本周英语', Object.assign({}, base, { weekly: weeklyWithWords, familyToday: { today: '2026-09-16', kids: [], family_goal: null } }),
      ['本周英语', '这周练了 4 天，首轮正确率 78%', '这周还没练过英语；今天还没练']],
    ['本周英语(老后端没这字段)', Object.assign({}, base, { weekly: weeklyNoWords, familyToday: { today: '2026-09-16', kids: [], family_goal: null } }),
      ['全家共同目标']],
  ]
  for (const [name, props, need] of cases) {
    const html = await render(props)
    console.log('AdminInsights[' + name + ']：HTML ' + html.length + '，警告 ' + warns.length + ' 条')
    if (warns.length) console.log(warns.slice(0, 6).join('\n---\n'))
    for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
    console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
  }
}
main()
