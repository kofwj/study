<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from './api.js'

const emit = defineEmits(['exit'])
const tab = ref('shop')
const rewards = ref([])
const ranks = ref([])
const subjects = ref([])
const units = ref([])
const tasks = ref([])
const daily = ref([])
const cursors = ref({})
const redemptions = ref([])
const toast = ref('')

function showToast(m) { toast.value = m; setTimeout(() => (toast.value = ''), 2200) }
function unitName(id) { return units.value.find(u => u.id === id)?.name || id }

async function load() {
  const [r, rk, t, rd] = await Promise.all([api.rewards(), api.admin.ranks(), api.tasks(), api.admin.redemptions()])
  rewards.value = r
  ranks.value = rk
  subjects.value = t.subjects
  units.value = t.units
  tasks.value = t.tasks
  daily.value = t.daily
  cursors.value = t.cursors || {}
  redemptions.value = rd
}

// —— 商店 ——
const newReward = reactive({ name: '', price: 30, category: '娱乐' })
async function addReward() {
  if (!newReward.name || !newReward.price) return showToast('填名称和价格')
  await api.admin.createReward({ ...newReward })
  Object.assign(newReward, { name: '', price: 30, category: '娱乐' })
  showToast('已新增'); await load()
}
async function saveReward(r) { await api.admin.updateReward(r.id, r); showToast('已保存') }
async function delReward(id) { if (!confirm('删除这个奖励？')) return; await api.admin.delReward(id); await load() }

// —— 兑换审批 ——
async function approveRedeem(id) {
  try { await api.admin.approveRedeem(id); showToast('已同意并扣除阳光'); await load() }
  catch (e) { showToast(e.message) }
}
async function rejectRedeem(id) {
  if (!confirm('拒绝这条申请？')) return
  try { await api.admin.rejectRedeem(id); showToast('已拒绝'); await load() }
  catch (e) { showToast(e.message) }
}

// —— 等级 ——
const newRank = reactive({ name: '', min_sunshine: 0 })
async function addRank() {
  if (!newRank.name) return showToast('填等级名')
  await api.admin.createRank({ ...newRank })
  Object.assign(newRank, { name: '', min_sunshine: 0 })
  showToast('已新增'); await load()
}
async function saveRank(r) { await api.admin.updateRank(r.id, r); showToast('已保存') }
async function delRank(id) {
  if (!confirm('删除这个等级？')) return
  try { await api.admin.delRank(id); await load() } catch (e) { showToast(e.message) }
}

// —— 单元任务 ——
const newTask = reactive({ subject_id: '', unit_id: '', action: '', title: '', sunshine: 5 })
const unitOptions = computed(() => units.value.filter(u => u.subject_id === newTask.subject_id))
function pickSubject() { newTask.unit_id = '' }
async function addTask() {
  if (!newTask.subject_id || !newTask.unit_id || !newTask.title) return showToast('选科目/单元、填标题')
  await api.admin.createTask({ ...newTask })
  Object.assign(newTask, { subject_id: '', unit_id: '', action: '', title: '', sunshine: 5 })
  showToast('已新增'); await load()
}
async function saveTask(t) { await api.admin.updateTask(t.id, t); showToast('已保存') }
async function delTask(id) { if (!confirm('删除这个任务？')) return; await api.admin.delTask(id); await load() }

const tasksBySubject = computed(() => {
  const m = {}
  for (const t of tasks.value) {
    if (!m[t.subject_id]) m[t.subject_id] = []
    m[t.subject_id].push(t)
  }
  return m
})
const subjectName = (id) => subjects.value.find(s => s.id === id)?.name || id

// —— 每日任务 ——
const DIRS = [['higher_better', '越多越好'], ['lower_better', '越少越好']]
const newDaily = reactive({ subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, metrics: [] })
function addMetric(arr) { arr.push({ id: 'm' + Date.now(), label: '', unit: '', direction: 'higher_better', note: '' }) }
const cleanMetrics = (ms) => (ms || []).map(({ id, label, unit, direction }) => ({ id, label, unit, direction }))
async function addDaily() {
  if (!newDaily.name) return showToast('填任务名')
  await api.admin.createDaily({ ...newDaily, metrics: cleanMetrics(newDaily.metrics) })
  Object.assign(newDaily, { subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, metrics: [] })
  showToast('已新增'); await load()
}
async function saveDaily(d) {
  await api.admin.updateDaily(d.id, { subject_id: d.subject_id, name: d.name, sunshine: d.sunshine, bonus_per_metric: d.bonus_per_metric, metrics: cleanMetrics(d.metrics) })
  showToast('已保存')
}
async function delDaily(id) { if (!confirm('删除这个每日任务？')) return; await api.admin.delDaily(id); await load() }

// —— 密码 ——
const pinForm = reactive({ cur: '', next: '' })
async function setCursor(subj, taskId) {
  try {
    await api.admin.setCursor({ subject_id: subj, task_id: taskId })
    cursors.value = { ...cursors.value, [subj]: taskId }
    showToast('已更新「已学到」')
  } catch (e) { showToast(e.message) }
}

