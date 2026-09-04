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
  toastTimer = setTimeout(() => (toast.value = ''), 2500)
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
      showToast(`完成 +${r.delta} 阳光 ☀️`)
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
  // unit tasks grouped
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
const activeTab = ref('')

onMounted(async () => {
  await refresh()
  if (data.subjects.length) activeTab.value = data.subjects[0].id
})

function pickValue(daily, id) {
  return daily.today_metrics?.[id] ?? ''
}
</script>

<template>
  <Admin v-if="isAdmin" @exit="exitAdmin" />
  <div v-else class="wrap">
    <!-- 顶栏 -->
    <header class="top">
      <div class="level">
        <div class="lv-line">
          <span class="lv-name">{{ data.level.level }}</span>
          <span v-if="data.level.next" class="lv-next">→ {{ data.level.next }}</span>
        </div>
        <div class="bar"><i :style="{ width: data.level.progress + '%' }"></i></div>
        <div class="lv-meta">
          <span>累计 {{ data.level.earned }} ☀️</span>
          <span v-if="data.level.next" class="dim">还差 {{ data.level.next_need - data.level.earned }} 升级</span>
        </div>
      </div>
      <div class="right">
        <div class="balance">☀️ {{ data.level.balance }}</div>
        <div class="streak">🔥 连续 {{ data.streak }} 天</div>
      </div>
    </header>

    <!-- 签到 -->
    <button class="checkin-btn" :disabled="data.today_checkin" @click="checkin">
      {{ data.today_checkin ? '今日已签到 ✅' : '🌞 每日签到领阳光' }}
    </button>

    <!-- 今日推荐 -->
    <section class="card">
      <h2>⭐ 今日推荐</h2>
      <p v-if="!recommend.length" class="dim">今天都完成啦，太棒了！</p>
      <div v-for="t in recommend" :key="t.id || t.name" class="row">
        <div class="t-info">
          <span class="badge" :class="t.frequency === 'daily' ? 'daily' : ''">{{ t.frequency === 'daily' ? '每天' : t.action }}</span>
          <span class="t-title">{{ t.frequency === 'daily' ? t.name : t.title }}</span>
        </div>
        <div class="t-actions">
          <span v-if="t.frequency === 'daily' && t.pb && Object.values(t.pb).some(v => v !== null)" class="pb">纪录 {{ Object.values(t.pb).filter(v => v !== null).join(' / ') }}</span>
          <button v-if="t.frequency === 'daily'" class="do" @click="openDaily(t)">去打卡</button>
          <button v-else class="do" @click="toggleTask(t)">完成 +{{ t.sunshine }}</button>
        </div>
      </div>
    </section>

    <!-- 学科任务 -->
    <section class="card">
      <div class="tabs">
        <button v-for="s in data.subjects" :key="s.id"
          :class="{ active: activeTab === s.id }" @click="activeTab = s.id">{{ s.name }}</button>
      </div>
      <div v-if="bySubject[activeTab]" class="units">
        <div v-for="u in bySubject[activeTab].units" :key="u.id" class="unit">
          <div class="unit-h">{{ u.name }} <span class="dim">({{ u.tasks.filter(t => !t.done).length }}/{{ u.tasks.length }} 未完成)</span></div>
          <div v-for="t in u.tasks" :key="t.id" class="row" :class="{ done: t.done }">
            <div class="t-info">
              <span class="badge">{{ t.action }}</span>
              <span class="t-title">{{ t.title }}</span>
            </div>
            <button class="do" @click="toggleTask(t)">{{ t.done ? '取消' : '+5' }}</button>
          </div>
        </div>
        <!-- 体育每日卡 -->
        <div class="unit" v-if="data.daily.some(x => x.subject_id === activeTab)">
          <div class="unit-h">每日打卡</div>
          <div v-for="d in data.daily.filter(x => x.subject_id === activeTab)" :key="d.id" class="row" :class="{ done: d.done_today }">
            <div class="t-info">
              <span class="badge daily">每天</span>
              <span class="t-title">{{ d.name }}</span>
            </div>
            <div class="t-actions">
              <span v-if="d.pb && Object.values(d.pb).some(v => v !== null)" class="pb">纪录 {{ Object.values(d.pb).filter(v => v !== null).join(' / ') }}</span>
              <button class="do" v-if="!d.done_today" @click="openDaily(d)">去打卡</button>
              <button class="do" v-else @click="cancelDaily(d)">取消</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 商店 -->
    <section class="card">
      <h2>🛒 阳光兑换商店</h2>
      <div class="shop">
        <div v-for="r in rewards" :key="r.id" class="shop-item">
          <div class="shop-name">{{ r.name }}</div>
          <div class="shop-price">☀️ {{ r.price }}</div>
          <button class="do" :class="{ disabled: data.level.balance < r.price }" @click="redeem(r)">兑换</button>
        </div>
      </div>
    </section>

    <!-- 流水 -->
    <section class="card">
      <h2>📜 最近流水</h2>
      <div v-for="l in ledger" :key="l.id" class="ledger">
        <span class="note">{{ l.note }}</span>
        <span class="delta" :class="l.delta > 0 ? 'pos' : 'neg'">{{ l.delta > 0 ? '+' : '' }}{{ l.delta }}</span>
      </div>
      <p v-if="!ledger.length" class="dim">还没有记录</p>
    </section>

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

    <!-- 家长入口 -->
    <button class="parent-btn" @click="pinForm.open = true">👤 家长</button>

    <div v-if="toast" class="toast">{{ toast }}</div>
    <p v-if="err" class="err">{{ err }}</p>

    <!-- 家长密码弹窗 -->
    <div v-if="pinForm.open" class="mask" @click.self="pinForm.open = false">
      <div class="modal">
        <h3>家长密码</h3>
        <input v-model="pinForm.val" type="password" inputmode="numeric" placeholder="密码" @keyup.enter="verifyPin" />
        <button class="do big" @click="verifyPin">进入管理</button>
        <button class="ghost" @click="pinForm.open = false">取消</button>
      </div>
    </div>
  </div>
