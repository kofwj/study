<script setup>
// 每日打卡指标弹窗：数值/时间(分:秒.百分秒)/围棋赢局录入，负责把输入拼成 metrics 载荷。
// 用法：父组件 <DailyDialog ref="dailyRef" @submit="submitDaily" />，
// 调 dailyRef.value.open(task) 打开；提交只 emit，父级调 dailyRef.value.close() 关闭。
import { reactive, computed } from 'vue'
import { Sun } from '@lucide/vue'
import { isTimeMetric, pad2, secondsToMetric, isGoPlay, goWinCount } from '../format.js'

const emit = defineEmits(['submit'])

const dailyDialog = reactive({ open: false, task: null, vals: {}, time: {} })
// 时间输入的函数 ref：秒填满 2 位后自动跳百分秒（替代旧的 getElementById）
const csEls = {}
function setCsEl(id, el) { if (el) csEls[id] = el; else delete csEls[id] }

const goDialogWins = computed(() => goWinCount(dailyDialog.vals))
function dailySunshineHint(task) {
  if (!task) return ''
  if (isGoPlay(task)) return `看「赢了几局」：填 1 或更多才给 +${task.sunshine || 5} 阳光。赢 0 局（空着也算 0）不给，输了几局不影响`
  return `打卡 +${task.sunshine || 5} 阳光`
}
function dailySubmitLabel(task) {
  if (isGoPlay(task) && goDialogWins.value < 1) return '记下对局，这次没有阳光'
  return '打卡，赚阳光'
}

function open(task) {
  dailyDialog.task = task
  dailyDialog.vals = {}
  dailyDialog.time = {}
  for (const m of task.metrics) {
    dailyDialog.vals[m.id] = ''
    if (isTimeMetric(m)) dailyDialog.time[m.id] = { min: '', sec: '', cs: '' }
  }
  dailyDialog.open = true
}
function close() { dailyDialog.open = false }
defineExpose({ open, close })

function clampDigits(v, max) {
  const digits = String(v ?? '').replace(/\D/g, '').slice(0, 2)
  if (digits === '') return ''
  const n = Math.max(0, Math.min(max, Number(digits)))
  return digits.length === 2 ? pad2(n) : String(n)
}
function onTimePart(id, field, event, max) {
  const next = clampDigits(event.target.value, max)
  dailyDialog.time[id][field] = next
  event.target.value = next
  if (field === 'sec' && next.length === 2) csEls[id]?.focus()
}
function timePartsToSeconds(t) {
  if (!t) return null
  const has = (t.min !== '' && t.min != null) || (t.sec !== '' && t.sec != null) || (t.cs !== '' && t.cs != null)
  if (!has) return null
  const mm = Number(t.min)
  const ss = Number(t.sec)
  const cs = Number(t.cs)
  const total = (Number.isNaN(mm) ? 0 : Math.max(0, mm)) * 60
    + (Number.isNaN(ss) ? 0 : Math.max(0, Math.min(59, ss)))
    + (Number.isNaN(cs) ? 0 : Math.max(0, Math.min(99, cs))) / 100
  return Math.round(total * 100) / 100
}
function submit(event) {
  const metrics = {}
  for (const m of dailyDialog.task.metrics) {
    if (isTimeMetric(m)) {
      const totalSec = timePartsToSeconds(dailyDialog.time[m.id])
      if (totalSec == null) continue
      const stored = secondsToMetric(m, totalSec)
      if (stored != null && !Number.isNaN(stored)) metrics[m.id] = stored
    } else {
      const raw = dailyDialog.vals[m.id]
      if (raw === '' || raw == null) continue
      const v = Number(raw)
      if (!Number.isNaN(v)) metrics[m.id] = v
    }
  }
  emit('submit', { task: dailyDialog.task, metrics, event })
}
</script>

<template>
  <div v-if="dailyDialog.open" class="mask" @click.self="close">
    <div class="shop-modal enter">
      <h3>{{ dailyDialog.task.name }}</h3>
      <p v-if="dailyDialog.task.note" class="daily-dialog-note">怎么做：{{ dailyDialog.task.note }}</p>
      <p v-if="isGoPlay(dailyDialog.task)" class="daily-dialog-award">{{ dailySunshineHint(dailyDialog.task) }}</p>
      <div v-for="m in dailyDialog.task.metrics" :key="m.id" class="metric">
        <label>{{ m.label }}</label>
        <div v-if="m.note" class="metric-note">{{ m.note }}</div>
        <div v-if="isTimeMetric(m)" class="time-row">
          <label class="time-part"><input :value="dailyDialog.time[m.id].min" type="number" inputmode="numeric" min="0" placeholder="0" @input="dailyDialog.time[m.id].min = $event.target.value === '' ? '' : Math.max(0, Math.floor(Number($event.target.value) || 0))" /><span>分</span></label>
          <span class="time-sep">:</span>
          <label class="time-part"><input :value="dailyDialog.time[m.id].sec" type="text" inputmode="numeric" maxlength="2" placeholder="00" @input="onTimePart(m.id, 'sec', $event, 59)" /><span>秒</span></label>
          <span class="time-sep">.</span>
          <label class="time-part"><input :ref="el => setCsEl(m.id, el)" :value="dailyDialog.time[m.id].cs" type="text" inputmode="numeric" maxlength="2" placeholder="00" @input="onTimePart(m.id, 'cs', $event, 99)" /><span>百分秒</span></label>
        </div>
        <input v-else v-model.number="dailyDialog.vals[m.id]" type="number" inputmode="decimal" min="0" :placeholder="m.unit" />
      </div>
      <button class="do big" @click="submit($event)">{{ dailySubmitLabel(dailyDialog.task) }} <Sun v-if="!(isGoPlay(dailyDialog.task) && goDialogWins < 1)" class="ico" :size="15" /></button>
      <button class="ghost" @click="close">取消</button>
    </div>
  </div>
</template>

<style scoped>
.metric { margin-bottom: 10px; }
.metric label { display: block; font-size: 13px; margin-bottom: 4px; }
.daily-dialog-note, .metric-note { margin: -4px 0 8px; color: var(--ink-3); font-size: 12px; line-height: 1.5; }
.daily-dialog-award { margin: -2px 0 10px; color: var(--accent-ink); font-size: 13px; line-height: 1.5; font-weight: 700; }
.metric-note { margin: -1px 0 4px; }
.time-row { display: flex; gap: 6px; align-items: center; }
.time-part { display: flex; flex-direction: column; align-items: stretch; gap: 4px; flex: 1; margin: 0; min-width: 0; }
.time-part span { font-size: 12px; font-weight: 700; color: var(--ink-3); text-align: center; }
.time-part input { width: 100%; text-align: center; font-variant-numeric: tabular-nums; font-weight: 800; font-size: 22px; }
.time-sep { font-weight: 800; font-size: 22px; color: var(--ink-2); padding-bottom: 16px; }
.metric input { width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--radius-sm); font-size: 15px; }
</style>
