<script setup>
// 家长工作台 · 英语单词页（纯视图）
// 数据与请求在 ../adminWords.js（模块级单例），这样侧栏来回切换不会重拉
import { ref, watch } from 'vue'
import { useAdminWords } from '../adminWords.js'

const props = defineProps({
  kid: { type: String, default: '' },
  kidName: { type: String, default: '' },
})

// 折叠态属于这一页：切孩子回到收起（和刷新一致）
const wordWeekOpen = ref(false)
const wordImportOpen = ref(false)
watch(() => props.kid, () => {
  wordWeekOpen.value = false
  wordImportOpen.value = false
})

const {
  wordCfg, wordBooks, wordBookGroups, selectedReviewBookCount, wordOverview,
  wordProblems, wordStats, wordOpenBook, wordNewBook, wordImport, wordBusy,
  WORD_SCOPE_PRESETS, matchedWordScopePreset, isReviewBook,
  saveWordNow, saveWordRhythm, saveWordReviewMode, applyWordScopePreset,
  toggleReviewBook, addWordBook, saveWordBook, delWordBook, importWordBook,
  openWordBook, focusWord,
} = useAdminWords()
</script>

<template>
    <section class="a-card enter">
      <h3>英语单词</h3>
      <p class="dim">给 {{ kidName || '当前孩子' }} 用。朗读马上生效；每天几个词、给多少阳光，明天新的一组才按这个来。</p>
      <h4 class="w-h">今天</h4>
      <div class="w-summary word-ov">
        <div class="w-box"><span>新词</span><b>{{ wordOverview.newn }}</b></div>
        <div class="w-box"><span>复习</span><b>{{ wordOverview.due }}</b></div>
        <div class="w-box"><span>首轮对</span><b>{{ wordOverview.correct }}/{{ wordOverview.total || 0 }}</b></div>
        <div class="w-box"><span>还没写完</span><b>{{ wordOverview.left }}</b></div>
        <div class="w-box"><span>积压到期</span><b>{{ wordOverview.backlog }}</b></div>
        <div class="w-box"><span>今天写了</span><b>{{ (wordStats.today && wordStats.today.wrote) || 0 }}<template v-if="wordStats.today && wordStats.today.goal">/{{ wordStats.today.goal }}</template></b></div>
        <div class="w-box"><span>最好一轮</span><b>{{ (wordStats.today && wordStats.today.best_score) ? wordStats.today.best_score + ' 分' : '—' }}</b></div>
        <div class="w-box"><span>今天阳光</span><b>{{ (wordStats.today && wordStats.today.sunshine) || 0 }}/{{ (wordStats.today && wordStats.today.sunshine_limit) || 10 }}</b></div>
      </div>
      <p v-if="wordStats.today_sentence" class="dim">{{ wordStats.today_sentence }}</p>
      <p v-if="wordStats.week_sentence" class="dim">{{ wordStats.week_sentence }}</p>
      <p v-if="wordStats.today_source" class="dim">{{ wordStats.today_source }}</p>
      <h4 class="w-h">高频错词</h4>
      <p v-if="!wordProblems.length" class="dim">还没有错两次以上的词。</p>
      <div v-for="w in wordProblems" :key="w.word_id" class="word-row">
        <div>
          <b>{{ w.word }}</b>
          <span>{{ w.cn }} · 错 {{ w.wrong_count }} 次 · {{ w.book_name }}<template v-if="w.unit_id"> · {{ w.unit_id }}</template></span>
          <em>{{ [w.last_seen_at ? ('最近 ' + String(w.last_seen_at).slice(0, 10)) : '', w.due_at ? ('下次 ' + w.due_at) : ''].filter(Boolean).join(' · ') }}</em>
        </div>
        <button class="ok" @click="focusWord(w.word_id)">明天重点练</button>
      </div>
      <button type="button" class="ghost-s rules-toggle" @click="wordWeekOpen = !wordWeekOpen">{{ wordWeekOpen ? '收起近 7 日' : '近 7 日' }}</button>
      <template v-if="wordWeekOpen">
        <p class="dim">完成 {{ wordStats.completed_sessions || 0 }} 次<template v-if="wordStats.first_try_rate != null"> · 首轮正确率 {{ wordStats.first_try_rate }}%</template></p>
        <div class="w-chart word-week">
          <div v-for="d in wordStats.days || []" :key="d.date" class="w-bar-col">
            <div class="w-bar" :class="{ down: !d.completed }" :style="{ height: (d.completed ? Math.max(18, d.rate == null ? 40 : d.rate) : 6) + '%' }"><i v-if="d.rate != null">{{ d.rate }}%</i></div>
            <span>{{ d.label }}</span>
          </div>
        </div>
      </template>
      <h4 class="w-h">怎么练</h4>
      <div class="lock-row mt14">
        <span class="badge">单词练习</span>
        <span class="grow">孩子端显示今日单词</span>
        <button type="button" :class="['toggle', { on: wordCfg.enabled }]" @click="saveWordNow({ enabled: !wordCfg.enabled })">{{ wordCfg.enabled ? '开' : '关' }}</button>
      </div>
      <div class="frm-row mt14">
        <label class="fld grow"><span>复习范围</span>
          <select :value="wordCfg.review_mode" @change="saveWordReviewMode($event.target.value)">
            <option value="current">跟随当前词书</option>
            <option value="scope">自定义范围（补基础）</option>
          </select>
        </label>
        <label v-if="wordCfg.review_mode === 'scope'" class="fld grow mt8"><span>快捷方案</span>
          <select :value="matchedWordScopePreset" @change="applyWordScopePreset($event.target.value)">
            <option v-if="!matchedWordScopePreset" value="" disabled>选择一个复习方案</option>
            <option v-for="p in WORD_SCOPE_PRESETS" :key="p.id" :value="p.id">{{ p.label }}</option>
          </select>
        </label>
        <span class="dim review-scope-count">{{ wordCfg.review_mode === 'scope' ? `已选 ${selectedReviewBookCount} 本系统词书` : '当前模式只练当前词书；到期复习保持旧行为' }}</span>
      </div>
      <template v-if="wordCfg.review_mode === 'current'">
        <div class="frm-row">
          <label class="fld grow"><span>当前新词词书</span>
            <select :value="wordCfg.current_book" @change="saveWordNow({ current_book: $event.target.value })">
              <option value="">还没选</option>
              <option v-for="b in wordBooks" :key="b.id" :value="b.id" :disabled="b.is_system && !b.selectable">
                {{ b.name }}{{ b.is_system ? ' · 系统' : ' · 家庭' }}{{ b.is_system && !b.selectable ? '（先设英语已学到）' : '' }}
              </option>
            </select>
          </label>
        </div>
      </template>
      <template v-else>
        <div class="scope-books">
          <div v-for="group in wordBookGroups" :key="group.id" class="scope-group">
            <strong>{{ group.label }}</strong>
            <label v-for="b in group.books" :key="b.id" class="scope-book-check">
              <input type="checkbox" :checked="isReviewBook(b.id)" @change="toggleReviewBook(b)" />
              <span>{{ b.name }}</span>
            </label>
          </div>
        </div>
        <label class="fld grow mt8"><span>新词起始/当前书（可选）</span>
          <select :value="wordCfg.current_book" @change="saveWordNow({ current_book: $event.target.value })">
            <option value="">从范围首本开始</option>
            <option v-for="b in wordBooks.filter(x => isReviewBook(x.id))" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </label>
        <p class="dim">自定义范围不受英语「已学到」游标限制；新词会从当前书及之后依次进入，已学过的词自动跳过。</p>
      </template>
      <div class="frm-row">
        <label class="fld w64"><span>每天新词</span><input v-model.number="wordCfg.new_per_day" type="number" min="1" max="10" /></label>
        <label class="fld w64"><span>到期上限</span><input v-model.number="wordCfg.max_due" type="number" min="5" max="15" /></label>
        <label class="fld w64"><span>一局词数</span><input v-model.number="wordCfg.game_size" type="number" min="10" max="40" /></label>
        <label class="fld w64"><span>每日目标</span><input v-model.number="wordCfg.daily_goal" type="number" min="0" max="40" /></label>
        <label class="fld w64"><span>连线每块</span><input v-model.number="wordCfg.match_size" type="number" min="3" max="6" /></label>
        <label class="fld w64"><span>连线块数</span><input v-model.number="wordCfg.match_blocks" type="number" min="0" max="3" /></label>
        <button class="ok" @click="saveWordRhythm">保存节奏</button>
      </div>
      <p class="dim">每日目标：今天写够几个词点亮目标环，<b>0 = 不显示</b>；连线每块 3–6 个词（默认 5），
        连线块数 <b>0 = 不玩「连一连」</b>（只认 + 写）。这三项下一局生效。</p>
      <div v-if="wordCfg.review_mode === 'current'" class="lock-row mt14">
        <span class="badge">词书锁</span>
        <span class="grow">系统词书跟着英语「已学到」</span>
        <button type="button" :class="['toggle', { on: wordCfg.unlock_by_cursor }]" @click="saveWordNow({ unlock_by_cursor: !wordCfg.unlock_by_cursor })">{{ wordCfg.unlock_by_cursor ? '开' : '关' }}</button>
      </div>
      <div class="lock-row">
        <span class="badge">朗读</span>
        <span class="grow">看词页听读音</span>
        <button type="button" :class="['toggle', { on: wordCfg.tts }]" @click="saveWordNow({ tts: !wordCfg.tts })">{{ wordCfg.tts ? '开' : '关' }}</button>
      </div>
      <div class="lock-row">
        <span class="badge">自动读</span>
        <span class="grow">进入看词页读一次（默写不出声）</span>
        <button type="button" :class="['toggle', { on: wordCfg.tts_autoplay }]" @click="saveWordNow({ tts_autoplay: !wordCfg.tts_autoplay })">{{ wordCfg.tts_autoplay ? '开' : '关' }}</button>
      </div>
      <div class="frm-row">
        <label class="fld w104"><span>口音</span>
          <select :value="wordCfg.tts_lang" @change="saveWordNow({ tts_lang: $event.target.value })">
            <option value="en-GB">英式</option>
            <option value="en-US">美式</option>
          </select>
        </label>
      </div>

      <h4 class="w-h">词书</h4>
      <div class="word-book" v-for="b in wordBooks" :key="b.id">
        <div class="word-book-h">
          <strong>{{ b.name }}</strong>
          <span class="badge">{{ b.is_system ? '系统' : '家庭' }}</span>
          <span class="dim">{{ b.word_count }} 词<template v-if="b.source_unit"> · {{ b.source_unit }}</template><template v-if="b.source_ver"> · {{ b.source_ver }}</template> · 已学 {{ b.learned_count }} · 到期 {{ b.due_count }} · 错词 {{ b.problem_count }}</span>
          <button class="ghost-s" @click="openWordBook(b.id)">看词</button>
        </div>
        <template v-if="!b.is_system">
          <div class="frm-row">
            <label class="fld grow"><span>名字</span><input v-model="b.name" /></label>
            <button class="ok" @click="saveWordBook(b)">改名</button>
            <button class="del" @click="delWordBook(b)">删</button>
          </div>
        </template>
        <p v-else class="dim">系统词书只读，不能改词、不能导入。</p>
      </div>
      <div class="frm-row">
        <label class="fld grow"><span>新建家庭词书</span><input v-model="wordNewBook" placeholder="如：课外词" maxlength="30" /></label>
        <button class="ok" @click="addWordBook">＋新建</button>
      </div>
      <button type="button" class="ghost-s rules-toggle" @click="wordImportOpen = !wordImportOpen">{{ wordImportOpen ? '收起导入' : '导入单词' }}</button>
      <div v-if="wordImportOpen" class="add-box mt14">
        <div class="add-title">导入家庭词书</div>
        <p class="dim">一列英文、一列中文，音标可空。制表符或逗号都行，一次最多 500 行。</p>
        <pre class="word-sample">always	总是	/ˈɔːlweɪz/
