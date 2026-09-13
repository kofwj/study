import { ref, watch, onUnmounted } from 'vue'

function prefersReducedMotion() {
  try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) }
  catch { return false }
}

/** 数字从旧值滚到新值。reduced-motion 或时长过短时直接跳到目标。 */
export function useCountUp(source, { duration = 280 } = {}) {
  const shown = ref(Number(typeof source === 'function' ? source() : source.value) || 0)
  let timer = 0
  function jump(n) {
    if (timer) cancelAnimationFrame(timer)
    timer = 0
    shown.value = n
  }
  function run(from, to) {
    if (from === to || prefersReducedMotion() || duration < 16) {
      jump(to)
      return
    }
    const start = performance.now()
    function tick(now) {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - t) * (1 - t)
      shown.value = Math.round(from + (to - from) * eased)
      if (t < 1) timer = requestAnimationFrame(tick)
      else { timer = 0; shown.value = to }
    }
    timer = requestAnimationFrame(tick)
  }
  watch(() => Number(typeof source === 'function' ? source() : source.value) || 0, (n, prev) => {
    run(prev == null ? n : prev, n)
  })
  onUnmounted(() => { if (timer) cancelAnimationFrame(timer) })
  return shown
}
