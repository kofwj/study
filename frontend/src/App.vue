<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from './api.js'
import Admin from './Admin.vue'

const data = reactive({
  level: { earned: 0, balance: 0, level: '阳光萌新', next: null, next_need: 0, progress: 0 },
  streak: 0,
  today_checkin: false,
  subjects: [],
  units: [],
  tasks: [],
  daily: [],
})
const rewards = ref([])
const ledger = ref([])
const loading = ref(true)
const err = ref('')
const toast = ref('')

let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2600)
}

// —— 家长入口 ——
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
    const [t, r, l] = await Promise.all([api.tasks(), api.rewards(), api.ledger()])
    Object.assign(data, t)
    rewards.value = r
    ledger.value = l
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
    showToast(`签到成功 +${r.delta} 阳光 ☀️`)
    await refresh()
  } catch (e) { showToast(e.message) }
}

async function toggleTask(task) {
  try {
    if (task.done) {
      await api.cancel(task.id)
      showToast('已取消，扣回阳光')
    } else {
      const r = await api.complete(task.id)
      showToast(`太棒了！完成「${task.title}」+${r.delta} ☀️`)
    }
    await refresh()
  } catch (e) { showToast(e.message) }
}

// ---- 每日任务（跳绳等）----
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
    showToast(r.bonus > 0 ? `完成 +${r.delta} ☀️（破纪录 +${r.bonus}！）` : `完成 +${r.delta} 阳光 ☀️`)
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
  if (!confirm(`确定用 ${reward.price} 阳光兑换「${reward.name}」吗？`)) return
  try {
    await api.redeem(reward.id)
    showToast(`兑换成功 🎁 -${reward.price} 阳光`)
    await refresh()
  } catch (e) { showToast(e.message) }
}

const unitName = (id) => data.units.find(u => u.id === id)?.name || ''
const incompleteTasks = computed(() => data.tasks.filter(t => !t.done))
const recommend = computed(() => {
  const d = data.daily.filter(d => !d.done_today)
  const u = incompleteTasks.value.slice(0, 6)
  return [...d, ...u]
})
const bySubject = computed(() => {
  const m = {}
  for (const s of data.subjects) m[s.id] = { name: s.name, units: [] }
  const seen = new Set()
  for (const t of data.tasks) {
    const subj = data.subjects.find(s => s.id === t.subject_id)
    if (!subj) continue
    if (!m[t.subject_id]) m[t.subject_id] = { name: t.subject_id, units: [] }
    const un = m[t.subject_id]
    if (!seen.has(t.unit_id + t.subject_id)) {
      seen.add(t.unit_id + t.subject_id)
      un.units.push({ id: t.unit_id, name: unitName(t.unit_id), tasks: [] })
    }
    const unit = un.units.find(u => u.id === t.unit_id)
    unit.tasks.push(t)
  }
  return m
})
const subjectProgress = computed(() => {
  const m = {}
  for (const s of data.subjects) m[s.id] = { done: 0, total: 0 }
  for (const t of data.tasks) {
    const p = m[t.subject_id]
    if (!p) continue
    p.total++
    if (t.done) p.done++
  }
  for (const d of data.daily) {
    const p = m[d.subject_id]
    if (!p) continue
    p.total++
    if (d.done_today) p.done++
  }
  return m
})
const activeTab = ref('')

onMounted(async () => {
  await refresh()
  if (data.subjects.length) activeTab.value = data.subjects[0].id
})
</script>