usually	通常	/ˈjuːʒuəli/
get up	起床</pre>
        <label class="fld grow"><span>导入到</span>
          <select v-model="wordImport.book_id">
            <option value="">选一本家庭词书</option>
            <option v-for="b in wordBooks.filter(x => !x.is_system)" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </label>
        <textarea v-model="wordImport.text" class="word-import" rows="5" placeholder="always	总是	/ˈɔːlweɪz/&#10;get up	起床"></textarea>
        <button class="ok" :disabled="wordBusy" @click="importWordBook">导入</button>
        <p v-if="wordImport.result" class="dim">成功 {{ wordImport.result.ok }} 行<template v-if="(wordImport.result.errors || []).length"> · {{ wordImport.result.errors.length }} 行有问题</template></p>
        <ul v-if="wordImport.result && wordImport.result.errors && wordImport.result.errors.length" class="word-err">
          <li v-for="e in wordImport.result.errors.slice(0, 8)" :key="e.line">第 {{ e.line }} 行：{{ e.error }}</li>
        </ul>
      </div>
      <div v-if="wordOpenBook" class="word-list">
        <h4 class="w-h">{{ wordOpenBook.name }} 的词</h4>
        <div v-for="w in (wordOpenBook.words || []).filter(x => x.active !== 0)" :key="w.id" class="word-row">
          <b>{{ w.word }}</b>
          <span>{{ w.cn }}</span>
          <em>{{ w.ipa }}</em>
        </div>
        <button class="ghost-s" @click="wordOpenBook = null">收起</button>
      </div>
    </section>
