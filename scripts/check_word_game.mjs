#!/usr/bin/env node
// 英语复习页（/word/）的规则回归：阳光档位 + 正确率 + 连击 + 题型编排 + 小关切分，逐条断言。
// 阳光口径（2026-09-16 改）：**不看正确率**，改看「完成 + 进步」——
// 今天写过一个词 0.25、其中写对的再 0.25；错题不扣分；一天上限 10。
// 例：20 词全对 = 10；20 词做完全错 = 5；10 词全对 = 5。
// 题型（P3）：认 4 选 1 → 写；熟词先过一遍「连一连」。三种题型都推进「今天写了几个词」。
// 用法：node scripts/check_word_game.mjs
import {
  scoreOf, sunshineForProgress, streakUpdate,
  questionPlan, buildOptions, matchGroups, buildMatchBoard, planSession, entryCardText, shuffleQueue,
  chunkLevels, levelEnds,
} from '../frontend/src/wordGame.js'

let bad = 0
let n = 0
const ok = (cond, msg) => { n++; if (!cond) { console.log('  ' + msg); bad++ } }
// 固定随机源，断言才能复现
function seeded(seed) {
  let s = seed >>> 0
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 }
}

/* ---------- 阳光档位（完成 + 进步）/ 正确率 / 连击 ---------- */
const progCases = [
  [0, 0, 0], [1, 0, 0], [2, 0, 0], [4, 0, 1], [2, 2, 1],
  [10, 0, 2], [10, 10, 5], [20, 0, 5], [20, 10, 7], [20, 14, 8], [20, 20, 10],
  [100, 100, 10],                  // 超范围按满分
  ['20', '14', 8],                 // 字符串也能算
  [3, 99, 1],                      // 写对的不会多于写过的
  [null, null, 0], [NaN, NaN, 0], [-5, -5, 0], [undefined, undefined, 0],
]
for (const [d, r2, want] of progCases) {
  n++
  const got = sunshineForProgress(d, r2)
  if (got !== want) { console.log(`  阳光档位不符：写了${d}/对${r2} → ${got}（应为 ${want}）`); bad++ }
}
const scoreCases = [[0, 0, 0], [1, 1, 100], [17, 20, 85], [1, 3, 33], [2, 3, 67]]
for (const [right, total, want] of scoreCases) {
  n++
  const got = scoreOf(right, total)
  if (got !== want) { console.log(`  正确率不符：${right}/${total} → ${got}（应为 ${want}）`); bad++ }
}
const streakCases = [[0, true, 1], [3, true, 4], [5, false, 0], [0, false, 0]]
for (const [now, right, want] of streakCases) {
  n++
  const got = streakUpdate(now, right)
  if (got !== want) { console.log(`  连击不符：${now}+${right ? '对' : '错'} → ${got}（应为 ${want}）`); bad++ }
}

