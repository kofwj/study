<script setup>
// 阳光统计页：周趋势、五条途径、还没做好清单。
// 周合计读 /api/ledger/summary（自然周）；点柱拉当日 pocket 明细；
// dailyTodo/studyNext 是父级计算属性，props 传入；点跳转 emit('navigate', gap)。
import { computed, ref, watch } from 'vue'
import { TrendingUp, Target, BookOpen, Globe, CalendarDays, FileText, Gift, ChevronLeft, ChevronRight } from '@lucide/vue'
import { api } from '../api.js'
import { ledgerSummary, weekOffset, data, wordDueCard, wordNewCard, reviewDue, todayPenalty } from '../store.js'

const props = defineProps({
  dailyTodo: { type: Array, default: () => [] },
  studyNext: { type: Array, default: () => [] },
})
const emit = defineEmits(['navigate'])

const SUN_EARN = new Set(['task', 'daily', 'word_daily', 'word_perfect', 'test', 'box', 'milestone', 'bank_deposit', 'bank_interest'])
const SUN_REVERT = new Set(['cancel', 'test_cancel'])
const SUN_SPEND = new Set(['redeem'])
const SUN_PATHS = [
  { id: 'task', name: '课文任务', hint: '把今天的课往前推', reasons: ['task'], icon: BookOpen, tab: null },
  { id: 'word', name: '英语单词', hint: '复习或新词还没写完', reasons: ['word_daily', 'word_perfect'], icon: Globe, tab: '英语' },
  { id: 'daily', name: '每日打卡', hint: '今天的打卡还空着', reasons: ['daily'], icon: CalendarDays, tab: '今日推荐' },
  { id: 'test', name: '单元测试', hint: '测完告诉家长登分', reasons: ['test'], icon: FileText, tab: null },
  { id: 'box', name: '宝箱连击', hint: '连续打卡才会开箱', reasons: ['box', 'milestone'], icon: Gift, tab: null },
]
const REASON_LABEL = {
  task: '课文任务', daily: '每日打卡', word_daily: '单词练习', word_perfect: '单词全对',
  test: '单元测试', box: '开宝箱', milestone: '连击奖励', bank_deposit: '存进银行',
  bank_interest: '银行利息', cancel: '取消打卡', test_cancel: '删测试', redeem: '商店兑换',
  penalty: '约定扣分', penalty_cancel: '撤回约定',
}
const WD = '日一二三四五六'
function pocketRow(r) { return (r.account || 'pocket') === 'pocket' }
function sunDelta(r) { return Number(r.delta) || 0 }
function isSunEarn(r) { return pocketRow(r) && SUN_EARN.has(r.reason) }
function isSunRevert(r) { return pocketRow(r) && SUN_REVERT.has(r.reason) }
function isSunSpend(r) { return pocketRow(r) && SUN_SPEND.has(r.reason) && sunDelta(r) < 0 }
function pathSum(days, id) {
  return (days || []).reduce((s, d) => s + (Number(d.by_reason && d.by_reason[id]) || 0), 0)
}
function md(iso) {
  const p = String(iso || '').split('-')
  return `${Number(p[1])}/${Number(p[2])}`
}

const loadingWeek = ref(false)
let weekSeq = 0
async function loadWeek(offset) {
  const n = Math.max(0, Math.min(52, Number(offset) || 0))
  weekOffset.value = n
  const seq = ++weekSeq
  loadingWeek.value = true
  try {
    const s = await api.ledgerSummary(n)
    if (seq !== weekSeq) return
    ledgerSummary.value = s
  } catch { /* 沿用已有聚合 */ }
  finally { if (seq === weekSeq) loadingWeek.value = false }
}
function shiftWeek(dir) {
  const next = Math.max(0, Math.min(52, (weekOffset.value || 0) + dir))
  if (next === (weekOffset.value || 0)) return
  openDate.value = ''
  dayRows.value = []
  loadWeek(next)
}

