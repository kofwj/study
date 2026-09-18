<script setup>
// 家长工作台 · 已学到（已学到哪一课 + 孩子端显示学科 + 进度锁 + 图鉴与基地，四块合一段）
// 数据（cursors / progressLock / hiddenSubjects / spriteCfg 等）由 Admin.vue 按页加载持有；
// 这一页四个开关都是即时保存，动作仍由工作台执行（含切孩子在途请求的守卫），子组件只 emit。
import { computed } from 'vue'
import { SUBJECT_ORDER } from '../format.js'
import AdminSwitch from './AdminSwitch.vue'

const props = defineProps({
  cursors: { type: Object, default: () => ({}) },
  progressLock: { type: Boolean, default: true },
  hiddenSubjects: { type: Array, default: () => [] },
  spriteCfg: { type: Object, default: () => ({ enabled: true, base_enabled: true }) },
  subjects: { type: Array, default: () => [] },
  tasks: { type: Array, default: () => [] },
  daily: { type: Array, default: () => [] },
  termUnits: { type: Array, default: () => [] },
  tasksBySubject: { type: Object, default: () => ({}) },
  kidName: { type: String, default: '' },
})
defineEmits(['set-cursor', 'toggle-lock', 'set-subject-visible', 'save-sprites-cfg'])

const cursorSubjects = computed(() => {
  const unitIds = new Set(props.termUnits.map(u => u.id))
  const ids = new Set(props.tasks.filter(t => unitIds.has(t.unit_id)).map(t => t.subject_id))
  return props.subjects.filter(s => ids.has(s.id))
})
const displaySubjects = computed(() => {
  const ids = new Set([
    ...props.tasks.map(t => t.subject_id),
    ...props.daily.map(d => d.subject_id),
  ])
  const list = props.subjects.filter(s => ids.has(s.id))
  list.sort((a, b) => SUBJECT_ORDER.indexOf(a.id) - SUBJECT_ORDER.indexOf(b.id))
  return list
})
// 开关按钮的「开/关」判定：读 hiddenSubjects（壳里那份 subjectShown 留给 toggleSubjectVisible 用）
function subjectShown(id) {
  return !(props.hiddenSubjects || []).includes(id)
}
</script>

<template>
    <section class="a-card enter">
      <h3>已学到哪一课</h3>
      <div class="cursor-row" v-for="s in cursorSubjects" :key="s.id">
        <span class="cursor-subj">{{ s.name }}</span>
        <select :value="cursors[s.id] || ''" @change="$emit('set-cursor', s.id, $event.target.value)">
          <option value="">从头开始</option>
          <option v-for="t in (tasksBySubject[s.id] || [])" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select>
      </div>
      <h4 class="w-h">孩子端显示学科</h4>
      <p class="dim">关掉的科目，孩子侧栏和今日推荐都看不到；任务还在，随时开回来。</p>
      <div class="lock-row" v-for="s in displaySubjects" :key="'vis-' + s.id">
        <span class="badge">{{ s.name }}</span>
        <span class="grow">孩子端显示</span>
        <AdminSwitch :model-value="subjectShown(s.id)" :label="s.name + ' 孩子端显示'" @update:model-value="$emit('set-subject-visible', s.id)" />
      </div>
      <div class="lock-row mt14">
        <span class="badge">进度锁</span>
        <span class="grow">只让打「当前单元」</span>
        <AdminSwitch :model-value="progressLock" label="进度锁" @update:model-value="$emit('toggle-lock')" />
      </div>
      <h4 class="w-h">图鉴与基地</h4>
      <p class="dim">给 {{ kidName || '当前孩子' }} 用。关掉图鉴后，连击宝箱只给阳光；秘密基地仍在，孩子端显示「建设中」。</p>
      <div class="lock-row">
        <span class="badge">阳光图鉴</span>
        <span class="grow">连击宝箱会孵出阳光精灵，进图鉴。关掉则宝箱只给阳光。</span>
        <AdminSwitch :model-value="spriteCfg.enabled" label="阳光图鉴" @update:model-value="$emit('save-sprites-cfg', { enabled: !spriteCfg.enabled })" />
      </div>
      <div class="lock-row">
        <span class="badge">秘密基地</span>
        <span class="grow">精灵住进天台/树屋/云上，星尘可以买小玩具。关掉则图鉴只显示格子。</span>
        <AdminSwitch :model-value="spriteCfg.base_enabled" label="秘密基地" @update:model-value="$emit('save-sprites-cfg', { base_enabled: !spriteCfg.base_enabled })" />
      </div>
    </section>
</template>
