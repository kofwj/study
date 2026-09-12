// 孩子端共享状态（App.vue 拆分的第 2 步）。
// 只放「全局公共区」：会话、任务主数据、refresh 分发的公共结果。
// 各功能块的专属状态（wordToday/sprites/capsule/bankData）留在原块，
// 全部拆完后 refresh() 才迁进来——先迁状态不迁中枢，保证每步行为零变化。
import { reactive, ref, computed } from 'vue'
import { api } from './api.js'
import { playSound, playLevelUpBeep, playEvolveBeep } from './sounds.js'
import companionEggImg from './assets/companion-egg.png'
import companionSproutImg from './assets/companion-sprout.png'
import companionLeafImg from './assets/companion-leaf.png'
import companionBloomImg from './assets/companion-bloom.png'

export const data = reactive({
  level: { earned: 0, balance: 0, level: '阳光萌新', next: null, next_need: 0, progress: 0 },
  streak: 0,
  kid_name: '乐乐',
  kid_id: '',
  today: '',
  active_term: '',
  cursors: {},
  today_checkin: false,
  checkin_window: { open: true, from: '07:00', until: '21:00', hint: '', now: '' },
  subjects: [],
  hidden_subjects: [],
  units: [],
  tasks: [],
  daily: [],
  unit_scores: {},
  test_fail_score: 80,
  fitness_goals: {},
  weak_tags: {},
  companion: {
    stage: 'egg', stage_name: '阳光蛋', name: '', earned: 0,
    next_stage: 'sprout', next_stage_name: '阳光芽', next_need: 50,
    progress: 0, aura: null, evolve: false,
  },
})

export const loading = ref(true)
export const err = ref('')
export const me = ref(null)
export const authed = ref(false)
export const isAdmin = ref(false)
export const mustChangePin = ref(false)
export const pendingRecovery = ref('') // 家长注册/找回后的一次性找回码，传给 Admin 展示

// ---- 单词练习：共享状态与纯派生（App 卡片与 WordPractice 组件共用）----
export const wordToday = ref({ enabled: false, finished: false, session: null, config: {} })
export function wordItems() { return wordToday.value.session?.items || [] }
export function wordLaneOf(item) { return item && item.source === 'due' ? 'due' : 'new' }
export const wordSun = computed(() => {
  const cfg = wordToday.value.config || {}
  return cfg.base_sunshine != null ? cfg.base_sunshine : 3
})
export function buildWordLane(kind) {
  const t = wordToday.value
  if (!t.enabled) return null
  const sess = t.session
  const counts = (sess && sess.counts) || {}
  const items = (wordItems()).filter(x => wordLaneOf(x) === kind)
  let total = items.length
  if (!total && sess) total = Number(kind === 'due' ? counts.due : counts.new) || 0
  if (!total && !sess && !t.finished) {
    if (kind === 'due') total = Number(t.backlog_due) || 0
    else total = 1
  }
  if (!total) return null
  const left = items.length ? items.filter(x => x.state !== 'done').length : total
  const finished = !!(t.finished || (sess && sess.state === 'completed') || (items.length && left === 0))
  let detail = kind === 'due' ? '到期的词，直接默写' : '本课新词，先看再写'
  if (finished) detail = kind === 'due' ? `复习完成 · ${total} 个` : `新词完成 · ${total} 个`
  else if (items.length) detail = `还剩 ${left} 个 · ${kind === 'due' ? '到期复习' : '本课新词'}`
  else detail = kind === 'due' ? `约 ${total} 个到期` : '去学几个新词'
  return { kind, title: kind === 'due' ? '今日复习' : '今日新词', detail, finished, left, total, sun: wordSun.value }
}
export const wordDueCard = computed(() => buildWordLane('due'))
export const wordNewCard = computed(() => buildWordLane('new'))

