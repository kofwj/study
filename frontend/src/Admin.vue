<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api, setSelectedKid } from './api.js'
import { rankIcon } from './icons.js'
import { BarChart3, Baby, Users, KeyRound, Lock, Store, Trophy, ClipboardCheck, BookOpen, RefreshCw, MapPinned, FileText, Settings, Sun, Star, Check, ArrowLeft } from 'lucide-vue-next'

const emit = defineEmits(['exit', 'switched'])
const kids = ref([])
const members = ref([])
const inviteProtect = ref(false)
const invites = ref([])
const selectedKid = ref('')
const newKid = reactive({ name: '', account: '', pin: '', term_id: 'g5s1' })
const section = ref('weekly')
const SECTIONS = [
  { group: '概览', items: [{ id: 'weekly', icon: BarChart3, label: '周报' }] },
  { group: '家庭', items: [
    { id: 'kids', icon: Baby, label: '孩子' },
    { id: 'members', icon: Users, label: '家长成员' },
    { id: 'invites', icon: KeyRound, label: '邀请码' },
    { id: 'pin', icon: Lock, label: '家长密码' },
  ] },
  { group: '奖励', items: [
    { id: 'shop', icon: Store, label: '兑换商店' },
    { id: 'rank', icon: Trophy, label: '成长等级' },
    { id: 'approve', icon: ClipboardCheck, label: '兑换审批' },
  ] },
  { group: '学习', items: [
    { id: 'unit-task', icon: BookOpen, label: '单元任务' },
    { id: 'daily', icon: RefreshCw, label: '每日任务' },
    { id: 'cursor', icon: MapPinned, label: '已学到' },
    { id: 'test', icon: FileText, label: '单元测试' },
  ] },
]
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
  const [ks, ms, fam, inv] = await Promise.all([api.admin.kids(), api.admin.members(), api.admin.family(), api.admin.invites()])
  kids.value = ks
  members.value = ms
  inviteProtect.value = !!fam.invite_protect
  invites.value = inv
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
async function refreshInvites() { invites.value = await api.admin.invites() }
async function makeInvite(role) {
  try {
    const r = await api.admin.invite(role)
    await refreshInvites()
    showToast('已生成 ' + r.code + '，点「复制」分享')
  } catch (e) { showToast(e.message) }
}
function inviteStatus(iv) {
  if (iv.expired) return '已过期'
  if (iv.used_up) return '已用' + (iv.used_by ? '（' + iv.used_by + '）' : '')
  if (iv.used_count > 0) return '已用 ' + iv.used_count + ' 次' + (iv.used_by ? '（最近 ' + iv.used_by + '）' : '')
  return '未用'
}
async function copyCode(code) {
  try {
    await navigator.clipboard.writeText(code)
  } catch {
    const t = document.createElement('textarea')
    t.value = code; document.body.appendChild(t); t.select()
    document.execCommand('copy'); document.body.removeChild(t)
  }
  showToast('已复制 ' + code)
}
async function delInvite(code) {
  try { await api.admin.delInvite(code); await refreshInvites(); showToast('已删除') } catch (e) { showToast(e.message) }
}
async function toggleProtect(e) {
  try {
    await api.admin.setInviteProtect(e.target.checked)
    inviteProtect.value = e.target.checked
    showToast(e.target.checked ? '邀请码保护已开（一次性 + 24h）' : '邀请码保护已关（常驻复用）')
  } catch (err) { showToast(err.message); e.target.checked = inviteProtect.value }
}
async function delMember(m) {
  if (!confirm('删除「' + m.name + '」？立刻失效。')) return
  try {
    await api.admin.delMember(m.id)
    showToast('已删除')
    await load()
  } catch (e) { showToast(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="admin">
    <header class="a-head">
      <div>
        <div class="a-title"><Settings class="ico" :size="18" /> 家长管理</div>
        <div class="a-sub">给孩子配置奖励、等级与任务</div>
        <label class="a-term">看哪个娃
          <select v-model="selectedKid" @change="switchKid">
            <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
          </select>
        </label>
      </div>
      <button class="a-exit" @click="emit('exit')"><ArrowLeft class="ico" :size="14" /> 回到孩子端</button>
    </header>

    <div class="a-body">
      <aside class="a-side">
        <template v-for="g in SECTIONS" :key="g.group">
          <div class="a-group">{{ g.group }}</div>
          <button v-for="it in g.items" :key="it.id" :class="['a-nav', { on: section === it.id }]" @click="section = it.id">
            <span class="a-nav-ico"><component :is="it.icon" :size="16" /></span>{{ it.label }}
          </button>
        </template>
      </aside>
      <main class="a-main">

    <!-- 周报 -->
    <section v-if="section === 'weekly'" class="a-card enter">
      <h3><BarChart3 class="ico" :size="16" /> 本周周报</h3>
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
          <polyline :points="weekPoints" fill="none" stroke="var(--brand)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
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
    <section v-if="section === 'shop'" class="a-card enter">
      <h3>兑换商店</h3>
      <p class="lead">孩子会用阳光兑换这些，改价格实时生效。</p>
      <div class="task-row" v-for="r in rewards" :key="r.id">
        <label class="fld grow"><span>奖励名</span><input v-model="r.name" /></label>
        <label class="fld w64"><span>阳光</span><input v-model.number="r.price" type="number" /></label>
        <label class="fld w84"><span>分类</span><input v-model="r.category" /></label>
        <div class="ops">
          <button class="ok" @click="saveReward(r)">保存</button>
          <button class="del" @click="delReward(r.id)">删</button>
        </div>
      </div>
      <div class="add-box">
        <div class="add-title">新增奖励</div>
        <div class="frm-row">
          <label class="fld grow"><span>奖励名</span><input v-model="newReward.name" placeholder="如：看动画30分钟" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="newReward.price" type="number" placeholder="30" /></label>
          <label class="fld w84"><span>分类</span><input v-model="newReward.category" placeholder="如：娱乐" /></label>
        </div>
        <button class="ok wide" @click="addReward">＋新增奖励</button>
      </div>
    </section>

    <!-- 审批 -->
    <section v-if="section === 'approve'" class="a-card enter">
      <h3>兑换审批与兑现</h3>
      <p class="lead">需家长同意的奖励先到「待同意」；同意后扣阳光，实际给了再点「标记已兑现」。</p>
      <div v-if="!redemptions.length" class="dim">还没有任何兑换记录。</div>
      <div class="apv-row" v-for="rd in redemptions" :key="rd.id">
        <div class="apv-info">
          <span class="apv-name">{{ rd.name }}</span>
          <span class="dim">{{ rd.date }} · -{{ rd.price }} <Sun class="ico sun" :size="12" /></span>
        </div>
        <div class="apv-right">
          <template v-if="rd.status === 'pending'">
            <span class="st pending">待同意</span>
            <button class="ok" @click="approveRedeem(rd.id)">同意</button>
            <button class="del" @click="rejectRedeem(rd.id)">拒绝</button>
          </template>
          <template v-else-if="rd.status === 'done'">
            <span class="st done">已扣阳光</span>
            <button class="ok ghost-o" @click="deliverRedeem(rd.id)">标记已兑现</button>
          </template>
          <span v-else class="st delivered">已兑现 <Check class="ico" :size="12" /></span>
        </div>
      </div>
    </section>

    <!-- 等级 -->
    <section v-if="section === 'rank'" class="a-card enter">
      <h3>成长等级（按累计获得阳光）</h3>
      <p class="lead">等级看「累计获得」，消费不会掉级。</p>
      <div class="task-row" v-for="r in ranks" :key="r.id">
        <span class="rank-icon"><component :is="rankIcon(r.icon)" class="ico" :size="18" /></span>
        <label class="fld grow"><span>等级名</span><input v-model="r.name" /></label>
        <label class="fld w84"><span>累计阳光 ≥</span><input v-model.number="r.min_sunshine" type="number" /></label>
        <div class="ops">
          <button class="ok" @click="saveRank(r)">保存</button>
          <button class="del" @click="delRank(r.id)">删</button>
        </div>
      </div>
      <div class="add-box">
        <div class="add-title">新增等级</div>
        <div class="frm-row">
          <span class="rank-icon"><Star class="ico" :size="18" /></span>
          <label class="fld grow"><span>等级名</span><input v-model="newRank.name" placeholder="如：阳光萌新" /></label>
          <label class="fld w84"><span>累计阳光 ≥</span><input v-model.number="newRank.min_sunshine" type="number" placeholder="0" /></label>
        </div>
        <button class="ok wide" @click="addRank">＋新增等级</button>
      </div>
    </section>

    <!-- 任务 -->
    <section v-if="section === 'unit-task'" class="a-card enter">
      <h3>单元任务</h3>
      <p class="lead">按学科折叠；改「标题 / 动作 / 阳光」后点保存。</p>
      <details v-for="(arr, sid) in tasksBySubject" :key="sid" class="subj">
        <summary>{{ subjectName(sid) }}<em>{{ arr.length }} 项</em></summary>
        <div class="task-row" v-for="t in arr" :key="t.id">
          <span class="badge">{{ unitName(t.unit_id) }}</span>
          <label class="fld grow"><span>标题</span><input v-model="t.title" /></label>
          <label class="fld w84"><span>动作</span><input v-model="t.action" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="t.sunshine" type="number" /></label>
          <div class="ops">
            <button class="ok" @click="saveTask(t)">保存</button>
            <button class="del" @click="delTask(t.id)">删</button>
          </div>
        </div>
      </details>
      <div class="add-box">
        <div class="add-title">新增单元任务（针对当前学期）</div>
        <div class="frm-row">
          <label class="fld"><span>科目</span>
            <select v-model="newTask.subject_id" @change="pickSubject">
              <option value="" disabled>选科目</option>
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>单元</span>
            <select v-model="newTask.unit_id">
              <option value="" disabled>选单元</option>
              <option v-for="u in unitOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
          </label>
        </div>
        <div class="frm-row">
          <label class="fld grow"><span>标题</span><input v-model="newTask.title" placeholder="如：背诵第3课" /></label>
          <label class="fld w84"><span>动作</span><input v-model="newTask.action" placeholder="读 / 写 / 背" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="newTask.sunshine" type="number" /></label>
        </div>
        <button class="ok wide" @click="addTask">＋新增任务</button>
      </div>
    </section>

    <!-- 每日任务 -->
    <section v-if="section === 'daily'" class="a-card enter">
      <h3>每日任务（循环打卡）</h3>
      <p class="lead">系统内置任务只读；你自己建的可以改、可加「破纪录」指标。</p>
      <div class="daily-card" v-for="d in daily" :key="d.id">
        <div v-if="d.family_id == null" class="sys-row">
          <span class="badge daily">每天</span>
          <span class="sys-name">{{ d.name }}</span>
          <span class="dim">+{{ d.sunshine }} 阳光 · 系统内置</span>
        </div>
        <template v-else>
          <div class="dc-head">
            <span class="badge daily">每天</span>
            <label class="fld grow"><span>名称</span><input v-model="d.name" /></label>
            <label class="fld w84"><span>科目</span>
              <select v-model="d.subject_id">
                <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </label>
            <label class="fld w64"><span>基础阳光</span><input v-model.number="d.sunshine" type="number" /></label>
            <label class="fld w84"><span>破纪录 +</span><input v-model.number="d.bonus_per_metric" type="number" /></label>
            <div class="ops">
              <button class="ok" @click="saveDaily(d)">保存</button>
              <button class="del" @click="delDaily(d.id)">删</button>
            </div>
          </div>
          <div class="dc-metrics" v-if="d.metrics.length">
            <div class="dc-m-head">破纪录指标</div>
            <div class="m-row" v-for="(m, i) in d.metrics" :key="m.id">
              <label class="fld grow"><span>名称</span><input v-model="m.label" placeholder="如：跳绳个数" /></label>
              <label class="fld w84"><span>单位</span><input v-model="m.unit" placeholder="个" /></label>
              <label class="fld w104"><span>方向</span>
                <select v-model="m.direction">
                  <option v-for="[v, n] in DIRS" :key="v" :value="v">{{ n }}</option>
                </select>
              </label>
              <button class="del" @click="d.metrics.splice(i, 1)">×</button>
            </div>
          </div>
          <button class="ghost-s" @click="addMetric(d.metrics)">＋加破纪录指标</button>
        </template>
      </div>
      <div class="add-box">
        <div class="add-title">新增每日任务（你自己家的）</div>
        <div class="frm-row">
          <label class="fld w84"><span>科目</span>
            <select v-model="newDaily.subject_id">
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>名称</span><input v-model="newDaily.name" placeholder="如：跳绳打卡" /></label>
          <label class="fld w64"><span>基础阳光</span><input v-model.number="newDaily.sunshine" type="number" /></label>
          <label class="fld w84"><span>破纪录 +</span><input v-model.number="newDaily.bonus_per_metric" type="number" /></label>
        </div>
        <div class="m-row" v-for="(m, i) in newDaily.metrics" :key="m.id">
          <label class="fld grow"><span>指标名</span><input v-model="m.label" placeholder="如：跳绳个数" /></label>
          <label class="fld w84"><span>单位</span><input v-model="m.unit" placeholder="个" /></label>
          <label class="fld w104"><span>方向</span>
            <select v-model="m.direction">
              <option v-for="[v, n] in DIRS" :key="v" :value="v">{{ n }}</option>
            </select>
          </label>
          <button class="del" @click="newDaily.metrics.splice(i, 1)">×</button>
        </div>
        <button class="ghost-s" @click="addMetric(newDaily.metrics)">＋加破纪录指标</button>
        <div style="margin-top:10px"><button class="ok wide" @click="addDaily">＋新增任务</button></div>
      </div>
    </section>

    <!-- 已学到 -->
    <section v-if="section === 'cursor'" class="a-card enter">
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
      <p class="lead" style="margin-top:8px">开启后，每科只有正在学的那个单元能打卡，后面的课自动锁住（灰显 <Lock class="ico" :size="12" />），防没学就打卡刷阳光。</p>
    </section>

    <!-- 单元测试成绩 -->
    <section v-if="section === 'test'" class="a-card enter">
      <h3>单元测试成绩奖励</h3>
      <p class="lead">孩子考完单元测试，你录入分数，按档自动发阳光（孩子不能自己录）。</p>
      <div class="band-box">
        <span v-for="[th, sun] in TEST_BANDS" :key="th" class="band">{{ th === 0 ? '85 以下' : th + ' 分' }} · +{{ sun }} 阳光</span>
      </div>
      <div class="add-box">
        <div class="add-title">录入成绩</div>
        <div class="frm-row">
          <label class="fld w104"><span>科目</span>
            <select v-model="newTest.subject_id" @change="newTest.unit_id = ''">
              <option value="" disabled>选科目</option>
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>单元（可选）</span>
            <select v-model="newTest.unit_id">
              <option value="">不选</option>
              <option v-for="u in units.filter(x => x.subject_id === newTest.subject_id)" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
          </label>
          <label class="fld w84"><span>分数</span><input v-model="newTest.score" type="number" placeholder="0~100" /></label>
          <label class="fld w104"><span>备注</span><input v-model="newTest.note" placeholder="如：期中" /></label>
        </div>
        <button class="ok wide" @click="addTest">录成绩并发阳光</button>
      </div>
      <div v-if="!tests.length" class="dim">还没录过测试成绩。</div>
      <div class="test-row" v-for="t in tests" :key="t.id">
        <span class="badge">{{ t.subject_id }}</span>
        <span class="badge daily">{{ t.score }} 分</span>
        <span class="dim">{{ t.note || '—' }} · {{ t.date }}</span>
        <span class="st delivered">+{{ t.sunshine }} <Sun class="ico sun" :size="12" /></span>
        <button class="del" @click="delTest(t.id)">删</button>
      </div>
    </section>

    <section v-if="section === 'kids'" class="a-card enter">
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

    <!-- 家长成员 -->
    <section v-if="section === 'members'" class="a-card enter">
      <h3>家长成员</h3>
      <p class="lead">另一位家长共同管理，爷爷奶奶…当「观察员」只能看。</p>
      <div class="a-item" v-for="m in members" :key="m.id">
        <span class="badge">{{ m.name }}</span>
        <span class="dim">{{ m.account }} · {{ m.role }}</span>
        <button class="del" @click="delMember(m)">删</button>
      </div>
    </section>

    <!-- 邀请码 -->
    <section v-if="section === 'invites'" class="a-card enter">
      <h3>邀请码</h3>
      <label style="display:flex;gap:8px;align-items:center;margin:10px 0 4px;font-size:13px;cursor:pointer">
        <input type="checkbox" :checked="inviteProtect" @change="toggleProtect" />
        <span>邀请码保护（开 = 一次性 + 24h 限时）</span>
      </label>
      <p class="dim" style="margin-top:8px">
        <button class="ok" @click="makeInvite('parent')">家长邀请码</button>
        <button class="ok" @click="makeInvite('observer')">观察员码</button>
      </p>
      <div class="a-item" v-for="iv in invites" :key="iv.code" style="flex-wrap:wrap">
        <span class="badge">{{ iv.role === 'observer' ? '观察员' : '家长' }}</span>
        <code style="font-family:ui-monospace,monospace;font-weight:700;font-size:14px">{{ iv.code }}</code>
        <span class="dim">{{ inviteStatus(iv) }}</span>
        <button class="ok" @click="copyCode(iv.code)">复制</button>
        <button class="del" @click="delInvite(iv.code)">删</button>
      </div>
      <p v-if="!invites.length" class="dim" style="margin-top:6px">还没有邀请码，点上面生成，再点「复制」分享给家人。</p>
    </section>

    <!-- 密码 -->
    <section v-if="section === 'pin'" class="a-card enter">
      <h3>修改家长密码</h3>
      <div class="a-item">
        <input v-model="pinForm.next" type="password" placeholder="新密码（至少 4 位）" class="w-name" />
        <button class="ok" @click="changePin">改密码</button>
      </div>
      <p class="dim">账号 parent；改密后旧设备要重新登录。首登请改掉迁移来的旧密码。</p>
    </section>
      </main>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.admin { max-width: 780px; margin: 0 auto; padding: 14px; padding-top: calc(14px + env(safe-area-inset-top)); font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: var(--ink); }
.a-head {
  background: linear-gradient(180deg, var(--brand) 0%, var(--brand) 100%);
  color: #fff; border-radius: 20px; padding: 16px 20px;
  display: flex; justify-content: space-between; align-items: center;
}
.a-title { font-size: 20px; font-weight: 800; }
.a-sub { font-size: 12px; opacity: .85; margin-top: 4px; }
.a-term { display: block; margin-top: 8px; font-size: 12px; }
.a-term select { margin-left: 6px; padding: 4px 8px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); }
.a-exit { background: rgba(255,255,255,.22); border: none; color: #fff; border-radius: 20px; padding: 9px 16px; font-weight: 700; cursor: pointer; font-family: inherit; }
.a-body { display: flex; gap: 16px; align-items: flex-start; }
.a-side { width: 164px; flex: none; background: var(--surface); border-radius: 16px; padding: 10px 8px; box-shadow: 0 4px 14px rgba(60,120,170,.07); border: 1px solid var(--line); position: sticky; top: calc(8px + env(safe-area-inset-top)); }
.a-group { font-size: 11px; color: var(--ink-3); font-weight: 800; padding: 10px 10px 4px; letter-spacing: .5px; }
.a-nav { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: none; background: none; border-radius: 10px; color: var(--ink-2); font-weight: 700; font-size: 13px; cursor: pointer; text-align: left; font-family: inherit; }
.a-nav:hover { background: var(--surface-2); }
.a-nav.on { background: var(--brand); color: #fff; }
.a-nav-ico { width: 18px; text-align: center; }
.a-main { flex: 1; min-width: 0; }
.a-card { background: var(--surface); border-radius: var(--r-card); padding: 18px; margin-bottom: 14px; box-shadow: var(--sh-card); border: 1px solid var(--line); }
.a-card h3 { margin: 0 0 6px; font-size: 16px; color: var(--ink); }
.lead { color: var(--ink-3); font-size: 12px; margin: 0 0 14px; }
.lock-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink-2); font-weight: 700; }
.toggle { border: none; background: var(--surface-2); color: var(--ink-2); padding: 7px 16px; border-radius: 16px; font-weight: 800; cursor: pointer; font-family: inherit; }
.toggle.on { background: var(--accent); color: #fff; }
.dim { color: var(--ink-3); font-size: 12px; }
.a-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 0; border-bottom: 1px solid var(--surface-2); }
.a-item.add { border-top: 1px dashed var(--line); margin-top: 8px; padding-top: 12px; }
.a-subject-h { font-weight: 800; color: var(--brand-deep); margin-top: 8px; font-size: 14px; }
.a-item input, .a-item select { border: 1px solid var(--line); border-radius: 8px; padding: 7px 9px; font-size: 13px; color: var(--ink); font-family: inherit; }
.a-item input:focus, .a-item select:focus { outline: none; border-color: var(--brand); }
.w-name { flex: 1; min-width: 120px; }
.w-num { width: 70px; }
.w-cat { width: 90px; }
.badge { font-size: 11px; padding: 3px 8px; border-radius: 10px; background: var(--surface-2); color: var(--brand-deep); white-space: nowrap; font-weight: 700; }
.badge.daily { background: var(--warm); color: var(--accent-ink); }
.rank-icon { font-size: 18px; }
.st { font-size: 11px; padding: 3px 9px; border-radius: 10px; font-weight: 700; white-space: nowrap; }
.st.pending { background: var(--warm); color: var(--accent-ink); }
.st.done { background: var(--surface-2); color: var(--brand-deep); }
.st.delivered { background: var(--ok-bg); color: var(--ok); }
.ok { padding: 7px 14px; border: none; border-radius: 16px; background: var(--accent); color: #fff; font-weight: 700; cursor: pointer; font-family: inherit; }
.ok.ghost-o { background: var(--brand); }
.del { padding: 6px 10px; border: none; border-radius: 14px; background: var(--danger-bg); color: var(--danger); cursor: pointer; font-family: inherit; }
.ghost-s { background: none; border: none; color: var(--brand-deep); font-size: 12px; cursor: pointer; font-family: inherit; }
.daily .d-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; width: 100%; padding: 4px 0; }
.toast { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%); background: rgba(31,59,85,.92); color: #fff; padding: 10px 18px; border-radius: 22px; font-size: 14px; z-index: 20; }

.w-kids { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 12px; }
.w-kids .w-box { cursor: pointer; }
.w-kids .w-box.on { outline: 2px solid var(--accent); }
.w-kids .w-box i { display: block; font-style: normal; font-size: 11px; }
.w-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.w-box { background: var(--surface-2); border: 1px solid var(--line); border-radius: 12px; padding: 12px 6px; text-align: center; }
.w-box span { display: block; font-size: 11px; color: var(--ink-3); margin-bottom: 4px; }
.w-box b { font-size: 20px; color: var(--ink); }
.w-h { margin: 20px 0 10px; font-size: 14px; color: var(--ink); }
.w-trend { margin-bottom: 4px; }
.w-trend-svg { width: 100%; height: 90px; }
.w-trend-labels { display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-3); margin-top: 6px; }
.w-trend-labels i { font-style: normal; color: var(--brand-deep); font-weight: 700; margin-left: 3px; }
.w-chart { display: flex; align-items: flex-end; gap: 8px; height: 140px; padding-top: 20px; }
.w-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; height: 100%; justify-content: flex-end; }
.w-bar { width: 100%; max-width: 34px; background: var(--accent); border-radius: 6px 6px 0 0; position: relative; min-height: 2px; }
.w-bar i { position: absolute; top: -20px; left: 0; width: 100%; text-align: center; font-size: 11px; color: var(--accent-ink); font-style: normal; font-weight: 700; }
.w-bar-col span { font-size: 11px; color: var(--ink-2); }
.w-subj-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.w-subj-name { width: 48px; font-weight: 700; color: var(--ink); flex: none; }
.w-subj-track { flex: 1; background: var(--line); border-radius: 6px; height: 12px; overflow: hidden; }
.w-subj-track i { display: block; height: 100%; background: linear-gradient(90deg,var(--brand),var(--brand)); border-radius: 6px; }
.w-subj-num { flex: none; font-size: 12px; color: var(--ink-2); }
.band-box { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; }
.band { font-size: 12px; padding: 4px 10px; border-radius: 12px; background: var(--warm); color: var(--accent-ink); font-weight: 700; }

