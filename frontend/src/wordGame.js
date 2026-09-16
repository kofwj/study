// 英语复习页（/word/）的纯逻辑：算分、连击、阳光档位、题型编排。
// 单独放一个模块是为了能跑 scripts/check_word_game.mjs 逐条断言（别再把规则写死在页面里）。
//
// 阳光口径（2026-09-16 定）：一局得分 = 本局正确率（整数百分比）；
// 当天按**最好成绩**结算一次额度：60 分以下 0，60–100 分线性到 10，向下取整。
// （补差额与幂等由后端负责，这里只给「这个分数对应多少阳光」。）
//
// 题型口径（P3）：认（4 选 1，不计分）→ 写（拼写，唯一计分）；熟词先过一遍「连一连」（不计分）。
// 每个词最后都要「写」，所以分数与分母口径完全没变。

export function scoreOf(right, total) {
  if (!total) return 0
  return Math.max(0, Math.min(100, Math.round((right / total) * 100)))
}

export function sunshineFor(score) {
  const s = Number(score)
  if (!Number.isFinite(s) || s < 60) return 0
  const capped = Math.min(100, s)
  return Math.max(0, Math.min(10, Math.floor(((capped - 60) / 40) * 10)))
}

export function streakUpdate(streak, right) {
  return right ? Number(streak || 0) + 1 : 0
}

// 关卡文案：孩子看得懂就行，别出现「失败」「扣分」这类词
export function verdictText(right) {
  return right ? '对了' : '再看一眼'
}

/* ============================================================
   题型：按掌握度自动切（阈值全部来自 word_progress，服务端随每题下发）
   ------------------------------------------------------------
   recognize 认（4 选 1）· plain 直接写 · match 先连一连再写
   ============================================================ */
export function questionPlan(item, progress) {
  const p = progress || (item && item.progress) || {}
  if (!p.first_seen_at) return 'recognize'                                  // 从没见过 → 先认一认
  if (Number(p.wrong_count || 0) >= 2 || p.last_result === 'wrong') return 'recognize'  // 老错 → 再认一认
  if (Number(p.interval_idx || 0) >= 2 && Number(p.streak_right || 0) >= 2) return 'match'  // 熟 → 先连一连
  return 'plain'
}

function shuffle(list, rand) {
  const r = typeof rand === 'function' ? rand : Math.random
  const out = [...list]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1))
    const t = out[i]; out[i] = out[j]; out[j] = t
  }
  return out
}

/* 认题的 4 个选项：必含正确答案；池子不够时补「—」，绝不崩。 */
export function buildOptions(item, pool, n = 4, rand = Math.random) {
  const want = Math.max(2, Number(n) || 4)
  const answer = item && item.cn != null ? String(item.cn) : ''
  const seen = new Set([answer])
  const others = []
  for (const x of pool || []) {
    const cn = x && typeof x === 'object' ? (x.cn == null ? '' : String(x.cn)) : String(x == null ? '' : x)
    if (!cn || seen.has(cn)) continue
    const wid = x && typeof x === 'object' ? x.word_id : null
    if (wid != null && item && item.word_id != null && wid === item.word_id) continue   // 别把自己当干扰项
    seen.add(cn)
    others.push(cn)
  }
  const picks = shuffle(others, rand).slice(0, want - 1)
  while (picks.length < want - 1) picks.push('—')
  return shuffle([answer, ...picks], rand)
}

/* 配对分组：只挑熟词，一块 size 个（默认 5），一局最多 maxBlocks 块（0 = 不玩）。
   凑不满一块就整块不要（不足就是 0 块，不拼半块板给孩子）；同一块里中文重复的丢掉（免得没法分辨）。 */
export function matchGroups(items, size = 5, maxBlocks = 3) {
  const s = Math.max(2, Number(size) || 5)
  const cap = Number(maxBlocks)
  if (!Number.isFinite(cap) || cap <= 0) return []
  const seenCn = new Set()
  const eligible = []
  for (const x of items || []) {
    if (!x || questionPlan(x) !== 'match') continue
    const cn = String(x.cn == null ? '' : x.cn)
    if (!cn || seenCn.has(cn)) continue
    seenCn.add(cn)
    eligible.push(x)
  }
  const out = []
  for (let i = 0; i + s <= eligible.length && out.length < cap; i += s) out.push(eligible.slice(i, i + s))
  return out
}

