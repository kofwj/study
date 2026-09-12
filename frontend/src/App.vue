<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick, defineAsyncComponent } from 'vue'
import { api } from './api.js'
import { APP_LABEL, APP_REVISION } from './version.js'
// ponytail: 家长后台（1147 行）单独切 chunk，孩子端首屏不加载
const Admin = defineAsyncComponent(() => import('./Admin.vue'))
import { SUBJECT_ICONS as ICONS, rankIcon } from './icons.js'
import { mottoFor } from './dailyMottos.js'
import { Sun, Lock, Gift, Check, TrendingUp, Target, User, ShoppingCart, Medal, Map, CalendarDays, RefreshCw, PartyPopper, Sparkles, BookOpen, Flame, House, Landmark, Mail } from '@lucide/vue'

import { soundManager, playSound, playCompleteBeep, playCoinBeep } from './sounds.js'
import { getEncouragement, getCompanionMessage } from './encouragements.js'
import { SUBJECT_ORDER, n1, isGoPlay } from './format.js'
import { data, loading, err, me, authed, isAdmin, mustChangePin, pendingRecovery, rewards, achievements, boxes, recentLedger, ledgerSummary, reviewDue, activeTab, toast, showToast, newAchCount, achNew, companion, companionImage, companionTitle, companionPulse, companionEvolve, pendingLevelUp, pulseCompanion, showLevelCelebrate, triggerCompanionEvolve, wordToday, wordDueCard, wordNewCard, wordSun, sprites, capsule, spriteScene, spritesOpen, dutySprite, spImg, displayName, loadSprites, maybeShowMorning, applyCapsule, todayPenalty } from './store.js'

import SunshinePage from './components/SunshinePage.vue'
import TrendChart from './components/TrendChart.vue'
import AchievementsModal from './components/AchievementsModal.vue'
import ShopDrawer from './components/ShopDrawer.vue'
import LoginScreen from './components/LoginScreen.vue'
import DailyDialog from './components/DailyDialog.vue'
import CompanionDrawer from './components/CompanionDrawer.vue'
import WordPractice from './components/WordPractice.vue'
import SpritesBase from './components/SpritesBase.vue'
import CapsuleBox from './components/CapsuleBox.vue'
import BankPage from './components/BankPage.vue'
const topbarEl = ref(null)
const updateBarEl = ref(null)
const topbarHeight = ref(0)
const updateBarHeight = ref(0)
let topbarObserver = null
function syncTopbarHeight() {
  updateBarHeight.value = updateBarEl.value?.offsetHeight || 0
  topbarHeight.value = (topbarEl.value?.offsetHeight || 0) + updateBarHeight.value
}
function observeChrome() {
  topbarObserver?.disconnect()
  topbarObserver = null
  const els = [topbarEl.value, updateBarEl.value].filter(Boolean)
  if (!els.length) return
  syncTopbarHeight()
  if (typeof ResizeObserver !== 'undefined') {
    topbarObserver = new ResizeObserver(syncTopbarHeight)
    els.forEach(el => topbarObserver.observe(el))
  }
}
watch([topbarEl, updateBarEl], observeChrome)
onBeforeUnmount(() => {
  topbarObserver?.disconnect()
  boxTimers.forEach(clearTimeout)
})
const checkingTask = ref(null) // 记录正在打卡的任务 ID
const actionBusy = ref(false)
// 商店抽屉（components/ShopDrawer.vue）
const shopRef = ref(null)
function openShop() { shopRef.value?.open() }
// 成就墙弹窗（components/AchievementsModal.vue）
const achRef = ref(null)
function openAch() { achRef.value?.open() }
// 单词练习（components/WordPractice.vue）；共享状态 wordToday 与卡片派生在 store
const wordRef = ref(null)
function openWordLane(kind) {
  if (!guardCheckinOpen()) return
  wordRef.value?.open(kind)
}
// 时间胶囊（components/CapsuleBox.vue）+ 秘密基地（components/SpritesBase.vue）
const capsuleRef = ref(null)
const baseRef = ref(null)
function openCapsuleBox() { capsuleRef.value?.open() }
async function goOpenCapsule() {
  await goBase()
  capsuleRef.value?.open()
}
async function goBase() {
  activeTab.value = 'base'
  await loadSprites()
  maybeShowMorning()
}
function openSprites() { baseRef.value?.openSprites() }

const boxOpen = ref(false)
const boxResult = ref(null)
const boxPhase = ref('sun')
let boxTimers = []
function closeBoxMask() {
  if (boxResult.value && boxResult.value.kind === 'sprite' && (boxPhase.value === 'sun' || boxPhase.value === 'egg')) return
  boxOpen.value = false
  boxResult.value = null
  boxPhase.value = 'sun'
  boxTimers.forEach(clearTimeout)
  boxTimers = []
}
const rankMapOpen = ref(false)
const rankMap = ref(null)
const updateReady = ref(false)
// 伙伴抽屉（components/CompanionDrawer.vue）；庆祝层状态在 store
const drawerRef = ref(null)
const spriteButton = computed(() => {
  if (sprites.value.enabled) return `阳光图鉴 ${sprites.value.owned}/12`
  if (sprites.value.base_enabled) return '秘密基地'
  return ''
})
function openCompanion() { drawerRef.value?.open() }

// 趋势图弹窗（components/TrendChart.vue）
const chartRef = ref(null)

// 打卡飘出 +N 阳光
const floaters = ref([])
let floaterId = 0
function flyPlus(x, y, text) {
  const id = ++floaterId
  floaters.value.push({ id, text, x, y })
  setTimeout(() => {
    floaters.value = floaters.value.filter(f => f.id !== id)
  }, 1000)
}
function scoreClass(s) {
  if (s >= 95) return 'gold'
  if (s >= 90) return 'green'
  if (s >= 85) return 'blue'
  return 'gray'
}
function unitWeak(id) {
  const s = data.unit_scores[id]
  return s && s.score < (data.test_fail_score || 80)
}
function dueUnit(id) {
  return reviewDue.value.some(x => x.unit_id === id)
}
function dueCount(id) {
  return reviewDue.value.filter(x => x.unit_id === id).length
}
function fitnessBar(d) {
  const g = (data.fitness_goals || {})[d.id]
  if (!g) return null
  const last = (d.today_metrics && d.today_metrics[g.metric_id] != null)
    ? Number(d.today_metrics[g.metric_id])
    : (d.pb && d.pb[g.metric_id] != null ? Number(d.pb[g.metric_id]) : null)
  const cap = g.excellent || g.pass
  const pct = last == null ? 0 : Math.max(0, Math.min(100, Math.round(last / cap * 100)))
  const who = (g.grade ? g.grade + '年级' : '') + (g.gender || '')
  const lines = `${who} 达标 ${n1(g.pass)}${g.unit}` + (g.excellent != null ? ` · 优秀 ${n1(g.excellent)}${g.unit}` : '')
  let status = last == null ? '还没记' : (last >= (g.excellent || g.pass) ? '优秀了' : (last >= g.pass ? '达标了' : `还差 ${n1(g.pass - last)}${g.unit}`))
  return { ...g, last, pct, status, lines }
}

function afterKidLogin(r) {
  // 孩子登录后拉全量数据；家长登录进 Admin，不需要
  if (r && r.role !== 'parent') refresh()
}
const loginRef = ref(null)
async function exitAdmin() {
  // 家长会话不能直接当孩子会话渲染；退出后台后回到孩子登录页，避免角色状态残留导致白屏。
  await api.logout().catch(() => {})
  me.value = null
  isAdmin.value = false
  mustChangePin.value = false
  authed.value = false
  pendingRecovery.value = ''
  activeTab.value = '今日推荐'
}
async function openParent() {
  if (me.value && me.value.role === 'parent') {
    isAdmin.value = true
    return
  }
  await api.logout().catch(() => {})
  me.value = null
  authed.value = false
  await nextTick()
  loginRef.value?.show('parent')
}
async function doLogout() {
  await api.logout().catch(() => {})
  me.value = null
  isAdmin.value = false
  authed.value = false // 组件重挂载，自动回到孩子登录页
}

let refreshSeq = 0
async function refresh() {
  const seq = ++refreshSeq
  try {
    const [t, r, bx, rv, led, sum, ach, wd, sp, cap] = await Promise.all([
      api.tasks(), api.rewards(), api.boxes(),
      api.reviewDue().catch(() => []), api.ledger().catch(() => []),
      api.ledgerSummary(0).catch(() => null),
      api.achievements().catch(() => null),
      api.wordsToday().catch(() => null),
      api.sprites().catch(() => null),
      api.capsule().catch(() => null),
    ])

    if (seq !== refreshSeq) return // 已有更新的刷新在途，丢弃旧响应避免回滚新状态
    const prevId = data.level && data.level.level_id
    const prevEarned = data.level && (data.level.earned || 0)
    Object.assign(data, t)
    triggerCompanionEvolve(t.companion && t.companion.evolve ? t.companion : null)
    // 升级检测：等级变了且累计阳光增加了才庆祝（取消扣回导致的降级不庆祝）
    if (prevId && t.level.level_id !== prevId && t.level.earned >= prevEarned) {
      const payload = { icon: t.level.level_icon || '', name: t.level.level }
      if (companionEvolve.value) pendingLevelUp.value = payload
      else showLevelCelebrate(payload)
    }
    rewards.value = r
    boxes.value = bx
    const hidden = new Set(data.hidden_subjects || [])
    if (hidden.has(activeTab.value) || SIDEBAR_DAILY_ONLY.has(activeTab.value)) activeTab.value = '今日推荐'
    reviewDue.value = (rv || []).filter(x => !hidden.has(x.subject_id))
    recentLedger.value = led || []
    if (sum) ledgerSummary.value = sum

    if (Array.isArray(ach)) achievements.value = ach
    if (wd) wordToday.value = wd
    if (sp) {
      Object.assign(sprites.value, sp)
      sprites.value.loaded = true
      if (activeTab.value === 'base' || spritesOpen.value) maybeShowMorning()
    }
    if (cap) applyCapsule(cap)
    err.value = ''
  } catch (e) {
    if (seq !== refreshSeq) return
    if (e.status === 401) { me.value = null; authed.value = false }
    err.value = e.message
  } finally {
    if (seq === refreshSeq) loading.value = false
  }
}
const checkinClosed = computed(() => data.checkin_window && data.checkin_window.open === false)
function checkinClosedHint() {
  return (data.checkin_window && data.checkin_window.hint) || '每天 7:00 到 21:00 才能打卡'
}
function guardCheckinOpen() {
  if (!checkinClosed.value) return true
  showToast(checkinClosedHint())
  return false
}
async function checkin() {
  if (actionBusy.value) return
  if (!guardCheckinOpen()) return
  actionBusy.value = true
  try {
    const r = await api.checkin()
    pulseCompanion()
    playSound('complete') || playCompleteBeep()
    if (navigator.vibrate) navigator.vibrate([40, 20, 40])
    const encouragement = getEncouragement({ type: 'checkin' })
    showToast(encouragement + milestoneTxt(r.milestone))
    await refresh()
  } catch (e) { showToast(e.message) }
  finally { actionBusy.value = false }
}


async function toggleTaskWithAnim(task, event) {
  if (task.done || actionBusy.value) {
    return toggleTask(task, event)
  }
  if (!guardCheckinOpen()) return
  checkingTask.value = task.id
  setTimeout(async () => {
    await toggleTask(task, event)
    checkingTask.value = null
  }, 300)
}

