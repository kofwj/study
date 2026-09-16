// 英语复习独立页（/word/）—— P1：能玩、能记录（SRS 照常推进），**先不发阳光、不写签到**（那是 P2）。
// 关键约定：拼写判分用 src/wordSpell.js（标点/空格自动带出，孩子只敲字母）—— 与 App 里那套同一份逻辑，别再抄一遍。
import { slotCells, assembleSpelling, lettersOf } from '../src/wordSpell.js'
import { scoreOf, streakUpdate } from '../src/wordGame.js'

const $ = (id) => document.getElementById(id)

const state = {
  sid: '',
  queue: [],
  idx: 0,
  attempt: 2,          // 第几轮（第 1 轮 = spell，之后 = retry）
  right: 0,
  answered: 0,
  streak: 0,
  best: 0,
  item: null,
  typing: '',
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

function setStat() {
  const total = state.queue.length
  const n = Math.min(state.idx + 1, total)
  $('stat').textContent = total ? `第 ${n}/${total} 题 · 连击 ${state.streak}` : ''
  $('progress').style.width = total ? Math.round((state.idx / total) * 100) + '%' : '0%'
}

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
  el.focus()
}

function renderActions() {
  if (state.phase === 'ask') {
    $('actions').innerHTML = '<button class="do" id="check" type="button">检查</button>' +
      '<button class="sec" id="peek" type="button">忘了，看一眼</button>'
    $('check').onclick = check
    $('peek').onclick = peek
  } else if (state.phase === 'feedback') {
    $('actions').innerHTML = ''
  } else {
    $('actions').innerHTML = ''
  }
}

function ask() {
  state.item = state.queue[state.idx] || null
  state.typing = ''
  state.phase = state.item ? 'ask' : 'sum'
  $('feedback').innerHTML = ''
  $('streak').className = 'streak' + (state.streak >= 3 ? ' on' : '')
  $('streak').textContent = state.streak >= 3 ? `连击 ${state.streak} 🔥` : (state.streak ? `连击 ${state.streak}` : '')
  if (!state.item) return finish()
  $('card-quiz').hidden = false
  $('cn').textContent = state.item.cn || ''
  $('hint').textContent = '按中文写出英文，只敲字母就行（空格和标点会自动补）'
  setStat()
  renderSlots('')
  renderActions()
  focusInput()
}

function renderFeedback(right, typed) {
  const item = state.item
  const cls = right ? 'right' : 'wrong'
  renderSlots(cls)
  $('streak').className = 'streak' + (state.streak >= 3 ? ' on' : '')
  $('streak').textContent = state.streak >= 3 ? `连击 ${state.streak} 🔥` : (state.streak ? `连击 ${state.streak}` : '')
  const head = right
    ? `<p class="fb ok">对了！</p><div class="big-en">${item.word}</div>`
    : `<p class="fb no">你写了 ${typed || '（空）'}</p><div class="big-en">${item.word}</div>` +
      `<div class="ipa">${item.ipa || ''}</div>`
  $('feedback').innerHTML = head +
    '<div class="row"><button class="do" id="next" type="button">下一题</button>' +
    (right ? '' : '<button class="sec" id="retry" type="button">再写一次</button>') + '</div>'
  $('next').onclick = () => { state.idx += 1; ask() }
  if (!right) $('retry').onclick = () => { state.phase = 'ask'; renderActions(); $('feedback').innerHTML = ''; renderSlots(''); focusInput() }
}

async function submit(text) {
  const item = state.item
  state.busy = true
  try {
    const payload = await api(`/api/words/session/${state.sid}/spell`, 'POST', {
      word_id: item.word_id, text, phase: state.attempt > 1 ? 'retry' : 'spell', attempt_no: state.attempt,
    })
    const right = payload && payload.result === 'right'
    state.answered += 1
    if (right) state.right += 1
    state.streak = streakUpdate(state.streak, right)
    state.best = Math.max(state.best, state.streak)
    state.phase = 'feedback'
    renderFeedback(right, text)
    setStat()
    if (right) window.setTimeout(() => { if (state.phase === 'feedback') { state.idx += 1; ask() } }, 900)
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
  const text = assembleSpelling(state.item.word, state.typing)
  if (!lettersOf(state.typing)) { $('hint').textContent = '先写一写'; focusInput(); return }
  hideErr()
  submit(text)
}

function peek() {
  const item = state.item
  if (!item) return
  $('feedback').innerHTML = `<p class="fb no">看一眼：<b>${item.word}</b></p>` +
    '<div class="row"><button class="sec" id="retry" type="button">再写一次</button>' +
    '<button class="sec" id="skip" type="button">下一题</button></div>'
  $('retry').onclick = () => { $('feedback').innerHTML = ''; focusInput() }
  $('skip').onclick = () => {
    state.answered += 1
    state.streak = streakUpdate(state.streak, false)
    state.idx += 1
    ask()
  }
  $('actions').innerHTML = ''
}

async function finish() {
  state.phase = 'sum'
  $('card-quiz').hidden = true
  $('card-sum').hidden = false
  const pct = scoreOf(state.right, state.answered)
  $('sum-pct').textContent = pct + '%'
  $('sum-sub').textContent = `这一轮答对 ${state.right}/${state.answered} 题 · 最高连击 ${state.best}`
  $('progress').style.width = '100%'
  $('stat').textContent = ''
  if (state.sid) { try { await api(`/api/words/session/${state.sid}/complete`, 'POST') } catch { /* 结算失败不影响这一轮的成绩展示 */ } }
}

function again() {
  state.idx = 0
  state.attempt += 1
  state.right = 0
  state.answered = 0
  state.streak = 0
  state.best = 0
  $('card-sum').hidden = true
  ask()
}

async function load() {
  $('card-loading').hidden = false
  $('card-quiz').hidden = true
  $('card-sum').hidden = true
  hideErr()
  let today
  try {
    today = await api('/api/words/today')
    if (!today.session || !(today.session.items || []).length) {
      today = await api('/api/words/session/start', 'POST')
    }
  } catch (e) {
    $('card-loading').hidden = true
    if (e.status === 401 || e.status === 403) return showErr('还没登录', '先用孩子的账号登录，再打开这一页')
    return showErr('加载失败', e.message)
  }
  $('card-loading').hidden = true
  if (today && today.enabled === false) return showErr('单词练习没开', '找家长在「英语单词」页把它打开')
  const session = today && today.session
  const items = (session && session.items) || []
  if (!items.length) return showErr('今天没有要复习的词', '明天再来，或让家长加点新词')
  state.sid = session.id
  state.queue = items.filter((x) => x.state !== 'done')
  if (!state.queue.length) state.queue = items          // 今天已经全答对过：允许再练一遍
  state.idx = 0
  state.right = 0
  state.answered = 0
  state.streak = 0
  state.best = 0
  $('card-quiz').hidden = false
  ask()
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
