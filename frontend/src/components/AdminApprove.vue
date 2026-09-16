<script setup>
import { ref, computed } from 'vue'
import { Sun, Check } from '@lucide/vue'
// 家长工作台 · 兑换审批（纯视图）
// 数据由 Admin.vue 的 approve 包持有；这里只做筛选展示，动作抛给壳。
const props = defineProps({
  redemptions: { type: Array, default: () => [] },
})
defineEmits(['approve', 'reject', 'deliver'])

const redeemFilter = ref('pending')
const filteredRedemptions = computed(() => {
  const rows = props.redemptions || []
  if (redeemFilter.value === 'pending') return rows.filter(r => r.status === 'pending')
  if (redeemFilter.value === 'done') return rows.filter(r => r.status === 'done')
  return rows.filter(r => r.status !== 'pending' && r.status !== 'done')
})
const redeemEmptyText = computed(() => {
  if (redeemFilter.value === 'pending') return '没有待同意的申请'
  if (redeemFilter.value === 'done') return '没有待兑现的'
  return '还没有结束的记录'
})
</script>

<template>
    <section class="a-card enter">
      <h3>兑换审批与兑现</h3>
      <div class="subj-tabs review-filter">
        <button type="button" :class="['subj-tab', { on: redeemFilter === 'pending' }]" @click="redeemFilter = 'pending'">待同意</button>
        <button type="button" :class="['subj-tab', { on: redeemFilter === 'done' }]" @click="redeemFilter = 'done'">待兑现</button>
        <button type="button" :class="['subj-tab', { on: redeemFilter === 'ended' }]" @click="redeemFilter = 'ended'">已结束</button>
      </div>
      <div v-if="!filteredRedemptions.length" class="dim">{{ redeemEmptyText }}</div>
      <div class="apv-row" v-for="rd in filteredRedemptions" :key="rd.id">
        <div class="apv-info">
          <span class="apv-name">{{ rd.name }}</span>
          <span class="dim">{{ rd.date }} · -{{ rd.price }} <Sun class="ico sun" :size="12" /></span>
        </div>
        <div class="apv-right">
          <template v-if="rd.status === 'pending'">
            <span class="st pending">待同意</span>
            <button class="ok" @click="$emit('approve', rd.id)">同意</button>
            <button class="del" @click="$emit('reject', rd.id)">拒绝</button>
          </template>
          <template v-else-if="rd.status === 'done'">
            <span class="st done">已扣阳光</span>
            <button class="ok ghost-o" @click="$emit('deliver', rd.id)">标记已兑现</button>
          </template>
          <span v-else-if="rd.status === 'rejected'" class="st pending">已拒绝</span>
          <span v-else class="st delivered">已兑现 <Check class="ico" :size="12" /></span>
        </div>
      </div>
    </section>
</template>
