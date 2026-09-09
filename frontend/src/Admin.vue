<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api, setSelectedKid } from './api.js'
import { APP_LABEL, APP_REVISION } from './version.js'
import { rankIcon } from './icons.js'
import { tagHelp } from './tagHelp.js'
import { Eye, Baby, Users, KeyRound, Lock, Store, Trophy, ClipboardCheck, BookOpen, RefreshCw, MapPinned, FileText, Sun, Star, Check, ArrowLeft, BookMarked, Globe } from '@lucide/vue'

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
    { id: 'unit-task', icon: BookOpen, label: '任务与考点' },
    { id: 'daily', icon: RefreshCw, label: '每日任务' },
    { id: 'words', icon: Globe, label: '英语单词' },
    { id: 'cursor', icon: MapPinned, label: '已学到' },
    { id: 'test', icon: FileText, label: '单元测试' },
  ] },
  { group: '阳光', items: [
    { id: 'shop', icon: Store, label: '兑换商店' },
    { id: 'rank', icon: Trophy, label: '成长等级' },
    { id: 'penalty', icon: FileText, label: '扣分' },
  ] },
  { group: '家庭', items: [
    { id: 'kids', icon: Baby, label: '孩子账号' },
    { id: 'members', icon: Users, label: '家长成员' },
    { id: 'invites', icon: KeyRound, label: '邀请码' },
    { id: 'pin', icon: Lock, label: '家长密码' },
  ] },
]
const rewards = ref([])
const ranks = ref([])
const subjects = ref([])
const units = ref([])
const tasks = ref([])
const daily = ref([])
const fitnessGoals = ref({})
const dailyHist = ref({})
const terms = ref([])
const activeTerm = ref('g5s1')
const activeSubject = ref('')
const cursors = ref({})
const progressLock = ref(true)
const redemptions = ref([])
const tests = ref([])
const newTest = reactive({ subject_id: '', unit_id: '', score: '', note: '' })
const catalog = ref({ tags: [], unit_tags: [] })
const weakByUnit = ref({})
const weakPoints = ref([])
const reviewDue = ref([])
const firstReview = ref('')
const DEFAULT_TEST_BANDS = [[100, 30], [95, 20], [90, 15], [85, 10], [0, 5]]
const testBands = ref(DEFAULT_TEST_BANDS.map(x => [...x]))
const weekly = ref({ days: [], weeks: [], by_subject: [], kids: [], total_earned: 0, total_spent: 0, net: 0, balance: 0, earned_all: 0, streak: 0, checkins: 0, week_start: '', week_end: '', insight: null, family_insight: null, mastered_by_kid: [], penalty_net: 0, penalty_count: 0 })
const insights = ref({ rules: { test_fail_count: 2, test_fail_score: 80, drop_ratio: 0.3, streak_break: 2 }, kids: [] })
const familyToday = ref({ today: '', kids: [] })
const rulesOpen = ref(false)
const RULE_DEFAULTS = { test_fail_count: 2, test_fail_score: 80, drop_ratio: 0.3, streak_break: 2 }
const toast = ref('')

