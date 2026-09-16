/* ============================================================
   家长工作台 · 英语单词页的状态与请求（模块级单例）
   ------------------------------------------------------------
   为什么放在模块作用域，而不是子组件内部：
   侧栏切页是 v-if，子组件会被卸载；如果单词数据放在子组件里，
   每次切回「英语单词」都要重拉 4 个接口，C2「已经拉过的不重拉」就回退了。
   放模块作用域后：数据在内存里活着，Admin.vue 的包调度（loadPack/loaded）
   语义完全不变，AdminWords.vue 只做视图。

   由 Admin.vue 在 setup 里注入上下文：
     initAdminWords({ getKid, getTerms, toast })
   ============================================================ */
import { reactive, ref, computed } from 'vue'
import { api } from './api.js'

let ctx = {
  getKid: () => '',
  getTerms: () => [],
  toast: () => {},
}
export function initAdminWords(next) {
  ctx = { ...ctx, ...next }
}

/* —— 配置 / 词书 —— */
const wordCfg = reactive({
  enabled: false, new_per_day: 5, max_due: 10, game_size: 20,
  daily_goal: 10, match_size: 5, match_blocks: 3,
  unlock_by_cursor: true, current_book: '', review_mode: 'current', review_books: [],
  tts: true, tts_autoplay: false, tts_lang: 'en-GB',
})
const wordBooks = ref([])
const wordBookGroups = computed(() => {
  const groups = {}
  for (const b of wordBooks.value.filter(x => x.is_system)) {
    const key = b.term_id || 'other'
    if (!groups[key]) groups[key] = { id: key, label: ctx.getTerms().find(t => t.id === key)?.label || key, books: [] }
    groups[key].books.push(b)
  }
  return Object.values(groups)
})
const selectedReviewBookCount = computed(() => (wordCfg.review_books || []).length)
function isReviewBook(id) { return (wordCfg.review_books || []).includes(id) }
async function saveWordReviewMode(mode) {
  let selected = [...(wordCfg.review_books || [])]
  if (mode === 'scope' && wordCfg.current_book) {
    const current = wordBooks.value.find(b => b.id === wordCfg.current_book)
    if (current?.is_system && !selected.includes(current.id)) selected.push(current.id)
  }
  await saveWordNow({ review_mode: mode, review_books: selected })
}
function wordScopePresetIds(preset) {
  return wordBooks.value
    .filter(b => b.is_system && preset.terms.includes(b.term_id))
    .sort((a, b) => (Number(a.sort) || 0) - (Number(b.sort) || 0) || String(a.id).localeCompare(String(b.id)))
    .map(b => b.id)
}
export const WORD_SCOPE_PRESETS = [
  { id: 'g3', label: '三年级基础', terms: ['g3s1', 'g3x2'] },
  { id: 'g4', label: '四年级基础', terms: ['g4s1', 'g4x2'] },
  { id: 'g3g4', label: '三、四年级补基础', terms: ['g3s1', 'g3x2', 'g4s1', 'g4x2'] },
]
const matchedWordScopePreset = computed(() => {
  if (wordCfg.review_mode !== 'scope') return ''
  const selected = new Set(wordCfg.review_books || [])
  if (!selected.size) return ''
  for (const p of WORD_SCOPE_PRESETS) {
    const ids = wordScopePresetIds(p)
    if (!ids.length || ids.length !== selected.size) continue
    if (ids.every(id => selected.has(id))) return p.id
  }
  return ''
})
async function applyWordScopePreset(id) {
  if (!id) return
  const preset = WORD_SCOPE_PRESETS.find(x => x.id === id)
  if (!preset) return
  const ids = wordScopePresetIds(preset)
  await saveWordNow({ review_mode: 'scope', review_books: ids, current_book: ids[0] || '' })
}
async function toggleReviewBook(book) {
  const selected = new Set(wordCfg.review_books || [])
  if (selected.has(book.id)) {
    selected.delete(book.id)
    if (wordCfg.current_book === book.id) {
      await saveWordNow({ review_books: [...selected], current_book: '' })
      return
    }
  } else selected.add(book.id)
  await saveWordNow({ review_books: [...selected] })
}

/* —— 今日 / 错词 / 统计 / 看词 / 导入 —— */
const wordToday = ref({ enabled: false, finished: true, backlog_due: 0, session: null })
const wordProblems = ref([])
const wordStats = ref({ days: [], completed_sessions: 0, first_try_rate: null })
const wordNewBook = ref('')
const wordImport = reactive({ book_id: '', text: '', result: null })
const wordOpenBook = ref(null)
const wordBusy = ref(false)
const wordOverview = computed(() => {
  const s = wordToday.value.session
  const counts = (s && s.counts) || { due: 0, new: 0, answered: 0, correct_first_try: 0 }
  const total = ((s && s.items) || []).length
  const left = ((s && s.items) || []).filter(x => x.state !== 'done').length
  return {
    newn: counts.new || 0,
    due: counts.due || 0,
    correct: counts.correct_first_try || 0,
    total,
    left: wordToday.value.finished ? 0 : (s ? left : (wordToday.value.enabled ? '—' : 0)),
    backlog: wordToday.value.backlog_due || 0,
    finished: !!wordToday.value.finished,
  }
})

/* 切孩子：看词面板和半截导入丢掉（和 B3「切孩子都从收起开始」一致） */
let lastKid = ''
function resetTransient(kid) {
  if (kid === lastKid) return
  lastKid = kid
  wordOpenBook.value = null
  wordImport.book_id = ''
  wordImport.text = ''
  wordImport.result = null
}