<template>
  <Admin v-if="isAdmin" @exit="exitAdmin" />
  <div v-else class="app">

    <!-- 顶部问候 + 等级 -->
    <header class="hero">
      <div class="hero-top">
        <div class="hero-left">
          <div class="greet">你好呀，五年级的小主人！</div>
          <div class="sun">☀️ <b>{{ data.level.balance }}</b><span>阳光</span></div>
        </div>
        <div class="hero-chips">
          <span class="chip streak">🔥 连续 {{ data.streak }} 天</span>
          <span class="chip rank">{{ data.level.level }}</span>
        </div>
      </div>
      <div class="rank-bar"><i :style="{ width: data.level.progress + '%' }"></i></div>
      <div class="rank-meta">
        <span>累计获得 {{ data.level.earned }} ☀️</span>
        <span v-if="data.level.next" class="next">下一级「{{ data.level.next }}」还差 {{ data.level.next_need - data.level.earned }}</span>
        <span v-else class="next">已到最高等级 🎉</span>
      </div>
      <button class="checkin" :disabled="data.today_checkin" @click="checkin">
        {{ data.today_checkin ? '今日已签到 ✅' : '🌞 每日打卡领阳光 +5' }}
      </button>
    </header>

    <!-- 学科切换 -->
    <nav class="subjects">
      <button v-for="s in data.subjects" :key="s.id"
        :class="{ on: activeTab === s.id }" @click="activeTab = s.id">
        <span class="sn">{{ s.name }}</span>
        <span class="sp">{{ subjectProgress[s.id]?.done }}/{{ subjectProgress[s.id]?.total }}</span>
      </button>
    </nav>

    <!-- 今日推荐 -->
    <section class="sec">
      <h2 class="sec-h">⭐ 今日推荐 <span class="sec-sub">今天先做这些</span></h2>
      <div v-if="!recommend.length" class="empty">🎉 今天都完成啦，太棒了！</div>
      <div v-for="t in recommend" :key="t.id || t.name" class="task-card">
        <div class="tc-left">
          <span class="badge" :class="{ daily: t.frequency === 'daily' }">{{ t.frequency === 'daily' ? '每天' : t.action }}</span>
          <span class="tc-title">{{ t.frequency === 'daily' ? t.name : t.title }}</span>
        </div>
        <div class="tc-right">
          <span v-if="t.frequency === 'daily' && t.pb && Object.values(t.pb).some(v => v !== null)" class="pb">纪录 {{ Object.values(t.pb).filter(v => v !== null).join(' / ') }}</span>
          <button v-if="t.frequency === 'daily'" class="do" @click="openDaily(t)">去打卡</button>
          <button v-else class="do" @click="toggleTask(t)">+{{ t.sunshine }}</button>
        </div>
      </div>
    </section>

    <!-- 当前学科任务 -->
    <section class="sec" v-if="bySubject[activeTab]">
      <h2 class="sec-h"><span class="emoji">{{ activeTab === '语文' ? '📚' : activeTab === '数学' ? '🔢' : activeTab === '英语' ? '🔤' : activeTab === '体育' ? '🏃' : '📒' }}</span> {{ activeTab }} <span class="sec-sub">按单元完成</span></h2>
      <div v-for="u in bySubject[activeTab].units" :key="u.id" class="unit-block" v-show="u.tasks.length">
        <div class="unit-h">{{ u.name }} <span class="unit-cnt">{{ u.tasks.filter(t => !t.done).length }}/{{ u.tasks.length }} 未完成</span></div>
        <div v-for="t in u.tasks" :key="t.id" class="task-card" :class="{ done: t.done }">
          <div class="tc-left">
            <span class="badge">{{ t.action }}</span>
            <span class="tc-title">{{ t.title }}</span>
          </div>
          <button class="do" :class="{ ghosty: t.done }" @click="toggleTask(t)">{{ t.done ? '取消' : '+5' }}</button>
        </div>
      </div>
      <div class="unit-block" v-if="data.daily.some(x => x.subject_id === activeTab)">
        <div class="unit-h">每日打卡</div>
        <div v-for="d in data.daily.filter(x => x.subject_id === activeTab)" :key="d.id" class="task-card" :class="{ done: d.done_today }">
          <div class="tc-left">
            <span class="badge daily">每天</span>
            <span class="tc-title">{{ d.name }}</span>
          </div>
          <div class="tc-right">
            <span v-if="d.pb && Object.values(d.pb).some(v => v !== null)" class="pb">纪录 {{ Object.values(d.pb).filter(v => v !== null).join(' / ') }}</span>
            <button class="do" v-if="!d.done_today" @click="openDaily(d)">去打卡</button>
            <button class="do ghosty" v-else @click="cancelDaily(d)">取消</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 商店 -->
    <section class="sec">
      <h2 class="sec-h">🛒 阳光兑换商店 <span class="sec-sub">明码标价，自己算性价比</span></h2>
      <div class="shop">
        <div v-for="r in rewards" :key="r.id" class="shop-item">
          <div class="shop-name">{{ r.name }}</div>
          <div class="shop-price">☀️ {{ r.price }}</div>
          <button class="do" :class="{ ghosty: data.level.balance < r.price }" @click="redeem(r)">兑换</button>
        </div>
      </div>
    </section>

    <!-- 流水 -->
    <section class="sec">
      <h2 class="sec-h">📜 最近动态</h2>
      <div v-for="l in ledger" :key="l.id" class="ledger">
        <span class="lg-note">{{ l.note }}</span>
        <span class="lg-delta" :class="l.delta > 0 ? 'pos' : 'neg'">{{ l.delta > 0 ? '+' : '' }}{{ l.delta }}</span>
      </div>
      <p v-if="!ledger.length" class="dim empty">还没有记录，先签到或完成一项任务吧</p>
    </section>

    <button class="parent-btn" @click="pinForm.open = true">👤 家长</button>

    <!-- 每日任务弹窗 -->
    <div v-if="dailyDialog.open" class="mask" @click.self="dailyDialog.open = false">
      <div class="modal">
        <h3>{{ dailyDialog.task.name }}</h3>
        <div v-for="m in dailyDialog.task.metrics" :key="m.id" class="metric">
          <label>{{ m.label }}（{{ m.unit }}）</label>
          <input v-model.number="dailyDialog.vals[m.id]" type="number" inputmode="decimal" :placeholder="m.unit" />
        </div>
        <button class="do big" @click="submitDaily">打卡，赚阳光 ☀️</button>
        <button class="ghost" @click="dailyDialog.open = false">取消</button>
      </div>
    </div>

    <!-- 家长密码弹窗 -->
    <div v-if="pinForm.open" class="mask" @click.self="pinForm.open = false">
      <div class="modal">
        <h3>家长密码</h3>
        <input v-model="pinForm.val" type="password" inputmode="numeric" placeholder="密码" @keyup.enter="verifyPin" />
        <button class="do big" @click="verifyPin">进入管理</button>
        <button class="ghost" @click="pinForm.open = false">取消</button>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
    <p v-if="err" class="err">{{ err }}</p>
  </div>
