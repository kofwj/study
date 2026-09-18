<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api, setSelectedKid } from './api.js'
import { APP_LABEL, APP_REVISION } from './version.js'
import { initAdminWords, loadWords } from './adminWords.js'
import AdminWords from './components/AdminWords.vue'
import AdminInsights from './components/AdminInsights.vue'
import AdminTasks from './components/AdminTasks.vue'
import AdminApprove from './components/AdminApprove.vue'
import AdminReview from './components/AdminReview.vue'
import AdminShop from './components/AdminShop.vue'
import AdminKids from './components/AdminKids.vue'
import AdminQuiz from './components/AdminQuiz.vue'
import AdminCursor from './components/AdminCursor.vue'
import { initAdminEdit, useAdminEdit } from './adminEdit.js'
import PageBoundary from './components/PageBoundary.vue'
import { Eye, Baby, Store, ClipboardCheck, BookOpen, MapPinned, ArrowLeft, BookMarked, Globe, Trophy } from '@lucide/vue'

const props = defineProps({ recoveryCode: { type: String, default: '' } })
const emit = defineEmits(['exit', 'switched', 'consumed-recovery'])
const me = ref({ role: 'parent', parent_role: 'member' })  // 当前家长信息
const kids = ref([])
const members = ref([])
const inviteProtect = ref(false)
const penaltyEnabled = ref(false)
// 打卡时间窗 + 储蓄所营业时间（两家事、各有开关；后端 /api/admin/family 一起下发）
const familyHours = reactive({
  checkin: { enabled: true, open_hour: 7, close_hour: 21, from: '07:00', until: '21:00' },
  bank: { enabled: true, open_hour: 8, close_hour: 20, from: '08:00', until: '20:00' },
})
const penalties = ref([])
const penaltySummary = ref({ net: 0, count: 0, amount: 0, by_reason: [] })
const invites = ref([])
const selectedKid = ref('')
const setupKid = reactive({ name: '', account: '', pin: '', pin2: '', term_id: 'g5s1', gender: '' })
const setupBusy = ref(false)
const shownRecovery = ref('')
const section = ref('insights')
const needsSetup = computed(() => !kids.value.length)

// 计算是否为创建者
const isOwner = computed(() => me.value.parent_role === 'owner')

const SECTIONS = [
  { group: '今日', items: [
    { id: 'insights', icon: Eye, label: '总览' },
    { id: 'review', icon: BookMarked, label: '今日复习' },
    { id: 'approve', icon: ClipboardCheck, label: '兑换审批' },
  ] },
  { group: '学习', items: [
    { id: 'unit-task', icon: BookOpen, label: '任务' },
    { id: 'quiz', icon: Trophy, label: '大队委' },
    { id: 'words', icon: Globe, label: '英语单词' },
    { id: 'cursor', icon: MapPinned, label: '已学到' },
  ] },
  { group: '阳光', items: [
    { id: 'shop', icon: Store, label: '阳光' },
  ] },
  { group: '家庭', items: [
    { id: 'kids', icon: Baby, label: '家庭' },
  ] },
]
const SECTION_IDS = new Set(SECTIONS.flatMap(g => g.items.map(it => it.id)))
const SECTION_KEY = 'adminSection'
function persistSection(id) {
  try { localStorage.setItem(SECTION_KEY, id) } catch {}
}
function rememberedSection() {
  try {
    const saved = localStorage.getItem(SECTION_KEY)
    const mapped = { weekly: 'insights', sprites: 'cursor', daily: 'unit-task', test: 'unit-task', bank: 'shop', rank: 'shop', penalty: 'shop', members: 'kids', invites: 'kids', pin: 'kids' }[saved]
    const id = mapped || saved
    if (id && SECTION_IDS.has(id)) {
      if (id !== saved) persistSection(id)
      return id
    }
    if (saved) persistSection('insights')
  } catch {}
  return 'insights'
}
section.value = rememberedSection()
watch(section, (id) => {
  if (SECTION_IDS.has(id)) persistSection(id)
  if (!selectedKid.value || selectedKid.value !== loadedKid) return
  ensureSection(id).catch((e) => showToast(e && e.message ? `加载失败：${e.message}` : '加载失败，请检查网络后重试'))
})

const rewards = ref([])
const ranks = ref([])
const subjects = ref([])
const units = ref([])
const tasks = ref([])
const daily = ref([])
const dailyAll = ref([])   // 全家每日任务（含只给别的孩子看的），只给管理列表用
const fitnessGoals = ref({})
const dailyHist = ref({})
const terms = ref([])
const activeTerm = ref('g5s1')
const cursors = ref({})
const progressLock = ref(true)
const hiddenSubjects = ref([])
const weeklyGoal = ref(50)
const weeklyGoalBusy = ref(false)

