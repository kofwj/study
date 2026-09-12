<script setup>
// 伙伴抽屉 + 进化庆祝层 + 升级庆祝层。
// 用法：父组件 <CompanionDrawer ref="drawerRef" @opened="loadSprites" />，
// 顶栏头像按钮调 drawerRef.value.open()；庆祝层由 store 状态（companionEvolve/celebrate）驱动。
import { ref } from 'vue'
import { PartyPopper } from '@lucide/vue'
import { api } from '../api.js'
import { rankIcon } from '../icons.js'
import { data, companion, companionImage, companionTitle, companionEvolve, companionEvolveImage, celebrate, closeCompanionEvolve, showToast } from '../store.js'
import { confettiStyle } from '../celebrate.js'

const emit = defineEmits(['opened', 'open-sprites'])
const props = defineProps({ spriteButton: { type: String, default: '' } })
const open = ref(false)
const nameDraft = ref('')

function show() {
  nameDraft.value = (companion.value.name || '').trim()
  open.value = true
  emit('opened')
}
defineExpose({ open: show })

async function saveName() {
  try {
    const out = await api.companionName(nameDraft.value)
    data.companion = out
    showToast('已记住这个名字')
  } catch (e) { showToast(e.message) }
}
</script>

<template>
  <!-- 伙伴抽屉 -->
  <div v-if="open" class="mask" @click.self="open = false">
    <div class="companion-sheet enter">
      <div class="companion-big" :class="['stage-' + (companion.stage || 'egg'), companion.aura ? 'aura-' + companion.aura : '']">
        <img :src="companionImage" alt="伙伴" class="companion-img-big" />
      </div>
      <strong>{{ companionTitle }}</strong>
      <p v-if="companion.next_stage" class="dim">再 {{ Math.max(0, (companion.next_need || 0) - (companion.earned || 0)) }} 阳光到{{ companion.next_stage_name }}</p>
      <p v-else class="dim">开完花了，继续攒阳光也不会掉</p>
      <div class="next-bar companion-bar"><i :style="{ width: (companion.progress || 0) + '%' }"></i></div>
      <label class="fld companion-name"><span>给它起名</span>
        <input v-model="nameDraft" maxlength="8" placeholder="1 到 8 个字" @keyup.enter="saveName" />
      </label>
      <button type="button" class="do" @click="saveName">保存</button>
      <button v-if="spriteButton" type="button" class="ghost" @click="open = false; emit('open-sprites')">{{ spriteButton }}</button>
      <button type="button" class="ghost" @click="open = false">关闭</button>
    </div>
  </div>

  <!-- 进化庆祝 -->
  <div v-if="companionEvolve" class="celebrate companion-evolve" @click="closeCompanionEvolve">
    <div class="confetti">
      <span v-for="i in 18" :key="'e'+i" :style="confettiStyle(i)"></span>
    </div>
    <div class="celebrate-card companion-evolve-card">
      <div class="companion-big companion-evolve-figure" :class="'stage-' + (companionEvolve.stage || 'egg')">
        <img :src="companionEvolveImage" alt="伙伴成长了" class="companion-img-big" />
      </div>
      <div class="celebrate-title"><PartyPopper class="ico" :size="16" /> 长大了</div>
      <div class="celebrate-name">{{ companionEvolve.name ? companionEvolve.name + ' · ' : '' }}{{ companionEvolve.stage_name }}</div>
    </div>
  </div>

  <!-- 升级庆祝 -->
  <div v-if="celebrate" class="celebrate">
    <div class="confetti">
      <span v-for="i in 18" :key="'c'+i" :style="confettiStyle(i)"></span>
    </div>
    <div class="celebrate-card">
      <div class="celebrate-icon"><component :is="rankIcon(celebrate.icon)" class="ico" :size="40" /></div>
      <div class="celebrate-title"><PartyPopper class="ico" :size="16" /> 升级</div>
      <div class="celebrate-name"><component :is="rankIcon(celebrate.icon)" class="ico" :size="18" /> {{ celebrate.name }}</div>
    </div>
  </div>
</template>
