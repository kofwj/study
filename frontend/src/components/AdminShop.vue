<script setup>
// 家长工作台 · 阳光（商店 + 银行 + 等级 + 扣分，四段合一页）
// 数据由 Admin.vue 的 shop 包持有；本页表单与提交在子组件，
// 银行目标（脏条快照）与扣分开关仍由壳负责，用 emit 触发。
import { ref, reactive, computed } from 'vue'
import { Star } from '@lucide/vue'
import { api } from '../api.js'
import { rankIcon } from '../icons.js'
import { useAdminEdit } from '../adminEdit.js'

const props = defineProps({
  rewards: { type: Array, default: () => [] },
  ranks: { type: Array, default: () => [] },
  penalties: { type: Array, default: () => [] },
  penaltySummary: { type: Object, default: () => ({ net: 0, count: 0, amount: 0, by_reason: [] }) },
  penaltyEnabled: { type: Boolean, default: false },
  bankData: { type: Object, default: () => ({ enabled: false, balance: 0, pocket_balance: 0, goal: null, requests: [], ledger: [] }) },
  bankRequests: { type: Array, default: () => [] },
  bankGoal: { type: Object, required: true },
  bankInterest: { type: Object, required: true },
  bankBusy: { type: Boolean, default: false },
  isOwner: { type: Boolean, default: false },
  kidName: { type: String, default: '' },
  showToast: { type: Function, required: true },
  withBusy: { type: Function, required: true },
})
const emit = defineEmits(['reload', 'reload-bank', 'save-bank-goal', 'toggle-penalty'])

const { editKind, editId, findEditRow, clearEdit, beginEdit, cancelEdit, isEditing } = useAdminEdit()

// 本页自己的提交忙碌（壳的 bankBusy 只管「保存目标」那一颗按钮）
const busy = ref(false)
const bankBusy = computed(() => props.bankBusy || busy.value)

