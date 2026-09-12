<script setup>
// 阳光兑换商店抽屉：奖励列表 + 兑换申请 + 兑换记录。
// 用法：父组件 <ShopDrawer ref="shopRef" @changed="refresh" />，调 shopRef.value.open()。
import { ref } from 'vue'
import { ShoppingCart, ScrollText, Sun } from '@lucide/vue'
import { api } from '../api.js'
import { data, rewards, showToast } from '../store.js'

const emit = defineEmits(['changed'])
const STATUS_TXT = { pending: '等家长同意', done: '已兑换', delivered: '已兑现', rejected: '家长没同意' }

const open = ref(false)
const myRedeems = ref([])
const busy = ref(false)

async function show() {
  open.value = true
  try { myRedeems.value = await api.redemptions() } catch {}
}
async function redeem(reward) {
  if (busy.value) return
  busy.value = true
  try {
    await api.redeem(reward.id)
    showToast(`已提交「${reward.name}」，等家长同意`)
    open.value = false
    emit('changed') // 父级刷新等级/账本
  } catch (e) { showToast(e.message) }
  finally { busy.value = false }
}
defineExpose({ open: show })
</script>

<template>
  <div v-if="open" class="mask" @click.self="open = false">
    <div class="shop-modal enter">
      <h3><ShoppingCart class="ico" :size="18" /> 阳光兑换商店</h3>
      <div class="shop-list">
        <div v-for="r in rewards" :key="r.id" class="shop-item">
          <div>
            <div class="shop-name">{{ r.name }} · 需家长同意</div>
            <div class="shop-price"><Sun class="ico sun" :size="14" /> {{ r.price }}</div>
          </div>
          <button class="do" :disabled="data.level.balance < r.price" @click="redeem(r)">申请</button>
        </div>
      </div>
      <div v-if="myRedeems.length" class="redeem-hist">
        <h4><ScrollText class="ico" :size="15" /> 兑换记录</h4>
        <div v-for="rd in myRedeems" :key="rd.id" class="redeem-row">
          <span>{{ rd.name }}</span>
          <span class="dim-s">-{{ rd.price }} <Sun class="ico sun" :size="12" /></span>
          <span :class="{ wait: rd.status === 'pending' }">{{ STATUS_TXT[rd.status] || rd.status }}</span>
        </div>
      </div>
      <button class="ghost" @click="open = false">关闭</button>
    </div>
  </div>
</template>

<style scoped>
.shop-list { display: flex; flex-direction: column; gap: 12px; }
.shop-item { display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--line); border-radius: var(--radius-md); padding: 12px; }
.shop-price { color: var(--accent); font-weight: 800; }
.redeem-hist { margin-top: 16px; border-top: 1px dashed var(--line); padding-top: 12px; }
.redeem-hist h4 { margin: 0 0 8px; font-size: 13px; color: var(--ink-3); }
.redeem-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; padding: 4px 0; }
.redeem-row .wait { color: var(--accent); font-weight: 700; }
</style>
