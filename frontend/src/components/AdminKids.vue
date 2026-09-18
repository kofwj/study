<script setup>
// 家长工作台 · 家庭（孩子账号 + 家长成员 + 邀请码 + 家长密码，四段合一页）
// 数据由 Admin.vue 按页加载持有（kids/terms/members/invites/inviteProtect/me），这里只渲染 + 本页表单；
// 邀请码保护开关与「当前选中孩子」仍归壳，用 emit 触发。
import { reactive, ref } from 'vue'
import { api } from '../api.js'
import { useAdminEdit } from '../adminEdit.js'
import AdminSwitch from './AdminSwitch.vue'

const props = defineProps({
  kids: { type: Array, default: () => [] },
  terms: { type: Array, default: () => [] },
  members: { type: Array, default: () => [] },
  invites: { type: Array, default: () => [] },
  inviteProtect: { type: Boolean, default: false },
  hours: { type: Object, default: () => ({}) },
  isOwner: { type: Boolean, default: false },
  meAccount: { type: String, default: '' },
  showToast: { type: Function, required: true },
})
const emit = defineEmits(['reload', 'reload-invites', 'toggle-protect', 'kid-removed'])

const { editKind, editId, findEditRow, clearEdit, beginEdit, cancelEdit, isEditing } = useAdminEdit()

const newKid = reactive({ name: '', account: '', pin: '', pin2: '', term_id: 'g5s1', gender: '' })
const kidAddOpen = ref(false)
const pinForm = reactive({ cur: '', next: '', confirm: '' })

