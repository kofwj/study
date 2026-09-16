<script setup>
// 家长工作台 · 任务页（任务与考点 + 每日任务 + 单元测试）
// 三段在侧栏是同一项（v0.3.24 合页）。数据仍由 Admin.vue 的按页加载持有
// （tasks 包被总览/复习/已学到/单词/家庭共用），子组件只渲染 + 本页表单；
// 提交成功后 emit('reload') 让壳刷新，切页回来不会重拉（v0.3.23 语义不变）。
import { ref, reactive, computed, watch } from 'vue'
import { Sun } from '@lucide/vue'
import { api } from '../api.js'
import { tagHelp } from '../tagHelp.js'
import { useAdminEdit } from '../adminEdit.js'

const props = defineProps({
  tasksBySubject: { type: Object, default: () => ({}) },
  dailyAll: { type: Array, default: () => [] },
  kids: { type: Array, default: () => [] },
  subjects: { type: Array, default: () => [] },
  units: { type: Array, default: () => [] },
  activeTerm: { type: String, default: '' },
  unitsBySubject: { type: Object, default: () => ({}) },
  catalog: { type: Object, default: () => ({ tags: [], unit_tags: [] }) },
  weakByUnit: { type: Object, default: () => ({}) },
  tests: { type: Array, default: () => [] },
  testBands: { type: Array, default: () => [] },
  insightRules: { type: Object, default: () => ({}) },
  firstReview: { type: String, default: '' },
  showToast: { type: Function, required: true },
  withBusy: { type: Function, required: true },
})
const emit = defineEmits([
  'update:firstReview', 'save-test-bands', 'reset-test-bands',
  'save-rule', 'reset-rule', 'toggle-tag', 'reload',
])

// 编辑会话走 adminEdit.js（模块级单例，与商店/等级/孩子共用同一套）
const { editKind, editId, findEditRow, clearEdit, beginEdit, cancelEdit, isEditing } = useAdminEdit()

// ---- 本页视图状态（newTask / newDaily / newTest 在下方从壳原样搬来）----
const taskAddOpen = ref(false)
const textbookOpen = reactive({})
const dailyAddOpen = ref(false)
const rulesOpen = ref(false)
const activeSubject = ref('')

// 科目 tab 的兜底：原来由壳的 applyTasks 负责，现在本页自己看住
watch(() => props.unitsBySubject, (m) => {
  if (!activeSubject.value || !(m || {})[activeSubject.value]) activeSubject.value = Object.keys(m || {})[0] || ''
}, { immediate: true })

function filled(v) { return String(v ?? '').trim() !== '' }

const DIRS = [['higher_better', '越多越好'], ['lower_better', '越少越好']]
const EMPTY_DAILY = { subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, note: '', kid_id: '', link: '', require_quiz: false, metrics: [] }
const newDaily = reactive({ subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, note: '', kid_id: '', link: '', require_quiz: false, metrics: [] })
const orderedDaily = computed(() => [...props.dailyAll].sort((a, b) =>
  Number(b.family_id != null) - Number(a.family_id != null)
  || String(a.kid_id || '').localeCompare(String(b.kid_id || ''))))
