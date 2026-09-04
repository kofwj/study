<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from './api.js'
import Admin from './Admin.vue'

const data = reactive({
  level: { earned: 0, balance: 0, level: '阳光萌新', next: null, next_need: 0, progress: 0 },
  streak: 0,
  kid_name: '乐乐',
  today: '',
  cursors: {},
  today_checkin: false,
  subjects: [],
  units: [],
  tasks: [],
  daily: [],
})
const rewards = ref([])
const loading = ref(true)
const err = ref('')
const toast = ref('')
const shopOpen = ref(false)
const myRedeems = ref([])
const celebrate = ref(null)
const chartOpen = reactive({ open: false, task: null, history: [] })
const customTitle = ref('')
const renaming = ref(false)
const renameVal = ref('')

const ICONS = {
  语文: '📖', 数学: '🔢', 英语: '🌍', 科学: '🔬',
  道法: '💛', 体育: '⚽', 音美: '🎨', 综合: '✳️',
}

let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2800)
}

const isAdmin = ref(false)
const pinForm = reactive({ open: false, val: '' })
async function verifyPin() {
  try {
    await api.admin.verify(pinForm.val)
    sessionStorage.setItem('admin_pin', pinForm.val)
    pinForm.open = false
    pinForm.val = ''
    isAdmin.value = true
  } catch (e) { showToast(e.message) }
}
function exitAdmin() {
  isAdmin.value = false
  sessionStorage.removeItem('admin_pin')
  refresh()
}

