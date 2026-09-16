<script setup>
// 家长工作台 · 大队委（题库成绩）
//
// 这个页面存在的唯一理由：**把可信的数字和不那么可信的数字分开**。
// 选择/多选/填空是后端机器判的；问答是孩子自评的（参考答案是整句，机器判不了）；
// 2026-09-16 之前的老记录分不清是谁判的，单独算一类。
//
// 组件自己发请求（照 AdminWords.vue 的做法），孩子切换交给父组件，通过 watch(kid) 重新拉。
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  kids: { type: Array, default: () => [] },
  kid: { type: String, default: '' },
  showToast: { type: Function, required: true },
})
const emit = defineEmits(['pick-kid'])

const MODE_LABEL = { study: '学习', practice: '练习', exam: '考试' }
const data = ref({ banks: [] })
const loading = ref(false)
const showRight = ref(false)

/* 逐层容错：后端字段缺了也不能让页面炸 / 出现 undefined */
function banks() {
  const b = (data.value && data.value.banks) || []
  return Array.isArray(b) ? b : []
}
function num(v) { const n = Number(v); return Number.isFinite(n) ? n : 0 }
function pct(right, total) {
  const t = num(total)
  if (!t) return ''
  return Math.round((num(right) / t) * 100) + '%'
}
function modeLabel(m) { return MODE_LABEL[m] || '' }
function switchable() { return (props.kids || []).length > 1 }

async function load(quiet) {
  loading.value = true
  try {
    const res = await api.admin.quizSummary()
    data.value = res && typeof res === 'object' ? res : { banks: [] }
  } catch (e) {
    if (!quiet) props.showToast(e.message)
    data.value = { banks: [] }
  } finally {
    loading.value = false
  }
}

onMounted(() => load(true))
watch(() => props.kid, () => { showRight.value = false; load(true) })

const totalsLine = (b) => {
  const t = b.totals || {}
  const parts = [`做了 ${num(t.answered)} 题`, `对 ${num(t.right)}`, `错 ${num(t.wrong)}`]
  if (num(t.unjudged)) parts.push(`还有 ${num(t.unjudged)} 题没判`)
  return parts.join(' · ')
}
const visibleQuestions = (b) => {
  const qs = Array.isArray(b.questions) ? b.questions : []
  return showRight.value ? qs : qs.filter((q) => q.correct !== true)
}
const wrongCount = (b) => (Array.isArray(b.questions) ? b.questions : []).filter((q) => q.correct === false).length
const expiredExam = (b) => {
  if (!b.end_at) return false
  const d = new Date()
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return today > String(b.end_at)
}
const answerText = (arr) => (Array.isArray(arr) && arr.length ? arr.map((x) => String(x)).join(' ／ ') : '（题库里没写参考答案）')
</script>

<template>
  <section class="a-card enter">
    <div class="lock-row">
      <h3 class="grow">大队委题库成绩</h3>
      <button class="sec" :disabled="loading" @click="load(false)">{{ loading ? '读取中…' : '刷新' }}</button>
    </div>
    <div v-if="switchable()" class="frm-row mt8">
      <label class="fld grow">
        <span>看哪个孩子</span>
        <select :value="kid" @change="emit('pick-kid', $event.target.value)">
          <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
        </select>
      </label>
    </div>
    <p class="dim">
      「机器判」= 单选、多选、填空题由后端判分（孩子改不了）；
      「孩子自评」= 问答题，参考答案是整句话，只能孩子自己判 —— 数字仅供参考，下面能看到他到底写了什么。
    </p>
  </section>

  <section v-if="!banks().length" class="a-card enter">
    <p class="dim mt6">{{ loading ? '正在读取…' : '这个孩子还没有做过大队委的题。' }}</p>
  </section>

  <section v-for="b in banks()" :key="b.bank_id" class="a-card enter">
    <h3>{{ b.name || b.bank_id }}</h3>
    <p class="dim mt6">
      练了 {{ num(b.sessions) }} 次 · {{ num(b.days) }} 天 ·
      最近一次：{{ b.last_date || '—' }}<span v-if="modeLabel(b.last_mode)">（{{ modeLabel(b.last_mode) }}）</span>
      <span v-if="b.end_at"> · 考试日期 {{ b.end_at }}</span>
    </p>
    <p v-if="expiredExam(b)" class="dim mt6">这场考试已经结束。</p>

    <div class="frm-row mt14">
      <div class="fld">
        <span>机器判分</span>
        <b>{{ num((b.auto || {}).right) }} / {{ num((b.auto || {}).total) }}</b>
        <small class="dim">{{ pct((b.auto || {}).right, (b.auto || {}).total) || '—' }}</small>
      </div>
      <div class="fld">
        <span>孩子自评</span>
        <b>{{ num((b.self || {}).right) }} / {{ num((b.self || {}).total) }}</b>
        <small class="dim">{{ pct((b.self || {}).right, (b.self || {}).total) || '—' }}</small>
      </div>
      <div v-if="num((b.legacy || {}).total)" class="fld">
        <span>改版前</span>
        <b>{{ num((b.legacy || {}).total) }} 题</b>
        <small class="dim">分不清谁判的</small>
      </div>
    </div>
    <p class="dim mt6">{{ totalsLine(b) }}</p>

    <table v-if="(b.by_kind || []).length" class="a-table mt14">
      <thead>
        <tr><th>题型</th><th>做了</th><th>对</th><th>错</th><th>判分方式</th></tr>
      </thead>
      <tbody>
        <tr v-for="k in b.by_kind" :key="k.kind">
          <td>{{ k.label || k.kind }}</td>
          <td>{{ num(k.answered) }}</td>
          <td>{{ num(k.right) }}</td>
          <td>{{ num(k.wrong) }}</td>
          <td>
            <span class="badge" :style="k.judged_by === 'self' ? 'background:#FFF4E0;color:#8A5A00' : 'background:#EAF6EF;color:#2F8F5B'">
              {{ k.judged_label || (k.judged_by === 'self' ? '孩子自评' : '机器判') }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="lock-row mt14">
      <span class="badge">最近一次逐题</span>
      <span class="grow dim">
        {{ showRight ? '答对答错都看着' : (wrongCount(b) ? `只看错的 ${wrongCount(b)} 道` : '这次没有错题 🎉') }}
      </span>
      <button class="sec" @click="showRight = !showRight">{{ showRight ? '只看错的' : '也看答对的' }}</button>
    </div>
    <div v-if="!(b.questions || []).length" class="dim mt6">这次还没有逐题记录。</div>
    <div v-else-if="!visibleQuestions(b).length" class="dim mt6">这次没有错题 🎉</div>
    <div v-for="q in visibleQuestions(b)" :key="q.n" class="member-row" :class="{ err: q.correct === false }">
      <div class="member-info">
        <b>
          第 {{ num(q.n) }} 题
          <span class="badge">{{ q.label || q.kind }}</span>
          <span v-if="q.correct === true" class="badge" style="background:#EAF6EF;color:#2F8F5B">对</span>
          <span v-else-if="q.correct === false" class="badge" style="background:#FDEEEE;color:#A33">错</span>
          <span v-else class="badge">未判</span>
          <span class="dim">{{ q.judged_label || '' }}</span>
        </b>
        <div class="dim mt6">{{ q.stem }}</div>
        <div class="mt6">
          <span class="dim">他写的：</span>
          <b>{{ q.got || '（没写）' }}</b>
        </div>
        <div class="dim mt6">参考答案：{{ answerText(q.answer) }}</div>
      </div>
    </div>
  </section>
</template>
