<script setup>
// 每日任务趋势图弹窗：数值维度画折线+个人纪录，无数值维度画近 14 天打卡日历。
// 用法：父组件 <TrendChart ref="chartRef" />，调 chartRef.value.open(task)。
import { reactive, computed } from 'vue'
import { TrendingUp, Medal } from '@lucide/vue'
import { api } from '../api.js'
import { formatMetricValue } from '../format.js'
import { showToast } from '../store.js'

const chartOpen = reactive({ open: false, task: null, history: [] })

async function open(task) {
  try {
    const hist = await api.dailyHistory(task.id)
    chartOpen.task = task
    chartOpen.history = hist
    chartOpen.open = true
  } catch (e) { showToast(e.message) }
}
defineExpose({ open })

// 为某维度算趋势折线坐标 + 个人纪录定位
function lineFor(m) {
  const hist = (chartOpen.history || []).filter(h => h.metrics && h.metrics[m.id] != null && h.metrics[m.id] !== '')
  const vals = hist.map(h => Number(h.metrics[m.id]))
  if (!vals.length) return { pts: '', dots: [], min: '—', max: '—', bestY: 0 }
  const min = Math.min(...vals), max = Math.max(...vals)
  const span = (max - min) || 1
  const W = 288, H = 92, padL = 14, padR = 14, padT = 12, padB = 20
  const n = vals.length
  const bestVal = m.direction === 'lower_better' ? min : max
  const dots = vals.map((v, i) => {
    const x = n === 1 ? (W - padL - padR) / 2 + padL : padL + i * (W - padL - padR) / (n - 1)
    const y = padT + (1 - (v - min) / span) * (H - padT - padB)
    return { x: +x.toFixed(1), y: +y.toFixed(1), v, best: v === bestVal }
  })
  const bestY = dots.find(p => p.best).y
  return { pts: dots.map(p => `${p.x},${p.y}`).join(' '), dots, min, max, bestY,
           sum: vals.reduce((a, b) => a + b, 0), count: n }
}

// 无数值维度任务（眼保健操/阅读/练字）：近 14 天打卡日历
const chartDays = computed(() => {
  const done = new Set((chartOpen.history || []).map(h => h.date))
  const days = []
  const now = new Date()
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    days.push({ date: iso, daynum: d.getDate(), done: done.has(iso), today: i === 0 })
  }
  return days
})
</script>

<template>
  <div v-if="chartOpen.open" class="mask" @click.self="chartOpen.open = false">
    <div class="shop-modal chart-modal">
      <h3><TrendingUp class="ico" :size="18" /> {{ chartOpen.task?.name }} 成长趋势</h3>

      <div v-if="!chartOpen.history.length" class="dim-s">还没打过卡，坚持一下吧！</div>

      <!-- 有数值维度：折线图 + 个人纪录 -->
      <template v-if="chartOpen.history.length && (chartOpen.task?.metrics || []).length">
        <div v-for="m in chartOpen.task.metrics" :key="m.id" class="chart-block">
          <div class="chart-head">
            <span class="chart-title">{{ m.label }}</span>
            <span class="chart-scale">{{ formatMetricValue(m, lineFor(m).min) }} ~ {{ formatMetricValue(m, lineFor(m).max) }}</span>
          </div>
          <svg viewBox="0 0 288 92" class="chart-svg" preserveAspectRatio="none">
            <line v-if="lineFor(m).dots.length" x1="14" :y1="lineFor(m).bestY" x2="274" :y2="lineFor(m).bestY" class="chart-pb-line" />
            <polyline :points="lineFor(m).pts" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            <circle v-for="(p, i) in lineFor(m).dots" :key="i" :cx="p.x" :cy="p.y" :r="p.best ? 5 : 3.5" :fill="p.best ? 'var(--danger)' : 'var(--accent)'" stroke="#fff" stroke-width="1.5">
              <title>{{ formatMetricValue(m, p.v) }}</title>
            </circle>
          </svg>
          <div class="chart-pb"><Medal class="ico" :size="13" /> 个人纪录 {{ formatMetricValue(m, chartOpen.task.pb?.[m.id]) }} · 共 {{ lineFor(m).count }} 次</div>
        </div>
      </template>

      <!-- 无数值维度：打卡日历 -->
      <template v-else-if="chartOpen.history.length">
        <div class="cal-block">
          <div class="chart-head">
            <span class="chart-title">坚持打卡</span>
            <span class="chart-scale">共打卡 {{ chartOpen.history.length }} 次</span>
          </div>
          <div class="cal-row">
            <div v-for="d in chartDays" :key="d.date" class="cal-cell" :class="{ on: d.done, today: d.today }">
              {{ d.daynum }}
            </div>
          </div>
          <div class="cal-legend">近 14 天 · 绿色=已打卡 · 橙色框=今天</div>
        </div>
      </template>

      <button class="ghost" @click="chartOpen.open = false">关闭</button>
    </div>
  </div>
</template>

<style scoped>
.chart-modal { max-width: 460px; max-height: 86vh; overflow-y: auto; }
.chart-block { margin-bottom: 12px; padding: 10px 12px; background: var(--surface-2); border-radius: var(--radius-md); }
.chart-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.chart-title { font-weight: 700; font-size: 14px; color: var(--ink); }
.chart-scale { font-size: 12px; color: var(--ink-3); }
.chart-svg { width: 100%; height: 92px; display: block; }
.chart-pb-line { stroke: var(--danger); stroke-width: 1.5; stroke-dasharray: 4 4; opacity: .55; }
.chart-pb { font-size: 12px; color: var(--accent-ink); margin-top: 6px; }
.cal-block { padding: 10px 12px; background: var(--surface-2); border-radius: var(--radius-md); }
.cal-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.cal-cell { width: 34px; height: 34px; border-radius: var(--radius-sm); background: var(--surface-2); color: var(--ink-3); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; border: 2px solid transparent; }
.cal-cell.on { background: var(--ok); color: #fff; }
.cal-cell.today { border-color: var(--accent); }
.cal-legend { font-size: 11px; color: var(--ink-3); margin-top: 8px; }
</style>