// 打卡时间窗 / 储蓄所营业时间：各自一个开关 + 整点区间；后端会校验「开门必须早于打烊」
async function saveHours(kind, patch) {
  const cur = (props.hours || {})[kind]
  if (!cur) return
  const body = {
    enabled: patch && 'enabled' in patch ? patch.enabled : cur.enabled,
    open_hour: cur.open_hour,
    close_hour: cur.close_hour,
  }
  try {
    const r = kind === 'checkin' ? await api.admin.setCheckinHours(body) : await api.admin.setBankHours(body)
    const next = (kind === 'checkin' ? r.checkin_hours : r.bank_hours) || {}
    Object.assign(cur, next)
    props.showToast(kind === 'checkin' ? '打卡时间已保存' : '储蓄所时间已保存')
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function addKid() {
  if (!newKid.name) return props.showToast('填名字')
  if (!(newKid.account || '').trim()) return props.showToast('填登录账号')
  if ((newKid.pin || '').trim() && newKid.pin.length < 6) return props.showToast('密码至少 6 位')
  try {
    const r = await api.admin.createKid({ ...newKid })
    const kidName = newKid.name || r.account || '孩子'
    newKid.name = newKid.account = newKid.pin = newKid.pin2 = ''
    newKid.gender = ''
    if (r && r.pin) alert(`已添加。${kidName}的登录密码是：${r.pin}\n（系统随机生成，只显示这一次，请记下来告诉孩子）`)
    else props.showToast('已添加')
    kidAddOpen.value = false
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function saveKid(k) {
  if (k._pin) {
    if (String(k._pin).trim().length < 6) return props.showToast('孩子密码至少 6 位')
    if (!confirm('要改「' + k.name + '」的登录密码？改完孩子要用新密码登录。')) return
  }
  try {
    await api.admin.updateKid(k.id, { name: k.name, account: k.account, term_id: k.term_id, pin: k._pin || '', gender: k.gender || '' })
    k._pin = ''
    clearEdit()
    props.showToast('已保存')
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function delKid(k) {
  if (!props.isOwner) return props.showToast('只有创建者能删除孩子')
  if (!confirm('删除「' + k.name + '」？打卡记录还在库里，只是账号没了。')) return
  try {
    await api.admin.delKid(k.id)
    emit('kid-removed', k.id)
    props.showToast('已删除')
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function transferOwner(m) {
  if (!props.isOwner) return props.showToast('只有创建者能转让')
  if (!confirm(`把创建者交给「${m.name}」？交出去后你变成普通成员，不能再删人、删孩子、发邀请码。`)) return
  try {
    await api.admin.transferOwner(m.id)
    props.showToast('已交给 ' + m.name)
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function delMember(m) {
  if (!confirm('删除「' + m.name + '」？立刻失效。')) return
  try {
    await api.admin.delMember(m.id)
    props.showToast('已删除')
    emit('reload')
  } catch (e) { props.showToast(e.message) }
}
async function makeInvite() {
  try {
    const r = await api.admin.invite()
    emit('reload-invites')
    props.showToast('已生成 ' + r.code + '，点「复制」分享')
  } catch (e) { props.showToast(e.message) }
}
function inviteStatus(iv) {
  if (iv.expired) return '已过期'
  if (iv.used_up) return '已用' + (iv.used_by ? '（' + iv.used_by + '）' : '')
  if (iv.used_count > 0) return '已用 ' + iv.used_count + ' 次' + (iv.used_by ? '（最近 ' + iv.used_by + '）' : '')
  return '未用'
}
async function copyCode(code) {
  try {
    await navigator.clipboard.writeText(code)
  } catch {
    const t = document.createElement('textarea')
    t.value = code; document.body.appendChild(t); t.select()
    document.execCommand('copy'); document.body.removeChild(t)
  }
  props.showToast('已复制 ' + code)
}
async function delInvite(code) {
  try { await api.admin.delInvite(code); emit('reload-invites'); props.showToast('已删除') } catch (e) { props.showToast(e.message) }
}
async function changePin() {
  const cur = pinForm.cur.trim()
  const next = pinForm.next.trim()
  if (!cur) return props.showToast('请输入当前密码')
  if (!next) return props.showToast('请输入新密码')
  if (next.length < 8) return props.showToast('家长密码至少 8 位')
  if (next !== pinForm.confirm) return props.showToast('两次新密码不一致')
  try {
    await api.admin.changePin(next, cur)
    pinForm.cur = pinForm.next = pinForm.confirm = ''
    props.showToast('密码已改，其他设备需要重新登录')
  } catch (e) { props.showToast(e.message) }
}
// ---- 脏条要的三件事（壳通过 ref 调用）----
function filled(v) { return String(v ?? '').trim() !== '' }
function isAddDirty() {
  if (filled(newKid.name) || filled(newKid.account) || filled(newKid.pin) || filled(newKid.pin2) || (newKid.term_id || 'g5s1') !== 'g5s1' || (newKid.gender || '')) return true
  return false
}
function discardAdd() {
  Object.assign(newKid, { name: '', account: '', pin: '', pin2: '', term_id: 'g5s1', gender: '' })
  kidAddOpen.value = false
}
async function saveCurrentEdit() {
  const row = findEditRow(editKind.value, editId.value)
  if (!row) return
  if (editKind.value === 'kid') await saveKid(row)
}
defineExpose({ isAddDirty, discardAdd, saveCurrentEdit })
</script>

<template>
    <section class="a-card">
      <h3>家庭</h3>
      <h4 class="w-h">孩子账号</h4>
      <p v-if="!terms.length" class="dim">学期列表还没载入，退出再进一次家长端。</p>

      <div class="kid-card" v-for="k in kids" :key="k.id">
        <template v-if="isEditing('kid', k.id)">
          <label class="fld"><span>家里怎么叫</span><input v-model="k.name" placeholder="如：乐乐" /></label>
          <label class="fld"><span>登录账号</span><input v-model="k.account" placeholder="如：lele" /></label>
          <label class="fld"><span>现在读哪册</span>
            <select v-model="k.term_id">
              <option disabled value="">请选择</option>
              <option v-for="tm in terms" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
            </select>
          </label>
          <label class="fld"><span>性别</span>
            <select v-model="k.gender">
              <option value="">还没填</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>
          <label class="fld kid-pin"><span>改密码</span><input v-model="k._pin" type="password" autocomplete="new-password" placeholder="至少 6 位，不要重复或连续数字" /></label>
          <div class="ops">
            <button class="ok" @click="saveKid(k)">保存资料</button>
            <button class="ghost-s" @click="cancelEdit">取消</button>
            <button v-if="isOwner" class="del" @click="delKid(k)">删除账号</button>
            <span v-else class="dim">只有创建者能删除孩子</span>
          </div>
        </template>
        <template v-else>
          <div class="sys-row kid-readonly">
            <span class="sys-name">{{ k.name }}</span>
            <span class="dim">{{ k.account }} · {{ (terms.find(tm => tm.id === k.term_id) || {}).label || k.term_id }}<template v-if="k.gender"> · {{ k.gender }}</template></span>
            <div class="ops">
              <button class="ghost-s" @click="beginEdit('kid', k)">改</button>
              <button v-if="isOwner" class="del" @click="delKid(k)">删</button>
            </div>
          </div>
        </template>
      </div>
      <button type="button" class="ghost-s rules-toggle" @click="kidAddOpen = !kidAddOpen">{{ kidAddOpen ? '收起新增' : '＋再加一个孩子' }}</button>
      <div v-if="kidAddOpen" class="add-box">
        <div class="add-title">再加一个孩子</div>
        <div class="frm-row">
          <label class="fld grow"><span>家里怎么叫</span><input v-model="newKid.name" placeholder="如：弟弟" /></label>
          <label class="fld grow"><span>登录账号</span><input v-model="newKid.account" placeholder="如：didi" /></label>
          <label class="fld grow"><span>密码</span><input v-model="newKid.pin" type="password" autocomplete="new-password" placeholder="留空自动生成；自填至少 6 位" /></label>
        </div>
        <div class="frm-row">
          <label class="fld grow"><span>现在读哪册</span>
            <select v-model="newKid.term_id">
              <option v-for="tm in terms" :key="tm.id" :value="tm.id">{{ tm.label }}</option>
            </select>
          </label>
          <label class="fld w84"><span>性别</span>
            <select v-model="newKid.gender">
              <option value="">还没填</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>
        </div>
        <button class="ok wide" @click="addKid">添加</button>
      </div>
    </section>

    <section class="a-card enter">
      <h3>家长成员</h3>
      <div class="member-row" v-for="m in members" :key="m.id">
        <div class="member-info">
          <strong>{{ m.name }}</strong>
          <span class="dim">{{ m.account }}</span>
        </div>
        <span class="badge" :class="{ daily: m.parent_role === 'owner' }">{{ m.parent_role === 'owner' ? '创建者' : '成员' }}</span>
        <button v-if="isOwner && m.account !== meAccount" class="ok" @click="transferOwner(m)">交给创建者</button>
        <button v-if="isOwner && m.account !== meAccount" class="del" @click="delMember(m)">删</button>
        <span v-else-if="!isOwner" class="dim">只有创建者能改成员</span>
      </div>
      <p v-if="!members.length" class="dim">还没有家长成员。</p>
    </section>

    <section class="a-card enter">
      <h3>邀请码</h3>
      <div class="lock-row">
        <span class="badge">邀请码保护</span>
        <span class="grow">开着时邀请码一次性 + 24 小时；关掉则常驻复用</span>
        <AdminSwitch v-if="isOwner" :model-value="inviteProtect" label="邀请码保护" @update:model-value="$emit('toggle-protect')" />
      </div>
      <p v-if="!isOwner" class="dim">只有创建者能开关保护和生成邀请码。</p>
      <div class="frm-row mt8">
        <button v-if="isOwner" class="ok" @click="makeInvite()">生成邀请码</button>
      </div>
      <div class="member-row" v-for="iv in invites" :key="iv.code">
        <div class="member-info">
          <code class="invite-code">{{ iv.code }}</code>
          <span class="dim">{{ inviteStatus(iv) }}</span>
        </div>
        <button class="ok" @click="copyCode(iv.code)">复制</button>
        <button v-if="isOwner" class="del" @click="delInvite(iv.code)">删</button>
      </div>
      <p v-if="!invites.length" class="dim mt6">还没有邀请码。</p>
    </section>

    <section class="a-card enter">
      <h3>打卡与储蓄所时间</h3>
      <p class="dim">孩子端「每日签到」和「阳光储蓄所」各自的营业时间，按家里的作息改。按整点、每天生效；关掉某一项就等于那件事全天都能做。</p>

      <div class="lock-row">
        <span class="badge">打卡时间窗</span>
        <span class="grow">关掉 = 全天都能签到</span>
        <AdminSwitch :model-value="!!(hours.checkin && hours.checkin.enabled)" label="打卡时间窗"
                     @update:model-value="saveHours('checkin', { enabled: !(hours.checkin && hours.checkin.enabled) })" />
      </div>
      <div v-if="hours.checkin && hours.checkin.enabled" class="frm-row">
        <label class="fld w64"><span>开门</span><input v-model.number="hours.checkin.open_hour" type="number" min="0" max="23" /></label>
        <label class="fld w64"><span>打烊</span><input v-model.number="hours.checkin.close_hour" type="number" min="1" max="24" /></label>
        <button class="ok" @click="saveHours('checkin')">保存</button>
      </div>

      <div class="lock-row mt8">
        <span class="badge">储蓄所营业</span>
        <span class="grow">关掉 = 全天都能存取</span>
        <AdminSwitch :model-value="!!(hours.bank && hours.bank.enabled)" label="储蓄所营业"
                     @update:model-value="saveHours('bank', { enabled: !(hours.bank && hours.bank.enabled) })" />
      </div>
      <div v-if="hours.bank && hours.bank.enabled" class="frm-row">
        <label class="fld w64"><span>开门</span><input v-model.number="hours.bank.open_hour" type="number" min="0" max="23" /></label>
        <label class="fld w64"><span>打烊</span><input v-model.number="hours.bank.close_hour" type="number" min="1" max="24" /></label>
        <button class="ok" @click="saveHours('bank')">保存</button>
      </div>
      <p class="dim mt6">默认：打卡 7:00–21:00，储蓄所 8:00–20:00。改时间只是换入口开关，已有记录、余额和利息都不受影响。</p>
    </section>

    <section class="a-card enter">
      <h3>修改家长密码</h3>
      <p class="dim">当前账号 {{ meAccount || '—' }}</p>
      <form class="settings-form" @submit.prevent="changePin">
        <label class="fld">
          <span>当前密码</span>
          <input v-model="pinForm.cur" type="password" autocomplete="current-password" />
        </label>
        <label class="fld">
          <span>新密码</span>
          <input v-model="pinForm.next" type="password" autocomplete="new-password" placeholder="至少 8 位" />
        </label>
        <label class="fld">
          <span>确认新密码</span>
          <input v-model="pinForm.confirm" type="password" autocomplete="new-password" />
        </label>
        <button class="ok" type="submit">保存新密码</button>
      </form>
    </section>
</template>