// ---- 秘密基地 / 阳光图鉴 / 时间胶囊（App 卡片、SpritesBase、CapsuleBox 共用）----
export const sprites = ref({
  enabled: false, base_enabled: false, loaded: false,
  dust: 0, owned: 0, total: 12, series: [], layout: {}, shop: [],
  base_items: [], on_duty: '', today: {}, morning: { new: false, who: '', text: '' },
  memos: { award: false, flag: false }, star_cost: 12,
})
export const capsule = ref({ state: 'empty', capsule: null, wait: '', options: [], now: null, questions: [], min_open_on: '', max_open_on: '' })
export const capsuleOpen = ref(false)
export const capsuleOpenedView = ref(false)
export const spriteScene = ref('sun')
export const spritesOpen = ref(false)
export const morningShow = ref(false)
export const toyFlip = reactive({})

export const SPRITE_CACHE = 'pw3'
export function isNight() {
  const h = new Date().getHours()
  return h >= 19 || h < 6
}
export function spImg(id) { return `/sprites/${id}.webp?v=${SPRITE_CACHE}` }
export function toyImg(id) { return `/sprites/toys/${id}.webp?v=${SPRITE_CACHE}` }
export function baseImg(scene) { return `/sprites/base/${scene}-${isNight() ? 'night' : 'day'}.webp?v=${SPRITE_CACHE}` }
export function displayName(it) { return (it.nickname && it.nickname.trim()) || it.name }
export const dutySprite = computed(() => {
  if (!sprites.value.enabled || !sprites.value.base_enabled || !sprites.value.on_duty) return null
  for (const s of sprites.value.series || []) {
    const it = (s.items || []).find(x => x.id === sprites.value.on_duty && x.owned)
    if (it) return it
  }
  return null
})

const FLOOR = {
  sun: [{ x: 52, y: 90 }, { x: 66, y: 90 }, { x: 78, y: 90 }],
  leaf: [{ x: 30, y: 92 }, { x: 42, y: 92 }, { x: 72, y: 92 }],
  sky: [{ x: 38, y: 86 }, { x: 50, y: 86 }, { x: 62, y: 86 }],
}
export function sceneToys(scene) {
  const layout = (sprites.value.layout && sprites.value.layout[scene]) || []
  const bought = new Set(sprites.value.base_items || [])
  const today = sprites.value.today || {}
  const dailyDone = Number(today.daily_done || 0) > 0
  return layout.filter(t => {
    if (t.kind === 'shop') return bought.has(t.id)
    if (t.id === 'trace-pinwheel') return dailyDone
    if (t.id === 'memo-capsule') return true
    // 奖状/小旗要有「拿到了」的仪式，不按旧连击或旧全对补挂到树上
    if (t.id === 'memo-award' || t.id === 'memo-flag') return false
    return false
  })
}
export function sceneBuddies(scene) {
  const ser = (sprites.value.series || []).find(s => s.id === scene)
  const owned = (ser?.items || []).filter(x => x.owned)
  const toys = sceneToys(scene)
  const seats = toys.filter(t => t.sit)
  const used = new Set()
  const out = []
  const duty = sprites.value.on_duty
  const moon = toys.find(t => t.id === 'sky-moonbed')
  if (scene === 'sky' && moon && isNight() && duty) {
    const d = owned.find(x => x.id === duty)
    if (d) {
      out.push({ ...d, x: moon.x, y: moon.y - 8, w: moon.sit?.w || 8, pose: 'lie' })
      used.add(d.id)
    }
  }
  for (const seat of seats) {
    if (seat.id === 'sky-moonbed') continue
    const who = owned.find(x => !used.has(x.id))
    if (!who) break
    used.add(who.id)
    out.push({
      ...who,
      x: seat.x - 4 + (seat.sit.x - 50) * seat.w / 100,
      y: seat.y - (100 - (seat.sit.y || 70)) * 0.12,
      w: seat.sit.w || 8,
      pose: seat.pose || 'sit',
    })
  }
  const floors = FLOOR[scene] || []
  let fi = 0
  for (const who of owned) {
    if (used.has(who.id) || fi >= floors.length) continue
    out.push({ ...who, x: floors[fi].x, y: floors[fi].y, w: 8, pose: 'stand' })
    fi += 1
  }
  return out
}