</template>

<style scoped>
.review-scope-count { align-self: flex-end; padding-bottom: 10px; }
.scope-books { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin: 4px 0 8px; }
.scope-group { border: 1px solid var(--line); border-radius: var(--radius-md); padding: 10px 12px; background: var(--surface-2); }
.scope-group > strong { display: block; margin-bottom: 7px; color: var(--brand-deep); font-size: 13px; }
.scope-book-check { display: flex; align-items: center; gap: 6px; padding: 4px 0; color: var(--ink-2); font-size: 12px; }
.word-ov { grid-template-columns: repeat(5, 1fr); }
.word-book { border: 1px solid var(--line); border-radius: var(--radius-md); padding: 12px 14px; margin-bottom: 10px; background: var(--surface); }
.word-book-h { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.word-book-h strong { font-size: 15px; }
.word-import { width: 100%; margin: 8px 0; border: 1px solid var(--line); border-radius: var(--radius-md); padding: 8px 10px; font-family: ui-monospace, Menlo, monospace; font-size: 13px; min-height: 100px; color: var(--ink); background: var(--surface); resize: vertical; }
.word-sample { margin: 6px 0 10px; padding: 10px 12px; background: var(--surface); border-radius: var(--radius-sm); font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: var(--ink-2); white-space: pre-wrap; overflow-x: auto; }
.word-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--surface-2); flex-wrap: wrap; }
.word-row > div { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; min-width: 0; }
.word-row em { font-style: normal; color: var(--ink-3); font-size: 11px; }
.word-list { margin-top: 10px; padding: 10px 12px; background: var(--surface-2); border-radius: var(--radius-md); }
.word-err { margin: 6px 0 0; padding-left: 18px; color: var(--danger); font-size: 12px; }
.word-week { height: 120px; }
@media (max-width: 760px) {
  .word-ov { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 560px) {
  .word-ov { grid-template-columns: repeat(2, 1fr); }
}
</style>