/* ---------- 题型判定（questionPlan） ---------- */
const P = (o) => ({ first_seen_at: '2026-09-01T08:00:00', interval_idx: 0, streak_right: 0, wrong_count: 0, last_result: '', ...o })
const planCases = [
  [{ word_id: 1, cn: '雨伞' }, undefined, 'recognize', '没带 progress 的新词 → 先认一认'],
  [{ word_id: 1, cn: '雨伞', progress: { first_seen_at: '', interval_idx: 0, streak_right: 0, wrong_count: 0, last_result: '' } }, undefined, 'recognize', '从没见过 → 先认一认'],
  [{ word_id: 2, cn: '雨伞', progress: P() }, undefined, 'plain', '见过、没大错 → 直接写'],
  [{ word_id: 3, cn: '雨伞', progress: P({ wrong_count: 2 }) }, undefined, 'recognize', '错了 2 次 → 再认一认'],
  [{ word_id: 4, cn: '雨伞', progress: P({ last_result: 'wrong' }) }, undefined, 'recognize', '上次写错 → 再认一认'],
  [{ word_id: 5, cn: '雨伞', progress: P({ interval_idx: 2, streak_right: 2 }) }, undefined, 'match', '熟词 → 先连一连'],
  [{ word_id: 6, cn: '雨伞', progress: P({ interval_idx: 4, streak_right: 5 }) }, undefined, 'match', '很熟 → 先连一连'],
  [{ word_id: 7, cn: '雨伞', progress: P({ interval_idx: 3, streak_right: 3, last_result: 'wrong' }) }, undefined, 'recognize', '熟但上次写错 → 先认一认（老错优先）'],
  [{ word_id: 8, cn: '雨伞', progress: P({ interval_idx: 2, streak_right: 1 }) }, undefined, 'plain', '阶梯到了但连对不够 → 直接写'],
  [{ word_id: 9, cn: '雨伞' }, P({ interval_idx: 2, streak_right: 2 }), 'match', '第二个参数（progress）优先'],
  [null, undefined, 'recognize', 'null 词不炸'],
]
for (const [item, prog, want, why] of planCases) {
  n++
  const got = questionPlan(item, prog)
  if (got !== want) { console.log(`  题型不符（${why}）：${got}（应为 ${want}）`); bad++ }
}
ok(questionPlan({ word_id: 10, cn: '雨伞', progress: P({ wrong_count: '3' }) }) === 'recognize', 'wrong_count 是字符串也按 3 算')
ok(questionPlan({ word_id: 11, cn: '雨伞', progress: P({ interval_idx: '2', streak_right: '2' }) }) === 'match', 'interval/streak 是字符串也认得熟词')

/* ---------- 认题选项（buildOptions） ---------- */
const pool = [
  { word_id: 1, cn: '雨伞' }, { word_id: 2, cn: '电影院' }, { word_id: 3, cn: '早饭' },
  { word_id: 4, cn: '图书馆' }, { word_id: 5, cn: '电影院' }, { word_id: 6, cn: '晚饭' },
]
const item1 = { word_id: 1, word: 'umbrella', cn: '雨伞' }
const o1 = buildOptions(item1, pool, 4, seeded(7))
ok(o1.length === 4, `选项应为 4 个，实际 ${o1.length}`)
ok(o1.includes('雨伞'), '选项里必须有正确答案')
ok(new Set(o1).size === o1.length, '选项不能有重复')
const oBig = buildOptions(item1, [...pool, { word_id: 11, cn: '早上好' }, { word_id: 12, cn: '下午' }], 4, seeded(9))
ok(oBig.length === 4 && oBig.filter((x) => x === '雨伞').length === 1, '池子够时仍是 4 个、答案只出现一次')
const oSelf = buildOptions(item1, [item1, { word_id: 2, cn: '电影院' }], 4, seeded(3))
ok(oSelf.length === 4, '池子不够也要凑满 4 个')
ok(oSelf.filter((x) => x === '雨伞').length === 1, '自己不能当干扰项')
ok(oSelf.filter((x) => x === '—').length === 2, '不够的用「—」补齐，不崩')
const oStr = buildOptions(item1, ['电影院', '早饭', item1, null, ''], 3, seeded(5))
ok(oStr.length === 3 && oStr.includes('雨伞'), '池子里混着字符串/null/空也能用')
const oNo = buildOptions({ word_id: 99, cn: '' }, [], 4, seeded(1))
ok(oNo.length === 4 && oNo.filter((x) => x === '—').length === 3, '答案为空也不崩')

