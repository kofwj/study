// App.vue 与 Admin.vue 共享的格式化纯函数与常量。
// 注意：n1 对空串返回空（Admin 语义）；formatMetricValue 在调用前已挡掉空值。

export const SUBJECT_ORDER = ['语文', '数学', '英语', '科学', '道法', '体育', '音美', '综合', '围棋']

export function pad2(n) { return String(n).padStart(2, '0') }

export function n1(v) {
  if (v == null || v === '') return ''
  const x = Math.round(Number(v) * 10) / 10
  return x % 1 ? String(x) : String(Math.round(x))
}

export function isTimeMetric(m) {
  const u = String((m && m.unit) || '')
  return u.includes('秒') || u.includes('分钟')
}

export function metricToSeconds(m, v) {
  if (v == null || v === '') return null
  const n = Number(v)
  if (Number.isNaN(n)) return null
  return String((m && m.unit) || '').includes('分钟') ? n * 60 : n
}

export function secondsToMetric(m, sec) {
  if (sec == null || Number.isNaN(Number(sec))) return null
  const s = Number(sec)
  return String((m && m.unit) || '').includes('分钟') ? s / 60 : s
}

export function formatDuration(sec) {
  if (sec == null || Number.isNaN(Number(sec))) return '—'
  const totalCs = Math.max(0, Math.round(Number(sec) * 100))
  const mm = Math.floor(totalCs / 6000)
  const ss = Math.floor((totalCs % 6000) / 100)
  const cs = totalCs % 100
  return mm + "'" + pad2(ss) + '.' + pad2(cs) + '"'
}

export function formatMetricValue(m, v) {
  if (v == null || v === '') return '—'
  if (isTimeMetric(m)) {
    const n = Number(v)
    if (Number.isNaN(n)) return '—'
    const sec = String((m && m.unit) || '').includes('分钟') ? n * 60 : n
    return formatDuration(sec)
  }
  return n1(v)
}
