// 英语单词页（AdminWords.vue）SSR 渲染体检：P4-a 的「今天 / 本周」数字 + 两句人话 + 抓 Vue 警告/抛错。
// 这个页面以前没有 fixture（模板引用了没传的字段、或默认值里少个键，就会渲染出 undefined）。
// 反向对照：把 wordStats.today_sentence 去掉（或把 today 那几个 w-box 的 `wordStats.today &&` 去掉），重跑应报缺失/undefined。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import AdminWords from './src/components/AdminWords.vue'
import { useAdminWords, initAdminWords } from './src/adminWords.js'

const aw = useAdminWords()
initAdminWords({ getKid: () => 'k1', getTerms: () => [], toast: () => {} })

// 一局 20 词、对 14（70 分）：今天写了 20 词、目标 10（已达标）、阳光 2/10
const TODAY_DONE = {
  date: '2026-09-16', wrote: 20, rounds: 1, best_score: 70,
  sunshine: 2, sunshine_limit: 10, goal: 10, goal_done: true, finished: true,
}
const TODAY_NONE = {
  date: '2026-09-16', wrote: 0, rounds: 0, best_score: 0,
  sunshine: 0, sunshine_limit: 10, goal: 10, goal_done: false, finished: false,
}
const SESSION = {
  id: 'ws-1', study_date: '2026-09-16', state: 'completed',
  counts: { due: 3, new: 5, answered: 6, correct_first_try: 5 },
  items: [
    { word_id: 1, word: 'morning', cn: '早上好', source: 'due', state: 'done', first_result: 'right' },
    { word_id: 2, word: 'umbrella', cn: '雨伞', source: 'new', state: 'done', first_result: 'wrong' },
    { word_id: 3, word: 'dinner', cn: '晚饭', source: 'new', state: 'study', first_result: null },
  ],
}

const DAYS = [
  { date: '2026-09-10', label: '09-10', completed: 0, items: 0, correct_first_try: 0, rate: null },
  { date: '2026-09-11', label: '09-11', completed: 1, items: 20, correct_first_try: 14, rate: 70 },
  { date: '2026-09-12', label: '09-12', completed: 1, items: 10, correct_first_try: 9, rate: 90 },
  { date: '2026-09-13', label: '09-13', completed: 0, items: 0, correct_first_try: 0, rate: null },
  { date: '2026-09-14', label: '09-14', completed: 1, items: 18, correct_first_try: 15, rate: 83 },
  { date: '2026-09-15', label: '09-15', completed: 1, items: 10, correct_first_try: 7, rate: 70 },
  { date: '2026-09-16', label: '09-16', completed: 1, items: 20, correct_first_try: 14, rate: 70 },
]

const warns = []
async function render(stats, cfg) {
  Object.assign(aw.wordCfg, {
    enabled: true, new_per_day: 5, max_due: 10, game_size: 20,
    daily_goal: 10, match_size: 5, match_blocks: 3, level_size: 6, ...(cfg || {}),
  })
  aw.wordBooks.value = []
  aw.wordProblems.value = []
  aw.wordToday.value = { enabled: true, finished: true, backlog_due: 0, session: SESSION }
  aw.wordStats.value = stats
  warns.length = 0
  const app = createSSRApp(AdminWords, { kid: 'k1', kidName: '乐乐' })
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
    ['练过一局', {
      days: DAYS, completed_sessions: 4, first_try_rate: 78,
      today: TODAY_DONE, week: { days: 4, words: 58, rate: 78 },
      today_sentence: '今天写了 20 词（目标 10，已达标） · 最好一轮 70 分 · 阳光 2/10',
      week_sentence: '这周练了 4 天，首轮正确率 78%；今天写了 20/10 词（达标）',
      today_source: '这批词来自：五年级上 Unit 1（20 个） · 新词：五年级上 Unit 1',
    }, {}, ['今天写了', '20/10', '最好一轮', '70 分', '今天阳光', '2/10',
             '今天写了 20 词（目标 10，已达标）', '这周练了 4 天，首轮正确率 78%',
             '这批词来自：五年级上 Unit 1（20 个）']],
    ['今天还没练', {
      days: DAYS.map((d) => (d.date === '2026-09-16' ? { ...d, completed: 0, items: 0, correct_first_try: 0, rate: null } : d)),
      completed_sessions: 3, first_try_rate: 78,
      today: TODAY_NONE, week: { days: 3, words: 38, rate: 78 },
      today_sentence: '今天还没练',
      week_sentence: '这周练了 3 天，首轮正确率 78%；今天还没练',
    }, {}, ['今天还没练', '这周练了 3 天，首轮正确率 78%']],
    ['英语关掉', {
      days: DAYS, completed_sessions: 4, first_try_rate: 78, today: TODAY_NONE,
      week: { days: 4, words: 58, rate: 78 },
      today_sentence: '英语单词没开', week_sentence: '英语单词没开',
    }, { enabled: false }, ['英语单词没开']],
    // 接口还没回来：页面只拿到空对象，也不许渲染出 undefined
    ['接口没回来', {}, {}, ['今天写了', '最好一轮', '近 7 日']],
  ]
  for (const [name, stats, cfg, need] of cases) {
    const html = await render(stats, cfg)
    console.log('AdminWords[' + name + ']：HTML ' + html.length + '，警告 ' + warns.length + ' 条')
    if (warns.length) console.log(warns.slice(0, 6).join('\n---\n'))
    for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
    console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
  }
}
main()