/* ---------- 配对分组（matchGroups） ---------- */
const hot = (id) => ({ word_id: id, word: 'w' + id, cn: 'cn' + id, progress: P({ interval_idx: 3, streak_right: 3 }) })
const cold = (id) => ({ word_id: id, word: 'w' + id, cn: 'cn' + id, progress: { first_seen_at: '', interval_idx: 0, streak_right: 0, wrong_count: 0, last_result: '' } })
const twentyHot = Array.from({ length: 20 }, (_, i) => hot(i + 1))
const g3 = matchGroups(twentyHot, 5, 3)
ok(g3.length === 3, `20 熟词 + 一块 5 + 最多 3 块 → 应为 3 块，实际 ${g3.length}`)
ok(g3.every((g) => g.length === 5), '每块都是 5 个词')
ok(new Set(g3.flat().map((x) => x.word_id)).size === 15, '一个词只上一次板，最多 15 个词')
ok(matchGroups(twentyHot, 4, 3).every((g) => g.length === 4), '一块 4 词（家长可设 3–6）')
ok(matchGroups(twentyHot, 5, 0).length === 0, '块数 0 = 不玩连一连')
ok(matchGroups(twentyHot, 5, -1).length === 0, '块数负数也不玩')
ok(matchGroups(twentyHot, 5, 1).length === 1, '块数 1 = 只连一块')
ok(matchGroups(Array.from({ length: 4 }, (_, i) => hot(i + 1)), 5, 3).length === 0, '只有 4 个熟词凑不满一块 → 0 块')
ok(matchGroups([...Array.from({ length: 4 }, (_, i) => hot(i + 1)), cold(9)], 5, 3).length === 0, '新词不进连线板')
const dupCn = [hot(1), { ...hot(2), cn: 'cn1' }, hot(3), hot(4), hot(5), hot(6)]
ok(matchGroups(dupCn, 5, 3).length === 1, '中文重复的先丢掉，凑不满一块就不开板')
ok(matchGroups([], 5, 3).length === 0, '空数组返回空')
ok(matchGroups(undefined, 5, 3).length === 0, 'undefined 不炸')

/* ---------- 连线板（buildMatchBoard） ---------- */
const board = buildMatchBoard(g3[0], seeded(11))
ok(board.left.length === 5 && board.right.length === 5, '两列都是 5 个格子')
ok(board.left.every((c, i) => c.word_id === g3[0][i].word_id && c.text === g3[0][i].word), '左列是英文原文顺序')
const rightIds = board.right.map((c) => c.word_id).sort((a, b) => a - b)
ok(rightIds.join(',') === board.left.map((c) => c.word_id).sort((a, b) => a - b).join(','), '右列是同一批词（打乱）')
ok(board.right.every((c) => {
  const src = g3[0].find((x) => x.word_id === c.word_id)
  return src && c.text === src.cn
}), '右列的每个中文都跟着自己的 word_id')
const board2 = buildMatchBoard(g3[0], seeded(11))
ok(board2.right.map((c) => c.word_id).join(',') === board.right.map((c) => c.word_id).join(','), '同一个随机源结果可复现')
ok(buildMatchBoard([], seeded(1)).left.length === 0, '空板块不炸')

/* ---------- 整局编排（planSession） ---------- */
const mixed = [...Array.from({ length: 10 }, (_, i) => hot(i + 1)), ...Array.from({ length: 10 }, (_, i) => cold(i + 101))]
const plan = planSession(mixed, { matchSize: 5, matchBlocks: 3 })
const count = (k) => plan.steps.filter((s) => s.kind === k).length
ok(count('match') === 2, `10 熟词 + 一块 5 → 2 块，实际 ${count('match')}`)
ok(count('spell') === 20, `每个词都要写：20 个 spell 步，实际 ${count('spell')}`)
ok(count('recognize') === 10, `10 个新词先认，实际 ${count('recognize')}`)
const spellIds = plan.steps.filter((s) => s.kind === 'spell').map((s) => s.item.word_id)
ok(new Set(spellIds).size === 20 && spellIds.length === 20, '每个词恰好写一次')
ok(plan.steps[0].kind === 'match' && plan.steps[1].kind === 'match', '连一连排在整局最前面')
const inBlock = new Set(plan.blocks.flat().map((x) => x.word_id))
const recIds = plan.steps.filter((s) => s.kind === 'recognize').map((s) => s.item.word_id)
ok(recIds.every((id) => !inBlock.has(id)), '进了连线板的词不再出认题')