async function changePin() {
  if (!pinForm.next) return showToast('填新密码')
  try {
    await api.admin.changePin(pinForm.next)
    sessionStorage.setItem('admin_pin', pinForm.next)
    pinForm.cur = pinForm.next = ''
    showToast('密码已改')
  } catch (e) { showToast(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="admin">
    <header class="a-head">
      <span class="a-title">🛠️ 家长管理</span>
      <button class="a-exit" @click="emit('exit')">← 回到孩子端</button>
    </header>

    <div class="a-tabs">
      <button :class="{ on: tab === 'shop' }" @click="tab = 'shop'">商店</button>
      <button :class="{ on: tab === 'approve' }" @click="tab = 'approve'">审批</button>
      <button :class="{ on: tab === 'rank' }" @click="tab = 'rank'">等级</button>
      <button :class="{ on: tab === 'task' }" @click="tab = 'task'">任务</button>
      <button :class="{ on: tab === 'cursor' }" @click="tab = 'cursor'">已学到</button>
      <button :class="{ on: tab === 'pin' }" @click="tab = 'pin'">密码</button>
    </div>

    <!-- 商店 -->
    <section v-if="tab === 'shop'" class="a-card">
      <h3>兑换商店</h3>
      <div class="a-item" v-for="r in rewards" :key="r.id">
        <input v-model="r.name" class="w-name" />
        <input v-model.number="r.price" type="number" class="w-num" /> ☀️
        <input v-model="r.category" class="w-cat" />
        <button class="ok" @click="saveReward(r)">保存</button>
        <button class="del" @click="delReward(r.id)">删</button>
      </div>
      <div class="a-item add">
        <input v-model="newReward.name" placeholder="奖励名（如：看动画30分钟）" class="w-name" />
        <input v-model.number="newReward.price" type="number" placeholder="价格" class="w-num" />
        <input v-model="newReward.category" placeholder="分类" class="w-cat" />
        <button class="ok" @click="addReward">＋新增</button>
      </div>
    </section>

    <!-- 审批 -->
    <section v-if="tab === 'approve'" class="a-card">
      <h3>兑换审批（需家长同意的奖励）</h3>
      <p class="dim">孩子申请「游乐场/心愿礼物」这类奖励会先到这里，你同意后才会扣阳光。</p>
      <div v-if="!redemptions.length" class="dim">还没有任何兑换记录。</div>
      <div class="a-item" v-for="rd in redemptions" :key="rd.id">
        <span class="badge">{{ rd.name }}</span>
        <span class="dim">{{ rd.date }} · -{{ rd.price }} ☀️</span>
        <template v-if="rd.status === 'pending'">
          <button class="ok" @click="approveRedeem(rd.id)">同意</button>
          <button class="del" @click="rejectRedeem(rd.id)">拒绝</button>
        </template>
        <span v-else class="badge daily">{{ rd.status === 'done' ? '已兑换' : rd.status }}</span>
      </div>
    </section>

    <!-- 等级 -->
    <section v-if="tab === 'rank'" class="a-card">
      <h3>成长等级（按累计获得阳光）</h3>
      <div class="a-item" v-for="r in ranks" :key="r.id">
        <input v-model="r.name" class="w-name" />
        <span class="dim">≥</span>
        <input v-model.number="r.min_sunshine" type="number" class="w-num" /> 阳光
        <button class="ok" @click="saveRank(r)">保存</button>
        <button class="del" @click="delRank(r.id)">删</button>
      </div>
      <div class="a-item add">
        <input v-model="newRank.name" placeholder="等级名（如：阳光萌新）" class="w-name" />
        <span class="dim">≥</span>
        <input v-model.number="newRank.min_sunshine" type="number" placeholder="0" class="w-num" />
        <button class="ok" @click="addRank">＋新增</button>
      </div>
    </section>

    <!-- 任务 -->
    <section v-if="tab === 'task'" class="a-card">
      <h3>单元任务</h3>
      <div v-for="(arr, sid) in tasksBySubject" :key="sid" class="a-subject">
        <div class="a-subject-h">{{ subjectName(sid) }}</div>
        <div class="a-item" v-for="t in arr" :key="t.id">
          <span class="badge">{{ unitName(t.unit_id) }}</span>
          <input v-model="t.action" class="w-cat" />
          <input v-model="t.title" class="w-name" />
          <input v-model.number="t.sunshine" type="number" class="w-num" />
          <button class="ok" @click="saveTask(t)">保存</button>
          <button class="del" @click="delTask(t.id)">删</button>
        </div>
      </div>
      <div class="a-item add">
        <select v-model="newTask.subject_id" @change="pickSubject">
          <option value="" disabled>科目</option>
          <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <select v-model="newTask.unit_id">
          <option value="" disabled>单元</option>
          <option v-for="u in unitOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
        </select>
        <input v-model="newTask.action" placeholder="动作" class="w-cat" />
        <input v-model="newTask.title" placeholder="标题" class="w-name" />
        <input v-model.number="newTask.sunshine" type="number" class="w-num" />
        <button class="ok" @click="addTask">＋新增</button>
      </div>

      <h3 style="margin-top:20px">每日任务（循环打卡）</h3>
      <div class="a-item daily" v-for="d in daily" :key="d.id">
        <div class="d-row">
          <span class="badge daily">每天</span>
          <input v-model="d.name" class="w-name" />
          <input v-model.number="d.sunshine" type="number" class="w-num" /> 基础
          <input v-model.number="d.bonus_per_metric" type="number" class="w-num" /> 破纪录/项
          <button class="ok" @click="saveDaily(d)">保存</button>
          <button class="del" @click="delDaily(d.id)">删</button>
        </div>
        <div class="d-row" v-for="(m, i) in d.metrics" :key="m.id">
          <span class="dim">维度</span>
          <input v-model="m.label" placeholder="名称" class="w-cat" />
          <input v-model="m.unit" placeholder="单位" class="w-cat" />
          <select v-model="m.direction">
            <option v-for="[v, n] in DIRS" :key="v" :value="v">{{ n }}</option>
          </select>
          <button class="del" @click="d.metrics.splice(i, 1)">×</button>
        </div>
        <button class="ghost-s" @click="addMetric(d.metrics)">＋加维度</button>
      </div>
      <div class="a-item add daily">
        <input v-model="newDaily.name" placeholder="任务名（如：跳绳打卡）" class="w-name" />
        <input v-model.number="newDaily.sunshine" type="number" class="w-num" />
        <input v-model.number="newDaily.bonus_per_metric" type="number" class="w-num" />
        <button class="ok" @click="addDaily">＋新增</button>
      </div>
    </section>

    <!-- 已学到 -->
    <section v-if="tab === 'cursor'" class="a-card">
      <h3>已学到哪一课（推荐从这里往后，前面不加阳光）</h3>
      <div class="a-item" v-for="s in ['语文','数学','英语']" :key="s">
        <span class="badge">{{ s }}</span>
        <select :value="cursors[s] || ''" @change="setCursor(s, $event.target.value)">
          <option value="">从头开始</option>
          <option v-for="t in (tasksBySubject[s] || [])" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select>
      </div>
      <p class="dim">语文默认已学到《珍珠鸟》。开学中途接入时把锚点拨到当前课。</p>
    </section>

    <!-- 密码 -->
    <section v-if="tab === 'pin'" class="a-card">
      <h3>修改家长密码</h3>
      <div class="a-item">
        <input v-model="pinForm.next" type="password" placeholder="新密码（默认 8888）" class="w-name" />
        <button class="ok" @click="changePin">改密码</button>
      </div>
      <p class="dim">孩子端看不到这里，需输入密码才能进入管理。</p>
    </section>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.admin { max-width: 720px; margin: 0 auto; padding: 14px; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: #4a3b1f; }
.a-head { display: flex; justify-content: space-between; align-items: center; }
.a-title { font-size: 18px; font-weight: 800; color: #6d4c00; }
.a-exit { background: none; border: 1px solid #e4d5b4; border-radius: 20px; padding: 6px 14px; color: #8a7444; cursor: pointer; }
.a-tabs { display: flex; gap: 8px; margin: 14px 0; }
.a-tabs button { padding: 8px 16px; border: 1px solid #f0e0bb; background: #fff; border-radius: 20px; color: #8a7444; cursor: pointer; }
.a-tabs button.on { background: #ffb800; border-color: #ffb800; color: #fff; font-weight: 700; }
.a-card { background: #fff; border-radius: 16px; padding: 16px; margin-bottom: 14px; }
.a-card h3 { margin: 0 0 12px; font-size: 15px; color: #6d5a2b; }
.a-item { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 7px 0; border-bottom: 1px solid #f7ecd4; }
.a-item.add { border-top: 1px dashed #e8dfc8; margin-top: 8px; padding-top: 10px; }
.a-subject-h { font-weight: 700; color: #6d5a2b; margin-top: 6px; }
.a-item input, .a-item select { border: 1px solid #e4d5b4; border-radius: 8px; padding: 6px 8px; font-size: 13px; }
.w-name { flex: 1; min-width: 120px; }
.w-num { width: 70px; }
.w-cat { width: 90px; }
.badge { font-size: 10px; padding: 2px 7px; border-radius: 9px; background: #eef4ff; color: #4a6db0; white-space: nowrap; }
.badge.daily { background: #fff0d6; color: #c07b00; }
.dim { color: #b7a26b; font-size: 12px; }
.ok { padding: 6px 12px; border: none; border-radius: 16px; background: #ffb800; color: #fff; font-weight: 700; cursor: pointer; }
.del { padding: 5px 9px; border: none; border-radius: 14px; background: #fbe3e3; color: #c62828; cursor: pointer; }
.ghost-s { background: none; border: none; color: #b8860b; font-size: 12px; cursor: pointer; }
.daily .d-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; width: 100%; padding: 4px 0; }
.toast { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%); background: rgba(60,45,10,.9); color: #fff; padding: 10px 18px; border-radius: 22px; font-size: 14px; z-index: 20; }
</style>