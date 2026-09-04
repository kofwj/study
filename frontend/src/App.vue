<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from './api.js'
import Admin from './Admin.vue'

const data = reactive({
  level: { earned: 0, balance: 0, level: '阳光萌新', next: null, next_need: 0, progress: 0 },
  streak: 0,
  kid_name: '乐乐',
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
    Object.assign(data, t)
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
  if (!confirm(`确定用 ${reward.price} 阳光兑换「${reward.name}」吗？`)) return
  try {
    await api.redeem(reward.id)
    showToast(`兑换成功 🎁 -${reward.price} 阳光`)
    shopOpen.value = false
    await refresh()
  } catch (e) { showToast(e.message) }
}

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
    const cur = units.find(u => u.tasks.some(t => !t.done))
    if (cur) out.push(...cur.tasks.filter(t => !t.done).slice(0, 2))
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
          <div class="hello">你好呀，五年级的小主人！</div>
          <div class="name-row">
            <template v-if="!renaming">
              <b class="kid">{{ data.kid_name }}</b>
              <button class="rename" @click="renaming = true; renameVal = data.kid_name">✏️ 点击改名</button>
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
        <span class="pill star">⭐ {{ data.level.level }}</span>
      </div>
      <div class="next">
        下一级 {{ data.level.next || '满级' }}
        <span v-if="data.level.next">（{{ data.level.earned }}/{{ data.level.next_need }} ☀️）</span>
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
            </div>
          </div>
        </template>

        <template v-else>
          <h1>{{ ICONS[activeTab] || '📒' }} {{ activeTab }}</h1>
          <p class="hint">完成一项 +5 ☀️，取消勾选会扣回哦。把鼠标移到卡片右上角可以删除自定义任务。</p>

          <div v-for="u in currentUnits" :key="u.id" class="unit">
            <h2><i></i> {{ u.name }}</h2>
            <div class="grid">
              <div v-for="t in u.tasks" :key="t.id" class="card" :class="{ done: t.done }">
                <button v-if="t.custom" class="x" title="删除" @click="delCustom(t)">×</button>
                <button class="circle" :class="{ ok: t.done }" @click="toggleTask(t)">{{ t.done ? '✓' : '' }}</button>
                <div class="card-body">
                  <div class="card-title">{{ t.title }}</div>
                  <div class="plus">+{{ t.sunshine }} ☀️</div>
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
      <span class="foot-label">自定义任务</span>
      <input v-model="customTitle" class="foot-input" placeholder="任务名称，如：背古诗《山居秋暝》"
        @keyup.enter="addCustom" />
      <button class="foot-add" @click="addCustom">添加</button>
      <button class="shop-fab" @click="shopOpen = true">🛒 阳光兑换商店</button>
    </footer>

    <!-- 商店抽屉 -->
    <div v-if="shopOpen" class="mask" @click.self="shopOpen = false">
      <div class="shop-modal">
        <h3>🛒 阳光兑换商店</h3>
        <div class="shop-list">
          <div v-for="r in rewards" :key="r.id" class="shop-item">
            <div>
              <div class="shop-name">{{ r.name }}</div>
              <div class="shop-price">☀️ {{ r.price }}</div>
            </div>
            <button class="do" :disabled="data.level.balance < r.price" @click="redeem(r)">兑换</button>
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
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.card {
  position: relative; background: #fff; border-radius: 16px; padding: 16px 14px 14px 14px;
  display: flex; gap: 10px; align-items: flex-start; min-height: 86px;
  box-shadow: 0 4px 14px rgba(60,120,170,.07); border: 1px solid #e8f3fa;
}
.card.done { background: #eaf8ee; border-color: #cfead6; }
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
.do { border: none; background: #3aa4e0; color: #fff; border-radius: 16px; padding: 8px 16px; font-weight: 800; cursor: pointer; }
.do:disabled { background: #c5d8e6; cursor: default; }
.do.big { width: 100%; padding: 12px; margin-top: 8px; }
.ghost { width: 100%; margin-top: 8px; border: none; background: none; color: #7aa0b8; cursor: pointer; }
.metric { margin-bottom: 10px; }
.metric label { display: block; font-size: 13px; margin-bottom: 4px; }
.shop-modal input, .metric input { width: 100%; padding: 10px 12px; border: 1px solid #d7e6f0; border-radius: 10px; font-size: 15px; }
.parent { position: fixed; left: 16px; bottom: 86px; border: none; background: none; color: #7aa0b8; cursor: pointer; z-index: 5; }
.err { color: #c62828; text-align: center; }

@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
  .body { flex-direction: column; }
  .side { width: 100%; flex: none; display: flex; overflow-x: auto; }
  .nav { min-width: 120px; }
  .next { margin-left: 0; text-align: left; width: 100%; }
}
</style>
