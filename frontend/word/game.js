// 英语复习独立页（/word/）—— P3：题型按掌握度自动切（认 4 选 1 / 写 / 连一连）+ 每日目标环。
// 口径没变：只有「写」计分（分母 = 这一局词数），钱由后端按当天最好一轮补差；认/连一连不计分、不发钱。
// 拼写判分用 src/wordSpell.js（标点/空格自动带出，孩子只敲字母）；题型规则用 src/wordGame.js（有单测）。
import { slotCells, assembleSpelling, lettersOf } from '../src/wordSpell.js'
import { scoreOf, streakUpdate, planSession, buildOptions, buildMatchBoard, shuffleQueue } from '../src/wordGame.js'

const $ = (id) => document.getElementById(id)

const KIND = { recognize: '先认一认', spell: '默写', match: '连一连' }

// 家长端可设的三个旋钮（开局时读一次；局中改了不生效，下一局才变）
const cfg = { matchSize: 5, matchBlocks: 3 }

const state = {
  sid: '',
  queue: [],
  steps: [],
  si: 0,               // 第几步（一步 = 认一题 / 写一词 / 连一块板）
  round: 1,            // 第几轮（正式作答走 spell，轮内「再写一次」走 retry、不计分）
  right: 0,
  answered: 0,
  streak: 0,
  best: 0,
  step: null,
  item: null,
  typing: '',
  retryNext: false,
  board: null,
  pickL: null,
  pickR: null,
  matched: 0,
  blockNo: 0,
  recOpts: [],
  recDone: false,
  goal: { scored_words: 0, goal: 0, goal_done: false },
  counted: new Set(),  // 今天已经写过的词（开局时按 first_result 记下；目标环靠它判重）
  phase: 'idle',       // idle | ask | feedback | sum
  busy: false,
}

async function api(path, method = 'GET', body) {
  const res = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = null }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || ('HTTP ' + res.status)
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  return data
}

function showErr(title, msg) {
  $('err-title').textContent = title
  $('err-body').textContent = msg || ''
  $('err').hidden = false
}
function hideErr() { $('err').hidden = true }

/* ---------- 每日目标环（只展示，不发钱） ---------- */
function setGoal(next) {
  if (next) state.goal = { ...state.goal, ...next }
  const { scored_words: n, goal, goal_done } = state.goal
  if (!goal) { $('goal').hidden = true; return }
  $('goal').hidden = false
  $('goal').classList.toggle('done', !!goal_done)
  $('goal-text').textContent = goal_done ? `今天目标 ${n}/${goal} 达成` : `今天目标 ${n}/${goal}`
  $('goal-fill').style.width = Math.min(100, Math.round((n / goal) * 100)) + '%'
  $('goal-mark').textContent = goal_done ? '🎉' : ''
}
// 乐观更新：结算时会被服务端数字纠正；今天已经写过的词先记在 counted 里，不重复加
function bumpGoal(item) {
  const { goal, scored_words: n } = state.goal
  if (!goal || !item || state.counted.has(item.word_id)) return
  state.counted.add(item.word_id)
  const next = n + 1
  setGoal({ scored_words: next, goal_done: next >= goal })
}

/* ---------- 顶部进度 ---------- */
function setStat() {
  const total = state.steps.length
  const n = Math.min(state.si + 1, total)
  $('stat').textContent = total ? `第 ${n}/${total} 题 · 连击 ${state.streak}` : ''
  $('progress').style.width = total ? Math.round((state.si / total) * 100) + '%' : '0%'
}

function renderStreak() {
  $('streak').className = 'streak' + (state.streak >= 3 ? ' on' : '')
  $('streak').textContent = state.streak >= 3 ? `连击 ${state.streak} 🔥` : (state.streak ? `连击 ${state.streak}` : '')
}

function showPane(kind) {
  $('kind').textContent = KIND[kind] || ''
  $('q-recognize').hidden = kind !== 'recognize'
  $('q-match').hidden = kind !== 'match'
  $('q-spell').hidden = kind !== 'spell'
}

/* ---------- 写（拼写） ---------- */
function renderSlots(cls) {
  const item = state.item
  if (!item) return
  const cells = slotCells(item.word, state.typing)
  $('slots').className = 'slots' + (cls ? ' ' + cls : '')
  $('slots').innerHTML = cells.map((c) => {
    const kind = c.kind === 'hyphen' ? 'fix' : c.kind
    const cur = c.cur && state.phase === 'ask' ? ' cur' : ''
    const ch = c.fill === ' ' ? '' : (c.fill || '')
    return `<i class="${kind}${cur}">${ch}</i>`
  }).join('')
}

