<script setup>
// 家长工作台 · 总览页（纯视图）
// 数据仍由 Admin.vue 的按页加载（loadCore / ensureSection / 各 pack）持有，
// 子组件只渲染 + 抛动作；这样侧栏来回切换不会重拉（v0.3.23 的语义不变）。
import { ref, computed } from 'vue'
import { n1, isTimeMetric, formatMetricValue } from '../format.js'

const props = defineProps({
  weekly: { type: Object, required: true },
  familyToday: { type: Object, required: true },
  insightKids: { type: Array, default: () => [] },
  daily: { type: Array, default: () => [] },
  dailyHist: { type: Object, default: () => ({}) },
  fitnessGoals: { type: Object, default: () => ({}) },
  reviewCount: { type: Number, default: 0 },
  pendingRedeem: { type: Number, default: 0 },
  isMultiKid: { type: Boolean, default: false },
  selectedKid: { type: String, default: '' },
  kidName: { type: String, default: '' },
  parentName: { type: String, default: '' },
  weeklyGoal: { type: Number, default: 50 },
  weeklyGoalBusy: { type: Boolean, default: false },
  subjectName: { type: Function, required: true },
})
const emit = defineEmits([
  'update:weeklyGoal', 'save-weekly-goal', 'go-section',
  'pick-kid', 'go-review-kid', 'go-insight', 'undo-daily',
  'save-family-goal', 'close-family-goal',
])

// —— B4 全家共同目标：只渲染 + 抛动作，接口在壳里 ——
const goalForm = ref({ metric: 'cards', target: 10, reward: 5 })
const goal = computed(() => (props.familyToday && props.familyToday.family_goal) || null)
const goalPct = computed(() => {
  const p = goal.value && goal.value.progress
  if (!p || !p.target) return 0
  return Math.min(100, Math.round((p.value / p.target) * 100))
})
const goalKids = computed(() => ((goal.value && goal.value.by_kid) || []).map((x) => `${x.name} ${x.value}`).join(' · '))
function startGoal() {
  const t = Math.max(1, Math.min(999, Math.round(Number(goalForm.value.target) || 0)))
  const r = Math.max(0, Math.min(20, Math.round(Number(goalForm.value.reward) || 0)))
  emit('save-family-goal', { metric: goalForm.value.metric, target: t, reward: r })
}

// 「本周详情」折叠：属于这一页，切页回来从收起开始（B1 的减负要求）
const dashWeekOpen = ref(false)