const newReward = reactive({ name: '', price: 30, category: '娱乐' })
const newRank = reactive({ name: '', min_sunshine: 0 })
const newPenalty = reactive({ amount: 1, reason: '磨蹭', note: '' })
const bankHistoryOpen = ref(false)
const penaltySubmitting = ref(false)  // 扣分提交中
const PENALTY_REASONS = ['磨蹭', '没完成约定', '没礼貌', '其他']
const PENALTY_AMOUNTS = [1, 2, 3, 5]
const pendingBankRequests = computed(() => (props.bankRequests || []).filter(r => r.status === 'pending'))
const historyBankRequests = computed(() => (props.bankRequests || []).filter(r => r.status !== 'pending'))
const penaltyReasonRows = computed(() => (props.penaltySummary.by_reason || []).filter(x => x.count > 0))
const maxPenaltyAmount = computed(() => Math.max(1, ...penaltyReasonRows.value.map(x => x.amount || 0)))
async function addReward() {
  if (!newReward.name || !newReward.price) return props.showToast('填名称和价格')
  await props.withBusy(async () => {
    await api.admin.createReward({ ...newReward })
    Object.assign(newReward, { name: '', price: 30, category: '娱乐' })
    props.showToast('已新增'); emit('reload')
  })
}
async function saveReward(r) { await props.withBusy(async () => { await api.admin.updateReward(r.id, r); clearEdit(); props.showToast('已保存') }) }
async function delReward(id) { if (!confirm('删除这个奖励？')) return; await props.withBusy(async () => { await api.admin.delReward(id); emit('reload') }) }
async function addRank() {
  if (!newRank.name) return props.showToast('填等级名')
  await props.withBusy(async () => {
    await api.admin.createRank({ ...newRank })
    Object.assign(newRank, { name: '', min_sunshine: 0 })
    props.showToast('已新增'); emit('reload')
  })
}
async function saveRank(r) { await props.withBusy(async () => { await api.admin.updateRank(r.id, r); clearEdit(); props.showToast('已保存') }) }
async function delRank(id) {
  if (!confirm('删除这个等级？')) return
  try { await api.admin.delRank(id); emit('reload') } catch (e) { props.showToast(e.message) }
}
async function addPenalty() {
  if (!props.penaltyEnabled) return props.showToast('扣分未开启')
  if (penaltySubmitting.value) return  // 防止重复提交
  
  const amount = Number(newPenalty.amount)
  if (!Number.isInteger(amount) || amount < 1) return props.showToast('扣分要是正整数')
  if (newPenalty.reason === '其他' && !String(newPenalty.note || '').trim()) return props.showToast('选「其他」时要写备注')
  const who = props.kidName || '这个孩子'
  if (!confirm(`给「${who}」扣 ${amount} 阳光（${newPenalty.reason}）？余额扣到 0 为止，等级不变。`)) return
  
  penaltySubmitting.value = true
  try {
    await api.admin.createPenalty({ amount, reason: newPenalty.reason, note: newPenalty.note })
    Object.assign(newPenalty, { amount: 1, reason: '磨蹭', note: '' })
    props.showToast('已记下扣分')
    emit('reload')
  } catch (e) { 
    props.showToast(e.message) 
  } finally {
    penaltySubmitting.value = false
  }
}
async function cancelPenalty(id) {
  if (penaltySubmitting.value) return
  if (!confirm('撤回这笔扣分？阳光会加回去，等级不变。')) return
  penaltySubmitting.value = true
  try {
    await api.admin.cancelPenalty(id)
    props.showToast('已撤回')
    emit('reload')
  } catch (e) { props.showToast(e.message) }
  finally { penaltySubmitting.value = false }
}
async function toggleBank() {
  busy.value = true
  try { Object.assign(props.bankData, await api.admin.setBankEnabled(!props.bankData.enabled)); props.showToast(props.bankData.enabled ? '已开启阳光银行' : '已关闭阳光银行') }
  catch (e) { props.showToast(e.message) }
  finally { busy.value = false }
}
async function saveBankInterest() {
  busy.value = true
  try {
    const r = await api.admin.saveBankInterestConfig({ enabled: props.bankInterest.enabled, cycle: props.bankInterest.cycle, rate: props.bankInterest.rate, threshold: props.bankInterest.threshold })
    Object.assign(props.bankInterest, r)
    props.showToast('利息配置已保存')
  } catch (e) { props.showToast(e.message) }
  finally { busy.value = false }
}
async function bankGoalDeliver() {
  if (!confirm('确认这个目标已经兑现？')) return
  try { Object.assign(props.bankData, await api.admin.deliverBankGoal()); props.showToast('已标记兑现') }
  catch (e) { props.showToast(e.message) }
}
async function handleBankRequest(id, action) {
  try { await (action === 'approve' ? api.admin.approveBankRequest(id) : api.admin.rejectBankRequest(id)); props.showToast(action === 'approve' ? '已批准取出' : '已拒绝申请'); emit('reload-bank') }
  catch (e) { props.showToast(e.message) }
}
async function settleInterestNow() {
  try {
    const r = await api.admin.settleInterestNow()
    props.showToast(r.settled ? `已结算利息 ${r.interest} 颗` : '暂无需结算')
    emit('reload-bank')
  } catch (e) { props.showToast(e.message) }
}
// ---- 脏条要的三件事（壳通过 ref 调用）----
function filled(v) { return String(v ?? '').trim() !== '' }
function isAddDirty() {
  if (filled(newReward.name) || Number(newReward.price) !== 30 || (newReward.category || '') !== '娱乐') return true
  if (filled(newRank.name) || Number(newRank.min_sunshine) !== 0) return true
  return false
}
function discardAdd() {
  Object.assign(newReward, { name: '', price: 30, category: '娱乐' })
  Object.assign(newRank, { name: '', min_sunshine: 0 })
}
async function saveCurrentEdit() {
  const row = findEditRow(editKind.value, editId.value)
  if (!row) return
  if (editKind.value === 'reward') await saveReward(row)
  else if (editKind.value === 'rank') await saveRank(row)
}
defineExpose({ isAddDirty, discardAdd, saveCurrentEdit })
</script>

