#!/usr/bin/env node
// 英语复习页（/word/）的规则回归：阳光档位 + 正确率 + 连击，逐条断言。
// 口径（2026-09-16 定）：60 分以下 0；60–100 线性到 10，向下取整（70→2、80→5、95→8、100→10）。
// 用法：node scripts/check_word_game.mjs
import { scoreOf, sunshineFor, streakUpdate } from '../frontend/src/wordGame.js'

const cases = [
  [0, 0], [59, 0], [60, 0], [61, 0], [70, 2], [75, 3], [80, 5], [90, 7], [95, 8], [99, 9], [100, 10],
  [120, 10],                       // 超范围按满分
  ['70', 2],                       // 字符串也能算
  [null, 0], [NaN, 0],
]
let bad = 0
for (const [score, want] of cases) {
  const got = sunshineFor(score)
  if (got !== want) { console.log(`  阳光档位不符：${score} → ${got}（应为 ${want}）`); bad++ }
}
const scoreCases = [[0, 0, 0], [1, 1, 100], [17, 20, 85], [1, 3, 33], [2, 3, 67]]
for (const [right, total, want] of scoreCases) {
  const got = scoreOf(right, total)
  if (got !== want) { console.log(`  正确率不符：${right}/${total} → ${got}（应为 ${want}）`); bad++ }
}
const streakCases = [[0, true, 1], [3, true, 4], [5, false, 0], [0, false, 0]]
for (const [now, right, want] of streakCases) {
  const got = streakUpdate(now, right)
  if (got !== want) { console.log(`  连击不符：${now}+${right ? '对' : '错'} → ${got}（应为 ${want}）`); bad++ }
}
console.log(`英语复习页规则：${cases.length + scoreCases.length + streakCases.length} 条断言，失败 ${bad} 条`)
process.exit(bad ? 1 : 0)
