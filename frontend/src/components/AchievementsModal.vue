<script setup>
// 成就墙弹窗：按系列分组展示，NEW 成就自动弹出详情并回执已读。
// 用法：父组件 <AchievementsModal ref="achRef" />，调 achRef.value.open()。
import { ref, computed } from 'vue'
import { Medal } from '@lucide/vue'
import { api } from '../api.js'
import { achIcon } from '../icons.js'
import { achievements, achOn, achNew, newAchCount, showToast } from '../store.js'
import { confettiStyle } from '../celebrate.js'

const SERIES_NAME = { milestone: '里程碑', study: '学科', habit: '坚持', wealth: '阳光' }
const SERIES_ORDER = ['milestone', 'study', 'habit', 'wealth']
const RARITY_LABEL = { bronze: '青铜', silver: '白银', gold: '黄金', legend: '传说' }

const open = ref(false)
const achModal = ref(null)

const achBySeries = computed(() => {
  const groups = {}
  for (const a of achievements.value) {
    const s = a.series || 'milestone'
    ;(groups[s] ||= []).push(a)
  }
  return SERIES_ORDER.filter(s => groups[s]).concat(Object.keys(groups).filter(s => !SERIES_ORDER.includes(s)))
    .map(s => ({ id: s, name: SERIES_NAME[s] || s, items: groups[s] }))
})
function seriesTiers(items) {
  const seen = []
  for (const a of items) {
    if (a.tier && !seen.includes(a.tier)) seen.push(a.tier)
  }
  return seen
}
function timeAgo(iso) {
  if (!iso) return ''
  const t = new Date(iso)
  if (Number.isNaN(t.getTime())) return ''
  const sec = Math.max(0, (Date.now() - t.getTime()) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return Math.floor(sec / 60) + ' 分钟前'
  if (sec < 86400) return Math.floor(sec / 3600) + ' 小时前'
  const d = Math.floor(sec / 86400)
  if (d === 1) return '昨天'
  if (d < 30) return d + ' 天前'
  return String(iso).slice(0, 10)
}
function pickUnseenAch() {
  const fresh = achievements.value.filter(achNew)
  if (!fresh.length) return null
  const order = { legend: 0, gold: 1, silver: 2, bronze: 3 }
  fresh.sort((a, b) => (order[a.rarity] ?? 9) - (order[b.rarity] ?? 9))
  return fresh[0]
}

async function show() {
  open.value = true
  try {
    achievements.value = await api.achievements()
    if (!achModal.value) achModal.value = pickUnseenAch()
  } catch {}
}
function openDetail(a) { achModal.value = a }
async function closeDetail() {
  const a = achModal.value
  achModal.value = null
  if (a && achNew(a)) {
    try { await api.markAchievementSeen(a.id) } catch {}
    a.seen = 1
    const next = pickUnseenAch()
    if (next) achModal.value = next
  }
}
defineExpose({ open: show })
</script>

<template>
  <div v-if="open" class="mask" @click.self="open = false">
    <div class="shop-modal ach-modal">
      <h3>
        <Medal class="ico" :size="18" /> 我的成就
        <span v-if="newAchCount" class="ach-head-new">{{ newAchCount }} 个新</span>
      </h3>
      <div class="ach-body">
        <details v-for="g in achBySeries" :key="g.id" class="ach-series" open>
          <summary>{{ g.name }} ({{ g.items.filter(achOn).length }}/{{ g.items.length }})</summary>
          <div v-for="tier in seriesTiers(g.items)" :key="tier" class="tier-track">
            <div v-for="a in g.items.filter(x => x.tier === tier)" :key="a.id"
              class="ach-cell" :class="[a.rarity, { on: achOn(a), new: achNew(a) }]"
              @click="openDetail(a)">
              <div class="ach-icon"><component :is="achIcon(a.icon)" class="ico" :size="24" /></div>
              <div class="ach-name">{{ a.name }}</div>
              <div class="ach-prog">{{ Math.min(a.current, a.target) }}/{{ a.target }}</div>
              <span v-if="achNew(a)" class="new-dot">NEW</span>
            </div>
            <span class="tier-progress">{{ (g.items.find(x => x.tier === tier) || {}).chain_progress }}</span>
          </div>
          <div class="ach-grid">
            <div v-for="a in g.items.filter(x => !x.tier)" :key="a.id"
              class="ach-cell" :class="[a.rarity, { on: achOn(a), new: achNew(a) }]"
              @click="openDetail(a)">
              <div class="ach-icon"><component :is="achIcon(a.icon)" class="ico" :size="24" /></div>
              <div class="ach-name">{{ a.name }}</div>
              <div class="ach-prog">{{ Math.min(a.current, a.target) }}/{{ a.target }}</div>
              <span v-if="achNew(a)" class="new-dot">NEW</span>
            </div>
          </div>
        </details>
      </div>
      <button class="ghost" @click="open = false">关闭</button>
    </div>
    <div v-if="achModal" class="ach-pop" @click.self="closeDetail">
      <div class="confetti" v-if="achNew(achModal)">
        <span v-for="i in 18" :key="'a'+i" :style="confettiStyle(i)"></span>
      </div>
      <div :class="['ach-detail', achModal.rarity]">
        <div class="ach-icon"><component :is="achIcon(achModal.icon)" class="ico" :size="48" /></div>
        <h3>{{ achModal.name }}</h3>
        <p>{{ achModal.desc }}</p>
        <p class="rarity-label">{{ RARITY_LABEL[achModal.rarity] || achModal.rarity }}</p>
        <p v-if="achModal.earned_at" class="earned-time">{{ timeAgo(achModal.earned_at) }}获得</p>
        <p v-else class="earned-time">{{ Math.min(achModal.current, achModal.target) }}/{{ achModal.target }}</p>
        <button class="do" @click="closeDetail">关闭</button>
      </div>
    </div>
  </div>
</template>