function focusInput() {
  const el = $('input')
  el.value = state.typing
  try { el.focus() } catch { /* 认/连一连的时候输入框是隐藏的，聚焦失败不影响 */ }
}

function renderActions() {
  if (state.phase === 'ask' && state.step && state.step.kind === 'spell') {
    $('actions').innerHTML = '<button class="do" id="check" type="button">检查</button>' +
      '<button class="sec" id="peek" type="button">忘了，看一眼</button>'
    $('check').onclick = check
    $('peek').onclick = peek
  } else {
    $('actions').innerHTML = ''
  }
}

function askSpell() {
  const item = state.item
  state.typing = ''
  state.retryNext = false
  state.phase = 'ask'
  $('feedback').innerHTML = ''
  $('cn').textContent = item.cn || ''
  $('hint').textContent = '按中文写出英文，只敲字母就行（空格和标点会自动补）'
  renderActions()
  renderSlots('')
  focusInput()
}

/* ---------- 认（4 选 1）· 不计分 ---------- */
function askRecognize() {
  state.recDone = false
  state.recOpts = buildOptions(state.item, state.queue, 4)
  $('rec-word').textContent = state.item.word || ''
  $('rec-opts').innerHTML = state.recOpts
    .map((t, i) => `<button class="opt" type="button" data-i="${i}">${t}</button>`).join('')
  for (const b of $('rec-opts').querySelectorAll('.opt')) b.onclick = () => answerRecognize(b)
}

function answerRecognize(btn) {
  if (state.recDone) return
  state.recDone = true
  const answer = state.item.cn || ''
  const right = state.recOpts[+btn.dataset.i] === answer
  btn.classList.add(right ? 'ok' : 'no')
  for (const b of $('rec-opts').querySelectorAll('.opt')) {
    if (state.recOpts[+b.dataset.i] === answer) b.classList.add('ok')   // 错了也把对的标出来，看一眼再写
    b.disabled = true
  }
  // 认对了快一点走，认错了多停一会儿让孩子看清
  window.setTimeout(() => {
    if (state.phase === 'ask' && state.step && state.step.kind === 'recognize') advance()
  }, right ? 700 : 1500)
}

/* ---------- 连一连（配对）· 不计分 ---------- */
function cellHtml(side) {
  return (c) => `<button class="cell" type="button" data-side="${side}" data-wid="${c.word_id}">${c.text}</button>`
}

function renderMatchStat() {
  const size = (state.step && state.step.items) ? state.step.items.length : 0
  $('m-stat').textContent = `配好 ${state.matched}/${size}`
}

function askMatch() {
  state.board = buildMatchBoard(state.step.items)
  state.pickL = null
  state.pickR = null
  state.matched = 0
  state.blockNo += 1
  $('m-block').textContent = `连一连 · 第 ${state.blockNo} 块`
  renderMatchStat()
  $('m-left').innerHTML = state.board.left.map(cellHtml('L')).join('')
  $('m-right').innerHTML = state.board.right.map(cellHtml('R')).join('')
  for (const el of $('q-match').querySelectorAll('.cell')) el.onclick = () => pickMatch(el)
}

function pickMatch(el) {
  if (el.classList.contains('done')) return
  if (el === state.pickL || el === state.pickR) {          // 再点一下取消选择
    el.classList.remove('pick')
    if (el === state.pickL) state.pickL = null
    if (el === state.pickR) state.pickR = null
    return
  }
  if (el.dataset.side === 'L') {
    if (state.pickL) state.pickL.classList.remove('pick')
    state.pickL = el
  } else {
    if (state.pickR) state.pickR.classList.remove('pick')
    state.pickR = el
  }
  el.classList.add('pick')
  if (!state.pickL || !state.pickR) return
  const a = state.pickL
  const b = state.pickR
  if (a.dataset.wid === b.dataset.wid) {
    a.classList.remove('pick')
    b.classList.remove('pick')
    a.classList.add('done')
    b.classList.add('done')
    state.pickL = null
    state.pickR = null
    state.matched += 1
    renderMatchStat()
    if (state.matched >= state.step.items.length) {
      window.setTimeout(() => {
        if (state.phase === 'ask' && state.step && state.step.kind === 'match') advance()
      }, 450)
    }
    return
  }
  // 配错：红一下弹回来，不扣分
  a.classList.add('bad')
  b.classList.add('bad')
  window.setTimeout(() => {
    a.classList.remove('bad')
    b.classList.remove('bad')
    if (state.pickL === a) { a.classList.remove('pick'); state.pickL = null }
    if (state.pickR === b) { b.classList.remove('pick'); state.pickR = null }
  }, 450)
}

