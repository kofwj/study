#!/usr/bin/env node
// 大队委刷题页的填空判分回归。
//
// 页面的判分逻辑内联在 frontend/public/quiz/index.html 里（这个页面要能双击打开，
// 不能靠 import 拆模块），所以这里从 QUIZ-JUDGE-START / QUIZ-JUDGE-END 之间把那段抽出来跑。
// 用例来自 data/quiz_judge_cases.json —— backend/test_quiz_phase2.py 读同一份，
// 两边口径不许漂移。
//
// 用法：node scripts/check_quiz_judge.mjs
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const html = readFileSync(join(ROOT, 'frontend', 'public', 'quiz', 'index.html'), 'utf8')
const cases = JSON.parse(readFileSync(join(ROOT, 'data', 'quiz_judge_cases.json'), 'utf8'))

const m = html.match(/\/\* QUIZ-JUDGE-START[\s\S]*?\*\/([\s\S]*?)\/\* QUIZ-JUDGE-END \*\//)
if (!m) {
  console.log('❌ 在 frontend/public/quiz/index.html 里找不到 QUIZ-JUDGE-START / QUIZ-JUDGE-END 标记')
  process.exit(1)
}
const src = m[1] + '\nexport { SEP, normText, judgeBlankLocal, displayGot };\n'
const mod = await import('data:text/javascript;base64,' + Buffer.from(src, 'utf8').toString('base64'))
const { SEP, normText, judgeBlankLocal, displayGot } = mod

let n = 0
let bad = 0
const ok = (cond, msg) => { n++; if (!cond) { console.log('  ✗ ' + msg); bad++ } }

for (const [a, b] of cases.norm_equal) {
  ok(normText(a) === normText(b), `规范化后应该相等：${JSON.stringify(a)} vs ${JSON.stringify(b)}`)
}
for (const [a, b] of cases.norm_diff) {
  ok(normText(a) !== normText(b), `规范化后不应该相等：${JSON.stringify(a)} vs ${JSON.stringify(b)}`)
}
ok(normText('') === '' && normText(null) === '' && normText(undefined) === '', '空值/未知值不炸')

for (const c of cases.blank) {
  const qq = { answer: c.answer, accept: c.accept || [] }
  const got = judgeBlankLocal(qq, c.parts)
  // want === null 是「后端判不了（未评）」；页面本地没有这个概念，只能是 false
  const want = c.want === null ? false : c.want
  ok(got === want, `填空判分不符（${c.why}）：${JSON.stringify(c.parts)} → ${got}（应为 ${want}）`)
}

ok(displayGot('a' + SEP + 'b') === 'a ／ b', 'displayGot：两个空用 ／ 连接')
ok(displayGot('a' + SEP + '') === 'a ／ （空）', 'displayGot：空位显示（空）')
ok(displayGot('') === '' && displayGot(null) === '', 'displayGot：空值不炸')
ok(displayGot('单个') === '单个', 'displayGot：没有分隔符就原样返回')

console.log(`大队委填空判分：${n} 条断言，失败 ${bad} 条`)
process.exit(bad ? 1 : 0)
