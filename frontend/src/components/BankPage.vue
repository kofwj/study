<script setup>
// 阳光储蓄所 tab 页：活期/定存存取、存单、金库存折。
// 数据挂载时自拉（tab 每次切入重新挂载）；存取成功后 emit('changed') 让父级刷新等级/账本。
import { ref, computed } from 'vue'
import { Landmark } from '@lucide/vue'
import { api } from '../api.js'
import { showToast } from '../store.js'

const emit = defineEmits(['changed'])

const bankData = ref({ enabled: false, balance: 0, locked: 0, available: 0, pocket_balance: 0, goal: null, requests: [], ledger: [], interest: null, deposit_terms: [], deposits: [], hours: { open: true, from: '08:00', until: '20:00', hint: '', now: '' } })
const bankAmount = ref(5)
const bankDays = ref(0)
const bankBusy = ref(false)
const bankPassbookOpen = ref(false)

const bankPending = computed(() => (bankData.value.requests || []).filter(r => r.status === 'pending'))
const bankActiveDeposits = computed(() => (bankData.value.deposits || []).filter(d => d.state === 'active'))
const bankClosed = computed(() => bankData.value.hours && bankData.value.hours.open === false)
function bankClosedHint() {
  return (bankData.value.hours && bankData.value.hours.hint) || '储蓄所每天 8:00 到 20:00 营业'
}
function guardBankOpen() {
  if (!bankClosed.value) return true
  showToast(bankClosedHint())
  return false
}

function bankInterestCycle(cycle) {
  if (cycle === 'biweekly') return '每两周'
  if (cycle === 'monthly') return '每月'
  return '每周六'
}
function bankInterestLabel(it) {
  if (!it) return ''
  return `活期 ${bankInterestCycle(it.cycle)} ${it.rate}%`
}
function bankTermOn(days) {
  return Number(bankDays.value) === Number(days)
}
function pickBankDays(days) {
  bankDays.value = Number(bankDays.value) === Number(days) ? 0 : Number(days)
}
function bankVaultPct() {
  const bal = Number(bankData.value.balance) || 0
  const g = bankData.value.goal
  if (g && Number(g.target) > 0) return Math.max(0, Math.min(100, Math.round(bal / Number(g.target) * 100)))
  if (bal <= 0) return 0
  return Math.max(8, Math.min(88, Math.round(bal / Math.max(bal, 100) * 80)))
}
function bankPassbookTitle(row) {
  if (row.reason === 'bank_interest') {
    if (String(row.note || '').includes('提前')) return '提前支取利息'
    if (String(row.note || '').includes('到期') || String(row.note || '').includes('存单')) return '定存到期利息'
    const c = bankData.value.interest && bankData.value.interest.cycle
    if (c === 'biweekly') return '两周结息'
    if (c === 'monthly') return '本月结息'
    return '本周结息'
  }
  if (row.delta > 0) return String(row.note || '').includes('定存') ? '开了一张存单' : '存进金库'
  return '柜员开了门'
}
function bankRequestStatus(st) {
  if (st === 'pending') return '等家长开门'
  if (st === 'approved') return '柜员开了门'
  return '这张单没过'
}
function bankDepositHint(d) {
  if (!d) return ''
  if (d.state === 'matured') return `到期已结 ${d.interest_paid} 颗`
  if (d.state === 'broken') return `提前支取，利息 ${d.interest_paid} 颗`
  if (d.left_days === 0) return '今天到期'
  return `还要等 ${d.left_days} 天 · 到期 +${d.mature_interest}`
}

async function load() {
  try {
    const b = await api.bank()
    if (b) bankData.value = b
  } catch {}
}
load()

