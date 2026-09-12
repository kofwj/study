<script setup>
// 阳光统计页：周趋势、五条途径、还没做好清单。
// 账本数据读 store.recentLedger；dailyTodo/studyNext 是父级计算属性，props 传入；
// 点跳转 emit('navigate', gap)，由父级切 tab 或打开单词练习。
import { computed } from 'vue'
import { TrendingUp, Target, BookOpen, Globe, CalendarDays, FileText, Gift } from '@lucide/vue'
import { recentLedger, data, wordDueCard, wordNewCard, reviewDue, todayPenalty } from '../store.js'

const props = defineProps({
  dailyTodo: { type: Array, default: () => [] },
  studyNext: { type: Array, default: () => [] },
})
const emit = defineEmits(['navigate'])

function ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const SUN_EARN = new Set(['task', 'daily', 'word_daily', 'word_perfect', 'test', 'box', 'milestone'])
const SUN_REVERT = new Set(['cancel', 'test_cancel'])
const SUN_SPEND = new Set(['redeem'])
const SUN_PATHS = [
  { id: 'task', name: '课文任务', hint: '把今天的课往前推', reasons: ['task'], icon: BookOpen, tab: null },
  { id: 'word', name: '英语单词', hint: '复习或新词还没写完', reasons: ['word_daily', 'word_perfect'], icon: Globe, tab: '英语' },
  { id: 'daily', name: '每日打卡', hint: '今天的打卡还空着', reasons: ['daily'], icon: CalendarDays, tab: '今日推荐' },
  { id: 'test', name: '单元测试', hint: '测完告诉家长登分', reasons: ['test'], icon: FileText, tab: null },
  { id: 'box', name: '宝箱连击', hint: '连续打卡才会开箱', reasons: ['box', 'milestone'], icon: Gift, tab: null },
]
const WD = '日一二三四五六'
function pocketRow(r) { return (r.account || 'pocket') === 'pocket' }
function sunDelta(r) { return Number(r.delta) || 0 }
function isSunEarn(r) { return pocketRow(r) && SUN_EARN.has(r.reason) }
function isSunRevert(r) { return pocketRow(r) && SUN_REVERT.has(r.reason) }
function isSunSpend(r) { return pocketRow(r) && SUN_SPEND.has(r.reason) && sunDelta(r) < 0 }
function sunSum(rows, pred) {
  return rows.filter(pred).reduce((s, r) => s + Math.abs(sunDelta(r)), 0)
}
function sunSumSigned(rows, pred) {
  return rows.filter(pred).reduce((s, r) => s + sunDelta(r), 0)
}
const sunshineStats = computed(() => {
  const rows = (recentLedger.value || []).filter(pocketRow)
  const now = new Date()
  const dayList = []
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
    dayList.push(ymd(d))
  }
  const weekDates = dayList.slice(7)
  const prevDates = dayList.slice(0, 7)
  const weekSet = new Set(weekDates)
  const prevSet = new Set(prevDates)
  const days = weekDates.map((iso, i) => {
    const dayRows = rows.filter(r => r.date === iso)
    const inn = Math.max(0, sunSumSigned(dayRows, r => isSunEarn(r) || isSunRevert(r)))
    const out = sunSum(dayRows, isSunSpend)
    const [yy, mm, dd] = iso.split('-').map(Number)
    const d = new Date(yy, mm - 1, dd) // 本地时区解析，避免 'YYYY-MM-DD' 被当 UTC 导致星期错一天
    return { date: iso, wd: i === 6 ? '今天' : WD[d.getDay()], inn, out, today: i === 6, quiet: inn === 0 }
  })
  const weekIn = Math.max(0, sunSumSigned(rows.filter(r => weekSet.has(r.date)), r => isSunEarn(r) || isSunRevert(r)))
  const weekOut = days.reduce((s, d) => s + d.out, 0)
  const maxAbs = Math.max(1, ...days.map(d => Math.max(d.inn, d.out)))
  const paths = SUN_PATHS.map(p => {
    const week = sunSum(rows.filter(r => weekSet.has(r.date) && p.reasons.includes(r.reason)), isSunEarn)
    const prev = sunSum(rows.filter(r => prevSet.has(r.date) && p.reasons.includes(r.reason)), isSunEarn)
    let vs = '这周还没有'
    if (week > 0 && prev === 0) vs = '这周刚开始有'
    else if (week > prev) vs = `比上周多 ${week - prev}`
    else if (week < prev) vs = `比上周少 ${prev - week}`
    else if (week > 0) vs = '和上周差不多'
    return { ...p, week, prev, vs }
  })
  const maxPath = Math.max(1, ...paths.map(p => p.week), 0)
  const top = [...paths].sort((a, b) => b.week - a.week)[0]
  return {
    days, weekIn, weekOut, maxAbs, paths, maxPath,
    quiet: days.filter(d => d.quiet && !d.today),
    topName: top && top.week ? top.name : '',
  }
})
const sunshineGaps = computed(() => {
  const g = []
  const st = sunshineStats.value
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
  const gap = sunshineGaps.value[0]
  if (gap) return gap.text
  if (st.topName) return `这周阳光主要来自${st.topName}`
  return '去做任务，口袋就会亮起来'
})
function goSunGap(g) {
  emit('navigate', g)
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

    <div v-if="sunshineGaps.length" class="sun-gaps">
      <h3 class="section-title"><Target class="ico" :size="18" /> 还没做好</h3>
      <button v-for="g in sunshineGaps.slice(0, 5)" :key="g.id" type="button" class="sun-gap" :disabled="!g.go && !g.lane" @click="goSunGap(g)">
        <span>{{ g.text }}</span>
        <em v-if="g.go || g.lane">去看看</em>
      </button>
    </div>
    <div v-else class="sun-gaps ok">
      <p>这周该做的都有阳光进账，继续保持。</p>
    </div>

    <div class="bank-operations">
      <div class="op-header">
        <h3>这周趋势</h3>
        <span class="sun-week-sum">攒 {{ sunshineStats.weekIn }} · 兑换 {{ sunshineStats.weekOut }}</span>
      </div>
      <div class="sun-week">
        <div v-for="d in sunshineStats.days" :key="d.date" class="sun-col" :class="{ quiet: d.quiet && !d.today }">
          <span class="sun-col-n" :class="{ zero: !d.inn }">{{ d.inn ? '+' + d.inn : '0' }}</span>
          <div class="sun-track dual">
            <i class="in" :style="{ height: Math.max(d.inn ? 8 : 0, Math.round(d.inn / sunshineStats.maxAbs * 68)) + 'px' }"></i>
            <i class="out" :style="{ height: Math.max(d.out ? 8 : 0, Math.round(d.out / sunshineStats.maxAbs * 68)) + 'px' }"></i>
          </div>
          <span :class="{ today: d.today }">{{ d.wd }}</span>
        </div>
      </div>
      <p class="sun-week-legend"><i class="in"></i> 攒到的 <i class="out"></i> 商店兑换</p>
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
