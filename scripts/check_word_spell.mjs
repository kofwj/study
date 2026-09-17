#!/usr/bin/env node
// 拼写题回归：拿真实词库逐条断言「孩子敲字母 + 撇号 → 拼出来的文本 = 答案」。
// 起因（v0.3.52）：答案里的句号/问号/叹号被当成一个字母槽位，导致带标点的句型永远判错
// （家长端「英语单词」页看到「错 N 次」，孩子怎么改都错）。
// v0.3.58 补：同一个坑还有**撇号** —— `'` 以前算进「要敲的字母」，槽位上看不见，
//   孩子按槽位敲就会整串错位一格（`It's your turn.` → `Itsy ourt urn.`）→ 永远判错。
// v0.3.66 再改：撇号改成**看得见、必须填**的格子（它是单词的一部分）；空格和句末标点仍免敲。
//
// 用法：node scripts/check_word_spell.mjs [词库路径]
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import { assembleSpelling, slotCells, typedOf } from '../frontend/src/wordSpell.js'

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
  // 孩子要敲的：字母 + 撇号（弯撇号也算，统一成直的）；空格、句号这些由答案带出
  const typedRight = word.replace(/[\u2018\u2019]/g, "'").replace(/[^A-Za-z']/g, '')
  const chars = [...word]
  const cells = slotCells(word, typedRight)
  if (/[^A-Za-z ]/.test(word)) punctWords += 1
  if (/['\u2019]/.test(word)) aposWords += 1

  // 1) 各种「孩子可能怎么敲」都要拼出原答案
  const ways = [
    ['只敲字母和撇号', typedRight],
    ['连标点一起敲', word],
    ['末尾多敲一个句号', typedRight + '.'],
    ['字母之间乱加空格', typedRight.replace(/([a-z'])(?=[a-z'])/gi, '$1 ')],
    ['全大写', typedRight.toUpperCase()],
    ['撇号用弯的', typedRight.replace(/'/g, '\u2019')],
  ]
  for (const [label, typed] of ways) {
    n += 1
    const got = assembleSpelling(word, typed)
    if (got.toLowerCase() !== word.toLowerCase()) problems.push([word, label, typed, got])
  }

  // 2) 槽位：一个不多一个不少；**字母和撇号是要敲的格**，只有空格和其它标点固定
  n += 1
  if (cells.length !== chars.length) problems.push([word, '槽位数和答案对不上', cells.length, chars.length])
  cells.forEach((c, i) => {
    n += 1
    const ch = chars[i]
    const typable = /[A-Za-z'\u2019]/.test(ch)
    if (typable && c.kind !== 'letter') problems.push([word, '该敲的格子没做成要敲的格', ch, c.kind])
    if (!typable && c.kind === 'letter') problems.push([word, '标点/空格被当成了要敲的格子', ch, c.kind])
  })
  n += 1
  if (cells.filter((c) => c.kind === 'letter').length !== typedRight.length) {
    problems.push([word, '要敲的格子数和「该敲的字符数」不一致', typedRight.length,
      cells.filter((c) => c.kind === 'letter').length])
  }

  // 3) 撇号必须是**看得见、且要孩子自己填**的格子（v0.3.66 改：以前是自动补的固定格）
  if (/['\u2019]/.test(word)) {
    n += 1
    const qi = chars.findIndex((ch) => /['\u2019]/.test(ch))
    const cell = cells[qi]
    const ki = chars.slice(0, qi).filter((c) => /[A-Za-z'\u2019]/.test(c)).length   // 这是第几个要敲的格
    if (!cell || cell.kind !== 'letter' || cell.fill !== typedRight[ki]) {
      problems.push([word, '撇号不是「看得见、要自己填」的格子', JSON.stringify(chars[qi]),
        cell ? cell.kind + '/' + JSON.stringify(cell.fill) : 'none'])
    }
    // 漏敲撇号 → 拼出来的串必须不等于原答案（会被判错），这才是练它的意义
    n += 1
    if (assembleSpelling(word, typedRight.replace(/'/g, '')).toLowerCase() === word.toLowerCase()) {
      problems.push([word, '漏敲撇号竟然还能拼出原答案', typedRight, ''])
    }
  }

  // 4) typedOf 只留「要敲的字符」：字母 + 撇号；空格、句末标点都要被剔掉
  n += 1
  // typedOf 保留大小写（页面上要照着孩子敲的显示），所以这里跟「原样大小写」的 typedRight 比
  if (typedOf(word) !== typedRight) {
    problems.push([word, 'typedOf 结果不对', typedOf(word), typedRight])
  }

  // 5) 只敲标点（例如只按一个句号）＝ 没输入，页面该提示「先写一写」
  n += 1
  const onlyPunct = word.replace(/[A-Za-z']/g, '')
  if (onlyPunct && typedOf(onlyPunct) !== '') problems.push([word, '只敲标点竟然算有输入', onlyPunct, typedOf(onlyPunct)])
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
  // 光标的上界是「已经敲进去的字符数」（字母 + 撇号），不是单词的格子数
  const wantNo = Math.max(0, Math.min(typedOf(typed).length, Math.floor(rawCaret)))
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