const bankData = ref({ enabled: false, balance: 0, pocket_balance: 0, goal: null, requests: [], ledger: [] })
const bankRequests = ref([])
const bankGoal = reactive({ name: '', target: 100 })
const bankInterest = reactive({ enabled: false, cycle: 'weekly', rate: 5.0, threshold: 20, last_settle: '' })
const bankBusy = ref(false)
const redemptions = ref([])
const tests = ref([])
const catalog = ref({ tags: [], unit_tags: [] })
const weakByUnit = ref({})
const weakPoints = ref([])
const reviewDue = ref([])
const firstReview = ref('')
const DEFAULT_TEST_BANDS = [[100, 30], [95, 20], [90, 15], [85, 10], [0, 5]]
const testBands = ref(DEFAULT_TEST_BANDS.map(x => [...x]))
const weeklyGoalSnap = ref(null)
const testBandsSnap = ref(null)
const bankGoalSnap = ref(null)
function snapWeeklyGoal() { weeklyGoalSnap.value = weeklyGoal.value }
function snapTestBands() { testBandsSnap.value = (testBands.value || []).map(x => [...x]) }
function snapBankGoal() { bankGoalSnap.value = { name: bankGoal.name, target: bankGoal.target } }
const weekly = ref({ days: [], weeks: [], by_subject: [], kids: [], total_earned: 0, total_spent: 0, net: 0, balance: 0, earned_all: 0, streak: 0, checkins: 0, week_start: '', week_end: '', insight: null, family_insight: null, mastered_by_kid: [], penalty_net: 0, penalty_count: 0 })
const insights = ref({ rules: { test_fail_count: 2, test_fail_score: 80, drop_ratio: 0.3, streak_break: 2 }, kids: [] })
const familyToday = ref({ today: '', kids: [] })
const tasksRef = ref(null)  // 任务页子组件：脏条要调它的 isAddDirty/discardAdd/saveCurrentEdit
const shopRef = ref(null)  // 阳光页子组件：脏条要调它的 isAddDirty/discardAdd/saveCurrentEdit
const kidsRef = ref(null)  // 家庭页子组件：脏条要调它的 isAddDirty/discardAdd/saveCurrentEdit
// 编辑会话在 adminEdit.js（模块级单例）：商店、等级、家长任务、每日任务、孩子共用同一套
initAdminEdit({
  getLists: () => ({ rewards: rewards.value, ranks: ranks.value, dailyAll: dailyAll.value, daily: daily.value, tasks: tasks.value, kids: kids.value }),
})
const {
  editKind, editId, findEditRow, clearEdit,
  beginEdit, cancelEdit, isEditing, isEditDirty,
} = useAdminEdit()




const RULE_DEFAULTS = { test_fail_count: 2, test_fail_score: 80, drop_ratio: 0.3, streak_break: 2 }
const toast = ref('')

const weekNet = (w) => Number(w && (w.net != null ? w.net : w.earned)) || 0
const maxWeek = computed(() => {
  const vals = (weekly.value.weeks || []).map(weekNet)
  return Math.max(1, ...vals.map(Math.abs), 0)
})

let toastTimer = null
function showToast(m) {
  toast.value = m
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2200)
}

// 单词页的数据与请求在 adminWords.js（模块级单例）：包调度和单词视图共用同一份
initAdminWords({
  getKid: () => selectedKid.value,
  getTerms: () => terms.value,
  toast: showToast,
})

function unitName(id) { return units.value.find(u => u.id === id)?.name || id }

const loaded = new Set()
const inflight = new Map()
const packError = ref('')   // 按页加载里某个包失败时给家长一条能读的提示（别让页面静默空白）
const KID_PACKS = new Set(['tasks', 'hist', 'weekly', 'insights', 'familyToday', 'redemptions', 'reviewDue', 'weak', 'tests', 'words', 'bank', 'sprites', 'penalties'])
const SECTION_PACKS = {
  insights: ['tasks', 'hist', 'weekly', 'insights', 'familyToday', 'redemptions', 'reviewDue'],
  review: ['tasks', 'reviewDue', 'weak'],
  approve: ['redemptions'],
  'unit-task': ['tasks', 'catalog', 'weak', 'tests', 'insights'],
  words: ['tasks', 'words'],
  cursor: ['tasks', 'sprites'],
  shop: ['rewards', 'bank', 'ranks', 'penalties'],
  kids: ['tasks'],
}
let loadedKid = ''
let loadGen = 0

function dropKidPacks() {
  loadGen += 1
  inflight.clear()
  for (const name of [...loaded]) {
    if (KID_PACKS.has(name)) loaded.delete(name)
  }
}
function invalidateSection(id) {
  loadGen += 1
  for (const name of SECTION_PACKS[id] || []) {
    loaded.delete(name)
    inflight.delete(name)
  }
}
function staleKid(kid) {
  return !!kid && selectedKid.value !== kid
}
function staleNow(kid, gen) {
  return gen !== loadGen || staleKid(kid)
}

async function loadPack(name, fn) {
  if (loaded.has(name)) return
  if (inflight.has(name)) return inflight.get(name)
  const gen = loadGen
  const kid = selectedKid.value
  const p = (async () => {
    try {
      await fn()
      if (staleNow(kid, gen)) return
      loaded.add(name)
      packError.value = ''
    } catch (e) {
      // 一个包失败不该把整页拖空、也不该把 Promise 抛出去：留在条上给家长看
      packError.value = `${name}：${(e && e.message) || e}`
    }
  })().finally(() => { if (inflight.get(name) === p) inflight.delete(name) })
  inflight.set(name, p)
  return p
}

async function retryPacks() {
  packError.value = ''
  loaded.clear()
  try {
    await ensureSection(section.value)
  } catch (e) {
    packError.value = (e && e.message) || String(e)
  }
}