async function refresh() {
  try {
    const [t, r] = await Promise.all([api.tasks(), api.rewards()])
    const prevId = data.level && data.level.level_id
    const prevEarned = data.level && (data.level.earned || 0)
    Object.assign(data, t)
    // 升级检测：等级变了且累计阳光增加了才庆祝（取消扣回导致的降级不庆祝）
    if (prevId && t.level.level_id !== prevId && t.level.earned >= prevEarned) {
      celebrate.value = { icon: t.level.level_icon || '⭐', name: t.level.level }
      setTimeout(() => (celebrate.value = null), 2800)
    }
    rewards.value = r
    err.value = ''
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}

async function checkin() {
  try {
    const r = await api.checkin()
    showToast(`每日打卡领阳光 +${r.delta} ☀️`)
    await refresh()
  } catch (e) { showToast(e.message) }
}

async function toggleTask(task) {
  if (task.past) {
    showToast('这课已经学过了，不加阳光')
    return
  }
  try {
    if (task.done) {
      await api.cancel(task.id)
      showToast('已取消，扣回阳光')
    } else {
      const r = await api.complete(task.id)
      showToast(`太棒了！完成【${task.title}】+${r.delta} ☀️`)
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
  return { pts: dots.map(p => `${p.x},${p.y}`).join(' '), dots, min, max, bestY }
}
const dailyDialog = reactive({ open: false, task: null, vals: {} })
function openDaily(task) {
  if (task.done_today) return
  dailyDialog.task = task
  dailyDialog.vals = {}
  for (const m of task.metrics) dailyDialog.vals[m.id] = ''
  dailyDialog.open = true
}
async function submitDaily() {
  const metrics = {}
  for (const m of dailyDialog.task.metrics) {
    const v = Number(dailyDialog.vals[m.id])
    if (v && !Number.isNaN(v)) metrics[m.id] = v
  }
  try {
    const r = await api.complete(dailyDialog.task.id, metrics)
    showToast(r.bonus > 0 ? `完成 +${r.delta} ☀️（破纪录 +${r.bonus}！）` : `完成【${dailyDialog.task.name}】+${r.delta} ☀️`)
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
    if (r.pending) showToast(`已提交「${reward.name}」，等家长同意 ✅`)
    else showToast(`兑换成功 🎁 -${reward.price} 阳光`)
    shopOpen.value = false
    await refresh()
  } catch (e) { showToast(e.message) }
}
async function openShop() {
  shopOpen.value = true
  try { myRedeems.value = await api.redemptions() } catch {}
}
const STATUS_TXT = { pending: '等家长同意', done: '已兑换' }

async function saveName() {
  const n = renameVal.value.trim()
  if (!n) return
  try {
    const r = await api.setKidName(n)
    data.kid_name = r.name
    renaming.value = false
  } catch (e) { showToast(e.message) }
}

async function addCustom() {
  const title = customTitle.value.trim()
  if (!title) return showToast('填一下任务名称')
  const sid = activeTab.value === '今日推荐' ? '语文' : activeTab.value
  try {
    await api.customTask({ subject_id: sid, title, sunshine: 5 })
    customTitle.value = ''
    showToast('已添加自定义任务')
    await refresh()
  } catch (e) { showToast(e.message) }
}

async function delCustom(task) {
  if (!confirm(`删除自定义任务「${task.title}」？`)) return
  try {
    await api.delCustom(task.id)
    await refresh()
  } catch (e) { showToast(e.message) }
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
const SUBJECT_ORDER = ['语文', '数学', '英语', '科学', '道法', '体育', '音美', '综合']
const orderedSubjects = computed(() => {
  const list = [...data.subjects]
  list.sort((a, b) => SUBJECT_ORDER.indexOf(a.id) - SUBJECT_ORDER.indexOf(b.id))
  return list
})
const activeTab = ref('今日推荐')
const currentUnits = computed(() => bySubject.value[activeTab.value]?.units || [])

onMounted(async () => {
  await refresh()
})
</script>

<template>
  <Admin v-if="isAdmin" @exit="exitAdmin" />
  <div v-else class="desk">
    <!-- 蓝顶栏 -->
    <header class="topbar">
      <div class="who">
        <div class="avatar">😊</div>
        <div>
          <div class="hello">{{ data.today || '今天' }}</div>
          <div class="hello greet-long">你好呀，五年级的小主人！</div>
          <div class="name-row">
            <template v-if="!renaming">
              <b class="kid">{{ data.kid_name }}</b>
              <button class="rename" @click="renaming = true; renameVal = data.kid_name">✏️ <span class="rename-txt">点击改名</span></button>
            </template>
            <template v-else>
              <input v-model="renameVal" maxlength="12" @keyup.enter="saveName" />
              <button class="rename" @click="saveName">保存</button>
            </template>
          </div>
        </div>
      </div>
      <div class="pills">
        <span class="pill sun"><i></i> {{ data.level.balance }}</span>
        <span class="pill fire">🔥 连续打卡 {{ data.streak }} 天</span>
        <span class="pill star">{{ data.level.level_icon || '⭐' }} {{ data.level.level }}</span>
      </div>
      <div class="next">
        <span v-if="data.level.next">
          {{ data.level.level_icon || '⭐' }} {{ data.level.level }}
          · 再得 {{ data.level.next_need - data.level.earned }} ☀️ 升级 {{ data.level.next_icon || '⭐' }} {{ data.level.next }}
        </span>
        <span v-else>{{ data.level.level_icon || '👑' }} 已是最高等级！</span>
        <div class="next-bar"><i :style="{ width: data.level.progress + '%' }"></i></div>
      </div>
    </header>

    <div class="cta-row">
      <button class="cta check" :disabled="data.today_checkin" @click="checkin">
        📅 每日打卡领阳光（+5 ☀️）
      </button>
      <div v-if="toast" class="cta toast-bar">{{ toast }}</div>
    </div>

    <div class="body">
      <!-- 左栏 -->
      <aside class="side">
        <button class="nav" :class="{ on: activeTab === '今日推荐' }" @click="activeTab = '今日推荐'">
          <span>⭐ 今日推荐</span>
        </button>
        <button v-for="s in orderedSubjects" :key="s.id" class="nav"
          :class="{ on: activeTab === s.id }" @click="activeTab = s.id">
          <span>{{ ICONS[s.id] || '📒' }} {{ s.name }}</span>
          <em>{{ subjectProgress[s.id]?.done || 0 }}/{{ subjectProgress[s.id]?.total || 0 }}</em>
        </button>
      </aside>

      <!-- 右栏 -->
      <main class="main">
        <template v-if="activeTab === '今日推荐'">
          <h1>⭐ 今日推荐</h1>
          <p class="hint">完成一项 +5 ☀️，取消勾选会扣回哦。</p>
          <div v-if="!recommend.length" class="empty">🎉 今天都完成啦，太棒了！</div>
          <div class="grid">
            <div v-for="t in recommend" :key="t.id || t.name" class="card" :class="{ done: t.done }">
              <button v-if="t.frequency === 'daily'" class="circle" @click="openDaily(t)">○</button>
              <button v-else class="circle" :class="{ ok: t.done }" @click="toggleTask(t)">{{ t.done ? '✓' : '' }}</button>
              <div class="card-body">
                <div class="card-title">{{ t.frequency === 'daily' ? t.name : t.title }}</div>
                <div class="plus">{{ t.subject_id || '体育' }} · +{{ t.sunshine || 5 }} ☀️</div>
              </div>
              <button v-if="t.frequency === 'daily'" class="trend" @click="openChart(t)" title="看趋势">📈</button>
            </div>
          </div>
        </template>

        <template v-else>
          <h1>{{ ICONS[activeTab] || '📒' }} {{ activeTab }}</h1>
          <p class="hint">完成一项 +5 ☀️，再点一次会扣回。自定义任务点卡片右上角可删。</p>

          <div v-for="u in currentUnits" :key="u.id" class="unit">
            <h2><i></i> {{ u.name }}</h2>
            <div class="grid">
              <div v-for="t in u.tasks" :key="t.id" class="card" :class="{ done: t.done, past: t.past }">
                <button v-if="t.custom" class="x" title="删除" @click="delCustom(t)">×</button>
                <button class="circle" :class="{ ok: t.done || t.past }" @click="toggleTask(t)">{{ t.done || t.past ? '✓' : '' }}</button>
                <div class="card-body">
                  <div class="card-title">{{ t.title }}</div>
                  <div class="plus">{{ t.past ? '已学过' : ('+' + t.sunshine + ' ☀️') }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="unit" v-if="data.daily.some(x => x.subject_id === activeTab)">
            <h2><i></i> 每日打卡</h2>
            <div class="grid">
              <div v-for="d in data.daily.filter(x => x.subject_id === activeTab)" :key="d.id"
                class="card" :class="{ done: d.done_today }">
                <button class="circle" :class="{ ok: d.done_today }"
                  @click="d.done_today ? cancelDaily(d) : openDaily(d)">{{ d.done_today ? '✓' : '' }}</button>
                <div class="card-body">
                  <div class="card-title">{{ d.name }}</div>
                  <div class="plus">+{{ d.sunshine }} ☀️</div>
                </div>
                <button class="trend" @click="openChart(d)" title="看趋势">📈</button>
              </div>
            </div>
          </div>

          <div v-if="!currentUnits.length && !data.daily.some(x => x.subject_id === activeTab)" class="empty">
            这科还没任务，用下面「自定义任务」加一条，或等家长补目录。
          </div>
        </template>
      </main>
    </div>

    <!-- 底栏：自定义任务 + 商店 -->
    <footer class="foot">
      <span class="foot-label">自定义</span>
      <input v-model="customTitle" class="foot-input" placeholder="任务名，如：背《山居秋暝》"
        @keyup.enter="addCustom" />
      <button class="foot-add" @click="addCustom">添加</button>
      <button class="shop-fab" @click="openShop">🛒 商店</button>
    </footer>

    <!-- 商店抽屉 -->
    <div v-if="shopOpen" class="mask" @click.self="shopOpen = false">
      <div class="shop-modal">
        <h3>🛒 阳光兑换商店</h3>
        <div class="shop-list">
          <div v-for="r in rewards" :key="r.id" class="shop-item">
            <div>
              <div class="shop-name">{{ r.name }}<template v-if="r.need_approval"> · 需家长同意</template></div>
              <div class="shop-price">☀️ {{ r.price }}</div>
            </div>
            <button class="do" :disabled="data.level.balance < r.price" @click="redeem(r)">
              {{ r.need_approval ? '申请' : '兑换' }}
            </button>
          </div>
        </div>
        <div v-if="myRedeems.length" class="redeem-hist">
          <h4>📜 兑换记录</h4>
          <div v-for="rd in myRedeems" :key="rd.id" class="redeem-row">
            <span>{{ rd.name }}</span>
            <span class="dim-s">-{{ rd.price }} ☀️</span>
            <span :class="{ wait: rd.status === 'pending' }">{{ STATUS_TXT[rd.status] || rd.status }}</span>
          </div>
        </div>
        <button class="ghost" @click="shopOpen = false">关闭</button>
      </div>
    </div>

    <!-- 跳绳弹窗 -->
    <div v-if="dailyDialog.open" class="mask" @click.self="dailyDialog.open = false">
      <div class="shop-modal">
        <h3>{{ dailyDialog.task.name }}</h3>
        <div v-for="m in dailyDialog.task.metrics" :key="m.id" class="metric">
          <label>{{ m.label }}（{{ m.unit }}）</label>
          <input v-model.number="dailyDialog.vals[m.id]" type="number" inputmode="decimal" :placeholder="m.unit" />
        </div>
        <button class="do big" @click="submitDaily">打卡，赚阳光 ☀️</button>
        <button class="ghost" @click="dailyDialog.open = false">取消</button>
      </div>
    </div>

    <!-- 跳绳趋势 -->
    <div v-if="chartOpen.open" class="mask" @click.self="chartOpen.open = false">
      <div class="shop-modal chart-modal">
        <h3>📈 {{ chartOpen.task?.name }} 成长趋势</h3>
        <div v-if="!chartOpen.history.length" class="dim-s">还没打过卡，先跳一跳吧！</div>
        <div v-for="m in (chartOpen.task?.metrics || [])" :key="m.id" class="chart-block">
          <div class="chart-head">
            <span class="chart-title">{{ m.label }}</span>
            <span class="chart-scale">{{ lineFor(m).min }} ~ {{ lineFor(m).max }} {{ m.unit }}</span>
          </div>
          <svg viewBox="0 0 288 92" class="chart-svg" preserveAspectRatio="none">
            <line v-if="lineFor(m).dots.length" x1="14" :y1="lineFor(m).bestY" x2="274" :y2="lineFor(m).bestY" class="chart-pb-line" />
            <polyline :points="lineFor(m).pts" fill="none" stroke="#ff9800" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            <circle v-for="(p, i) in lineFor(m).dots" :key="i" :cx="p.x" :cy="p.y" :r="p.best ? 5 : 3.5" :fill="p.best ? '#e53935' : '#ffb800'" stroke="#fff" stroke-width="1.5">
              <title>{{ p.v }}{{ m.unit }}</title>
            </circle>
          </svg>
          <div class="chart-pb">🏅 个人纪录：{{ chartOpen.task.pb?.[m.id] ?? '—' }} {{ m.unit }} · 共 {{ lineFor(m).dots.length }} 次</div>
        </div>
        <button class="ghost" @click="chartOpen.open = false">关闭</button>
      </div>
    </div>

    <!-- 家长 -->
    <button class="parent" @click="pinForm.open = true">👤 家长</button>
    <div v-if="pinForm.open" class="mask" @click.self="pinForm.open = false">
      <div class="shop-modal">
        <h3>家长密码</h3>
        <input v-model="pinForm.val" type="password" inputmode="numeric" placeholder="密码" @keyup.enter="verifyPin" />
        <button class="do big" @click="verifyPin">进入管理</button>
        <button class="ghost" @click="pinForm.open = false">取消</button>
      </div>
    </div>
    <p v-if="err" class="err">{{ err }}</p>

    <!-- 升级庆祝 -->
    <div v-if="celebrate" class="celebrate">
      <div class="confetti">
        <span v-for="i in 14" :key="i" :style="{ left: (i * 7.1) + '%', animationDelay: (i * 0.09) + 's' }">✦</span>
      </div>
      <div class="celebrate-card">
        <div class="celebrate-icon">{{ celebrate.icon }}</div>
        <div class="celebrate-title">🎉 升级啦！</div>
        <div class="celebrate-name">{{ celebrate.icon }} {{ celebrate.name }}</div>
      </div>
    </div>
  </div>
</template>

<style>
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  margin: 0;
  font-family: ui-rounded, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #eef6fb;
  color: #1f3b55;
}
.desk { min-height: 100vh; padding-bottom: 78px; }

.topbar {
  background: linear-gradient(180deg, #4db6ea 0%, #3aa4e0 100%);
  color: #fff; padding: 14px 22px 12px;
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
}
.who { display: flex; align-items: center; gap: 10px; min-width: 180px; }
.avatar {
  width: 46px; height: 46px; border-radius: 50%; background: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 26px;
  flex: 0 0 46px; aspect-ratio: 1; overflow: hidden;
}
.hello { font-size: 12px; opacity: .92; }
.kid { font-size: 20px; }
.name-row { display: flex; align-items: center; gap: 8px; }
.rename { background: none; border: none; color: #e8f6ff; font-size: 12px; cursor: pointer; }
.name-row input { width: 90px; border: none; border-radius: 8px; padding: 4px 8px; }

.pills { display: flex; gap: 10px; flex: 1; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,.22); border-radius: 22px; padding: 8px 16px;
  font-weight: 800; font-size: 15px; display: inline-flex; align-items: center; gap: 6px;
}
.pill.sun i {
  width: 16px; height: 16px; border-radius: 50%; background: #ffc107; display: inline-block;
}
.next { margin-left: auto; text-align: right; font-size: 13px; min-width: 180px; }
.next-bar { height: 6px; background: rgba(255,255,255,.35); border-radius: 4px; margin-top: 6px; overflow: hidden; }
.next-bar i { display: block; height: 100%; background: #ffc107; }

.cta-row { background: #3aa4e0; padding: 0 22px 16px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
.cta {
  border: none; border-radius: 22px; padding: 11px 22px; font-weight: 800; font-size: 15px; cursor: pointer;
}
.cta.check { background: #ffc107; color: #5a3d00; }
.cta.check:disabled { background: #ffe9a8; color: #9a7a30; cursor: default; }
.toast-bar { background: #ff9800; color: #fff; }

.body { display: flex; gap: 18px; padding: 18px 22px; align-items: flex-start; }
.side {
  width: 196px; flex: 0 0 196px; background: #fff; border-radius: 22px; padding: 10px;
  box-shadow: 0 8px 24px rgba(60,120,170,.08);
}
.nav {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  border: none; background: none; padding: 11px 12px; border-radius: 14px;
  color: #4a6780; font-size: 15px; cursor: pointer; margin-bottom: 2px;
}
.nav em { font-style: normal; font-size: 12px; color: #7aa0b8; background: #eef6fb; padding: 2px 8px; border-radius: 10px; }
.nav.on { background: #dff3ff; color: #1f7bb8; font-weight: 800; }
.nav.on em { background: #cde9fb; color: #1f7bb8; }

.main { flex: 1; min-width: 0; }
.main h1 { margin: 4px 0 6px; font-size: 26px; }
.hint { color: #7aa0b8; font-size: 13px; margin: 0 0 16px; }
.unit { margin-bottom: 22px; }
.unit h2 {
  margin: 0 0 10px; font-size: 16px; color: #1f7bb8; display: flex; align-items: center; gap: 8px;
}
.unit h2 i { width: 4px; height: 16px; background: #3aa4e0; border-radius: 2px; display: inline-block; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 260px)); gap: 12px; }
.card {
  position: relative; background: #fff; border-radius: 16px; padding: 16px 14px 14px 14px;
  display: flex; gap: 10px; align-items: flex-start; min-height: 86px;
  box-shadow: 0 4px 14px rgba(60,120,170,.07); border: 1px solid #e8f3fa;
}
.card.done { background: #eaf8ee; border-color: #cfead6; }
.card.past { opacity: .55; }
.circle {
  width: 28px; height: 28px; border-radius: 50%; border: 2px solid #c5d8e6; background: #fff;
  flex: 0 0 28px; cursor: pointer; color: #fff; font-weight: 800;
}
.circle.ok { background: #3cb371; border-color: #3cb371; }
.card-body { flex: 1; min-width: 0; }
.card-title { font-size: 14px; line-height: 1.45; font-weight: 600; }
.plus { margin-top: 8px; color: #f5a623; font-weight: 800; font-size: 13px; }
.x {
  position: absolute; top: 6px; right: 8px; border: none; background: none; color: #b7c9d6;
  cursor: pointer; font-size: 16px; display: none;
}
.card:hover .x { display: block; }
.empty { color: #7aa0b8; padding: 30px 0; }

.foot {
  position: fixed; left: 0; right: 0; bottom: 0; background: #fff;
  display: flex; align-items: center; gap: 10px; padding: 12px 22px;
  box-shadow: 0 -4px 18px rgba(60,120,170,.08);
}
.foot-label {
  background: #fff; border: 1px solid #d7e6f0; border-radius: 12px; padding: 10px 14px; color: #7aa0b8; font-size: 13px;
}
.foot-input {
  flex: 1; border: 1px solid #d7e6f0; border-radius: 12px; padding: 10px 14px; font-size: 14px;
}
.foot-add { border: none; background: #3aa4e0; color: #fff; border-radius: 12px; padding: 10px 16px; font-weight: 800; cursor: pointer; }
.shop-fab {
  border: none; background: #ffc107; color: #5a3d00; border-radius: 22px; padding: 10px 18px;
  font-weight: 800; cursor: pointer; white-space: nowrap;
}

.mask { position: fixed; inset: 0; background: rgba(20,40,60,.35); display: flex; align-items: center; justify-content: center; z-index: 20; }
.shop-modal { background: #fff; border-radius: 18px; padding: 22px; width: 92%; max-width: 420px; }
.shop-modal h3 { margin: 0 0 14px; }
.shop-list { display: flex; flex-direction: column; gap: 10px; }
.shop-item { display: flex; justify-content: space-between; align-items: center; border: 1px solid #e8f3fa; border-radius: 12px; padding: 12px; }
.shop-price { color: #f5a623; font-weight: 800; }
.redeem-hist { margin-top: 16px; border-top: 1px dashed #e8f3fa; padding-top: 12px; }
.redeem-hist h4 { margin: 0 0 8px; font-size: 13px; color: #7aa0b8; }
.redeem-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; padding: 4px 0; }
.redeem-row .wait { color: #f5a623; font-weight: 700; }
.dim-s { color: #9db8c8; }
.do { border: none; background: #3aa4e0; color: #fff; border-radius: 16px; padding: 8px 16px; font-weight: 800; cursor: pointer; }
.do:disabled { background: #c5d8e6; cursor: default; }
.do.big { width: 100%; padding: 12px; margin-top: 8px; }
.ghost { width: 100%; margin-top: 8px; border: none; background: none; color: #7aa0b8; cursor: pointer; }
.metric { margin-bottom: 10px; }
.metric label { display: block; font-size: 13px; margin-bottom: 4px; }
.trend { position: absolute; top: 8px; right: 8px; border: none; background: #fff3d6; border-radius: 14px; padding: 3px 8px; font-size: 15px; cursor: pointer; line-height: 1; }
.chart-modal { max-width: 460px; max-height: 86vh; overflow-y: auto; }
.chart-block { margin-bottom: 12px; padding: 10px 12px; background: #f7fbfe; border-radius: 12px; }
.chart-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.chart-title { font-weight: 700; font-size: 14px; color: #1f3b55; }
.chart-scale { font-size: 12px; color: #9db8c8; }
.chart-svg { width: 100%; height: 92px; display: block; }
.chart-pb-line { stroke: #e53935; stroke-width: 1.5; stroke-dasharray: 4 4; opacity: .55; }
.chart-pb { font-size: 12px; color: #c07b00; margin-top: 6px; }
.shop-modal input, .metric input { width: 100%; padding: 10px 12px; border: 1px solid #d7e6f0; border-radius: 10px; font-size: 15px; }
.parent { position: fixed; left: 16px; bottom: 86px; border: none; background: none; color: #7aa0b8; cursor: pointer; z-index: 5; }
.err { color: #c62828; text-align: center; }

/* 升级庆祝 */
.celebrate { position: fixed; inset: 0; z-index: 40; display: flex; align-items: center; justify-content: center; pointer-events: none; }
.celebrate-card { position: relative; z-index: 2; background: #fff; border-radius: 24px; padding: 32px 44px; text-align: center; box-shadow: 0 20px 60px rgba(20,50,80,.25); animation: pop .5s cubic-bezier(.2,1.6,.4,1) both; }
.celebrate-icon { font-size: 64px; animation: bounce 1s ease-in-out infinite; }
.celebrate-title { font-size: 22px; font-weight: 800; color: #f5a623; margin-top: 8px; }
.celebrate-name { font-size: 18px; font-weight: 700; color: #1f3b55; margin-top: 6px; }
.confetti { position: absolute; inset: 0; z-index: 1; overflow: hidden; }
.confetti span { position: absolute; top: -40px; font-size: 24px; color: #ffc107; animation: fall 2.6s linear forwards; }
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
  }
  .who { width: 100%; min-width: 0; }
  .who > div { min-width: 0; flex: 1; }
  .avatar { width: 40px; height: 40px; font-size: 22px; flex: 0 0 40px; aspect-ratio: 1; }
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
    position: sticky; top: 0; z-index: 6;
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
  .parent { left: auto; right: 12px; bottom: calc(80px + env(safe-area-inset-bottom)); }
}
</style>
