// 孩子端英语入口卡（WordGameCard.vue）SSR 渲染体检：P4-b 的四种状态 + 抓 Vue 警告/抛错。
// 文案来自 wordGame.js 的 entryCardText（纯函数，scripts/check_word_game.mjs 另外有 16 条断言），
// 这里只确认「模板真的把它渲染出来了、没有 undefined」。
// 反向对照：把模板里的 text.detail 改个名（少一个字段），重跑应报缺失/undefined。
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import WordGameCard from './src/components/WordGameCard.vue'

const goal = (scored, target, done) => ({ scored_words: scored, goal: target, goal_done: done })
const sess = (states, due) => ({
  counts: { due, new: 0, answered: states.filter((x) => x === 'done').length, correct_first_try: 0 },
  items: states.map((s, i) => ({ word_id: i + 1, state: s })),
})

const warns = []
async function render(today) {
  warns.length = 0
  const app = createSSRApp(WordGameCard, { today })
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
    ['有到期没练', { enabled: true, finished: false, backlog_due: 12, config: { game_size: 20 }, goal: goal(0, 10, false) },
      ['英语复习', '今天 0/10 词 · 到期 12 个', '这一局 20 词', '还差 10 个', '开一局']],
    ['练了一半', { enabled: true, finished: false, config: { game_size: 20 }, session: sess(['done', 'done', 'done', 'study', 'study'], 2), goal: goal(3, 10, false) },
      ['今天 3/10 词', '还有 2 个没练', '还差 7 个']],
    ['今天达标', { enabled: true, finished: true, config: { game_size: 20 }, goal: goal(10, 10, true) },
      ['今天 10/10 词', '达标了 🎉', '今天的目标达成了']],
    ['今天没词', { enabled: true, finished: false, backlog_due: 0, session: null, goal: goal(0, 10, false) },
      ['今天没有要复习的词', '明天再来']],
    ['英语关掉', { enabled: false }, ['英语复习']],
  ]
  for (const [name, today, need] of cases) {
    const html = await render(today)
    console.log('WordGameCard[' + name + ']：HTML ' + html.length + '，警告 ' + warns.length + ' 条')
    if (warns.length) console.log(warns.slice(0, 6).join('\n---\n'))
    for (const s of need) console.log('  ' + (html.includes(s) ? 'OK   ' : '缺失 ') + s)
    console.log('  渲染出 undefined 的次数 ' + (html.match(/undefined/g) || []).length)
  }
}
main()
