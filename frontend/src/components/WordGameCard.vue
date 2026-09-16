<script setup>
// P4-b：孩子端「今天」页的英语复习入口卡 —— 点一下去 /word/ 独立页开一局。
// 文案由 ../wordGame.js 的 entryCardText 算（纯函数、scripts/check_word_game.mjs 有断言），
// 这里只渲染，不再写第二份文案。样式全用孩子端现有 class（.card/.circle/.card-body/.fit-bar/.go-link）。
import { computed } from 'vue'
import { ArrowRight } from '@lucide/vue'
import { entryCardText } from '../wordGame.js'

const props = defineProps({
  today: { type: Object, default: () => ({}) },   // GET /api/words/today 的 payload
})
defineEmits(['play'])

const text = computed(() => entryCardText(props.today))
</script>

<template>
  <div class="card enter word-game-card" role="button" tabindex="0" @click="$emit('play')" @keyup.enter="$emit('play')">
    <button type="button" class="circle" @click.stop="$emit('play')"></button>
    <div class="card-body">
      <div class="card-title">{{ text.title }}</div>
      <div class="card-detail">{{ text.detail }}</div>
      <div v-if="text.pct !== null" class="fit-bar">
        <i :style="{ width: text.pct + '%' }"></i><em>{{ text.bar }}</em>
      </div>
      <div class="plus">{{ text.hint }}</div>
      <button type="button" class="go-link" @click.stop="$emit('play')">开一局 <ArrowRight :size="14" /></button>
    </div>
  </div>
</template>

<style scoped>
.word-game-card { cursor: pointer; }
</style>