// 认的上限：一局里最多出现在前一半的词上
const allNew = Array.from({ length: 20 }, (_, i) => cold(i + 1))
const planNew = planSession(allNew, { matchSize: 5, matchBlocks: 3 })
ok(planNew.steps.filter((s) => s.kind === 'recognize').length === 10, '20 个新词 → 最多 10 题认（前一半）')
const recOrder = planNew.steps.filter((s) => s.kind === 'recognize').map((s) => s.item.word_id)
ok(recOrder.join(',') === Array.from({ length: 10 }, (_, i) => i + 1).join(','), `认的是前 10 个词：${recOrder.join(',')}`)
const planSmall = planSession([cold(1), cold(2), cold(3), cold(4), cold(5)], { matchSize: 5, matchBlocks: 3 })
ok(planSmall.steps.filter((s) => s.kind === 'recognize').length === 3, '5 个新词 → 3 题认（ceil(5/2)）')
ok(planSmall.steps.filter((s) => s.kind === 'spell').length === 5, '5 个词 5 次写')
const planNoMatch = planSession(mixed, { matchSize: 5, matchBlocks: 0 })
ok(planNoMatch.steps.filter((s) => s.kind === 'match').length === 0, '块数 0 → 整局没有连一连')
ok(planNoMatch.steps.filter((s) => s.kind === 'spell').length === 20, '关掉连一连照样每个词都要写')
ok(planSession([], {}).steps.length === 0, '没有词 → 没有步骤')
ok(planSession(undefined, {}).steps.length === 0, 'undefined 不炸')
// 熟词凑不够一块时：直接进「写」，也不补认题（熟词本来就认得）
const fewHot = [...Array.from({ length: 3 }, (_, i) => hot(i + 1)), cold(10)]
const planFew = planSession(fewHot, { matchSize: 5, matchBlocks: 3 })
ok(planFew.steps.filter((s) => s.kind === 'match').length === 0, '凑不满一块 → 不开板')
ok(planFew.steps.filter((s) => s.kind === 'spell').length === 4, '凑不满也照样写 4 次')

/* ---------- 孩子端「今天」页的入口卡文案（entryCardText） ---------- */
const sessOf = (states, due) => ({
  counts: { due, new: 0, answered: states.filter((x) => x === 'done').length, correct_first_try: 0 },
  items: states.map((s, i) => ({ word_id: i + 1, state: s })),
})
const goalOf = (scored, target, done) => ({ scored_words: scored, goal: target, goal_done: done })
const c1 = entryCardText({ enabled: true, finished: false, backlog_due: 5, config: { game_size: 20 }, goal: goalOf(0, 10, false) })
ok(c1.ready === true && c1.title === '英语复习', '入口卡：开了就能玩')
ok(c1.detail === '今天 0/10 词 · 到期 5 个', `入口卡：有到期没练 → ${c1.detail}`)
ok(c1.hint === '这一局 20 词', `入口卡：还没开局 → ${c1.hint}`)
ok(c1.pct === 0 && c1.bar === '还差 10 个', `入口卡：进度条 → ${c1.pct}/${c1.bar}`)
const c2 = entryCardText({
  enabled: true, finished: false, backlog_due: 0, config: { game_size: 20 },
  session: sessOf(['done', 'done', 'done', 'study', 'study'], 2), goal: goalOf(2, 10, false),
})
ok(c2.detail === '今天 2/10 词 · 到期 2 个', `入口卡：练了一半 → ${c2.detail}`)
ok(c2.hint === '这一局 20 词 · 还有 2 个没练', `入口卡：还剩几个 → ${c2.hint}`)
ok(c2.pct === 20 && c2.bar === '还差 8 个', `入口卡：进度 20% → ${c2.pct}/${c2.bar}`)
const c3 = entryCardText({ enabled: true, finished: true, config: { game_size: 20 }, goal: goalOf(10, 10, true) })
ok(c3.bar === '达标了 🎉' && c3.pct === 100, `入口卡：达标 → ${c3.bar}/${c3.pct}`)
ok(c3.hint === '今天的目标达成了 🎉 · 再练一遍也行', `入口卡：达标提示 → ${c3.hint}`)
const c4 = entryCardText({ enabled: true, finished: true, backlog_due: 0, config: { game_size: 10 }, goal: goalOf(7, 0, false) })
ok(c4.detail === '今天写了 7 个词' && c4.pct === null && c4.bar === '', `入口卡：目标关掉 → ${c4.detail}/${c4.pct}`)
ok(c4.hint === '今天已经练完一局，再练一遍也行', `入口卡：练完没目标 → ${c4.hint}`)
const c5 = entryCardText({ enabled: true, finished: false, backlog_due: 0, session: null, goal: goalOf(0, 10, false) })
ok(c5.detail === '今天没有要复习的词', `入口卡：空态 → ${c5.detail}`)
ok(c5.hint === '明天再来，或让家长加点新词', `入口卡：空态提示 → ${c5.hint}`)
const c6 = entryCardText({ enabled: false })
ok(c6.ready === false && c6.detail === '今天没有要复习的词', '入口卡：英语关掉不炸')
ok(entryCardText(undefined).title === '英语复习' && entryCardText({}).pct === null, '入口卡：空 payload 不炸')
ok(entryCardText({ enabled: true, config: {}, goal: goalOf(3, 10, false), session: sessOf(['study'], 0) }).pct === 30, '入口卡：只给最小字段也能算进度')

