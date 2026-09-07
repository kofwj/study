<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, defineAsyncComponent } from 'vue'
import { api } from './api.js'
import { APP_LABEL, APP_REVISION } from './version.js'
// ponytail: 家长后台（1147 行）单独切 chunk，孩子端首屏不加载
const Admin = defineAsyncComponent(() => import('./Admin.vue'))
import { SUBJECT_ICONS as ICONS, rankIcon, achIcon } from './icons.js'
import { tagHelp } from './tagHelp.js'
import { Sun, Lock, Gift, Check, TrendingUp, Target, User, ShoppingCart, ScrollText, Medal, ChartColumn, Map, CalendarDays, RefreshCw, PartyPopper, Sparkles, BookOpen, Flame } from '@lucide/vue'

const data = reactive({
  level: { earned: 0, balance: 0, level: '阳光萌新', next: null, next_need: 0, progress: 0 },
  streak: 0,
  kid_name: '乐乐',
  kid_id: '',
  today: '',
  cursors: {},
  today_checkin: false,
  subjects: [],
  units: [],
  tasks: [],
  daily: [],
  unit_scores: {},
  test_fail_score: 80,
  fitness_goals: {},
  weak_tags: {},
})
const rewards = ref([])
const loading = ref(true)
const err = ref('')
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
onBeforeUnmount(() => topbarObserver?.disconnect())
const toast = ref('')
const shopOpen = ref(false)
const myRedeems = ref([])
const achievements = ref([])
const achOpen = ref(false)
const boxes = ref({ avail: 0, opened: 0, earned: 0, streak: 0 })
const boxOpen = ref(false)
const boxResult = ref(null)
const rankMapOpen = ref(false)
const rankMap = ref(null)
const reviewDue = ref([])
const updateReady = ref(false)
const celebrate = ref(null)
const chartOpen = reactive({ open: false, task: null, history: [] })
const renaming = ref(false)
const renameVal = ref('')

let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2800)
}
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
function n1(v) {
  if (v == null) return ''
  const x = Math.round(Number(v) * 10) / 10
  return x % 1 ? String(x) : String(Math.round(x))
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

const isAdmin = ref(false)
const me = ref(null)
const authed = ref(false)
const mustChangePin = ref(false)
const newPin = ref('')
const newPin2 = ref('')
const pinForm = reactive({ mode: 'login', account: 'lele', val: '', name: '', family: '我家', code: '' })
async function afterLogin(r) {
  me.value = r
  pinForm.val = ''
  authed.value = true
  isAdmin.value = r.role === 'parent'
  mustChangePin.value = !!(r.force_pin_change && r.role === 'parent')
  if (!isAdmin.value) await refresh()
}
async function doChangePin() {
  const p = newPin.value.trim()
  if (p.length < 8) { showToast('家长密码至少 8 位'); return }
  if (p !== newPin2.value) { showToast('两次输入不一致'); return }
  try {
    await api.admin.changePin(p)
    mustChangePin.value = false
    newPin.value = ''; newPin2.value = ''
    me.value = await api.me().catch(() => me.value)
    showToast('密码已更新')
  } catch (e) { showToast(e.message) }
}
async function verifyPin() {
  try {
    if (pinForm.mode === 'register') {
      await afterLogin(await api.register({ account: pinForm.account, pin: pinForm.val, name: pinForm.name, family_name: pinForm.family }))
    } else if (pinForm.mode === 'join') {
      await afterLogin(await api.join({ account: pinForm.account, pin: pinForm.val, name: pinForm.name, code: pinForm.code }))
    } else {
      await afterLogin(await api.login(pinForm.account, pinForm.val))
    }
  } catch (e) { showToast(e.message) }
}
function exitAdmin() {
  isAdmin.value = false
  refresh()
}
async function openParent() {
  if (me.value && me.value.role === 'parent') {
    isAdmin.value = true
    return
  }
  await api.logout().catch(() => {})
  me.value = null
  authed.value = false
  pinForm.mode = 'login'
  pinForm.account = 'parent'
  pinForm.val = ''
}
async function doLogout() {
  await api.logout().catch(() => {})
  me.value = null
  isAdmin.value = false
  authed.value = false
  pinForm.mode = 'login'
  pinForm.account = 'lele'
  pinForm.val = ''
}

async function refresh() {
  try {
    const [t, r, bx, rv] = await Promise.all([api.tasks(), api.rewards(), api.boxes(), api.reviewDue().catch(() => [])])
    const prevId = data.level && data.level.level_id
    const prevEarned = data.level && (data.level.earned || 0)
    Object.assign(data, t)
    // 升级检测：等级变了且累计阳光增加了才庆祝（取消扣回导致的降级不庆祝）
    if (prevId && t.level.level_id !== prevId && t.level.earned >= prevEarned) {
      celebrate.value = { icon: t.level.level_icon || '', name: t.level.level }
      setTimeout(() => (celebrate.value = null), 2800)
    }
    rewards.value = r
    boxes.value = bx
    reviewDue.value = rv || []
    err.value = ''
  } catch (e) {
    if (e.status === 401) { me.value = null; authed.value = false }
    err.value = e.message
  } finally {
    loading.value = false
  }
}

async function checkin() {
  try {
    const r = await api.checkin()
    showToast('已签到，开始学习吧！' + milestoneTxt(r.milestone))
    await refresh()
  } catch (e) { showToast(e.message) }
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
  try {
    if (task.done) {
      await api.cancel(task.id)
      showToast('已取消，扣回阳光')
    } else {
      const r = await api.complete(task.id)
      if (event) flyPlus(event.clientX, event.clientY, `+${r.delta} 阳光`)
      showToast(`太棒了！完成【${task.title}】+${r.delta} 阳光` + milestoneTxt(r.milestone))
    }
    await refresh()
  } catch (e) { showToast(e.message) }
}

async function openChart(task) {
  try {
    const hist = await api.dailyHistory(task.id)
    chartOpen.task = task
    chartOpen.history = hist
    chartOpen.open = true
  } catch (e) { showToast(e.message) }
}
// 为某维度算趋势折线坐标 + 个人纪录定位
function lineFor(m) {
  const hist = (chartOpen.history || []).filter(h => h.metrics && h.metrics[m.id] != null && h.metrics[m.id] !== '')
  const vals = hist.map(h => Number(h.metrics[m.id]))
  if (!vals.length) return { pts: '', dots: [], min: '—', max: '—', bestY: 0 }
  const min = Math.min(...vals), max = Math.max(...vals)
  const span = (max - min) || 1
  const W = 288, H = 92, padL = 14, padR = 14, padT = 12, padB = 20
  const n = vals.length
  const bestVal = m.direction === 'lower_better' ? min : max
  const dots = vals.map((v, i) => {
    const x = n === 1 ? (W - padL - padR) / 2 + padL : padL + i * (W - padL - padR) / (n - 1)
    const y = padT + (1 - (v - min) / span) * (H - padT - padB)
    return { x: +x.toFixed(1), y: +y.toFixed(1), v, best: v === bestVal }
  })
  const bestY = dots.find(p => p.best).y
  return { pts: dots.map(p => `${p.x},${p.y}`).join(' '), dots, min, max, bestY,
           sum: vals.reduce((a, b) => a + b, 0), count: n }
}
// 无数值维度任务（眼保健操/阅读/练字）：近 14 天打卡日历
const chartDays = computed(() => {
  const done = new Set((chartOpen.history || []).map(h => h.date))
  const days = []
  const now = new Date()
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    days.push({ date: iso, daynum: d.getDate(), done: done.has(iso), today: i === 0 })
  }
  return days
})
const dailyDialog = reactive({ open: false, task: null, vals: {} })
function openDaily(task) {
  if (task.done_today) return
  dailyDialog.task = task
  dailyDialog.vals = {}
  for (const m of task.metrics) dailyDialog.vals[m.id] = ''
  dailyDialog.open = true
}
async function submitDaily(event) {
  const metrics = {}
  for (const m of dailyDialog.task.metrics) {
    const v = Number(dailyDialog.vals[m.id])
    if (v && !Number.isNaN(v)) metrics[m.id] = v
  }
  try {
    const r = await api.complete(dailyDialog.task.id, metrics)
    if (event) flyPlus(event.clientX, event.clientY, `+${r.delta} 阳光`)
    showToast((r.bonus > 0 ? `完成 +${r.delta} 阳光（破纪录 +${r.bonus}！）` : `完成【${dailyDialog.task.name}】+${r.delta} 阳光`) + milestoneTxt(r.milestone))
    dailyDialog.open = false
    await refresh()
  } catch (e) { showToast(e.message) }
}
async function cancelDaily(task) {
  try {
    await api.cancel(task.id)
    showToast('已取消，扣回阳光')
    await refresh()
  } catch (e) { showToast(e.message) }
}