function applyTasks(t) {
  subjects.value = t.subjects
  units.value = t.units
  tasks.value = (t.tasks || []).map(x => ({ ...x, kid_id: x.kid_id || '' }))
  daily.value = t.daily
  dailyAll.value = t.daily_all || t.daily
  fitnessGoals.value = t.fitness_goals || {}
  terms.value = t.terms || []
  activeTerm.value = t.active_term || 'g5s1'
  cursors.value = t.cursors || {}
  progressLock.value = t.progress_lock === '1'
  hiddenSubjects.value = t.hidden_subjects || []
}
function applyWeak(wps) {
  const openWeakPoints = wps || []
  const wb = {}
  for (const x of openWeakPoints) {
    if (!wb[x.unit_id]) wb[x.unit_id] = {}
    wb[x.unit_id][x.tag_id] = true
  }
  weakPoints.value = openWeakPoints
  weakByUnit.value = wb
}
function applyPenalties(pn) {
  if (pn && !Array.isArray(pn) && Array.isArray(pn.items)) {
    penalties.value = pn.items
    penaltySummary.value = pn.summary || { net: 0, count: 0, amount: 0, by_reason: [] }
  } else {
    penalties.value = Array.isArray(pn) ? pn : []
    penaltySummary.value = { net: 0, count: 0, amount: 0, by_reason: [] }
  }
}
function applyInsights(ig) {
  insights.value = ig
  testBands.value = (ig.rules?.test_bands || DEFAULT_TEST_BANDS).map(x => [...x])
  snapTestBands()
}

async function loadTasks() {
  const kid = selectedKid.value
  const t = await api.tasks()
  if (staleKid(kid)) return
  applyTasks(t)
}
async function loadHist() {
  const kid = selectedKid.value
  const withM = (daily.value || []).filter(d => (d.metrics || []).length)
  const histPairs = await Promise.all(withM.map(async d => {
    try { return [d.id, await api.dailyHistory(d.id)] }
    catch { return [d.id, []] }
  }))
  if (staleKid(kid)) return
  dailyHist.value = Object.fromEntries(histPairs)
}
async function loadWeeklyPack() {
  const kid = selectedKid.value
  const [wk, sun] = await Promise.all([api.admin.weekly(), api.ledgerSummary(0).catch(() => null)])
  if (staleKid(kid)) return
  weekly.value = wk
  weeklyGoal.value = sun && sun.weekly_goal != null ? sun.weekly_goal : 50
  snapWeeklyGoal()
}
async function loadInsightsPack() {
  const kid = selectedKid.value
  const ig = await api.admin.insights()
  if (staleKid(kid)) return
  applyInsights(ig)
}
async function loadFamilyToday() {
  const kid = selectedKid.value
  const ft = await api.admin.familyToday() || { today: '', kids: [] }
  if (staleKid(kid)) return
  familyToday.value = ft
}

// —— B4 家庭共同目标：动作放壳里（子组件只 emit；改完重拉 family-today 拿新进度）——
async function saveFamilyGoal(o) {
  await withBusy(async () => {
    try {
      await api.admin.setFamilyGoal(o)
      await loadFamilyToday()
      showToast('共同目标已设好')
    } catch (e) { showToast(e.message) }
  })
}
async function closeFamilyGoal() {
  if (!confirm('关掉当前共同目标？不扣分，也不会补发。')) return
  await withBusy(async () => {
    try {
      await api.admin.closeFamilyGoal()
      await loadFamilyToday()
      showToast('已关掉共同目标')
    } catch (e) { showToast(e.message) }
  })
}
async function loadRedemptions() {
  const kid = selectedKid.value
  const rd = await api.admin.redemptions()
  if (staleKid(kid)) return
  redemptions.value = rd
}
async function loadReviewDue() {
  const kid = selectedKid.value
  const rv = await api.admin.reviewDue() || []
  if (staleKid(kid)) return
  reviewDue.value = rv
}
async function loadWeak() {
  const kid = selectedKid.value
  const wps = await api.admin.weakPoints('')
  if (staleKid(kid)) return
  applyWeak(wps)
}
async function loadCatalog() {
  const cat = await api.admin.unitTags()
  catalog.value = cat && cat.tags ? cat : { tags: [], unit_tags: [] }
}
async function loadTests() {
  const kid = selectedKid.value
  const ts = await api.admin.tests()
  if (staleKid(kid)) return
  tests.value = ts
}
async function loadRewards() { rewards.value = await api.rewards() }
async function loadRanks() { ranks.value = await api.admin.ranks() }
async function loadPenalties() {
  const kid = selectedKid.value
  const pn = await api.admin.penalties().catch(() => ({ items: [], summary: null }))
  if (staleKid(kid)) return
  applyPenalties(pn)
}

const PACK_LOADERS = {
  tasks: loadTasks,
  hist: loadHist,
  weekly: loadWeeklyPack,
  insights: loadInsightsPack,
  familyToday: loadFamilyToday,
  redemptions: loadRedemptions,
  reviewDue: loadReviewDue,
  weak: loadWeak,
  catalog: loadCatalog,
  tests: loadTests,
  rewards: loadRewards,
  ranks: loadRanks,
  penalties: loadPenalties,
  words: () => loadWords(),
  bank: () => loadBank(),
  sprites: () => loadSpritesCfg(),
}

async function ensureSection(id) {
  if (!selectedKid.value) return
  const packs = SECTION_PACKS[id] || []
  if (packs.includes('tasks')) await loadPack('tasks', loadTasks)
  await Promise.all(packs.filter(name => name !== 'tasks').map(name => loadPack(name, PACK_LOADERS[name])))
}