/* —— 单元任务 / 每日任务 表单重排 —— */
.fld { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.fld > span { font-size: 11px; color: var(--ink-3); font-weight: 700; }
.fld input, .fld select { border: 1px solid var(--line); border-radius: 8px; padding: 6px 9px; font-size: 13px; color: var(--ink); background: var(--surface); font-family: inherit; width: 100%; }
.fld input:focus, .fld select:focus { outline: none; border-color: var(--brand); }
.grow { flex: 1 1 120px; }
.w64 { width: 64px; flex: none; }
.w84 { width: 84px; flex: none; }
.w104 { width: 104px; flex: none; }
.ops { display: flex; gap: 6px; align-items: center; flex: none; }

details.subj { border: 1px solid var(--line); border-radius: 12px; margin-bottom: 8px; background: var(--surface); overflow: hidden; }
details.subj summary { list-style: none; cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 11px 14px; font-weight: 800; color: var(--brand-deep); font-size: 14px; }
details.subj summary::-webkit-details-marker { display: none; }
details.subj summary em { font-style: normal; font-size: 11px; color: var(--ink-3); background: var(--surface-2); padding: 1px 8px; border-radius: 10px; }
details.subj summary::after { content: ''; margin-left: auto; width: 8px; height: 8px; border-right: 2px solid var(--ink-3); border-bottom: 2px solid var(--ink-3); transform: rotate(45deg); transition: transform .18s var(--ease); flex: none; }
details.subj[open] summary::after { transform: rotate(-135deg); }
.task-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 14px; border-top: 1px solid var(--surface-2); }
.task-row .badge { flex: none; }

