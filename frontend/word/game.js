// 英语复习独立页（/word/）—— 小关制 + 发音 + 「收获式」结算。
//
// 阳光口径（2026-09-16 改）：**不看正确率**，改看「完成 + 进步」——
// 今天写过一个词 0.25 分、其中写对的再 0.25 分；错题不扣分；一天上限 10。
// 三种题型都推进「今天写了几个词」；正确率只给家长看，不给孩子当分数。
// 钱由后端按当天累计补差（口径在 backend/words.py），这一页只让孩子看见「练了多少、会了多少」。
//
// 发音（2026-09-16 新增）：家长端早就配好了 tts / tts_autoplay / tts_lang（见
// components/WordPractice.vue），/api/words/game/start 也一直在返回这三个值，这一页以前没用。
// 现在：认一认自动念、连一连点左边念、写完后各念一遍，默写时另有「🔊 听一听」当提示（比「看一眼」轻）。
// 拼写判分用 src/wordSpell.js；题型/小关规则用 src/wordGame.js（有单测）。
import { slotCells, assembleSpelling, typedOf } from '../src/wordSpell.js'
import {
  streakUpdate, planSession, buildOptions, buildMatchBoard, shuffleQueue, chunkLevels, levelEnds,
} from '../src/wordGame.js'

const $ = (id) => document.getElementById(id)

const KIND = { recognize: '先认一认', spell: '默写', match: '连一连' }

// 家长端可设的三个旋钮（开局时读一次；局中改了不生效，下一局才变）
const cfg = { matchSize: 5, matchBlocks: 3, tts: true, ttsAutoplay: false, ttsLang: 'en-GB', levelSize: 6 }

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
  // 默写：字母和光标都归我们自己管（平板上的输入框把光标钉在 0 位，
  // 依赖原生光标会出现「按顺序敲 good、显示成 doog」——见 v0.3.65 的输入层）
  letters: '',
  caret: 0,
  buf: '',
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
  phase: 'idle',       // idle | ask | feedback | level | sum
  busy: false,
  // 小关：把一局切成几小关，做完一关就给一次星星，不用等整局做完才看到「忙完了」
  levelEnds: [],
  levelIdx: 0,
  levelCount: 0,
  levelSpell: [],
  lvRight: 0,
  lvAnswered: 0,
  today: null,         // 结算时服务端回来的数字（今天写了几个 / 对几个）
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

/* ============================================================
   发音：优先走平板壳的原生桥（SunshineTts），退回浏览器 speechSynthesis
   —— 和 components/WordPractice.vue 同一套做法，家长端三个开关直接生效
   ============================================================ */
let utter = null
let ttsVoices = []
function ttsReady() { return typeof speechSynthesis !== 'undefined' }
function loadTtsVoices() {
  if (!ttsReady()) return []
  try { ttsVoices = speechSynthesis.getVoices() || [] } catch { ttsVoices = [] }
  return ttsVoices
}
function pickTtsVoice(lang) {
  const want = String(lang || 'en-GB').toLowerCase()
  const en = loadTtsVoices().filter((v) => String(v.lang || '').toLowerCase().startsWith('en'))
  if (!en.length) return null
  return en.find((v) => String(v.lang || '').toLowerCase() === want)
    || en.find((v) => String(v.lang || '').toLowerCase().startsWith(want.slice(0, 2)))
    || en[0]
}
function nativeTts() {
  try { return typeof SunshineTts !== 'undefined' && SunshineTts && typeof SunshineTts.speak === 'function' } catch { return false }
}
function stopSpeech() {
  utter = null
  try { if (nativeTts()) SunshineTts.stop() } catch { /* 没有原生桥就算了 */ }
  try { if (ttsReady()) speechSynthesis.cancel() } catch { /* 同上 */ }
}
function speak(text) {
  const t = String(text || '').trim()
  if (!cfg.tts || !t) return false
  const lang = cfg.ttsLang || 'en-GB'
  try { if (nativeTts()) { SunshineTts.speak(t, lang); return true } } catch { /* 落到浏览器 TTS */ }
  if (!ttsReady()) return false
  try {
    speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(t)
    const v = pickTtsVoice(lang)
    if (v) { u.voice = v; u.lang = v.lang || lang } else { u.lang = lang }
    u.rate = 0.85
    u.onerror = () => { if (utter === u) utter = null }
    u.onend = () => { if (utter === u) utter = null }
    utter = u
    speechSynthesis.speak(u)
    return true
  } catch { return false }
}

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
// 乐观更新：结算时会被服务端数字纠正；今天已经写过的词先记在 counted 里，不重复加。
// 写错的词也算「写过」（服务端就是这么算的），所以这里不看对错。
function bumpGoal(item) {
  const { goal, scored_words: n } = state.goal
  if (!goal || !item || state.counted.has(item.word_id)) return
  state.counted.add(item.word_id)
  const next = n + 1
  setGoal({ scored_words: next, goal_done: next >= goal })
}