/* ===== 以下计算原先在 Admin.vue，现改为读 props ===== */
const dayNet = (d) => Number(d && (d.net != null ? d.net : d.earned)) || 0
const maxDayEarn = computed(() => Math.max(1, ...(props.weekly.days || []).map((d) => Math.abs(dayNet(d)))))
const subjectRows = computed(() => [...(props.weekly.by_subject || [])].sort((a, b) => (b.sun || 0) - (a.sun || 0)))
const maxSubj = computed(() => Math.max(1, ...subjectRows.value.map((s) => s.sun || 0)))
const weekNet = (w) => Number(w && (w.net != null ? w.net : w.earned)) || 0
const weekPoints = computed(() => {
  const ws = props.weekly.weeks || []
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
function familyTodayStatus(k) {
  if (k.review_due > 0) return { cls: 'amber', text: '今日复习 ' + k.review_due + ' 项' }
  if (!k.checkin) return { cls: 'gray', text: '还没来' }
  return { cls: 'green', text: '今天来了' }
}
function completedDelta(k) {
  const d = (k.completed || 0) - (k.completed_last || 0)
  if (d > 0) return '比上周多 ' + d + ' 张'
  if (d < 0) return '比上周少 ' + (-d) + ' 张'
  return '和上周差不多'
}
const masteredLine = computed(() => {
  const rows = props.weekly.mastered_by_kid || []
  if (!rows.length) return ''
  return rows.map(r => r.name + '：' + (r.items || []).join('、')).join('；')
})
const greet = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '上午好'
  if (h < 18) return '下午好'
  return '晚上好'
})
const checkinCount = computed(() => (props.familyToday.kids || []).filter(k => k.checkin).length)
const kidCount = computed(() => (props.familyToday.kids || []).length)
const dashAttention = computed(() => {
  if (props.reviewCount) return { text: `今天有 ${props.reviewCount} 项复习到期`, go: 'review', label: '去复习' }
  if (props.pendingRedeem) return { text: `有 ${props.pendingRedeem} 笔兑换待同意`, go: 'approve', label: '去审批' }
  return { text: '', go: '', label: '' }
})
function lastMetric(d, mid) {
  if (d.today_metrics && d.today_metrics[mid] != null && d.today_metrics[mid] !== '') return Number(d.today_metrics[mid])
  const hist = props.dailyHist[d.id] || []
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
const dashDailies = computed(() => (props.daily || []).map(d => ({
  id: d.id, name: d.name, subject: d.subject_id || '', done: !!d.done_today,
})))
const peCards = computed(() => {
  const cards = []
  for (const d of props.daily || []) {
    const metrics = d.metrics || []
    if (!metrics.length) continue
    const g = props.fitnessGoals[d.id]
    if (!g) continue
    const hist = props.dailyHist[d.id] || []
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
</script>

<template>
    <section class="a-card enter dash">
      <h3>{{ greet }}，{{ parentName || '家长' }}</h3>
      <div v-if="dashAttention.text" class="w-next">
        <strong>待处理</strong>
        <span>{{ dashAttention.text }}</span>
        <button v-if="dashAttention.go" class="ok" @click="$emit('go-section', dashAttention.go)">{{ dashAttention.label }}</button>
      </div>
      <div class="dash-stats">
        <button type="button" class="dash-stat" @click="$emit('go-section', 'review')">
          <span>待复习</span><b>{{ reviewCount }}</b>
        </button>
        <button type="button" class="dash-stat" @click="$emit('go-section', 'approve')">
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
            <span class="dim">{{ subjectName(d.subject) }}</span>
            <button v-if="d.done" type="button" class="ghost-s dash-undo" @click="$emit('undo-daily', d)">撤销</button>
          </div>
        </div>
      </template>
      <h4 class="w-h">本周阳光{{ kidName ? ' · ' + kidName : '' }}</h4>
      <p class="lead dim">{{ weekly.week_start }} ~ {{ weekly.week_end }}</p>
      <div class="w-summary">
        <div class="w-box"><span>本周赚</span><b>+{{ weekly.total_earned }}</b></div>
        <div class="w-box"><span>兑换花</span><b>-{{ weekly.total_spent }}</b></div>
        <div class="w-box"><span>当前余额</span><b>{{ weekly.balance }}</b></div>
      </div>
      <div class="w-subj-row goal-row">
        <span class="dim">本周目标</span>
        <input :value="weeklyGoal" @input="$emit('update:weeklyGoal', Number($event.target.value))" type="number" min="0" max="10000" class="w-num" />
        <button class="ok" @click="$emit('save-weekly-goal')" :disabled="weeklyGoalBusy">保存目标</button>
      </div>
      <div v-if="masteredLine" class="w-mastered">本周已掌握：<b>{{ masteredLine }}</b></div>
      <div v-if="isMultiKid && (weekly.kids || []).length" class="w-kids">
        <div v-for="k in weekly.kids" :key="k.id" class="w-box" :class="{ on: k.current }" @click="$emit('pick-kid', k.id)">
          <span>{{ k.name }}</span><b>+{{ k.earned }}</b>
          <i class="dim">完成 {{ k.completed || 0 }} 张 · {{ completedDelta(k) }}</i>
          <i class="dim">花 {{ k.spent }} · 连击 {{ k.streak }}</i>
        </div>
      </div>
      <template v-if="isMultiKid && kidCount">
        <h4 class="w-h">孩子们</h4>
        <div class="fam-today">
          <button v-for="k in familyToday.kids" :key="k.kid_id" type="button"
            class="fam-card" :class="{ on: selectedKid === k.kid_id }" @click="$emit('pick-kid', k.kid_id)">
            <span class="apv-name">{{ k.name }}</span>
            <em class="fam-st" :class="familyTodayStatus(k).cls">{{ familyTodayStatus(k).text }}</em>
            <span class="dim">完成 {{ k.completed_today }} · 连击 {{ k.streak }} · 余额 {{ k.balance }}</span>
            <span v-if="k.review_due > 0" class="ok fam-go" @click.stop="$emit('go-review-kid', k)">去复习</span>
          </button>
        </div>
      </template>
      <p v-else-if="!kidCount" class="dim">还没有孩子，到「家庭」里添加。</p>
      <template v-if="(insightKids || []).length">
        <h4 class="w-h">本周盯点</h4>
        <div v-for="row in insightKids" :key="row.kid_id" class="apv-row">
          <div class="apv-info">
            <span v-if="isMultiKid" class="apv-name">{{ row.name }}</span>
            <span class="dim">{{ row.insight ? row.insight.text : '无' }}</span>
          </div>
          <button v-if="row.insight && row.insight.action" class="ok" @click="$emit('go-insight', row)">去解决</button>
        </div>
      </template>
      <!-- B4 全家共同目标（达标每人发 0–20 阳光，默认 5；同时只 1 个进行中） -->
      <h4 class="w-h">全家共同目标</h4>
      <template v-if="goal">
        <div class="w-subj-row">
          <div class="w-subj-track"><i :style="{ width: goalPct + '%' }"></i></div>
          <span class="w-subj-num">{{ goal.goal.metric_label }} {{ goal.progress.value }}/{{ goal.progress.target }} {{ goal.goal.unit }}</span>
        </div>
        <p class="dim">
          <template v-if="goal.goal.status === 'reached'">已达成本周目标，每人 +{{ goal.goal.reward }} 阳光<template v-if="goal.goal.reached_at">（{{ goal.goal.reached_at }}）</template></template>
          <template v-else>全家还差 {{ goal.progress.remaining }} {{ goal.goal.unit }}<template v-if="goal.goal.reward === 0">（这个目标不发阳光）</template></template>
        </p>
        <p v-if="goalKids" class="dim">每娃贡献：{{ goalKids }}</p>
        <button type="button" class="ghost-s" @click="$emit('close-family-goal')">关掉目标</button>
      </template>
      <template v-else>
        <p class="dim">还没有共同目标。全家一起完成一件小事：本周累计完成卡数 / 运动次数 / 签到天数，达标每人发阳光。</p>
        <div class="frm-row">
          <label class="fld"><span>指标</span>
            <select v-model="goalForm.metric">
              <option value="cards">完成卡数（张）</option>
              <option value="sport">运动次数（次）</option>
              <option value="checkin_days">签到天数（天）</option>
            </select>
          </label>
          <label class="fld w84"><span>目标</span><input v-model.number="goalForm.target" type="number" min="1" max="999" /></label>
          <label class="fld w84"><span>每人阳光</span><input v-model.number="goalForm.reward" type="number" min="0" max="20" /></label>
          <button type="button" class="ok" @click="startGoal">设好开始</button>
        </div>
      </template>
      <button type="button" class="ghost-s rules-toggle" @click="dashWeekOpen = !dashWeekOpen">{{ dashWeekOpen ? '收起本周详情' : '本周详情' }}</button>
      <template v-if="dashWeekOpen">
        <div class="w-summary">
          <div v-if="weekly.penalty_net" class="w-box"><span>本周约定</span><b>{{ weekly.penalty_net }}</b></div>
          <div class="w-box"><span>净增</span><b>{{ weekly.net }}</b></div>
          <div class="w-box"><span>本周签到</span><b>{{ weekly.checkins }} 天</b></div>
        </div>
        <template v-if="peCards.length">
          <h4 class="w-h">体测数值</h4>
          <div class="pe-grid">
            <div v-for="c in peCards" :key="c.key" class="pe-card">
              <span class="dim">{{ c.name }}</span>
              <strong>{{ c.label }}</strong>
              <b>{{ formatMetricValue({ unit: c.unit }, c.last) }}<small v-if="!isTimeMetric({ unit: c.unit })">{{ c.unit }}</small></b>
              <em class="fam-st" :class="c.cls">{{ c.gap || c.status }}{{ c.today ? ' · 今天记的' : '' }}</em>
              <div v-if="c.goal" class="w-subj-row pe-std">
                <div class="w-subj-track"><i :style="{ width: c.pct + '%' }"></i></div>
                <span class="w-subj-num">达标 {{ n1(c.goal.pass) }}{{ c.unit }}</span>
              </div>
              <span class="dim">个人最好 {{ formatMetricValue({ unit: c.unit }, c.pb) }}{{ c.series.length ? ' · ' + c.series.length + ' 次' : '' }}</span>
              <svg v-if="c.pts" viewBox="0 0 288 56" class="pe-svg" preserveAspectRatio="none">
                <polyline :points="c.pts" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
          </div>
        </template>
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
      </template>
    </section>
</template>