export async function loadWords() {
  const kid = ctx.getKid()
  if (!kid) return
  resetTransient(kid)
  try {
    const [cfg, today, problems, stats] = await Promise.all([
      api.admin.wordConfig(),
      api.wordsToday().catch(() => null),
      api.admin.problemWords().catch(() => []),
      api.admin.wordStats().catch(() => ({ days: [], completed_sessions: 0, first_try_rate: null })),
    ])
    if (ctx.getKid() !== kid) return
    Object.assign(wordCfg, {
      enabled: !!cfg.enabled,
      new_per_day: cfg.new_per_day,
      max_due: cfg.max_due,
      game_size: cfg.game_size,
      unlock_by_cursor: cfg.unlock_by_cursor !== false,
      daily_goal: cfg.daily_goal,
      match_size: cfg.match_size,
      match_blocks: cfg.match_blocks,
      current_book: cfg.current_book || '',
      review_mode: cfg.review_mode === 'scope' ? 'scope' : 'current',
      review_books: Array.isArray(cfg.review_books) ? cfg.review_books : [],
      tts: cfg.tts !== false,
      tts_autoplay: !!cfg.tts_autoplay,
      tts_lang: cfg.tts_lang === 'en-US' ? 'en-US' : 'en-GB',
    })
    wordBooks.value = cfg.books || []
    wordToday.value = today || { enabled: false, finished: true, backlog_due: 0, session: null }
    wordProblems.value = problems || []
    wordStats.value = stats || { days: [], completed_sessions: 0, first_try_rate: null }
  } catch (e) { ctx.toast(e.message) }
}
async function saveWordNow(patch) {
  try {
    const cfg = await api.admin.setWordConfig(patch)
    Object.assign(wordCfg, {
      enabled: !!cfg.enabled,
      current_book: cfg.current_book || '',
      review_mode: cfg.review_mode === 'scope' ? 'scope' : 'current',
      review_books: Array.isArray(cfg.review_books) ? cfg.review_books : [],
      tts: cfg.tts !== false,
      tts_autoplay: !!cfg.tts_autoplay,
      tts_lang: cfg.tts_lang === 'en-US' ? 'en-US' : 'en-GB',
      unlock_by_cursor: cfg.unlock_by_cursor !== false,
      daily_goal: cfg.daily_goal,
      match_size: cfg.match_size,
      match_blocks: cfg.match_blocks,
    })
    wordBooks.value = cfg.books || []
    await loadWords()
  } catch (e) { ctx.toast(e.message); await loadWords() }
}
async function saveWordRhythm() {
  try {
    await api.admin.setWordConfig({
      new_per_day: wordCfg.new_per_day,
      max_due: wordCfg.max_due,
      game_size: wordCfg.game_size,
      daily_goal: wordCfg.daily_goal,
      match_size: wordCfg.match_size,
      match_blocks: wordCfg.match_blocks,
    })
    ctx.toast('已保存：新词/到期明天生效，一局词数、连一连、每日目标下一局生效')
  } catch (e) { ctx.toast(e.message) }
}
async function addWordBook() {
  const name = wordNewBook.value.trim()
  if (!name) return ctx.toast('填词书名字')
  try {
    await api.admin.createWordBook({ name })
    wordNewBook.value = ''
    ctx.toast('已建家庭词书')
    await loadWords()
  } catch (e) { ctx.toast(e.message) }
}
async function saveWordBook(b) {
  try {
    await api.admin.updateWordBook(b.id, { name: b.name })
    ctx.toast('已改名')
    await loadWords()
  } catch (e) { ctx.toast(e.message) }
}
async function delWordBook(b) {
  if (!confirm('关掉这本家庭词书？')) return
  try {
    await api.admin.delWordBook(b.id)
    if (wordImport.book_id === b.id) wordImport.book_id = ''
    ctx.toast('已处理')
    await loadWords()
  } catch (e) { ctx.toast(e.message) }
}
async function importWordBook() {
  if (!wordImport.book_id) return ctx.toast('先选一本家庭词书')
  if (!wordImport.text.trim()) return ctx.toast('粘贴单词')
  wordBusy.value = true
  try {
    wordImport.result = await api.admin.importWords(wordImport.book_id, wordImport.text)
    ctx.toast('导入 ' + wordImport.result.ok + ' 个')
    await loadWords()
  } catch (e) { ctx.toast(e.message) }
  finally { wordBusy.value = false }
}
async function openWordBook(id) {
  try {
    wordOpenBook.value = await api.admin.wordBook(id)
  } catch (e) { ctx.toast(e.message) }
}
async function focusWord(id) {
  try {
    await api.admin.focusWord(id)
    ctx.toast('明天会练到')
    await loadWords()
  } catch (e) { ctx.toast(e.message) }
}

/* AdminWords.vue 取这一份 */
export function useAdminWords() {
  return {
    wordCfg, wordBooks, wordBookGroups, selectedReviewBookCount, wordOverview,
    wordToday, wordProblems, wordStats, wordOpenBook, wordNewBook,
    wordImport, wordBusy, WORD_SCOPE_PRESETS, matchedWordScopePreset,
    isReviewBook, loadWords, saveWordNow, saveWordRhythm, saveWordReviewMode,
    applyWordScopePreset, toggleReviewBook, addWordBook, saveWordBook,
    delWordBook, importWordBook, openWordBook, focusWord,
  }
}