/* 一块板的左右两列：左边英文按原顺序，右边中文打乱（靠着 word_id 判对错，不靠文字）。 */
export function buildMatchBoard(group, rand = Math.random) {
  const words = (group || []).filter(Boolean)
  return {
    left: words.map((x) => ({ word_id: x.word_id, text: x.word || '' })),
    right: shuffle(words.map((x) => ({ word_id: x.word_id, text: x.cn || '' })), rand),
  }
}

/* 整局编排：先把熟词的「连一连」板放前面，然后逐词走「（认）→ 写」。
   - 认最多出现在前一半的词上（后面超过上限的强制直接写），免得前半天全是选择题
   - 进了连线板的词就不再出认题（刚连过，直接写） */
export function planSession(items, opts = {}) {
  const list = (items || []).filter(Boolean)
  const matchSize = Number(opts.matchSize) > 0 ? Number(opts.matchSize) : 5
  const matchBlocks = Number(opts.matchBlocks) > 0 ? Number(opts.matchBlocks) : 0
  const blocks = matchGroups(list, matchSize, matchBlocks)
  const inBlock = new Set()
  for (const g of blocks) for (const x of g) inBlock.add(x.word_id)
  let recognizeLeft = Math.ceil(list.length / 2)
  const steps = []
  for (const group of blocks) steps.push({ kind: 'match', items: group })
  for (const it of list) {
    if (!inBlock.has(it.word_id) && questionPlan(it) === 'recognize' && recognizeLeft > 0) {
      recognizeLeft -= 1
      steps.push({ kind: 'recognize', item: it })
    }
    steps.push({ kind: 'spell', item: it })
  }
  return { steps, blocks }
}

/* ============================================================
   孩子端「今天」页的入口卡文案（P4-b）
   ------------------------------------------------------------
   给 /word/ 一个正门：卡上就说清「今天写了几个 / 目标多少 / 这一局几个词」。
   纯函数放这里是为了能跑 scripts/check_word_game.mjs 断言（组件只渲染，不写文案）。
   today = GET /api/words/today 的 payload（enabled / finished / backlog_due / session / goal / config）
   ============================================================ */
export function entryCardText(today) {
  const t = today || {}
  const goal = t.goal || {}
  const scored = Number(goal.scored_words || 0)
  const target = Number(goal.goal || 0)
  const done = !!goal.goal_done
  const items = (t.session && t.session.items) || []
  const counts = (t.session && t.session.counts) || {}
  const due = Number(counts.due || t.backlog_due || 0)
  const size = Number((t.config && t.config.game_size) || items.length || 20)
  const left = items.filter((x) => x && x.state !== 'done').length
  // 「今天真没东西可练」：没组、没过期词、今天也没写过 → 说清楚，别显示 0/10 让人以为漏了
  const nothing = !items.length && !due && scored === 0

  let detail
  if (nothing) {
    detail = '今天没有要复习的词'
  } else if (target > 0) {
    detail = `今天 ${scored}/${target} 词`
    if (due > 0) detail += ` · 到期 ${due} 个`
  } else if (scored > 0) {
    detail = `今天写了 ${scored} 个词`
  } else {
    detail = `到期 ${due} 个`
  }

  const pct = target > 0 ? Math.max(0, Math.min(100, Math.round((scored / target) * 100))) : null
  const bar = target > 0 ? (done ? '达标了 🎉' : `还差 ${Math.max(0, target - scored)} 个`) : ''

  let hint
  if (nothing) hint = '明天再来，或让家长加点新词'
  else if (done) hint = '今天的目标达成了 🎉 · 再练一遍也行'
  else if (t.finished) hint = '今天已经练完一局，再练一遍也行'
  else if (left > 0) hint = `这一局 ${size} 词 · 还有 ${left} 个没练`
  else hint = `这一局 ${size} 词`

  return { title: '英语复习', detail, bar, pct, hint, ready: !!t.enabled }
}