async function toggleTask(task, event) {
  if (task.past) {
    showToast('这课已经学过了，不加阳光')
    return
  }
  if (task.locked) {
    showToast('还没学到这课，先把前面的学完')
    return
  }
  if (actionBusy.value) return
  if (!task.done && !guardCheckinOpen()) return
  actionBusy.value = true
  try {
    if (task.done) {
      await api.cancel(task.id)
      showToast(getEncouragement({ type: 'cancel' }))
      if (navigator.vibrate) navigator.vibrate(100)
    } else {
      const r = await api.complete(task.id)
      pulseCompanion()
      playSound('complete') || playCompleteBeep()
      if (navigator.vibrate) navigator.vibrate([50, 30, 50])
      setTimeout(() => { playSound('coin') || playCoinBeep() }, 200)
      if (event) flyPlus(event.clientX, event.clientY, `+${r.delta} 阳光`)
      const encouragement = getEncouragement({
        type: 'taskComplete',
        streak: data.streak,
        timeOfDay: true,
        reward: r.delta,
        isRecord: r.bonus > 0,
      })
      const companionMsg = getCompanionMessage(companion.value.stage, 'complete')
      const fullMsg = companionMsg 
        ? `${encouragement}！${companionMsg} +${r.delta} 阳光`
        : `${encouragement}！+${r.delta} 阳光`
      showToast(fullMsg + milestoneTxt(r.milestone))
    }
    await refresh()
  } catch (e) { 
    showToast(e.message)
    if (navigator.vibrate) navigator.vibrate(200)
  }
  finally { actionBusy.value = false }
}

async function openChart(task) {
  chartRef.value?.open(task)
}
// 每日打卡弹窗（components/DailyDialog.vue）：表单在组件里，业务动作（发阳光/庆祝/刷新）在这里
const dailyRef = ref(null)
function dailySunshineHint(task) {
  if (!task) return ''
  if (isGoPlay(task)) return `看「赢了几局」：填 1 或更多才给 +${task.sunshine || 5} 阳光。赢 0 局（空着也算 0）不给，输了几局不影响`
  return `打卡 +${task.sunshine || 5} 阳光`
}
async function openDaily(task) {
  if (task.done_today) return
  if (!guardCheckinOpen()) return
  dailyRef.value?.open(task)
}
async function submitDaily({ task, metrics, event }) {
  if (actionBusy.value) return
  actionBusy.value = true
  try {
    const r = await api.complete(task.id, metrics)
    pulseCompanion()
    playSound('complete') || playCompleteBeep()
    if (navigator.vibrate) navigator.vibrate([50, 30, 50])
    if (event && r.delta > 0) flyPlus(event.clientX, event.clientY, `+${r.delta} 阳光`)
    const encouragement = getEncouragement({
      type: 'taskComplete',
      reward: r.delta,
      isRecord: r.bonus > 0,
    })
    let msg
    if (r.bonus > 0) msg = `${encouragement}！破纪录了 +${r.delta} 阳光（+${r.bonus} 奖励）`
    else if (r.delta > 0) msg = `${encouragement}！+${r.delta} 阳光`
    else if (isGoPlay(task)) msg = '记下了。赢了 0 局，这次没有阳光'
    else msg = `${encouragement}！记下了`
    showToast(msg + milestoneTxt(r.milestone))
    dailyRef.value?.close()
    await refresh()
  } catch (e) { showToast(e.message) }
  finally { actionBusy.value = false }
}
async function cancelDaily(task) {
  if (actionBusy.value) return
  actionBusy.value = true
  try {
    await api.cancel(task.id)
    showToast('已取消，扣回阳光')
    await refresh()
  } catch (e) { showToast(e.message) }
  finally { actionBusy.value = false }
}

const milestoneTxt = (m) => (m && m.length) ? m.map(([d, b]) => ` · 连续 ${d} 天 +${b} 阳光`).join('') : ''
async function openBox() {
  if (boxes.value.avail <= 0) {
    const need = (boxes.value.earned + 1) * 3 - boxes.value.streak
    showToast(`再连续打卡 ${Math.max(1, need)} 天解锁宝箱`)
    return
  }
  if (actionBusy.value) return
  actionBusy.value = true
  try {
    const r = await api.openBox()
    boxResult.value = r
    boxPhase.value = 'sun'
    boxOpen.value = true
    boxTimers.forEach(clearTimeout)
    boxTimers = []
    await refresh()
    if (r.kind === 'sprite') {
      boxTimers.push(setTimeout(() => { boxPhase.value = 'egg' }, 600))
      boxTimers.push(setTimeout(() => { boxPhase.value = r.duplicate ? 'dust' : 'hatch' }, 1400))
    }
  } catch (e) { showToast(e.message) }
  finally { actionBusy.value = false }
}
async function openRankMap() {
  rankMapOpen.value = true
  try { rankMap.value = await api.ranks() } catch {}
}
// 阳光统计页：今日约定与周聚合在 store；账本明细仍 refresh 拉一份留给下钻

function goSunGap(g) {
  if (g.lane) openWordLane(g.lane)
  else if (g.go) activeTab.value = g.go
}

const unitName = (id) => data.units.find(u => u.id === id)?.name || ''
const bySubject = computed(() => {
  const m = {}
  for (const s of data.subjects) m[s.id] = { name: s.name, units: [] }
  const seen = new Set()
  for (const t of data.tasks) {
    if (!m[t.subject_id]) m[t.subject_id] = { name: t.subject_id, units: [] }
    const un = m[t.subject_id]
    if (!seen.has(t.unit_id + t.subject_id)) {
      seen.add(t.unit_id + t.subject_id)
      un.units.push({ id: t.unit_id, name: unitName(t.unit_id), tasks: [] })
    }
    const unit = un.units.find(u => u.id === t.unit_id)
    if (unit) unit.tasks.push(t)
  }
  return m
})
const dailyTodo = computed(() => {
  return data.daily
    .map((d, i) => ({ d, i }))
    .filter(x => !x.d.done_today && !(data.hidden_subjects || []).includes(x.d.subject_id))
    .sort((a, b) => subjectRank(a.d.subject_id) - subjectRank(b.d.subject_id) || a.i - b.i)
    .map(x => x.d)
})
const todayCheckinItems = computed(() => {
  const items = []
  let wordPlaced = false
  const putWord = () => {
    if (wordPlaced || !wordToday.value.enabled) return
    wordPlaced = true
    if (wordDueCard.value && !wordDueCard.value.finished) items.push({ key: 'word-due', kind: 'word', lane: 'due' })
    if (wordNewCard.value && !wordNewCard.value.finished) items.push({ key: 'word-new', kind: 'word', lane: 'new' })
  }
  for (const d of dailyTodo.value) {
    if (subjectRank(d.subject_id) >= subjectRank('英语')) putWord()
    items.push({ key: d.id, kind: 'daily', d })
  }
  putWord()
  if (capsule.value.state === 'ready') items.unshift({ key: 'capsule', kind: 'capsule' })
  return items
})
const tabDailies = computed(() => {
  return data.daily
    .map((d, i) => ({ d, i }))
    .filter(x => x.d.subject_id === activeTab.value)
    .sort((a, b) => a.i - b.i)
    .map(x => x.d)
})
const dailyMotto = computed(() => {
  const m = /^g(\d)/.exec(data.active_term || '')
  return mottoFor(data.today, data.kid_id, m ? Number(m[1]) : 0)
})
const studyNext = computed(() => {
  const out = []
  for (const subject of orderedSubjects.value) {
    const units = bySubject.value[subject.id]?.units || []
    const current = units.find(u => u.tasks.some(t => !t.done && !t.past && !t.locked))
    const task = current?.tasks.find(t => !t.done && !t.past && !t.locked)
    if (task) out.push({ ...task, unit_name: current.name })
  }
  return out
})
const todayRemaining = computed(() => {
  const words = (wordDueCard.value && !wordDueCard.value.finished ? 1 : 0)
    + (wordNewCard.value && !wordNewCard.value.finished ? 1 : 0)
  return reviewDue.value.length + dailyTodo.value.length + studyNext.value.length + words
})
const subjectProgress = computed(() => {
  const m = {}
  for (const s of data.subjects) m[s.id] = { done: 0, total: 0 }
  for (const t of data.tasks) {
    const p = m[t.subject_id]
    if (!p) continue
    p.total++
    if (t.done || t.past) p.done++
  }
  for (const d of data.daily) {
    const p = m[d.subject_id]
    if (!p) continue
    p.total++
    if (d.done_today) p.done++
  }
  return m
})
const AVATAR_PALETTE = ['#f5a524', '#2fa6de', '#2e9e63', '#d2514f', '#7c6cf0', '#e06b9a']
const avatarLetter = computed(() => {
  const n = data.kid_name || '乐'
  return n[n.length - 1]
})
const avatarBg = computed(() => {
  const s = data.kid_id || data.kid_name || ''
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length]
})
function subjectRank(id) {
  const i = SUBJECT_ORDER.indexOf(id)
  return i < 0 ? 99 : i
}
const SIDEBAR_DAILY_ONLY = new Set(['体育', '围棋'])
const orderedSubjects = computed(() => {
  // 有课本进度才进侧栏；体育/围棋只有每日打卡，放今日推荐
  const hidden = new Set(data.hidden_subjects || [])
  const list = data.subjects.filter(s => {
    if (hidden.has(s.id) || SIDEBAR_DAILY_ONLY.has(s.id)) return false
    return (subjectProgress.value[s.id] || {}).total > 0
  })
  list.sort((a, b) => SUBJECT_ORDER.indexOf(a.id) - SUBJECT_ORDER.indexOf(b.id))
  return list
})
const currentUnits = computed(() => bySubject.value[activeTab.value]?.units || [])

function onSwUpdate() { updateReady.value = true }
onMounted(async () => {
  window.addEventListener('sw-update', onSwUpdate)
  // 音效初始化提示（首次需要用户交互才能播放），与 TTS 无关
  document.addEventListener('click', () => {
    if (!soundManager.tested) {
      soundManager.beep(440, 50, 'sine')
      soundManager.tested = true
    }
  }, { once: true })
  try {
    me.value = await api.me()
    authed.value = true
    isAdmin.value = me.value.role === 'parent'
    mustChangePin.value = !!(me.value.force_pin_change && me.value.role === 'parent')
    if (!isAdmin.value) await refresh()
  } catch (e) {
    authed.value = false
    loading.value = false
  }
})
function reloadApp() {
  const u = new URL(location.href)
  u.searchParams.set('_', Date.now())
  location.replace(u.href)
}
</script>

