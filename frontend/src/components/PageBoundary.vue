<script setup>
// 页面级错误边界：某个页面在渲染期抛错时，只在主区显示一条可读提示；侧栏、顶栏和其它页面照常。
// 起因：v0.3.47 概览页在「没有目标」的真实 payload 下读 null.metric_label 抛错，Vue 把整块子树卸载，
// 页面变成空白且没有任何线索 —— 这类错误必须留下痕迹。
import { ref, onErrorCaptured } from 'vue'

const err = ref('')
onErrorCaptured((e) => {
  err.value = (e && e.message) || String(e)
  return false            // 不再往上传，避免整个工作台被卸载
})
function retry() { err.value = '' }
</script>

<template>
  <div v-if="err" class="w-next pack-err">
    <strong>这一页渲染出错了</strong>
    <span>{{ err }}</span>
    <button type="button" class="ok" @click="retry">重试</button>
  </div>
  <slot v-else />
</template>