function addMetric(arr) { arr.push({ id: 'm' + Date.now(), label: '', unit: '', direction: 'higher_better', note: '' }) }
const cleanMetrics = (ms) => (ms || []).map(({ id, label, unit, direction, note }) => ({ id, label, unit, direction, note }))
const subjectName = (id) => props.subjects.find(s => s.id === id)?.name || id
const kidName = (id) => props.kids.find(k => k.id === id)?.name || '某个孩子'
const tagFor = (id) => (props.catalog.tags || []).find(t => t.id === id) || { id, name: id }
function tagsFor(uid) {
  // 自动标签只是未精标课程的内部占位，不能当作家长可判断的薄弱考点。
  return (props.catalog.unit_tags || []).filter(x => x.unit_id === uid).map(x => ({ ...x, ...tagFor(x.tag_id) })).filter(x => x.name && !x.auto)
}
function hasAutoTags(uid) {
  return (props.catalog.unit_tags || []).some(x => x.unit_id === uid && x.auto)
}
function tagOn(uid, tid) { return !!(props.weakByUnit[uid] && props.weakByUnit[uid][tid]) }
function weakTagCount(uid) { return Object.keys(props.weakByUnit[uid] || {}).length }
async function addDaily() {
  if (!newDaily.name) return props.showToast('填任务名')
  await props.withBusy(async () => {
    await api.admin.createDaily({ ...newDaily, kid_id: newDaily.kid_id || null, link: newDaily.link || null, require_quiz: newDaily.require_quiz, metrics: cleanMetrics(newDaily.metrics) })
    const who = newDaily.kid_id ? kidName(newDaily.kid_id) : ''
    Object.assign(newDaily, EMPTY_DAILY)
    dailyAddOpen.value = false
    props.showToast(who ? `已新增，只有「${who}」能看到` : '已新增'); emit('reload')
  })
}
async function saveDaily(d) {
  await props.withBusy(async () => {
    await api.admin.updateDaily(d.id, { subject_id: d.subject_id, name: d.name, sunshine: d.sunshine, bonus_per_metric: d.bonus_per_metric, note: d.note, kid_id: d.kid_id || null, link: d.link || null, require_quiz: d.require_quiz, metrics: cleanMetrics(d.metrics) })
    clearEdit()
    props.showToast('已保存')
  })
}
async function delDaily(id) { if (!confirm('删除这个每日任务？')) return; await props.withBusy(async () => { await api.admin.delDaily(id); emit('reload') }) }
const newTask = reactive({ subject_id: '', unit_id: '', action: '', title: '', sunshine: 5, kid_id: '' })
const unitOptions = computed(() => props.units.filter(u => u.subject_id === newTask.subject_id && u.term_id === props.activeTerm))
const testUnitOptions = computed(() => props.units.filter(u => u.subject_id === newTest.subject_id && u.term_id === props.activeTerm))
function pickSubject() { newTask.unit_id = '' }
function unitTasks(sid, uid) { return (props.tasksBySubject[sid] || []).filter(x => x.unit_id === uid) }
function customUnitTasks(sid, uid) { return unitTasks(sid, uid).filter(x => x.custom) }
function textbookUnitTasks(sid, uid) { return unitTasks(sid, uid).filter(x => !x.custom) }
async function addTask() {
  if (!newTask.subject_id || !newTask.unit_id || !newTask.title) return props.showToast('选科目/单元、填标题')
  await props.withBusy(async () => {
    await api.admin.createTask({ ...newTask, kid_id: newTask.kid_id || null })
    Object.assign(newTask, { subject_id: '', unit_id: '', action: '', title: '', sunshine: 5, kid_id: '' })
    taskAddOpen.value = false
    props.showToast('已新增'); emit('reload')
  })
}
async function saveTask(t) { await props.withBusy(async () => { await api.admin.updateTask(t.id, { ...t, kid_id: t.kid_id || null }); clearEdit(); props.showToast('已保存') }) }
async function delTask(id) { if (!confirm('删除这个任务？')) return; await props.withBusy(async () => { await api.admin.delTask(id); emit('reload') }) }
const newTest = reactive({ subject_id: '', unit_id: '', score: '', note: '' })
async function addTest() {
  if (!newTest.subject_id || newTest.score === '' || newTest.score === null) return props.showToast('选科目、填分数')
  const sc = Number(newTest.score)
  if (sc < 0 || sc > 100) return props.showToast('分数要在 0~100')
  try {
    const r = await api.admin.createTest({ subject_id: newTest.subject_id, unit_id: newTest.unit_id, score: sc, note: newTest.note })
    props.showToast(`已发 +${r.sunshine} 阳光`)
    Object.assign(newTest, { subject_id: '', unit_id: '', score: '', note: '' })
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function delTest(id) {
  if (!confirm('删除这条测试记录？会冲正扣回阳光。')) return
  await props.withBusy(async () => { await api.admin.delTest(id); emit('reload') })
}
function testBandRange(i) {
  const low = Number(props.testBands[i][0])
  const high = i === 0 ? 100 : Number(props.testBands[i - 1][0]) - 1
  return low === high ? `${low} 分` : `${low}～${high} 分`
}
const testPreview = computed(() => {
  const sc = Number(newTest.score)
  if (newTest.score === '' || newTest.score === null || Number.isNaN(sc) || sc < 0 || sc > 100) return null
  const bands = props.testBands || []
  for (let i = 0; i < bands.length; i++) {
    if (sc >= Number(bands[i][0])) return { range: testBandRange(i), sun: Number(bands[i][1]) }
  }
  return { range: '', sun: 0 }
})
// ---- 脏条要的三件事（壳通过 ref 调用）----
function isAddDirty() {
  if (newTask.subject_id || newTask.unit_id || filled(newTask.action) || filled(newTask.title) || Number(newTask.sunshine) !== 5 || newTask.kid_id) return true
  if ((newDaily.subject_id || '体育') !== '体育' || filled(newDaily.name) || Number(newDaily.sunshine) !== 5 || Number(newDaily.bonus_per_metric) !== 3 || filled(newDaily.note) || (newDaily.kid_id || '') || filled(newDaily.link) || newDaily.require_quiz || (newDaily.metrics || []).length) return true
  return false
}
function discardAdd() {
  Object.assign(newTask, { subject_id: '', unit_id: '', action: '', title: '', sunshine: 5, kid_id: '' })
  Object.assign(newDaily, { subject_id: '体育', name: '', sunshine: 5, bonus_per_metric: 3, note: '', kid_id: '', link: '', require_quiz: false, metrics: [] })
  taskAddOpen.value = false
  dailyAddOpen.value = false
}
async function saveCurrentEdit() {
  const kind = editKind.value
  const row = findEditRow(kind, editId.value)
  if (!row) return
  if (kind === 'daily') await saveDaily(row)
  else if (kind === 'task') await saveTask(row)
}
defineExpose({ isAddDirty, discardAdd, saveCurrentEdit })
</script>

<template>
    <section class="a-card enter">
      <h3>任务</h3>
      <h4 class="w-h">任务与考点</h4>
      <button type="button" class="ghost-s rules-toggle" @click="taskAddOpen = !taskAddOpen">{{ taskAddOpen ? '收起新增' : '＋给这一科加任务' }}</button>
      <div v-if="taskAddOpen" class="add-box task-add-box">
        <div class="add-title">新增家长任务</div>
        <div class="frm-row">
          <label class="fld grow"><span>哪一科</span>
            <select v-model="newTask.subject_id" @change="pickSubject">
              <option value="" disabled>先选科</option>
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ subjectName(s.id) }}</option>
            </select>
          </label>
          <label class="fld grow"><span>放在哪个单元</span>
            <select v-model="newTask.unit_id">
              <option value="" disabled>{{ newTask.subject_id ? '选单元' : '先选科' }}</option>
              <option v-for="u in unitOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>谁能看到</span>
            <select v-model="newTask.kid_id">
              <option value="">全家</option>
              <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
            </select>
          </label>
        </div>
        <div class="frm-row">
          <label class="fld grow"><span>任务名称</span><input v-model="newTask.title" placeholder="如：订正今天的错题" /></label>
          <label class="fld w84"><span>怎么做</span><input v-model="newTask.action" placeholder="读 / 写 / 练" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="newTask.sunshine" type="number" min="0" /></label>
        </div>
        <button class="ok wide" @click="addTask">＋新增任务</button>
      </div>
      <div class="subj-tabs">
        <button v-for="(arr, sid) in unitsBySubject" :key="sid" type="button"
          :class="['subj-tab', { on: activeSubject === sid }]"
          @click="activeSubject = sid">{{ subjectName(sid) }}</button>
      </div>
      <label class="fld review-date"><span>新加入的考点从这天开始</span>
        <input type="date" :value="firstReview" @input="$emit('update:firstReview', $event.target.value)" />
      </label>
      <div v-for="(arr, sid) in unitsBySubject" :key="sid" class="subj" v-show="activeSubject === sid">
        <div v-for="u in arr" :key="u.id" class="unit-block">
          <div class="unit-h">{{ u.name }} <span v-if="weakTagCount(u.id)" class="unit-wp-count">已记录 {{ weakTagCount(u.id) }} 项</span></div>
          <div class="tag-guide-row">
            <button v-for="tg in tagsFor(u.id)" :key="tg.tag_id" type="button"
              :class="['tag-guide', { on: tagOn(u.id, tg.tag_id), auto: tg.auto }]"
              :aria-pressed="tagOn(u.id, tg.tag_id)"
              @click="$emit('toggle-tag', u.id, tg.tag_id)">
              <span class="tag-guide-title">{{ tagOn(u.id, tg.tag_id) ? '✓ ' : '' }}{{ tg.name }}</span>
              <span class="tag-guide-help">{{ tagHelp(tg) }}</span>
              <span class="tag-guide-action">{{ tagOn(u.id, tg.tag_id) ? '已加入' : '加入复习' }}</span>
            </button>
            <span v-if="!tagsFor(u.id).length" class="dim">无考点</span>
          </div>
          <div class="task-row" v-for="t in customUnitTasks(sid, u.id)" :key="t.id">
            <template v-if="isEditing('task', t.id)">
              <label class="fld grow"><span>家长任务名称</span><input v-model="t.title" /></label>
              <label class="fld w84"><span>怎么做</span><input v-model="t.action" /></label>
              <label class="fld w64"><span>阳光</span><input v-model.number="t.sunshine" type="number" min="0" /></label>
              <label class="fld w104"><span>谁能看到</span>
                <select v-model="t.kid_id">
                  <option value="">全家</option>
                  <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
                </select>
              </label>
              <div class="ops">
                <button class="ok" @click="saveTask(t)">保存</button>
                <button class="ghost-s" @click="cancelEdit">取消</button>
                <button class="del" @click="delTask(t.id)">删</button>
              </div>
            </template>
            <template v-else>
              <span class="task-readonly-title">{{ t.title }}</span>
              <span class="badge">{{ t.action }}</span>
              <span class="dim">+{{ t.sunshine }} 阳光 · {{ t.kid_id ? ((kids.find(k => k.id === t.kid_id) || {}).name || '指定孩子') : '全家' }}</span>
              <div class="ops">
                <button class="ghost-s" @click="beginEdit('task', t)">改</button>
                <button class="del" @click="delTask(t.id)">删</button>
              </div>
            </template>
          </div>
          <button v-if="textbookUnitTasks(sid, u.id).length" type="button" class="ghost-s" @click="textbookOpen[u.id] = !textbookOpen[u.id]">{{ textbookOpen[u.id] ? '收起教材任务' : '教材任务 ' + textbookUnitTasks(sid, u.id).length + ' 项' }}</button>
          <div v-if="textbookOpen[u.id]" class="task-row" v-for="t in textbookUnitTasks(sid, u.id)" :key="t.id">
            <span class="task-readonly-title">{{ t.title }}</span>
            <span class="badge">{{ t.action }}</span>
            <span class="dim">+{{ t.sunshine }} 阳光 · 教材任务</span>
          </div>
        </div>
      </div>
    </section>

    <section class="a-card enter">
      <h3>每日任务</h3>
      <button type="button" class="ghost-s rules-toggle" @click="dailyAddOpen = !dailyAddOpen">{{ dailyAddOpen ? '收起新增' : '＋新增每日任务' }}</button>
      <p class="dim">下面的列表是全家所有的每日任务（含只给某个孩子看的），点「改」可以随时换人。</p>
      <div v-if="dailyAddOpen" class="add-box task-add-box">
        <div class="add-title">新增每日任务</div>
        <div class="frm-row">
          <label class="fld grow"><span>哪一科</span>
            <select v-model="newDaily.subject_id">
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>名称</span><input v-model="newDaily.name" placeholder="如：跳绳打卡" /></label>
          <label class="fld grow"><span>谁能看到</span>
            <select v-model="newDaily.kid_id">
              <option value="">全家</option>
              <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
            </select>
          </label>
          <label class="fld w64"><span>基础阳光</span><input v-model.number="newDaily.sunshine" type="number" /></label>
          <label class="fld w84"><span>破纪录 +</span><input v-model.number="newDaily.bonus_per_metric" type="number" /></label>
          <label class="fld grow"><span>怎么做</span><input v-model="newDaily.note" placeholder="如：完成后让家长检查" /></label>
          <label class="fld grow"><span>去哪做</span><input v-model="newDaily.link" placeholder="如 /quiz/，留空则不跳转" /></label>
          <label class="fld" style="display:flex;align-items:center;gap:6px;white-space:nowrap"><input type="checkbox" v-model="newDaily.require_quiz" /> 必须先完成今日题库</label>
        </div>
        <div class="m-row" v-for="(m, i) in newDaily.metrics" :key="m.id">
          <label class="fld grow"><span>指标名</span><input v-model="m.label" placeholder="如：跳绳个数" /></label>
          <label class="fld w84"><span>单位</span><input v-model="m.unit" placeholder="个" /></label>
          <label class="fld w104"><span>方向</span>
            <select v-model="m.direction">
              <option v-for="[v, n] in DIRS" :key="v" :value="v">{{ n }}</option>
            </select>
          </label>
          <label class="fld grow"><span>记录说明</span><input v-model="m.note" placeholder="如：只记完整正确的次数" /></label>
          <button class="del" @click="newDaily.metrics.splice(i, 1)">×</button>
        </div>
        <button class="ghost-s" @click="addMetric(newDaily.metrics)">＋加破纪录指标</button>
        <div class="mt10"><button class="ok wide" @click="addDaily">＋新增任务</button></div>
      </div>
      <div class="daily-card" v-for="d in orderedDaily" :key="d.id">
        <div v-if="d.family_id == null" class="sys-row">
          <span class="badge daily">每天</span>
          <span class="sys-name">{{ d.name }}</span>
          <span class="dim">+{{ d.sunshine }} 阳光 · 系统内置</span>
          <div v-if="d.note" class="daily-note">怎么做：{{ d.note }}</div>
        </div>
        <template v-else>
          <template v-if="isEditing('daily', d.id)">
            <div class="dc-head">
              <span class="badge daily">每天</span>
              <label class="fld grow"><span>名称</span><input v-model="d.name" /></label>
              <label class="fld grow"><span>哪一科</span>
                <select v-model="d.subject_id">
                  <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </label>
              <label class="fld grow"><span>谁能看到</span>
                <select v-model="d.kid_id">
                  <option value="">全家</option>
                  <option v-for="k in kids" :key="k.id" :value="k.id">{{ k.name }}</option>
                </select>
              </label>
              <label class="fld w64"><span>基础阳光</span><input v-model.number="d.sunshine" type="number" /></label>
              <label class="fld w84"><span>破纪录 +</span><input v-model.number="d.bonus_per_metric" type="number" /></label>
              <label class="fld grow"><span>怎么做</span><input v-model="d.note" placeholder="如：完成后让家长检查" /></label>
              <label class="fld grow"><span>去哪做</span><input v-model="d.link" placeholder="如 /quiz/，留空则不跳转" /></label>
              <label class="fld" style="display:flex;align-items:center;gap:6px;white-space:nowrap"><input type="checkbox" v-model="d.require_quiz" /> 必须先完成今日题库</label>
              <div class="ops">
                <button class="ok" @click="saveDaily(d)">保存</button>
                <button class="ghost-s" @click="cancelEdit">取消</button>
              </div>
            </div>
            <div class="dc-metrics" v-if="d.metrics.length">
              <div class="dc-m-head">破纪录指标</div>
              <div class="m-row" v-for="(m, i) in d.metrics" :key="m.id">
                <label class="fld grow"><span>名称</span><input v-model="m.label" placeholder="如：跳绳个数" /></label>
                <label class="fld w84"><span>单位</span><input v-model="m.unit" placeholder="个" /></label>
                <label class="fld w104"><span>方向</span>
                  <select v-model="m.direction">
                    <option v-for="[v, n] in DIRS" :key="v" :value="v">{{ n }}</option>
                  </select>
                </label>
                <label class="fld grow"><span>记录说明</span><input v-model="m.note" placeholder="如：只记完整正确的次数" /></label>
                <button class="del" @click="d.metrics.splice(i, 1)">×</button>
              </div>
            </div>
            <button class="ghost-s" @click="addMetric(d.metrics)">＋加破纪录指标</button>
          </template>
          <template v-else>
            <div class="sys-row">
              <span class="badge daily">每天</span>
              <span class="sys-name">{{ d.name }}</span>
              <span class="badge scope" :class="{ kid: d.kid_id }">{{ d.kid_id ? '只给 ' + kidName(d.kid_id) : '全家' }}</span>
              <span v-if="d.require_quiz" class="badge" style="background:#EAF6EF;color:#2F8F5B">需题库</span>
              <span class="dim">{{ subjectName(d.subject_id) }} · +{{ d.sunshine }} 阳光<template v-if="d.bonus_per_metric"> · 破纪录 +{{ d.bonus_per_metric }}</template></span>
              <div class="ops">
                <button class="ghost-s" @click="beginEdit('daily', d)">改</button>
                <button class="del" @click="delDaily(d.id)">删</button>
              </div>
              <div v-if="d.note" class="daily-note">怎么做：{{ d.note }}</div>
              <div v-if="d.link" class="daily-note">去哪做：<a :href="d.link" target="_blank" rel="noopener noreferrer">{{ d.link }}</a></div>
            </div>
            <div class="dc-metrics" v-if="d.metrics && d.metrics.length">
              <div class="dc-m-head">破纪录指标</div>
              <div class="dim" v-for="m in d.metrics" :key="m.id">{{ m.label }}<template v-if="m.unit"> · {{ m.unit }}</template> · {{ (DIRS.find(x => x[0] === m.direction) || [])[1] || m.direction }}<template v-if="m.note"> · {{ m.note }}</template></div>
            </div>
          </template>
        </template>
      </div>
    </section>

    <section class="a-card enter">
      <h3>单元测试</h3>
      <div class="add-box">
        <div class="add-title">录入成绩</div>
        <div class="frm-row">
          <label class="fld grow"><span>哪一科</span>
            <select v-model="newTest.subject_id" @change="newTest.unit_id = ''">
              <option value="" disabled>先选科</option>
              <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label class="fld grow"><span>哪一单元（可空）</span>
            <select v-model="newTest.unit_id">
              <option value="">不绑单元</option>
              <option v-for="u in testUnitOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
          </label>
          <label class="fld w84"><span>分数</span><input v-model="newTest.score" type="number" placeholder="0~100" /></label>
          <label class="fld w104"><span>备注</span><input v-model="newTest.note" placeholder="如：期中" /></label>
        </div>
        <p v-if="testPreview" class="test-preview">命中 {{ testPreview.range }}，将发 {{ testPreview.sun }} 阳光。</p>
        <button class="ok wide" @click="addTest">录成绩并发阳光</button>
      </div>
      <div v-if="!tests.length" class="dim">还没录过测试成绩。</div>
      <div class="test-row" v-for="t in tests" :key="t.id">
        <span class="badge">{{ subjectName(t.subject_id) }}</span>
        <span class="badge daily">{{ t.score }} 分</span>
        <span class="dim">{{ t.note || '—' }} · {{ t.date }}</span>
        <span class="st delivered">+{{ t.sunshine }} <Sun class="ico sun" :size="12" /></span>
        <button class="del" @click="delTest(t.id)">删</button>
      </div>
      <button type="button" class="ghost-s rules-toggle" @click="rulesOpen = !rulesOpen">{{ rulesOpen ? '收起规则' : '成绩档位与诊断阈值' }}</button>
      <template v-if="rulesOpen">
        <div class="test-band-editor">
          <div class="add-title">成绩对应阳光</div>
          <div class="test-band-head"><span>分数区间</span><span>发放阳光</span></div>
          <div class="band-edit" v-for="(band, i) in testBands" :key="i">
            <span class="band-range">{{ testBandRange(i) }}</span>
            <label class="fld band-threshold"><span>本档最低分</span><input v-model.number="band[0]" type="number" min="0" max="100" :disabled="i === testBands.length - 1" /></label>
            <span class="band-arrow">→</span>
            <label class="fld band-sun"><span>阳光</span><input v-model.number="band[1]" type="number" min="0" /></label>
            <Sun class="ico sun" :size="14" />
          </div>
          <div class="band-actions">
            <button class="ok" @click="$emit('save-test-bands')">保存设置</button>
            <button class="ghost-s" @click="$emit('reset-test-bands')">恢复默认</button>
          </div>
        </div>
        <div class="a-item">
          <span class="dim">连续低分次数</span>
          <input class="w-num" type="number" :value="insightRules.test_fail_count" @change="$emit('save-rule', 'test_fail_count', +$event.target.value)" />
          <button class="ghost" @click="$emit('reset-rule', 'test_fail_count')">默认</button>
        </div>
        <div class="a-item">
          <span class="dim">低于多少分算低</span>
          <input class="w-num" type="number" :value="insightRules.test_fail_score" @change="$emit('save-rule', 'test_fail_score', +$event.target.value)" />
          <button class="ghost" @click="$emit('reset-rule', 'test_fail_score')">默认</button>
        </div>
        <div class="a-item">
          <span class="dim">完成量少几成算下滑</span>
          <input class="w-num" type="number" step="0.1" :value="insightRules.drop_ratio" @change="$emit('save-rule', 'drop_ratio', +$event.target.value)" />
          <button class="ghost" @click="$emit('reset-rule', 'drop_ratio')">默认</button>
        </div>
        <div class="a-item">
          <span class="dim">连击断几天再提</span>
          <input class="w-num" type="number" :value="insightRules.streak_break" @change="$emit('save-rule', 'streak_break', +$event.target.value)" />
          <button class="ghost" @click="$emit('reset-rule', 'streak_break')">默认</button>
        </div>
      </template>
    </section>
</template>