export function applyCapsule(p) {
  if (!p) return
  capsule.value = p
}
export async function loadSprites() {
  try {
    const sp = await api.sprites()
    sprites.value = { ...sprites.value, ...sp, loaded: true }
  } catch {
    sprites.value.enabled = false
  }
}
export const morningPending = computed(() => !!(
  sprites.value.enabled && sprites.value.base_enabled && sprites.value.morning?.new && sprites.value.morning?.text
))
export function maybeShowMorning() {
  if (morningPending.value) morningShow.value = true
}

// ---- 阳光账本：今日约定（阳光页与今日推荐共用）----
export const todayPenalty = computed(() => {
  const today = data.today
  const rows = recentLedger.value || []
  const cancels = new Set(rows.filter(r => r.reason === 'penalty_cancel').map(r => r.ref_id))
  const active = rows.filter(r => r.reason === 'penalty' && r.date === today && !cancels.has(r.ref_id))
  if (!active.length) return null
  const n = active.reduce((s, r) => s + Math.abs(Number(r.delta) || 0), 0)
  const reason = ((active[0].note || '').split('：')[0] || '约定').trim()
  return { n, count: active.length, reason }
})
export const rewards = ref([])
export const achievements = ref([])

// ---- 成就（顶栏徽标与成就墙弹窗共用）----
export const achOn = (a) => !!(a && (a.earned || a.unlocked))
export const achNew = (a) => achOn(a) && Number(a.seen) === 0
export const newAchCount = computed(() => achievements.value.filter(achNew).length)
export const boxes = ref({ avail: 0, opened: 0, earned: 0, streak: 0 })
export const recentLedger = ref([])
export const reviewDue = ref([])
export const activeTab = ref('今日推荐')

// ---- 全局 toast（所有拆分出去的组件共用）----
export const toast = ref('')
let toastTimer = null
export function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2800)
}

// ---- 伙伴与全局庆祝（refresh/各业务动作都会触发）----
export const COMPANION_IMAGES = { egg: companionEggImg, sprout: companionSproutImg, leaf: companionLeafImg, bloom: companionBloomImg }
export const companion = computed(() => data.companion || {})
export const companionImage = computed(() => COMPANION_IMAGES[companion.value.stage] || companionEggImg)
export const companionTitle = computed(() => {
  const c = companion.value
  const stage = c.stage_name || '阳光蛋'
  return (c.name && String(c.name).trim()) ? (c.name.trim() + ' · ' + stage) : stage
})
export const celebrate = ref(null)
export const companionEvolve = ref(null)
export const companionEvolveImage = computed(() => COMPANION_IMAGES[companionEvolve.value?.stage] || companionEggImg)
export const companionPulse = ref(false)
export const pendingLevelUp = ref(null)
let evolveTimer = null
let companionPulseTimer = null

export function pulseCompanion() {
  companionPulse.value = false
  if (companionPulseTimer) clearTimeout(companionPulseTimer)
  requestAnimationFrame(() => { companionPulse.value = true })
  companionPulseTimer = setTimeout(() => { companionPulse.value = false; companionPulseTimer = null }, 720)
}

export function showLevelCelebrate(payload) {
  celebrate.value = payload
  playSound('levelup') || playLevelUpBeep()
  if (navigator.vibrate) navigator.vibrate([100, 50, 100, 50, 100])
  setTimeout(() => (celebrate.value = null), 2800)
}

export function closeCompanionEvolve() {
  if (!companionEvolve.value) return
  playSound('evolve') || playEvolveBeep()
  if (navigator.vibrate) navigator.vibrate([80, 40, 80, 40, 120])
  companionEvolve.value = null
  if (evolveTimer) { clearTimeout(evolveTimer); evolveTimer = null }
  api.ackCompanionEvolve().then(out => { if (out) data.companion = out }).catch(() => {})
  if (pendingLevelUp.value) {
    const p = pendingLevelUp.value
    pendingLevelUp.value = null
    showLevelCelebrate(p)
  }
}

// refresh 检测到伙伴可进化时触发；两秒半后自动收起
export function triggerCompanionEvolve(info) {
  if (!info || companionEvolve.value) return
  companionEvolve.value = info
  if (evolveTimer) clearTimeout(evolveTimer)
  evolveTimer = setTimeout(closeCompanionEvolve, 2800)
}
