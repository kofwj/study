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
