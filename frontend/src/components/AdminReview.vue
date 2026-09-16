<script setup>
// 家长工作台 · 今日复习（纯视图）
// reviewDue / weakPoints 由 Admin.vue 的 review 包与 task 包持有；这里只筛选与展示。
import { ref, computed, watch } from 'vue'

const props = defineProps({
  reviewDue: { type: Array, default: () => [] },
  weakPoints: { type: Array, default: () => [] },
  kid: { type: String, default: '' },
  subjectName: { type: Function, required: true },
})
defineEmits(['judge', 'go-section'])

// 科目筛选属于这一页；换孩子时重置（原来由壳的 switchKid 负责）
const reviewSubject = ref('')
const reviewSubjects = computed(() => {
  const ids = [...new Set((props.reviewDue || []).map(x => x.subject_id).filter(Boolean))]
  return ids
})
const filteredReviewDue = computed(() => {
  const rows = props.reviewDue || []
  return reviewSubject.value ? rows.filter(x => x.subject_id === reviewSubject.value) : rows
})
function weakPointTiming(x) {
  if (!x.review_due_at) return '等待安排'
  const now = new Date()
  const todayLocal = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  if (x.review_due_at <= todayLocal) return '今天要复习' // 后端 db.today() 是上海时区，这里不能用 UTC 的 toISOString
  const [, month, day] = x.review_due_at.split('-')
  return `下次：${Number(month)}月${Number(day)}日`
}
watch(() => props.kid, () => { reviewSubject.value = '' })
</script>

<template>
    <section class="a-card enter">
      <h3>今天复习 <span class="review-total">{{ reviewDue.length }} 项</span></h3>
      <div v-if="reviewDue.length && reviewSubjects.length > 1" class="subj-tabs review-filter">
        <button type="button" :class="['subj-tab', { on: !reviewSubject }]" @click="reviewSubject = ''">全部</button>
        <button v-for="sid in reviewSubjects" :key="sid" type="button"
          :class="['subj-tab', { on: reviewSubject === sid }]" @click="reviewSubject = sid">{{ subjectName(sid) }}</button>
      </div>
      <div v-if="!reviewDue.length && !weakPoints.length" class="review-empty">
        <strong>没有薄弱考点</strong>
        <button class="ghost-s review-link" @click="$emit('go-section', 'unit-task')">去记录 →</button>
      </div>
      <div v-else-if="!reviewDue.length" class="review-empty">
        <strong>今天没有到期复习</strong>
      </div>
      <div v-else-if="!filteredReviewDue.length" class="review-empty">
        <strong>这一科今天没有复习</strong>
      </div>
      <div v-for="x in filteredReviewDue" :key="x.id" class="review-item">
        <div class="review-item-info">
          <span class="review-item-title">{{ x.tag_name }}</span>
          <span class="dim">{{ subjectName(x.subject_id) }} · {{ x.unit_name }} · 第 {{ (x.interval_idx || 0) + 1 }} 次复习</span>
        </div>
        <div class="review-actions">
          <button class="ok" @click="$emit('judge', x.id, 'pass')">会了</button>
          <button class="del" @click="$emit('judge', x.id, 'fail')">还不熟</button>
          <button class="ok ghost-o" @click="$emit('judge', x.id, 'done')">已掌握</button>
        </div>
      </div>

      <div v-if="weakPoints.length" class="review-recorded">
        <h4>已记录的薄弱考点</h4>
        <div v-for="x in weakPoints" :key="x.id" class="review-recorded-row">
          <div>
            <strong>{{ x.tag_name }}</strong>
            <span>{{ subjectName(x.subject_id) }} · {{ x.unit_name }}</span>
          </div>
          <em :class="{ due: reviewDue.some(r => r.id === x.id) }">{{ weakPointTiming(x) }}</em>
        </div>
      </div>
    </section>
</template>