const dayNet = (d) => Number(d && (d.net != null ? d.net : d.earned)) || 0
const maxDayEarn = computed(() => Math.max(1, ...(weekly.value.days || []).map((d) => Math.abs(dayNet(d)))))
const subjectRows = computed(() => [...(weekly.value.by_subject || [])].sort((a, b) => (b.sun || 0) - (a.sun || 0)))
const maxSubj = computed(() => Math.max(1, ...subjectRows.value.map((s) => s.sun || 0)))
const weekNet = (w) => Number(w && (w.net != null ? w.net : w.earned)) || 0
const maxWeek = computed(() => {
  const vals = (weekly.value.weeks || []).map(weekNet)
  return Math.max(1, ...vals.map(Math.abs), 0)
})
const weekPoints = computed(() => {
  const ws = weekly.value.weeks || []
  if (!ws.length) return ''
  const vals = ws.map(weekNet)
  const min = Math.min(0, ...vals)
  const max = Math.max(0, ...vals)
  const span = (max - min) || 1
  const W = 288, H = 80, pad = 14
  return ws.map((w, i) => {
    const x = ws.length === 1 ? pad : pad + i * (W - 2 * pad) / (ws.length - 1)
    const y = H - pad - (weekNet(w) - min) / span * (H - 2 * pad)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

function showToast(m) { toast.value = m; setTimeout(() => (toast.value = ''), 2200) }
function unitName(id) { return units.value.find(u => u.id === id)?.name || id }

async function load() {
  if (section.value === 'weekly') section.value = 'insights'
  // 获取当前家长信息
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
    return
  }
  if (!selectedKid.value && ks.length) {
    selectedKid.value = ks[0].id
    setSelectedKid(ks[0].id)
  }
  const [r, rk, t, rd, wk, ts, ig, cat, wps, rv, ft, pn] = await Promise.all([api.rewards(), api.admin.ranks(), api.tasks(), api.admin.redemptions(), api.admin.weekly(), api.admin.tests(), api.admin.insights(), api.admin.unitTags(), api.admin.weakPoints(''), api.admin.reviewDue(), api.admin.familyToday(), api.admin.penalties().catch(() => ({ items: [], summary: null }))])
  rewards.value = r
  ranks.value = rk
  subjects.value = t.subjects
  units.value = t.units
  tasks.value = (t.tasks || []).map(x => ({ ...x, kid_id: x.kid_id || '' }))
  daily.value = t.daily
  fitnessGoals.value = t.fitness_goals || {}
  const withM = (t.daily || []).filter(d => (d.metrics || []).length)
  const histPairs = await Promise.all(withM.map(async d => {
    try { return [d.id, await api.dailyHistory(d.id)] }
    catch { return [d.id, []] }
  }))
  dailyHist.value = Object.fromEntries(histPairs)
  terms.value = t.terms || []
  activeTerm.value = t.active_term || 'g5s1'
  if (!activeSubject.value || !unitsBySubject.value[activeSubject.value]) activeSubject.value = Object.keys(unitsBySubject.value)[0] || ''
  cursors.value = t.cursors || {}
  progressLock.value = t.progress_lock === '1'
  redemptions.value = rd
  weekly.value = wk
  familyToday.value = ft || { today: '', kids: [] }
  if (pn && !Array.isArray(pn) && Array.isArray(pn.items)) {
    penalties.value = pn.items
    penaltySummary.value = pn.summary || { net: 0, count: 0, amount: 0, by_reason: [] }
  } else {
    penalties.value = Array.isArray(pn) ? pn : []
    penaltySummary.value = { net: 0, count: 0, amount: 0, by_reason: [] }
  }
  tests.value = ts
  insights.value = ig
  testBands.value = (ig.rules?.test_bands || DEFAULT_TEST_BANDS).map(x => [...x])
  catalog.value = cat && cat.tags ? cat : { tags: [], unit_tags: [] }
  const openWeakPoints = wps || []
  const wb = {}
  for (const x of openWeakPoints) {
    if (!wb[x.unit_id]) wb[x.unit_id] = {}
    wb[x.unit_id][x.tag_id] = true
  }
  weakPoints.value = openWeakPoints
  weakByUnit.value = wb
  reviewDue.value = rv || []
  await loadWords()
}

const wordCfg = reactive({
  enabled: false, new_per_day: 5, max_due: 10, base_sunshine: 3, perfect_sunshine: 2,
  unlock_by_cursor: true, current_book: '', tts: true, tts_autoplay: false, tts_lang: 'en-GB',
})
const wordBooks = ref([])
const wordToday = ref({ enabled: false, finished: true, backlog_due: 0, session: null })
const wordProblems = ref([])
const wordStats = ref({ days: [], completed_sessions: 0, first_try_rate: null })
const wordNewBook = ref('')
const wordImport = reactive({ book_id: '', text: '', result: null })
const wordOpenBook = ref(null)
const wordBusy = ref(false)
const wordOverview = computed(() => {
  const s = wordToday.value.session
  const counts = (s && s.counts) || { due: 0, new: 0, answered: 0, correct_first_try: 0 }
  const total = ((s && s.items) || []).length
  const left = ((s && s.items) || []).filter(x => x.state !== 'done').length
  return {
    newn: counts.new || 0,
    due: counts.due || 0,
    correct: counts.correct_first_try || 0,
    total,
    left: wordToday.value.finished ? 0 : (s ? left : (wordToday.value.enabled ? '—' : 0)),
    backlog: wordToday.value.backlog_due || 0,
    finished: !!wordToday.value.finished,
  }
})
async function loadWords() {
  if (!selectedKid.value) return
  try {
    const [cfg, today, problems, stats] = await Promise.all([
      api.admin.wordConfig(),
      api.wordsToday().catch(() => null),
      api.admin.problemWords().catch(() => []),
      api.admin.wordStats().catch(() => ({ days: [], completed_sessions: 0, first_try_rate: null })),
    ])
    Object.assign(wordCfg, {
      enabled: !!cfg.enabled,
      new_per_day: cfg.new_per_day,
      max_due: cfg.max_due,
      base_sunshine: cfg.base_sunshine,
      perfect_sunshine: cfg.perfect_sunshine,
      unlock_by_cursor: cfg.unlock_by_cursor !== false,
      current_book: cfg.current_book || '',
      tts: cfg.tts !== false,
      tts_autoplay: !!cfg.tts_autoplay,
      tts_lang: cfg.tts_lang === 'en-US' ? 'en-US' : 'en-GB',
    })
    wordBooks.value = cfg.books || []
    wordToday.value = today || { enabled: false, finished: true, backlog_due: 0, session: null }
    wordProblems.value = problems || []
    wordStats.value = stats || { days: [], completed_sessions: 0, first_try_rate: null }
  } catch (e) { showToast(e.message) }
}
async function saveWordNow(patch) {
  try {
    const cfg = await api.admin.setWordConfig(patch)
    Object.assign(wordCfg, {
      enabled: !!cfg.enabled,
      current_book: cfg.current_book || '',
      tts: cfg.tts !== false,
      tts_autoplay: !!cfg.tts_autoplay,
      tts_lang: cfg.tts_lang === 'en-US' ? 'en-US' : 'en-GB',
      unlock_by_cursor: cfg.unlock_by_cursor !== false,
    })
    wordBooks.value = cfg.books || []
    await loadWords()
  } catch (e) { showToast(e.message); await loadWords() }
}
async function saveWordRhythm() {
  try {
    await api.admin.setWordConfig({
      new_per_day: wordCfg.new_per_day,
      max_due: wordCfg.max_due,
      base_sunshine: wordCfg.base_sunshine,
      perfect_sunshine: wordCfg.perfect_sunshine,
    })
    showToast('已保存，明天的新练习才按这个来')
  } catch (e) { showToast(e.message) }
}
async function addWordBook() {
  const name = wordNewBook.value.trim()
  if (!name) return showToast('填词书名字')
  try {
    await api.admin.createWordBook({ name })
    wordNewBook.value = ''
    showToast('已建家庭词书')
    await loadWords()
  } catch (e) { showToast(e.message) }
}
async function saveWordBook(b) {
  try {
    await api.admin.updateWordBook(b.id, { name: b.name })
    showToast('已改名')
    await loadWords()
  } catch (e) { showToast(e.message) }
}
async function delWordBook(b) {
  if (!confirm('关掉这本家庭词书？')) return
  try {
    await api.admin.delWordBook(b.id)
    if (wordImport.book_id === b.id) wordImport.book_id = ''
    showToast('已处理')
    await loadWords()
  } catch (e) { showToast(e.message) }
}
async function importWordBook() {
  if (!wordImport.book_id) return showToast('先选一本家庭词书')
  if (!wordImport.text.trim()) return showToast('粘贴单词')
  wordBusy.value = true
  try {
    wordImport.result = await api.admin.importWords(wordImport.book_id, wordImport.text)
    showToast('导入 ' + wordImport.result.ok + ' 个')
    await loadWords()
  } catch (e) { showToast(e.message) }
  finally { wordBusy.value = false }
}
async function openWordBook(id) {
  try {
    wordOpenBook.value = await api.admin.wordBook(id)
  } catch (e) { showToast(e.message) }
}
async function focusWord(id) {
  try {
    await api.admin.focusWord(id)
    showToast('明天会练到')
    await loadWords()
  } catch (e) { showToast(e.message) }
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
const newTask = reactive({ subject_id: '', unit_id: '', action: '', title: '', sunshine: 5, kid_id: '' })
const unitOptions = computed(() => units.value.filter(u => u.subject_id === newTask.subject_id && u.term_id === activeTerm.value))
const testUnitOptions = computed(() => units.value.filter(u => u.subject_id === newTest.subject_id && u.term_id === activeTerm.value))
function pickSubject() { newTask.unit_id = '' }
async function addTask() {
  if (!newTask.subject_id || !newTask.unit_id || !newTask.title) return showToast('选科目/单元、填标题')
  await api.admin.createTask({ ...newTask, kid_id: newTask.kid_id || null })
  Object.assign(newTask, { subject_id: '', unit_id: '', action: '', title: '', sunshine: 5, kid_id: '' })
  showToast('已新增'); await load()
}
async function saveTask(t) { await api.admin.updateTask(t.id, { ...t, kid_id: t.kid_id || null }); showToast('已保存') }
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
const termUnits = computed(() => units.value.filter(u => u.term_id === activeTerm.value || (u.id || '').startsWith(activeTerm.value)))
const cursorSubjects = computed(() => {
  const unitIds = new Set(termUnits.value.map(u => u.id))
  const ids = new Set(tasks.value.filter(t => unitIds.has(t.unit_id)).map(t => t.subject_id))
  return subjects.value.filter(s => ids.has(s.id))
})
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
function tagsFor(uid) {
  // 自动标签只是未精标课程的内部占位，不能当作家长可判断的薄弱考点。
  return (catalog.value.unit_tags || []).filter(x => x.unit_id === uid).map(x => ({ ...x, ...tagFor(x.tag_id) })).filter(x => x.name && !x.auto)
}
function hasAutoTags(uid) {
  return (catalog.value.unit_tags || []).some(x => x.unit_id === uid && x.auto)
}
function tagOn(uid, tid) { return !!(weakByUnit.value[uid] && weakByUnit.value[uid][tid]) }
function weakTagCount(uid) { return Object.keys(weakByUnit.value[uid] || {}).length }
function weakPointTiming(x) {
  if (!x.review_due_at) return '等待安排'
  if (x.review_due_at <= new Date().toISOString().slice(0, 10)) return '今天要复习'
  const [, month, day] = x.review_due_at.split('-')
  return `下次：${Number(month)}月${Number(day)}日`
}
async function toggleTag(uid, tid) {
  const prev = { ...(weakByUnit.value[uid] || {}) }
  const cur = { ...prev }
  if (cur[tid]) delete cur[tid]
  else cur[tid] = true
  weakByUnit.value = { ...weakByUnit.value, [uid]: cur }
  try {
    const rows = await api.admin.setWeakPoints({ unit_id: uid, tag_ids: Object.keys(cur), kid_id: selectedKid.value, first_review: firstReview.value })
    const other = weakPoints.value.filter(x => x.unit_id !== uid)
    weakPoints.value = [...other, ...rows]
    reviewDue.value = await api.admin.reviewDue()
    showToast(cur[tid] ? '已加入今天复习' : '已取消记录')
  } catch (e) {
    weakByUnit.value = { ...weakByUnit.value, [uid]: prev }
    showToast(e.message)
  }
}

// —— 每日任务 ——
const DIRS = [['higher_better', '越多越好'], ['lower_better', '越少越好']]
const newDaily = reactive({ subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, note: '', metrics: [] })
const orderedDaily = computed(() => [...daily.value].sort((a, b) => Number(b.family_id != null) - Number(a.family_id != null)))
function addMetric(arr) { arr.push({ id: 'm' + Date.now(), label: '', unit: '', direction: 'higher_better', note: '' }) }
const cleanMetrics = (ms) => (ms || []).map(({ id, label, unit, direction, note }) => ({ id, label, unit, direction, note }))
async function addDaily() {
  if (!newDaily.name) return showToast('填任务名')
  await api.admin.createDaily({ ...newDaily, metrics: cleanMetrics(newDaily.metrics) })
  Object.assign(newDaily, { subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, note: '', metrics: [] })
  showToast('已新增'); await load()
}
async function saveDaily(d) {
  await api.admin.updateDaily(d.id, { subject_id: d.subject_id, name: d.name, sunshine: d.sunshine, bonus_per_metric: d.bonus_per_metric, note: d.note, metrics: cleanMetrics(d.metrics) })
  showToast('已保存')
}
async function delDaily(id) { if (!confirm('删除这个每日任务？')) return; await api.admin.delDaily(id); await load() }

// —— 密码 / 游标 ——
const pinForm = reactive({ cur: '', next: '', confirm: '' })
async function setCursor(subj, taskId) {
  try {
    await api.admin.setCursor({ subject_id: subj, task_id: taskId })
    cursors.value = { ...cursors.value, [subj]: taskId }
    showToast('已更新「已学到」')
  } catch (e) { showToast(e.message) }
}

async function switchKid() {
  setSelectedKid(selectedKid.value)
  reviewSubject.value = ''
  emit('switched')
  await load()
}
async function pickKid(id) {
  selectedKid.value = id
  await switchKid()
}

async function addKid() {
  if (!newKid.name) return showToast('填名字')
  if (!(newKid.account || '').trim()) return showToast('填登录账号')
  if (!(newKid.pin || '').trim()) return showToast('设一个密码，至少 6 位')
  try {
    await api.admin.createKid({ ...newKid })
    newKid.name = newKid.account = newKid.pin = newKid.pin2 = ''
    newKid.gender = ''
    showToast('已添加')
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
    showToast('奖励标准已保存')
  } catch (e) { showToast(e.message) }
}
async function resetTestBands() {
  testBands.value = DEFAULT_TEST_BANDS.map(x => [...x])
  await saveTestBands()
}
function testBandRange(i) {
  const low = Number(testBands.value[i][0])
  const high = i === 0 ? 100 : Number(testBands.value[i - 1][0]) - 1
  return low === high ? `${low} 分` : `${low}～${high} 分`
}
const reviewSubject = ref('')
const reviewSubjects = computed(() => {
  const ids = [...new Set((reviewDue.value || []).map(x => x.subject_id).filter(Boolean))]
  return ids
})
const filteredReviewDue = computed(() => {
  const rows = reviewDue.value || []
  return reviewSubject.value ? rows.filter(x => x.subject_id === reviewSubject.value) : rows
})
const testPreview = computed(() => {
  const sc = Number(newTest.score)
  if (newTest.score === '' || newTest.score === null || Number.isNaN(sc) || sc < 0 || sc > 100) return null
  const bands = testBands.value || []
  for (let i = 0; i < bands.length; i++) {
    if (sc >= Number(bands[i][0])) return { range: testBandRange(i), sun: Number(bands[i][1]) }
  }
  return { range: '', sun: 0 }
})
function familyTodayStatus(k) {
  if (k.review_due > 0) return { cls: 'amber', text: '今日复习 ' + k.review_due + ' 项' }
  if (!k.checkin) return { cls: 'gray', text: '还没来' }
  return { cls: 'green', text: '今天来了' }
}
const familyTodayEmpty = computed(() => {
  const ks = familyToday.value.kids || []
  if (!ks.length) return ''
  if (ks.some(k => k.review_due > 0 || !k.checkin)) return ''
  return ks.length === 1 ? '今天来了，没有到期复习。' : '今天都来了，没有到期复习。'
})
function goReviewKid(k) {
  selectedKid.value = k.kid_id
  setSelectedKid(k.kid_id)
  section.value = 'review'
  load()
}
function completedDelta(k) {
  const d = (k.completed || 0) - (k.completed_last || 0)
  if (d > 0) return '比上周多 ' + d + ' 张'
  if (d < 0) return '比上周少 ' + (-d) + ' 张'
  return '和上周差不多'
}
const masteredLine = computed(() => {
  const rows = weekly.value.mastered_by_kid || []
  if (!rows.length) return ''
  return rows.map(r => r.name + '：' + (r.items || []).join('、')).join('；')
})
const currentKidName = computed(() => kids.value.find(k => k.id === selectedKid.value)?.name || '')
const greet = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '上午好'
  if (h < 18) return '下午好'
  return '晚上好'
})
const pendingRedeem = computed(() => (redemptions.value || []).filter(r => r.status === 'pending').length)
const reviewCount = computed(() => (reviewDue.value || []).length)
const checkinCount = computed(() => (familyToday.value.kids || []).filter(k => k.checkin).length)
const kidCount = computed(() => (familyToday.value.kids || []).length)
const isMultiKid = computed(() => kids.value.length > 1)
const dashAttention = computed(() => {
  if (reviewCount.value) return { text: `今天有 ${reviewCount.value} 项复习到期`, go: 'review', label: '去复习' }
  if (pendingRedeem.value) return { text: `有 ${pendingRedeem.value} 笔兑换待同意`, go: 'approve', label: '去审批' }
  return { text: '', go: '', label: '' }
})
function n1(v) {
  if (v == null || v === '') return ''
  const x = Math.round(Number(v) * 10) / 10
  return x % 1 ? String(x) : String(Math.round(x))
}
function lastMetric(d, mid) {
  if (d.today_metrics && d.today_metrics[mid] != null && d.today_metrics[mid] !== '') return Number(d.today_metrics[mid])
  const hist = dailyHist.value[d.id] || []
  for (let i = hist.length - 1; i >= 0; i--) {
    const v = hist[i].metrics && hist[i].metrics[mid]
    if (v != null && v !== '') return Number(v)
  }
  if (d.pb && d.pb[mid] != null) return Number(d.pb[mid])
  return null
}
function metricLine(series) {
  if (!series.length) return ''
  const vals = series.map(s => s.v)
  const min = Math.min(...vals), max = Math.max(...vals)
  const span = (max - min) || 1
  const W = 288, H = 56, pad = 8
  return series.map((s, i) => {
    const x = series.length === 1 ? W / 2 : pad + i * (W - 2 * pad) / (series.length - 1)
    const y = H - pad - (s.v - min) / span * (H - 2 * pad)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}
const dashDailies = computed(() => (daily.value || []).map(d => ({
  id: d.id, name: d.name, subject: d.subject_id || '', done: !!d.done_today,
})))
const peCards = computed(() => {
  const cards = []
  for (const d of daily.value || []) {
    const metrics = d.metrics || []
    if (!metrics.length) continue
    const g = fitnessGoals.value[d.id]
    if (!g) continue
    const hist = dailyHist.value[d.id] || []
    for (const m of metrics) {
      if (g.metric_id && m.id !== g.metric_id) continue
      const series = hist
        .filter(h => h.metrics && h.metrics[m.id] != null && h.metrics[m.id] !== '')
        .map(h => ({ date: h.date, v: Number(h.metrics[m.id]) }))
      const last = lastMetric(d, m.id)
      const pb = d.pb ? d.pb[m.id] : null
      const unit = m.unit || (g && g.metric_id === m.id ? g.unit : '') || ''
      let status = '还没记过'
      let cls = 'gray'
      let gap = ''
      let pct = 0
      const goal = g && g.metric_id === m.id ? g : null
      if (goal && last != null) {
        const cap = goal.excellent || goal.pass
        pct = Math.max(0, Math.min(100, Math.round(last / cap * 100)))
        if (goal.excellent != null && last >= goal.excellent) { status = '优秀'; cls = 'green' }
        else if (last >= goal.pass) { status = '达标'; cls = 'green' }
        else { status = '未达标'; cls = 'amber'; gap = `还差 ${n1(goal.pass - last)}${unit}` }
      } else if (last != null) {
        status = '有记录'; cls = 'green'
      }
      cards.push({
        key: d.id + '-' + m.id,
        name: d.name,
        label: m.label || (goal && goal.item) || m.id,
        unit, last, pb, status, cls, gap, pct, goal, series,
        pts: metricLine(series),
        today: !!(d.today_metrics && d.today_metrics[m.id] != null),
      })
    }
  }
  return cards
})
const penaltyReasonRows = computed(() => (penaltySummary.value.by_reason || []).filter(x => x.count > 0))
const maxPenaltyAmount = computed(() => Math.max(1, ...penaltyReasonRows.value.map(x => x.amount || 0)))
function goInsight(row) {
  const a = row.insight?.action
  if (row.kid_id) {
    selectedKid.value = row.kid_id
    setSelectedKid(row.kid_id)
  }
  if (a === '单元测试') section.value = 'test'
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
async function toggleProtect(e) {
  try {
    await api.admin.setInviteProtect(e.target.checked)
    inviteProtect.value = e.target.checked
    showToast(e.target.checked ? '邀请码保护已开（一次性 + 24h）' : '邀请码保护已关（常驻复用）')
  } catch (err) { showToast(err.message); e.target.checked = inviteProtect.value }
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
  if (!confirm('撤回这笔扣分？阳光会加回去，等级不变。')) return
  try {
    await api.admin.cancelPenalty(id)
    showToast('已撤回')
    await load()
  } catch (e) { showToast(e.message) }
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
        <button class="a-exit" @click="emit('exit')"><ArrowLeft class="ico" :size="14" /> 回到孩子端</button>
      </div>
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

    <!-- 今日复习 -->
    <section v-if="section === 'review'" class="a-card enter">
      <h3>今天复习 <span class="review-total">{{ reviewDue.length }} 项</span></h3>
      <div v-if="reviewDue.length && reviewSubjects.length > 1" class="subj-tabs review-filter">
        <button type="button" :class="['subj-tab', { on: !reviewSubject }]" @click="reviewSubject = ''">全部</button>
        <button v-for="sid in reviewSubjects" :key="sid" type="button"
          :class="['subj-tab', { on: reviewSubject === sid }]" @click="reviewSubject = sid">{{ subjectName(sid) }}</button>
      </div>
      <div v-if="!reviewDue.length && !weakPoints.length" class="review-empty">
        <strong>没有薄弱考点</strong>
        <button class="ghost-s review-link" @click="section = 'unit-task'">去记录 →</button>
      </div>
      <div v-else-if="!reviewDue.length" class="review-empty">
        <strong>今天没有到期复习</strong>
      </div>
      <div v-else-if="!filteredReviewDue.length" class="review-empty">
        <strong>这一科今天没有复习</strong>
      </div>
      <div v-for="x in filteredReviewDue" :key="x.id" class="review-item">
        <div class="review-item-info">
          <span class="review-item-title">{{ x.tag_name }}</span>
          <span class="dim">{{ x.subject_id }} · {{ x.unit_name }} · 第 {{ (x.interval_idx || 0) + 1 }} 次复习</span>
        </div>
        <div class="review-actions">
          <button class="ok" @click="judge(x.id, 'pass')">会了</button>
          <button class="del" @click="judge(x.id, 'fail')">还不熟</button>
          <button class="ok ghost-o" @click="judge(x.id, 'done')">已掌握</button>
        </div>
      </div>

      <div v-if="weakPoints.length" class="review-recorded">
        <h4>已记录的薄弱考点</h4>
        <div v-for="x in weakPoints" :key="x.id" class="review-recorded-row">
          <div>
            <strong>{{ x.tag_name }}</strong>
            <span>{{ x.subject_id }} · {{ x.unit_name }}</span>
          </div>
          <em :class="{ due: reviewDue.some(r => r.id === x.id) }">{{ weakPointTiming(x) }}</em>
        </div>
      </div>
    </section>

    <!-- 概览：全家今日 + 本周盯点 -->
    <section v-if="section === 'insights'" class="a-card enter dash">
      <h3>{{ greet }}，{{ me.name || '家长' }}</h3>
      <div v-if="dashAttention.text" class="w-next">
        <strong>待处理</strong>
        <span>{{ dashAttention.text }}</span>
        <button v-if="dashAttention.go" class="ok" @click="section = dashAttention.go">{{ dashAttention.label }}</button>
      </div>
      <div class="dash-stats">
        <button type="button" class="dash-stat" @click="section = 'review'">
          <span>待复习</span><b>{{ reviewCount }}</b>
        </button>
        <button type="button" class="dash-stat" @click="section = 'approve'">
          <span>待审批</span><b>{{ pendingRedeem }}</b>
        </button>
        <div class="dash-stat">
          <span>今日签到</span><b>{{ isMultiKid ? (checkinCount + '/' + kidCount) : (checkinCount ? '已来' : (kidCount ? '还没来' : '—')) }}</b>
        </div>
        <div class="dash-stat">
          <span>连击</span><b>{{ weekly.streak || 0 }} 天</b>
        </div>
      </div>
      <template v-if="dashDailies.length">
        <h4 class="w-h">今日打卡</h4>
        <div class="dash-dailies">
          <div v-for="d in dashDailies" :key="d.id" class="dash-daily" :class="{ on: d.done }">
            <span class="apv-name">{{ d.name }}</span>
            <em class="fam-st" :class="d.done ? 'green' : 'gray'">{{ d.done ? '已打卡' : '还没做' }}</em>
            <span class="dim">{{ d.subject }}</span>
          </div>
        </div>
      </template>
      <template v-if="peCards.length">
        <h4 class="w-h">体测数值</h4>
        <div class="pe-grid">
          <div v-for="c in peCards" :key="c.key" class="pe-card">
            <span class="dim">{{ c.name }}</span>
            <strong>{{ c.label }}</strong>
            <b>{{ c.last == null ? '—' : n1(c.last) }}<small>{{ c.unit }}</small></b>
            <em class="fam-st" :class="c.cls">{{ c.gap || c.status }}{{ c.today ? ' · 今天记的' : '' }}</em>
            <div v-if="c.goal" class="w-subj-row pe-std">
              <div class="w-subj-track"><i :style="{ width: c.pct + '%' }"></i></div>
              <span class="w-subj-num">达标 {{ n1(c.goal.pass) }}{{ c.unit }}</span>
            </div>
            <span class="dim">个人最好 {{ c.pb == null ? '—' : n1(c.pb) }}{{ c.unit }}{{ c.series.length ? ' · ' + c.series.length + ' 次' : '' }}</span>
            <svg v-if="c.pts" viewBox="0 0 288 56" class="pe-svg" preserveAspectRatio="none">
              <polyline :points="c.pts" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
        </div>
      </template>
      <h4 class="w-h">本周阳光{{ currentKidName ? ' · ' + currentKidName : '' }}</h4>
      <p class="lead dim">{{ weekly.week_start }} ~ {{ weekly.week_end }}</p>
      <div class="w-summary">
        <div class="w-box"><span>本周赚</span><b>+{{ weekly.total_earned }}</b></div>
        <div class="w-box"><span>兑换花</span><b>-{{ weekly.total_spent }}</b></div>
        <div v-if="weekly.penalty_net" class="w-box"><span>本周约定</span><b>{{ weekly.penalty_net }}</b></div>
        <div class="w-box"><span>净增</span><b>{{ weekly.net }}</b></div>
        <div class="w-box"><span>当前余额</span><b>{{ weekly.balance }}</b></div>
        <div class="w-box"><span>本周签到</span><b>{{ weekly.checkins }} 天</b></div>
      </div>
      <div v-if="masteredLine" class="w-mastered">本周已掌握：<b>{{ masteredLine }}</b></div>
      <div v-if="isMultiKid && (weekly.kids || []).length" class="w-kids">
        <div v-for="k in weekly.kids" :key="k.id" class="w-box" :class="{ on: k.current }" @click="pickKid(k.id)">
          <span>{{ k.name }}</span><b>+{{ k.earned }}</b>
          <i class="dim">完成 {{ k.completed || 0 }} 张 · {{ completedDelta(k) }}</i>
          <i class="dim">花 {{ k.spent }} · 连击 {{ k.streak }}</i>
        </div>
      </div>
      <div class="dash-charts">
        <div class="dash-chart">
          <h4 class="w-h">近 4 周净增</h4>
          <div class="w-trend">
            <svg viewBox="0 0 288 80" class="w-trend-svg" preserveAspectRatio="none">
              <polyline :points="weekPoints" fill="none" stroke="var(--brand)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <div class="w-trend-labels">
              <span v-for="w in weekly.weeks" :key="w.week_start">{{ w.label }}<i>{{ weekNet(w) > 0 ? '+' : '' }}{{ weekNet(w) }}</i></span>
            </div>
          </div>
        </div>
        <div class="dash-chart">
          <h4 class="w-h">本周每天净增</h4>
          <div class="w-chart dash-bars">
            <div v-for="d in weekly.days" :key="d.date" class="w-bar-col">
              <div class="w-bar" :class="{ down: dayNet(d) < 0 }" :style="{ height: (Math.abs(dayNet(d)) / maxDayEarn * 100) + '%' }">
                <i v-if="dayNet(d)">{{ dayNet(d) > 0 ? '+' : '' }}{{ dayNet(d) }}</i>
              </div>
              <span>周{{ d.weekday }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="weekly.by_subject && weekly.by_subject.length" class="dash-chart">
        <h4 class="w-h">本周各科</h4>
        <div class="w-subj">
          <div v-for="s in subjectRows" :key="s.name" class="w-subj-row">
            <span class="w-subj-name">{{ s.name }}</span>
            <div class="w-subj-track"><i :style="{ width: ((s.sun || 0) / maxSubj * 100) + '%' }"></i></div>
            <span class="w-subj-num">+{{ s.sun }}</span>
          </div>
        </div>
      </div>
      <template v-if="isMultiKid && kidCount">
        <h4 class="w-h">孩子们</h4>
        <div class="fam-today">
          <button v-for="k in familyToday.kids" :key="k.kid_id" type="button"
            class="fam-card" :class="{ on: selectedKid === k.kid_id }" @click="pickKid(k.kid_id)">
            <span class="apv-name">{{ k.name }}</span>
            <em class="fam-st" :class="familyTodayStatus(k).cls">{{ familyTodayStatus(k).text }}</em>
            <span class="dim">完成 {{ k.completed_today }} · 连击 {{ k.streak }} · 余额 {{ k.balance }}</span>
            <span v-if="k.review_due > 0" class="ok fam-go" @click.stop="goReviewKid(k)">去复习</span>
          </button>
        </div>
      </template>
      <p v-else-if="!kidCount" class="dim">还没有孩子，到「家庭」里添加。</p>
      <template v-if="(insights.kids || []).length">
        <h4 class="w-h">本周盯点</h4>
        <div v-for="row in insights.kids" :key="row.kid_id" class="apv-row">
          <div class="apv-info">
            <span v-if="isMultiKid" class="apv-name">{{ row.name }}</span>
            <span class="dim">{{ row.insight ? row.insight.text : '无' }}</span>
          </div>
          <button v-if="row.insight && row.insight.action" class="ok" @click="goInsight(row)">去解决</button>
        </div>
      </template>
      <button type="button" class="ghost-s rules-toggle" @click="rulesOpen = !rulesOpen">{{ rulesOpen ? '收起诊断阈值' : '诊断阈值' }}</button>
      <template v-if="rulesOpen">
      <div class="a-item">
        <span class="dim">连续低分次数</span>
        <input class="w-num" type="number" :value="insights.rules.test_fail_count" @change="saveRule('test_fail_count', +$event.target.value)" />
        <button class="ghost" @click="resetRule('test_fail_count')">默认</button>
      </div>
      <div class="a-item">
        <span class="dim">低于多少分算低</span>
        <input class="w-num" type="number" :value="insights.rules.test_fail_score" @change="saveRule('test_fail_score', +$event.target.value)" />
        <button class="ghost" @click="resetRule('test_fail_score')">默认</button>
      </div>
      <div class="a-item">
        <span class="dim">完成量少几成算下滑</span>
        <input class="w-num" type="number" step="0.1" :value="insights.rules.drop_ratio" @change="saveRule('drop_ratio', +$event.target.value)" />
        <button class="ghost" @click="resetRule('drop_ratio')">默认</button>
      </div>
      <div class="a-item">
        <span class="dim">连击断几天再提</span>
        <input class="w-num" type="number" :value="insights.rules.streak_break" @change="saveRule('streak_break', +$event.target.value)" />
        <button class="ghost" @click="resetRule('streak_break')">默认</button>
      </div>
      </template>
    </section>

    <!-- 商店 -->
    <section v-if="section === 'shop'" class="a-card enter">
      <h3>兑换商店</h3>
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

    <!-- 扣分 -->
    <section v-if="section === 'penalty'" class="a-card enter">
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
            <span class="apv-name">{{ p.note || '扣分' }}</span>
            <span class="dim">{{ p.date }}</span>
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
    <section v-if="section === 'approve'" class="a-card enter">
      <h3>兑换审批与兑现</h3>
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
      <h3>成长等级</h3>
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
      <h3>任务与考点</h3>
      <div class="add-box task-add-box">
        <div class="add-title">新增家长任务</div>
        <div class="frm-row">
          <label class="fld grow"><span>哪一科</span>
            <select v-model="newTask.subject_id" @change="pickSubject">
              <option value="" disabled>先选科</option>
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ subjectName(s.id) }}</option>
            </select>
          </label>
          <label class="fld grow"><span>放在哪个单元</span>
            <select v-model="newTask.unit_id">
              <option value="" disabled>{{ newTask.subject_id ? '选单元' : '先选科' }}</option>
              <option v-for="u in unitOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>谁能看到</span>
            <select v-model="newTask.kid_id">
              <option value="">全家</option>
              <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
            </select>
          </label>
        </div>
        <div class="frm-row">
          <label class="fld grow"><span>任务名称</span><input v-model="newTask.title" placeholder="如：订正今天的错题" /></label>
          <label class="fld w84"><span>怎么做</span><input v-model="newTask.action" placeholder="读 / 写 / 练" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="newTask.sunshine" type="number" min="0" /></label>
        </div>
        <button class="ok wide" @click="addTask">＋新增任务</button>
      </div>

      <label class="fld review-date"><span>改成哪天开始复习</span>
        <input type="date" v-model="firstReview" />
      </label>
      <div class="subj-tabs">
        <button v-for="(arr, sid) in unitsBySubject" :key="sid" type="button"
          :class="['subj-tab', { on: activeSubject === sid }]"
          @click="activeSubject = sid">{{ subjectName(sid) }}</button>
      </div>
      <div v-for="(arr, sid) in unitsBySubject" :key="sid" class="subj" v-show="activeSubject === sid">
        <div v-for="u in arr" :key="u.id" class="unit-block">
          <div class="unit-h">{{ u.name }} <span v-if="weakTagCount(u.id)" class="unit-wp-count">已记录 {{ weakTagCount(u.id) }} 项</span></div>
          <div class="tag-guide-row">
            <button v-for="tg in tagsFor(u.id)" :key="tg.tag_id" type="button"
              :class="['tag-guide', { on: tagOn(u.id, tg.tag_id), auto: tg.auto }]"
              :aria-pressed="tagOn(u.id, tg.tag_id)"
              @click="toggleTag(u.id, tg.tag_id)">
              <span class="tag-guide-title">{{ tagOn(u.id, tg.tag_id) ? '✓ ' : '' }}{{ tg.name }}</span>
              <span class="tag-guide-help">{{ tagHelp(tg) }}</span>
              <span class="tag-guide-action">{{ tagOn(u.id, tg.tag_id) ? '已加入' : '加入复习' }}</span>
            </button>
            <span v-if="!tagsFor(u.id).length" class="dim">无考点</span>
          </div>
          <div class="task-row" v-for="t in (tasksBySubject[sid] || []).filter(x => x.unit_id === u.id)" :key="t.id">
            <template v-if="t.custom">
              <label class="fld grow"><span>家长任务名称</span><input v-model="t.title" /></label>
              <label class="fld w84"><span>怎么做</span><input v-model="t.action" /></label>
              <label class="fld w64"><span>阳光</span><input v-model.number="t.sunshine" type="number" min="0" /></label>
              <label class="fld w104"><span>谁能看到</span>
                <select v-model="t.kid_id">
                  <option value="">全家</option>
                  <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
                </select>
              </label>
              <div class="ops">
                <button class="ok" @click="saveTask(t)">保存</button>
                <button class="del" @click="delTask(t.id)">删</button>
              </div>
            </template>
            <template v-else>
              <span class="task-readonly-title">{{ t.title }}</span>
              <span class="badge">{{ t.action }}</span>
              <span class="dim">+{{ t.sunshine }} 阳光 · 教材任务</span>
            </template>
          </div>
        </div>
      </div>
    </section>

    <!-- 每日任务 -->
    <section v-if="section === 'daily'" class="a-card enter">
      <h3>每日任务</h3>
      <div class="add-box task-add-box">
        <div class="add-title">新增每日任务</div>
        <div class="frm-row">
          <label class="fld grow"><span>哪一科</span>
            <select v-model="newDaily.subject_id">
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>名称</span><input v-model="newDaily.name" placeholder="如：跳绳打卡" /></label>
          <label class="fld w64"><span>基础阳光</span><input v-model.number="newDaily.sunshine" type="number" /></label>
          <label class="fld w84"><span>破纪录 +</span><input v-model.number="newDaily.bonus_per_metric" type="number" /></label>
          <label class="fld grow"><span>怎么做</span><input v-model="newDaily.note" placeholder="如：完成后让家长检查" /></label>
        </div>
        <div class="m-row" v-for="(m, i) in newDaily.metrics" :key="m.id">
          <label class="fld grow"><span>指标名</span><input v-model="m.label" placeholder="如：跳绳个数" /></label>
          <label class="fld w84"><span>单位</span><input v-model="m.unit" placeholder="个" /></label>
          <label class="fld w104"><span>方向</span>
            <select v-model="m.direction">
              <option v-for="[v, n] in DIRS" :key="v" :value="v">{{ n }}</option>
            </select>
          </label>
          <label class="fld grow"><span>记录说明</span><input v-model="m.note" placeholder="如：只记完整正确的次数" /></label>
          <button class="del" @click="newDaily.metrics.splice(i, 1)">×</button>
        </div>
        <button class="ghost-s" @click="addMetric(newDaily.metrics)">＋加破纪录指标</button>
        <div class="mt10"><button class="ok wide" @click="addDaily">＋新增任务</button></div>
      </div>
      <div class="daily-card" v-for="d in orderedDaily" :key="d.id">
        <div v-if="d.family_id == null" class="sys-row">
          <span class="badge daily">每天</span>
          <span class="sys-name">{{ d.name }}</span>
          <span class="dim">+{{ d.sunshine }} 阳光 · 系统内置</span>
          <div v-if="d.note" class="daily-note">怎么做：{{ d.note }}</div>
        </div>
        <template v-else>
          <div class="dc-head">
            <span class="badge daily">每天</span>
            <label class="fld grow"><span>名称</span><input v-model="d.name" /></label>
            <label class="fld grow"><span>哪一科</span>
              <select v-model="d.subject_id">
                <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </label>
            <label class="fld w64"><span>基础阳光</span><input v-model.number="d.sunshine" type="number" /></label>
            <label class="fld w84"><span>破纪录 +</span><input v-model.number="d.bonus_per_metric" type="number" /></label>
            <label class="fld grow"><span>怎么做</span><input v-model="d.note" placeholder="如：完成后让家长检查" /></label>
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
              <label class="fld grow"><span>记录说明</span><input v-model="m.note" placeholder="如：只记完整正确的次数" /></label>
              <button class="del" @click="d.metrics.splice(i, 1)">×</button>
            </div>
          </div>
          <button class="ghost-s" @click="addMetric(d.metrics)">＋加破纪录指标</button>
        </template>
      </div>
    </section>

    <section v-if="section === 'words'" class="a-card enter">
      <h3>英语单词</h3>
      <p class="dim">给 {{ currentKidName || '当前孩子' }} 用。朗读马上生效；每天几个词、给多少阳光，明天新的一组才按这个来。</p>
      <div class="w-summary word-ov">
        <div class="w-box"><span>新词</span><b>{{ wordOverview.newn }}</b></div>
        <div class="w-box"><span>复习</span><b>{{ wordOverview.due }}</b></div>
        <div class="w-box"><span>首轮对</span><b>{{ wordOverview.correct }}/{{ wordOverview.total || 0 }}</b></div>
        <div class="w-box"><span>还没写完</span><b>{{ wordOverview.left }}</b></div>
        <div class="w-box"><span>积压到期</span><b>{{ wordOverview.backlog }}</b></div>
      </div>
      <div class="lock-row mt14">
        <span class="badge">单词练习</span>
        <span class="grow">孩子端显示今日单词</span>
        <button type="button" :class="['toggle', { on: wordCfg.enabled }]" @click="saveWordNow({ enabled: !wordCfg.enabled })">{{ wordCfg.enabled ? '开' : '关' }}</button>
      </div>
      <div class="frm-row mt14">
        <label class="fld grow"><span>当前新词词书</span>
          <select :value="wordCfg.current_book" @change="saveWordNow({ current_book: $event.target.value })">
            <option value="">还没选</option>
            <option v-for="b in wordBooks" :key="b.id" :value="b.id" :disabled="b.is_system && !b.selectable">
              {{ b.name }}{{ b.is_system ? ' · 系统' : ' · 家庭' }}{{ b.is_system && !b.selectable ? '（先设英语已学到）' : '' }}
            </option>
          </select>
        </label>
      </div>
      <div class="frm-row">
        <label class="fld w64"><span>每天新词</span><input v-model.number="wordCfg.new_per_day" type="number" min="1" max="10" /></label>
        <label class="fld w64"><span>到期上限</span><input v-model.number="wordCfg.max_due" type="number" min="5" max="15" /></label>
        <label class="fld w64"><span>完成阳光</span><input v-model.number="wordCfg.base_sunshine" type="number" min="0" max="10" /></label>
        <label class="fld w64"><span>全对阳光</span><input v-model.number="wordCfg.perfect_sunshine" type="number" min="0" max="5" /></label>
        <button class="ok" @click="saveWordRhythm">保存节奏</button>
      </div>
      <div class="lock-row mt14">
        <span class="badge">词书锁</span>
        <span class="grow">系统词书跟着英语「已学到」</span>
        <button type="button" :class="['toggle', { on: wordCfg.unlock_by_cursor }]" @click="saveWordNow({ unlock_by_cursor: !wordCfg.unlock_by_cursor })">{{ wordCfg.unlock_by_cursor ? '开' : '关' }}</button>
      </div>
      <div class="lock-row">
        <span class="badge">朗读</span>
        <span class="grow">看词页听读音</span>
        <button type="button" :class="['toggle', { on: wordCfg.tts }]" @click="saveWordNow({ tts: !wordCfg.tts })">{{ wordCfg.tts ? '开' : '关' }}</button>
      </div>
      <div class="lock-row">
        <span class="badge">自动读</span>
        <span class="grow">进入看词页读一次（默写不出声）</span>
        <button type="button" :class="['toggle', { on: wordCfg.tts_autoplay }]" @click="saveWordNow({ tts_autoplay: !wordCfg.tts_autoplay })">{{ wordCfg.tts_autoplay ? '开' : '关' }}</button>
      </div>
      <div class="frm-row">
        <label class="fld w104"><span>口音</span>
          <select :value="wordCfg.tts_lang" @change="saveWordNow({ tts_lang: $event.target.value })">
            <option value="en-GB">英式</option>
            <option value="en-US">美式</option>
          </select>
        </label>
      </div>

      <h4 class="w-h">词书</h4>
      <div class="word-book" v-for="b in wordBooks" :key="b.id">
        <div class="word-book-h">
          <strong>{{ b.name }}</strong>
          <span class="badge">{{ b.is_system ? '系统' : '家庭' }}</span>
          <span class="dim">{{ b.word_count }} 词 · 已学 {{ b.learned_count }} · 到期 {{ b.due_count }}</span>
          <button class="ghost-s" @click="openWordBook(b.id)">看词</button>
        </div>
        <template v-if="!b.is_system">
          <div class="frm-row">
            <label class="fld grow"><span>名字</span><input v-model="b.name" /></label>
            <button class="ok" @click="saveWordBook(b)">改名</button>
            <button class="del" @click="delWordBook(b)">删</button>
          </div>
        </template>
        <p v-else class="dim">系统词书只能改代码里的词表，家长不能改。</p>
      </div>
      <div class="frm-row">
        <label class="fld grow"><span>新建家庭词书</span><input v-model="wordNewBook" placeholder="如：课外词" maxlength="30" /></label>
        <button class="ok" @click="addWordBook">＋新建</button>
      </div>
      <div class="add-box mt14">
        <div class="add-title">导入家庭词书</div>
        <label class="fld grow"><span>导入到</span>
          <select v-model="wordImport.book_id">
            <option value="">选一本家庭词书</option>
            <option v-for="b in wordBooks.filter(x => !x.is_system)" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </label>
        <textarea v-model="wordImport.text" class="word-import" rows="5" placeholder="always	总是	/ˈɔːlweɪz/&#10;get up	起床"></textarea>
        <button class="ok" :disabled="wordBusy" @click="importWordBook">导入</button>
        <p v-if="wordImport.result" class="dim">成功 {{ wordImport.result.ok }} 行<template v-if="(wordImport.result.errors || []).length"> · {{ wordImport.result.errors.length }} 行有问题</template></p>
        <ul v-if="wordImport.result && wordImport.result.errors && wordImport.result.errors.length" class="word-err">
          <li v-for="e in wordImport.result.errors.slice(0, 8)" :key="e.line">第 {{ e.line }} 行：{{ e.error }}</li>
        </ul>
      </div>
      <div v-if="wordOpenBook" class="word-list">
        <h4 class="w-h">{{ wordOpenBook.name }} 的词</h4>
        <div v-for="w in (wordOpenBook.words || []).filter(x => x.active !== 0)" :key="w.id" class="word-row">
          <b>{{ w.word }}</b>
          <span>{{ w.cn }}</span>
          <em>{{ w.ipa }}</em>
        </div>
        <button class="ghost-s" @click="wordOpenBook = null">收起</button>
      </div>

      <h4 class="w-h">高频错词</h4>
      <p v-if="!wordProblems.length" class="dim">还没有错两次以上的词。</p>
      <div v-for="w in wordProblems" :key="w.word_id" class="word-row">
        <div>
          <b>{{ w.word }}</b>
          <span>{{ w.cn }} · 错 {{ w.wrong_count }} 次 · {{ w.book_name }}</span>
          <em>{{ w.due_at ? ('下次 ' + w.due_at) : '' }}</em>
        </div>
        <button class="ok" @click="focusWord(w.word_id)">明天重点练</button>
      </div>

      <h4 class="w-h">近 7 日</h4>
      <p class="dim">完成 {{ wordStats.completed_sessions || 0 }} 次<template v-if="wordStats.first_try_rate != null"> · 首轮正确率 {{ wordStats.first_try_rate }}%</template></p>
      <div class="w-chart word-week">
        <div v-for="d in wordStats.days || []" :key="d.date" class="w-bar-col">
          <div class="w-bar" :style="{ height: (d.completed ? 70 : 4) + '%' }"><i v-if="d.rate != null">{{ d.rate }}%</i></div>
          <span>{{ d.label }}</span>
        </div>
      </div>
    </section>

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
      <div class="lock-row mt14">
        <span class="badge">进度锁</span>
        <span class="grow">只让打「当前单元」</span>
        <button :class="['toggle', { on: progressLock }]" @click="toggleLock">{{ progressLock ? '开' : '关' }}</button>
      </div>

    </section>

    <!-- 单元测试成绩 -->
    <section v-if="section === 'test'" class="a-card enter">
      <h3>单元测试</h3>
      <div class="test-band-editor">
        <div class="add-title">成绩对应阳光</div>
        <div class="test-band-head"><span>分数区间</span><span>发放阳光</span></div>
        <div class="band-edit" v-for="(band, i) in testBands" :key="i">
          <span class="band-range">{{ testBandRange(i) }}</span>
          <label class="fld band-threshold"><span>本档最低分</span><input v-model.number="band[0]" type="number" min="0" max="100" :disabled="i === testBands.length - 1" /></label>
          <span class="band-arrow">→</span>
          <label class="fld band-sun"><span>阳光</span><input v-model.number="band[1]" type="number" min="0" /></label>
          <Sun class="ico sun" :size="14" />
        </div>
        <div class="band-actions">
          <button class="ok" @click="saveTestBands">保存设置</button>
          <button class="ghost-s" @click="resetTestBands">恢复默认</button>
        </div>
      </div>
      <div class="add-box">
        <div class="add-title">录入成绩</div>
        <div class="frm-row">
          <label class="fld grow"><span>哪一科</span>
            <select v-model="newTest.subject_id" @change="newTest.unit_id = ''">
              <option value="" disabled>先选科</option>
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>哪一单元（可空）</span>
            <select v-model="newTest.unit_id">
              <option value="">不绑单元</option>
              <option v-for="u in testUnitOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
          </label>
          <label class="fld w84"><span>分数</span><input v-model="newTest.score" type="number" placeholder="0~100" /></label>
          <label class="fld w104"><span>备注</span><input v-model="newTest.note" placeholder="如：期中" /></label>
        </div>
        <p v-if="testPreview" class="test-preview">命中 {{ testPreview.range }}，将发 {{ testPreview.sun }} 阳光。</p>

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

    <section v-if="section === 'kids'" class="a-card">
      <h3>孩子账号</h3>
      <p v-if="!terms.length" class="dim">学期列表还没载入，退出再进一次家长端。</p>
      <div class="kid-card" v-for="k in kids" :key="k.id">
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
          <button v-if="isOwner" class="del" @click="delKid(k)">删除账号</button>
          <span v-else class="dim">只有创建者能删除孩子</span>
        </div>
      </div>
      <div class="add-box">
        <div class="add-title">再加一个孩子</div>
        <div class="frm-row">
          <label class="fld grow"><span>家里怎么叫</span><input v-model="newKid.name" placeholder="如：弟弟" /></label>
          <label class="fld grow"><span>登录账号</span><input v-model="newKid.account" placeholder="如：didi" /></label>
          <label class="fld grow"><span>密码</span><input v-model="newKid.pin" type="password" autocomplete="new-password" placeholder="至少 6 位，不要重复或连续数字" /></label>
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
    <section v-if="section === 'members'" class="a-card enter">
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
    <section v-if="section === 'invites'" class="a-card enter">
      <h3>邀请码</h3>
      <label class="invite-protect">
        <input type="checkbox" :checked="inviteProtect" @change="toggleProtect" :disabled="!isOwner" />
        <span>邀请码保护（一次性 + 24 小时）</span>
      </label>
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

    <section v-if="section === 'pin'" class="a-card enter">
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
.review-date { max-width: 220px; margin-bottom: 10px; }
.invite-protect { display: flex; gap: 8px; align-items: center; margin: 10px 0 4px; font-size: 13px; cursor: pointer; }
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
.a-main { flex: 1; min-width: 0; }
.a-card { background: var(--surface); border-radius: var(--radius-xl); padding: 22px; margin-bottom: 14px; box-shadow: var(--shadow-md); border: 1px solid var(--line); }
.a-card h3 { margin: 0 0 6px; font-size: 22px; color: var(--ink); letter-spacing: -.02em; }
.dash-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 0 0 18px; }
.dash-stat {
  display: block; width: 100%; text-align: left; border: none; cursor: pointer;
  background: var(--surface-2); border-radius: var(--radius-lg); padding: 14px 16px;
  font-family: inherit; color: inherit;
}
.dash-stat span { display: block; font-size: 12px; color: var(--ink-3); font-weight: 700; }
.dash-stat b { display: block; margin-top: 4px; font-size: 24px; color: var(--ink); letter-spacing: -.03em; }
.dash-charts { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; margin: 4px 0 8px; }
.dash-dailies { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
.dash-daily { padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--surface); display: flex; flex-direction: column; gap: 2px; }
.dash-daily.on { background: var(--ok-bg); border-color: var(--ok-bg); }
.pe-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.pe-card { display: flex; flex-direction: column; gap: 4px; padding: 14px; border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--surface-2); }
.pe-card b { font-size: 24px; letter-spacing: -.03em; }
.pe-card small { font-size: 12px; font-weight: 600; margin-left: 4px; color: var(--ink-3); }
.pe-std { margin: 6px 0 2px; }
.pe-svg { width: 100%; height: 56px; display: block; margin-top: 6px; }
.dash-chart .w-h { margin-top: 8px; }
.dash-bars { height: 100px; padding-top: 18px; }
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
.lead { color: var(--ink-2); font-size: 13px; margin: 0 0 16px; line-height: 1.5; }
.review-total { color: var(--accent-ink); font-size: 13px; font-weight: 800; }
.review-steps { display: flex; align-items: center; gap: 7px; margin: 0 0 16px; padding: 10px 12px; background: var(--surface-2); border-radius: var(--radius-md); color: var(--ink-2); font-size: 12px; }
.review-steps b { display: inline-flex; width: 20px; height: 20px; align-items: center; justify-content: center; margin-right: 4px; border-radius: var(--radius-circle); background: var(--brand); color: #fff; font-size: 11px; }
.review-steps i { color: var(--ink-3); font-style: normal; }
.review-empty { display: flex; flex-direction: column; gap: 4px; padding: 18px 0 8px; color: var(--ink-2); }
.review-empty span { color: var(--ink-3); font-size: 12px; }
.review-item { padding: 12px 0; border-top: 1px solid var(--surface-2); }
.review-item-info { display: flex; flex-direction: column; gap: 4px; }
.review-item-title { font-size: 15px; font-weight: 800; color: var(--ink); }
.review-actions { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
.review-actions button { font-size: 12px; }
.review-help { margin: 12px 0 0; color: var(--ink-3); font-size: 11px; line-height: 1.5; }
.review-recorded { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--line); }
.review-recorded h4 { margin: 0; font-size: 14px; color: var(--ink); }
.review-recorded > p { margin: 4px 0 10px; color: var(--ink-3); font-size: 11px; line-height: 1.5; }
.review-recorded-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 0; border-top: 1px solid var(--surface-2); }
.review-recorded-row > div { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.review-recorded-row strong { font-size: 13px; color: var(--ink); }
.review-recorded-row span { color: var(--ink-3); font-size: 11px; }
.review-recorded-row em { flex: none; font-style: normal; color: var(--ink-3); font-size: 11px; }
.review-recorded-row em.due { color: var(--danger); font-weight: 800; }
.review-how { display: flex; flex-direction: column; gap: 5px; margin-top: 18px; padding: 12px; background: var(--surface-2); border-radius: var(--radius-md); color: var(--ink-2); }
.review-how span { color: var(--ink-3); font-size: 12px; line-height: 1.5; }
.review-link { width: auto; align-self: flex-start; margin-top: 2px; padding: 0; }
.unit-wp-count { margin-left: 6px; color: var(--accent-ink); font-size: 11px; font-weight: 700; }
@media (max-width: 560px) {
  .admin { padding: 10px; padding-top: calc(10px + env(safe-area-inset-top)); }
  .review-steps { align-items: flex-start; flex-direction: column; gap: 5px; }
  .review-steps i { display: none; }
  .review-actions { flex-direction: column; }
  .review-actions button { width: 100%; }
}
.lock-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; color: var(--ink-2); font-weight: 700; }
.toggle { border: none; background: var(--surface-2); color: var(--ink-2); padding: 7px 16px; border-radius: var(--radius-pill); font-weight: 800; cursor: pointer; font-family: inherit; }
.toggle.on { background: var(--accent); color: #fff; }
.dim { color: var(--ink-3); font-size: 12px; }
.a-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 0; border-bottom: 1px solid var(--surface-2); }
.a-item.add { border-top: 1px dashed var(--line); margin-top: 8px; padding-top: 12px; }
.a-subject-h { font-weight: 800; color: var(--brand-deep); margin-top: 8px; font-size: 14px; }
.a-item input, .a-item select { border: 1px solid var(--line); border-radius: var(--radius-md); padding: 8px 10px; font-size: 15px; color: var(--ink); background: var(--surface); font-family: inherit; min-height: 40px; }
.a-item input:focus, .a-item select:focus { outline: none; border-color: var(--brand); }
.w-name { flex: 1; min-width: 120px; }
.w-num { width: 70px; }
.w-cat { width: 90px; }
.badge { font-size: 11px; padding: 3px 8px; border-radius: var(--radius-sm); background: var(--surface-2); color: var(--brand-deep); white-space: nowrap; font-weight: 700; }
.badge.daily { background: var(--warm); color: var(--accent-ink); }
.rank-icon { font-size: 18px; }
.st { font-size: 11px; padding: 3px 9px; border-radius: var(--radius-sm); font-weight: 700; white-space: nowrap; }
.st.pending { background: var(--warm); color: var(--accent-ink); }
.st.done { background: var(--surface-2); color: var(--brand-deep); }
.st.delivered { background: var(--ok-bg); color: var(--ok); }
.ok { padding: 7px 14px; border: none; border-radius: var(--radius-md); background: var(--accent); color: #fff; font-weight: 700; cursor: pointer; font-family: inherit; }
.ok.ghost-o { background: var(--brand); }
.del { padding: 6px 10px; border: none; border-radius: var(--radius-md); background: var(--danger-bg); color: var(--danger); cursor: pointer; font-family: inherit; }
.ghost-s { background: none; border: none; color: var(--brand-deep); font-size: 12px; cursor: pointer; font-family: inherit; }
.daily .d-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; width: 100%; padding: 4px 0; }
.toast { position: fixed; left: 50%; bottom: 30px; transform: translateX(-50%); background: rgba(31,59,85,.92); color: #fff; padding: 10px 18px; border-radius: var(--radius-pill); font-size: 14px; z-index: 20; }

.fam-today { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 8px; }
.fam-card { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 150px; flex: 1; padding: 12px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--surface); text-align: left; font-family: inherit; }
button.fam-card { cursor: pointer; }
.fam-card.on { outline: 2px solid var(--accent); }
.fam-st { font-size: 12px; font-weight: 700; font-style: normal; }
.fam-st.amber { color: var(--accent-ink); }
.fam-st.gray { color: var(--ink-3); }
.fam-st.green { color: var(--ok); }
.fam-go { margin-top: 4px; }
.rules-toggle { margin: 12px 0 8px; }
.w-kids { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 12px; }
.w-kids .w-box { cursor: pointer; }
.w-kids .w-box.on { outline: 2px solid var(--accent); }
.w-kids .w-box i { display: block; font-style: normal; font-size: 11px; }
.w-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.w-box { background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 12px 6px; text-align: center; }
.w-box span { display: block; font-size: 11px; color: var(--ink-3); margin-bottom: 4px; }
.w-box b { font-size: 20px; color: var(--ink); }
.w-h { margin: 20px 0 10px; font-size: 14px; color: var(--ink); }
.w-trend { margin-bottom: 4px; }
.w-trend-svg { width: 100%; height: 90px; }
.w-trend-labels { display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-3); margin-top: 6px; }
.w-trend-labels i { font-style: normal; color: var(--brand-deep); font-weight: 700; margin-left: 3px; }
.w-chart { display: flex; align-items: flex-end; gap: 8px; height: 140px; padding-top: 20px; }
.w-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; height: 100%; justify-content: flex-end; }
.w-bar { width: 100%; max-width: 34px; background: var(--accent); border-radius: var(--radius-xs) var(--radius-xs) 0 0; position: relative; min-height: 2px; }
.w-bar.down { background: var(--ink-3); }
.w-bar i { position: absolute; top: -20px; left: 0; width: 100%; text-align: center; font-size: 11px; color: var(--accent-ink); font-style: normal; font-weight: 700; }
.w-bar-col span { font-size: 11px; color: var(--ink-2); }
.w-subj-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.w-subj-name { width: 48px; font-weight: 700; color: var(--ink); flex: none; }
.pen-sum { margin: 12px 0 4px; }
.pen-sum .w-subj-name { width: 84px; }
.w-subj-track { flex: 1; background: var(--line); border-radius: var(--radius-xs); height: 12px; overflow: hidden; }
.w-subj-track i { display: block; height: 100%; background: linear-gradient(90deg,var(--brand),var(--brand)); border-radius: var(--radius-xs); }
.w-subj-num { flex: none; min-width: 2.6em; text-align: right; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--ink-2); }
.band-box { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; }
.band { font-size: 12px; padding: 4px 10px; border-radius: var(--radius-pill); background: var(--warm); color: var(--accent-ink); font-weight: 700; }
.test-band-editor { padding: 12px 0 4px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-bottom: 14px; }
.test-band-head, .band-edit { display: grid; grid-template-columns: minmax(120px, 1fr) 112px 20px 92px 18px; align-items: end; gap: 8px; }
.test-band-head { padding: 0 8px 6px; color: var(--ink-3); font-size: 11px; font-weight: 700; }
.band-edit { padding: 7px 8px; border-top: 1px solid var(--surface-2); }
.band-edit .fld { margin: 0; }
.band-range { color: var(--ink); font-weight: 700; font-size: 13px; padding-bottom: 10px; }
.band-threshold { grid-column: 2; }
.band-arrow { color: var(--ink-3); font-size: 12px; text-align: center; padding-bottom: 10px; }
.band-sun { grid-column: 4; }
.band-actions { display: flex; align-items: center; gap: 8px; margin: 10px 0 4px; }
@media (max-width: 560px) {
  .test-band-head { display: none; }
  .band-edit { grid-template-columns: minmax(100px, 1fr) 88px 18px 76px 18px; }
  .tag-guide-row { grid-template-columns: 1fr; }
}

