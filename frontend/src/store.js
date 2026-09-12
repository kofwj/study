// 孩子端共享状态（App.vue 拆分的第 2 步）。
// 只放「全局公共区」：会话、任务主数据、refresh 分发的公共结果。
// 各功能块的专属状态（wordToday/sprites/capsule/bankData）留在原块，
// 全部拆完后 refresh() 才迁进来——先迁状态不迁中枢，保证每步行为零变化。
import { reactive, ref, computed } from 'vue'

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