<template>
    <section class="a-card enter">
      <h3>阳光</h3>
      <h4 class="w-h">兑换商店</h4>
      <div class="task-row" v-for="r in rewards" :key="r.id">
        <template v-if="isEditing('reward', r.id)">
          <label class="fld grow"><span>奖励名</span><input v-model="r.name" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="r.price" type="number" /></label>
          <label class="fld w84"><span>分类</span><input v-model="r.category" /></label>
          <div class="ops">
            <button class="ok" @click="saveReward(r)">保存</button>
            <button class="ghost-s" @click="cancelEdit">取消</button>
          </div>
        </template>
        <template v-else>
          <span class="task-readonly-title">{{ r.name }}</span>
          <span class="badge daily">{{ r.price }} 阳光</span>
          <span class="dim">{{ r.category }}</span>
          <div class="ops">
            <button class="ghost-s" @click="beginEdit('reward', r)">改</button>
            <button class="del" @click="delReward(r.id)">删</button>
          </div>
        </template>
      </div>
      <div class="add-box">
        <div class="add-title">新增奖励</div>
        <div class="frm-row">
          <label class="fld grow"><span>奖励名</span><input v-model="newReward.name" placeholder="如：看动画30分钟" /></label>
          <label class="fld w64"><span>阳光</span><input v-model.number="newReward.price" type="number" placeholder="30" /></label>
          <label class="fld w84"><span>分类</span><input v-model="newReward.category" placeholder="如：娱乐" /></label>
        </div>
        <button class="ok wide" @click="addReward">＋新增奖励</button>
      </div>

    <!-- 阳光银行 -->
      <h4 class="w-h">阳光银行{{ kidName ? ' · ' + kidName : '' }}</h4>
      <div class="lock-row">
        <span class="badge">孩子端开关</span>
        <span class="grow">关闭后不显示入口，余额和目标保留</span>
        <button type="button" :class="['toggle', { on: bankData.enabled }]" @click="toggleBank" :disabled="bankBusy">{{ bankData.enabled ? '开' : '关' }}</button>
      </div>
      <div class="sun-hero bank-admin-hero">
        <div class="sun-box"><span>银行余额</span><b>{{ bankData.balance }}</b></div>
        <div class="sun-box"><span>口袋余额</span><b>{{ bankData.pocket_balance }}</b></div>
      </div>
      <div class="add-box">
        <div class="add-title">一个存钱目标</div>
        <div class="frm-row">
          <label class="fld grow"><span>目标名称</span><input v-model="bankGoal.name" maxlength="40" placeholder="如：周末去公园" /></label>
          <label class="fld w84"><span>需要阳光</span><input v-model.number="bankGoal.target" type="number" min="1" max="10000" /></label>
          <button class="ok" @click="$emit('save-bank-goal')">保存目标</button>
        </div>
        <div v-if="bankData.goal" class="dim">已存 {{ bankData.goal.saved }} / {{ bankData.goal.target }} · {{ bankData.goal.reached ? '已达成' : '进行中' }}</div>
        <button v-if="bankData.goal?.reached" class="ok mt8" @click="bankGoalDeliver">标记已兑现</button>
      </div>
      <h4 class="w-h">取出申请</h4>
      <div v-if="!pendingBankRequests.length" class="dim">还没有取出申请。</div>
      <div v-for="r in pendingBankRequests" :key="r.id" class="apv-row">
        <div class="apv-info"><span class="apv-name">{{ r.kid_name }}申请取出 {{ r.amount }} 颗</span><span class="dim">{{ r.created_at }}</span></div>
        <div class="apv-right"><button class="ok" @click="handleBankRequest(r.id, 'approve')">批准</button><button class="del" @click="handleBankRequest(r.id, 'reject')">拒绝</button></div>
      </div>
      <button v-if="historyBankRequests.length" type="button" class="ghost-s rules-toggle" @click="bankHistoryOpen = !bankHistoryOpen">{{ bankHistoryOpen ? '收起已处理' : '看已处理' }}</button>
      <div v-if="bankHistoryOpen" v-for="r in historyBankRequests" :key="'h-' + r.id" class="apv-row">
        <div class="apv-info"><span class="apv-name">{{ r.kid_name }}申请取出 {{ r.amount }} 颗</span><span class="dim">{{ r.created_at }}</span></div>
        <div class="apv-right"><span class="st delivered">{{ r.status === 'approved' ? '已批准' : '已拒绝' }}</span></div>
      </div>
      <p class="dim mt14">银行里的阳光不能用于兑换商店；取出必须由家长批准。</p>
      
      <h4 class="w-h">利息设置</h4>
      <div class="lock-row">
        <span class="badge">利息开关</span>
        <span class="grow">关闭后不再结算利息</span>
        <button type="button" :class="['toggle', { on: bankInterest.enabled }]" @click="bankInterest.enabled = !bankInterest.enabled; saveBankInterest()" :disabled="bankBusy">{{ bankInterest.enabled ? '开' : '关' }}</button>
      </div>
      <div v-if="bankInterest.enabled" class="frm-row">
        <label class="fld"><span>结算周期</span>
          <select v-model="bankInterest.cycle" @change="saveBankInterest">
            <option value="weekly">每周六</option>
            <option value="biweekly">每两周六</option>
            <option value="monthly">每月最后一天</option>
          </select>
        </label>
        <label class="fld"><span>利率 (%)</span>
          <input v-model.number="bankInterest.rate" type="number" min="0" max="10" step="0.5" @blur="saveBankInterest" />
        </label>
        <label class="fld"><span>起存点</span>
          <select v-model.number="bankInterest.threshold" @change="saveBankInterest">
            <option :value="0">不限</option>
            <option :value="10">10 颗</option>
            <option :value="20">20 颗</option>
            <option :value="50">50 颗</option>
            <option :value="100">100 颗</option>
          </select>
        </label>
      </div>
      <div v-if="bankInterest.enabled" class="dim">
        <p>💡 利息是什么？银行为「存在这里的阳光」付一点报酬，鼓励孩子延迟满足、积累财富。</p>
        <p>这里的利率只管<strong>活期</strong>。孩子还能自己开定存单：7 天 2%、10 天 3%、15 天 5%、30 天 8%、60 天 12%。到期一次结息；提前支取按已过天数打五折，当天存当天取没有利息。</p>
        <p>利率不宜过高，否则孩子可能失去做任务的动力。建议低年级 3%–5%、高年级 5%–8%。</p>
        <p v-if="bankInterest.last_settle">上次结算：{{ bankInterest.last_settle }}</p>
        <button v-if="isOwner" class="ghost-s mt8" @click="settleInterestNow">补结算上一期利息</button>
      </div>
    </section>

    <section class="a-card enter">
      <h3>记下扣分{{ kidName ? ' · ' + kidName : '' }}</h3>
      <div class="lock-row">
        <span class="badge">扣分开关</span>
        <span class="grow">{{ penaltyEnabled ? '已开' : '未开' }}</span>
        <button v-if="isOwner" :class="['toggle', { on: penaltyEnabled }]" @click="$emit('toggle-penalty')">{{ penaltyEnabled ? '已开' : '未开' }}</button>
        <span v-else class="dim">只有创建者能开关</span>
      </div>
      <template v-if="penaltyEnabled">
        <div class="add-box">
          <div class="add-title">记一笔</div>
          <div class="chip-row">
            <span class="chip-label">扣多少</span>
            <button v-for="n in PENALTY_AMOUNTS" :key="n" type="button" :class="['chip', { on: newPenalty.amount === n }]" @click="newPenalty.amount = n">-{{ n }}</button>
          </div>
          <div class="chip-row">
            <span class="chip-label">原因</span>
            <button v-for="r in PENALTY_REASONS" :key="r" type="button" :class="['chip', { on: newPenalty.reason === r }]" @click="newPenalty.reason = r">{{ r }}</button>
          </div>
          <label class="fld">
            <span>{{ newPenalty.reason === '其他' ? '说明（必填）' : '说明（可选）' }}</span>
            <input v-model="newPenalty.note" maxlength="40" placeholder="如：约好 8 点写完还在玩" />
          </label>
          <button class="ok wide" @click="addPenalty" :disabled="penaltySubmitting">{{ penaltySubmitting ? '提交中...' : '确认扣 ' + newPenalty.amount + ' 阳光' }}</button>
        </div>
        <div v-if="penaltySummary.count" class="pen-sum">
          <p class="dim">{{ penaltySummary.count }} 笔 · 净扣 {{ penaltySummary.amount }}</p>
          <div class="w-subj">
            <div v-for="s in penaltyReasonRows" :key="s.reason" class="w-subj-row">
              <span class="w-subj-name">{{ s.reason }}</span>
              <div class="w-subj-track"><i :style="{ width: (s.amount / maxPenaltyAmount * 100) + '%' }"></i></div>
              <span class="w-subj-num">{{ s.count }} 笔 · -{{ s.amount }}</span>
            </div>
          </div>
        </div>
        <div v-if="!penalties.length" class="dim mt8">还没有扣分记录。</div>
        <div class="apv-row" v-for="p in penalties" :key="p.id">
          <div class="apv-info">
            <span class="apv-name">{{ p.reason || p.note || '扣分' }}</span>
            <span class="dim">{{ p.note && p.note !== p.reason ? p.note + ' · ' : '' }}{{ p.date }}</span>
          </div>
          <div class="apv-right">
            <span class="pen-amt">{{ p.delta }}</span>
            <span v-if="p.cancelled" class="st delivered">已撤回</span>
            <button v-else class="ghost-s" @click="cancelPenalty(p.id)">撤回</button>
          </div>
        </div>
      </template>

    </section>

    <section class="a-card enter">
      <h3>成长等级</h3>
      <div class="task-row" v-for="r in ranks" :key="r.id">
        <span class="rank-icon"><component :is="rankIcon(r.icon)" class="ico" :size="18" /></span>
        <template v-if="isEditing('rank', r.id)">
          <label class="fld grow"><span>等级名</span><input v-model="r.name" /></label>
          <label class="fld w84"><span>累计阳光 ≥</span><input v-model.number="r.min_sunshine" type="number" /></label>
          <div class="ops">
            <button class="ok" @click="saveRank(r)">保存</button>
            <button class="ghost-s" @click="cancelEdit">取消</button>
          </div>
        </template>
        <template v-else>
          <span class="task-readonly-title">{{ r.name }}</span>
          <span class="dim">累计阳光 ≥ {{ r.min_sunshine }}</span>
          <div class="ops">
            <button class="ghost-s" @click="beginEdit('rank', r)">改</button>
            <button class="del" @click="delRank(r.id)">删</button>
          </div>
        </template>
      </div>
      <div class="add-box">
        <div class="add-title">新增等级</div>
        <div class="frm-row">
          <span class="rank-icon"><Star class="ico" :size="18" /></span>
          <label class="fld grow"><span>等级名</span><input v-model="newRank.name" placeholder="如：阳光萌新" /></label>
          <label class="fld w84"><span>累计阳光 ≥</span><input v-model.number="newRank.min_sunshine" type="number" placeholder="0" /></label>
        </div>
        <button class="ok wide" @click="addRank">＋新增等级</button>
      </div>
    </section>
</template>