async function loadCore() {
  const userInfo = await api.me()
  me.value = userInfo
  const [ks, ms, fam, inv] = await Promise.all([api.admin.kids(), api.admin.members(), api.admin.family(), api.admin.invites()])
  kids.value = ks
  members.value = ms
  inviteProtect.value = !!fam.invite_protect
  penaltyEnabled.value = !!fam.penalty_enabled
  if (fam.checkin_hours) Object.assign(familyHours.checkin, fam.checkin_hours)
  if (fam.bank_hours) Object.assign(familyHours.bank, fam.bank_hours)
  invites.value = inv
  if (!ks.length) {
    terms.value = [{ id: 'g5s1', label: '五年级上册' }]
    loadedKid = ''
    return false
  }
  if (!selectedKid.value || !ks.some(k => k.id === selectedKid.value)) {
    selectedKid.value = ks[0].id
    setSelectedKid(ks[0].id)
  }
  if (selectedKid.value !== loadedKid) {
    dropKidPacks()
    loadedKid = selectedKid.value
  }
  return true
}

async function load() {
  try {
    const ok = await loadCore()
    if (!ok) return
    clearEdit()
    invalidateSection(section.value)
    await ensureSection(section.value)
  } catch (e) {
    showToast(e && e.message ? `加载失败：${e.message}` : '加载失败，请检查网络后重试')
  }
}



async function loadBank() {
  const kid = selectedKid.value
  if (!kid) return
  try {
    const [b, rs, ic] = await Promise.all([api.admin.bank(), api.admin.bankRequests(), api.admin.bankInterestConfig()])
    if (staleKid(kid)) return
    bankData.value = b || bankData.value
    bankRequests.value = rs || []
    if (ic) Object.assign(bankInterest, ic)
    if (bankData.value.goal) Object.assign(bankGoal, { name: bankData.value.goal.name, target: bankData.value.goal.target })
    else Object.assign(bankGoal, { name: '', target: 100 })
    snapBankGoal()
  } catch (e) { showToast(e.message) }
}
async function saveBankGoal() {
  if (!bankGoal.name.trim()) return showToast('填目标名称')
  bankBusy.value = true
  try { bankData.value = await api.admin.saveBankGoal({ name: bankGoal.name, target: bankGoal.target }); snapBankGoal(); showToast('目标已保存') }
  catch (e) { showToast(e.message) }
  finally { bankBusy.value = false }
}
const spriteCfg = reactive({ enabled: true, base_enabled: true })

async function loadSpritesCfg() {
  const kid = selectedKid.value
  if (!kid) return
  try {
    const cfg = await api.admin.spritesConfig()
    if (staleKid(kid)) return
    spriteCfg.enabled = !!cfg.enabled
    spriteCfg.base_enabled = !!cfg.base_enabled
  } catch (e) { showToast(e.message) }
}
async function saveSpritesCfg(patch) {
  const kid = selectedKid.value
  try {
    const cfg = await api.admin.setSpritesConfig(patch)
    if (staleKid(kid)) return
    spriteCfg.enabled = !!cfg.enabled
    spriteCfg.base_enabled = !!cfg.base_enabled
    showToast('已保存')
  } catch (e) { showToast(e.message); if (!staleKid(kid)) await loadSpritesCfg() }
}

// 保存类操作统一包装：防重复提交 + 失败提示（避免 unhandled rejection）
let saveBusy = false
async function withBusy(fn) {
  if (saveBusy) return
  saveBusy = true
  try { await fn() } catch (e) { showToast(e && e.message ? e.message : '操作失败，请重试') }
  finally { saveBusy = false }
}

// —— 商店 ——

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
// —— 等级 ——

// —— 单元任务 ——

const tasksBySubject = computed(() => {
  const m = {}
  for (const t of tasks.value) {
    if (!m[t.subject_id]) m[t.subject_id] = []
    m[t.subject_id].push(t)
  }
  return m
})
const subjectName = (id) => subjects.value.find(s => s.id === id)?.name || id
const termUnits = computed(() => units.value.filter(u => u.term_id === activeTerm.value || (u.id || '').startsWith(activeTerm.value)))
function subjectShown(id) {
  return !(hiddenSubjects.value || []).includes(id)
}
const unitsBySubject = computed(() => {
  const m = {}
  for (const u of termUnits.value) {
    if (!m[u.subject_id]) m[u.subject_id] = []
    m[u.subject_id].push(u)
  }
  return m
})
const tagFor = (id) => (catalog.value.tags || []).find(t => t.id === id) || { id, name: id }
const tagName = (id) => tagFor(id).name
async function toggleTag(uid, tid) {
  const kid = selectedKid.value
  const prev = { ...(weakByUnit.value[uid] || {}) }
  const cur = { ...prev }
  if (cur[tid]) delete cur[tid]
  else cur[tid] = true
  weakByUnit.value = { ...weakByUnit.value, [uid]: cur }
  try {
    const rows = await api.admin.setWeakPoints({ unit_id: uid, tag_ids: Object.keys(cur), kid_id: kid, first_review: firstReview.value })
    if (staleKid(kid)) return
    const other = weakPoints.value.filter(x => x.unit_id !== uid)
    weakPoints.value = [...other, ...rows]
    reviewDue.value = await api.admin.reviewDue()
    if (staleKid(kid)) return
    showToast(cur[tid] ? '已加入今天复习' : '已取消记录')
  } catch (e) {
    if (!staleKid(kid)) weakByUnit.value = { ...weakByUnit.value, [uid]: prev }
    showToast(e.message)
  }
}

// —— 每日任务 ——
const kidName = (id) => kids.value.find(k => k.id === id)?.name || '某个孩子'
// 管理列表看全家的任务；系统内置排最后，其余按「全家 → 各孩子」分组