async function redeem(reward) {
  try {
    const r = await api.redeem(reward.id)
    showToast(`已提交「${reward.name}」，等家长同意`)
    shopOpen.value = false
    await refresh()
  } catch (e) { showToast(e.message) }
}
async function openShop() {
  shopOpen.value = true
  try { myRedeems.value = await api.redemptions() } catch {}
}
const STATUS_TXT = { pending: '等家长同意', done: '已兑换', delivered: '已兑现' }
const milestoneTxt = (m) => (m && m.length) ? m.map(([d, b]) => ` · 连续 ${d} 天 +${b} 阳光`).join('') : ''
async function openAch() {
  achOpen.value = true
  try { achievements.value = await api.achievements() } catch {}
}
async function openBox() {
  if (boxes.value.avail <= 0) {
    const need = (boxes.value.earned + 1) * 3 - boxes.value.streak
    showToast(`再连续打卡 ${Math.max(1, need)} 天解锁下一个宝箱！`)
    return
  }
  try {
    const r = await api.openBox()
    boxResult.value = r.delta
    boxOpen.value = true
    await refresh()
  } catch (e) { showToast(e.message) }
}
async function openRankMap() {
  rankMapOpen.value = true
  try { rankMap.value = await api.ranks() } catch {}
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
const dailyTodo = computed(() => data.daily.filter(d => !d.done_today))
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
const todayRemaining = computed(() => reviewDue.value.length + dailyTodo.value.length + studyNext.value.length)
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
const SUBJECT_ORDER = ['语文', '数学', '英语', '科学', '道法', '体育', '音美', '综合', '围棋']
const orderedSubjects = computed(() => {
  // 只显示有内容的学科（单元任务或每日任务），空的（科学/道法/音美/综合）先隐藏，补目录后自动出现
  const list = data.subjects.filter(s => (subjectProgress.value[s.id] || {}).total > 0)
  list.sort((a, b) => SUBJECT_ORDER.indexOf(a.id) - SUBJECT_ORDER.indexOf(b.id))
  return list
})
const activeTab = ref('今日推荐')
const currentUnits = computed(() => bySubject.value[activeTab.value]?.units || [])

onMounted(async () => {
  window.addEventListener('sw-update', () => { updateReady.value = true })
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
  <Admin v-if="isAdmin && !mustChangePin" @exit="exitAdmin" @switched="refresh" />
  <div v-else-if="isAdmin && mustChangePin" class="login-screen">
    <div class="login-card">
      <div class="login-logo"><Lock class="ico" :size="36" /></div>
      <h1>改一下家长密码</h1>
      <p class="login-sub">家长密码现在至少 8 位，改完才能继续。</p>
      <input v-model="newPin" type="password" placeholder="新密码（至少 8 位）" autocomplete="new-password" />
      <input v-model="newPin2" type="password" placeholder="再输一遍确认" autocomplete="new-password" @keyup.enter="doChangePin" />
      <button class="login-enter" @click="doChangePin">保存新密码</button>
      <p v-if="toast" class="login-note danger">{{ toast }}</p>
    </div>
  </div>
  <div v-else-if="authed" class="desk" :style="{ '--topbar-height': topbarHeight + 'px', '--update-bar-height': updateBarHeight + 'px' }">
    <button v-if="updateReady" ref="updateBarEl" type="button" class="update-bar" @click="reloadApp"><RefreshCw class="ico" :size="15" /> 有新版本，点我刷新</button>
    <div v-if="toast" class="toast-note global-toast" role="status">{{ toast }}</div>
    <!-- 蓝顶栏 -->
    <header ref="topbarEl" class="topbar">
      <div class="who">
        <div class="avatar" :style="{ background: avatarBg }">{{ avatarLetter }}</div>
        <div>
          <div class="hello">{{ data.today || '今天' }}</div>
          <div class="hello greet-long">你好呀，五年级的小主人！</div>
          <div class="name-row">
            <b class="kid">{{ data.kid_name }}</b>
          </div>
        </div>
      </div>
      <div class="pills">
        <span class="pill sun"><i></i> {{ data.level.balance }}</span>
        <span class="pill fire"><Flame class="ico" :size="15" /> 连续打卡 {{ data.streak }} 天</span>
        <button class="pill star" @click="openRankMap"><component :is="rankIcon(data.level.level_icon)" class="ico" :size="15" /> {{ data.level.level }}</button>
        <button class="pill ach" @click="openAch"><Medal class="ico" :size="15" /> 成就</button>
        <button class="pill box" :class="{ ready: boxes.avail > 0 }" @click="openBox">
          <Gift class="ico" :size="15" /> {{ boxes.avail > 0 ? '宝箱 ×' + boxes.avail : '宝箱' }}
        </button>
      </div>
      <div class="next">
        <span v-if="data.level.next">
          <component :is="rankIcon(data.level.level_icon)" class="ico" :size="14" /> {{ data.level.level }}
          · 再得 {{ data.level.next_need - data.level.earned }} <Sun class="ico sun" :size="13" /> 升级 <component :is="rankIcon(data.level.next_icon)" class="ico" :size="14" /> {{ data.level.next }}
        </span>
        <span v-else><component :is="rankIcon(data.level.level_icon)" class="ico" :size="14" /> 已是最高等级！</span>
        <div class="next-bar"><i :style="{ width: data.level.progress + '%' }"></i></div>
      </div>
    </header>

    <div class="body">
      <!-- 左栏 -->
      <aside class="side">
        <button class="nav" :class="{ on: activeTab === '今日推荐' }" @click="activeTab = '今日推荐'">
          <span><Sparkles class="ico" :size="15" /> 今日推荐</span>
        </button>
        <button v-for="s in orderedSubjects" :key="s.id" class="nav"
          :class="{ on: activeTab === s.id }" @click="activeTab = s.id">
          <span><component :is="ICONS[s.id] || BookOpen" class="ico" :size="15" /> {{ s.name }}</span>
          <em>{{ subjectProgress[s.id]?.done || 0 }}/{{ subjectProgress[s.id]?.total || 0 }}</em>
        </button>
      </aside>

      <!-- 右栏 -->
      <main class="main">
        <template v-if="activeTab === '今日推荐'">
          <h1><Sparkles class="ico" :size="20" /> 今天怎么做</h1>
          <p class="hint">按顺序做就行。每完成一项，点圆圈领取阳光。</p>
          <div class="today-summary">
            <div class="today-progress">
              <strong v-if="todayRemaining">今天还有 {{ todayRemaining }} 项</strong>
              <strong v-else>今天安排的事都完成了</strong>
              <div class="today-breakdown">
                <span v-if="reviewDue.length">复习 {{ reviewDue.length }} 项</span>
                <span v-if="dailyTodo.length">打卡 {{ dailyTodo.length }} 项</span>
                <span v-if="studyNext.length">学习 {{ studyNext.length }} 项</span>
              </div>
            </div>
            <button class="cta check" :disabled="data.today_checkin" @click="checkin">
              <CalendarDays class="ico" :size="16" /> {{ data.today_checkin ? '今日已签到' : '每日签到' }}
            </button>
          </div>

          <section v-if="reviewDue.length" class="plan-section review-today">
            <div class="plan-head">
              <span class="plan-step">先做</span>
              <div>
                <h2><BookOpen class="ico" :size="18" /> 到期复习</h2>
                <p>每项照练习册做一遍，再告诉家长结果。</p>
              </div>
            </div>
            <div class="plan-list">
              <article v-for="x in reviewDue" :key="x.id" class="plan-row review-card enter">
                <div class="plan-row-main">
                  <span class="plan-subject">{{ x.subject_id }}</span>
                  <div><strong>{{ x.tag_name }}</strong><small>{{ x.unit_name }} · 第 {{ (x.interval_idx || 0) + 1 }} 次</small><small class="plan-review-help">{{ tagHelp(x) }}</small></div>
                </div>
                <span class="plan-state">做完告诉家长</span>
              </article>
            </div>
          </section>

          <section v-if="dailyTodo.length" class="plan-section">
            <div class="plan-head">
              <span class="plan-step">然后</span>
              <div><h2><RefreshCw class="ico" :size="18" /> 每日打卡</h2><p>把今天要坚持的事做完。</p></div>
            </div>
            <div class="grid plan-grid">
              <div v-for="d in dailyTodo" :key="d.id" class="card enter">
                <button class="circle" @click="openDaily(d)">○</button>
                <div class="card-body">
                  <div class="card-title">{{ d.name }}</div>
                  <div v-if="d.note" class="card-detail">{{ d.note }}</div>
                  <template v-if="fitnessBar(d)">
                    <div class="fit-bar"><i :style="{ width: fitnessBar(d).pct + '%' }"></i><em>{{ fitnessBar(d).status }}</em></div>
                    <div class="fit-std">{{ fitnessBar(d).lines }}</div>
                  </template>
                  <div class="plus">{{ d.subject_id || '体育' }} · +{{ d.sunshine || 5 }} <Sun class="ico sun" :size="12" /></div>
                </div>
                <button class="trend" @click="openChart(d)" title="看趋势"><TrendingUp :size="15" /></button>
              </div>
            </div>
          </section>

          <section v-if="studyNext.length" class="plan-section">
            <div class="plan-head">
              <span class="plan-step">最后</span>
              <div><h2><BookOpen class="ico" :size="18" /> 本课下一步</h2><p>每科先做一项，做完后会自动出现下一项。</p></div>
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

        <template v-else>
          <h1><component :is="ICONS[activeTab] || BookOpen" class="ico" :size="20" /> {{ activeTab }}</h1>
          <p class="hint">完成一项 +5 <Sun class="ico sun" :size="13" />，再点一次会扣回。</p>

          <div class="unit" v-if="data.daily.some(x => x.subject_id === activeTab)">
            <h2><i></i> 每日打卡</h2>
            <div class="grid">
              <div v-for="d in data.daily.filter(x => x.subject_id === activeTab)" :key="d.id"
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
                  <div class="plus">+{{ d.sunshine }} <Sun class="ico sun" :size="12" /></div>
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
                <button class="circle" :class="{ ok: t.done || t.past }" @click="toggleTask(t, $event)"><Check v-if="t.done || t.past" :size="15" /><Lock v-else-if="t.locked" :size="14" /></button>
                <div class="card-body">
                  <div class="card-title">{{ t.title }}</div>
                  <div v-if="t.detail" class="card-detail">{{ t.detail }}</div>
                  <div class="plus"><template v-if="t.past">已学过</template><template v-else-if="t.locked">未解锁</template><template v-else>+{{ t.sunshine }} <Sun class="ico sun" :size="12" /></template></div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!currentUnits.length && !data.daily.some(x => x.subject_id === activeTab)" class="empty">
            这科还没任务，家长可以在家长端「任务」里补充。
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

    <!-- 商店抽屉 -->
    <div v-if="shopOpen" class="mask" @click.self="shopOpen = false">
      <div class="shop-modal enter">
        <h3><ShoppingCart class="ico" :size="18" /> 阳光兑换商店</h3>
        <div class="shop-list">
          <div v-for="r in rewards" :key="r.id" class="shop-item">
            <div>
              <div class="shop-name">{{ r.name }} · 需家长同意</div>
              <div class="shop-price"><Sun class="ico sun" :size="14" /> {{ r.price }}</div>
            </div>
            <button class="do" :disabled="data.level.balance < r.price" @click="redeem(r)">申请</button>
          </div>
        </div>
        <div v-if="myRedeems.length" class="redeem-hist">
          <h4><ScrollText class="ico" :size="15" /> 兑换记录</h4>
          <div v-for="rd in myRedeems" :key="rd.id" class="redeem-row">
            <span>{{ rd.name }}</span>
            <span class="dim-s">-{{ rd.price }} <Sun class="ico sun" :size="12" /></span>
            <span :class="{ wait: rd.status === 'pending' }">{{ STATUS_TXT[rd.status] || rd.status }}</span>
          </div>
        </div>
        <button class="ghost" @click="shopOpen = false">关闭</button>
      </div>
    </div>

    <!-- 跳绳弹窗 -->
    <div v-if="dailyDialog.open" class="mask" @click.self="dailyDialog.open = false">
      <div class="shop-modal enter">
        <h3>{{ dailyDialog.task.name }}</h3>
        <p v-if="dailyDialog.task.note" class="daily-dialog-note">怎么做：{{ dailyDialog.task.note }}</p>
        <div v-for="m in dailyDialog.task.metrics" :key="m.id" class="metric">
          <label>{{ m.label }}（{{ m.unit }}）</label>
          <div v-if="m.note" class="metric-note">{{ m.note }}</div>
          <input v-model.number="dailyDialog.vals[m.id]" type="number" inputmode="decimal" :placeholder="m.unit" />
        </div>
        <button class="do big" @click="submitDaily($event)">打卡，赚阳光 <Sun class="ico" :size="15" /></button>
        <button class="ghost" @click="dailyDialog.open = false">取消</button>
      </div>
    </div>

    <!-- 跳绳趋势 -->
    <div v-if="chartOpen.open" class="mask" @click.self="chartOpen.open = false">
      <div class="shop-modal chart-modal">
        <h3><TrendingUp class="ico" :size="18" /> {{ chartOpen.task?.name }} 成长趋势</h3>

        <div v-if="!chartOpen.history.length" class="dim-s">还没打过卡，坚持一下吧！</div>

        <!-- 有数值维度：折线图 + 个人纪录 -->
        <template v-if="chartOpen.history.length && (chartOpen.task?.metrics || []).length">
          <div v-for="m in chartOpen.task.metrics" :key="m.id" class="chart-block">
            <div class="chart-head">
              <span class="chart-title">{{ m.label }}</span>
              <span class="chart-scale">{{ lineFor(m).min }} ~ {{ lineFor(m).max }} {{ m.unit }}</span>
            </div>
            <svg viewBox="0 0 288 92" class="chart-svg" preserveAspectRatio="none">
              <line v-if="lineFor(m).dots.length" x1="14" :y1="lineFor(m).bestY" x2="274" :y2="lineFor(m).bestY" class="chart-pb-line" />
              <polyline :points="lineFor(m).pts" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              <circle v-for="(p, i) in lineFor(m).dots" :key="i" :cx="p.x" :cy="p.y" :r="p.best ? 5 : 3.5" :fill="p.best ? 'var(--danger)' : 'var(--accent)'" stroke="#fff" stroke-width="1.5">
                <title>{{ p.v }}{{ m.unit }}</title>
              </circle>
            </svg>
            <div class="chart-pb"><Medal class="ico" :size="13" /> 个人纪录 {{ chartOpen.task.pb?.[m.id] ?? '—' }} {{ m.unit }} · <ChartColumn class="ico" :size="13" /> 累计 {{ lineFor(m).sum }} {{ m.unit }} · 共 {{ lineFor(m).count }} 次</div>
          </div>
        </template>

        <!-- 无数值维度：打卡日历 -->
        <template v-else-if="chartOpen.history.length">
          <div class="cal-block">
            <div class="chart-head">
              <span class="chart-title">坚持打卡</span>
              <span class="chart-scale">共打卡 {{ chartOpen.history.length }} 次</span>
            </div>
            <div class="cal-row">
              <div v-for="d in chartDays" :key="d.date" class="cal-cell" :class="{ on: d.done, today: d.today }">
                {{ d.daynum }}
              </div>
            </div>
            <div class="cal-legend">近 14 天 · 绿色=已打卡 · 橙色框=今天</div>
          </div>
        </template>

        <button class="ghost" @click="chartOpen.open = false">关闭</button>
      </div>
    </div>

    <p v-if="err" class="err">{{ err }}</p>

    <!-- +N 阳光飞出 -->
    <div v-for="f in floaters" :key="f.id" class="floater" :style="{ left: f.x + 'px', top: f.y + 'px' }">{{ f.text }}</div>

    <!-- 升级庆祝 -->
    <div v-if="celebrate" class="celebrate">
      <div class="confetti">
        <span v-for="i in 14" :key="i" :style="{ left: (i * 7.1) + '%', animationDelay: (i * 0.09) + 's' }">•</span>
      </div>
      <div class="celebrate-card">
        <div class="celebrate-icon"><component :is="rankIcon(celebrate.icon)" class="ico" :size="40" /></div>
        <div class="celebrate-title"><PartyPopper class="ico" :size="16" /> 升级啦！</div>
        <div class="celebrate-name"><component :is="rankIcon(celebrate.icon)" class="ico" :size="18" /> {{ celebrate.name }}</div>
      </div>
    </div>

    <!-- 成就墙 -->
    <div v-if="achOpen" class="mask" @click.self="achOpen = false">
      <div class="shop-modal ach-modal">
        <h3><Medal class="ico" :size="18" /> 我的成就</h3>
        <div class="ach-grid">
          <div v-for="a in achievements" :key="a.id" class="ach-cell" :class="{ on: a.earned }">
            <div class="ach-icon"><component :is="achIcon(a.icon)" class="ico" :size="24" /></div>
            <div class="ach-name">{{ a.name }}</div>
            <div class="ach-prog">{{ Math.min(a.current, a.target) }}/{{ a.target }}</div>
          </div>
        </div>
        <button class="ghost" @click="achOpen = false">关闭</button>
      </div>
    </div>

    <!-- 连击宝箱 -->
    <div v-if="boxOpen" class="mask" @click.self="boxOpen = false">
      <div class="shop-modal box-modal">
        <h3><Gift class="ico" :size="18" /> 连击宝箱</h3>
        <div class="box-result">
          <div class="box-icon"><Gift :size="34" /></div>
          <div class="box-gain">+{{ boxResult }} <Sun class="ico sun" :size="16" /></div>
          <div class="box-tip">太棒了，坚持打卡的奖励！</div>
        </div>
        <button class="do big" @click="boxOpen = false">收下奖励</button>
      </div>
    </div>

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

  <div v-else class="login-screen">
    <div class="login-card">
      <div class="login-logo"><Sun class="ico" :size="36" /></div>
      <h1>阳光学习工作台</h1>
      <p class="login-sub">孩子的每日学习打卡小助手</p>
      <p class="login-ver" :title="APP_REVISION">{{ APP_LABEL }}</p>
      <div class="login-tabs">
        <button type="button" :class="{ on: pinForm.mode==='login' }" @click="pinForm.mode='login'">登录</button>
        <button type="button" :class="{ on: pinForm.mode==='register' }" @click="pinForm.mode='register'">注册新家</button>
        <button type="button" :class="{ on: pinForm.mode==='join' }" @click="pinForm.mode='join'">邀请码加入</button>
      </div>
      <input v-model="pinForm.account" placeholder="账号" autocomplete="username" />
      <input v-model="pinForm.val" type="password" :placeholder="pinForm.mode==='login' ? '密码' : '家长密码至少 8 位'" autocomplete="current-password" @keyup.enter="verifyPin" />
      <input v-if="pinForm.mode!=='login'" v-model="pinForm.name" placeholder="你的名字" />
      <input v-if="pinForm.mode==='register'" v-model="pinForm.family" placeholder="家庭名（如：乐乐的家）" />
      <input v-if="pinForm.mode==='join'" v-model="pinForm.code" placeholder="邀请码" />
      <button class="login-enter" @click="verifyPin">进入</button>
      <p class="login-note">
        <template v-if="pinForm.mode==='register'">注册就是为你家开一个独立空间，不需要邀请码。</template>
        <template v-else-if="pinForm.mode==='join'">邀请码由家庭里已有的家长在设置页生成。</template>
        <template v-else>孩子用 4 位密码；家长注册/改密至少 8 位。</template>
      </p>
      <p v-if="toast" class="login-note danger">{{ toast }}</p>
    </div>
  </div>
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
.who { display: flex; align-items: center; gap: 10px; min-width: 180px; }
.avatar {
  width: 52px; height: 52px; border-radius: 50%; background: var(--accent);
  color: #fff; font-weight: 800; font-size: 22px; letter-spacing: 0;
  display: flex; align-items: center; justify-content: center;
  flex: 0 0 52px; aspect-ratio: 1; overflow: hidden;
  border: 3px solid rgba(255,255,255,.72); box-shadow: 0 3px 0 rgba(122,77,3,.16);
}
.hello { font-size: 12px; opacity: .92; }
.kid { font-size: 22px; font-weight: 850; }
.name-row { display: flex; align-items: center; gap: 8px; }
.rename { background: none; border: none; color: rgba(255,255,255,.85); font-size: 12px; cursor: pointer; }
.name-row input { width: 90px; border: none; border-radius: 8px; padding: 4px 8px; }

.pills { display: flex; gap: 10px; flex: 1; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,.24); border: 1px solid rgba(255,255,255,.2);
  border-radius: 22px; padding: 8px 16px;
  font-weight: 800; font-size: 15px; display: inline-flex; align-items: center; gap: 6px;
  box-shadow: 0 2px 0 rgba(20,70,110,.12);
}
.pill.sun { background: var(--accent); color: var(--accent-ink); border-color: rgba(255,255,255,.45); }
.pill.sun i {
  width: 16px; height: 16px; border-radius: 50%; background: #fff7cf; display: inline-block;
}
.next { margin-left: auto; text-align: right; font-size: 13px; min-width: 180px; }
.next-bar { height: 6px; background: rgba(255,255,255,.35); border-radius: 4px; margin-top: 6px; overflow: hidden; }
.next-bar i { display: block; height: 100%; background: var(--accent); }

.cta {
  border: none; border-radius: 22px; padding: 11px 22px; font-weight: 800; font-size: 15px; cursor: pointer;
}
.cta.check {
  background: var(--accent); color: var(--accent-ink);
  box-shadow: 0 4px 0 rgba(122,77,3,.18);
}
.cta.check:not(:disabled):hover { box-shadow: 0 6px 0 rgba(122,77,3,.18); }
.cta.check:not(:disabled):active { box-shadow: 0 2px 0 rgba(122,77,3,.18); }
.cta.check:disabled { background: var(--warm); color: var(--ink-3); cursor: default; }
.toast-note {
  background: var(--ink); color: #fff; border-radius: 999px; padding: 9px 16px;
  font-size: 13px; font-weight: 700; box-shadow: var(--sh-2);
}
.global-toast {
  position: fixed; left: 50%; bottom: calc(78px + 16px + env(safe-area-inset-bottom));
  z-index: 35; max-width: min(90vw, 520px); transform: translateX(-50%);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; animation: enter .25s var(--ease) both;
}

.body { display: flex; gap: 18px; padding: 18px 22px; align-items: flex-start; }
.side {
  width: 196px; flex: 0 0 196px; background: var(--surface); border-radius: 22px; padding: 10px;
  box-shadow: 0 8px 24px rgba(60,120,170,.08); border: 2px solid var(--line);
  position: sticky; top: calc(var(--topbar-height, 0px) + 18px); max-height: calc(100dvh - var(--topbar-height, 0px) - 36px); overflow-y: auto; z-index: 5;
}
.nav {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  border: none; background: none; padding: 11px 12px; border-radius: 14px;
  color: var(--ink-2); font-size: 15px; cursor: pointer; margin-bottom: 2px;
}
.nav em { font-style: normal; font-size: 12px; color: var(--ink-3); background: var(--surface-2); padding: 2px 8px; border-radius: 10px; }
.nav.on {
  background: var(--warm); color: var(--accent-ink); font-weight: 800;
  border-left: 4px solid var(--accent); padding-left: 8px;
}
.nav.on em { background: var(--line); color: var(--brand-deep); }

.main { flex: 1; min-width: 0; }
.main h1 { margin: 4px 0 6px; font-size: 28px; }
.main h1 .ico { color: var(--accent); }
.hint { color: var(--ink-3); font-size: 13px; margin: 0 0 16px; }
.unit { margin-bottom: 22px; }
.unit h2 {
  margin: 0 0 10px; font-size: 16px; color: var(--brand-deep); display: flex; align-items: center; gap: 8px;
}
.unit h2 i { width: 4px; height: 16px; background: var(--brand); border-radius: 2px; display: inline-block; }
.unit-score { font-size: 11px; padding: 2px 9px; border-radius: 10px; font-weight: 800; margin-left: 4px; white-space: nowrap; }
.unit-score.gold { background: var(--warm); color: var(--accent-ink); }
.unit-score.green { background: var(--ok-bg); color: var(--ok); }
.unit-score.blue { background: var(--surface-2); color: var(--brand-deep); }
.unit-score.gray { background: var(--surface-2); color: var(--ink-3); }
.unit-weak, .unit-review-status { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 800; background: var(--warm); color: var(--accent-ink); }
.unit-review-status { background: var(--accent); color: var(--accent-ink); }
.today-summary {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin: 0 0 18px;
  padding: 12px 14px; border: 2px dashed var(--accent); border-radius: 16px;
  background: var(--warm-2); color: var(--ink-2);
}
.today-progress { flex: 1; min-width: 180px; }
.today-summary strong { display: block; color: var(--ink); }
.today-breakdown { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 3px; }
.today-breakdown span { font-size: 12px; padding-left: 8px; border-left: 1px solid var(--line); }
.plan-section { margin: 0 0 24px; }
.plan-section.review-today { padding: 14px; border: 1px solid var(--accent); border-radius: var(--r-card); background: var(--warm-2); }
.plan-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
.plan-step {
  flex: none; padding: 4px 9px; border-radius: 999px; background: var(--brand);
  color: #fff; font-size: 11px; font-weight: 800; box-shadow: 0 2px 0 rgba(31,127,176,.18);
}
.plan-head h2 { margin: 0; font-size: 16px; color: var(--ink); display: flex; align-items: center; gap: 6px; }
.plan-head p { margin: 4px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.5; }
.plan-list { display: flex; flex-direction: column; gap: 6px; }
.plan-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.plan-row-main { display: flex; align-items: center; gap: 9px; min-width: 0; }
.plan-row-main strong { display: block; font-size: 13px; color: var(--ink); }
.plan-row-main small { display: block; margin-top: 3px; color: var(--ink-3); font-size: 11px; }
.plan-row-main .plan-review-help { max-width: 620px; color: var(--ink-2); line-height: 1.45; }
.plan-subject { flex: none; color: var(--brand-deep); font-size: 11px; font-weight: 800; }
.plan-state { flex: none; color: var(--accent-ink); font-size: 11px; font-weight: 700; }
.plan-grid { grid-template-columns: repeat(3, 1fr); }
.plan-task-meta { margin-bottom: 4px; color: var(--brand-deep); font-size: 11px; font-weight: 700; }
.review-card { background: var(--surface); }
.review-card-meta { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-bottom: 5px; color: var(--ink-3); font-size: 11px; }
.review-card-meta .wp-round { margin-right: 0; }
.fit-bar { position: relative; height: 14px; background: var(--surface-2); border-radius: 8px; margin: 6px 0 4px; overflow: hidden; }
.fit-bar i { display: block; height: 100%; background: var(--brand); border-radius: 8px; }
.fit-bar em { position: absolute; inset: 0; font-style: normal; font-size: 10px; font-weight: 800; color: var(--ink-2); display: flex; align-items: center; justify-content: center; }
.fit-std { font-size: 11px; color: var(--ink-3); margin: 0 0 4px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.card {
  position: relative; background: var(--surface); border-radius: 20px; padding: 16px 14px 14px 14px;
  display: flex; gap: 10px; align-items: flex-start; min-height: 86px;
  box-shadow: var(--sh-card); border: 2px solid var(--line);
  transition: transform .18s var(--spring), box-shadow .18s var(--ease), border-color .18s var(--ease);
}
@media (hover: hover) {
  .card:not(.past):not(.locked):hover {
    transform: translateY(-3px) rotate(-.3deg);
    border-color: rgba(245,165,36,.55);
    box-shadow: 0 8px 18px rgba(60,120,170,.12);
  }
}
.card.done { background: var(--ok-bg); border-color: var(--ok-bg); }
.card.past { opacity: .55; }
.circle {
  width: 34px; height: 34px; border-radius: 50%; border: 2px dashed var(--brand);
  background: #fff; flex: 0 0 34px; cursor: pointer; color: #fff; font-weight: 800;
  transition: transform .18s var(--spring), background .18s var(--ease), border-color .18s var(--ease);
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
  background: var(--warm-2); border: 2px dashed rgba(245,165,36,.55); border-radius: 18px;
}

.foot {
  position: fixed; left: 0; right: 0; bottom: 0; background: var(--surface);
  display: flex; align-items: center; gap: 10px; padding: 12px 22px;
  box-shadow: 0 -4px 18px rgba(60,120,170,.08);
}
.foot-label {
  background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; color: var(--ink-3); font-size: 13px;
}
.foot-input {
  flex: 1; border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; font-size: 14px;
}
.foot-add { border: none; background: var(--brand); color: #fff; border-radius: 12px; padding: 10px 16px; font-weight: 800; cursor: pointer; }
.shop-fab {
  border: none; background: var(--accent); color: var(--accent-ink); border-radius: 22px; padding: 10px 18px;
  font-weight: 800; cursor: pointer; white-space: nowrap;
}
.app-ver {
  color: var(--ink-3); font-size: 11px; font-weight: 700; letter-spacing: .02em;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
.login-ver { margin: -8px 0 14px; color: var(--ink-3); font-size: 12px; font-weight: 700; }

.mask { position: fixed; inset: 0; background: rgba(20,40,60,.35); display: flex; align-items: center; justify-content: center; z-index: 20; padding: 12px; overflow: auto; }
.shop-modal { background: var(--surface); border-radius: var(--r-card); padding: 22px; width: min(92%, 420px); max-height: calc(100vh - 24px); max-height: calc(100dvh - 24px); overflow: auto; }
.shop-modal h3 { margin: 0 0 14px; }
.shop-list { display: flex; flex-direction: column; gap: 10px; }
.shop-item { display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
.shop-price { color: var(--accent); font-weight: 800; }
.redeem-hist { margin-top: 16px; border-top: 1px dashed var(--line); padding-top: 12px; }
.redeem-hist h4 { margin: 0 0 8px; font-size: 13px; color: var(--ink-3); }
.redeem-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; padding: 4px 0; }
.redeem-row .wait { color: var(--accent); font-weight: 700; }
.dim-s { color: var(--ink-3); }
.do { border: none; background: var(--brand); color: #fff; border-radius: 16px; padding: 8px 16px; font-weight: 800; cursor: pointer; }
.do:disabled { background: var(--line); cursor: default; }
.do.big { width: 100%; padding: 12px; margin-top: 8px; }
.ghost { width: 100%; margin-top: 8px; border: none; background: none; color: var(--ink-3); cursor: pointer; }
.metric { margin-bottom: 10px; }
.metric label { display: block; font-size: 13px; margin-bottom: 4px; }
.daily-dialog-note, .metric-note { margin: -4px 0 8px; color: var(--ink-3); font-size: 12px; line-height: 1.5; }
.metric-note { margin: -1px 0 4px; }
.trend { position: absolute; top: 8px; right: 8px; border: none; background: var(--warm); border-radius: 14px; padding: 3px 8px; font-size: 15px; cursor: pointer; line-height: 1; }
.chart-modal { max-width: 460px; max-height: 86vh; overflow-y: auto; }
.chart-block { margin-bottom: 12px; padding: 10px 12px; background: var(--surface-2); border-radius: 12px; }
.chart-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.chart-title { font-weight: 700; font-size: 14px; color: var(--ink); }
.chart-scale { font-size: 12px; color: var(--ink-3); }
.chart-svg { width: 100%; height: 92px; display: block; }
.chart-pb-line { stroke: var(--danger); stroke-width: 1.5; stroke-dasharray: 4 4; opacity: .55; }
.chart-pb { font-size: 12px; color: var(--accent-ink); margin-top: 6px; }
.cal-block { padding: 10px 12px; background: var(--surface-2); border-radius: 12px; }
.cal-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.cal-cell { width: 34px; height: 34px; border-radius: 8px; background: var(--surface-2); color: var(--ink-3); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; border: 2px solid transparent; }
.cal-cell.on { background: var(--ok); color: #fff; }
.cal-cell.today { border-color: var(--accent); }
.cal-legend { font-size: 11px; color: var(--ink-3); margin-top: 8px; }
.shop-modal input, .metric input { width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; font-size: 15px; }
.parent { border: none; background: none; color: var(--ink-3); font-size: 13px; font-weight: 700; cursor: pointer; padding: 10px 4px; white-space: nowrap; }
.err { color: var(--danger); text-align: center; }

/* 登录页 */
.login-screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; background: var(--bg); }
.login-card { background: var(--surface); border-radius: var(--r-card); padding: 32px 28px; width: 92%; max-width: 380px; box-shadow: var(--sh-2); text-align: center; }
.login-logo { width: 72px; height: 72px; margin: 0 auto 14px; border-radius: 50%; background: var(--warm); color: var(--accent); display: flex; align-items: center; justify-content: center; }
.login-card h1 { font-size: 22px; margin: 0 0 4px; }
.login-sub { color: var(--ink-3); font-size: 13px; margin: 0 0 18px; }
.login-tabs { display: flex; gap: 4px; margin-bottom: 16px; background: var(--surface-2); border-radius: 999px; padding: 4px; }
.login-tabs button { flex: 1; border: none; background: none; padding: 8px 4px; border-radius: 999px; font-size: 13px; color: var(--ink-2); cursor: pointer; font-weight: 700; }
.login-tabs button.on { background: var(--surface); color: var(--brand-deep); box-shadow: var(--sh-1); }
.login-card input { width: 100%; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--r-input); font-size: 15px; margin-bottom: 10px; box-sizing: border-box; font-family: inherit; }
.login-enter { width: 100%; border: none; background: var(--brand); color: #fff; border-radius: var(--r-input); padding: 12px; font-weight: 800; font-size: 15px; cursor: pointer; margin-top: 2px; font-family: inherit; }
.login-note { font-size: 12px; color: var(--ink-3); margin: 12px 0 0; line-height: 1.5; }

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
.celebrate-card { position: relative; z-index: 2; background: var(--surface); border-radius: 24px; padding: 32px 44px; text-align: center; box-shadow: 0 20px 60px rgba(20,50,80,.25); animation: pop .5s cubic-bezier(.2,1.6,.4,1) both; }
.celebrate-icon { font-size: 64px; animation: bounce 1s ease-in-out infinite; }
.celebrate-title { font-size: 22px; font-weight: 800; color: var(--accent); margin-top: 8px; }
.celebrate-name { font-size: 18px; font-weight: 700; color: var(--ink); margin-top: 6px; }
.pill.ach { cursor: pointer; border: none; font-family: inherit; }
.pill.star, .pill.box { cursor: pointer; border: none; font-family: inherit; }
.pill.box.ready { animation: boxpulse 1.1s ease-in-out infinite; }
@keyframes boxpulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.12); } }
@keyframes checkpop { 0% { transform: scale(.75); } 70% { transform: scale(1.15); } 100% { transform: scale(1); } }
.box-modal { max-width: 380px; text-align: center; }
.box-result { padding: 16px 0 8px; }
.box-icon { font-size: 64px; animation: bounce 1s ease-in-out infinite; }
.box-gain { font-size: 28px; font-weight: 800; color: var(--accent); margin-top: 6px; }
.box-tip { font-size: 13px; color: var(--ink-3); margin-top: 4px; }
.map-modal, .ach-modal { max-width: 480px; max-height: calc(100vh - 24px); max-height: calc(100dvh - 24px); overflow: hidden; display: flex; flex-direction: column; }
.map-list { display: flex; flex: 1 1 auto; flex-direction: column; gap: 6px; margin: 14px 0; min-height: 0; overflow-y: auto; }
.map-node { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 12px; background: var(--surface-2); opacity: .55; }
.map-node.done { opacity: 1; background: var(--ok-bg); }
.map-node.cur { opacity: 1; background: var(--warm-2); border: 2px solid var(--accent); }
.map-icon { font-size: 24px; }
.map-name { font-weight: 700; color: var(--ink); flex: 1; }
.map-th { font-size: 12px; color: var(--ink-3); }
.map-node.cur .map-th { color: var(--accent-ink); }
.ach-modal { max-width: 460px; }
.ach-grid { display: grid; flex: 1 1 auto; min-height: 0; overflow-y: auto; grid-template-columns: repeat(auto-fill, minmax(88px, 1fr)); gap: 10px; margin: 14px 0; }
.ach-cell { background: var(--surface-2); border-radius: 14px; padding: 12px 6px; text-align: center; opacity: .5; }
.ach-cell.on { opacity: 1; background: var(--warm-2); border: 1px solid var(--accent); }
.ach-icon { font-size: 30px; }
.ach-name { font-size: 12px; font-weight: 700; color: var(--ink-2); margin-top: 4px; }
.ach-prog { font-size: 11px; color: var(--ink-3); margin-top: 2px; }
.ach-cell.on .ach-prog { color: var(--accent-ink); }
.map-modal > .ghost, .ach-modal > .ghost { flex: 0 0 auto; }
.confetti { position: absolute; inset: 0; z-index: 1; overflow: hidden; }
.confetti span { position: absolute; top: -40px; font-size: 24px; color: var(--accent); animation: fall 2.6s linear forwards; }
@keyframes pop { from { transform: scale(.4); opacity: 0; } to { transform: scale(1); opacity: 1; } }
@keyframes bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
@keyframes fall { to { transform: translateY(110vh) rotate(720deg); opacity: 0; } }

@media (max-width: 900px) {
  .plan-section.review-today { padding: 12px; }
  .plan-grid { grid-template-columns: 1fr; }
  .plan-row { align-items: flex-start; flex-direction: column; gap: 5px; }
  .plan-state { padding-left: 38px; }
  .plan-head h2 { font-size: 15px; }
  .review-card-meta { align-items: flex-start; flex-direction: column; gap: 4px; }
  .desk { padding-bottom: calc(72px + env(safe-area-inset-bottom)); }
  .topbar {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 12px 14px 8px;
    padding-top: calc(12px + env(safe-area-inset-top));
  }
  .who { width: 100%; min-width: 0; }
  .who > div { min-width: 0; flex: 1; }
  .who > .avatar { width: 40px; height: 40px; font-size: 22px; flex: 0 0 40px; aspect-ratio: 1; }
  .kid { font-size: 18px; white-space: nowrap; }
  .hello { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .greet-long { display: none; }
  .name-row { flex-wrap: nowrap; }
  .rename { font-size: 12px; white-space: nowrap; flex: 0 0 auto; }
  .rename-txt { display: none; }
  .pills { width: 100%; justify-content: flex-start; flex-wrap: wrap; gap: 8px; }
  .pill { padding: 6px 10px; font-size: 13px; }
  .next { margin-left: 0; text-align: left; min-width: 0; width: 100%; font-size: 12px; }
  .cta { width: 100%; padding: 12px; font-size: 15px; }
  .today-summary { align-items: stretch; gap: 10px; }
  .today-progress { min-width: 100%; }
  .global-toast { bottom: calc(72px + 12px + env(safe-area-inset-bottom)); }

  .body { flex-direction: column; gap: 0; padding: 0; }
  .side {
    width: 100%; flex: none; border-radius: 0;
    position: sticky; top: var(--topbar-height, 0px); z-index: 9;
    max-height: none;
    display: flex; gap: 6px; overflow-x: auto;
    padding: 8px 12px; box-shadow: 0 4px 12px rgba(60,120,170,.08);
    -webkit-overflow-scrolling: touch;
  }
  .nav {
    flex: 0 0 auto; min-width: auto; width: auto; margin: 0;
    flex-direction: column; align-items: flex-start; gap: 2px;
    padding: 8px 12px; white-space: nowrap;
  }
  .nav em { padding: 0; background: none; }

  .mask { padding: 12px; }
  .shop-modal { width: 100%; max-width: none; }
  .main { padding: 12px 14px 16px; }
  .main h1 { font-size: 20px; margin: 0 0 4px; }
  .hint { font-size: 12px; margin-bottom: 10px; }
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
</style>
