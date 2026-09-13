<script setup>
// 阳光统计页：周趋势、五条途径、还没做好清单。
// 周合计读 /api/ledger/summary（自然周）；点柱拉当日 pocket 明细；
// dailyTodo/studyNext 从 store 读；点跳转 emit('navigate', gap)。
import { computed, ref, watch } from 'vue'
import { TrendingUp, Target, BookOpen, Globe, CalendarDays, FileText, Gift, ChevronLeft, ChevronRight } from '@lucide/vue'
import { api } from '../api.js'
import { useCountUp } from '../countUp.js'
import { ledgerSummary, weekOffset, data, wordDueCard, wordNewCard, reviewDue, todayPenalty, dailyTodo, studyNext } from '../store.js'

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

function barH(n, maxAbs) {
  const v = Math.max(0, Number(n) || 0)
  if (!v) return 0
  return Math.max(8, Math.round(v / maxAbs * 68))
}
const sunshineStats = computed(() => {
  const s = ledgerSummary.value || {}
  const today = s.today || data.today
  const rawDays = s.days || []
  const prevDays = s.prev_week || []
  const maxAbs = Math.max(1, ...rawDays.map((d, i) => {
    const prev = prevDays[i] || {}
    return Math.max(
      Math.max(0, Number(d.earn) || 0), Math.max(0, Number(d.spend) || 0),
      Math.max(0, Number(prev.earn) || 0), Math.max(0, Number(prev.spend) || 0),
    )
  }), 0)
  const days = rawDays.map((d, i) => {
    const [yy, mm, dd] = String(d.date || '').split('-').map(Number)
    const dt = new Date(yy, mm - 1, dd)
    const isToday = d.date === today
    const inn = Math.max(0, Number(d.earn) || 0)
    const out = Math.max(0, Number(d.spend) || 0)
    const prev = prevDays[i] || {}
    const prevInn = Math.max(0, Number(prev.earn) || 0)
    const prevOut = Math.max(0, Number(prev.spend) || 0)
    const future = today && d.date > today
    const wd = isToday ? '今天' : WD[dt.getDay()] || ''
    return {
      date: d.date, wd, inn, out, prevInn, prevOut, today: isToday, quiet: inn === 0 && !future,
      innH: barH(inn, maxAbs), outH: barH(out, maxAbs),
      prevInnH: barH(prevInn, maxAbs), prevOutH: barH(prevOut, maxAbs),
      aria: `${wd} 攒 ${inn} 兑 ${out}`,
    }
  })
  const weekIn = Math.max(0, s.week_in == null ? days.reduce((n, d) => n + d.inn, 0) : Number(s.week_in) || 0)
  const weekOut = s.week_out == null ? days.reduce((n, d) => n + d.out, 0) : Number(s.week_out) || 0
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
  const emptyWeek = days.length === 7 && !weekIn && !weekOut
  return {
    days, weekIn, weekOut, maxAbs, paths, maxPath, emptyWeek,
    quiet: days.filter(d => d.quiet && !d.today),
    topName: top && top.week ? top.name : '',
    rangeLabel: start && end ? `${md(start)}–${md(end)}` : '',
    offset: Number(s.offset || 0),
    redemptions: s.redemptions || [],
    weeklyGoal: Math.max(0, Number(s.weekly_goal) || 0),
  }
})
const weekInShown = useCountUp(() => sunshineStats.value.weekIn)
const weekOutShown = useCountUp(() => sunshineStats.value.weekOut)


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
    const goal = Number(r && r.weekly_goal)
    ledgerSummary.value.weekly_goal = Number.isFinite(goal) ? goal : n
    editingGoal.value = false
  } catch { /* 保留编辑态 */ }
  finally { goalBusy.value = false }
}
const sunshineGaps = computed(() => {
  const g = []
  const st = sunshineStats.value
  if (st.offset) return []
  if (dailyTodo.value.length) g.push({ id: 'daily', text: `今天还有 ${dailyTodo.value.length} 项打卡没做`, go: '今日推荐' })
  if (wordDueCard.value && !wordDueCard.value.finished) g.push({ id: 'word-due', text: `单词复习还剩 ${wordDueCard.value.left} 个`, lane: 'due' })
  if (wordNewCard.value && !wordNewCard.value.finished) g.push({ id: 'word-new', text: `新词还剩 ${wordNewCard.value.left} 个`, lane: 'new' })
  if (reviewDue.value.length) g.push({ id: 'review', text: `有 ${reviewDue.value.length} 项复习到期了`, go: '今日推荐' })
  if (studyNext.value.length) g.push({ id: 'study', text: `课文还没往前：${studyNext.value[0].subject_id}`, go: studyNext.value[0].subject_id })

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
      <div v-if="editingGoal" class="sun-goal-form">
        <input v-model.number="goalDraft" type="number" min="0" max="10000" />
        <button type="button" class="sun-goal-edit" :disabled="goalBusy" @click="saveGoal">保存</button>
        <button type="button" class="sun-goal-edit ghost" :disabled="goalBusy" @click="editingGoal = false">取消</button>
        <span class="sun-goal-hint">0 表示关掉</span>
      </div>
      <div class="goal-bar sun-week-goal-bar"><i class="goal-fill" :style="{ width: weekGoalBar.pct + '%' }"></i></div>
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
    <div v-else-if="sunshineStats.emptyWeek && !sunshineStats.offset" class="sun-gaps ok">
      <p>完成第一个任务，这里就会亮起来</p>
    </div>
    <div v-else-if="!sunshineStats.offset" class="sun-gaps ok">
      <p>这周该做的都有阳光进账，继续保持。</p>
    </div>

    <div class="bank-operations">
      <div class="op-header">
        <h3>这周趋势</h3>
        <span class="sun-week-sum">攒 {{ weekInShown }} · 兑换 {{ weekOutShown }}</span>
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
        <button v-for="d in sunshineStats.days" :key="d.date" type="button" class="sun-col" :class="{ quiet: d.quiet && !d.today, open: openDate === d.date }" :aria-label="d.aria" @click="toggleDay(d.date)">
          <span class="sun-col-n" :class="{ zero: !d.inn }">{{ d.inn ? '+' + d.inn : '0' }}</span>
          <div class="sun-track dual">
            <span class="sun-pair">
              <i class="ghost in" :style="{ height: d.prevInnH + 'px' }"></i>
              <i class="in" :style="{ height: d.innH + 'px' }"></i>
            </span>
            <span class="sun-pair">
              <i class="ghost out" :style="{ height: d.prevOutH + 'px' }"></i>
              <i class="out" :style="{ height: d.outH + 'px' }"></i>
            </span>
          </div>
          <span :class="{ today: d.today }">{{ d.wd }}</span>
        </button>
      </div>
      <p class="sun-week-legend"><i class="in"></i> 攒到的 <i class="out"></i> 商店兑换 · 浅色是上周 · 点一天看明细</p>

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

<style scoped>
.sun-page { max-width: 720px; padding-bottom: 24px; }
.sun-gaps { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.sun-gaps.ok { background: var(--ok-bg); border-radius: var(--radius-xl); padding: 14px 16px; }
.sun-gaps.ok p { margin: 0; font-weight: 700; color: var(--ok); }
.sun-gap { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; text-align: left; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 12px 14px; font-family: inherit; cursor: pointer; }
.sun-gap:disabled { cursor: default; }
.sun-gap span { font-size: 14px; font-weight: 800; color: var(--ink); }
.sun-gap em { font-style: normal; font-size: 12px; font-weight: 800; color: var(--accent-ink); background: var(--warm); padding: 4px 10px; border-radius: var(--radius-pill); }
.sun-week-sum { font-size: 12px; font-weight: 800; color: var(--ink-2); }
.sun-ico {
  width: 36px; height: 36px; border-radius: var(--radius-circle);
  display: inline-flex; align-items: center; justify-content: center;
  margin-bottom: 8px; color: #fff;
}
.sun-ico.daily { background: #2e9e63; }
.sun-ico.box { background: #d2514f; }
.sun-week { display: flex; align-items: flex-end; gap: 8px; height: 140px; padding-top: 8px; }
.sun-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; border: 0; background: transparent; padding: 0; font-family: inherit; cursor: pointer; }
.sun-col-n { font-size: 12px; font-weight: 800; color: var(--accent-ink); min-height: 16px; }
.sun-col-n.down, .sun-col-n.zero { color: var(--ink-3); }
.sun-track { flex: 1; width: 100%; max-width: 28px; display: flex; align-items: flex-end; justify-content: center; }
.sun-track i { display: block; width: 100%; background: var(--accent); border-radius: 6px 6px 0 0; min-height: 6px; }
.sun-track i.down { background: var(--ink-3); }
.sun-col span:last-child { font-size: 12px; color: var(--ink-2); font-weight: 700; }
.sun-col span.today { color: var(--accent-ink); }
.sun-track.dual { display: flex; align-items: flex-end; justify-content: center; gap: 3px; }
.sun-track.dual i { width: 10px; min-height: 0; border-radius: 5px 5px 0 0; transition: height 120ms ease; }
.sun-pair { position: relative; display: flex; align-items: flex-end; width: 10px; height: 68px; }
.sun-pair i { position: absolute; left: 0; bottom: 0; width: 10px; }
.sun-pair i.ghost { opacity: .28; z-index: 0; }
.sun-pair i.in, .sun-pair i.out { z-index: 1; }
.sun-track.dual i.in, .sun-week-legend i.in { background: var(--accent); }
.sun-track.dual i.out, .sun-week-legend i.out { background: var(--ink-3); }
.sun-col.quiet .sun-col-n { color: var(--danger); }
.sun-week-legend { display: flex; align-items: center; gap: 6px; margin: 10px 0 0; font-size: 12px; font-weight: 700; color: var(--ink-3); }
.sun-week-legend i { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.sun-week-nav { display: flex; align-items: center; justify-content: center; gap: 10px; margin: 4px 0 2px; }
.sun-week-btn { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: 1px solid var(--line); background: var(--surface); border-radius: var(--radius-circle); color: var(--ink); cursor: pointer; }
.sun-week-btn:disabled { opacity: .35; cursor: default; }
.sun-week-range { font-size: 13px; font-weight: 800; color: var(--ink-2); min-width: 88px; text-align: center; }
.sun-col.open { background: var(--warm); border-radius: 10px 10px 0 0; }
.sun-day-panel { margin-top: 10px; background: var(--surface-2); border-radius: var(--radius-lg); padding: 10px 12px; }
.sun-day-empty { margin: 0; font-size: 13px; font-weight: 700; color: var(--ink-3); }
.sun-day-list, .sun-redeem ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.sun-day-list li, .sun-redeem li { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13px; font-weight: 700; }
.sun-day-list b { font-variant-numeric: tabular-nums; color: var(--accent-ink); }
.sun-day-list li.down b, .sun-redeem b { color: var(--ink-3); font-variant-numeric: tabular-nums; }
.sun-redeem { margin-top: 12px; }
.sun-redeem h4 { margin: 0 0 8px; font-size: 13px; font-weight: 800; color: var(--ink-2); }
.sun-week-goal { margin: 0 0 16px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-xl); padding: 12px 14px; }
.sun-week-goal.done { background: var(--ok-bg); border-color: transparent; }
.sun-week-goal.done strong { color: var(--ok); }
.sun-week-goal.off { background: transparent; border: 0; padding: 0 0 12px; }
.sun-week-goal-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.sun-week-goal-row strong { font-size: 14px; }
.sun-week-goal-bar { height: 12px; background: var(--surface-2); }
.sun-week-goal-bar .goal-fill { display: block; height: 100%; transition: width 180ms ease; }
.sun-week-goal.done .goal-fill { background: linear-gradient(90deg, #8ee0ad, var(--ok)); }
.sun-goal-edit { border: 0; background: var(--warm); color: var(--accent-ink); font: inherit; font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: var(--radius-pill); cursor: pointer; }
.sun-goal-edit.ghost { background: var(--surface-2); color: var(--ink-2); }
.sun-goal-form { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; flex-wrap: wrap; }

.sun-goal-form input { width: 88px; font: inherit; font-weight: 800; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--line); }
.sun-goal-hint { font-size: 12px; font-weight: 700; color: var(--ink-3); }
.sun-path-list { display: flex; flex-direction: column; gap: 8px; }
.sun-path { display: grid; grid-template-columns: 36px 1fr auto; grid-template-areas: "ico name amt" "bar bar bar"; gap: 2px 10px; align-items: center; background: var(--surface-2); border-radius: var(--radius-lg); padding: 12px; }
.sun-path.miss { opacity: .72; }
.sun-path .sun-ico { grid-area: ico; margin: 0; width: 32px; height: 32px; }
.sun-path div:not(.goal-bar) { grid-area: name; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.sun-path strong { font-size: 14px; }
.sun-path small { font-size: 12px; color: var(--ink-2); font-weight: 700; }
.sun-path b { grid-area: amt; font-variant-numeric: tabular-nums; }
.sun-path .src-bar { grid-area: bar; margin-top: 6px; }
.sun-ico.task { background: var(--brand); }
.sun-ico.word { background: #7c6cf0; }
.sun-ico.test { background: #2e9e63; }
.src-bar { margin-top: 8px; height: 6px; }
.src-bar .goal-fill { display: block; height: 100%; }
@media (prefers-reduced-motion: reduce) {
  .sun-track.dual i, .sun-week-goal-bar .goal-fill { transition: none; }
}

@media (max-width: 1100px) {
  .sun-page { max-width: none; }
  .sun-week { height: 120px; gap: 4px; }
  .sun-col-n { font-size: 11px; }
  .sun-gap { padding: 12px; }
  .sun-gap span { font-size: 14px; line-height: 1.35; }
}
@media (max-width: 700px) {
  .sun-week { height: 108px; gap: 2px; }
  .sun-col-n { font-size: 10px; }
  .sun-track.dual i, .sun-pair, .sun-pair i { width: 7px; }
}
</style>

