<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api, setSelectedKid } from './api.js'

const emit = defineEmits(['exit', 'switched'])
const kids = ref([])
const selectedKid = ref('')
const newKid = reactive({ name: '', account: '', pin: '', term_id: 'g5s1' })
const tab = ref('weekly')
const rewards = ref([])
const ranks = ref([])
const subjects = ref([])
const units = ref([])
const tasks = ref([])
const daily = ref([])
const terms = ref([])
const activeTerm = ref('g5s1')
const cursors = ref({})
const progressLock = ref(true)
const redemptions = ref([])
const tests = ref([])
const newTest = reactive({ subject_id: '', unit_id: '', score: '', note: '' })
const TEST_BANDS = [[100, 30], [95, 20], [90, 15], [85, 10], [0, 5]]
const weekly = ref({ days: [], weeks: [], by_subject: [], kids: [], total_earned: 0, total_spent: 0, net: 0, balance: 0, earned_all: 0, streak: 0, checkins: 0, week_start: '', week_end: '' })
const toast = ref('')

const maxDayEarn = computed(() => Math.max(1, ...(weekly.value.days || []).map((d) => d.earned)))
const maxSubj = computed(() => Math.max(1, ...(weekly.value.by_subject || []).map((s) => s.count)))
const maxWeek = computed(() => Math.max(1, ...(weekly.value.weeks || []).map((w) => w.earned)))
const weekPoints = computed(() => {
  const ws = weekly.value.weeks || []
  if (!ws.length) return ''
  const W = 288, H = 80, pad = 14
  return ws.map((w, i) => {
    const x = ws.length === 1 ? pad : pad + i * (W - 2 * pad) / (ws.length - 1)
    const y = H - pad - (w.earned / maxWeek.value) * (H - 2 * pad)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

function showToast(m) { toast.value = m; setTimeout(() => (toast.value = ''), 2200) }
function unitName(id) { return units.value.find(u => u.id === id)?.name || id }

async function load() {
  const ks = await api.admin.kids()
  kids.value = ks
  if (!selectedKid.value && ks.length) {
    selectedKid.value = ks[0].id
    setSelectedKid(ks[0].id)
  }
  const [r, rk, t, rd, wk, ts] = await Promise.all([api.rewards(), api.admin.ranks(), api.tasks(), api.admin.redemptions(), api.admin.weekly(), api.admin.tests()])
  rewards.value = r
  ranks.value = rk
  subjects.value = t.subjects
  units.value = t.units
  tasks.value = t.tasks
  daily.value = t.daily
  terms.value = t.terms || []
  activeTerm.value = t.active_term || 'g5s1'
  cursors.value = t.cursors || {}
  progressLock.value = t.progress_lock === '1'
  redemptions.value = rd
  weekly.value = wk
  tests.value = ts
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
async function deliverRedeem(id) {
  try { await api.admin.deliverRedeem(id); showToast('已标记兑现'); await load() }
  catch (e) { showToast(e.message) }
}
async function addTest() {
  if (!newTest.subject_id || newTest.score === '' || newTest.score === null) return showToast('选科目、填分数')
  const sc = Number(newTest.score)
  if (sc < 0 || sc > 100) return showToast('分数要在 0~100')
  try {
    const r = await api.admin.createTest({ subject_id: newTest.subject_id, unit_id: newTest.unit_id, score: sc, note: newTest.note })
    showToast(`已发 +${r.sunshine} 阳光`)
    Object.assign(newTest, { subject_id: '', unit_id: '', score: '', note: '' })
    await load()
  } catch (e) { showToast(e.message) }
}
async function delTest(id) {
  if (!confirm('删除这条测试记录？会冲正扣回阳光。')) return
  await api.admin.delTest(id); await load()
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

// —— 密码 / 游标 ——
const pinForm = reactive({ cur: '', next: '' })
async function setCursor(subj, taskId) {
  try {
    await api.admin.setCursor({ subject_id: subj, task_id: taskId })
    cursors.value = { ...cursors.value, [subj]: taskId }
    showToast('已更新「已学到」')
  } catch (e) { showToast(e.message) }
}

async function switchKid() {
  setSelectedKid(selectedKid.value)
  emit('switched')
  await load()
}
async function pickKid(id) {
  selectedKid.value = id
  await switchKid()
}

async function addKid() {
  if (!newKid.name) return showToast('填名字')
  try {
    await api.admin.createKid({ ...newKid })
    newKid.name = newKid.account = newKid.pin = ''
    showToast('已添加')
    await load()
  } catch (e) { showToast(e.message) }
}

async function saveKid(k) {
  try {
    await api.admin.updateKid(k.id, { name: k.name, term_id: k.term_id, pin: k._pin || '' })
    k._pin = ''
    showToast('已保存')
    await load()
  } catch (e) { showToast(e.message) }
}
async function delKid(k) {
  if (!confirm('删除「' + k.name + '」？打卡记录还在库里，只是账号没了。')) return
  try {
    await api.admin.delKid(k.id)
    if (selectedKid.value === k.id) { selectedKid.value = ''; setSelectedKid('') }
    showToast('已删除')
    await load()
  } catch (e) { showToast(e.message) }
}

async function toggleLock() {
  try {
    await api.admin.setProgressLock(!progressLock.value)
    progressLock.value = !progressLock.value
    showToast(progressLock.value ? '进度锁已开：只能打当前单元' : '进度锁已关：可自由打卡')
  } catch (e) { showToast(e.message) }
}

async function changePin() {
  if (!pinForm.next) return showToast('填新密码')
  try {
    await api.admin.changePin(pinForm.next)
    pinForm.cur = pinForm.next = ''
    showToast('密码已改')
  } catch (e) { showToast(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="admin">
    <header class="a-head">
      <div>
        <div class="a-title">🛠️ 家长管理</div>
        <div class="a-sub">给孩子配置奖励、等级与任务</div>
        <label class="a-term">看哪个娃
          <select v-model="selectedKid" @change="switchKid">
            <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
          </select>
        </label>
      </div>
      <button class="a-exit" @click="emit('exit')">← 回到孩子端</button>
    </header>

    <div class="a-tabs">
      <button :class="{ on: tab === 'weekly' }" @click="tab = 'weekly'">周报</button>
      <button :class="{ on: tab === 'shop' }" @click="tab = 'shop'">商店</button>
      <button :class="{ on: tab === 'approve' }" @click="tab = 'approve'">审批</button>
      <button :class="{ on: tab === 'rank' }" @click="tab = 'rank'">等级</button>
      <button :class="{ on: tab === 'task' }" @click="tab = 'task'">任务</button>
      <button :class="{ on: tab === 'cursor' }" @click="tab = 'cursor'">已学到</button>
      <button :class="{ on: tab === 'test' }" @click="tab = 'test'">测试</button>
      <button :class="{ on: tab === 'kids' }" @click="tab = 'kids'">孩子</button>
      <button :class="{ on: tab === 'pin' }" @click="tab = 'pin'">密码</button>
    </div>

    <!-- 周报 -->
    <section v-if="tab === 'weekly'" class="a-card">
      <h3>📊 本周周报</h3>
      <p class="lead">{{ weekly.week_start }} ~ {{ weekly.week_end }}（周一到周日）</p>
      <div v-if="(weekly.kids || []).length" class="w-kids">
        <div v-for="k in weekly.kids" :key="k.id" class="w-box" :class="{ on: k.current }" @click="pickKid(k.id)">
          <span>{{ k.name }}</span><b>+{{ k.earned }}</b>
          <i class="dim">花 {{ k.spent }} · 连击 {{ k.streak }}</i>
        </div>
      </div>
      <div class="w-summary">
        <div class="w-box"><span>本周赚</span><b>+{{ weekly.total_earned }}</b></div>
        <div class="w-box"><span>兑换花</span><b>-{{ weekly.total_spent }}</b></div>
        <div class="w-box"><span>净增</span><b>{{ weekly.net }}</b></div>
        <div class="w-box"><span>当前余额</span><b>{{ weekly.balance }}</b></div>
        <div class="w-box"><span>连击</span><b>{{ weekly.streak }} 天</b></div>
        <div class="w-box"><span>本周签到</span><b>{{ weekly.checkins }} 天</b></div>
      </div>

      <h4 class="w-h">近 4 周阳光趋势</h4>
      <div class="w-trend">
        <svg viewBox="0 0 288 80" class="w-trend-svg" preserveAspectRatio="none">
          <polyline :points="weekPoints" fill="none" stroke="#3aa4e0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="w-trend-labels">
          <span v-for="w in weekly.weeks" :key="w.week_start">{{ w.label }}<i>+{{ w.earned }}</i></span>
        </div>
      </div>

      <h4 class="w-h">每天赚到的阳光</h4>
      <div class="w-chart">
        <div v-for="d in weekly.days" :key="d.date" class="w-bar-col">
          <div class="w-bar" :style="{ height: (d.earned / maxDayEarn * 100) + '%' }">
            <i v-if="d.earned">{{ d.earned }}</i>
          </div>
          <span>周{{ d.weekday }}</span>
        </div>
      </div>

      <h4 class="w-h">本周各科完成</h4>
      <div v-if="!weekly.by_subject.length" class="dim">本周还没完成任务。</div>
      <div v-else class="w-subj">
        <div v-for="s in weekly.by_subject" :key="s.name" class="w-subj-row">
          <span class="w-subj-name">{{ s.name }}</span>
          <div class="w-subj-track"><i :style="{ width: (s.count / maxSubj * 100) + '%' }"></i></div>
          <span class="w-subj-num">{{ s.count }} 次 · +{{ s.sun }}</span>
        </div>
      </div>
    </section>

    <!-- 商店 -->
    <section v-if="tab === 'shop'" class="a-card">
      <h3>兑换商店</h3>
      <p class="lead">孩子会用阳光兑换这些，改价格实时生效。</p>
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
      <h3>兑换审批与兑现</h3>
      <p class="lead">需家长同意的奖励先到「待同意」；同意后扣阳光，实际给了奖励再点「标记已兑现」。</p>
      <div v-if="!redemptions.length" class="dim">还没有任何兑换记录。</div>
      <div class="a-item" v-for="rd in redemptions" :key="rd.id">
        <span class="badge">{{ rd.name }}</span>
        <span class="dim">{{ rd.date }} · -{{ rd.price }} ☀️</span>
        <template v-if="rd.status === 'pending'">
          <span class="st pending">待同意</span>
          <button class="ok" @click="approveRedeem(rd.id)">同意</button>
          <button class="del" @click="rejectRedeem(rd.id)">拒绝</button>
        </template>
        <template v-else-if="rd.status === 'done'">
          <span class="st done">已扣阳光</span>
          <button class="ok ghost-o" @click="deliverRedeem(rd.id)">标记已兑现</button>
        </template>
        <span v-else class="st delivered">已兑现 ✓</span>
      </div>
    </section>

    <!-- 等级 -->
    <section v-if="tab === 'rank'" class="a-card">
      <h3>成长等级（按累计获得阳光）</h3>
      <p class="lead">等级看「累计获得」，消费不会掉级。</p>
      <div class="a-item" v-for="r in ranks" :key="r.id">
        <span class="rank-icon">{{ r.icon || '⭐' }}</span>
        <input v-model="r.name" class="w-name" />
        <span class="dim">≥</span>
        <input v-model.number="r.min_sunshine" type="number" class="w-num" /> 阳光
        <button class="ok" @click="saveRank(r)">保存</button>
        <button class="del" @click="delRank(r.id)">删</button>
      </div>
      <div class="a-item add">
        <span class="rank-icon">⭐</span>
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

      <h3 style="margin-top:24px">每日任务（循环打卡）</h3>
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
      <h3>已学到哪一课</h3>
      <p class="lead">推荐从这里往后，前面的课标灰「已学过」，不再计阳光。</p>
      <div class="a-item" v-for="s in ['语文','数学','英语']" :key="s">
        <span class="badge">{{ s }}</span>
        <select :value="cursors[s] || ''" @change="setCursor(s, $event.target.value)">
          <option value="">从头开始</option>
          <option v-for="t in (tasksBySubject[s] || [])" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select>
      </div>
      <div class="lock-row" style="margin-top:14px">
        <span class="badge">进度锁</span>
        <span style="flex:1">只让打「当前单元」</span>
        <button :class="['toggle', { on: progressLock }]" @click="toggleLock">{{ progressLock ? '开' : '关' }}</button>
      </div>
      <p class="lead" style="margin-top:8px">开启后，每科只有正在学的那个单元能打卡，后面的课自动锁住（灰显 🔒），防没学就打卡刷阳光。</p>
    </section>

    <!-- 单元测试成绩 -->
    <section v-if="tab === 'test'" class="a-card">
      <h3>单元测试成绩奖励</h3>
      <p class="lead">孩子考完单元测试，你录入分数，按档自动发阳光（孩子不能自己录）。</p>
      <div class="band-box">
        <span v-for="[th, sun] in TEST_BANDS" :key="th" class="band">{{ th === 0 ? '85 以下' : th + ' 分' }} → +{{ sun }} 阳光</span>
      </div>
      <div class="a-item add">
        <select v-model="newTest.subject_id" @change="newTest.unit_id = ''">
          <option value="" disabled>科目</option>
          <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <select v-model="newTest.unit_id">
          <option value="">选单元（可选）</option>
          <option v-for="u in units.filter(x => x.subject_id === newTest.subject_id)" :key="u.id" :value="u.id">{{ u.name }}</option>
        </select>
        <input v-model="newTest.score" type="number" placeholder="分数 0~100" class="w-num" />
        <input v-model="newTest.note" placeholder="备注（如：期中）" class="w-cat" />
        <button class="ok" @click="addTest">录成绩</button>
      </div>
      <div v-if="!tests.length" class="dim">还没录过测试成绩。</div>
      <div class="a-item" v-for="t in tests" :key="t.id">
        <span class="badge">{{ t.subject_id }}</span>
        <span class="badge daily">{{ t.score }} 分</span>
        <span class="dim" style="flex:1">{{ t.note || '—' }} · {{ t.date }}</span>
        <span class="st delivered">+{{ t.sunshine }} ☀️</span>
        <button class="del" @click="delTest(t.id)">删</button>
      </div>
    </section>

    <section v-if="tab === 'kids'" class="a-card">
      <h3>管理孩子</h3>
      <div class="a-item" v-for="k in kids" :key="k.id">
        <span class="badge">{{ k.name }}</span>
        <span class="dim">{{ k.account }}</span>
        <select v-model="k.term_id">
          <option v-for="tm in terms" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
        </select>
        <input v-model="k._pin" type="password" placeholder="改密码" class="w-num" />
        <button class="ok" @click="saveKid(k)">存</button>
        <button class="del" @click="delKid(k)">删</button>
      </div>
      <div class="a-item add">
        <input v-model="newKid.name" placeholder="名字" class="w-name" />
        <input v-model="newKid.account" placeholder="账号" class="w-cat" />
        <input v-model="newKid.pin" placeholder="密码" class="w-num" />
        <select v-model="newKid.term_id">
          <option v-for="tm in terms" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
        </select>
        <button class="ok" @click="addKid">添加</button>
      </div>
    </section>

    <!-- 密码 -->
    <section v-if="tab === 'pin'" class="a-card">
      <h3>修改家长密码</h3>
      <div class="a-item">
        <input v-model="pinForm.next" type="password" placeholder="新密码（至少 4 位）" class="w-name" />
        <button class="ok" @click="changePin">改密码</button>
      </div>
      <p class="dim">账号 parent；改密后旧设备要重新登录。首登请改掉迁移来的旧密码。</p>
    </section>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.admin { max-width: 780px; margin: 0 auto; padding: 14px; padding-top: calc(14px + env(safe-area-inset-top)); font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: #1f3b55; }
.a-head {
  background: linear-gradient(180deg, #4db6ea 0%, #3aa4e0 100%);
  color: #fff; border-radius: 20px; padding: 16px 20px;
  display: flex; justify-content: space-between; align-items: center;
}
.a-title { font-size: 20px; font-weight: 800; }
.a-sub { font-size: 12px; opacity: .85; margin-top: 4px; }
.a-term { display: block; margin-top: 8px; font-size: 12px; }
.a-term select { margin-left: 6px; padding: 4px 8px; border-radius: 8px; border: 1px solid #cfe4f2; background: #fff; color: #1f3b55; }
.a-exit { background: rgba(255,255,255,.22); border: none; color: #fff; border-radius: 20px; padding: 9px 16px; font-weight: 700; cursor: pointer; font-family: inherit; }
.a-tabs { display: flex; gap: 8px; margin: 14px 0; overflow-x: auto; padding-bottom: 4px; }
.a-tabs button {
  flex: 0 0 auto; padding: 9px 16px; border: 1px solid #d3e8f5; background: #fff; border-radius: 22px;
  color: #4a6780; cursor: pointer; font-weight: 700; font-size: 13px; font-family: inherit;
}
.a-tabs button.on { background: #3aa4e0; border-color: #3aa4e0; color: #fff; }
.a-card { background: #fff; border-radius: 16px; padding: 18px; margin-bottom: 14px; box-shadow: 0 4px 14px rgba(60,120,170,.07); border: 1px solid #e8f3fa; }
.a-card h3 { margin: 0 0 6px; font-size: 16px; color: #1f3b55; }
.lead { color: #7aa0b8; font-size: 12px; margin: 0 0 14px; }
.lock-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #4a6780; font-weight: 700; }
.toggle { border: none; background: #dbe6ee; color: #6b8aa1; padding: 7px 16px; border-radius: 16px; font-weight: 800; cursor: pointer; font-family: inherit; }
.toggle.on { background: #ffb800; color: #fff; }
.dim { color: #7aa0b8; font-size: 12px; }
.a-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 0; border-bottom: 1px solid #eef6fb; }
.a-item.add { border-top: 1px dashed #d3e8f5; margin-top: 8px; padding-top: 12px; }
.a-subject-h { font-weight: 800; color: #2f7db8; margin-top: 8px; font-size: 14px; }
.a-item input, .a-item select { border: 1px solid #d3e8f5; border-radius: 8px; padding: 7px 9px; font-size: 13px; color: #1f3b55; font-family: inherit; }
.a-item input:focus, .a-item select:focus { outline: none; border-color: #3aa4e0; }
.w-name { flex: 1; min-width: 120px; }
.w-num { width: 70px; }
.w-cat { width: 90px; }
.badge { font-size: 11px; padding: 3px 8px; border-radius: 10px; background: #e8f2fb; color: #2f7db8; white-space: nowrap; font-weight: 700; }
.badge.daily { background: #fff3d6; color: #c07b00; }
.rank-icon { font-size: 18px; }
.st { font-size: 11px; padding: 3px 9px; border-radius: 10px; font-weight: 700; white-space: nowrap; }
.st.pending { background: #fff3d6; color: #c07b00; }
.st.done { background: #e8f2fb; color: #2f7db8; }
.st.delivered { background: #eaf8ee; color: #2e8b57; }
.ok { padding: 7px 14px; border: none; border-radius: 16px; background: #ffb800; color: #fff; font-weight: 700; cursor: pointer; font-family: inherit; }
.ok.ghost-o { background: #3aa4e0; }
.del { padding: 6px 10px; border: none; border-radius: 14px; background: #fbe3e3; color: #c62828; cursor: pointer; font-family: inherit; }
.ghost-s { background: none; border: none; color: #2f7db8; font-size: 12px; cursor: pointer; font-family: inherit; }
.daily .d-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; width: 100%; padding: 4px 0; }
.toast { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%); background: rgba(31,59,85,.92); color: #fff; padding: 10px 18px; border-radius: 22px; font-size: 14px; z-index: 20; }

.w-kids { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 12px; }
.w-kids .w-box { cursor: pointer; }
.w-kids .w-box.on { outline: 2px solid #ffb800; }
.w-kids .w-box i { display: block; font-style: normal; font-size: 11px; }
.w-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.w-box { background: #f4fafd; border: 1px solid #e8f3fa; border-radius: 12px; padding: 12px 6px; text-align: center; }
.w-box span { display: block; font-size: 11px; color: #7aa0b8; margin-bottom: 4px; }
.w-box b { font-size: 20px; color: #1f3b55; }
.w-h { margin: 20px 0 10px; font-size: 14px; color: #1f3b55; }
.w-trend { margin-bottom: 4px; }
.w-trend-svg { width: 100%; height: 90px; }
.w-trend-labels { display: flex; justify-content: space-between; font-size: 11px; color: #7aa0b8; margin-top: 6px; }
.w-trend-labels i { font-style: normal; color: #2f7db8; font-weight: 700; margin-left: 3px; }
.w-chart { display: flex; align-items: flex-end; gap: 8px; height: 140px; padding-top: 20px; }
.w-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; height: 100%; justify-content: flex-end; }
.w-bar { width: 100%; max-width: 34px; background: #ffb800; border-radius: 6px 6px 0 0; position: relative; min-height: 2px; }
.w-bar i { position: absolute; top: -20px; left: 0; width: 100%; text-align: center; font-size: 11px; color: #c07b00; font-style: normal; font-weight: 700; }
.w-bar-col span { font-size: 11px; color: #4a6780; }
.w-subj-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.w-subj-name { width: 48px; font-weight: 700; color: #1f3b55; flex: none; }
.w-subj-track { flex: 1; background: #e8f3fa; border-radius: 6px; height: 12px; overflow: hidden; }
.w-subj-track i { display: block; height: 100%; background: linear-gradient(90deg,#4db6ea,#3aa4e0); border-radius: 6px; }
.w-subj-num { flex: none; font-size: 12px; color: #4a6780; }
.band-box { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; }
.band { font-size: 12px; padding: 4px 10px; border-radius: 12px; background: #fff3d6; color: #c07b00; font-weight: 700; }

@media (max-width: 560px) {
  .w-summary { grid-template-columns: repeat(2, 1fr); }
}
</style>