function sameJson(a, b) { return JSON.stringify(a) === JSON.stringify(b) }
function isWeeklyDirty() {
  if (weeklyGoalSnap.value == null) return false
  return Number(weeklyGoal.value) !== Number(weeklyGoalSnap.value)
}
function isBandsDirty() {
  if (testBandsSnap.value == null) return false
  return !sameJson(testBands.value, testBandsSnap.value)
}
function isBankDirty() {
  if (bankGoalSnap.value == null) return false
  return (bankGoal.name || '') !== (bankGoalSnap.value.name || '') || Number(bankGoal.target) !== Number(bankGoalSnap.value.target)
}
const isDirty = computed(() => isEditDirty() || !!kidsRef.value?.isAddDirty?.() || !!shopRef.value?.isAddDirty?.() || !!tasksRef.value?.isAddDirty?.() || isWeeklyDirty() || isBandsDirty() || isBankDirty())
function discardDirty() {
  cancelEdit()
  if (weeklyGoalSnap.value != null) weeklyGoal.value = weeklyGoalSnap.value
  if (testBandsSnap.value != null) testBands.value = testBandsSnap.value.map(x => [...x])
  if (bankGoalSnap.value != null) Object.assign(bankGoal, { name: bankGoalSnap.value.name, target: bankGoalSnap.value.target })
  shopRef.value?.discardAdd?.()
  kidsRef.value?.discardAdd?.()
  tasksRef.value?.discardAdd?.()
}
async function saveDirty() {
  if (kidsRef.value?.isAddDirty?.() || tasksRef.value?.isAddDirty?.() || shopRef.value?.isAddDirty?.()) {
    showToast('新增还没提交，点新增或放弃')
    return
  }
  if (isEditDirty()) {
    const row = findEditRow(editKind.value, editId.value)
    if (!row) return
    const kind = editKind.value
    if (kind === 'reward' || kind === 'rank') await shopRef.value?.saveCurrentEdit?.()
    else if (kind === 'daily' || kind === 'task') await tasksRef.value?.saveCurrentEdit?.()
    else if (kind === 'kid') await kidsRef.value?.saveCurrentEdit?.()
    if (isEditDirty()) return
  }
  if (isWeeklyDirty()) {
    await saveWeeklyGoal()
    if (isWeeklyDirty()) return
  }
  if (isBandsDirty()) {
    await saveTestBands()
    if (isBandsDirty()) return
  }
  if (isBankDirty()) await saveBankGoal()
}
function confirmLeave() {
  if (!isDirty.value) return true
  if (!confirm('有未保存的修改，要离开吗？离开会丢掉这些修改。')) return false
  discardDirty()
  return true
}
function goSection(id) {
  if (!id || id === section.value) return
  if (!confirmLeave()) return
  section.value = id
}
function exitAdminView() {
  if (!confirmLeave()) return
  emit('exit')
}