const openDate = ref('')
const dayRows = ref([])
const dayLoading = ref(false)
let daySeq = 0
async function toggleDay(iso) {
  if (openDate.value === iso) {
    openDate.value = ''
    dayRows.value = []
    return
  }
  openDate.value = iso
  const seq = ++daySeq
  dayLoading.value = true
  try {
    const rows = await api.ledgerDay(iso)
    if (seq !== daySeq) return
    dayRows.value = rows || []
  } catch {
    if (seq !== daySeq) return
    dayRows.value = []
  } finally { if (seq === daySeq) dayLoading.value = false }
}
watch(() => ledgerSummary.value && ledgerSummary.value.week_start, () => {
  openDate.value = ''
  dayRows.value = []
})

const sunshineStats = computed(() => {
  const s = ledgerSummary.value || {}
  const today = s.today || data.today
  const rawDays = s.days || []
  const prevDays = s.prev_week || []
  const days = rawDays.map(d => {
    const [yy, mm, dd] = String(d.date || '').split('-').map(Number)
    const dt = new Date(yy, mm - 1, dd)
    const isToday = d.date === today
    const inn = Math.max(0, Number(d.earn) || 0)
    const out = Math.max(0, Number(d.spend) || 0)
    const future = today && d.date > today
    return { date: d.date, wd: isToday ? '今天' : WD[dt.getDay()] || '', inn, out, today: isToday, quiet: inn === 0 && !future }
  })
  const weekIn = Math.max(0, s.week_in == null ? days.reduce((n, d) => n + d.inn, 0) : Number(s.week_in) || 0)
  const weekOut = s.week_out == null ? days.reduce((n, d) => n + d.out, 0) : Number(s.week_out) || 0
  const maxAbs = Math.max(1, ...days.map(d => Math.max(d.inn, d.out)), 0)
  const paths = SUN_PATHS.map(p => {
    const week = pathSum(rawDays, p.id)
    const prev = pathSum(prevDays, p.id)
    let vs = '这周还没有'
    if (week > 0 && prev === 0) vs = '这周刚开始有'
    else if (week > prev) vs = `比上周多 ${week - prev}`
    else if (week < prev) vs = `比上周少 ${prev - week}`
    else if (week > 0) vs = '和上周差不多'
    return { ...p, week, prev, vs }
  })
  const maxPath = Math.max(1, ...paths.map(p => p.week), 0)
  const top = [...paths].sort((a, b) => b.week - a.week)[0]
  const start = s.week_start || (days[0] && days[0].date) || ''
  const end = days[6] && days[6].date || ''
  return {
    days, weekIn, weekOut, maxAbs, paths, maxPath,
    quiet: days.filter(d => d.quiet && !d.today),
    topName: top && top.week ? top.name : '',
    rangeLabel: start && end ? `${md(start)}–${md(end)}` : '',
    offset: Number(s.offset || 0),
    redemptions: s.redemptions || [],
    weeklyGoal: Math.max(0, Number(s.weekly_goal) || 0),
  }
})
const weekGoalBar = computed(() => {
  const st = sunshineStats.value
  const goal = st.weeklyGoal
  if (!goal) return null
  const got = st.weekIn
  const over = Math.max(0, got - goal)
  const pct = Math.min(100, Math.round(got / goal * 100))
  let text = `本周目标 ${got}/${goal}`
  if (over) text = `本周目标 ${got}/${goal} · 超标 ${over}`
  else if (got >= goal) text = `本周目标 ${got}/${goal} · 达标了`
  return { goal, got, over, pct, done: got >= goal, text }
})
const editingGoal = ref(false)
const goalDraft = ref(50)
const goalBusy = ref(false)
function openGoalEdit() {
  goalDraft.value = sunshineStats.value.weeklyGoal || 50
  editingGoal.value = true
}
async function saveGoal() {
  const n = Math.max(0, Math.min(10000, Math.round(Number(goalDraft.value) || 0)))
  goalBusy.value = true
  try {
    const r = await api.setWeeklyGoal(n)
    ledgerSummary.value = { ...ledgerSummary.value, weekly_goal: r.weekly_goal }
    editingGoal.value = false
  } catch { /* 保留编辑态 */ }
  finally { goalBusy.value = false }
}
const sunshineGaps = computed(() => {
  const g = []
  const st = sunshineStats.value
  if (st.offset) return []
  if (props.dailyTodo.length) g.push({ id: 'daily', text: `今天还有 ${props.dailyTodo.length} 项打卡没做`, go: '今日推荐' })
  if (wordDueCard.value && !wordDueCard.value.finished) g.push({ id: 'word-due', text: `单词复习还剩 ${wordDueCard.value.left} 个`, lane: 'due' })
  if (wordNewCard.value && !wordNewCard.value.finished) g.push({ id: 'word-new', text: `新词还剩 ${wordNewCard.value.left} 个`, lane: 'new' })
  if (reviewDue.value.length) g.push({ id: 'review', text: `有 ${reviewDue.value.length} 项复习到期了`, go: '今日推荐' })
  if (props.studyNext.length) g.push({ id: 'study', text: `课文还没往前：${props.studyNext[0].subject_id}`, go: props.studyNext[0].subject_id })
  if (st.quiet.length) g.push({ id: 'quiet', text: `这周有 ${st.quiet.length} 天没有攒到阳光` })
  const emptyPath = st.paths.find(p => p.week === 0 && (p.id === 'task' || p.id === 'daily' || p.id === 'word'))
  if (emptyPath) g.push({ id: 'path-' + emptyPath.id, text: `这周还没有「${emptyPath.name}」的阳光`, go: emptyPath.tab || '今日推荐' })
  if (st.weekOut > st.weekIn && st.weekOut) g.push({ id: 'spend', text: `这周兑换了 ${st.weekOut}，只攒了 ${st.weekIn}` })
  if (todayPenalty.value) g.push({ id: 'penalty', text: `今天有约定：${todayPenalty.value.reason}` })
  const seen = new Set()
  return g.filter(x => (seen.has(x.id) ? false : seen.add(x.id)))
})
const sunshineLead = computed(() => {
  const st = sunshineStats.value
  if (st.offset) {
    if (st.weekIn || st.weekOut) return `${st.rangeLabel} 攒了 ${st.weekIn}，兑换 ${st.weekOut}`
    return `${st.rangeLabel} 没有阳光进出`
  }
  const gap = sunshineGaps.value[0]
  if (gap) return gap.text
  if (st.topName) return `这周阳光主要来自${st.topName}`
  return '去做任务，口袋就会亮起来'
})
function goSunGap(g) {
  emit('navigate', g)
}
function rowLabel(r) {
  return (r.note && String(r.note).trim()) || REASON_LABEL[r.reason] || r.reason || '阳光'
}
function fmtDelta(n) {
  const v = Number(n) || 0
  return v > 0 ? '+' + v : String(v)
}
</script>

