/* ============================================================
   家长工作台 · 编辑会话（模块级单例）
   ------------------------------------------------------------
   同一个会话被五个地方共用：商店、成长等级、家长自定义任务、家庭每日任务、孩子账号。
   拆页之后它们分属不同组件（商店/等级/孩子留在 Admin.vue，任务/每日会去 AdminTasks.vue），
   所以会话必须放在模块里，不能归某一个组件私有。

   约定（v0.3.25 定的语义，原样保留）：
   - 同一时刻全工作台只编一行
   - 点另一行「改」：先把上一行按快照还原，再给当前行拍快照
   - 取消 = 按快照还原（含每日任务的 metrics 深拷贝）
   - 保存成功才退出编辑（各保存函数自己调 clearEdit）
   - load() 刷新列表时丢掉会话

   由 Admin.vue 注入数据查找：
     initAdminEdit({ getLists: () => ({ rewards, ranks, dailyAll, daily, tasks, kids }) })
   ============================================================ */
import { ref } from 'vue'

let getLists = () => ({})
export function initAdminEdit(ctx) {
  if (ctx && typeof ctx.getLists === 'function') getLists = ctx.getLists
}

const editKind = ref('')
const editId = ref('')
const editSnap = ref(null)

function cloneEdit(kind, row) {
  if (kind === 'reward') return { name: row.name, price: row.price, category: row.category }
  if (kind === 'rank') return { name: row.name, min_sunshine: row.min_sunshine }
  if (kind === 'daily') return { name: row.name, subject_id: row.subject_id, sunshine: row.sunshine, bonus_per_metric: row.bonus_per_metric, note: row.note, kid_id: row.kid_id || '', link: row.link || '', require_quiz: !!row.require_quiz, metrics: JSON.parse(JSON.stringify(row.metrics || [])) }
  if (kind === 'task') return { title: row.title, action: row.action, sunshine: row.sunshine, kid_id: row.kid_id || '' }
  if (kind === 'kid') return { name: row.name, account: row.account, term_id: row.term_id, gender: row.gender || '' }
  return {}
}

function findEditRow(kind, id) {
  const L = getLists() || {}
  if (kind === 'reward') return (L.rewards || []).find(x => x.id === id)
  if (kind === 'rank') return (L.ranks || []).find(x => x.id === id)
  if (kind === 'daily') return (L.dailyAll || []).find(x => x.id === id) || (L.daily || []).find(x => x.id === id)
  if (kind === 'task') return (L.tasks || []).find(x => x.id === id)
  if (kind === 'kid') return (L.kids || []).find(x => x.id === id)
}

function restoreEditSnap() {
  const snap = editSnap.value
  const kind = editKind.value
  const id = editId.value
  if (!snap || !kind || !id) return
  const row = findEditRow(kind, id)
  if (row) {
    if (kind === 'reward') { row.name = snap.name; row.price = snap.price; row.category = snap.category }
    else if (kind === 'rank') { row.name = snap.name; row.min_sunshine = snap.min_sunshine }
    else if (kind === 'daily') {
      row.name = snap.name
      row.subject_id = snap.subject_id
      row.sunshine = snap.sunshine
      row.bonus_per_metric = snap.bonus_per_metric
      row.note = snap.note
      row.kid_id = snap.kid_id || ''
      row.link = snap.link || ''
      row.require_quiz = !!snap.require_quiz
      row.metrics = JSON.parse(JSON.stringify(snap.metrics || []))
    }
    else if (kind === 'task') { row.title = snap.title; row.action = snap.action; row.sunshine = snap.sunshine; row.kid_id = snap.kid_id || '' }
    else if (kind === 'kid') { row.name = snap.name; row.account = snap.account; row.term_id = snap.term_id; row.gender = snap.gender; row._pin = '' }
  }
  editSnap.value = null
}

function clearEdit() {
  editSnap.value = null
  editKind.value = ''
  editId.value = ''
}

function beginEdit(kind, row) {
  if (editKind.value === kind && editId.value === row.id) return
  restoreEditSnap()
  editSnap.value = cloneEdit(kind, row)
  if (kind === 'kid') row._pin = ''
  editKind.value = kind
  editId.value = row.id
}

function cancelEdit() {
  restoreEditSnap()
  clearEdit()
}

function isEditing(kind, id) {
  return editKind.value === kind && editId.value === id
}

function sameJson(a, b) { return JSON.stringify(a) === JSON.stringify(b) }

/* 当前这一行有没有未保存的改动（壳的脏条用） */
function isEditDirty() {
  const kind = editKind.value
  const id = editId.value
  const snap = editSnap.value
  if (!kind || !id || !snap) return false
  const row = findEditRow(kind, id)
  if (!row) return false
  if (kind === 'kid' && String(row._pin || '').trim()) return true
  return !sameJson(cloneEdit(kind, row), snap)
}

export function useAdminEdit() {
  return {
    editKind, editId, editSnap,
    cloneEdit, findEditRow, restoreEditSnap, clearEdit,
    beginEdit, cancelEdit, isEditing, isEditDirty,
  }
}