// —— 密码 / 游标 ——
async function setCursor(subj, taskId) {
  const kid = selectedKid.value
  try {
    await api.admin.setCursor({ subject_id: subj, task_id: taskId })
    if (staleKid(kid)) return
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
  if (id === selectedKid.value) return
  if (!confirmLeave()) return
  selectedKid.value = id
  await switchKid()
}

function onKidRemoved(id) {
  if (selectedKid.value === id) { selectedKid.value = ''; setSelectedKid('') }
}

async function finishSetup() {
  if (!setupKid.name) return showToast('填孩子在家里怎么叫')
  if (!(setupKid.account || '').trim()) return showToast('填孩子登录账号')
  if ((setupKid.pin || '').trim().length < 6) return showToast('孩子密码至少 6 位')
  if (setupKid.pin !== setupKid.pin2) return showToast('两次密码不一致')
  if (setupBusy.value) return
  setupBusy.value = true
  try {
    await api.admin.createKid({ name: setupKid.name, account: setupKid.account, pin: setupKid.pin, term_id: setupKid.term_id || 'g5s1', gender: setupKid.gender })
    if (props.recoveryCode) shownRecovery.value = props.recoveryCode
    showToast('孩子账号已建好')
    await load()
  } catch (e) { showToast(e.message) }
  finally { setupBusy.value = false }
}
function dismissRecovery() {
  shownRecovery.value = ''
  emit('consumed-recovery')
}


async function saveRule(key, val) {
  try {
    insights.value.rules = await api.admin.setInsightRules({ [key]: val })
    showToast('已保存')
    await load()
  } catch (e) { showToast(e.message) }
}
async function resetRule(key) {
  await saveRule(key, RULE_DEFAULTS[key])
}
async function saveTestBands() {
  try {
    insights.value.rules = await api.admin.setInsightRules({ test_bands: testBands.value })
    testBands.value = (insights.value.rules?.test_bands || DEFAULT_TEST_BANDS).map(x => [...x])
    snapTestBands()
    showToast('奖励标准已保存')
  } catch (e) { showToast(e.message) }
}
async function resetTestBands() {
  testBands.value = DEFAULT_TEST_BANDS.map(x => [...x])
  await saveTestBands()
}
const familyTodayEmpty = computed(() => {
  const ks = familyToday.value.kids || []
  if (!ks.length) return ''
  if (ks.some(k => k.review_due > 0 || !k.checkin)) return ''
  return ks.length === 1 ? '今天来了，没有到期复习。' : '今天都来了，没有到期复习。'
})
function goReviewKid(k) {
  if (k.kid_id === selectedKid.value && section.value === 'review') return
  if (!confirmLeave()) return
  if (k.kid_id !== selectedKid.value) {
    selectedKid.value = k.kid_id
    setSelectedKid(k.kid_id)
    section.value = 'review'
    load()
    return
  }
  section.value = 'review'
}
const currentKidName = computed(() => kids.value.find(k => k.id === selectedKid.value)?.name || '')
const pendingRedeem = computed(() => (redemptions.value || []).filter(r => r.status === 'pending').length)
const reviewCount = computed(() => (reviewDue.value || []).length)
const isMultiKid = computed(() => kids.value.length > 1)
// 家长抽查：孩子自己点了打卡但没做，家长一键撤销、阳光扣回（走 /api/cancel，与孩子端「点绿勾」同一个动作）
async function undoDaily(d) {
  if (!confirm(`撤销「${d.name}」今天的打卡？\n${currentKidName.value || '这个孩子'}的阳光会扣回。`)) return
  await withBusy(async () => {
    try {
      await api.cancel(d.id)
      showToast('已撤销，阳光已扣回')
      await load()
    } catch (e) { showToast(e.message) }
  })
}
function goInsight(row) {
  const a = row.insight?.action
  const nextSection = a === '单元测试' ? 'unit-task' : a === '今日复习' ? 'review' : ''
  const leavingApp = a === '每日打卡' || a === '运动打卡'
  const kidChange = !!(row.kid_id && row.kid_id !== selectedKid.value)
  if ((nextSection && nextSection !== section.value) || leavingApp || kidChange) {
    if (!confirmLeave()) return
  }
  if (row.kid_id) {
    selectedKid.value = row.kid_id
    setSelectedKid(row.kid_id)
  }
  if (a === '单元测试') section.value = 'unit-task'
  else if (a === '每日打卡' || a === '运动打卡') emit('exit')
  else if (a === '今日复习') section.value = 'review'
  if (row.kid_id) load()
}
async function judge(id, action) {
  try {
    await api.admin.judgeWeak(id, action)
    showToast(action === 'done' ? '已巩固，结束' : action === 'pass' ? '过关，间隔拉长' : '还在错，间隔缩短')
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

async function saveWeeklyGoal() {
  const n = Math.max(0, Math.min(10000, Math.round(Number(weeklyGoal.value) || 0)))
  weeklyGoalBusy.value = true
  try {
    const r = await api.setWeeklyGoal(n)
    weeklyGoal.value = r.weekly_goal
    snapWeeklyGoal()
    showToast(n ? `本周目标设为 ${n}` : '已关掉本周目标')
  } catch (e) { showToast(e.message) }
  finally { weeklyGoalBusy.value = false }
}


async function toggleSubjectVisible(id) {
  const on = !subjectShown(id)
  try {
    const r = await api.admin.setSubjectVisible(id, on)
    hiddenSubjects.value = r.hidden_subjects || []
    showToast(on ? `孩子端显示${subjectName(id)}` : `孩子端已隐藏${subjectName(id)}`)
  } catch (e) { showToast(e.message) }
}

async function refreshInvites() {
  try { invites.value = await api.admin.invites() } catch (e) { showToast(e.message) }
}
async function toggleProtect() {
  if (!isOwner.value) return showToast('只有创建者能开关')
  try {
    const next = !inviteProtect.value
    await api.admin.setInviteProtect(next)
    inviteProtect.value = next
    showToast(next ? '邀请码保护已开（一次性 + 24h）' : '邀请码保护已关（常驻复用）')
  } catch (err) { showToast(err.message) }
}
async function togglePenalty() {
  if (!isOwner.value) return showToast('只有创建者能开关')
  try {
    const r = await api.admin.setPenalty(!penaltyEnabled.value)
    penaltyEnabled.value = !!r.penalty_enabled
    showToast(penaltyEnabled.value ? '已开启记下扣分' : '已关闭记下扣分')
  } catch (e) { showToast(e.message) }
}

function onBeforeUnload(e) {
  if (!isDirty.value) return
  e.preventDefault()
  e.returnValue = ''
}
onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
  load()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))
</script>

<template>
  <div v-if="needsSetup && !shownRecovery" class="admin setup">
    <div class="a-card enter setup-card">
      <h3>第一个孩子</h3>
      <label class="fld"><span>家里怎么叫</span><input v-model="setupKid.name" placeholder="如：乐乐" /></label>
      <label class="fld"><span>登录账号</span><input v-model="setupKid.account" placeholder="如：lele" autocomplete="username" /></label>
      <label class="fld"><span>孩子密码</span><input v-model="setupKid.pin" type="password" autocomplete="new-password" placeholder="至少 6 位，不要重复或连续数字" /></label>
      <label class="fld"><span>再输一遍密码</span><input v-model="setupKid.pin2" type="password" autocomplete="new-password" @keyup.enter="finishSetup" /></label>
      <label class="fld"><span>现在读哪册</span>
        <select v-model="setupKid.term_id">
          <option v-for="tm in (terms.length ? terms : [{ id: 'g5s1', label: '五年级上册' }])" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
        </select>
      </label>
      <label class="fld"><span>性别</span>
        <select v-model="setupKid.gender">
          <option value="">还没填</option>
          <option value="男">男</option>
          <option value="女">女</option>
        </select>
      </label>
      <button class="ok wide lg" :disabled="setupBusy" @click="finishSetup">{{ setupBusy ? '正在创建…' : '创建并进入' }}</button>
      <p v-if="toast" class="dim">{{ toast }}</p>
    </div>
  </div>
  <div v-else-if="shownRecovery" class="admin setup">
    <div class="a-card enter setup-card">
      <h3>找回码</h3>
      <p class="recovery-code">{{ shownRecovery }}</p>
      <button class="ok wide lg" @click="dismissRecovery">我已抄好，进入工作台</button>
    </div>
  </div>
  <div v-else class="admin">
    <header class="a-head">
      <div>
        <div class="a-title">家长工作台</div>
        <div class="a-sub" :title="APP_REVISION">{{ APP_LABEL }}</div>
      </div>
      <div class="a-head-right">
        <div v-if="isMultiKid" class="kid-switch">
          <button v-for="k in kids" :key="k.id" type="button" :class="{ on: selectedKid === k.id }" @click="pickKid(k.id)">{{ k.name }}</button>
        </div>
        <div v-else-if="currentKidName" class="kid-one">{{ currentKidName }}</div>
        <button class="a-exit" @click="exitAdminView"><ArrowLeft class="ico" :size="14" /> 回到孩子端</button>
      </div>
    </header>

    <div class="a-body">
      <aside class="a-side">
        <template v-for="g in SECTIONS" :key="g.group">
          <div class="a-group">{{ g.group }}</div>
          <button v-for="it in g.items" :key="it.id" :class="['a-nav', { on: section === it.id }]" @click="goSection(it.id)">
            <span class="a-nav-ico"><component :is="it.icon" :size="16" /></span>{{ it.label }}
          </button>
        </template>
      </aside>
      <main class="a-main">

    <!-- 今日复习 -->
      <PageBoundary>
    <AdminReview
      v-if="section === 'review'"
      :review-due="reviewDue"
      :weak-points="weakPoints"
      :kid="selectedKid"
      :subject-name="subjectName"
      @judge="judge"
      @go-section="goSection"
    />

    <!-- 概览：全家今日 + 本周盯点 -->
    <AdminInsights
      v-if="section === 'insights'"
      :weekly="weekly"
      :family-today="familyToday"
      :insight-kids="insights.kids"
      :daily="daily"
      :daily-hist="dailyHist"
      :fitness-goals="fitnessGoals"
      :review-count="reviewCount"
      :pending-redeem="pendingRedeem"
      :is-multi-kid="isMultiKid"
      :selected-kid="selectedKid"
      :kid-name="currentKidName"
      :parent-name="me.name || ''"
      :weekly-goal="weeklyGoal"
      :weekly-goal-busy="weeklyGoalBusy"
      :subject-name="subjectName"
      @update:weekly-goal="weeklyGoal = $event"
      @save-weekly-goal="saveWeeklyGoal"
      @go-section="goSection"
      @pick-kid="pickKid"
      @save-family-goal="saveFamilyGoal"
      @close-family-goal="closeFamilyGoal"
      @go-review-kid="goReviewKid"
      @go-insight="goInsight"
      @undo-daily="undoDaily"
    />

    <!-- 阳光（商店 / 银行 / 等级 / 扣分）-->
    <AdminShop
      v-if="section === 'shop'"
      ref="shopRef"
      :rewards="rewards"
      :ranks="ranks"
      :penalties="penalties"
      :penalty-summary="penaltySummary"
      :penalty-enabled="penaltyEnabled"
      :bank-data="bankData"
      :bank-requests="bankRequests"
      :bank-goal="bankGoal"
      :bank-interest="bankInterest"
      :bank-busy="bankBusy"
      :is-owner="isOwner"
      :kid-name="currentKidName"
      :show-toast="showToast"
      :with-busy="withBusy"
      @reload="load"
      @reload-bank="loadBank"
      @save-bank-goal="saveBankGoal"
      @toggle-penalty="togglePenalty"
    />

    <!-- 审批 -->
    <AdminApprove
      v-if="section === 'approve'"
      :redemptions="redemptions"
      @approve="approveRedeem"
      @reject="rejectRedeem"
      @deliver="deliverRedeem"
    />

    <!-- 任务 -->
    <AdminTasks
      v-if="section === 'unit-task'"
      ref="tasksRef"
      :tasks-by-subject="tasksBySubject"
      :daily-all="dailyAll"
      :kids="kids"
      :subjects="subjects"
      :units="units"
      :active-term="activeTerm"
      :units-by-subject="unitsBySubject"
      :catalog="catalog"
      :weak-by-unit="weakByUnit"
      :tests="tests"
      :test-bands="testBands"
      :insight-rules="insights.rules"
      :first-review="firstReview"
      :show-toast="showToast"
      :with-busy="withBusy"
      @update:first-review="firstReview = $event"
      @save-test-bands="saveTestBands"
      @reset-test-bands="resetTestBands"
      @save-rule="saveRule"
      @reset-rule="resetRule"
      @toggle-tag="toggleTag"
      @reload="load"
    />

    <!-- 大队委（题库成绩）：机器判的 / 孩子自评的分开报 -->
    <AdminQuiz
      v-if="section === 'quiz'"
      :kids="kids"
      :kid="selectedKid"
      :show-toast="showToast"
      @pick-kid="pickKid"
    />

    <!-- 每日任务 -->



    <AdminWords
      v-if="section === 'words'"
      :kid="selectedKid"
      :kid-name="currentKidName"
    />

    <!-- 已学到 -->
    <AdminCursor
      v-if="section === 'cursor'"
      :cursors="cursors"
      :progress-lock="progressLock"
      :hidden-subjects="hiddenSubjects"
      :sprite-cfg="spriteCfg"
      :tasks-by-subject="tasksBySubject"
      :kid-name="currentKidName"
      :subjects="subjects"
      :tasks="tasks"
      :daily="daily"
      :term-units="termUnits"
      @set-cursor="setCursor"
      @toggle-lock="toggleLock"
      @set-subject-visible="toggleSubjectVisible"
      @save-sprites-cfg="saveSpritesCfg"
    />
    <!-- 单元测试成绩 -->

    <!-- 家庭（孩子账号 / 家长成员 / 邀请码 / 家长密码）-->
    <AdminKids
      v-if="section === 'kids'"
      ref="kidsRef"
      :kids="kids"
      :terms="terms"
      :members="members"
      :invites="invites"
      :invite-protect="inviteProtect"
      :is-owner="isOwner"
      :me-account="me.account"
      :hours="familyHours"
      :show-toast="showToast"
      @reload="load"
      @reload-invites="refreshInvites"
      @toggle-protect="toggleProtect"
      @kid-removed="onKidRemoved"
    />
      </PageBoundary>

      <div v-if="packError" class="w-next pack-err">
        <strong>这一页的数据没加载上</strong>
        <span>{{ packError }}</span>
        <button type="button" class="ok" @click="retryPacks">重试</button>
      </div>
      <div v-if="isDirty" class="w-next dirty-bar">
        <strong>有未保存的修改</strong>
        <span></span>
        <button type="button" class="ok" @click="saveDirty">保存</button>
        <button type="button" class="ghost-s" @click="discardDirty">放弃</button>
      </div>
      </main>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.admin { max-width: 1160px; margin: 0 auto; padding: 20px 24px; padding-top: calc(20px + env(safe-area-inset-top)); font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: var(--ink); }
.a-head {
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand-deep) 100%);
  color: #fff; border-radius: var(--radius-xl); padding: 16px 20px;
  display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
  box-shadow: var(--shadow-md);
}
.a-title { font-size: 20px; font-weight: 800; letter-spacing: -.02em; }
.a-sub { font-size: 12px; opacity: .75; margin-top: 2px; }
.a-head-right { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.kid-switch { display: flex; gap: 6px; flex-wrap: wrap; }
.kid-switch button {
  border: none; background: rgba(255,255,255,.18); color: #fff;
  border-radius: var(--radius-pill); padding: 7px 14px; font-weight: 700;
  cursor: pointer; font-family: inherit; font-size: 13px;
}
.kid-switch button.on { background: #fff; color: var(--brand-deep); }
.kid-one { font-weight: 700; font-size: 14px; opacity: .95; }
.a-exit { background: rgba(255,255,255,.22); border: none; color: #fff; border-radius: var(--radius-pill); padding: 9px 16px; font-weight: 700; cursor: pointer; font-family: inherit; }
.a-body { display: flex; gap: 22px; align-items: flex-start; margin-top: 18px; }
.a-side { width: 200px; flex: none; background: var(--surface); border-radius: var(--radius-xl); padding: 12px 10px; box-shadow: var(--shadow-md); border: 1px solid var(--line); position: sticky; top: calc(12px + env(safe-area-inset-top)); }
.a-group { font-size: 11px; color: var(--ink-3); font-weight: 800; padding: 12px 10px 4px; letter-spacing: .08em; }
.a-group:first-child { padding-top: 4px; }
.a-nav { display: flex; align-items: center; gap: 8px; width: 100%; padding: 9px 12px; border: none; background: none; border-radius: var(--radius-md); color: var(--ink-2); font-weight: 700; font-size: 13px; cursor: pointer; text-align: left; font-family: inherit; }
.a-nav:hover { background: var(--surface-2); }
.a-nav.on { background: var(--accent); color: #fff; box-shadow: var(--shadow-button); }
.a-nav-ico { width: 18px; text-align: center; }
.a-main { flex: 1; min-width: 0; padding-bottom: 72px; }
@media (max-width: 560px) {
  .admin { padding: 10px; padding-top: calc(10px + env(safe-area-inset-top)); }
}

/* 任务页行样式（.a-item 等）在 adminBase.css：本文件的 scoped 规则到不了子组件 */
.toast { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%); background: rgba(31,59,85,.92); color: #fff; padding: 10px 18px; border-radius: var(--radius-pill); font-size: 14px; z-index: 20; }
.dirty-bar { position: sticky; bottom: 0; margin: 0; z-index: 5; box-shadow: var(--shadow-md); padding-bottom: calc(12px + env(safe-area-inset-bottom)); }
/* .pack-err（数据没加载上 / 页面渲染出错）在 adminBase.css：PageBoundary 是子组件，本文件的 scoped 到不了它 */

@media (max-width: 760px) {
  .a-body { flex-direction: column; }
  .a-side { width: 100%; position: static; display: flex; gap: 6px; overflow-x: auto; padding: 8px; }
  .a-group { display: none; }
  .a-nav { flex: 0 0 auto; width: auto; white-space: nowrap; }
  .a-title { font-size: 22px; }
}
.setup { min-height: 80vh; display: flex; align-items: center; justify-content: center; }
.setup-card { max-width: 420px; width: 100%; }
.setup-card .fld { display: block; margin: 10px 0; }
.recovery-code {
  font-family: ui-monospace, Menlo, monospace; font-size: 22px; font-weight: 800;
  letter-spacing: .18em; text-align: center; padding: 14px; background: var(--surface-2);
  border-radius: var(--radius-md); margin: 16px 0;
}
</style>