.daily-card { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; background: var(--surface); }
.dc-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sys-row { display: flex; align-items: center; gap: 10px; }
.sys-name { font-weight: 700; }
.dc-metrics { margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 10px; }
.dc-m-head { font-size: 11px; color: var(--ink-3); font-weight: 800; margin-bottom: 8px; }
.m-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }

.add-box { margin-top: 14px; border: 1px dashed var(--line); border-radius: 12px; padding: 14px; background: var(--surface-2); }
.add-title { font-size: 12px; font-weight: 800; color: var(--ink-2); margin-bottom: 10px; }
.frm-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.ok.wide { width: 100%; }

/* —— 兑换审批 / 单元测试 行 —— */
.apv-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--surface-2); flex-wrap: wrap; }
.apv-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.apv-name { font-weight: 700; }
.apv-right { display: flex; align-items: center; gap: 8px; flex: none; }
.test-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--surface-2); flex-wrap: wrap; }
.test-row .dim { flex: 1; min-width: 0; }

@media (max-width: 760px) {
  .a-body { flex-direction: column; }
  .a-side { width: 100%; position: static; display: flex; gap: 6px; overflow-x: auto; padding: 8px; }
  .a-group { display: none; }
  .a-nav { flex: 0 0 auto; width: auto; white-space: nowrap; }
}
@media (max-width: 560px) {
  .w-summary { grid-template-columns: repeat(2, 1fr); }
}
</style>