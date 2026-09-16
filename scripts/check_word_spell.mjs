#!/usr/bin/env node
// 拼写题回归：拿真实词库逐条断言「孩子只敲字母 → 拼出来的文本 = 答案」。
// 起因（v0.3.52）：答案里的句号/问号/叹号被当成一个字母槽位，导致带标点的句型永远判错
// （家长端「英语单词」页看到「错 N 次」，孩子怎么改都错）。
// v0.3.58 补：同一个坑还有**撇号** —— `'` 以前算进「要敲的字母」，槽位上看不见，
//   孩子按槽位敲就会整串错位一格（`It's your turn.` → `Itsy ourt urn.`）→ 永远判错。
//   现在几种敲法都必须拼出原答案：只敲字母 / 连标点一起敲 / 末尾多敲句号 / 字母之间乱加空格。
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
let n = 0
let punctWords = 0
let aposWords = 0
for (const it of words) {
  const word = String(it.word)
  const bare = word.replace(/[^A-Za-z]/g, '')      // 孩子最自然的敲法：只敲字母（连撇号都不敲）
  const chars = [...word]
  const cells = slotCells(word, bare)
  if (/[^A-Za-z ]/.test(word)) punctWords += 1
  if (/['’]/.test(word)) aposWords += 1

  // 1) 各种「孩子可能怎么敲」都要拼出原答案
  const ways = [
    ['只敲字母', bare],
    ['连标点一起敲', word],
    ['末尾多敲一个句号', bare + '.'],
    ['字母之间乱加空格', bare.replace(/([a-z])(?=[a-z])/g, '$1 ')],
    ['只敲字母大写', bare.toUpperCase()],
  ]
  for (const [label, typed] of ways) {
    n += 1
    const got = assembleSpelling(word, typed)
    // 大小写不参与判分（后端只比字母），所以这里也按小写比
    if (got.toLowerCase() !== word.toLowerCase()) problems.push([word, label, typed, got])
  }

  // 2) 槽位：一个不多一个不少；除了 A–Z/a–z，全部是固定格（不吃输入）
  n += 1
  if (cells.length !== chars.length) problems.push([word, '槽位数和答案对不上', cells.length, chars.length])
  cells.forEach((c, i) => {
    n += 1
    const ch = chars[i]
    if (!/[A-Za-z]/.test(ch) && c.kind === 'letter') problems.push([word, '槽位把标点/撇号当成要敲的字母格', ch, c.kind])
  })

  // 3) 撇号必须是「看得见的固定格」：孩子要知道这里有个撇号，但不用敲
  if (/['’]/.test(word)) {
    n += 1
    const qi = chars.findIndex((ch) => /['’]/.test(ch))
    const cell = cells[qi]
    if (!cell || cell.kind !== 'hyphen' || cell.fill !== chars[qi]) {
      problems.push([word, '撇号不是「看得见的固定格」', JSON.stringify(chars[qi]), cell ? cell.kind + '/' + cell.fill : 'none'])
    }
  }

  // 4) lettersOf 只留字母：撇号、空格、标点都要被剔掉
  n += 1
  if (lettersOf(word) !== bare) problems.push([word, 'lettersOf 没剔干净（撇号/标点还在）', lettersOf(word), bare])

  // 5) 只敲标点（例如只按一个句号）＝ 没输入，页面该提示「先写一写」
  n += 1
  const onlyPunct = word.replace(/[A-Za-z]/g, '')
  if (onlyPunct && lettersOf(onlyPunct) !== '') problems.push([word, '只敲标点竟然算有输入', onlyPunct, lettersOf(onlyPunct)])
}

/* 6) 光标（v0.3.63 加）：slotCells 第三个参数 = 光标在第几个字母前。
   不传 = 老行为（当前格 = 第一个空位）；传了就要精确落在那一格 ——
   这是「点某一格就能改那一格」的底层保证。 */
const caretCases = [
  ['hello', 'hel', 0],          // 光标在开头
  ['hello', 'hel', 2],          // 中间
  ['hello', 'hel', 3],          // 正好是第一个空位（= 老行为）
  ['do exercise', 'doex', 0],   // 空格/固定格不算字母序号
  ['do exercise', 'doex', 2],
  ['It\u2019s your turn.', 'its', 1],
  ['hello', 'hel', -5],         // 越界夹住 → 0
  ['hello', 'hel', 99],         // 越界夹住 → 字母数
]
for (const [word, typed, rawCaret] of caretCases) {
  n += 1
  const cells = slotCells(word, typed, rawCaret)
  const letterCells = []
  cells.forEach((c, i) => { if (c.kind === 'letter') letterCells.push(i) })
  const curs = letterCells.filter((i) => cells[i].cur)
  // 光标的上界是「已经敲进去的字母数」，不是单词的字母格数
  const wantNo = Math.max(0, Math.min(lettersOf(typed).length, Math.floor(rawCaret)))
  const gotNo = curs.length === 1 ? letterCells.indexOf(curs[0]) : -1
  if (gotNo !== wantNo) {
    problems.push([word, `「当前格」应落在第 ${wantNo} 个字母格（光标 ${rawCaret}）`, typed, `实际 ${gotNo}`])
  }
}
// 填满了就没有「当前格」（和以前一致）
n += 1
if (slotCells('hello', 'hello', 5).some((c) => c.cur)) {
  problems.push(['hello', '填满时不该有「当前格」', 'hello', ''])
}
// 不传 / null / undefined 三种都必须和以前一模一样
for (const [word, typed] of [['hello', 'he'], ['do exercise', 'doex'], ['hello', '']]) {
  n += 1
  const a = JSON.stringify(slotCells(word, typed))
  const b = JSON.stringify(slotCells(word, typed, null))
  const c = JSON.stringify(slotCells(word, typed, undefined))
  if (a !== b || a !== c) problems.push([word, '不传 caret 时行为和以前不一致', typed, ''])
}

console.log(`词条 ${words.length} 条（含标点 ${punctWords} 条，其中带撇号 ${aposWords} 条）；断言 ${n} 条，失败 ${problems.length} 条`)
for (const [w, why, typed, got] of problems.slice(0, 10)) {
  console.log(`  ${JSON.stringify(w)}  ${why}：敲「${typed}」却拼出「${got}」`)
}
process.exit(problems.length ? 1 : 0)