/* ---------- 顶部进度 ---------- */
/* ---------- 顶部进度：倒着数「还剩几个词」 ---------- */
function setStat() {
  const total = state.steps.length
  const left = state.steps.slice(state.si).filter((s) => s.kind === 'spell').length
  const lv = Math.min(state.levelIdx + 1, state.levelCount || 1)
  $('stat').textContent = total ? `第 ${lv} 关 · 还剩 ${left} 个词` : ''
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
// 光标在第几个字母前（0..字母数）。输入框里只留字母，所以 selectionStart 就是字母序号。
function renderSlots(cls) {
  const item = state.item
  if (!item) return
  const cells = slotCells(item.word, state.letters, state.caret)
  $('slots').className = 'slots' + (cls ? ' ' + cls : '')
  $('slots').innerHTML = cells.map((c) => {
    const kind = c.kind === 'hyphen' ? 'fix' : c.kind
    const cur = c.cur && state.phase === 'ask' ? ' cur' : ''
    const ch = c.fill === ' ' ? '' : (c.fill || '')
    return `<i class="${kind}${cur}">${ch}</i>`
  }).join('')
}

/* 把输入框里的新字符并进来。
   为什么不用输入框自己的光标：**平板（Android WebView）会把插入点钉在最前面**，
   于是按顺序敲 g-o-o-d 会显示成 d-o-o-g。所以这里只把输入框当「按键来源」：
   每次读完立刻清空它，字符插到我们自己维护的 letters 上的 caret 处 —— 平台怎么插都不影响。 */
// 只收「要孩子敲的字符」：字母 + 撇号（弯撇号折成直的）。
// 这里的 letters 是**要敲的字符**，不是「字母」—— 撇号也在这条线上（v0.3.66 改）。
function insertLetters(chars) {
  for (const ch of typedOf(chars)) {
    if (state.caret < state.letters.length) {
      state.letters = state.letters.slice(0, state.caret) + ch + state.letters.slice(state.caret + 1)
    } else {
      state.letters += ch
    }
    state.caret += 1
  }
}

function backspaceLetter() {
  if (state.caret <= 0 || !state.letters.length) return
  state.letters = state.letters.slice(0, state.caret - 1) + state.letters.slice(state.caret)
  state.caret -= 1
}

// 两个字符串的最长公共前后缀之间就是「这次新敲进去的」
function diffInserted(prev, next) {
  const p = String(prev || ''), n = String(next || '')
  let a = 0
  while (a < p.length && a < n.length && p[a] === n[a]) a += 1
  let b = 0
  while (b < p.length - a && b < n.length - a && p[p.length - 1 - b] === n[n.length - 1 - b]) b += 1
  return n.slice(a, n.length - b)
}

function clearBuf() {
  state.buf = ''
  const el = $('input')
  el.value = ''
  try { el.setSelectionRange(0, 0) } catch { /* 老浏览器没有就算了 */ }
}

function syncFocus() {
  const on = document.activeElement === $('input')
  const w = $('slotwrap')
  if (w) w.classList.toggle('caret-off', !on)
  const t = $('tap-hint')
  if (t) t.hidden = on || state.phase !== 'ask' || !(state.step && state.step.kind === 'spell')
  renderSlots('')
}

function focusInput() {
  try { $('input').focus() } catch { /* 认/连一连的时候输入框是隐藏的，聚焦失败不影响 */ }
  clearBuf()
  syncFocus()
}

// 点某一格 → 光标移到那一格（这就是「改中间那个字母」不用退格删到那儿的原因）
function focusSlotAt(target) {
  let idx = 0
  for (const c of $('slots').querySelectorAll('i')) {
    if (c.classList.contains('space') || c.classList.contains('fix')) continue
    if (c === target) break
    idx += 1
  }
  state.caret = Math.max(0, Math.min(state.letters.length, idx))
  try { $('input').focus() } catch { /* 同上 */ }
  clearBuf()
  syncFocus()
}

function renderActions() {
  if (state.phase === 'ask' && state.step && state.step.kind === 'spell') {
    $('actions').innerHTML = '<button class="do" id="check" type="button">检查</button>' +
      '<button class="sec" id="hear" type="button">🔊 听一听</button>' +
      '<button class="sec" id="peek" type="button">忘了，看一眼</button>'
    $('check').onclick = check
    $('hear').onclick = () => speak(state.item && state.item.word)
    $('peek').onclick = peek
  } else {
    $('actions').innerHTML = ''
  }
}

function askSpell() {
  const item = state.item
  state.letters = ''
  state.caret = 0
  state.buf = ''
  state.retryNext = false
  state.phase = 'ask'
  $('feedback').innerHTML = ''
  $('cn').textContent = item.cn || ''
  $('hint').textContent = '按中文写出英文。字母和撇号要自己敲，空格和句号会自动补'
  renderActions()
  renderSlots('')
  focusInput()
}

/* ---------- 认（4 选 1）· 不给孩子打分 ---------- */
function askRecognize() {
  state.recDone = false
  state.recOpts = buildOptions(state.item, state.queue, 4)
  $('rec-word').textContent = state.item.word || ''
  $('rec-opts').innerHTML = state.recOpts
    .map((t, i) => `<button class="opt" type="button" data-i="${i}">${t}</button>`).join('')
  for (const b of $('rec-opts').querySelectorAll('.opt')) b.onclick = () => answerRecognize(b)
  $('rec-hear').onclick = () => speak(state.item && state.item.word)
  if (cfg.ttsAutoplay) speak(state.item.word)     // 认一认念出来不泄题（题面本来就是英文）
}

function answerRecognize(btn) {
  if (state.recDone) return
  state.recDone = true
  speak(state.item.word)                          // 对错都把音和形再对一次
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
    speak(el.textContent)                                  // 点英文那侧就念一遍
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
  state.letters = ''
  state.caret = 0
  state.buf = ''
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

/* ---------- 小关：做完一关就给一次星星，不用等整局做完 ---------- */
function showLevelDone() {
  const spellN = state.levelSpell[state.levelIdx] || 0
  const right = state.lvRight
  const stars = spellN === 0 ? 3 : (right >= spellN ? 3 : (right * 10 >= spellN * 7 ? 2 : 1))
  state.phase = 'level'
  $('lv-stars').textContent = '⭐'.repeat(stars) + '☆'.repeat(3 - stars)
  $('lv-title').textContent = `第 ${state.levelIdx + 1} 小关过完啦`
  $('lv-sub').textContent = spellN ? `这一关写了 ${spellN} 个词，对了 ${right} 个` : '这一关全配上了'
  $('card-quiz').hidden = true
  $('card-level').hidden = false
  setStat()
}

function advance() {
  const finished = state.si            // 刚做完的那一步
  state.si += 1
  if (state.levelEnds.includes(finished) && state.si < state.steps.length) return showLevelDone()
  nextStep()
}

function renderFeedback(right, typed) {
  const item = state.item
  renderSlots(right ? 'right' : 'wrong')
  renderStreak()
  speak(item.word)                                        // 对错都念一遍，把音记住
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
      state.letters = ''          // 「再写一次」就是把空的格子重写，不带着上一次的错字
      state.caret = 0
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
      state.lvAnswered += 1
      if (right) { state.right += 1; state.lvRight += 1 }
      state.streak = streakUpdate(state.streak, right)
      state.best = Math.max(state.best, state.streak)
      bumpGoal(item)                    // 写错也算「写过」（服务端就是这么算的）
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
  const text = assembleSpelling(state.item.word, state.letters)
  if (!typedOf(state.letters)) { $('hint').textContent = '先写一写'; focusInput(); return }
  hideErr()
  submit(text, state.retryNext)
}

function peek() {
  const item = state.item
  if (!item) return
  speak(item.word)                                    // 看一眼：顺便把音记住
  $('feedback').innerHTML = `<p class="fb no">看一眼：<b>${item.word}</b></p>` +
    '<div class="row"><button class="sec" id="peek-retry" type="button">再写一次</button>' +
    '<button class="sec" id="peek-skip" type="button">下一题</button></div>'
  $('peek-retry').onclick = () => {
    state.letters = ''           // 同上：看过答案之后从头写
    state.caret = 0
    $('feedback').innerHTML = ''
    state.phase = 'ask'
    renderActions()
    renderSlots('')
    focusInput()
  }
  $('peek-skip').onclick = () => {
    state.answered += 1                 // 跳过的算没对（分母就是这一局词数）
    state.lvAnswered += 1
    state.streak = streakUpdate(state.streak, false)
    advance()
  }
  $('actions').innerHTML = ''
}

/* ---------- 结算 ---------- */
/* ---------- 结算：说「收获」，不给孩子打分 ---------- */
function renderSumGoal() {
  const { scored_words: n, goal, goal_done } = state.goal
  if (!goal) { $('sum-goal').hidden = true; return }
  $('sum-goal').hidden = false
  $('sum-goal').classList.toggle('done', !!goal_done)
  $('sum-goal').textContent = goal_done
    ? `🎉 今天的目标达成了：写了 ${n} 个词（目标 ${goal}）`
    : `今天写了 ${n} 个词 · 目标 ${goal}`
}

// 收获清单：练了多少 / 会了多少 / 还有多少要再来一回。没有百分比、没有「错」字。
function renderSumList() {
  const t = state.today || {}
  const done = t.words_done != null ? Number(t.words_done) : state.answered
  const right = t.words_right != null ? Number(t.words_right) : state.right
  const again = Math.max(0, done - right)
  const rows = [['今天练了', `${done} 个词`], ['已经会写', `${right} 个`]]
  if (again > 0) rows.push(['还要再来一回', `${again} 个`])
  $('sum-list').innerHTML = rows
    .map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`).join('')
}

async function finish() {
  state.phase = 'sum'
  $('card-quiz').hidden = true
  $('card-level').hidden = true
  $('card-sum').hidden = false
  $('sum-note').hidden = true
  $('sum-goal').hidden = true
  $('progress').style.width = '100%'
  $('stat').textContent = ''
  state.today = null
  renderSumList()
  renderSumGoal()
  if (!state.sid) return
  try {
    const res = await api('/api/words/game/settle', 'POST', { session_id: state.sid })
    state.today = res.today || {}
    const t = state.today
    renderSumList()                                  // 用服务端的数字纠正（分母口径以服务端为准）
    const bits = []
    if ((t.granted || 0) > 0) bits.push(`阳光 +${t.granted}`)
    bits.push(`今天英语阳光 ${t.got || 0}/${t.limit || 10}`)
    if (state.best >= 3) bits.push(`最高连击 ${state.best} 🔥`)
    $('sum-note').textContent = bits.join(' · ')
    $('sum-note').hidden = false
    setGoal(t)
  } catch (e) {
    $('sum-note').textContent = '这次没记上成绩：' + e.message
    $('sum-note').hidden = false
  }
  renderSumGoal()
}

// 开局与「再练一遍」共用：重置这一轮的计数、把小关切开、从第一步开始
function beginRound() {
  state.si = 0
  state.right = 0
  state.answered = 0
  state.streak = 0
  state.best = 0
  state.blockNo = 0
  state.lvRight = 0
  state.lvAnswered = 0
  state.levelIdx = 0
  state.today = null
  const groups = chunkLevels(state.steps, cfg.levelSize)
  state.levelCount = groups.length
  state.levelSpell = groups.map((g) => g.filter((s) => s.kind === 'spell').length)
  state.levelEnds = levelEnds(state.steps.length, cfg.levelSize)
  $('card-sum').hidden = true
  $('card-level').hidden = true
  $('card-quiz').hidden = false
  nextStep()
}

function again() {
  state.round += 1
  state.queue = shuffleQueue(state.queue)          // ① 每次「再练一遍」也换顺序
  state.steps = planSession(state.queue, { matchSize: cfg.matchSize, matchBlocks: cfg.matchBlocks }).steps
  beginRound()
}

async function load() {
  $('card-loading').hidden = false
  $('card-quiz').hidden = true
  $('card-level').hidden = true
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
  // 发音三件套：家长端「英语单词」页已经能设、后端一直在发，这一页以前没用上
  cfg.tts = c.tts !== false
  cfg.ttsAutoplay = !!c.tts_autoplay
  cfg.ttsLang = c.tts_lang === 'en-US' ? 'en-US' : 'en-GB'
  cfg.levelSize = Number(c.level_size) > 0 ? Number(c.level_size) : 6   // 一小关几步（家长端「一关几步」3–10）
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
  state.round = 1
  state.steps = planSession(state.queue, { matchSize: cfg.matchSize, matchBlocks: cfg.matchBlocks }).steps
  beginRound()
}

$('input').addEventListener('focus', syncFocus)
$('input').addEventListener('blur', syncFocus)
$('slots').addEventListener('click', (e) => {
  const cell = e.target && e.target.closest ? e.target.closest('i') : null
  if (cell) return focusSlotAt(cell)
  focusInput()
})
// 退格：keydown 就拦下来（preventDefault 之后浏览器不会动输入框，也就不会再冒 input 事件）
$('input').addEventListener('keydown', (e) => {
  if (e.key !== 'Backspace') return
  if (state.phase !== 'ask' || !state.step || state.step.kind !== 'spell') return
  e.preventDefault()
  backspaceLetter()
  renderSlots('')
})
$('input').addEventListener('input', (e) => {
  if (state.phase !== 'ask' || !state.step || state.step.kind !== 'spell') return
  const el = e.target
  const raw = String(el.value || '')
  const type = String(e.inputType || '')
  if (type.indexOf('delete') === 0) {
    backspaceLetter()
  } else {
    insertLetters(typedOf(diffInserted(state.buf, raw)))
  }
  clearBuf()                       // 读完就清空：平台的插入位置从此与我们无关
  renderSlots('')
})
$('input').addEventListener('keyup', (e) => { if (e.key === 'Enter') check() })
document.addEventListener('selectionchange', () => {
  if (document.activeElement === $('input')) clearBuf()
})
$('lv-next').addEventListener('click', () => {
  state.levelIdx += 1
  state.lvRight = 0
  state.lvAnswered = 0
  $('card-level').hidden = true
  $('card-quiz').hidden = false
  nextStep()
})
$('again').addEventListener('click', again)
$('home').addEventListener('click', () => { stopSpeech(); location.href = '/' })
$('err-retry').addEventListener('click', load)
// 有些浏览器要等用户碰一下才肯发声；顺便把音色列表加载进来（Chrome 是异步给的）
document.addEventListener('pointerdown', () => { loadTtsVoices() }, { once: true })
if (ttsReady()) { try { speechSynthesis.onvoiceschanged = loadTtsVoices } catch { /* 不支持就算了 */ } }

load()
