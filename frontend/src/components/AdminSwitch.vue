<script setup>
// 家长工作台统一开关
// ------------------------------------------------------------
// 在这之前，家长端的「开 / 关」是一个带文字的胶囊按钮（.admin .toggle），
// 每处还要自己写 `{{ x ? '开' : '关' }}`，行里再重复一遍状态文字。
// 现在统一成一颗真开关：开 = 品牌蓝实心胶囊 + 白色圆钮（滑到右边），关 = iOS 那种浅灰轨道 + 圆钮在左。
//
// 用法（值归父组件时用 :model-value + @update:model-value）：
//   <AdminSwitch :model-value="wordCfg.tts" label="朗读"
//                @update:model-value="saveWordNow({ tts: !wordCfg.tts })" />
//   <AdminSwitch :model-value="progressLock" label="进度锁" :disabled="busy"
//                @update:model-value="$emit('toggle-lock')" />
//
// 无障碍：原生 <button> + role="switch" + aria-checked，Tab 可聚焦、Enter/Space 可切；
// label 是读屏用的名字（视觉上开关左侧本来就有说明文字，所以不再重复渲染文字）。
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'md' },   // md 48×28 | sm 40×24
})

const emit = defineEmits(['update:modelValue', 'change'])

const sizeClass = computed(() => (props.size === 'sm' ? 'sw-sm' : 'sw-md'))

function toggle() {
  if (props.disabled) return
  const next = !props.modelValue
  emit('update:modelValue', next)
  emit('change', next)
}
</script>

<template>
  <button
    type="button"
    role="switch"
    class="sw"
    :class="[sizeClass, { on: modelValue }]"
    :aria-checked="modelValue ? 'true' : 'false'"
    :aria-label="label || undefined"
    :title="label || undefined"
    :disabled="disabled"
    @click="toggle"
  >
    <span class="sw-knob" aria-hidden="true"></span>
  </button>
</template>

<style scoped>
/* 关 = iOS 那种浅灰轨道（#e9e9ea）+ 白钮在左；开 = --brand 品牌蓝实心胶囊 + 白钮在右。
   浅灰轨道在白卡片上本来就淡，所以靠一圈 16% 的内描边定住形状、钮带阴影 —— iOS 也这么做。 */
/* 尺寸两档：md 48×28（页面里）/ sm 40×24（密集行）。 */
.sw {
  --sw-w: 48px;
  --sw-h: 28px;
  --sw-pad: 3px;
  position: relative;
  flex: none;
  width: var(--sw-w);
  height: var(--sw-h);
  padding: 0;
  border: none;
  border-radius: var(--radius-pill);
  background: #e9e9ea;
  box-shadow: inset 0 0 0 1px rgba(28, 39, 51, .16);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color .22s var(--ease), box-shadow .22s var(--ease);
}
.sw-md { --sw-w: 48px; --sw-h: 28px; }
.sw-sm { --sw-w: 40px; --sw-h: 24px; }
.sw.on { background: var(--brand); box-shadow: inset 0 0 0 1px var(--brand); }
.sw:disabled { opacity: .55; cursor: default; }

/* 开关按下时不跟着整块缩放：动的是里面那颗钮（ui.css 的 button:active / :hover 规则在这里让位） */
.sw,
.sw:hover:not(:disabled),
.sw:active:not(:disabled) { transform: none; }

.sw-knob {
  position: absolute;
  top: var(--sw-pad);
  left: var(--sw-pad);
  width: calc(var(--sw-h) - var(--sw-pad) * 2);
  height: calc(var(--sw-h) - var(--sw-pad) * 2);
  border-radius: var(--radius-circle);
  background: #fff;
  box-shadow: 0 2px 5px rgba(28, 39, 51, .20), 0 0 0 1px rgba(28, 39, 51, .08);
  transition: transform .26s var(--spring);
}
.sw.on .sw-knob { transform: translateX(calc(var(--sw-w) - var(--sw-h))); }
</style>