<template>
  <div class="sun-page">
    <div class="bank-header">
      <div class="bank-title">
        <TrendingUp class="bank-icon" :size="28" />
        <div>
          <h1>我的阳光</h1>
          <p>{{ sunshineLead }}</p>
        </div>
      </div>
    </div>
    <div v-if="weekGoalBar" class="sun-week-goal" :class="{ done: weekGoalBar.done }">
      <div class="sun-week-goal-row">
        <strong>{{ weekGoalBar.text }}</strong>
        <button v-if="!editingGoal" type="button" class="sun-goal-edit" @click="openGoalEdit">改目标</button>
      </div>
      <div class="goal-bar sun-week-goal-bar"><i class="goal-fill" :style="{ width: weekGoalBar.pct + '%' }"></i></div>
      <div v-if="editingGoal" class="sun-goal-form">
        <input v-model.number="goalDraft" type="number" min="0" max="10000" />
        <button type="button" class="sun-goal-edit" :disabled="goalBusy" @click="saveGoal">保存</button>
        <button type="button" class="sun-goal-edit ghost" :disabled="goalBusy" @click="editingGoal = false">取消</button>
        <span class="sun-goal-hint">0 表示关掉</span>
      </div>
    </div>
    <div v-else class="sun-week-goal off">
      <button type="button" class="sun-goal-edit" @click="openGoalEdit">设本周攒阳光目标</button>
    </div>


    <div v-if="sunshineGaps.length" class="sun-gaps">
      <h3 class="section-title"><Target class="ico" :size="18" /> 还没做好</h3>
      <button v-for="g in sunshineGaps.slice(0, 5)" :key="g.id" type="button" class="sun-gap" :disabled="!g.go && !g.lane" @click="goSunGap(g)">
        <span>{{ g.text }}</span>
        <em v-if="g.go || g.lane">去看看</em>
      </button>
    </div>
    <div v-else-if="!sunshineStats.offset" class="sun-gaps ok">
      <p>这周该做的都有阳光进账，继续保持。</p>
    </div>

    <div class="bank-operations">
      <div class="op-header">
        <h3>这周趋势</h3>
        <span class="sun-week-sum">攒 {{ sunshineStats.weekIn }} · 兑换 {{ sunshineStats.weekOut }}</span>
      </div>
      <div class="sun-week-nav">
        <button type="button" class="sun-week-btn" :disabled="sunshineStats.offset >= 52 || loadingWeek" @click="shiftWeek(1)" aria-label="上一周">
          <ChevronLeft :size="18" />
        </button>
        <span class="sun-week-range">{{ sunshineStats.rangeLabel || '本周' }}</span>
        <button type="button" class="sun-week-btn" :disabled="!sunshineStats.offset || loadingWeek" @click="shiftWeek(-1)" aria-label="下一周">
          <ChevronRight :size="18" />
        </button>
      </div>
      <div class="sun-week">
        <button v-for="d in sunshineStats.days" :key="d.date" type="button" class="sun-col" :class="{ quiet: d.quiet && !d.today, open: openDate === d.date }" @click="toggleDay(d.date)">
          <span class="sun-col-n" :class="{ zero: !d.inn }">{{ d.inn ? '+' + d.inn : '0' }}</span>
          <div class="sun-track dual">
            <i class="in" :style="{ height: Math.max(d.inn ? 8 : 0, Math.round(d.inn / sunshineStats.maxAbs * 68)) + 'px' }"></i>
            <i class="out" :style="{ height: Math.max(d.out ? 8 : 0, Math.round(d.out / sunshineStats.maxAbs * 68)) + 'px' }"></i>
          </div>
          <span :class="{ today: d.today }">{{ d.wd }}</span>
        </button>
      </div>
      <p class="sun-week-legend"><i class="in"></i> 攒到的 <i class="out"></i> 商店兑换 · 点一天看明细</p>
      <div v-if="openDate" class="sun-day-panel">
        <p v-if="dayLoading" class="sun-day-empty">在看 {{ md(openDate) }} 的流水…</p>
        <p v-else-if="!dayRows.length" class="sun-day-empty">这一天还没有口袋流水</p>
        <ul v-else class="sun-day-list">
          <li v-for="r in dayRows" :key="r.id" :class="{ down: (Number(r.delta) || 0) < 0 }">
            <span>{{ rowLabel(r) }}</span>
            <b>{{ fmtDelta(r.delta) }}</b>
          </li>
        </ul>
      </div>
      <div v-if="sunshineStats.redemptions.length" class="sun-redeem">
        <h4>本周兑换</h4>
        <ul>
          <li v-for="(r, i) in sunshineStats.redemptions" :key="i">
            <span>{{ md(r.date) }} · {{ r.note || '商店兑换' }}</span>
            <b>{{ fmtDelta(r.delta) }}</b>
          </li>
        </ul>
      </div>
    </div>

    <div class="bank-operations">
      <div class="op-header"><h3>五条途径</h3></div>
      <div class="sun-path-list">
        <div v-for="p in sunshineStats.paths" :key="p.id" class="sun-path" :class="{ miss: !p.week }">
          <i class="sun-ico" :class="p.id"><component :is="p.icon" :size="18" /></i>
          <div>
            <strong>{{ p.name }}</strong>
            <small>{{ p.week ? p.vs : p.hint }}</small>
          </div>
          <b>{{ p.week ? '+' + p.week : '0' }}</b>
          <div class="goal-bar src-bar"><i class="goal-fill" :style="{ width: Math.round(p.week / sunshineStats.maxPath * 100) + '%' }"></i></div>
        </div>
      </div>
    </div>
  </div>
</template>