<template>
  <Admin v-if="isAdmin && !mustChangePin" :recovery-code="pendingRecovery" @exit="exitAdmin" @switched="refresh" @consumed-recovery="pendingRecovery = ''" />
  <LoginScreen v-else-if="isAdmin && mustChangePin" mode="force-change" />
  <div v-else-if="authed" class="desk" :style="{ '--topbar-height': topbarHeight + 'px', '--update-bar-height': updateBarHeight + 'px' }">
    <button v-if="updateReady" ref="updateBarEl" type="button" class="update-bar" @click="reloadApp"><RefreshCw class="ico" :size="15" /> 有新版本，刷新</button>
    <div v-if="toast" class="toast-note global-toast" role="status">{{ toast }}</div>
    <!-- 蓝顶栏 -->
    <header ref="topbarEl" class="topbar">
      <div class="who">
        <button type="button" class="avatar companion" :class="['stage-' + (companion.stage || 'egg'), companion.aura ? 'aura-' + companion.aura : '', { 'companion-pulse': companionPulse }]" @click="openCompanion">
          <img :src="companionImage" alt="伙伴" class="companion-img" />
        </button>
        <img v-if="dutySprite" class="duty-face" :src="spImg(dutySprite.id)" :alt="displayName(dutySprite)" />
        <div class="who-copy">
          <div class="hello">{{ data.today || '今天' }}</div>
          <div class="name-row">
            <b class="kid">{{ data.kid_name }}</b>
          </div>
          <div class="companion-line">{{ companionTitle }}</div>
          <div v-if="companion.next_stage" class="companion-need">再 {{ Math.max(0, (companion.next_need || 0) - (companion.earned || 0)) }} 阳光到{{ companion.next_stage_name }}</div>
          <div v-else class="companion-need">开完花了，继续攒阳光也不会掉</div>
        </div>
      </div>
      <div class="pills">
        <span class="pill sun"><i></i> {{ data.level.balance }}</span>
        <span class="pill fire"><Flame class="ico" :size="15" /> <span class="pill-long">连续打卡 </span>{{ data.streak }}<span class="pill-long"> 天</span></span>
        <button class="pill star" @click="openRankMap"><component :is="rankIcon(data.level.level_icon)" class="ico" :size="15" /> {{ data.level.level }}</button>
        <button class="pill ach" @click="openAch"><Medal class="ico" :size="15" /> <span class="pill-long">成就</span><em v-if="newAchCount" class="ach-pill-new">{{ newAchCount }}</em></button>
        <button class="pill box" :class="{ ready: boxes.avail > 0 }" @click="openBox">
          <Gift class="ico" :size="15" /> <span class="pill-long">{{ boxes.avail > 0 ? '宝箱 ×' + boxes.avail : '宝箱' }}</span><span class="pill-short">{{ boxes.avail > 0 ? '×' + boxes.avail : '' }}</span>
        </button>
      </div>
      <div class="next">
        <span v-if="data.level.next" class="next-copy">
          再得 {{ data.level.next_need - data.level.earned }} <Sun class="ico sun" :size="13" /> 到{{ data.level.next }}
        </span>
        <span v-else class="next-copy">最高等级</span>
        <div class="next-bar"><i :style="{ width: data.level.progress + '%' }"></i></div>
      </div>
    </header>

    <div class="body">
      <!-- 左栏 -->
      <aside class="side">
        <!-- 每日签到 - 放在最上面 -->
        <button class="nav nav-checkin" :class="{ done: data.today_checkin, closed: checkinClosed && !data.today_checkin }" @click="checkin" :disabled="data.today_checkin || checkinClosed">
          <span><CalendarDays class="ico" :size="15" /> {{ data.today_checkin ? '今日已签到' : (checkinClosed ? '现在打烊' : '每日签到') }}</span>
        </button>
        <p v-if="checkinClosed && !data.today_checkin" class="checkin-closed">{{ checkinClosedHint() }}</p>
        <div class="side-split" role="separator"></div>
        <div class="nav-group">
          <button class="nav" :class="{ on: activeTab === '今日推荐' }" @click="activeTab = '今日推荐'">
            <span><Sparkles class="ico" :size="15" /> 今日推荐</span>
          </button>
          <button v-for="s in orderedSubjects" :key="s.id" class="nav"
            :class="{ on: activeTab === s.id }" @click="activeTab = s.id">
            <span><component :is="ICONS[s.id] || BookOpen" class="ico" :size="15" /> {{ s.name }}</span>
            <em>{{ subjectProgress[s.id]?.done || 0 }}/{{ subjectProgress[s.id]?.total || 0 }}</em>
          </button>
        </div>
        <div class="side-split" role="separator"></div>
        <div class="nav-group">
          <button class="nav" :class="{ on: activeTab === 'sunshine' }" @click="activeTab = 'sunshine'">
            <span><Sun class="ico" :size="15" /> 我的阳光</span>
          </button>
          <button class="nav" :class="{ on: activeTab === 'base' }" @click="goBase">
            <span><House class="ico" :size="15" /> 秘密基地</span>
          </button>
          <button class="nav" :class="{ on: activeTab === 'bank' }" @click="activeTab = 'bank'">
            <span><Landmark class="ico" :size="15" /> 阳光储蓄所</span>
          </button>
        </div>
      </aside>

      <!-- 右栏 -->
      <main class="main">
        <template v-if="activeTab === '今日推荐'">
          <h1><Sparkles class="ico" :size="20" /> 今天</h1>
          <div class="today-summary">
            <div class="today-progress">
              <strong v-if="todayRemaining">今天还有 {{ todayRemaining }} 项</strong>
              <strong v-else>今天安排的事都完成了</strong>
              <div class="today-breakdown">
                <span v-if="reviewDue.length">复习 {{ reviewDue.length }} 项</span>
                <span v-if="dailyTodo.length">打卡 {{ dailyTodo.length }} 项</span>
                <span v-if="studyNext.length">学习 {{ studyNext.length }} 项</span>
                <span v-if="wordDueCard && !wordDueCard.finished">单词复习 {{ wordDueCard.left }}</span>
                <span v-if="wordNewCard && !wordNewCard.finished">新词 {{ wordNewCard.left }}</span>
              </div>
            </div>
          </div>
          <p v-if="todayPenalty" class="today-pact">
            今天有约定：{{ todayPenalty.reason }} · {{ todayPenalty.n }}
          </p>

          <section v-if="reviewDue.length" class="plan-section review-today">
            <div class="plan-head">
              <div>
                <h2><BookOpen class="ico" :size="18" /> 到期复习</h2>
              </div>
            </div>
            <div class="plan-list">
              <article v-for="x in reviewDue" :key="x.id" class="plan-row review-card enter">
                <div class="plan-row-main">
                  <span class="plan-subject">{{ x.subject_id }}</span>
                  <div><strong>{{ x.tag_name }}</strong><small>{{ x.unit_name }} · 第 {{ (x.interval_idx || 0) + 1 }} 次</small></div>
                </div>
                <span class="plan-state">做完告诉家长</span>
              </article>
            </div>
          </section>

          <section v-if="todayCheckinItems.length" class="plan-section">
            <div class="plan-head">
              <h2>
                <RefreshCw class="ico" :size="18" /> 每日打卡
                <em class="daily-motto" :title="dailyMotto.text + ' · ' + dailyMotto.from">{{ dailyMotto.text }}<i>{{ dailyMotto.from }}</i></em>
              </h2>
              <p v-if="checkinClosed" class="checkin-closed in-page">{{ checkinClosedHint() }}</p>
            </div>
            <div class="grid plan-grid">
              <template v-for="it in todayCheckinItems" :key="it.key">
                <div v-if="it.kind === 'capsule'" class="card enter word-daily-card" role="button" @click="goOpenCapsule">
                  <button type="button" class="circle" @click.stop="goOpenCapsule"><Mail :size="15" /></button>
                  <div class="card-body">
                    <div class="card-title">时间胶囊</div>
                    <div class="card-detail">有一封给自己的信可以拆了</div>
                  </div>
                </div>
                <div v-else-if="it.kind === 'word'" class="card enter word-daily-card" role="button" @click="openWordLane(it.lane)">
                  <button type="button" class="circle" @click.stop="openWordLane(it.lane)"></button>
                  <div class="card-body">
                    <div class="card-title">{{ it.lane === 'due' ? '今日复习' : '今日新词' }}</div>
                    <div class="card-detail">{{ (it.lane === 'due' ? wordDueCard : wordNewCard).detail }}</div>
                    <div class="plus">英语<template v-if="it.lane === 'new'"> · +{{ wordSun }} <Sun class="ico sun" :size="12" /></template></div>
                  </div>
                </div>
                <div v-else class="card enter">
                  <button class="circle" @click="openDaily(it.d)">○</button>
                  <div class="card-body">
                    <div class="card-title">{{ it.d.name }}</div>
                    <div v-if="it.d.note" class="card-detail">{{ it.d.note }}</div>
                    <template v-if="fitnessBar(it.d)">
                      <div class="fit-bar"><i :style="{ width: fitnessBar(it.d).pct + '%' }"></i><em>{{ fitnessBar(it.d).status }}</em></div>
                      <div class="fit-std">{{ fitnessBar(it.d).lines }}</div>
                    </template>
                    <div class="plus">{{ dailySunshineHint(it.d) }} <Sun class="ico sun" :size="12" /></div>
                  </div>
                  <button class="trend" @click="openChart(it.d)" title="看趋势"><TrendingUp :size="15" /></button>
                </div>
              </template>
            </div>
          </section>

          <section v-if="studyNext.length" class="plan-section">
            <div class="plan-head">
              <div><h2><BookOpen class="ico" :size="18" /> 本课下一步</h2></div>
            </div>
            <div class="grid plan-grid">
              <div v-for="t in studyNext" :key="t.id" class="card enter">
                <button class="circle" @click="toggleTask(t, $event)">○</button>
                <div class="card-body">
                  <div class="plan-task-meta">{{ t.subject_id }} · {{ t.unit_name }}</div>
                  <div class="card-title">{{ t.title }}</div>
                  <div v-if="t.detail" class="card-detail">{{ t.detail }}</div>
                  <div class="plus">+{{ t.sunshine }} <Sun class="ico sun" :size="12" /></div>
                </div>
              </div>
            </div>
          </section>
          <div v-if="!todayRemaining" class="empty"><PartyPopper class="ico" :size="16" /> 今天安排的事都完成了。</div>
        </template>

        <template v-else-if="activeTab === 'sunshine'">
          <SunshinePage :daily-todo="dailyTodo" :study-next="studyNext" @navigate="goSunGap" />
        </template>

        <template v-else-if="activeTab === 'base'">
          <SpritesBase ref="baseRef" @open-capsule="openCapsuleBox" />
        </template>

        <template v-else-if="activeTab === 'bank'">
          <BankPage @changed="refresh" />
        </template>

        <template v-else>
          <h1><component :is="ICONS[activeTab] || BookOpen" class="ico" :size="20" /> {{ activeTab }}</h1>

          <div class="unit" v-if="data.daily.some(x => x.subject_id === activeTab) || (activeTab === '英语' && wordToday.enabled)">
            <h2><i></i> 每日打卡</h2>
            <div class="grid">
              <div v-if="activeTab === '英语' && wordDueCard"
                class="card enter word-daily-card" :class="{ done: wordDueCard.finished }" role="button" @click="openWordLane('due')">
                <button type="button" class="circle" :class="{ ok: wordDueCard.finished }" @click.stop="openWordLane('due')"><Check v-if="wordDueCard.finished" :size="15" /></button>
                <div class="card-body">
                  <div class="card-title">今日复习</div>
                  <div class="card-detail">{{ wordDueCard.detail }}</div>
                </div>
              </div>
              <div v-if="activeTab === '英语' && wordNewCard"
                class="card enter word-daily-card" :class="{ done: wordNewCard.finished }" role="button" @click="openWordLane('new')">
                <button type="button" class="circle" :class="{ ok: wordNewCard.finished }" @click.stop="openWordLane('new')"><Check v-if="wordNewCard.finished" :size="15" /></button>
                <div class="card-body">
                  <div class="card-title">今日新词</div>
                  <div class="card-detail">{{ wordNewCard.detail }}</div>
                  <div class="plus">+{{ wordSun }} <Sun class="ico sun" :size="12" /></div>
                </div>
              </div>
              <div v-for="d in tabDailies" :key="d.id"
                class="card enter" :class="{ done: d.done_today }">
                <button class="circle" :class="{ ok: d.done_today }"
                  @click="d.done_today ? cancelDaily(d) : openDaily(d)"><Check v-if="d.done_today" :size="15" /></button>
                <div class="card-body">
                  <div class="card-title">{{ d.name }}</div>
                  <div v-if="d.note" class="card-detail">{{ d.note }}</div>
                  <template v-if="fitnessBar(d)">
                    <div class="fit-bar"><i :style="{ width: fitnessBar(d).pct + '%' }"></i><em>{{ fitnessBar(d).status }}</em></div>
                    <div class="fit-std">{{ fitnessBar(d).lines }}</div>
                  </template>
                  <div class="plus">{{ dailySunshineHint(d) }} <Sun class="ico sun" :size="12" /></div>
                </div>
                <button class="trend" @click="openChart(d)" title="看趋势"><TrendingUp :size="15" /></button>
              </div>
            </div>
          </div>

          <div v-for="u in currentUnits" :key="u.id" class="unit">
            <h2>
              <i></i> {{ u.name }}
              <span v-if="data.unit_scores[u.id]" class="unit-score" :class="scoreClass(data.unit_scores[u.id].score)">
                <Target class="ico" :size="13" /> {{ data.unit_scores[u.id].score }} 分
              </span>
              <span v-if="dueUnit(u.id)" class="unit-review-status">今天复习 {{ dueCount(u.id) }} 项</span>
              <span v-else-if="(data.weak_tags[u.id] || []).length" class="unit-weak">正在巩固</span>
              <span v-else-if="unitWeak(u.id)" class="unit-weak">这单元还要练</span>
            </h2>
            <div class="grid">
              <div v-for="t in u.tasks" :key="t.id" class="card enter" :class="{ done: t.done, past: t.past, locked: t.locked }">
                <button 
              class="circle" 
              :class="{ ok: t.done || t.past, filling: checkingTask === t.id }" 
              @click="toggleTaskWithAnim(t, $event)"
            >
              <div class="circle-fill"></div>
              <Check class="circle-icon" v-if="t.done || t.past" :size="15" /><Lock v-else-if="t.locked" :size="14" /></button>
                <div class="card-body">
                  <div class="card-title">{{ t.title }}</div>
                  <div v-if="t.detail" class="card-detail">{{ t.detail }}</div>
                  <div class="plus"><template v-if="t.past">已学过</template><template v-else-if="t.locked">未解锁</template><template v-else>+{{ t.sunshine }} <Sun class="ico sun" :size="12" /></template></div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!currentUnits.length && !data.daily.some(x => x.subject_id === activeTab) && !(activeTab === '英语' && wordToday.enabled)" class="empty">
            这科没有任务
          </div>
        </template>
      </main>
    </div>

    <!-- 底栏：自定义任务 + 商店 -->
    <footer class="foot">
      <button class="parent" @click="openParent"><User class="ico" :size="15" /> 家长</button>
      <button class="parent" @click="doLogout">退出</button>
      <span class="app-ver" :title="APP_REVISION">{{ APP_LABEL }}</span>
      <span class="grow"></span>
      <button class="shop-fab" @click="openShop"><ShoppingCart class="ico" :size="16" /> 商店</button>
    </footer>

    <!-- 商店抽屉（components/ShopDrawer.vue） -->
    <ShopDrawer ref="shopRef" @changed="refresh" />

    <!-- 时间胶囊（components/CapsuleBox.vue） -->
    <CapsuleBox ref="capsuleRef" />

    <!-- 每日打卡弹窗（components/DailyDialog.vue） -->
    <DailyDialog ref="dailyRef" @submit="submitDaily" />

    <!-- 跳绳趋势（components/TrendChart.vue） -->
    <TrendChart ref="chartRef" />

    <p v-if="err" class="err">{{ err }}</p>

    <!-- 单词练习（components/WordPractice.vue） -->
    <WordPractice ref="wordRef" @collected="refresh" />

    <!-- +N 阳光飞出 -->
    <div v-for="f in floaters" :key="f.id" class="floater" :style="{ left: f.x + 'px', top: f.y + 'px' }">{{ f.text }}</div>

    <!-- 伙伴抽屉 + 庆祝层（components/CompanionDrawer.vue） -->
    <CompanionDrawer ref="drawerRef" :sprite-button="spriteButton" @opened="loadSprites" @open-sprites="openSprites" />

    <!-- 成就墙（components/AchievementsModal.vue） -->
    <AchievementsModal ref="achRef" />

    <!-- 连击宝箱 -->
    <div v-if="boxOpen" class="mask" @click.self="closeBoxMask">
      <div class="shop-modal box-modal">
        <h3><Gift class="ico" :size="18" /> 连击宝箱</h3>
        <div class="box-result">
          <div v-if="boxPhase === 'sun' || !boxResult?.kind" class="box-gain">+{{ boxResult?.delta ?? boxResult }} <Sun class="ico sun" :size="16" /></div>
          <div v-else-if="boxPhase === 'egg'" class="box-egg">🥚</div>
          <template v-else-if="boxPhase === 'hatch'">
            <img class="box-face" :src="spImg(boxResult.item)" :alt="boxResult.sprite?.name" />
            <div class="box-gain">遇到了{{ boxResult.sprite?.name }}</div>
          </template>
          <template v-else-if="boxPhase === 'dust'">
            <div class="box-gain">已经有了 · 星尘 +{{ boxResult.dust_gain }}</div>
          </template>
        </div>
        <button v-if="boxPhase !== 'egg' && !(boxResult?.kind === 'sprite' && boxPhase === 'sun')" class="do big" @click="closeBoxMask">收下</button>
      </div>
    </div>

    <!-- 秘密基地 + 阳光图鉴（components/SpritesBase.vue） -->

    <!-- 成长地图 -->
    <div v-if="rankMapOpen" class="mask" @click.self="rankMapOpen = false">
      <div class="shop-modal map-modal">
        <h3><Map class="ico" :size="18" /> 我的成长之路</h3>
        <div class="map-list">
          <div v-for="r in (rankMap?.ranks || [])" :key="r.id" class="map-node"
            :class="{ done: r.min_sunshine <= (rankMap?.earned || 0), cur: r.id === (rankMap?.current) }">
            <span class="map-icon"><component :is="rankIcon(r.icon)" class="ico" :size="18" /></span>
            <span class="map-name">{{ r.name }}</span>
            <span class="map-th">{{ r.min_sunshine }} <Sun class="ico sun" :size="12" /></span>
          </div>
        </div>
        <button class="ghost" @click="rankMapOpen = false">关闭</button>
      </div>
    </div>
  </div>

  <!-- 登录页（components/LoginScreen.vue） -->
  <LoginScreen v-else ref="loginRef" @ready="afterKidLogin" />