async function bankMove(kind) {
  if (!guardBankOpen()) return
  const amount = Number(bankAmount.value)
  if (!Number.isInteger(amount) || amount < 1) return showToast('请输入正整数阳光')
  if (bankBusy.value) return

  bankBusy.value = true
  try {
    if (kind === 'deposit') {
      const days = Number(bankDays.value) || 0
      bankData.value = await api.bankDeposit(amount, days || undefined)
      showToast(days ? `开了 ${days} 天存单，存进 ${amount} 颗` : `已存进金库 ${amount} 颗阳光`)
    } else {
      bankData.value = await api.bankWithdraw(amount)
      showToast(`已请柜员开门，取出 ${amount} 颗`)
    }
    emit('changed')
  } catch (e) { showToast(e.message) }
  finally { bankBusy.value = false }
}
async function bankBreak(d) {
  if (!guardBankOpen()) return
  if (!d || bankBusy.value) return

  const pay = Number(d.early_interest) || 0
  const ok = window.confirm(pay ? `提前支取只给一半进度的利息，大约 ${pay} 颗。确定吗？` : '今天刚存，提前支取没有利息。确定吗？')
  if (!ok) return
  bankBusy.value = true
  try {
    bankData.value = await api.bankBreakDeposit(d.id)
    showToast(pay ? `提前支取了，利息 ${pay} 颗` : '提前支取了，这次没有利息')
    emit('changed')
  } catch (e) { showToast(e.message) }
  finally { bankBusy.value = false }
}
</script>

