<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api, setSelectedKid } from './api.js'
import { APP_LABEL, APP_REVISION } from './version.js'
import { rankIcon } from './icons.js'
import { tagHelp } from './tagHelp.js'
import { SUBJECT_ORDER, n1, isTimeMetric, formatDuration, formatMetricValue } from './format.js'
import { initAdminWords, loadWords } from './adminWords.js'
import AdminWords from './components/AdminWords.vue'
import AdminInsights from './components/AdminInsights.vue'
import AdminTasks from './components/AdminTasks.vue'
import AdminApprove from './components/AdminApprove.vue'
import AdminReview from './components/AdminReview.vue'
import { initAdminEdit, useAdminEdit } from './adminEdit.js'
import { Eye, Baby, Store, ClipboardCheck, BookOpen, MapPinned, Sun, Star, Check, ArrowLeft, BookMarked, Globe } from '@lucide/vue'

const props = defineProps({ recoveryCode: { type: String, default: '' } })
const emit = defineEmits(['exit', 'switched', 'consumed-recovery'])
const me = ref({ role: 'parent', parent_role: 'member' })  // 当前家长信息
const kids = ref([])
const members = ref([])
const inviteProtect = ref(false)
const penaltyEnabled = ref(false)
const penalties = ref([])
const penaltySummary = ref({ net: 0, count: 0, amount: 0, by_reason: [] })
const newPenalty = reactive({ amount: 1, reason: '磨蹭', note: '' })
const penaltySubmitting = ref(false)  // 扣分提交中
const PENALTY_REASONS = ['磨蹭', '没完成约定', '没礼貌', '其他']
const PENALTY_AMOUNTS = [1, 2, 3, 5]
const invites = ref([])
const selectedKid = ref('')
const newKid = reactive({ name: '', account: '', pin: '', pin2: '', term_id: 'g5s1', gender: '' })
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
const bankHistoryOpen = ref(false)
const kidAddOpen = ref(false)
const tasksRef = ref(null)  // 任务页子组件：脏条要调它的 isAddDirty/discardAdd/saveCurrentEdit
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
    await fn()
    if (staleNow(kid, gen)) return
    loaded.add(name)
  })().finally(() => { if (inflight.get(name) === p) inflight.delete(name) })
  inflight.set(name, p)
  return p
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
async function toggleBank() {
  bankBusy.value = true
  try { bankData.value = await api.admin.setBankEnabled(!bankData.value.enabled); showToast(bankData.value.enabled ? '已开启阳光银行' : '已关闭阳光银行') }
  catch (e) { showToast(e.message) }
  finally { bankBusy.value = false }
}
async function saveBankGoal() {
  if (!bankGoal.name.trim()) return showToast('填目标名称')
  bankBusy.value = true
  try { bankData.value = await api.admin.saveBankGoal({ name: bankGoal.name, target: bankGoal.target }); snapBankGoal(); showToast('目标已保存') }
  catch (e) { showToast(e.message) }
  finally { bankBusy.value = false }
}
async function bankGoalDeliver() {
  if (!confirm('确认这个目标已经兑现？')) return
  try { bankData.value = await api.admin.deliverBankGoal(); showToast('已标记兑现') }
  catch (e) { showToast(e.message) }
}
async function handleBankRequest(id, action) {
  try { await (action === 'approve' ? api.admin.approveBankRequest(id) : api.admin.rejectBankRequest(id)); showToast(action === 'approve' ? '已批准取出' : '已拒绝申请'); await loadBank() }
  catch (e) { showToast(e.message) }
}
async function saveBankInterest() {
  bankBusy.value = true
  try {
    const r = await api.admin.saveBankInterestConfig({ enabled: bankInterest.enabled, cycle: bankInterest.cycle, rate: bankInterest.rate, threshold: bankInterest.threshold })
    Object.assign(bankInterest, r)
    showToast('利息配置已保存')
  } catch (e) { showToast(e.message) }
  finally { bankBusy.value = false }
}
async function settleInterestNow() {
  try {
    const r = await api.admin.settleInterestNow()
    showToast(r.settled ? `已结算利息 ${r.interest} 颗` : '暂无需结算')
    await loadBank()
  } catch (e) { showToast(e.message) }
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
const newReward = reactive({ name: '', price: 30, category: '娱乐' })
async function addReward() {
  if (!newReward.name || !newReward.price) return showToast('填名称和价格')
  await withBusy(async () => {
    await api.admin.createReward({ ...newReward })
    Object.assign(newReward, { name: '', price: 30, category: '娱乐' })
    showToast('已新增'); await load()
  })
}
async function saveReward(r) { await withBusy(async () => { await api.admin.updateReward(r.id, r); clearEdit(); showToast('已保存') }) }
async function delReward(id) { if (!confirm('删除这个奖励？')) return; await withBusy(async () => { await api.admin.delReward(id); await load() }) }

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
const newRank = reactive({ name: '', min_sunshine: 0 })
async function addRank() {
  if (!newRank.name) return showToast('填等级名')
  await withBusy(async () => {
    await api.admin.createRank({ ...newRank })
    Object.assign(newRank, { name: '', min_sunshine: 0 })
    showToast('已新增'); await load()
  })
}
async function saveRank(r) { await withBusy(async () => { await api.admin.updateRank(r.id, r); clearEdit(); showToast('已保存') }) }
async function delRank(id) {
  if (!confirm('删除这个等级？')) return
  try { await api.admin.delRank(id); await load() } catch (e) { showToast(e.message) }
}

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
const cursorSubjects = computed(() => {
  const unitIds = new Set(termUnits.value.map(u => u.id))
  const ids = new Set(tasks.value.filter(t => unitIds.has(t.unit_id)).map(t => t.subject_id))
  return subjects.value.filter(s => ids.has(s.id))
})
const displaySubjects = computed(() => {
  const ids = new Set([
    ...tasks.value.map(t => t.subject_id),
    ...daily.value.map(d => d.subject_id),
  ])
  const list = subjects.value.filter(s => ids.has(s.id))
  list.sort((a, b) => SUBJECT_ORDER.indexOf(a.id) - SUBJECT_ORDER.indexOf(b.id))
  return list
})
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
function filled(v) { return String(v ?? '').trim() !== '' }
function isAddDirty() {
  if (filled(newReward.name) || Number(newReward.price) !== 30 || (newReward.category || '') !== '娱乐') return true
  if (filled(newRank.name) || Number(newRank.min_sunshine) !== 0) return true
  if (filled(newKid.name) || filled(newKid.account) || filled(newKid.pin) || filled(newKid.pin2) || (newKid.term_id || 'g5s1') !== 'g5s1' || (newKid.gender || '')) return true
  return false
}
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
const isDirty = computed(() => isEditDirty() || isAddDirty() || !!tasksRef.value?.isAddDirty?.() || isWeeklyDirty() || isBandsDirty() || isBankDirty())
function discardDirty() {
  cancelEdit()
  if (weeklyGoalSnap.value != null) weeklyGoal.value = weeklyGoalSnap.value
  if (testBandsSnap.value != null) testBands.value = testBandsSnap.value.map(x => [...x])
  if (bankGoalSnap.value != null) Object.assign(bankGoal, { name: bankGoalSnap.value.name, target: bankGoalSnap.value.target })
  Object.assign(newReward, { name: '', price: 30, category: '娱乐' })
  Object.assign(newRank, { name: '', min_sunshine: 0 })
  Object.assign(newKid, { name: '', account: '', pin: '', pin2: '', term_id: 'g5s1', gender: '' })
  tasksRef.value?.discardAdd?.()
  kidAddOpen.value = false
}
async function saveDirty() {
  if (isAddDirty()) {
    showToast('新增还没提交，点新增或放弃')
    return
  }
  if (isEditDirty()) {
    const row = findEditRow(editKind.value, editId.value)
    if (!row) return
    const kind = editKind.value
    if (kind === 'reward') await saveReward(row)
    else if (kind === 'rank') await saveRank(row)
    else if (kind === 'daily' || kind === 'task') await tasksRef.value?.saveCurrentEdit?.()
    else if (kind === 'kid') await saveKid(row)
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
const pinForm = reactive({ cur: '', next: '', confirm: '' })
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

async function addKid() {
  if (!newKid.name) return showToast('填名字')
  if (!(newKid.account || '').trim()) return showToast('填登录账号')
  if ((newKid.pin || '').trim() && newKid.pin.length < 6) return showToast('密码至少 6 位')
  try {
    const r = await api.admin.createKid({ ...newKid })
    const kidName = newKid.name || r.account || '孩子'
    newKid.name = newKid.account = newKid.pin = newKid.pin2 = ''
    newKid.gender = ''
    if (r && r.pin) alert(`已添加。${kidName}的登录密码是：${r.pin}\n（系统随机生成，只显示这一次，请记下来告诉孩子）`)
    else showToast('已添加')
    kidAddOpen.value = false
    await load()
  } catch (e) { showToast(e.message) }
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

async function saveKid(k) {
  if (k._pin) {
    if (String(k._pin).trim().length < 6) return showToast('孩子密码至少 6 位')
    if (!confirm('要改「' + k.name + '」的登录密码？改完孩子要用新密码登录。')) return
  }
  try {
    await api.admin.updateKid(k.id, { name: k.name, account: k.account, term_id: k.term_id, pin: k._pin || '', gender: k.gender || '' })
    k._pin = ''
    clearEdit()
    showToast('已保存')
    await load()
  } catch (e) { showToast(e.message) }
}
async function delKid(k) {
  if (!isOwner.value) return showToast('只有创建者能删除孩子')
  if (!confirm('删除「' + k.name + '」？打卡记录还在库里，只是账号没了。')) return
  try {
    await api.admin.delKid(k.id)
    if (selectedKid.value === k.id) { selectedKid.value = ''; setSelectedKid('') }
    showToast('已删除')
    await load()
  } catch (e) { showToast(e.message) }
}
async function transferOwner(m) {
  if (!isOwner.value) return showToast('只有创建者能转让')
  if (!confirm(`把创建者交给「${m.name}」？交出去后你变成普通成员，不能再删人、删孩子、发邀请码。`)) return
  try {
    await api.admin.transferOwner(m.id)
    showToast('已交给 ' + m.name)
    await load()
  } catch (e) { showToast(e.message) }
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
const pendingBankRequests = computed(() => (bankRequests.value || []).filter(r => r.status === 'pending'))
const historyBankRequests = computed(() => (bankRequests.value || []).filter(r => r.status !== 'pending'))
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
const penaltyReasonRows = computed(() => (penaltySummary.value.by_reason || []).filter(x => x.count > 0))
const maxPenaltyAmount = computed(() => Math.max(1, ...penaltyReasonRows.value.map(x => x.amount || 0)))
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

async function changePin() {
  const cur = pinForm.cur.trim()
  const next = pinForm.next.trim()
  if (!cur) return showToast('请输入当前密码')
  if (!next) return showToast('请输入新密码')
  if (next.length < 8) return showToast('家长密码至少 8 位')
  if (next !== pinForm.confirm) return showToast('两次新密码不一致')
  try {
    await api.admin.changePin(next, cur)
    pinForm.cur = pinForm.next = pinForm.confirm = ''
    showToast('密码已改，其他设备需要重新登录')
  } catch (e) { showToast(e.message) }
}
async function refreshInvites() { invites.value = await api.admin.invites() }
async function makeInvite() {
  try {
    const r = await api.admin.invite()
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
async function addPenalty() {
  if (!penaltyEnabled.value) return showToast('扣分未开启')
  if (penaltySubmitting.value) return  // 防止重复提交
  
  const amount = Number(newPenalty.amount)
  if (!Number.isInteger(amount) || amount < 1) return showToast('扣分要是正整数')
  if (newPenalty.reason === '其他' && !String(newPenalty.note || '').trim()) return showToast('选「其他」时要写备注')
  const who = currentKidName.value || '这个孩子'
  if (!confirm(`给「${who}」扣 ${amount} 阳光（${newPenalty.reason}）？余额扣到 0 为止，等级不变。`)) return
  
  penaltySubmitting.value = true
  try {
    await api.admin.createPenalty({ amount, reason: newPenalty.reason, note: newPenalty.note })
    Object.assign(newPenalty, { amount: 1, reason: '磨蹭', note: '' })
    showToast('已记下扣分')
    await load()
  } catch (e) { 
    showToast(e.message) 
  } finally {
    penaltySubmitting.value = false
  }
}
async function cancelPenalty(id) {
  if (penaltySubmitting.value) return
  if (!confirm('撤回这笔扣分？阳光会加回去，等级不变。')) return
  penaltySubmitting.value = true
  try {
    await api.admin.cancelPenalty(id)
    showToast('已撤回')
    await load()
  } catch (e) { showToast(e.message) }
  finally { penaltySubmitting.value = false }
}
async function delMember(m) {
  if (!confirm('删除「' + m.name + '」？立刻失效。')) return
  try {
    await api.admin.delMember(m.id)
    showToast('已删除')
    await load()
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
      <button class="ok wide" :disabled="setupBusy" @click="finishSetup">{{ setupBusy ? '正在创建…' : '创建并进入' }}</button>
      <p v-if="toast" class="dim">{{ toast }}</p>
    </div>
  </div>
  <div v-else-if="shownRecovery" class="admin setup">
    <div class="a-card enter setup-card">
      <h3>找回码</h3>
      <p class="recovery-code">{{ shownRecovery }}</p>
      <button class="ok wide" @click="dismissRecovery">我已抄好，进入工作台</button>
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
      @go-review-kid="goReviewKid"
      @go-insight="goInsight"
      @undo-daily="undoDaily"
    />

    <!-- 商店 -->
    <section v-if="section === 'shop'" class="a-card enter">
      <h3>阳光</h3>
      <h4 class="w-h">兑换商店</h4>
      <div class="task-row" v-for="r in rewards" :key="r.id">
        <template v-if="isEditing('reward', r.id)">
          <label class="fld grow"><span>奖励名</span><input v-model="r.name" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="r.price" type="number" /></label>
          <label class="fld w84"><span>分类</span><input v-model="r.category" /></label>
          <div class="ops">
            <button class="ok" @click="saveReward(r)">保存</button>
            <button class="ghost-s" @click="cancelEdit">取消</button>
          </div>
        </template>
        <template v-else>
          <span class="task-readonly-title">{{ r.name }}</span>
          <span class="badge daily">{{ r.price }} 阳光</span>
          <span class="dim">{{ r.category }}</span>
          <div class="ops">
            <button class="ghost-s" @click="beginEdit('reward', r)">改</button>
            <button class="del" @click="delReward(r.id)">删</button>
          </div>
        </template>
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

    <!-- 阳光银行 -->
      <h4 class="w-h">阳光银行{{ currentKidName ? ' · ' + currentKidName : '' }}</h4>
      <div class="lock-row">
        <span class="badge">孩子端开关</span>
        <span class="grow">关闭后不显示入口，余额和目标保留</span>
        <button type="button" :class="['toggle', { on: bankData.enabled }]" @click="toggleBank" :disabled="bankBusy">{{ bankData.enabled ? '开' : '关' }}</button>
      </div>
      <div class="sun-hero bank-admin-hero">
        <div class="sun-box"><span>银行余额</span><b>{{ bankData.balance }}</b></div>
        <div class="sun-box"><span>口袋余额</span><b>{{ bankData.pocket_balance }}</b></div>
      </div>
      <div class="add-box">
        <div class="add-title">一个存钱目标</div>
        <div class="frm-row">
          <label class="fld grow"><span>目标名称</span><input v-model="bankGoal.name" maxlength="40" placeholder="如：周末去公园" /></label>
          <label class="fld w84"><span>需要阳光</span><input v-model.number="bankGoal.target" type="number" min="1" max="10000" /></label>
          <button class="ok" @click="saveBankGoal">保存目标</button>
        </div>
        <div v-if="bankData.goal" class="dim">已存 {{ bankData.goal.saved }} / {{ bankData.goal.target }} · {{ bankData.goal.reached ? '已达成' : '进行中' }}</div>
        <button v-if="bankData.goal?.reached" class="ok mt8" @click="bankGoalDeliver">标记已兑现</button>
      </div>
      <h4 class="w-h">取出申请</h4>
      <div v-if="!pendingBankRequests.length" class="dim">还没有取出申请。</div>
      <div v-for="r in pendingBankRequests" :key="r.id" class="apv-row">
        <div class="apv-info"><span class="apv-name">{{ r.kid_name }}申请取出 {{ r.amount }} 颗</span><span class="dim">{{ r.created_at }}</span></div>
        <div class="apv-right"><button class="ok" @click="handleBankRequest(r.id, 'approve')">批准</button><button class="del" @click="handleBankRequest(r.id, 'reject')">拒绝</button></div>
      </div>
      <button v-if="historyBankRequests.length" type="button" class="ghost-s rules-toggle" @click="bankHistoryOpen = !bankHistoryOpen">{{ bankHistoryOpen ? '收起已处理' : '看已处理' }}</button>
      <div v-if="bankHistoryOpen" v-for="r in historyBankRequests" :key="'h-' + r.id" class="apv-row">
        <div class="apv-info"><span class="apv-name">{{ r.kid_name }}申请取出 {{ r.amount }} 颗</span><span class="dim">{{ r.created_at }}</span></div>
        <div class="apv-right"><span class="st delivered">{{ r.status === 'approved' ? '已批准' : '已拒绝' }}</span></div>
      </div>
      <p class="dim mt14">银行里的阳光不能用于兑换商店；取出必须由家长批准。</p>
      
      <h4 class="w-h">利息设置</h4>
      <div class="lock-row">
        <span class="badge">利息开关</span>
        <span class="grow">关闭后不再结算利息</span>
        <button type="button" :class="['toggle', { on: bankInterest.enabled }]" @click="bankInterest.enabled = !bankInterest.enabled; saveBankInterest()" :disabled="bankBusy">{{ bankInterest.enabled ? '开' : '关' }}</button>
      </div>
      <div v-if="bankInterest.enabled" class="frm-row">
        <label class="fld"><span>结算周期</span>
          <select v-model="bankInterest.cycle" @change="saveBankInterest">
            <option value="weekly">每周六</option>
            <option value="biweekly">每两周六</option>
            <option value="monthly">每月最后一天</option>
          </select>
        </label>
        <label class="fld"><span>利率 (%)</span>
          <input v-model.number="bankInterest.rate" type="number" min="0" max="10" step="0.5" @blur="saveBankInterest" />
        </label>
        <label class="fld"><span>起存点</span>
          <select v-model.number="bankInterest.threshold" @change="saveBankInterest">
            <option :value="0">不限</option>
            <option :value="10">10 颗</option>
            <option :value="20">20 颗</option>
            <option :value="50">50 颗</option>
            <option :value="100">100 颗</option>
          </select>
        </label>
      </div>
      <div v-if="bankInterest.enabled" class="dim">
        <p>💡 利息是什么？银行为「存在这里的阳光」付一点报酬，鼓励孩子延迟满足、积累财富。</p>
        <p>这里的利率只管<strong>活期</strong>。孩子还能自己开定存单：7 天 2%、10 天 3%、15 天 5%、30 天 8%、60 天 12%。到期一次结息；提前支取按已过天数打五折，当天存当天取没有利息。</p>
        <p>利率不宜过高，否则孩子可能失去做任务的动力。建议低年级 3%–5%、高年级 5%–8%。</p>
        <p v-if="bankInterest.last_settle">上次结算：{{ bankInterest.last_settle }}</p>
        <button v-if="isOwner" class="ghost-s mt8" @click="settleInterestNow">补结算上一期利息</button>
      </div>
    </section>

    <!-- 扣分 -->
    <section v-if="section === 'shop'" class="a-card enter">
      <h3>记下扣分{{ currentKidName ? ' · ' + currentKidName : '' }}</h3>
      <div class="lock-row">
        <span class="badge">扣分开关</span>
        <span class="grow">{{ penaltyEnabled ? '已开' : '未开' }}</span>
        <button v-if="isOwner" :class="['toggle', { on: penaltyEnabled }]" @click="togglePenalty">{{ penaltyEnabled ? '已开' : '未开' }}</button>
        <span v-else class="dim">只有创建者能开关</span>
      </div>
      <template v-if="penaltyEnabled">
        <div class="add-box">
          <div class="add-title">记一笔</div>
          <div class="chip-row">
            <span class="chip-label">扣多少</span>
            <button v-for="n in PENALTY_AMOUNTS" :key="n" type="button" :class="['chip', { on: newPenalty.amount === n }]" @click="newPenalty.amount = n">-{{ n }}</button>
          </div>
          <div class="chip-row">
            <span class="chip-label">原因</span>
            <button v-for="r in PENALTY_REASONS" :key="r" type="button" :class="['chip', { on: newPenalty.reason === r }]" @click="newPenalty.reason = r">{{ r }}</button>
          </div>
          <label class="fld">
            <span>{{ newPenalty.reason === '其他' ? '说明（必填）' : '说明（可选）' }}</span>
            <input v-model="newPenalty.note" maxlength="40" placeholder="如：约好 8 点写完还在玩" />
          </label>
          <button class="ok wide" @click="addPenalty" :disabled="penaltySubmitting">{{ penaltySubmitting ? '提交中...' : '确认扣 ' + newPenalty.amount + ' 阳光' }}</button>
        </div>
        <div v-if="penaltySummary.count" class="pen-sum">
          <p class="dim">{{ penaltySummary.count }} 笔 · 净扣 {{ penaltySummary.amount }}</p>
          <div class="w-subj">
            <div v-for="s in penaltyReasonRows" :key="s.reason" class="w-subj-row">
              <span class="w-subj-name">{{ s.reason }}</span>
              <div class="w-subj-track"><i :style="{ width: (s.amount / maxPenaltyAmount * 100) + '%' }"></i></div>
              <span class="w-subj-num">{{ s.count }} 笔 · -{{ s.amount }}</span>
            </div>
          </div>
        </div>
        <div v-if="!penalties.length" class="dim mt8">还没有扣分记录。</div>
        <div class="apv-row" v-for="p in penalties" :key="p.id">
          <div class="apv-info">
            <span class="apv-name">{{ p.reason || p.note || '扣分' }}</span>
            <span class="dim">{{ p.note && p.note !== p.reason ? p.note + ' · ' : '' }}{{ p.date }}</span>
          </div>
          <div class="apv-right">
            <span class="pen-amt">{{ p.delta }}</span>
            <span v-if="p.cancelled" class="st delivered">已撤回</span>
            <button v-else class="ghost-s" @click="cancelPenalty(p.id)">撤回</button>
          </div>
        </div>
      </template>

    </section>

    <!-- 审批 -->
    <AdminApprove
      v-if="section === 'approve'"
      :redemptions="redemptions"
      @approve="approveRedeem"
      @reject="rejectRedeem"
      @deliver="deliverRedeem"
    />

    <!-- 等级 -->
    <section v-if="section === 'shop'" class="a-card enter">
      <h3>成长等级</h3>
      <div class="task-row" v-for="r in ranks" :key="r.id">
        <span class="rank-icon"><component :is="rankIcon(r.icon)" class="ico" :size="18" /></span>
        <template v-if="isEditing('rank', r.id)">
          <label class="fld grow"><span>等级名</span><input v-model="r.name" /></label>
          <label class="fld w84"><span>累计阳光 ≥</span><input v-model.number="r.min_sunshine" type="number" /></label>
          <div class="ops">
            <button class="ok" @click="saveRank(r)">保存</button>
            <button class="ghost-s" @click="cancelEdit">取消</button>
          </div>
        </template>
        <template v-else>
          <span class="task-readonly-title">{{ r.name }}</span>
          <span class="dim">累计阳光 ≥ {{ r.min_sunshine }}</span>
          <div class="ops">
            <button class="ghost-s" @click="beginEdit('rank', r)">改</button>
            <button class="del" @click="delRank(r.id)">删</button>
          </div>
        </template>
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

    <!-- 每日任务 -->



    <AdminWords
      v-if="section === 'words'"
      :kid="selectedKid"
      :kid-name="currentKidName"
    />

    <!-- 已学到 -->
    <section v-if="section === 'cursor'" class="a-card enter">
      <h3>已学到哪一课</h3>
      <div class="cursor-row" v-for="s in cursorSubjects" :key="s.id">
        <span class="cursor-subj">{{ s.name }}</span>
        <select :value="cursors[s.id] || ''" @change="setCursor(s.id, $event.target.value)">
          <option value="">从头开始</option>
          <option v-for="t in (tasksBySubject[s.id] || [])" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select>
      </div>
      <h4 class="w-h">孩子端显示学科</h4>
      <p class="dim">关掉的科目，孩子侧栏和今日推荐都看不到；任务还在，随时开回来。</p>
      <div class="lock-row" v-for="s in displaySubjects" :key="'vis-' + s.id">
        <span class="badge">{{ s.name }}</span>
        <span class="grow">孩子端显示</span>
        <button type="button" :class="['toggle', { on: subjectShown(s.id) }]" @click="toggleSubjectVisible(s.id)">{{ subjectShown(s.id) ? '开' : '关' }}</button>
      </div>
      <div class="lock-row mt14">
        <span class="badge">进度锁</span>
        <span class="grow">只让打「当前单元」</span>
        <button :class="['toggle', { on: progressLock }]" @click="toggleLock">{{ progressLock ? '开' : '关' }}</button>
      </div>
      <h4 class="w-h">图鉴与基地</h4>
      <p class="dim">给 {{ currentKidName || '当前孩子' }} 用。关掉图鉴后，连击宝箱只给阳光；秘密基地仍在，孩子端显示「建设中」。</p>
      <div class="lock-row">
        <span class="badge">阳光图鉴</span>
        <span class="grow">连击宝箱会孵出阳光精灵，进图鉴。关掉则宝箱只给阳光。</span>
        <button type="button" :class="['toggle', { on: spriteCfg.enabled }]" @click="saveSpritesCfg({ enabled: !spriteCfg.enabled })">{{ spriteCfg.enabled ? '开' : '关' }}</button>
      </div>
      <div class="lock-row">
        <span class="badge">秘密基地</span>
        <span class="grow">精灵住进天台/树屋/云上，星尘可以买小玩具。关掉则图鉴只显示格子。</span>
        <button type="button" :class="['toggle', { on: spriteCfg.base_enabled }]" @click="saveSpritesCfg({ base_enabled: !spriteCfg.base_enabled })">{{ spriteCfg.base_enabled ? '开' : '关' }}</button>
      </div>
    </section>
    <!-- 单元测试成绩 -->

    <section v-if="section === 'kids'" class="a-card">
      <h3>家庭</h3>
      <h4 class="w-h">孩子账号</h4>
      <p v-if="!terms.length" class="dim">学期列表还没载入，退出再进一次家长端。</p>

      <div class="kid-card" v-for="k in kids" :key="k.id">
        <template v-if="isEditing('kid', k.id)">
          <label class="fld"><span>家里怎么叫</span><input v-model="k.name" placeholder="如：乐乐" /></label>
          <label class="fld"><span>登录账号</span><input v-model="k.account" placeholder="如：lele" /></label>
          <label class="fld"><span>现在读哪册</span>
            <select v-model="k.term_id">
              <option disabled value="">请选择</option>
              <option v-for="tm in terms" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
            </select>
          </label>
          <label class="fld"><span>性别</span>
            <select v-model="k.gender">
              <option value="">还没填</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>
          <label class="fld kid-pin"><span>改密码</span><input v-model="k._pin" type="password" autocomplete="new-password" placeholder="至少 6 位，不要重复或连续数字" /></label>
          <div class="ops">
            <button class="ok" @click="saveKid(k)">保存资料</button>
            <button class="ghost-s" @click="cancelEdit">取消</button>
            <button v-if="isOwner" class="del" @click="delKid(k)">删除账号</button>
            <span v-else class="dim">只有创建者能删除孩子</span>
          </div>
        </template>
        <template v-else>
          <div class="sys-row kid-readonly">
            <span class="sys-name">{{ k.name }}</span>
            <span class="dim">{{ k.account }} · {{ (terms.find(tm => tm.id === k.term_id) || {}).label || k.term_id }}<template v-if="k.gender"> · {{ k.gender }}</template></span>
            <div class="ops">
              <button class="ghost-s" @click="beginEdit('kid', k)">改</button>
              <button v-if="isOwner" class="del" @click="delKid(k)">删</button>
            </div>
          </div>
        </template>
      </div>
      <button type="button" class="ghost-s rules-toggle" @click="kidAddOpen = !kidAddOpen">{{ kidAddOpen ? '收起新增' : '＋再加一个孩子' }}</button>
      <div v-if="kidAddOpen" class="add-box">
        <div class="add-title">再加一个孩子</div>
        <div class="frm-row">
          <label class="fld grow"><span>家里怎么叫</span><input v-model="newKid.name" placeholder="如：弟弟" /></label>
          <label class="fld grow"><span>登录账号</span><input v-model="newKid.account" placeholder="如：didi" /></label>
          <label class="fld grow"><span>密码</span><input v-model="newKid.pin" type="password" autocomplete="new-password" placeholder="留空自动生成；自填至少 6 位" /></label>
        </div>
        <div class="frm-row">
          <label class="fld grow"><span>现在读哪册</span>
            <select v-model="newKid.term_id">
              <option v-for="tm in terms" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
            </select>
          </label>
          <label class="fld w84"><span>性别</span>
            <select v-model="newKid.gender">
              <option value="">还没填</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>
        </div>
        <button class="ok wide" @click="addKid">添加</button>
      </div>
    </section>

    <!-- 家长成员 -->
    <section v-if="section === 'kids'" class="a-card enter">
      <h3>家长成员</h3>
      <div class="member-row" v-for="m in members" :key="m.id">
        <div class="member-info">
          <strong>{{ m.name }}</strong>
          <span class="dim">{{ m.account }}</span>
        </div>
        <span class="badge" :class="{ daily: m.parent_role === 'owner' }">{{ m.parent_role === 'owner' ? '创建者' : '成员' }}</span>
        <button v-if="isOwner && m.account !== me.account" class="ok" @click="transferOwner(m)">交给创建者</button>
        <button v-if="isOwner && m.account !== me.account" class="del" @click="delMember(m)">删</button>
        <span v-else-if="!isOwner" class="dim">只有创建者能改成员</span>
      </div>
      <p v-if="!members.length" class="dim">还没有家长成员。</p>
    </section>

    <!-- 邀请码 -->
    <section v-if="section === 'kids'" class="a-card enter">
      <h3>邀请码</h3>
      <div class="lock-row">
        <span class="badge">邀请码保护</span>
        <span class="grow">开着时邀请码一次性 + 24 小时；关掉则常驻复用</span>
        <button v-if="isOwner" type="button" :class="['toggle', { on: inviteProtect }]" @click="toggleProtect">{{ inviteProtect ? '开' : '关' }}</button>
      </div>
      <p v-if="!isOwner" class="dim">只有创建者能开关保护和生成邀请码。</p>
      <div class="frm-row mt8">
        <button v-if="isOwner" class="ok" @click="makeInvite()">生成邀请码</button>
      </div>
      <div class="member-row" v-for="iv in invites" :key="iv.code">
        <div class="member-info">
          <code class="invite-code">{{ iv.code }}</code>
          <span class="dim">{{ inviteStatus(iv) }}</span>
        </div>
        <button class="ok" @click="copyCode(iv.code)">复制</button>
        <button v-if="isOwner" class="del" @click="delInvite(iv.code)">删</button>
      </div>
      <p v-if="!invites.length" class="dim mt6">还没有邀请码。</p>
    </section>

    <section v-if="section === 'kids'" class="a-card enter">
      <h3>修改家长密码</h3>
      <p class="dim">当前账号 {{ me.account || '—' }}</p>
      <form class="settings-form" @submit.prevent="changePin">
        <label class="fld">
          <span>当前密码</span>
          <input v-model="pinForm.cur" type="password" autocomplete="current-password" />
        </label>
        <label class="fld">
          <span>新密码</span>
          <input v-model="pinForm.next" type="password" autocomplete="new-password" placeholder="至少 8 位" />
        </label>
        <label class="fld">
          <span>确认新密码</span>
          <input v-model="pinForm.confirm" type="password" autocomplete="new-password" />
        </label>
        <button class="ok" type="submit">保存新密码</button>
      </form>
    </section>
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
.invite-code { font-family: ui-monospace, monospace; font-weight: 700; font-size: 14px; }
.a-term { display: block; margin-top: 8px; font-size: 12px; }
.a-term select { margin-left: 6px; padding: 4px 8px; border-radius: var(--radius-sm); border: 1px solid var(--line); background: var(--surface); color: var(--ink); }
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
.cursor-row {
  display: grid; grid-template-columns: 88px minmax(0, 1fr); align-items: center; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid var(--surface-2);
}
.cursor-subj { font-weight: 800; color: var(--brand-deep); }
.cursor-row select {
  width: 100%; min-width: 0; border: 1px solid var(--line); border-radius: var(--radius-md);
  padding: 8px 10px; font-size: 15px; color: var(--ink); background: var(--surface);
  font-family: inherit; min-height: 40px;
}
.chip-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 10px; }
.chip-label { font-size: 12px; color: var(--ink-3); font-weight: 700; width: 48px; }
.chip {
  border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: var(--radius-pill); padding: 6px 12px; font-weight: 700; font-size: 13px;
  cursor: pointer; font-family: inherit;
}
.chip.on { background: var(--accent); color: #fff; border-color: var(--accent); }
.pen-amt { font-weight: 800; color: var(--danger); font-variant-numeric: tabular-nums; }
@media (max-width: 560px) {
  .admin { padding: 10px; padding-top: calc(10px + env(safe-area-inset-top)); }
}
.a-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 0; border-bottom: 1px solid var(--surface-2); }
.a-item.add { border-top: 1px dashed var(--line); margin-top: 8px; padding-top: 12px; }
.a-subject-h { font-weight: 800; color: var(--brand-deep); margin-top: 8px; font-size: 14px; }
.a-item input, .a-item select { border: 1px solid var(--line); border-radius: var(--radius-md); padding: 8px 10px; font-size: 15px; color: var(--ink); background: var(--surface); font-family: inherit; min-height: 40px; }
.a-item input:focus, .a-item select:focus { outline: none; border-color: var(--brand); }
.w-name { flex: 1; min-width: 120px; }
.w-cat { width: 90px; }
.toast { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%); background: rgba(31,59,85,.92); color: #fff; padding: 10px 18px; border-radius: var(--radius-pill); font-size: 14px; z-index: 20; }

.pen-sum { margin: 12px 0 4px; }
.pen-sum .w-subj-name { width: 84px; }

.settings-form { display: flex; flex-direction: column; gap: 12px; max-width: 380px; margin-top: 12px; }
.settings-form .ok { align-self: flex-start; }
.member-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 0; border-bottom: 1px solid var(--surface-2); }
.member-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.kid-card { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 14px; padding: 16px 0; border-bottom: 1px solid var(--line); }
.kid-card .fld { min-width: 0; }
.kid-pin { grid-column: 1 / -1; }
.kid-card .ops { grid-column: 1 / -1; justify-content: space-between; }
.dirty-bar { position: sticky; bottom: 0; margin: 0; z-index: 5; box-shadow: var(--shadow-md); padding-bottom: calc(12px + env(safe-area-inset-bottom)); }

@media (max-width: 760px) {
  .a-body { flex-direction: column; }
  .a-side { width: 100%; position: static; display: flex; gap: 6px; overflow-x: auto; padding: 8px; }
  .a-group { display: none; }
  .a-nav { flex: 0 0 auto; width: auto; white-space: nowrap; }
  .cursor-row { grid-template-columns: 1fr; gap: 6px; }
  .kid-card { grid-template-columns: 1fr; }
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