/* ---------- 一步接一步 ---------- */
function nextStep() {
  state.step = state.steps[state.si] || null
  state.item = state.step && state.step.item ? state.step.item : null
  state.typing = ''
  state.retryNext = false
  state.phase = 'ask'
  $('feedback').innerHTML = ''
  renderStreak()
  if (!state.step) return finish()
  setStat()
  showPane(state.step.kind)
  if (state.step.kind === 'recognize') return askRecognize()
  if (state.step.kind === 'match') return askMatch()
  return askSpell()
}

function advance() {
  state.si += 1
  nextStep()
}

function renderFeedback(right, typed) {
  const item = state.item
  renderSlots(right ? 'right' : 'wrong')
  renderStreak()
  const head = right
    ? `<p class="fb ok">对了！</p><div class="big-en">${item.word}</div>`
    : `<p class="fb no">你写了 ${typed || '（空）'}</p><div class="big-en">${item.word}</div>` +
      `<div class="ipa">${item.ipa || ''}</div>`
  $('feedback').innerHTML = head +
    '<div class="row"><button class="do" id="next" type="button">下一题</button>' +
    (right ? '' : '<button class="sec" id="retry" type="button">再写一次</button>') + '</div>'
  $('next').onclick = advance
  if (!right) {
    $('retry').onclick = () => {
      state.retryNext = true
      state.phase = 'ask'
      renderActions()
      $('feedback').innerHTML = ''
      renderSlots('')
      focusInput()
    }
  }
}

async function submit(text, retry) {
  const item = state.item
  state.busy = true
  try {
    const payload = await api(`/api/words/session/${state.sid}/spell`, 'POST', {
      word_id: item.word_id, text, phase: retry ? 'retry' : 'spell', attempt_no: state.round,
    })
    const right = payload && payload.result === 'right'
    if (!retry) {                       // 「再写一次」不计分、也不算连击（那一次已经判过了）
      state.answered += 1
      if (right) state.right += 1
      state.streak = streakUpdate(state.streak, right)
      state.best = Math.max(state.best, state.streak)
      if (right) bumpGoal(item)
    }
    state.phase = 'feedback'
    renderFeedback(right, text)
    setStat()
    if (right) window.setTimeout(() => { if (state.phase === 'feedback') advance() }, 900)
  } catch (e) {
    state.phase = 'ask'
    showErr('提交失败', e.message)
    renderActions()
  } finally {
    state.busy = false
  }
}

function check() {
  if (state.busy || state.phase !== 'ask' || !state.item) return
  if (!state.step || state.step.kind !== 'spell') return
  const text = assembleSpelling(state.item.word, state.typing)
  if (!lettersOf(state.typing)) { $('hint').textContent = '先写一写'; focusInput(); return }
  hideErr()
  submit(text, state.retryNext)
}

function peek() {
  const item = state.item
  if (!item) return
  $('feedback').innerHTML = `<p class="fb no">看一眼：<b>${item.word}</b></p>` +
    '<div class="row"><button class="sec" id="peek-retry" type="button">再写一次</button>' +
    '<button class="sec" id="peek-skip" type="button">下一题</button></div>'
  $('peek-retry').onclick = () => {
    $('feedback').innerHTML = ''
    state.phase = 'ask'
    renderActions()
    focusInput()
  }
  $('peek-skip').onclick = () => {
    state.answered += 1                 // 跳过的算没对（分母就是这一局词数）
    state.streak = streakUpdate(state.streak, false)
    advance()
  }
  $('actions').innerHTML = ''
}

/* ---------- 结算 ---------- */
function renderSumGoal() {
  const { scored_words: n, goal, goal_done } = state.goal
  if (!goal) { $('sum-goal').hidden = true; return }
  $('sum-goal').hidden = false
  $('sum-goal').classList.toggle('done', !!goal_done)
  $('sum-goal').textContent = goal_done
    ? `🎉 今天的目标达成了：写了 ${n} 个词（目标 ${goal}）`
    : `今天写了 ${n} 个词 · 目标 ${goal}`
}