<template>
  <div v-if="!bankData.enabled" class="coming-page">
    <div class="coming">
      <Landmark class="ico" :size="36" />
      <strong>阳光储蓄所</strong>
      <em>卷帘门还没拉开</em>
      <p>存折还在印，以后能把阳光存进金库。</p>
    </div>
  </div>
  <template v-else>
    <div class="bank-hall">
      <header class="bank-sign">
        <div class="bank-sign-board">
          <span class="bank-open-lamp" :class="{ closed: bankClosed }">{{ bankClosed ? '已打烊' : '营业中' }}</span>
          <h1>阳光储蓄所</h1>
          <p>{{ bankClosed ? bankClosedHint() : '每天 8:00 到 20:00 营业。活期随时可取；定存锁几天，到期一次多给一点。' }}</p>
        </div>
        <div v-if="bankData.interest || bankData.locked" class="bank-sign-rate">
          <strong v-if="bankData.interest">{{ bankInterestLabel(bankData.interest) }}</strong>
          <strong v-else>定存锁着 {{ bankData.locked }} 颗</strong>
          <small v-if="bankData.interest">只算没锁进存单的阳光</small>
          <small v-if="bankData.interest && bankData.interest.threshold">活期满 {{ bankData.interest.threshold }} 颗才结息</small>
          <small v-if="bankData.locked">定存锁着 {{ bankData.locked }} 颗，不拿活期息</small>
        </div>
      </header>

      <div class="bank-room">
        <section class="bank-counter" :class="{ busy: bankBusy, closed: bankClosed }">
          <div class="bank-window">
            <Landmark class="bank-teller-ico" :size="28" />
            <div>
              <strong>{{ bankClosed ? '柜台下班了' : (bankBusy ? '正在递单' : '柜台') }}</strong>
              <small>{{ bankClosed ? '现在不能存取，金库和存折还能看' : (bankDays ? '先选天数，再存成定存' : '不选天数就是活期') }}</small>
            </div>

          </div>

          <div class="bank-tray">
            <span class="bank-kicker">口袋</span>
            <strong>{{ bankData.pocket_balance }}</strong>
            <span>颗</span>
          </div>

          <div class="bank-chips">
            <button v-for="n in [5, 10, 20, 50]" :key="n" type="button"
              :class="['bank-chip', { on: bankAmount === n }]"
              :disabled="bankClosed"
              @click="bankAmount = n">{{ n }}</button>
            <input v-model.number="bankAmount" type="number" min="1" class="bank-chip-input" placeholder="自己写" :disabled="bankClosed" />
          </div>

          <div class="bank-terms">
            <span class="bank-kicker">存多久</span>
            <button type="button" :class="['bank-chip', { on: !bankDays }]" :disabled="bankClosed" @click="bankDays = 0">
              活期
              <small>随时可取</small>
            </button>
            <button v-for="t in (bankData.deposit_terms || [])" :key="t.days" type="button"
              :class="['bank-chip', { on: bankTermOn(t.days) }]"
              :disabled="bankClosed"
              @click="pickBankDays(t.days)">

              {{ t.label }}
              <small>{{ t.hint }}</small>
            </button>
          </div>

          <div class="bank-desk-btns">
            <button class="bank-act in" :disabled="bankBusy || bankClosed || bankData.pocket_balance < bankAmount" @click="bankMove('deposit')">
              <span>{{ bankDays ? '开存单' : '存进金库' }}</span>
              <small>{{ bankDays ? bankDays + ' 天后再给利息' : '从口袋转入活期' }}</small>
            </button>
            <button class="bank-act out" :disabled="bankBusy || bankClosed || (bankData.available || 0) < bankAmount" @click="bankMove('withdraw')">
              <span>请柜员开门</span>
              <small>只能取活期 {{ bankData.available || 0 }} 颗</small>
            </button>
          </div>


          <div v-if="bankActiveDeposits.length" class="bank-deposits">
            <div v-for="d in bankActiveDeposits" :key="d.id" class="bank-dep">
              <div>
                <strong>{{ d.amount }} 颗 · {{ d.days }} 天</strong>
                <small>{{ bankDepositHint(d) }}</small>
              </div>
              <button type="button" class="ghost" :disabled="bankBusy || bankClosed" @click.stop="bankBreak(d)">提前支取</button>

            </div>
          </div>

          <div v-if="bankPending.length" class="bank-wait">
            <div v-for="r in bankPending" :key="r.id" class="bank-wait-slip">
              <strong>取出 {{ r.amount }} 颗</strong>
              <em>等家长开门</em>
            </div>
          </div>
        </section>

        <section class="bank-vault" :class="{ reached: bankData.goal?.reached }" @click="bankPassbookOpen = !bankPassbookOpen">
          <div class="bank-vault-door">
            <i class="bank-vault-glow" :style="{ height: bankVaultPct() + '%' }"></i>
            <div class="bank-vault-copy">
              <span class="bank-kicker">金库</span>
              <strong>{{ bankData.balance }}</strong>
              <span>颗</span>
              <small v-if="bankData.locked">活期 {{ bankData.available || 0 }} · 定存 {{ bankData.locked }}</small>
            </div>
          </div>
          <p v-if="bankData.goal?.reached" class="bank-vault-seal">攒够啦，告诉家长来开门</p>
          <p v-else-if="bankData.goal" class="bank-vault-note">{{ bankData.goal.name }} · {{ bankData.goal.saved }} / {{ bankData.goal.target }}</p>
          <p v-else class="bank-vault-note dim">家长设一个小心愿，金库就开始涨</p>
          <small class="bank-vault-hint">{{ bankPassbookOpen ? '再点收起存折' : '点金库看存折' }}</small>

          <div v-if="bankPassbookOpen" class="bank-passbook" @click.stop>
            <h3>存折</h3>
            <div v-if="!(bankData.ledger || []).length" class="bank-pass-empty">还没有进出记录</div>
            <div v-for="row in (bankData.ledger || []).slice(0, 10)" :key="row.id" class="bank-pass-row">
              <span>{{ bankPassbookTitle(row) }}</span>
              <small>{{ row.date }}</small>
              <b :class="row.delta > 0 ? 'plus' : 'minus'">{{ row.delta > 0 ? '+' : '' }}{{ row.delta }}</b>
            </div>
            <div v-for="r in (bankData.requests || []).filter(x => x.status !== 'pending').slice(0, 4)" :key="'rq'+r.id" class="bank-pass-row quiet">
              <span>取出 {{ r.amount }} 颗</span>
              <small>{{ String(r.created_at || '').slice(0, 10) }}</small>
              <b>{{ bankRequestStatus(r.status) }}</b>
            </div>
          </div>
        </section>
      </div>
    </div>
  </template>
</template>