</template>

<style>
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  margin: 0; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #fff7e6; color: #4a3b1f;
}
.wrap { max-width: 720px; margin: 0 auto; padding: 14px 14px 40px; }

.top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.level { flex: 1; }
.lv-line { display: flex; align-items: baseline; gap: 8px; }
.lv-name { font-size: 20px; font-weight: 700; color: #b8860b; }
.lv-next { font-size: 12px; color: #b0975c; }
.bar { height: 8px; background: #f2e3c0; border-radius: 6px; overflow: hidden; margin: 6px 0; }
.bar i { display: block; height: 100%; background: linear-gradient(90deg,#ffb800,#ff8a00); border-radius: 6px; transition: width .4s; }
.lv-meta { font-size: 12px; color: #8a7444; display: flex; gap: 10px; }
.right { text-align: right; }
.balance { font-size: 26px; font-weight: 800; color: #ff8a00; }
.streak { font-size: 12px; color: #8a7444; }

.checkin-btn {
  width: 100%; margin: 14px 0; padding: 14px; font-size: 16px; font-weight: 700;
  background: linear-gradient(135deg,#ffd54f,#ffb300); color: #6d4c00; border: none;
  border-radius: 14px; cursor: pointer;
}
.checkin-btn:disabled { background: #e8dfc8; color: #9a8a63; cursor: default; }

.card { background: #fff; border-radius: 16px; padding: 16px; margin-bottom: 14px; box-shadow: 0 2px 10px rgba(180,130,20,.06); }
.card h2 { margin: 0 0 12px; font-size: 16px; color: #4a3b1f; }

.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.tabs button { padding: 7px 14px; border: 1px solid #f0e0bb; background: #fff; border-radius: 20px; color: #8a7444; cursor: pointer; font-size: 14px; }
.tabs button.active { background: #ffb800; border-color: #ffb800; color: #fff; font-weight: 700; }

.unit { margin-bottom: 14px; }
.unit-h { font-weight: 700; font-size: 14px; margin-bottom: 6px; color: #6d5a2b; }
.row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 9px 0; border-bottom: 1px solid #f7ecd4; }
.row.done { opacity: .55; }
.t-info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.t-title { font-size: 14px; }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: #eef4ff; color: #4a6db0; white-space: nowrap; }
.badge.daily { background: #fff0d6; color: #c07b00; }
.pb { font-size: 11px; color: #b0975c; }
.t-actions { display: flex; align-items: center; gap: 8px; }
.do {
  padding: 7px 14px; border: none; border-radius: 20px; background: #ffb800; color: #fff;
  font-weight: 700; cursor: pointer; font-size: 13px; white-space: nowrap;
}
.do:active { transform: scale(.96); }
.do.disabled { background: #e0d6be; cursor: not-allowed; }
.do.big { width: 100%; padding: 13px; font-size: 16px; }

.shop { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.shop-item { background: #fffaf0; border: 1px solid #f5e6c4; border-radius: 12px; padding: 12px; text-align: center; }
.shop-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
.shop-price { color: #ff8a00; font-weight: 700; margin-bottom: 8px; }

.ledger { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; border-bottom: 1px dashed #f2e6cd; }
.ledger .note { color: #6d5a2b; }
.delta.pos { color: #2e7d32; font-weight: 700; }
.delta.neg { color: #c62828; font-weight: 700; }

.dim { color: #b7a26b; font-size: 13px; }
.parent-btn { float: right; margin: 14px 0; background: none; border: 1px solid #e4d5b4; border-radius: 20px; padding: 6px 14px; color: #8a7444; cursor: pointer; }
.err { color: #c62828; text-align: center; }

.mask { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal { background: #fff; border-radius: 16px; padding: 20px; width: 90%; max-width: 360px; }
.modal h3 { margin: 0 0 14px; }
.metric { margin-bottom: 12px; }
.metric label { display: block; font-size: 13px; color: #6d5a2b; margin-bottom: 4px; }
.metric input { width: 100%; padding: 10px 12px; border: 1px solid #e4d5b4; border-radius: 10px; font-size: 16px; }
.ghost { width: 100%; margin-top: 10px; padding: 10px; background: none; border: none; color: #9a8a63; cursor: pointer; }

.toast {
  position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%);
  background: rgba(60,45,10,.9); color: #fff; padding: 10px 18px; border-radius: 22px; font-size: 14px; z-index: 20;
}
</style>