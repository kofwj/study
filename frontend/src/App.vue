<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from './api.js'
import Admin from './Admin.vue'
import { SUBJECT_ICONS as ICONS, rankIcon, achIcon } from './icons.js'
import { Sun, Lock, Gift, Check, TrendingUp, Target, User, ShoppingCart, ScrollText, Medal, BarChart3, Map, CalendarDays, RefreshCw, PartyPopper, Sparkles, BookOpen, Flame } from 'lucide-vue-next'

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
})
const rewards = ref([])
const loading = ref(true)
const err = ref('')
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

const isAdmin = ref(false)
const me = ref(null)
const authed = ref(false)
const pinForm = reactive({ open: false, mode: 'login', account: 'lele', val: '', name: '', family: '我家', code: '' })
async function afterLogin(r) {
  me.value = r
  pinForm.open = false
  pinForm.val = ''
  authed.value = true
  isAdmin.value = r.role === 'parent'
  if (r.force_pin_change) showToast('请先改密码')
  if (!isAdmin.value) await refresh()
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
  pinForm.mode = 'login'
  pinForm.account = 'parent'
  pinForm.open = true
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
    const [t, r, bx] = await Promise.all([api.tasks(), api.rewards(), api.boxes()])
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
    err.value = ''
  } catch (e) {
    if (e.status === 401) { me.value = null; pinForm.open = true }
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
  const needApproval = !!reward.need_approval
  if (!needApproval && !confirm(`确定用 ${reward.price} 阳光兑换「${reward.name}」吗？`)) return
  try {
    const r = await api.redeem(reward.id)
    if (r.pending) showToast(`已提交「${reward.name}」，等家长同意`)
    else showToast(`兑换成功 -${reward.price} 阳光`)
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
const recommend = computed(() => {
  // 今天该干啥：跳绳（未打）+ 语数英「当前单元」各 2 条
  // 当前单元 = 该科第一个还有未完成任务的单元；做完自动滚到下一单元
  const out = data.daily.filter(d => !d.done_today)
  for (const subj of ['语文', '数学', '英语']) {
    const units = (bySubject.value[subj] && bySubject.value[subj].units) || []
    const cur = units.find(u => u.tasks.some(t => !t.done && !t.past))
    if (cur) out.push(...cur.tasks.filter(t => !t.done && !t.past).slice(0, 2))
  }
  return out
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
  <Admin v-if="isAdmin" @exit="exitAdmin" @switched="refresh" />
  <div v-else-if="authed" class="desk">
    <button v-if="updateReady" type="button" class="update-bar" @click="reloadApp"><RefreshCw class="ico" :size="15" /> 有新版本，点我刷新</button>
    <!-- 蓝顶栏 -->
    <header class="topbar">
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

    <div class="cta-row">
      <button class="cta check" :disabled="data.today_checkin" @click="checkin">
        <CalendarDays class="ico" :size="16" /> {{ data.today_checkin ? '今日已签到' : '每日签到' }}
      </button>
      <div v-if="toast" class="cta toast-bar">{{ toast }}</div>
    </div>

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
          <h1><Sparkles class="ico" :size="20" /> 今日推荐</h1>
          <p class="hint">完成一项 +5 <Sun class="ico sun" :size="13" />，取消勾选会扣回哦。</p>
          <div v-if="!recommend.length" class="empty"><PartyPopper class="ico" :size="16" /> 今天都完成啦，太棒了！</div>
          <div class="grid">
            <div v-for="t in recommend" :key="t.id || t.name" class="card enter" :class="{ done: t.done }">
              <button v-if="t.frequency === 'daily'" class="circle" @click="openDaily(t)">○</button>
              <button v-else class="circle" :class="{ ok: t.done }" @click="toggleTask(t, $event)"><Check v-if="t.done" :size="15" /></button>
              <div class="card-body">
                <div class="card-title">{{ t.frequency === 'daily' ? t.name : t.title }}</div>
                <div v-if="t.note" class="card-detail">{{ t.note }}</div>
                <div v-if="t.detail" class="card-detail">{{ t.detail }}</div>
                <div class="plus">{{ t.subject_id || '体育' }} · +{{ t.sunshine || 5 }} <Sun class="ico sun" :size="12" /></div>
              </div>
              <button v-if="t.frequency === 'daily'" class="trend" @click="openChart(t)" title="看趋势"><TrendingUp :size="15" /></button>
            </div>
          </div>
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
      <span style="flex:1"></span>
      <button class="shop-fab" @click="openShop"><ShoppingCart class="ico" :size="16" /> 商店</button>
    </footer>

    <!-- 商店抽屉 -->
    <div v-if="shopOpen" class="mask" @click.self="shopOpen = false">
      <div class="shop-modal enter">
        <h3><ShoppingCart class="ico" :size="18" /> 阳光兑换商店</h3>
        <div class="shop-list">
          <div v-for="r in rewards" :key="r.id" class="shop-item">
            <div>
              <div class="shop-name">{{ r.name }}<template v-if="r.need_approval"> · 需家长同意</template></div>
              <div class="shop-price"><Sun class="ico sun" :size="14" /> {{ r.price }}</div>
            </div>
            <button class="do" :disabled="data.level.balance < r.price" @click="redeem(r)">
              {{ r.need_approval ? '申请' : '兑换' }}
            </button>
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
        <div v-for="m in dailyDialog.task.metrics" :key="m.id" class="metric">
          <label>{{ m.label }}（{{ m.unit }}）</label>
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
            <div class="chart-pb"><Medal class="ico" :size="13" /> 个人纪录 {{ chartOpen.task.pb?.[m.id] ?? '—' }} {{ m.unit }} · <BarChart3 class="ico" :size="13" /> 累计 {{ lineFor(m).sum }} {{ m.unit }} · 共 {{ lineFor(m).count }} 次</div>
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

    <div v-else class="login-screen">
      <div class="login-card">
        <div class="login-logo"><Sun class="ico" :size="36" /></div>
        <h1>阳光学习工作台</h1>
        <p class="login-sub">孩子的每日学习打卡小助手</p>
        <div class="login-tabs">
          <button type="button" :class="{ on: pinForm.mode==='login' }" @click="pinForm.mode='login'">登录</button>
          <button type="button" :class="{ on: pinForm.mode==='register' }" @click="pinForm.mode='register'">注册新家</button>
          <button type="button" :class="{ on: pinForm.mode==='join' }" @click="pinForm.mode='join'">邀请码加入</button>
        </div>
        <input v-model="pinForm.account" placeholder="账号" autocomplete="username" />
        <input v-model="pinForm.val" type="password" inputmode="numeric" placeholder="密码（4 位数字）" autocomplete="current-password" @keyup.enter="verifyPin" />
        <input v-if="pinForm.mode!=='login'" v-model="pinForm.name" placeholder="你的名字" />
        <input v-if="pinForm.mode==='register'" v-model="pinForm.family" placeholder="家庭名（如：乐乐的家）" />
        <input v-if="pinForm.mode==='join'" v-model="pinForm.code" placeholder="邀请码" />
        <button class="login-enter" @click="verifyPin">进入</button>
        <p class="login-note">
          <template v-if="pinForm.mode==='register'">注册就是为你家开一个独立空间，不需要邀请码。</template>
          <template v-else-if="pinForm.mode==='join'">邀请码由家庭里已有的家长在设置页生成。</template>
          <template v-else>孩子用小名账号登录打卡，家长用家长账号管理。</template>
        </p>
      </div>
    </div>

    <div v-if="pinForm.open" class="mask">
      <div class="shop-modal enter">
        <h3>{{ pinForm.mode === 'register' ? '注册家庭' : (pinForm.mode === 'join' ? '加入家庭' : '登录') }}</h3>
        <input v-model="pinForm.account" placeholder="账号" autocomplete="username" />
        <input v-model="pinForm.val" type="password" inputmode="numeric" placeholder="密码" autocomplete="current-password" @keyup.enter="verifyPin" />
        <input v-if="pinForm.mode !== 'login'" v-model="pinForm.name" placeholder="你的名字" />
        <input v-if="pinForm.mode === 'register'" v-model="pinForm.family" placeholder="家庭名" />
        <input v-if="pinForm.mode === 'join'" v-model="pinForm.code" placeholder="邀请码" />
        <button class="do big" @click="verifyPin">进入</button>
        <p class="dim" style="margin-top:8px">
          <button class="ghost" @click="pinForm.mode = 'login'">登录</button>
          <button class="ghost" @click="pinForm.mode = 'register'">注册</button>
          <button class="ghost" @click="pinForm.mode = 'join'">邀请码</button>
        </p>
        <button v-if="me" class="ghost" @click="pinForm.open = false">取消</button>
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
</template>

<style>
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  margin: 0;
  font-family: ui-rounded, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.update-bar { width: 100%; border: none; background: var(--accent); color: #fff; padding: 9px 22px; display: flex; justify-content: center; align-items: center; font-weight: 700; font-size: 14px; font-family: inherit; position: sticky; top: env(safe-area-inset-top); z-index: 30; cursor: pointer; }
.desk { min-height: 100vh; padding-bottom: 78px; }

.topbar {
  background: linear-gradient(180deg, var(--brand) 0%, var(--brand) 100%);
  color: #fff; padding: 14px 22px 12px;
  padding-top: calc(14px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
  position: sticky; top: 0; z-index: 10;
}
.who { display: flex; align-items: center; gap: 10px; min-width: 180px; }
.avatar {
  width: 46px; height: 46px; border-radius: 50%; background: var(--accent);
  color: #fff; font-weight: 800; font-size: 20px; letter-spacing: 0;
  display: flex; align-items: center; justify-content: center;
  flex: 0 0 46px; aspect-ratio: 1; overflow: hidden; box-shadow: var(--sh-1);
}
.hello { font-size: 12px; opacity: .92; }
.kid { font-size: 20px; }
.name-row { display: flex; align-items: center; gap: 8px; }
.rename { background: none; border: none; color: rgba(255,255,255,.85); font-size: 12px; cursor: pointer; }
.name-row input { width: 90px; border: none; border-radius: 8px; padding: 4px 8px; }

.pills { display: flex; gap: 10px; flex: 1; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,.22); border-radius: 22px; padding: 8px 16px;
  font-weight: 800; font-size: 15px; display: inline-flex; align-items: center; gap: 6px;
}
.pill.sun i {
  width: 16px; height: 16px; border-radius: 50%; background: var(--accent); display: inline-block;
}
.next { margin-left: auto; text-align: right; font-size: 13px; min-width: 180px; }
.next-bar { height: 6px; background: rgba(255,255,255,.35); border-radius: 4px; margin-top: 6px; overflow: hidden; }
.next-bar i { display: block; height: 100%; background: var(--accent); }

.cta-row { background: var(--brand); padding: 0 22px 16px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
.cta {
  border: none; border-radius: 22px; padding: 11px 22px; font-weight: 800; font-size: 15px; cursor: pointer;
}
.cta.check { background: var(--accent); color: var(--accent-ink); }
.cta.check:disabled { background: var(--warm); color: var(--ink-3); cursor: default; }
.toast-bar { background: var(--accent); color: #fff; }

.body { display: flex; gap: 18px; padding: 18px 22px; align-items: flex-start; }
.side {
  width: 196px; flex: 0 0 196px; background: var(--surface); border-radius: 22px; padding: 10px;
  box-shadow: 0 8px 24px rgba(60,120,170,.08);
}
.nav {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  border: none; background: none; padding: 11px 12px; border-radius: 14px;
  color: var(--ink-2); font-size: 15px; cursor: pointer; margin-bottom: 2px;
}
.nav em { font-style: normal; font-size: 12px; color: var(--ink-3); background: var(--surface-2); padding: 2px 8px; border-radius: 10px; }
.nav.on { background: var(--surface-2); color: var(--brand-deep); font-weight: 800; }
.nav.on em { background: var(--line); color: var(--brand-deep); }

.main { flex: 1; min-width: 0; }
.main h1 { margin: 4px 0 6px; font-size: 26px; }
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
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.card {
  position: relative; background: var(--surface); border-radius: var(--r-card); padding: 16px 14px 14px 14px;
  display: flex; gap: 10px; align-items: flex-start; min-height: 86px;
  box-shadow: var(--sh-card); border: 1px solid var(--line);
}
.card.done { background: var(--ok-bg); border-color: var(--ok-bg); }
.card.past { opacity: .55; }
.circle {
  width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--line); background: var(--surface);
  flex: 0 0 28px; cursor: pointer; color: #fff; font-weight: 800;
}
.circle.ok { background: var(--ok); border-color: var(--ok); }
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
.empty { color: var(--ink-3); padding: 30px 0; }

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

.mask { position: fixed; inset: 0; background: rgba(20,40,60,.35); display: flex; align-items: center; justify-content: center; z-index: 20; }
.shop-modal { background: var(--surface); border-radius: var(--r-card); padding: 22px; width: 92%; max-width: 420px; }
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
.box-modal { max-width: 380px; text-align: center; }
.box-result { padding: 16px 0 8px; }
.box-icon { font-size: 64px; animation: bounce 1s ease-in-out infinite; }
.box-gain { font-size: 28px; font-weight: 800; color: var(--accent); margin-top: 6px; }
.box-tip { font-size: 13px; color: var(--ink-3); margin-top: 4px; }
.map-modal { max-width: 480px; }
.map-list { display: flex; flex-direction: column; gap: 6px; margin: 14px 0; max-height: 60vh; overflow-y: auto; }
.map-node { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 12px; background: var(--surface-2); opacity: .55; }
.map-node.done { opacity: 1; background: var(--ok-bg); }
.map-node.cur { opacity: 1; background: var(--warm-2); border: 2px solid var(--accent); }
.map-icon { font-size: 24px; }
.map-name { font-weight: 700; color: var(--ink); flex: 1; }
.map-th { font-size: 12px; color: var(--ink-3); }
.map-node.cur .map-th { color: var(--accent-ink); }
.ach-modal { max-width: 460px; }
.ach-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(88px, 1fr)); gap: 10px; margin: 14px 0; }
.ach-cell { background: var(--surface-2); border-radius: 14px; padding: 12px 6px; text-align: center; opacity: .5; }
.ach-cell.on { opacity: 1; background: var(--warm-2); border: 1px solid var(--accent); }
.ach-icon { font-size: 30px; }
.ach-name { font-size: 12px; font-weight: 700; color: var(--ink-2); margin-top: 4px; }
.ach-prog { font-size: 11px; color: var(--ink-3); margin-top: 2px; }
.ach-cell.on .ach-prog { color: var(--accent-ink); }
.confetti { position: absolute; inset: 0; z-index: 1; overflow: hidden; }
.confetti span { position: absolute; top: -40px; font-size: 24px; color: var(--accent); animation: fall 2.6s linear forwards; }
@keyframes pop { from { transform: scale(.4); opacity: 0; } to { transform: scale(1); opacity: 1; } }
@keyframes bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
@keyframes fall { to { transform: translateY(110vh) rotate(720deg); opacity: 0; } }

@media (max-width: 900px) {
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
  .cta-row { padding: 0 14px 12px; }
  .cta { width: 100%; padding: 12px; font-size: 15px; }
  .toast-bar { width: 100%; text-align: center; }

  .body { flex-direction: column; gap: 0; padding: 0; }
  .side {
    width: 100%; flex: none; border-radius: 0;
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
