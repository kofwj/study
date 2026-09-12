<script setup>
// 时间胶囊弹窗：封一封信给以后的自己 / 到期拆信。
// 用法：父组件 <CapsuleBox ref="capsuleRef" />，调 capsuleRef.value.open()；
// open 会顺带把基地场景切到树屋（spriteScene 在 store）。
import { reactive, ref, computed } from 'vue'
import { api } from '../api.js'
import { capsule, capsuleOpen, capsuleOpenedView, spriteScene, applyCapsule, showToast } from '../store.js'

const capsuleBusy = ref(false)
const CAPSULE_Q_FALLBACK = [
  { key: 'q_good', label: '现在最拿手的一件事', placeholder: '比如：口算很快', examples: ['口算很快', '跳绳能连跳很多下', '英语单词记得住'] },
  { key: 'q_wish', label: '还想变好的一件事', placeholder: '比如：把字写得更工整', examples: ['把字写得更工整', '英语听写少错几个', '早睡早起不磨蹭'] },
  { key: 'q_line', label: '想对以后的自己说的一句', placeholder: '比如：别忘了现在有多努力', examples: ['别忘了现在有多努力', '以后的我要对自己说加油', '希望你还喜欢运动'] },
]
const capsuleForm = reactive({ when_kind: 'week', open_on: '', q_good: '', q_wish: '', q_line: '' })
const capsuleQuestions = computed(() => (capsule.value.questions && capsule.value.questions.length) ? capsule.value.questions : CAPSULE_Q_FALLBACK)

function resetCapsuleForm() {
  const opts = capsule.value.options || []
  capsuleForm.when_kind = (opts[0] && opts[0].kind) || 'week'
  capsuleForm.open_on = capsule.value.min_open_on || ''
  capsuleForm.q_good = ''
  capsuleForm.q_wish = ''
  capsuleForm.q_line = ''
}
function pickCapsuleWhen(kind) {
  capsuleForm.when_kind = kind
  if (kind === 'custom' && !capsuleForm.open_on) capsuleForm.open_on = capsule.value.min_open_on || ''
}
function fillCapsuleHint(key, text) {
  capsuleForm[key] = text
}
function capsuleDateText(iso) {
  if (!iso) return ''
  const [y, m, d] = String(iso).split('-')
  return `${Number(y)}年${Number(m)}月${Number(d)}日`
}
function snapLine(s) {
  if (!s) return '还没记下'
  const who = s.companion_name || s.companion_stage_name || '阳光芽'
  return `${s.level || '—'} · 连打 ${s.streak || 0} 天 · ${who}`
}
function closeCapsuleBox() {
  capsuleOpen.value = false
  if (capsuleOpenedView.value) capsuleOpenedView.value = false
}
function open() {
  if (capsule.value.state === 'empty' && !capsuleOpenedView.value) resetCapsuleForm()
  capsuleOpen.value = true
  spriteScene.value = 'leaf'
}
defineExpose({ open })
function startNextCapsule() {
  capsuleOpenedView.value = false
  resetCapsuleForm()
}
async function submitCapsule() {
  if (capsuleBusy.value) return
  if (capsuleForm.when_kind === 'custom' && !capsuleForm.open_on) {
    showToast('选一个开封的日子')
    return
  }
  capsuleBusy.value = true
  try {
    applyCapsule(await api.capsuleSeal({
      when_kind: capsuleForm.when_kind,
      open_on: capsuleForm.when_kind === 'custom' ? capsuleForm.open_on : '',
      q_good: capsuleForm.q_good,
      q_wish: capsuleForm.q_wish,
      q_line: capsuleForm.q_line,
    }))
    capsuleOpenedView.value = false
    capsuleOpen.value = false
    showToast('封进箱子了，到那天再拆')
  } catch (e) { showToast(e.message) }
  finally { capsuleBusy.value = false }
}
async function openCapsuleLetter() {
  if (capsuleBusy.value) return
  capsuleBusy.value = true
  try {
    const opened = await api.capsuleOpen()
    applyCapsule(await api.capsule())
    if (opened) {
      capsule.value.capsule = { ...(capsule.value.capsule || {}), ...opened, state: 'opened' }
      if (opened.now) capsule.value.now = opened.now
    }
    capsuleOpenedView.value = true
    showToast('拆开了')
  } catch (e) { showToast(e.message) }
  finally { capsuleBusy.value = false }
}
</script>

<template>
  <div v-if="capsuleOpen" class="mask" @click.self="closeCapsuleBox">
    <div class="shop-modal enter">
      <h3>给以后的自己</h3>
      <template v-if="capsule.state === 'sealed'">
        <p class="cap-wait">给 {{ capsuleDateText(capsule.capsule && capsule.capsule.open_on) || '以后' }} 的自己</p>
        <p class="dim-s">{{ capsule.wait }}。还不能看里面写了什么。</p>
        <button class="ghost" @click="closeCapsuleBox">关上</button>
      </template>
      <template v-else-if="capsule.state === 'ready'">
        <p>箱子可以拆了。</p>
        <button class="do big" :disabled="capsuleBusy" @click="openCapsuleLetter">拆开</button>
        <button class="ghost" @click="closeCapsuleBox">等一会儿</button>
      </template>
      <template v-else-if="capsuleOpenedView && capsule.capsule && capsule.capsule.q_line">
        <div class="cap-snap">
          <div><small>那时的你</small><strong>{{ snapLine(capsule.capsule.snapshot) }}</strong></div>
          <div><small>现在的你</small><strong>{{ snapLine(capsule.now) }}</strong></div>
        </div>
        <p class="cap-q"><small>最拿手</small>{{ capsule.capsule.q_good }}</p>
        <p class="cap-q"><small>还想变好</small>{{ capsule.capsule.q_wish }}</p>
        <p class="cap-q"><small>给以后的自己</small>{{ capsule.capsule.q_line }}</p>
        <button class="do big" @click="startNextCapsule">写下一封</button>
        <button class="ghost" @click="closeCapsuleBox">关上</button>
      </template>
       <template v-else>
         <p class="dim-s cap-lead">什么时候拆开？也可以自己选一天。</p>
         <div class="cap-opts">
           <button v-for="o in capsule.options" :key="o.kind" type="button"
             :class="['cap-opt', { on: capsuleForm.when_kind === o.kind }]"
             @click="pickCapsuleWhen(o.kind)">
             <strong>{{ o.label }}</strong>
             <small>{{ o.hint }}</small>
           </button>
         </div>
         <label v-if="capsuleForm.when_kind === 'custom'" class="fld">
           <span>开封那天</span>
           <input type="date" v-model="capsuleForm.open_on" :min="capsule.min_open_on" :max="capsule.max_open_on" />
         </label>
         <label v-for="q in capsuleQuestions" :key="q.key" class="fld">
           <span>{{ q.label }}</span>
           <input v-model="capsuleForm[q.key]" maxlength="40" :placeholder="q.placeholder" />
           <div class="cap-hints">
             <button v-for="ex in q.examples" :key="ex" type="button" class="cap-hint" @click="fillCapsuleHint(q.key, ex)">{{ ex }}</button>
           </div>
         </label>
         <button class="do big" :disabled="capsuleBusy" @click="submitCapsule">封进箱子</button>
         <button class="ghost" @click="closeCapsuleBox">取消</button>
       </template>
    </div>
  </div>
</template>
