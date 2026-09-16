#!/usr/bin/env node
// 拼写题回归：拿真实词库逐条断言「孩子只敲字母 → 拼出来的文本 = 答案」。
// 起因（v0.3.52）：答案里的句号/问号/叹号被当成一个字母槽位，导致带标点的句型永远判错
// （家长端「英语单词」页看到「错 N 次」，孩子怎么改都错）。
//
// 用法：node scripts/check_word_spell.mjs [词库路径]
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import { assembleSpelling, slotCells, lettersOf } from '../frontend/src/wordSpell.js'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const seedPath = process.argv[2] || resolve(ROOT, 'data/words.seed.multi.json')
const seed = JSON.parse(readFileSync(seedPath, 'utf8'))

const words = []
const walk = (o) => {
  if (!o || typeof o !== 'object') return
  if (typeof o.word === 'string') words.push(o)
  for (const v of Object.values(o)) walk(v)
}
walk(seed)
if (!words.length) {
  console.log('词库里没读到词条：' + seedPath)
  process.exit(1)
}

const problems = []
for (const it of words) {
  const typed = lettersOf(it.word)                 // 孩子实际能敲的（字母 + 撇号）
  const got = assembleSpelling(it.word, typed)
  if (got !== it.word) problems.push([it.word, typed, got])
  // 槽位：非字母必须是固定格（不吃输入），否则 UI 上会多出一个填不对的格子
  const bad = slotCells(it.word, typed).filter((c, i) => !/[A-Za-z']/.test([...it.word][i]) && c.kind === 'letter')
  if (bad.length) problems.push([it.word, typed, '槽位把标点当成字母格'])
}
const withPunct = words.filter((x) => /[^A-Za-z' ]/.test(x.word)).length
console.log(`词条 ${words.length} 条（含标点 ${withPunct} 条）；拼不对的 ${problems.length} 条`)
for (const [w, typed, got] of problems.slice(0, 10)) {
  console.log(`  ${w}  ← 敲「${typed}」却拼出「${got}」`)
}
process.exit(problems.length ? 1 : 0)