</template>

<style>
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  margin: 0;
  font-family: ui-rounded, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.update-bar { width: 100%; border: none; background: var(--accent); color: #fff; padding: calc(9px + env(safe-area-inset-top)) 22px 9px; display: flex; justify-content: center; align-items: center; font-weight: 700; font-size: 14px; font-family: inherit; position: sticky; top: 0; z-index: 30; cursor: pointer; }
.desk {
  min-height: 100vh;
  padding-bottom: 78px;
  background-color: var(--bg);
  background-image: radial-gradient(rgba(245,165,36,.14) 1.5px, transparent 1.5px);
  background-size: 28px 28px;
}

.topbar {
  background: var(--brand);
  color: #fff; padding: 14px 22px 12px;
  border-bottom: 4px solid rgba(245,165,36,.9);
  padding-top: calc(14px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
  position: sticky; top: var(--update-bar-height, 0px); z-index: 10;
}
.who { display: flex; align-items: center; gap: 12px; min-width: 180px; }
.who-copy { min-width: 0; }
.pill-short { display: none; }
.avatar {
  width: 52px; height: 52px; border-radius: var(--radius-circle); background: var(--accent);
  color: #fff; font-weight: 800; font-size: 22px; letter-spacing: 0;
  display: flex; align-items: center; justify-content: center;
  flex: 0 0 52px; aspect-ratio: 1; overflow: hidden;
  border: 3px solid rgba(255,255,255,.72); box-shadow: var(--shadow-press-active);
}
.avatar.companion { border: none; cursor: pointer; font-family: inherit; padding: 0; color: #fff; position: relative; transition: transform .18s ease; }
.companion-img { width: 100%; height: 100%; object-fit: contain; display: block; }
.companion-img-big { width: 100%; height: 100%; object-fit: contain; display: block; }
.companion-pulse { animation: companion-hop .72s cubic-bezier(.2,1.6,.4,1) both; }
.companion-pulse .companion-img { animation: companion-wiggle .72s ease-out both; }
.avatar.stage-egg, .companion-big.stage-egg { background: #c5ced6; color: #4a5560; }
.avatar.stage-sprout, .companion-big.stage-sprout { background: #7dba6a; color: #fff; }
.avatar.stage-leaf, .companion-big.stage-leaf { background: #2e8f55; color: #fff; }
.avatar.stage-bloom, .companion-big.stage-bloom { background: #f5a524; color: #fff; }
.avatar.aura-week { box-shadow: 0 0 0 3px #f5a524; }
.avatar.aura-fortnight { box-shadow: 0 0 0 3px #f5a524, 0 0 10px 2px rgba(245,165,36,.85); }
.avatar.aura-month { box-shadow: 0 0 0 4px #e8c547, 0 0 14px 3px rgba(232,197,71,.9); }
.companion-line { margin-top: 2px; font-size: 13px; font-weight: 700; opacity: .95; }
.companion-need { font-size: 11px; opacity: .88; margin-top: 1px; }
.companion-sheet {
  width: min(360px, calc(100vw - 32px)); background: var(--surface); border-radius: var(--radius-xl);
  padding: 22px 20px 16px; text-align: center; box-shadow: var(--shadow-lg);
}
.companion-big {
  width: 120px; height: 120px; border-radius: var(--radius-circle); margin: 0 auto 10px;
  display: flex; align-items: center; justify-content: center; color: #fff;
}
.companion-evolve-card { min-width: min(280px, calc(100vw - 40px)); }
.companion-evolve-figure { width: 152px; height: 152px; margin-bottom: 4px; background: transparent; }
.companion-sheet strong { display: block; font-size: 18px; }
.companion-bar { margin: 10px 0 14px; background: var(--surface-2); }
.companion-name { text-align: left; margin: 8px 0 10px; }
.companion-evolve { pointer-events: auto; cursor: pointer; }
.hello { font-size: 12px; opacity: .92; }
.kid { font-size: 22px; font-weight: 800; }
.name-row { display: flex; align-items: center; gap: 8px; }
.rename { background: none; border: none; color: rgba(255,255,255,.85); font-size: 12px; cursor: pointer; }
.name-row input { width: 90px; border: none; border-radius: var(--radius-sm); padding: 4px 8px; }

.pills { display: flex; gap: 12px; flex: 1; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,.24); border: 1px solid rgba(255,255,255,.2);
  border-radius: var(--radius-xl); padding: 8px 16px;
  font-weight: 800; font-size: 15px; display: inline-flex; align-items: center; gap: 6px;
  box-shadow: var(--shadow-sm);
}
.pill.sun { background: var(--accent); color: var(--accent-ink); border-color: rgba(255,255,255,.45); }
.pill.sun i {
  width: 16px; height: 16px; border-radius: var(--radius-circle); background: #fff7cf; display: inline-block;
}
.next { margin-left: auto; text-align: right; font-size: 13px; min-width: 180px; }
.next-bar { height: 6px; background: rgba(255,255,255,.35); border-radius: var(--radius-xs); margin-top: 6px; overflow: hidden; }
.next-bar i { display: block; height: 100%; background: var(--accent); }

/* 签到按钮样式 - 独立显示 */
.nav-checkin {
  background: var(--brand);
  color: #fff;
  font-weight: 700;
  margin-bottom: 0;
  box-shadow: var(--shadow-md);
  position: relative;
}
.nav-checkin:hover:not(:disabled) {
  background: var(--brand-deep);
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}
.nav-checkin.done {
  background: var(--warm);
  color: var(--ink-2);
  cursor: default;
}
.nav-checkin.closed {
  background: var(--surface-2);
  color: var(--ink-2);
  box-shadow: none;
}
.nav-checkin .ico {
  color: inherit;
}
.checkin-closed {
  margin: 6px 10px 2px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-2);
  line-height: 1.4;
}
.checkin-closed.in-page { margin: 0 0 10px; }

.side-split {
  height: 1px;
  margin: 8px 10px;
  background: var(--line);
  flex: none;
}
.nav-group {
  padding-bottom: 0;
  margin-bottom: 0;
}
.nav:first-of-type {
  margin-top: 0;
}

.coming-page {
  min-height: calc(100dvh - var(--topbar-height, 72px) - 120px);
  display: flex; align-items: center; justify-content: center;
}
.coming {
  width: min(420px, 100%); margin: 0; text-align: center;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-xl);
  padding: 40px 28px; box-shadow: var(--shadow-md);
}
.coming .ico { color: var(--accent-ink); }
.coming strong { display: block; margin: 12px 0 4px; font-size: 22px; }
.coming em { display: block; font-style: normal; font-size: 13px; font-weight: 800; color: var(--accent-ink); margin-bottom: 8px; }
.coming p { margin: 0; color: var(--ink-2); font-size: 14px; line-height: 1.6; }
.sun-lead { color: var(--ink-2); margin: 0 0 14px; font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.sun-lead .ico { color: var(--accent-ink); flex: none; }
.sun-hero { display: grid; grid-template-columns: 1.15fr 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.sun-box { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 14px 14px 12px; }
.sun-box span { display: block; font-size: 12px; color: var(--ink-3); font-weight: 700; }
.sun-box b { display: block; margin-top: 2px; font-size: 28px; letter-spacing: -.03em; }
.sun-box small { font-size: 13px; margin-left: 3px; color: var(--ink-3); font-weight: 700; }
.sun-box.main { background: var(--warm); border-color: transparent; }
.sun-ico {
  width: 36px; height: 36px; border-radius: var(--radius-circle);
  display: inline-flex; align-items: center; justify-content: center;
  margin-bottom: 8px; color: #fff;
}
.sun-ico.pocket { background: var(--accent); color: var(--accent-ink); }
.sun-ico.pile { background: var(--brand); }
.sun-ico.fire { background: #e86b2a; }
.sun-ico.study { background: var(--brand); }
.sun-ico.daily { background: #2e9e63; }
.sun-ico.box { background: #d2514f; }
.sun-week { display: flex; align-items: flex-end; gap: 8px; height: 140px; padding-top: 8px; }
.sun-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; }
.sun-col-n { font-size: 12px; font-weight: 800; color: var(--accent-ink); min-height: 16px; }
.sun-col-n.down, .sun-col-n.zero { color: var(--ink-3); }
.sun-track { flex: 1; width: 100%; max-width: 28px; display: flex; align-items: flex-end; justify-content: center; }
.sun-track i { display: block; width: 100%; background: var(--accent); border-radius: 6px 6px 0 0; min-height: 6px; }
.sun-track i.down { background: var(--ink-3); }
.sun-col span:last-child { font-size: 12px; color: var(--ink-2); font-weight: 700; }
.sun-col span.today { color: var(--accent-ink); }
.sun-src-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.sun-src-card {
  background: var(--surface-2); border-radius: var(--radius-lg); padding: 14px 12px;
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
}
.sun-src-card span { font-size: 13px; font-weight: 700; color: var(--ink-2); }
.sun-src-card b { font-size: 22px; letter-spacing: -.03em; }
.sun-log-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--surface-2); }
.sun-log-ico {
  flex: none; width: 32px; height: 32px; border-radius: var(--radius-circle);
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--warm); color: var(--accent-ink);
}
.sun-log-ico.down { background: var(--surface-2); color: var(--ink-3); }
.sun-log-row div { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.sun-log-row strong { font-size: 14px; }
.sun-log-row small { color: var(--ink-3); font-size: 11px; }
.sun-log-row b { font-variant-numeric: tabular-nums; color: var(--accent-ink); font-size: 16px; }
.sun-log-row.down b { color: var(--ink-3); }
.sun-page { max-width: 720px; padding-bottom: 24px; }
.sun-gaps { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.sun-gaps.ok { background: var(--ok-bg); border-radius: var(--radius-xl); padding: 14px 16px; }
.sun-gaps.ok p { margin: 0; font-weight: 700; color: var(--ok); }
.sun-gap { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; text-align: left; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 12px 14px; font-family: inherit; cursor: pointer; }
.sun-gap:disabled { cursor: default; }
.sun-gap span { font-size: 14px; font-weight: 800; color: var(--ink); }
.sun-gap em { font-style: normal; font-size: 12px; font-weight: 800; color: var(--accent-ink); background: var(--warm); padding: 4px 10px; border-radius: var(--radius-pill); }
.sun-week-sum { font-size: 12px; font-weight: 800; color: var(--ink-2); }
.sun-track.dual { display: flex; align-items: flex-end; justify-content: center; gap: 3px; }
.sun-track.dual i { width: 10px; min-height: 0; border-radius: 5px 5px 0 0; }
.sun-track.dual i.in, .sun-week-legend i.in { background: var(--accent); }
.sun-track.dual i.out, .sun-week-legend i.out { background: var(--ink-3); }
.sun-col.quiet .sun-col-n { color: var(--danger); }
.sun-week-legend { display: flex; align-items: center; gap: 6px; margin: 10px 0 0; font-size: 12px; font-weight: 700; color: var(--ink-3); }
.sun-week-legend i { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.sun-path-list { display: flex; flex-direction: column; gap: 8px; }
.sun-path { display: grid; grid-template-columns: 36px 1fr auto; grid-template-areas: "ico name amt" "bar bar bar"; gap: 2px 10px; align-items: center; background: var(--surface-2); border-radius: var(--radius-lg); padding: 12px; }
.sun-path.miss { opacity: .72; }
.sun-path .sun-ico { grid-area: ico; margin: 0; width: 32px; height: 32px; }
.sun-path div:not(.goal-bar) { grid-area: name; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.sun-path strong { font-size: 14px; }
.sun-path small { font-size: 12px; color: var(--ink-2); font-weight: 700; }
.sun-path b { grid-area: amt; font-variant-numeric: tabular-nums; }
.sun-path .src-bar { grid-area: bar; margin-top: 6px; }
.sun-ico.task { background: var(--brand); }
.sun-ico.word { background: #7c6cf0; }
.sun-ico.test { background: #2e9e63; }
.src-bar { margin-top: 8px; height: 6px; }
.src-bar .goal-fill { display: block; height: 100%; }
.ledger-icon.down { background: var(--surface-2); color: var(--ink-3); }
.card-amount small { font-size: 14px; margin-left: 4px; font-weight: 800; color: inherit; opacity: .7; }
.bank-page { max-width: 720px; padding-bottom: 24px; }
.bank-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }
.bank-title { display: flex; align-items: center; gap: 12px; }
.bank-icon { flex: none; width: 48px; height: 48px; padding: 10px; border-radius: var(--radius-lg); background: linear-gradient(160deg, #ffd27a, var(--accent)); color: var(--accent-ink); box-shadow: var(--shadow-button); }
.bank-title h1 { margin: 0; font-size: 24px; letter-spacing: -.03em; }
.bank-title p { margin: 4px 0 0; color: var(--ink-2); font-size: 13px; font-weight: 600; }
.bank-interest-badge { display: flex; align-items: center; gap: 8px; background: var(--warm); border: 1px solid rgba(245,165,36,.35); border-radius: var(--radius-lg); padding: 8px 12px; }
.interest-icon { font-size: 16px; }
.interest-info { display: flex; flex-direction: column; }
.interest-info strong { font-size: 14px; color: var(--accent-ink); }
.interest-info small { font-size: 11px; color: var(--ink-2); font-weight: 700; }
.bank-cards { display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px; margin-bottom: 16px; }
.bank-card { position: relative; overflow: hidden; border-radius: var(--radius-xl); padding: 18px 18px 16px; min-height: 112px; }
.bank-card-primary { background: linear-gradient(145deg, #ffd27a 0%, #f5a524 70%, #e08a12 100%); color: var(--accent-ink); box-shadow: var(--shadow-button); }
.bank-card-secondary { background: var(--surface); border: 1px solid var(--line); box-shadow: var(--shadow-sm); }
.card-label { font-size: 12px; font-weight: 800; opacity: .78; }
.card-amount { margin-top: 6px; font-size: 36px; font-weight: 800; letter-spacing: -.04em; font-variant-numeric: tabular-nums; }
.card-icon { position: absolute; right: 14px; bottom: 12px; opacity: .22; }
.bank-goal-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-xl); padding: 16px; margin-bottom: 16px; box-shadow: var(--shadow-sm); }
.bank-goal-empty { display: flex; align-items: center; gap: 12px; color: var(--ink-2); }
.bank-goal-empty p { margin: 0; font-size: 13px; font-weight: 700; line-height: 1.5; }
.goal-header { display: flex; align-items: center; gap: 12px; }
.goal-icon { flex: none; color: var(--accent-ink); }
.goal-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.goal-info strong { font-size: 16px; }
.goal-info span { font-size: 12px; color: var(--ink-2); font-weight: 700; font-variant-numeric: tabular-nums; }
.goal-badge { flex: none; background: var(--ok-bg); color: var(--ok); font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: var(--radius-pill); }
.goal-progress { margin-top: 12px; }
.goal-bar { height: 10px; background: var(--surface-2); border-radius: var(--radius-pill); overflow: hidden; }
.goal-fill { height: 100%; background: linear-gradient(90deg, #ffd27a, var(--accent)); border-radius: var(--radius-pill); }
.goal-tip { margin: 8px 0 0; font-size: 13px; color: var(--ink-2); font-weight: 700; }
.bank-operations { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-xl); padding: 16px; margin-bottom: 16px; box-shadow: var(--shadow-sm); }
.op-header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.op-header h3 { margin: 0; font-size: 15px; }
.op-amounts { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.amount-chip { border: 1px solid var(--line); background: var(--surface-2); color: var(--ink); padding: 8px 14px; border-radius: var(--radius-pill); cursor: pointer; font-family: inherit; font-size: 14px; font-weight: 800; min-width: 52px; }
.amount-chip.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.amount-input { width: 92px; border: 1px solid var(--line); border-radius: var(--radius-pill); padding: 8px 12px; font-size: 14px; font-family: inherit; font-weight: 700; }
.op-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.op-btn { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; border: none; border-radius: var(--radius-lg); padding: 14px 16px; cursor: pointer; font-family: inherit; text-align: left; }
.op-btn span { font-size: 16px; font-weight: 800; }
.op-btn small { font-size: 12px; font-weight: 700; opacity: .78; }
.op-btn:disabled { opacity: .45; cursor: not-allowed; }
.op-btn-deposit { background: var(--accent); color: #fff; box-shadow: var(--shadow-button); }
.op-btn-withdraw { background: var(--surface-2); color: var(--ink); border: 1px solid var(--line); }
.bank-section { margin-bottom: 18px; }
.section-title { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; font-size: 15px; }
.request-list, .ledger-list { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-xl); padding: 4px 14px; box-shadow: var(--shadow-sm); }
.request-item, .ledger-item { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--surface-2); }
.request-item:last-child, .ledger-item:last-child { border-bottom: none; }
.request-info, .ledger-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.request-info strong, .ledger-info strong { font-size: 14px; }
.request-info small, .ledger-info small { font-size: 11px; color: var(--ink-3); font-weight: 700; }
.request-status { font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: var(--radius-pill); }
.request-status.pending { background: var(--warm); color: var(--accent-ink); }
.request-status.approved { background: var(--ok-bg); color: var(--ok); }
.request-status.rejected { background: var(--danger-bg); color: var(--danger); }
.ledger-icon { flex: none; width: 32px; height: 32px; border-radius: var(--radius-circle); display: inline-flex; align-items: center; justify-content: center; background: var(--warm); color: var(--accent-ink); }
.ledger-amount { font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; }
.ledger-amount.plus { color: var(--ok); }
.ledger-amount.minus { color: var(--ink-3); }
.bank-hall { max-width: 860px; padding-bottom: 28px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-xl); overflow: hidden; box-shadow: var(--shadow-sm); }
.bank-sign { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; width: 100%; padding: 16px 18px 14px; background: var(--warm); border-bottom: 1px solid rgba(245,165,36,.28); }
.bank-sign-board { flex: 1; min-width: 0; }
.bank-sign-board h1 { margin: 6px 0 0; font-size: 26px; letter-spacing: -.03em; }
.bank-sign-board p { margin: 4px 0 0; color: var(--ink-2); font-size: 13px; font-weight: 600; }
.bank-open-lamp { display: inline-block; background: var(--ok-bg); color: var(--ok); font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: var(--radius-pill); }
.bank-open-lamp.closed { background: #e8eef3; color: var(--ink-2); }

.bank-sign-rate { flex: none; background: var(--surface); border: 1px solid rgba(245,165,36,.35); border-radius: var(--radius-lg); padding: 8px 12px; }
.bank-sign-rate strong { display: block; font-size: 14px; color: var(--accent-ink); }
.bank-sign-rate small { display: block; margin-top: 2px; font-size: 11px; font-weight: 700; color: var(--ink-2); }
.bank-terms { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 0 0 12px; align-items: stretch; }
.bank-terms .bank-kicker { grid-column: 1 / -1; }
.bank-terms .bank-chip {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
  width: 100%; min-height: 58px; min-width: 0; padding: 8px 6px; border-radius: var(--radius-lg); text-align: center;
}
.bank-terms .bank-chip small { font-size: 11px; font-weight: 700; opacity: .78; line-height: 1.2; }
.bank-deposits { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.bank-dep { display: flex; justify-content: space-between; align-items: center; gap: 8px; background: var(--surface-2); border-radius: var(--radius-lg); padding: 10px 12px; }
.bank-dep strong { display: block; font-size: 13px; }
.bank-dep small { display: block; margin-top: 2px; font-size: 12px; color: var(--ink-2); font-weight: 700; }
.bank-vault-copy small { display: block; margin-top: 6px; font-size: 12px; font-weight: 700; opacity: .8; }
.bank-room { display: grid; grid-template-columns: 1.15fr .85fr; gap: 0; align-items: stretch; }
.bank-counter, .bank-vault { background: transparent; border: none; border-radius: 0; padding: 16px 18px 18px; box-shadow: none; }
.bank-counter { border-right: 1px solid var(--line); }
.bank-counter.closed { opacity: .78; }

.bank-counter.busy { box-shadow: var(--shadow-button); }
.bank-window { display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--surface-2); border-radius: var(--radius-lg); }
.bank-teller-ico { flex: none; width: 44px; height: 44px; padding: 8px; border-radius: var(--radius-lg); background: linear-gradient(160deg, #ffd27a, var(--accent)); color: var(--accent-ink); }
.bank-window strong { display: block; font-size: 15px; }
.bank-window small { display: block; margin-top: 2px; font-size: 12px; color: var(--ink-2); font-weight: 700; }
.bank-kicker { font-size: 12px; font-weight: 800; color: var(--ink-2); }
.bank-tray { margin-top: 14px; display: flex; align-items: baseline; gap: 8px; }
.bank-tray strong, .bank-vault-copy strong { font-size: 36px; font-weight: 800; letter-spacing: -.04em; font-variant-numeric: tabular-nums; color: var(--accent-ink); }
.bank-tray span:last-child, .bank-vault-copy span:last-child { font-size: 13px; font-weight: 800; color: var(--ink-3); }
.bank-chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0 12px; }
.bank-chip { border: 1px solid var(--line); background: var(--surface-2); color: var(--ink); padding: 8px 14px; border-radius: var(--radius-pill); cursor: pointer; font-family: inherit; font-size: 14px; font-weight: 800; min-width: 48px; }
.bank-chip.on { background: var(--accent); color: #fff; border-color: var(--accent); }
.bank-chip:disabled, .bank-chip-input:disabled { opacity: .45; cursor: not-allowed; }

.bank-chip-input { width: 88px; border: 1px solid var(--line); border-radius: var(--radius-pill); padding: 8px 12px; font-size: 14px; font-family: inherit; font-weight: 700; }
.bank-desk-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.bank-act { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; border: none; border-radius: var(--radius-lg); padding: 12px 14px; cursor: pointer; font-family: inherit; text-align: left; }
.bank-act span { font-size: 15px; font-weight: 800; }
.bank-act small { font-size: 12px; font-weight: 700; opacity: .78; }
.bank-act:disabled { opacity: .45; cursor: not-allowed; }
.bank-act.in { background: var(--accent); color: #fff; box-shadow: var(--shadow-button); }
.bank-act.out { background: var(--surface-2); color: var(--ink); border: 1px solid var(--line); }
.bank-wait { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.bank-wait-slip { display: flex; justify-content: space-between; align-items: center; gap: 8px; background: var(--warm); border-radius: var(--radius-lg); padding: 10px 12px; }
.bank-wait-slip strong { font-size: 13px; }
.bank-wait-slip em { font-style: normal; font-size: 12px; font-weight: 800; color: var(--accent-ink); }
.bank-vault { cursor: pointer; }
.bank-vault.reached { box-shadow: inset 0 0 0 2px rgba(245,165,36,.55); }
.bank-vault-door { position: relative; overflow: hidden; min-height: 148px; border-radius: var(--radius-lg); background: linear-gradient(160deg, #ffe3a8 0%, var(--accent) 100%); }
.bank-vault-glow { position: absolute; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,.28); }
.bank-vault-copy { position: relative; z-index: 1; padding: 18px 16px; color: var(--accent-ink); }
.bank-vault-copy .bank-kicker, .bank-vault-copy span:last-child { color: var(--accent-ink); opacity: .78; }
.bank-vault-copy strong { color: var(--accent-ink); }
.bank-vault-note, .bank-vault-seal, .bank-vault-hint { margin: 12px 0 0; font-size: 13px; font-weight: 700; line-height: 1.45; }
.bank-vault-note.dim { color: var(--ink-2); }
.bank-vault-seal { background: var(--ok-bg); color: var(--ok); border-radius: var(--radius-pill); padding: 6px 10px; display: inline-block; }
.bank-vault-hint { display: block; color: var(--ink-3); font-size: 11px; }
.bank-passbook { margin-top: 12px; background: var(--surface-2); border-radius: var(--radius-lg); padding: 10px 12px; max-height: 240px; overflow: auto; }
.bank-passbook h3 { margin: 0 0 8px; font-size: 14px; }
.bank-pass-empty { font-size: 13px; color: var(--ink-3); font-weight: 700; padding: 8px 0; }
.bank-pass-row { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
.bank-pass-row:last-child { border-bottom: none; }
.bank-pass-row small { color: var(--ink-3); font-weight: 700; }
.bank-pass-row b { font-variant-numeric: tabular-nums; }
.bank-pass-row.quiet { opacity: .78; }
.bank-pass-row .plus { color: var(--ok); }
.bank-pass-row .minus { color: var(--ink-3); }
@media (max-width: 1100px) {
  .sun-page { max-width: none; }
  .bank-title h1 { font-size: 22px; }
  .bank-title p { font-size: 13px; }
  .sun-week { height: 120px; gap: 4px; }
  .sun-col-n { font-size: 11px; }
  .sun-gap { padding: 12px; }
  .sun-gap span { font-size: 14px; line-height: 1.35; }
  .bank-hall { max-width: none; }
  .bank-sign { align-items: flex-start; padding: 14px 14px 12px; }
  .bank-sign-board h1 { font-size: 22px; }
  .bank-room { grid-template-columns: 1fr; }
  .bank-counter { border-right: none; border-bottom: 1px solid var(--line); }
  .base-head { gap: 8px; }
  .base-head .do { margin-left: auto; padding: 8px 12px; }
  .atlas-stage-page { max-width: none; }
  .atlas-scene-tabs .tab { min-height: 40px; }
}
@media (max-width: 700px) {
  .sun-week { height: 108px; gap: 2px; }
  .sun-col-n { font-size: 10px; }
  .sun-track.dual i { width: 7px; }
  .bank-desk-btns { grid-template-columns: 1fr; }
  .bank-terms { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .bank-chips { gap: 6px; }
  .bank-chip { min-width: 44px; padding: 8px 12px; }
  .bank-chip-input { width: 72px; }
  .bank-pass-row { grid-template-columns: 1fr auto; }
  .bank-pass-row small { grid-column: 1; }
  .atlas-scene-tabs { gap: 6px; }
  .atlas-scene-tabs .tab { flex: 1; text-align: center; padding: 8px 10px; }
  .atlas-stage { margin-left: -4px; margin-right: -4px; width: calc(100% + 8px); border-radius: 10px; }
}
@media (max-width: 640px) {
  .bank-cards { grid-template-columns: 1fr 1fr; }
  .card-amount { font-size: 28px; }
  .op-buttons { grid-template-columns: 1fr; }
}

.cta {
  border: none; border-radius: var(--radius-xl); padding: 11px 22px; font-weight: 800; font-size: 15px; cursor: pointer;
}
.cta.check {
  background: var(--accent); color: var(--accent-ink);
  box-shadow: var(--shadow-press);
}
.cta.check:not(:disabled):hover { box-shadow: var(--shadow-press-hover); }
.cta.check:not(:disabled):active { box-shadow: var(--shadow-press-active); }
.cta.check:disabled { background: var(--warm); color: var(--ink-3); cursor: default; }
.toast-note {
  background: var(--ink); color: #fff; border-radius: var(--radius-pill); padding: 9px 16px;
  font-size: 13px; font-weight: 700; box-shadow: var(--shadow-md);
}
.global-toast {
  position: fixed; left: 50%; top: calc(var(--topbar-height, 72px) + 12px); bottom: auto;
  z-index: 35; max-width: min(90vw, 520px); transform: translateX(-50%);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; animation: enter .25s var(--ease) both;
}

.body { display: flex; gap: 18px; padding: 18px 22px; align-items: flex-start; }
.side {
  width: 196px; flex: 0 0 196px; background: var(--surface); border-radius: var(--radius-xl); padding: 10px;
  box-shadow: var(--shadow-md); border: 2px solid var(--line);
  position: sticky; top: calc(var(--topbar-height, 0px) + 18px); max-height: calc(100dvh - var(--topbar-height, 0px) - 36px); overflow-y: auto; z-index: 5;
}
.nav {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  border: none; background: none; padding: 11px 12px; border-radius: var(--radius-lg);
  color: var(--ink-2); font-size: 15px; cursor: pointer; margin-bottom: 2px;
  transition: all 0.2s ease;
}
.nav:hover:not(.on) {
  background: var(--surface-2);
}
.nav em { font-style: normal; font-size: 12px; color: var(--ink-3); background: var(--surface-2); padding: 2px 8px; border-radius: var(--radius-sm); transition: all 0.2s ease; }
.nav.on {
  background: var(--accent);
  color: white;
  font-weight: 600;
  box-shadow: var(--shadow-button);
}
.nav.on .ico {
  color: white;
}
.nav.on em { 
  background: rgba(255, 255, 255, 0.25);
  color: white;
  font-weight: 600;
  backdrop-filter: blur(10px);
}

.main { flex: 1; min-width: 0; }
.main h1 { margin: 4px 0 6px; font-size: 28px; }
.main h1 .ico { color: var(--accent); }
.unit { margin-bottom: 22px; }
.unit h2 {
  margin: 0 0 10px; font-size: 16px; color: var(--brand-deep); display: flex; align-items: center; gap: 8px;
}
.unit h2 i { width: 4px; height: 16px; background: var(--brand); border-radius: var(--radius-xs); display: inline-block; }
.unit-score { font-size: 11px; padding: 2px 9px; border-radius: var(--radius-sm); font-weight: 800; margin-left: 4px; white-space: nowrap; }
.unit-score.gold { background: var(--warm); color: var(--accent-ink); }
.unit-score.green { background: var(--ok-bg); color: var(--ok); }
.unit-score.blue { background: var(--surface-2); color: var(--brand-deep); }
.unit-score.gray { background: var(--surface-2); color: var(--ink-3); }
.unit-weak, .unit-review-status { font-size: 11px; padding: 2px 8px; border-radius: var(--radius-sm); font-weight: 800; background: var(--warm); color: var(--accent-ink); }
.unit-review-status { background: var(--accent); color: var(--accent-ink); }
.today-summary {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin: 0 0 18px;
  padding: 12px 14px; border: 2px dashed var(--accent); border-radius: var(--radius-lg);
  background: var(--warm-2); color: var(--ink-2);
}
.today-progress { flex: 1; min-width: 180px; }
.today-summary strong { display: block; color: var(--ink); }
.today-breakdown { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 3px; }
.today-breakdown span { font-size: 12px; padding-left: 8px; border-left: 1px solid var(--line); }
.today-pact {
  margin: -6px 0 16px; padding: 10px 14px; border-radius: var(--radius-md);
  background: var(--warm); color: var(--accent-ink); font-size: 13px; line-height: 1.5;
}
.plan-section { margin: 0 0 24px; }
.plan-section.review-today { padding: 14px; border: 1px solid var(--accent); border-radius: var(--radius-lg); background: var(--warm-2); }
.plan-head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
.plan-head h2 { margin: 0; font-size: 16px; color: var(--ink); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; width: 100%; }
.daily-motto {
  flex: 1; min-width: 0; margin-left: 4px; font-style: normal; font-weight: 800; font-size: 13px;
  line-height: 1.3; padding: 4px 10px; border-radius: var(--radius-pill);
  background: var(--brand); color: #fff;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.daily-motto i { font-style: normal; font-weight: 600; opacity: .78; margin-left: 8px; }
.plan-list { display: flex; flex-direction: column; gap: 6px; }
.plan-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-sm); }
.plan-row-main { display: flex; align-items: center; gap: 9px; min-width: 0; }
.plan-row-main strong { display: block; font-size: 13px; color: var(--ink); }
.plan-row-main small { display: block; margin-top: 3px; color: var(--ink-3); font-size: 11px; }
.plan-subject { flex: none; color: var(--brand-deep); font-size: 11px; font-weight: 800; }
.plan-state { flex: none; color: var(--accent-ink); font-size: 11px; font-weight: 700; }
.plan-grid { grid-template-columns: repeat(3, 1fr); }
.plan-task-meta { margin-bottom: 4px; color: var(--brand-deep); font-size: 11px; font-weight: 700; }
.review-card { background: var(--surface); }
.review-card-meta { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-bottom: 5px; color: var(--ink-3); font-size: 11px; }
.review-card-meta .wp-round { margin-right: 0; }
.fit-bar { position: relative; height: 14px; background: var(--surface-2); border-radius: var(--radius-sm); margin: 6px 0 4px; overflow: hidden; }
.fit-bar i { display: block; height: 100%; background: var(--brand); border-radius: var(--radius-sm); }
.fit-bar em { position: absolute; inset: 0; font-style: normal; font-size: 10px; font-weight: 800; color: var(--ink-2); display: flex; align-items: center; justify-content: center; }
.fit-std { font-size: 11px; color: var(--ink-3); margin: 0 0 4px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.card {
  position: relative; background: var(--surface); border-radius: var(--radius-lg); padding: 20px 16px 18px 16px;
  display: flex; gap: 12px; align-items: flex-start; min-height: 96px;
  box-shadow: var(--shadow-md); border: 2px solid var(--line);
  transition: transform .18s var(--spring), box-shadow .18s var(--ease), border-color .18s var(--ease);
}
@media (hover: hover) {
  .card:not(.past):not(.locked):hover {
    transform: translateY(-3px) rotate(-.3deg);
    border-color: rgba(245,165,36,.55);
    box-shadow: var(--shadow-md);
  }
}
.card.done { background: var(--ok-bg); border-color: var(--ok-bg); }
.card.past { opacity: .55; }
.circle {
  width: 36px; height: 36px; border-radius: var(--radius-circle); border: 3px solid var(--brand);
  background: #fff; flex: 0 0 36px; cursor: pointer; color: #fff; font-weight: 800;
  transition: transform .18s var(--spring), background .18s var(--ease), border-color .18s var(--ease);
  position: relative;
  overflow: hidden;
}
.circle:not(.ok):hover { transform: scale(1.08) rotate(8deg); }
.circle.ok { animation: checkpop .3s var(--spring); }
.circle.ok { background: var(--ok); border: 2px solid var(--ok); }
.card-body { flex: 1; min-width: 0; }
.card-title { font-size: 14px; line-height: 1.45; font-weight: 600; }
.card-detail { margin-top: 4px; font-size: 12px; line-height: 1.5; color: var(--ink-3); }
.plus { margin-top: 8px; color: var(--accent); font-weight: 800; font-size: 13px; }
.card.locked { opacity: .45; }
.x {
  position: absolute; top: 6px; right: 8px; border: none; background: none; color: var(--ink-3);
  cursor: pointer; font-size: 16px; display: none;
}
.card:hover .x { display: block; }
.empty {
  color: var(--ink-2); padding: 30px 18px; text-align: center;
  background: var(--warm-2); border: 2px dashed rgba(245,165,36,.55); border-radius: var(--radius-lg);
}

.foot {
  position: fixed; left: 0; right: 0; bottom: 0; background: var(--surface);
  display: flex; align-items: center; gap: 12px; padding: 12px 22px;
  box-shadow: var(--shadow-up);
}
.foot-label {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 10px 14px; color: var(--ink-3); font-size: 13px;
}
.foot-input {
  flex: 1; border: 1px solid var(--line); border-radius: var(--radius-md); padding: 10px 14px; font-size: 14px;
}
.foot-add { border: none; background: var(--brand); color: #fff; border-radius: var(--radius-md); padding: 10px 16px; font-weight: 800; cursor: pointer; }
.shop-fab {
  border: none; background: var(--accent); color: var(--accent-ink); border-radius: var(--radius-xl); padding: 10px 18px;
  font-weight: 800; cursor: pointer; white-space: nowrap;
}
.app-ver {
  color: var(--ink-3); font-size: 11px; font-weight: 700; letter-spacing: .02em;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
.word-daily-card { cursor: pointer; }
.trend { position: absolute; top: 8px; right: 8px; border: none; background: var(--warm); border-radius: var(--radius-lg); padding: 3px 8px; font-size: 15px; cursor: pointer; line-height: 1; }
.parent { border: none; background: none; color: var(--ink-3); font-size: 13px; font-weight: 700; cursor: pointer; padding: 10px 4px; white-space: nowrap; }

/* 登录页 */
/* 升级庆祝 */
.celebrate { position: fixed; inset: 0; z-index: 40; display: flex; align-items: center; justify-content: center; pointer-events: none; }
.floater {
  position: fixed; z-index: 60; pointer-events: none;
  font-size: 22px; font-weight: 900; color: var(--accent);
  transform: translate(-50%, -50%); white-space: nowrap;
  text-shadow: 0 1px 3px rgba(0,0,0,.18);
  animation: flyup 1s ease-out forwards;
}
@keyframes flyup {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(.5); }
  15% { opacity: 1; transform: translate(-50%, -70%) scale(1.15); }
  100% { opacity: 0; transform: translate(-50%, -180%) scale(.85); }
}
.celebrate-card { position: relative; z-index: 2; background: var(--surface); border-radius: var(--radius-xl); padding: 32px 44px; text-align: center; box-shadow: var(--shadow-lg); animation: pop .5s cubic-bezier(.2,1.6,.4,1) both; }
.celebrate-icon { font-size: 64px; animation: bounce 1s ease-in-out infinite; }
.celebrate-title { font-size: 22px; font-weight: 800; color: var(--accent); margin-top: 8px; }
.celebrate-name { font-size: 18px; font-weight: 700; color: var(--ink); margin-top: 6px; }
.pill.ach { cursor: pointer; border: none; font-family: inherit; }
.pill.star, .pill.box { cursor: pointer; border: none; font-family: inherit; }
.pill.box.ready { animation: boxpulse 1.1s ease-in-out infinite; }
@keyframes boxpulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.12); } }

/* 圆圈填充动画 */
.circle-fill {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: var(--ok);
  transform: scale(0);
  opacity: 0;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 1;
}

.circle-icon {
  position: relative;
  z-index: 2;
}

.circle.filling .circle-fill {
  transform: scale(1);
  opacity: 1;
  animation: pulse-in 0.3s ease-out;
}

@keyframes pulse-in {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  60% {
    transform: scale(1.15);
    opacity: 1;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.circle.ok .circle-fill {
  transform: scale(1);
  opacity: 1;
}

.circle.ok {
  animation: check-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes check-pop {
  0% { 
    transform: scale(0.85); 
  }
  50% { 
    transform: scale(1.12); 
  }
  100% { 
    transform: scale(1); 
  }
}

.circle:not(.ok):hover {
  transform: scale(1.1) rotate(8deg);
  border-color: var(--accent);
}

.circle:active {
  transform: scale(0.95);
}

.box-modal { max-width: 380px; text-align: center; }
.box-result { padding: 16px 0 8px; }
.box-icon { font-size: 64px; animation: bounce 1s ease-in-out infinite; }
.box-gain { font-size: 28px; font-weight: 800; color: var(--accent); margin-top: 6px; }
.map-modal { max-width: 480px; max-height: calc(100vh - 24px); max-height: calc(100dvh - 24px); overflow: hidden; display: flex; flex-direction: column; }
.map-list { display: flex; flex: 1 1 auto; flex-direction: column; gap: 6px; margin: 14px 0; min-height: 0; overflow-y: auto; }
.map-node { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: var(--radius-md); background: var(--surface-2); opacity: .55; }
.map-node.done { opacity: 1; background: var(--ok-bg); }
.map-node.cur { opacity: 1; background: var(--warm-2); border: 2px solid var(--accent); }
.map-icon { font-size: 24px; }
.map-name { font-weight: 700; color: var(--ink); flex: 1; }
.map-th { font-size: 12px; color: var(--ink-3); }
.map-node.cur .map-th { color: var(--accent-ink); }
.pill.ach { position: relative; }
@keyframes pop { from { transform: scale(.4); opacity: 0; } to { transform: scale(1); opacity: 1; } }
@keyframes bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
@keyframes companion-hop { 0%,100% { transform: translateY(0) rotate(0); } 28% { transform: translateY(-9px) rotate(-4deg); } 58% { transform: translateY(1px) rotate(3deg); } 78% { transform: translateY(-4px) rotate(-2deg); } }
@keyframes companion-wiggle { 0%,100% { transform: scale(1) rotate(0); } 35% { transform: scale(1.06) rotate(-3deg); } 65% { transform: scale(1.02) rotate(3deg); } }

@media (max-width: 1100px) {
  .topbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      "who pills"
      "next next";
    align-items: center;
    column-gap: 10px;
    row-gap: 6px;
    padding: 8px 12px 8px;
    padding-top: calc(8px + env(safe-area-inset-top));
  }
  .who { grid-area: who; width: auto; min-width: 0; gap: 8px; }
  .who-copy { min-width: 0; flex: 1; }
  .who > .avatar { width: 40px; height: 40px; font-size: 18px; flex: 0 0 40px; aspect-ratio: 1; }
  .hello, .companion-line, .companion-need { display: none; }
  .kid { font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .name-row { flex-wrap: nowrap; }
  .rename { font-size: 12px; white-space: nowrap; flex: 0 0 auto; }
  .rename-txt { display: none; }
  .pills { grid-area: pills; width: auto; flex: 0 0 auto; flex-wrap: nowrap; justify-content: flex-end; gap: 6px; }
  .pill { padding: 5px 8px; font-size: 12px; }
  .pill-long { display: none; }
  .pill-short { display: inline; }
  .next { grid-area: next; margin-left: 0; text-align: left; min-width: 0; width: 100%; font-size: 11px; }
  .next-copy { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
  .next-bar { margin-top: 4px; }
}

@media (max-width: 900px) {
  .plan-section.review-today { padding: 12px; }
  .word-en { font-size: 32px; }
  .plan-grid { grid-template-columns: 1fr; }
  .plan-row { align-items: flex-start; flex-direction: column; gap: 5px; }
  .plan-state { padding-left: 38px; }
  .plan-head h2 { font-size: 15px; }
  .review-card-meta { align-items: flex-start; flex-direction: column; gap: 4px; }
  .desk { padding-bottom: calc(72px + env(safe-area-inset-bottom)); }
  .cta { width: 100%; padding: 12px; font-size: 15px; }
  .today-summary { align-items: stretch; gap: 12px; }

  .mask { padding: 12px; }
  .shop-modal { width: 100%; max-width: none; }
  .main { padding: 12px 14px 16px; }
  .main h1 { font-size: 20px; margin: 0 0 4px; }
  .grid { grid-template-columns: 1fr; gap: 8px; }
  .card { min-height: 64px; padding: 12px; align-items: center; max-width: none; }
  .circle { width: 32px; height: 32px; flex: 0 0 32px; }
  .x { display: block; }

  .foot {
    gap: 8px; padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  }
  .foot-label { display: none; }
  .foot-input { min-width: 0; font-size: 16px; }
  .shop-fab { padding: 10px 12px; }
}

/* iPad 竖屏：继续左侧栏，略收窄。不要把科目横滑。 */
@media (max-width: 1100px) and (min-width: 701px) {
  .side { width: 168px; flex: 0 0 168px; padding: 8px; }
  .nav { padding: 10px; font-size: 14px; }
  .nav em { padding: 1px 6px; font-size: 11px; }
  .side-sunshine-header { padding: 0 8px; }
}

/* 手机：顶下一行胶囊。最近阳光不挤进横条。 */
@media (max-width: 700px) {
  .pills { overflow-x: auto; max-width: 100%; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
  .pills::-webkit-scrollbar { display: none; }
  .body { flex-direction: column; gap: 0; padding: 0; }
  .side {
    width: 100%; flex: none; border-radius: 0;
    position: sticky; top: var(--topbar-height, 0px); z-index: 9;
    max-height: none;
    display: flex; align-items: center; gap: 8px; overflow-x: auto;
    padding: 8px 12px; box-shadow: var(--shadow-md);
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .side::-webkit-scrollbar { display: none; }
  .side-split { width: 1px; height: 28px; align-self: center; margin: 0 2px; }
  .sun-hero { grid-template-columns: 1fr 1fr; }
  .sun-cards { grid-template-columns: 1fr 1fr; }
  .sun-cards .bank-card-primary { grid-column: 1 / -1; }
  .sun-src-grid { grid-template-columns: 1fr; }
  .side-sunshine, .side-split-sun { display: none; }
  .nav-group {
    display: flex; flex-direction: row; align-items: center; gap: 8px;
    padding: 0; margin: 0;
  }
  .nav {
    flex: 0 0 auto; width: auto; margin: 0;
    flex-direction: row; align-items: center; justify-content: center; gap: 6px;
    padding: 8px 14px; white-space: nowrap;
    border-radius: var(--radius-pill);
    background: var(--surface-2);
  }
  .nav em { padding: 1px 6px; font-size: 11px; }
}
.duty-face { width: 24px; height: 24px; object-fit: contain; filter: drop-shadow(0 1px 1px rgba(0,0,0,.25)); }
.box-egg { font-size: 56px; animation: wobble 1s ease-in-out infinite; }
.box-face { width: 96px; height: 96px; object-fit: contain; display: block; margin: 0 auto 8px; }
@keyframes wobble { 0%,100% { transform: rotate(-8deg); } 50% { transform: rotate(8deg); } }
.morning-note {
  display: flex; gap: 12px; align-items: flex-start;
  max-width: 920px; margin: 0 0 10px;
  background: var(--warm-2); border: 2px solid var(--line); border-radius: var(--radius-lg);
  padding: 10px 12px; cursor: pointer;
}
.morning-note .duty-face { width: 36px; height: 36px; flex: 0 0 36px; }
.morning-note strong { display: block; font-size: 13px; color: var(--accent-ink); }
.morning-note p { margin: 2px 0 0; font-size: 14px; line-height: 1.45; }
.morning-note small { color: var(--ink-3); font-size: 12px; }
.atlas-dust { float: right; font-size: 13px; font-weight: 600; color: var(--ink-2); }
.atlas-scene-tabs { display: flex; gap: 8px; margin: 0 0 8px; }
.atlas-scene-tabs .tab { border: 2px solid var(--line); background: var(--surface-2); border-radius: 999px; padding: 4px 12px; font: inherit; cursor: pointer; }
.atlas-scene-tabs .tab.on { background: var(--ink); color: #fff; border-color: var(--ink); }
.atlas-stage { position: relative; width: 100%; aspect-ratio: 1448 / 543; border-radius: 12px; overflow: hidden; background: #1a1410; margin-bottom: 12px; }
.atlas-stage-page { max-width: 920px; overflow: visible; }
.atlas-building {
  position: absolute; inset: 0; z-index: 8;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  background: rgba(26,20,16,.42); color: #fffdf8; text-align: center; pointer-events: none;
}
.atlas-building b { font-size: 22px; letter-spacing: .12em; }
.atlas-building span { font-size: 13px; opacity: .9; }
.atlas-bg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; pointer-events: none; }
.atlas-toy { position: absolute; transform: translate(-50%, -100%); z-index: 2; }
.atlas-toy.ready .capsule-letter { animation: jar-glow 1.6s ease-in-out infinite; }
.atlas-toy.sealed .capsule-letter { filter: saturate(.92); }
.capsule-letter {
  position: relative; width: 100%; aspect-ratio: 5 / 4; pointer-events: none;
  filter: drop-shadow(0 2px 2px rgba(40,24,8,.28));
}
.capsule-letter .sheet {
  position: absolute; inset: 18% 6% 4% 6%;
  background: linear-gradient(180deg, #fff8ee, #f3e0c4);
  border: 2px solid #c9a06a; border-radius: 3px 3px 5px 5px;
}
.capsule-letter .flap {
  position: absolute; left: 8%; right: 8%; top: 2%; height: 42%;
  background: linear-gradient(180deg, #f7d7a4, #e8b56a);
  border: 2px solid #c4843d;
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}
.atlas-toy.ready .capsule-letter .flap { transform: translateY(-12%); }

.atlas-toy .toy, .atlas-toy .blades, .atlas-toy .fabric { width: 100%; display: block; pointer-events: none; position: relative; z-index: 2; }
.atlas-toy .stick { position: absolute; inset: 0; width: 100%; z-index: 1; pointer-events: none; }
.atlas-toy .pole { position: absolute; inset: 0; width: 100%; z-index: 3; pointer-events: none; }
.atlas-toy.flip .toy { transform: scaleX(-1); }
.atlas-toy.spin-wheel .blades { transform-origin: 49.5% 43.3%; animation: spin-hub 2.8s linear infinite; }
@keyframes spin-hub { to { transform: rotate(360deg); } }
.atlas-toy.glow .toy { animation: jar-glow 1.6s ease-in-out infinite; }
@keyframes jar-glow { 50% { filter: brightness(1.35) drop-shadow(0 0 6px #f5d76a); } }
.atlas-toy.wave .fabric { transform-origin: 16% 38%; animation: flag-flutter 1.7s ease-in-out infinite; }
@keyframes flag-flutter { 0%,100% { transform: scaleX(1); } 35% { transform: scaleX(.76); } 70% { transform: scaleX(1.06); } }
.atlas-buddy { position: absolute; transform: translate(-50%, -100%); z-index: 5; filter: drop-shadow(0 2px 3px rgba(0,0,0,.3)); pointer-events: none; }
.atlas-plane { position: absolute; width: 10%; top: 28%; left: -12%; animation: plane-fly 4.5s linear infinite; z-index: 6; }
@keyframes plane-fly { to { left: 110%; top: 18%; } }
.atlas-star { position: absolute; left: 18%; top: 14%; color: #ffe9a8; font-size: 18px; filter: drop-shadow(0 0 6px #ffe9a8); }
.atlas-stage.moon-full::after {
  content: "";
  position: absolute;
  left: 86.5%;
  top: 12.6%;
  width: 7.2%;
  aspect-ratio: 1;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  box-shadow: 0 0 22px 10px rgba(255, 244, 210, .45);
  animation: moon-glow 2.4s ease-in-out infinite;
}
@keyframes moon-glow {
  0%, 100% { opacity: .55; box-shadow: 0 0 16px 8px rgba(255, 244, 210, .32); }
  50% { opacity: 1; box-shadow: 0 0 28px 14px rgba(255, 244, 210, .55); }
}
.atlas-cell-face { width: 48px; height: 48px; object-fit: contain; }
.atlas-sil { width: 48px; height: 48px; margin: 0 auto; border-radius: 50%; background: var(--ink); opacity: .18; }
.base-head { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.base-head > span:first-child { display: inline-flex; align-items: center; gap: 6px; }
.dust-chip {
  display: inline-flex; align-items: center; font-size: 14px; font-weight: 700;
  background: var(--warm-2); color: var(--accent-ink); padding: 4px 12px; border-radius: 999px;
}
.toy-shop-dust { margin: 0 0 12px; }
.toy-shop-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin: 8px 0 14px; }
.toy-shop-card {
  display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center;
  background: var(--surface-2); border-radius: var(--radius-lg); padding: 12px 8px;
}
.toy-shop-card img { width: 72px; height: 72px; object-fit: contain; }
.toy-shop-card.have { opacity: .55; }
.toy-shop-card b { font-size: 14px; }
.toy-shop-card span { font-size: 12px; color: var(--ink-2); }
.atlas-shop-hint { margin: 8px 0 0; font-size: 13px; }
</style>