</template>

<style>
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
:root {
  --bg: #faf5ec;
  --card: #ffffff;
  --ink: #3a2e1b;
  --muted: #97886a;
  --line: #f1e8d6;
  --sun: #ffb300;
  --sun-deep: #f5921e;
  --ok: #43a047;
}
body {
  margin: 0;
  font-family: ui-rounded, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}
.app { max-width: 760px; margin: 0 auto; padding: 16px 14px 40px; }

/* 顶部 */
.hero {
  background: linear-gradient(160deg, #ffe9b3 0%, #ffd66b 55%, #ffc345 100%);
  border-radius: 24px; padding: 20px 20px 18px; color: #5b3d08;
  box-shadow: 0 8px 24px rgba(240, 160, 20, .25);
}
.hero-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.greet { font-size: 14px; opacity: .85; margin-bottom: 4px; }
.sun { font-size: 15px; }
.sun b { font-size: 34px; font-weight: 900; letter-spacing: -1px; margin-right: 4px; }
.sun span { font-size: 13px; opacity: .8; }
.hero-chips { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
.chip { background: rgba(255,255,255,.55); border-radius: 20px; padding: 5px 12px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.chip.streak { color: #d4491f; }
.chip.rank { background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.rank-bar { height: 10px; background: rgba(255,255,255,.5); border-radius: 8px; overflow: hidden; margin: 14px 0 8px; }
.rank-bar i { display: block; height: 100%; background: linear-gradient(90deg, #ff8a00, #ffb300); border-radius: 8px; transition: width .5s ease; }
.rank-meta { display: flex; justify-content: space-between; font-size: 12px; opacity: .85; }
.checkin {
  width: 100%; margin-top: 14px; padding: 14px; font-size: 16px; font-weight: 800;
  background: #fff; color: #6d4c00; border: none; border-radius: 16px; cursor: pointer;
  box-shadow: 0 4px 14px rgba(120, 80, 0, .15); transition: transform .1s;
}
.checkin:active { transform: scale(.98); }
.checkin:disabled { background: rgba(255,255,255,.6); color: #a08a5a; box-shadow: none; cursor: default; }

/* 学科 */
.subjects { display: flex; gap: 8px; overflow-x: auto; padding: 14px 2px; -webkit-overflow-scrolling: touch; }
.subjects button {
  flex: 0 0 auto; min-width: 64px; padding: 8px 12px; border: none; border-radius: 16px;
  background: var(--card); color: var(--muted); cursor: pointer; box-shadow: 0 1px 4px rgba(120,100,40,.08);
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.subjects button .sn { font-size: 14px; font-weight: 700; }
.subjects button .sp { font-size: 11px; opacity: .7; }
.subjects button.on { background: var(--sun); color: #fff; box-shadow: 0 4px 12px rgba(255,179,0,.35); }
.subjects button.on .sp { opacity: .9; }

/* 区块 */
.sec { background: var(--card); border-radius: 20px; padding: 16px; margin-bottom: 14px; box-shadow: 0 2px 12px rgba(140,105,30,.06); }
.sec-h { margin: 0 0 12px; font-size: 16px; font-weight: 800; display: flex; align-items: baseline; gap: 8px; }
.sec-h .emoji { font-size: 18px; }
.sec-sub { font-size: 12px; font-weight: 400; color: var(--muted); }
.empty { text-align: center; color: var(--muted); padding: 18px 0; font-size: 14px; }

/* 任务卡 */
.unit-h { font-weight: 800; font-size: 13px; color: #6d5a2b; margin: 14px 0 8px; display: flex; justify-content: space-between; align-items: center; }
.unit-cnt { font-weight: 400; color: var(--muted); font-size: 11px; }
.task-card {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  padding: 11px 12px; margin-bottom: 6px; border: 1px solid var(--line); border-radius: 14px;
  background: #fff; transition: all .15s;
}
.task-card:hover { border-color: #e8d5a5; box-shadow: 0 3px 10px rgba(200,150,30,.08); }
.task-card.done { opacity: .55; }
.task-card.done .tc-title { text-decoration: line-through; }
.tc-left { display: flex; align-items: center; gap: 9px; flex: 1; min-width: 0; }
.tc-title { font-size: 14px; line-height: 1.4; }
.badge { font-size: 11px; padding: 3px 9px; border-radius: 10px; background: #eef4ff; color: #4a6db0; white-space: nowrap; font-weight: 600; }
.badge.daily { background: #fff0d6; color: #c07b00; }
.tc-right { display: flex; align-items: center; gap: 8px; }
.pb { font-size: 11px; color: #b0975c; white-space: nowrap; }

.do {
  padding: 7px 15px; border: none; border-radius: 20px; background: var(--sun); color: #fff;
  font-weight: 800; cursor: pointer; font-size: 13px; white-space: nowrap; transition: transform .1s;
}
.do:active { transform: scale(.95); }
.do.ghosty { background: #ece3cf; color: #9a8a63; }

/* 商店 */
.shop { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.shop-item { background: #fffbf2; border: 1px solid #f5e6c4; border-radius: 14px; padding: 14px 12px; text-align: center; }
.shop-name { font-weight: 700; font-size: 14px; margin-bottom: 4px; }
.shop-price { color: var(--sun-deep); font-weight: 800; margin-bottom: 10px; }

/* 流水 */
.ledger { display: flex; justify-content: space-between; padding: 8px 0; font-size: 13px; border-bottom: 1px dashed #f2e6cd; }
.lg-note { color: #6d5a2b; }
.lg-delta.pos { color: var(--ok); font-weight: 800; }
.lg-delta.neg { color: #d4491f; font-weight: 800; }

.dim { color: #b7a26b; font-size: 13px; }
.parent-btn { display: block; margin: 6px auto 0; background: none; border: none; color: #b7a26b; cursor: pointer; font-size: 13px; }
.err { color: #c62828; text-align: center; }

/* 弹窗 */
.mask { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal { background: #fff; border-radius: 20px; padding: 22px; width: 90%; max-width: 360px; }
.modal h3 { margin: 0 0 16px; }
.metric { margin-bottom: 12px; }
.metric label { display: block; font-size: 13px; color: #6d5a2b; margin-bottom: 5px; }
.metric input, .modal input { width: 100%; padding: 11px 13px; border: 1px solid #e4d5b4; border-radius: 12px; font-size: 16px; }
.metric input:focus, .modal input:focus { outline: none; border-color: var(--sun); }
.ghost { width: 100%; margin-top: 10px; padding: 10px; background: none; border: none; color: #9a8a63; cursor: pointer; }
.do.big { width: 100%; margin-top: 6px; padding: 13px; font-size: 16px; }

/* 提示 */
.toast {
  position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%);
  background: rgba(58,46,27,.92); color: #fff; padding: 11px 20px; border-radius: 24px; font-size: 14px; z-index: 30;
  box-shadow: 0 6px 20px rgba(0,0,0,.2);
  animation: rise .22s ease;
}
@keyframes rise { from { opacity: 0; transform: translate(-50%, 10px); } to { opacity: 1; transform: translate(-50%, 0); } }
</style>