async function finish() {
  state.phase = 'sum'
  $('card-quiz').hidden = true
  $('card-sum').hidden = false
  $('sum-note').hidden = true
  $('sum-goal').hidden = true
  const size = state.queue.length || state.answered
  $('sum-pct').textContent = scoreOf(state.right, size) + '%'
  $('sum-sub').textContent = `这一轮答对 ${state.right}/${size} 题 · 最高连击 ${state.best}`
  $('progress').style.width = '100%'
  $('stat').textContent = ''
  if (!state.sid) return
  try {
    const res = await api('/api/words/game/settle', 'POST', { session_id: state.sid })
    const t = res.today || {}
    const rnd = res.round || {}
    const got = t.granted || 0
    const n = rnd.size || size
    const right = rnd.correct != null ? rnd.correct : state.right
    if (rnd.score != null) $('sum-pct').textContent = rnd.score + '%'
    $('sum-sub').textContent = `这一轮答对 ${right}/${n} 题 · 最高连击 ${state.best}`
    $('sum-note').textContent = (got > 0 ? `阳光 +${got} · ` : '') +
      `今天英语阳光 ${t.got || 0}/${t.limit || 10}（最好 ${t.best_score || 0} 分）`
    $('sum-note').hidden = false
    setGoal(t)
  } catch (e) {
    $('sum-note').textContent = '这次没记上成绩：' + e.message
    $('sum-note').hidden = false
  }
  renderSumGoal()
}

function again() {
  state.si = 0
  state.round += 1
  state.right = 0
  state.answered = 0
  state.streak = 0
  state.best = 0
  state.blockNo = 0
  state.queue = shuffleQueue(state.queue)          // ① 每次「再练一遍」也换顺序
  state.steps = planSession(state.queue, { matchSize: cfg.matchSize, matchBlocks: cfg.matchBlocks }).steps
  $('card-sum').hidden = true
  $('card-quiz').hidden = false
  nextStep()
}

async function load() {
  $('card-loading').hidden = false
  $('card-quiz').hidden = true
  $('card-sum').hidden = true
  $('goal').hidden = true
  hideErr()
  let today
  try {
    today = await api('/api/words/game/start', 'POST')
  } catch (e) {
    $('card-loading').hidden = true
    if (e.status === 401 || e.status === 403) return showErr('还没登录', '先用孩子的账号登录，再打开这一页')
    return showErr('加载失败', e.message)
  }
  $('card-loading').hidden = true
  if (today && today.enabled === false) return showErr('单词练习没开', '找家长在「英语单词」页把它打开')
  const c = (today && today.config) || {}
  cfg.matchSize = Number(c.match_size) > 0 ? Number(c.match_size) : 5
  cfg.matchBlocks = (c.match_blocks === undefined || c.match_blocks === null)
    ? 3                                                    // 老后端没这个键时按默认 3 块
    : (Number(c.match_blocks) || 0)
  setGoal(today && today.goal)
  const session = today && today.session
  const items = (session && session.items) || []
  if (!items.length) return showErr('今天没有要复习的词', '明天再来，或让家长加点新词')
  state.sid = session.id
  state.queue = items.filter((x) => x.state !== 'done')
  if (!state.queue.length) state.queue = items            // 今天已经全答对过：允许再练一遍
  // 今天已经写过的词先记下来：目标环的乐观更新靠它判重（结算时再按服务端数字对齐）
  state.counted = new Set(items.filter((x) => x.first_result).map((x) => x.word_id))
  state.queue = shuffleQueue(state.queue)          // ① 每次打开都换顺序（词序不固定）
  state.si = 0
  state.round = 1
  state.right = 0
  state.answered = 0
  state.streak = 0
  state.best = 0
  state.blockNo = 0
  state.steps = planSession(state.queue, { matchSize: cfg.matchSize, matchBlocks: cfg.matchBlocks }).steps
  $('card-quiz').hidden = false
  nextStep()
}

$('slots').addEventListener('click', focusInput)
$('input').addEventListener('input', (e) => {
  state.typing = e.target.value
  renderSlots('')
})
$('input').addEventListener('keyup', (e) => { if (e.key === 'Enter') check() })
$('again').addEventListener('click', again)
$('home').addEventListener('click', () => { location.href = '/' })
$('err-retry').addEventListener('click', load)

load()