/* ---------- 换顺序（shuffleQueue，P4-c ①） ---------- */
const q = [{ word_id: 1 }, { word_id: 2 }, { word_id: 3 }, { word_id: 4 }, { word_id: 5 }]
const s1 = shuffleQueue(q, seeded(11))
const s2 = shuffleQueue(q, seeded(11))
ok(s1.length === 5 && new Set(s1.map((x) => x.word_id)).size === 5, '换顺序：词一个不多一个不少')
ok(s1.map((x) => x.word_id).join(',') !== q.map((x) => x.word_id).join(','), '换顺序：顺序真的变了')
ok(s1.map((x) => x.word_id).join(',') === s2.map((x) => x.word_id).join(','), '换顺序：同一个随机源可复现')
ok(shuffleQueue([]).length === 0 && shuffleQueue().length === 0 && shuffleQueue(null).length === 0, '换顺序：空/非数组不炸')
ok(q.map((x) => x.word_id).join(',') === '1,2,3,4,5', '换顺序：不改原数组')
const many = shuffleQueue(Array.from({ length: 40 }, (_, i) => ({ word_id: i + 1 })))
ok(many.length === 40 && new Set(many.map((x) => x.word_id)).size === 40, '换顺序：40 个词也不丢不重')


/* ---------- 小关切分（chunkLevels / levelEnds） ---------- */
const L = (k) => Array.from({ length: k }, (_, i) => ({ kind: 'spell', item: { word_id: i + 1 } }))
const cl = chunkLevels(L(20), 6)
ok(cl.length === 4, `20 步 6 步一关 → 4 小关，实际 ${cl.length}`)
ok(cl.map((g) => g.length).join(',') === '6,6,6,2', `最后一关可以不满：${cl.map((g) => g.length).join(',')}`)
ok(chunkLevels(L(18), 6).length === 3, '正好整除 → 3 关，不凭空多一关')
ok(chunkLevels(L(20), 0).length === 4, '每关步数传 0 → 按默认 6 算，不炸')
ok(chunkLevels(L(5), 6).length === 1, '不足一关 → 1 关')
ok(chunkLevels([], 6).length === 0 && chunkLevels(undefined, 6).length === 0, '空/undefined 不炸')
ok(chunkLevels(L(20), 6).flat().length === 20, '切关不丢步、不多步')
ok(levelEnds(20, 6).join(',') === '5,11,17,19', `20 步 6 步一关 → 关尾 5,11,17,19，实际 ${levelEnds(20, 6).join(',')}`)
ok(levelEnds(18, 6).join(',') === '5,11,17', '正好整除 → 关尾 5,11,17')
ok(levelEnds(6, 6).join(',') === '5', '刚好一关 → 关尾 5，不重复补一个')
ok(levelEnds(7, 6).join(',') === '5,6', '第二关只有一步 → 也要补关尾')
ok(levelEnds(1, 6).join(',') === '0', '只有一步 → 关尾 0')
ok(levelEnds(0, 6).length === 0 && levelEnds(undefined, 6).length === 0, '没有步骤 → 没有关尾')
ok(levelEnds(20, 6).every((i) => i >= 0 && i < 20), '关尾下标都在这一局的范围内')
console.log(`英语复习页规则：${n} 条断言，失败 ${bad} 条`)
process.exit(bad ? 1 : 0)