/* —— 单元任务 / 每日任务 表单重排 —— */
.fld { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.fld > span { font-size: 11px; color: var(--ink-3); font-weight: 700; }
.fld input, .fld select { border: 1px solid var(--line); border-radius: var(--radius-md); padding: 8px 10px; font-size: 15px; color: var(--ink); background: var(--surface); font-family: inherit; width: 100%; min-height: 40px; }
.settings-form { display: flex; flex-direction: column; gap: 12px; max-width: 380px; margin-top: 12px; }
.settings-form .ok { align-self: flex-start; }
.member-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 0; border-bottom: 1px solid var(--surface-2); }
.member-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.kid-card { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 14px; padding: 16px 0; border-bottom: 1px solid var(--line); }
.kid-card .fld { min-width: 0; }
.kid-pin { grid-column: 1 / -1; }
.kid-card .ops { grid-column: 1 / -1; justify-content: space-between; }
.fld input:focus, .fld select:focus { outline: none; border-color: var(--brand); }
.grow { flex: 1 1 120px; }
.w64 { width: 64px; flex: none; }
.w84 { width: 84px; flex: none; }
.w104 { width: 104px; flex: none; }
.ops { display: flex; gap:  6px; align-items: center; flex: none; }
.w-mastered { margin: 12px 0; padding: 9px 12px; border-radius: var(--radius-md); background: var(--brand); color: #fff; font-size: 13px; font-weight: 600; }
.w-next { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 0 0 14px; padding: 12px 14px; border-radius: var(--radius-md); background: var(--warm); }
.w-next strong { font-size: 13px; }
.w-next span { flex: 1; min-width: 160px; color: var(--ink-2); font-size: 13px; }
.test-preview { margin: 0 0 10px; color: var(--accent-ink); font-size: 13px; font-weight: 700; }
.review-filter { margin: 8px 0 12px; }

.subj-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.subj-tab { border: 1px solid var(--line); border-radius: var(--radius-pill); padding: 6px 14px; font-size: 13px; font-weight: 700; color: var(--ink); background: var(--surface); cursor: pointer; }
.subj-tab.on { background: var(--brand); color: #fff; border-color: var(--brand); }
.subj { border: 1px solid var(--line); border-radius: var(--radius-md); margin-bottom: 8px; background: var(--surface); overflow: hidden; }
.subj .unit-block:first-child { border-top: none; }
.unit-block { padding: 10px 14px 12px; border-top: 1px solid var(--surface-2); }
.unit-h { font-weight: 800; font-size: 13px; margin-bottom: 6px; }
.task-readonly-title { flex: 1; min-width: 160px; color: var(--ink-2); font-size: 13px; }
.task-add-box { margin: 0 0 18px; }
.form-help { margin: -4px 0 10px; color: var(--ink-3); font-size: 11px; }
.tag-guide-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px; margin-bottom: 10px; }
.tag-guide { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 0; padding: 10px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); color: var(--ink); text-align: left; font-family: inherit; cursor: pointer; }
.tag-guide:hover { border-color: var(--brand); }
.tag-guide.on { border-color: var(--accent); background: var(--warm); }
.tag-guide:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.tag-guide.auto:not(.on) { opacity: .8; }
.tag-guide-title { font-size: 13px; font-weight: 800; }
.tag-guide-help { color: var(--ink-2); font-size: 12px; line-height: 1.5; }
.tag-guide-action { color: var(--brand-deep); font-size: 11px; font-weight: 700; }
.tag-guide.on .tag-guide-action { color: var(--accent-ink); }
.task-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 14px; border-top: 1px solid var(--surface-2); }
.task-row .badge { flex: none; }

.daily-card { border: 1px solid var(--line); border-radius: var(--radius-md); padding: 12px 14px; margin-bottom: 10px; background: var(--surface); }
.dc-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sys-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sys-name { font-weight: 700; }
.daily-note { flex-basis: 100%; color: var(--ink-2); font-size: 12px; padding-left: 58px; }
.dc-metrics { margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 10px; }
.dc-m-head { font-size: 11px; color: var(--ink-3); font-weight: 800; margin-bottom: 8px; }
.m-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }

.add-box { margin-top: 14px; border: 1px dashed var(--line); border-radius: var(--radius-md); padding: 14px; background: var(--surface-2); }
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
  .dash-stats { grid-template-columns: repeat(2, 1fr); }
  .dash-charts { grid-template-columns: 1fr; }
  .cursor-row { grid-template-columns: 1fr; gap: 6px; }
  .kid-card { grid-template-columns: 1fr; }
  .a-title { font-size: 22px; }
}
@media (max-width: 560px) {
  .w-summary { grid-template-columns: repeat(2, 1fr); }
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