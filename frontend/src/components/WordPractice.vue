<script setup>
// 单词练习弹窗：看词/默写/重试/收阳光的完整练习流，含 TTS 朗读。
// 共享状态 wordToday 与卡片派生（wordDueCard 等）在 store.js；
// 用法：父组件 <WordPractice ref="wordRef" @collected="refresh" />，
// 卡片按钮调 wordRef.value.open(kind)；打开前的营业时间守卫由父级负责。
import { reactive, ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Volume2 } from '@lucide/vue'
import { api } from '../api.js'
import { wordToday, wordItems, wordLaneOf, showToast } from '../store.js'

const emit = defineEmits(['collected'])

const WORD_PEEK_MAX = 1
const wordDialog = reactive({
  open: false, itemIndex: 0, phase: 'look', input: '', busy: false,
  feedback: null, peekUntil: 0, peekN: {}, heard: {}, filter: 'new', sid: '',
})
const wordInputEl = ref(null)
let wordPeekTimer = null
let wordNextTimer = null

function wordLaneItems(kind) {
  const k = kind || wordDialog.filter
  if (k === 'all') return wordItems()
  return wordItems().filter(x => wordLaneOf(x) === k)
}
const wordRemaining = computed(() => wordItems().filter(x => x.state !== 'done').length)
const wordCurrent = computed(() => wordLaneItems()[wordDialog.itemIndex] || null)
const wordCfg = computed(() => wordToday.value.config || {})
const wordTtsOn = computed(() => wordCfg.value.tts !== false)
const wordOtherLane = computed(() => wordDialog.filter === 'due' ? 'new' : 'due')
function buildWordLaneOther(kind) {
  // 复用 store 的卡片派生（done 页展示另一条车道进度）
  const t = wordToday.value
  if (!t.enabled) return null
  const sess = t.session
  const counts = (sess && sess.counts) || {}
  const items = wordLaneItems(kind)
  let total = items.length
  if (!total && sess) total = Number(kind === 'due' ? counts.due : counts.new) || 0
  if (!total) return null
  const left = items.length ? items.filter(x => x.state !== 'done').length : total
  const finished = !!(t.finished || (sess && sess.state === 'completed') || (items.length && left === 0))
  return { kind, finished, left, total }
}
const wordOtherCard = computed(() => buildWordLaneOther(wordOtherLane.value))
const wordPos = computed(() => {
  const items = wordLaneItems()
  const total = items.length
  const done = items.filter(x => x.state === 'done').length
  const cur = !total ? 0 : (done === total ? total : done + 1)
  return { cur, total, done, pct: total ? Math.round(done / total * 100) : 0 }
})
const wordOverlayTitle = computed(() => {
  if (wordDialog.filter === 'due') return '今日复习'
  if (wordDialog.filter === 'new') return '今日新词'
  return '今日单词'
})
const wordSlotCells = computed(() => {
  const w = wordCurrent.value?.word || ''
  const letters = String(wordDialog.input || '').replace(/[^A-Za-z']/g, '')
  let li = 0
  return [...w].map(ch => {
    if (ch === ' ') return { kind: 'space', fill: '', cur: false }
    if (ch === '-') return { kind: 'hyphen', fill: '-', cur: false }
    const fill = letters[li] || ''
    const cur = li === letters.length
    li += 1
    return { kind: 'letter', fill, cur }
  })
})
function spellSubmitText() {
  const w = wordCurrent.value?.word || ''
  const letters = String(wordDialog.input || '').replace(/[^A-Za-z']/g, '')
  let li = 0
  let out = ''
  for (const ch of w) {
    if (ch === ' ' || ch === '-') out += ch
    else out += letters[li++] || ''
  }
  return out.trim().slice(0, 60)
}
function ipaText(w) { return (w && String(w.ipa || '').trim()) ? w.ipa : '暂无音标' }
function wordPeekLeft(id) {
  if (!id) return 0
  return Math.max(0, WORD_PEEK_MAX - (wordDialog.peekN[id] || 0))
}

// refresh 写入 store.wordToday 后，这里同步弹窗内部状态
watch(wordToday, (t) => {
  if (!t) return
  const sid = (t.session && t.session.id) || ''
  if (sid && sid !== wordDialog.sid) {
    wordDialog.sid = sid
    wordDialog.peekN = {}
    wordDialog.heard = {}
  }
  const items = wordLaneItems()
  const i = items.findIndex(x => x.state !== 'done')
  wordDialog.itemIndex = i < 0 ? 0 : i
  if (wordDialog.open) syncWordPhase()
})

// ---- TTS ----
let wordUtter = null
let wordVoices = []
function ttsReady() { return typeof speechSynthesis !== 'undefined' }
function loadWordVoices() {
  if (!ttsReady()) return []
  try { wordVoices = speechSynthesis.getVoices() || [] } catch { wordVoices = [] }
  return wordVoices
}
function pickWordVoice(lang) {
  const want = (lang || wordCfg.value.tts_lang || 'en-GB').toLowerCase()
  const list = loadWordVoices()
  const en = list.filter(v => String(v.lang || '').toLowerCase().startsWith('en'))
  if (!en.length) return null
  return en.find(v => String(v.lang || '').toLowerCase() === want)
    || en.find(v => String(v.lang || '').toLowerCase().startsWith(want.slice(0, 2)))
    || en[0]
}
function nativeTts() {
  try { return typeof SunshineTts !== 'undefined' && SunshineTts && typeof SunshineTts.speak === 'function' } catch { return false }
}
function stopWordSpeech() {
  wordUtter = null
  try { if (nativeTts()) SunshineTts.stop() } catch {}
  try { if (ttsReady()) speechSynthesis.cancel() } catch {}
}
function speakWord(word, lang) {
  const text = String(word || '').trim()
  if (!text) return false
  const useLang = lang || wordCfg.value.tts_lang || 'en-GB'
  try {
    if (nativeTts()) {
      SunshineTts.speak(text, useLang)
      return true
    }
  } catch {}
  if (!ttsReady()) return false
  try {
    speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    const voice = pickWordVoice(useLang)
    if (voice) {
      u.voice = voice
      u.lang = voice.lang || useLang
    } else {
      u.lang = useLang
    }
    u.rate = 0.85
    u.onerror = () => { if (wordUtter === u) wordUtter = null }
    u.onend = () => { if (wordUtter === u) wordUtter = null }
    wordUtter = u
    speechSynthesis.speak(u)
    return true
  } catch { return false }
}
function hearWord() {
  const w = wordCurrent.value
  if (!w) return
  if (speakWord(w.word)) return
  if (!ttsReady() && !nativeTts()) return showToast('这台设备暂时不能朗读，先看音标')
  loadWordVoices()
  setTimeout(() => {
    if (!speakWord(w.word)) showToast('这台设备暂时不能朗读，先看音标')
  }, 280)
}
function wordPhaseOf(item) {
  if (!item) return 'done'
  if (item.state === 'retry') return 'retry'
  if (item.state === 'spell') return 'spell'
  if (item.state === 'done') return 'done'
  return item.source === 'due' ? 'spell' : 'look'
}
function focusWordInput() {
  if (wordDialog.phase !== 'spell' && wordDialog.phase !== 'retry') return
  nextTick(() => wordInputEl.value && wordInputEl.value.focus())
}
function maybeAutoSpeak() {
  const it = wordCurrent.value
  const cfg = wordCfg.value
  if (wordDialog.phase !== 'look' || !it || !wordTtsOn.value || !cfg.tts_autoplay) return
  if (wordDialog.peekUntil) return
  if (wordDialog.heard[it.word_id]) return
  wordDialog.heard[it.word_id] = 1
  speakWord(it.word, cfg.tts_lang)
}
function syncWordPhase() {
  const items = wordLaneItems()
  const sess = wordToday.value.session
  if (!sess || !items.length || items.every(x => x.state === 'done') || sess.state === 'completed' || wordToday.value.finished) {
    wordDialog.phase = 'done'
    wordDialog.feedback = null
    return
  }
  if (wordDialog.peekUntil && Date.now() < wordDialog.peekUntil) {
    wordDialog.phase = 'look'
    return
  }
  const i = items.findIndex(x => x.state !== 'done')
  wordDialog.itemIndex = i < 0 ? 0 : i
  wordDialog.phase = wordPhaseOf(items[wordDialog.itemIndex])
  maybeAutoSpeak()
  focusWordInput()
}

// ---- 流程 ----
async function open(kind) {
  if (wordDialog.busy) return
  wordDialog.filter = kind === 'due' ? 'due' : 'new'
  wordDialog.busy = true
  try {
    let t = await api.wordsToday()
    if (t.enabled && !t.finished && !t.session) t = await api.wordsStart()
    wordToday.value = t
    if (!t.enabled) { showToast('单词练习还没开'); return }
    if (t.finished && !t.session) { showToast('这一单元的词都练过了'); return }
    if (!wordLaneItems().length) {
      showToast(kind === 'due' ? '今天没有到期复习' : '今天没有新词')
      return
    }
    wordDialog.input = ''
    wordDialog.feedback = null
    wordDialog.peekUntil = 0
    wordDialog.open = true
    syncWordPhase()
  } catch (e) { showToast(e.message) }
  finally { wordDialog.busy = false }
}
defineExpose({ open })
function closeWords() {
  wordDialog.open = false
  wordDialog.feedback = null
  wordDialog.peekUntil = 0
  clearTimeout(wordPeekTimer)
  clearTimeout(wordNextTimer)
  stopWordSpeech()
}
async function wordKnown() {
  const it = wordCurrent.value
  const sid = wordToday.value.session && wordToday.value.session.id
  if (!it || !sid || wordDialog.busy) return
  wordDialog.busy = true
  try {
    wordToday.value = await api.wordsStudy(sid, it.word_id, 'known')
    wordDialog.input = ''
    wordDialog.feedback = null
    wordDialog.phase = 'spell'
    focusWordInput()
  } catch (e) { showToast(e.message) }
  finally { wordDialog.busy = false }
}
async function wordAgain() {
  const it = wordCurrent.value
  const sid = wordToday.value.session && wordToday.value.session.id
  if (!it || !sid || wordDialog.busy) return
  wordDialog.busy = true
  try {
    wordToday.value = await api.wordsStudy(sid, it.word_id, 'again')
    wordDialog.input = ''
    wordDialog.feedback = null
    syncWordPhase()
  } catch (e) { showToast(e.message) }
  finally { wordDialog.busy = false }
}
function firstLetter(w) {
  const m = String(w || '').match(/[A-Za-z']/)
  return m ? m[0] : ''
}
function wordPeek() {
  const it = wordCurrent.value
  if (!it || it.source !== 'due' || wordDialog.busy) return
  if (wordDialog.phase !== 'spell') return
  if (wordPeekLeft(it.word_id) <= 0) { showToast('这题不能再看了，先写；写错了会看到正确答案'); return }
  wordDialog.peekN[it.word_id] = (wordDialog.peekN[it.word_id] || 0) + 1
  wordDialog.peekUntil = Date.now() + 2000
  wordDialog.phase = 'look'
  clearTimeout(wordPeekTimer)
  wordPeekTimer = setTimeout(() => {
    wordDialog.peekUntil = 0
    if (wordDialog.open) { wordDialog.phase = 'spell'; focusWordInput() }
  }, 2000)
}
function wordGoNext() {
  wordDialog.feedback = null
  wordDialog.input = ''
  wordDialog.busy = false
  syncWordPhase()
}
async function wordCheck() {
  const it = wordCurrent.value
  const sid = wordToday.value.session && wordToday.value.session.id
  if (!it || !sid || wordDialog.busy) return
  const text = spellSubmitText()
  if (!text) { showToast('先写一写'); return }
  const retry = wordDialog.phase === 'retry' || it.state === 'retry'
  wordDialog.busy = true
  try {
    const t = await api.wordsSpell(sid, {
      word_id: it.word_id, text, phase: retry ? 'retry' : 'spell', attempt_no: 1,
    })
    wordToday.value = t
    const right = t.result === 'right'
    wordDialog.feedback = { kind: right ? 'right' : 'wrong', typed: text }
    if (right) {
      clearTimeout(wordNextTimer)
      wordNextTimer = setTimeout(wordGoNext, 800)
      return
    }
    wordDialog.phase = 'retry'
    if (!retry) wordDialog.input = firstLetter(it.word)
  } catch (e) { showToast(e.message) }
  finally {
    if (!(wordDialog.feedback && wordDialog.feedback.kind === 'right')) wordDialog.busy = false
  }
}
async function wordCollect() {
  const sess = wordToday.value.session
  if (!sess || wordDialog.busy) return
  if (sess.state === 'completed') { closeWords(); return }
  wordDialog.busy = true
  try {
    wordToday.value = await api.wordsComplete(sess.id)
    wordDialog.phase = 'done'
    emit('collected')
  } catch (e) { showToast(e.message) }
  finally { wordDialog.busy = false }
}

onMounted(() => {
  if (ttsReady()) {
    loadWordVoices()
    try { speechSynthesis.addEventListener('voiceschanged', loadWordVoices) } catch {}
  }
})
onBeforeUnmount(() => {
  clearTimeout(wordPeekTimer)
  clearTimeout(wordNextTimer)
  try { if (ttsReady()) speechSynthesis.removeEventListener('voiceschanged', loadWordVoices) } catch {}
  stopWordSpeech()
  try { if (ttsReady()) speechSynthesis.cancel() } catch {}
})
</script>

<template>
  <div v-if="wordDialog.open" class="mask" @click.self="closeWords">
    <div class="shop-modal word-modal">
      <div class="word-top">
        <strong>{{ wordOverlayTitle }}</strong>
        <span>{{ wordPos.cur }} / {{ wordPos.total }}</span>
      </div>
      <div class="word-bar"><i :style="{ width: wordPos.pct + '%' }"></i></div>
      <div v-if="wordCurrent && wordDialog.phase !== 'done'" class="word-tag">{{ wordCurrent.source === 'due' ? '复习' : '新学' }}</div>

      <div v-if="wordDialog.phase === 'look' && wordCurrent" class="word-pane">
        <div class="word-en">{{ wordCurrent.word }}</div>
        <div class="word-ipa">{{ ipaText(wordCurrent) }}</div>
        <div class="word-cn">{{ wordCurrent.cn }}</div>
        <button v-if="wordTtsOn" type="button" class="word-hear" :disabled="wordDialog.busy" aria-label="听读音" @click="hearWord">
          <Volume2 :size="18" /> 听读音
        </button>
        <p v-if="wordCurrent.example_en" class="word-ex">{{ wordCurrent.example_en }}</p>
        <div v-if="!wordDialog.peekUntil" class="word-actions">
          <button type="button" class="word-sec" :disabled="wordDialog.busy" @click="wordAgain">再看一次</button>
          <button type="button" class="do word-main" :disabled="wordDialog.busy" @click="wordKnown">去默写</button>
        </div>
      </div>

      <div v-else-if="(wordDialog.phase === 'spell' || wordDialog.phase === 'retry') && wordCurrent" class="word-pane">
        <p v-if="wordDialog.phase === 'retry'" class="word-retry-note">再写一次，不计分</p>
        <div class="word-cn big">{{ wordCurrent.cn }}</div>
        <div class="word-slots" :class="wordDialog.feedback && wordDialog.feedback.kind" @click="focusWordInput">
          <i v-for="(s, i) in wordSlotCells" :key="i" :class="[s.kind, { cur: s.cur && !wordDialog.feedback }]">{{ s.fill }}</i>
          <input v-if="!wordDialog.feedback" ref="wordInputEl" v-model="wordDialog.input" class="word-input-ghost"
            type="text" inputmode="text" autocomplete="off" autocapitalize="none" spellcheck="false"
            enterkeyhint="done" :disabled="wordDialog.busy" maxlength="60" aria-label="默写单词"
            @keyup.enter="wordCheck" />
        </div>
        <div v-if="wordDialog.feedback && wordDialog.feedback.kind === 'right'" class="word-fb ok">
          <div class="word-en fade">{{ wordCurrent.word }}</div>
          <div class="word-ipa fade">{{ ipaText(wordCurrent) }}</div>
        </div>
        <template v-else-if="wordDialog.feedback && wordDialog.feedback.kind === 'wrong'">
          <p class="word-wrong">你写了 {{ wordDialog.feedback.typed }} · 正确 {{ wordCurrent.word }}</p>
          <div class="word-ipa">{{ ipaText(wordCurrent) }}</div>
          <button v-if="wordTtsOn" type="button" class="word-hear" aria-label="听读音" @click="hearWord">
            <Volume2 :size="18" /> 听读音
          </button>
          <button v-if="wordCurrent.state === 'done'" type="button" class="do word-main" @click="wordGoNext">下一题</button>
          <button v-else type="button" class="do word-main" @click="wordDialog.feedback = null; focusWordInput()">再写一次</button>
        </template>
        <template v-else>
          <button type="button" class="do word-main" :disabled="wordDialog.busy" @click="wordCheck">检查</button>
          <button v-if="wordCurrent.source === 'due' && wordDialog.phase === 'spell' && wordPeekLeft(wordCurrent.word_id) > 0" type="button" class="word-sec" :disabled="wordDialog.busy" @click="wordPeek">忘了，看一眼</button>
        </template>
      </div>

      <div v-else-if="wordDialog.phase === 'done'" class="word-pane word-done">
        <h3>{{ wordDialog.filter === 'due' ? '复习完成' : '新词完成' }}</h3>
        <p v-if="wordOtherCard && !wordOtherCard.finished">{{ wordDialog.filter === 'due' ? '新词还没练' : '复习还没练' }} · {{ wordOtherCard.left }} 个</p>
        <p v-else>复习 {{ (wordToday.session && wordToday.session.counts && wordToday.session.counts.due) || 0 }} · 新学 {{ (wordToday.session && wordToday.session.counts && wordToday.session.counts.new) || 0 }}</p>
        <p v-if="!(wordOtherCard && !wordOtherCard.finished)">首轮正确 {{ (wordToday.session && wordToday.session.counts && wordToday.session.counts.correct_first_try) || 0 }} / {{ wordItems().length }}</p>
        <p v-if="wordToday.session && wordToday.session.reward" class="word-sun">+{{ wordToday.session.reward.base }} 阳光</p>
        <p v-if="wordToday.session && wordToday.session.reward && wordToday.session.reward.perfect" class="word-sun">+{{ wordToday.session.reward.perfect }} 全对</p>
        <button v-if="wordOtherCard && !wordOtherCard.finished" type="button" class="do big" :disabled="wordDialog.busy" @click="open(wordOtherLane)">
          去练{{ wordOtherLane === 'due' ? '复习' : '新词' }}
        </button>
        <button v-else type="button" class="do big" :disabled="wordDialog.busy" @click="wordCollect">
          {{ wordToday.session && wordToday.session.state === 'completed' ? '关闭' : '收下阳光' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.word-modal { max-width: 420px; text-align: center; }
.word-top { display: flex; justify-content: space-between; align-items: center; font-weight: 800; }
.word-bar { height: 6px; background: var(--surface-2); border-radius: 99px; margin: 8px 0 10px; overflow: hidden; }
.word-bar i { display: block; height: 100%; background: var(--accent); }
.word-tag { display: inline-block; font-size: 12px; font-weight: 800; color: var(--accent-ink); background: var(--warm); border-radius: var(--radius-pill); padding: 2px 10px; margin-bottom: 8px; }
.word-en { font-size: 34px; font-weight: 800; line-height: 1.2; word-break: break-word; }
.word-ipa { margin-top: 6px; font-size: 16px; color: var(--ink-2); font-family: ui-serif, "Times New Roman", serif; }
.word-cn { margin-top: 8px; font-size: 18px; font-weight: 700; }
.word-cn.big { font-size: 28px; margin: 8px 0 14px; }
.word-ex { margin: 10px 0 0; color: var(--ink-3); font-size: 13px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.word-hear, .word-sec, .word-main {
  min-height: 44px; min-width: 44px; margin-top: 12px; border: none; border-radius: var(--radius-lg);
  font-weight: 800; cursor: pointer; font-family: inherit; padding: 0 16px;
}
.word-hear { background: var(--surface-2); color: var(--ink); display: inline-flex; align-items: center; gap: 6px; }
.word-sec { background: none; color: var(--ink-3); }
.word-actions { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }
.word-actions .word-sec, .word-actions .word-main { flex: 1; margin-top: 0; }
.word-slots { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; margin: 8px 0 14px; min-height: 40px; position: relative; cursor: text; }
.word-slots i { width: 22px; height: 32px; border-bottom: 2px solid var(--ink-3); display: inline-flex; align-items: flex-end; justify-content: center; font-weight: 800; font-size: 20px; line-height: 1; }
.word-slots i.space { width: 12px; border: none; }
.word-slots i.hyphen { border: none; align-items: center; }
.word-slots i.cur { border-color: var(--accent); }
.word-slots.right i { border-color: var(--ok); color: var(--ok); }
.word-slots.wrong i { border-color: var(--accent); color: var(--accent-ink); }
.word-input-ghost {
  position: absolute; inset: 0; opacity: 0; border: 0; padding: 0; margin: 0;
  width: 100%; height: 100%; font-size: 16px; background: transparent; caret-color: transparent;
}
.word-retry-note { margin: 0 0 6px; font-size: 13px; color: var(--ink-3); }
.word-wrong { margin: 8px 0; color: var(--accent-ink); font-weight: 700; }
.word-fb.ok .fade { animation: wordfade .8s ease; }
@keyframes wordfade { from { opacity: 0; } to { opacity: 1; } }
.word-done h3 { margin: 8px 0 10px; }
.word-sun { font-size: 20px; font-weight: 800; color: var(--accent); }
</style>
