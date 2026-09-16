// 英语复习页（/word/）的纯逻辑：算分、连击、阳光档位。
// 单独放一个模块是为了能跑 scripts/check_word_game.mjs 逐条断言（别再把规则写死在页面里）。
//
// 阳光口径（2026-09-16 定）：一局得分 = 本局正确率（整数百分比）；
// 当天按**最好成绩**结算一次额度：60 分以下 0，60–100 分线性到 10，向下取整。
// （补差额与幂等由后端负责，这里只给「这个分数对应多少阳光」。）

export function scoreOf(right, total) {
  if (!total) return 0
  return Math.max(0, Math.min(100, Math.round((right / total) * 100)))
}

export function sunshineFor(score) {
  const s = Number(score)
  if (!Number.isFinite(s) || s < 60) return 0
  const capped = Math.min(100, s)
  return Math.max(0, Math.min(10, Math.floor(((capped - 60) / 40) * 10)))
}

export function streakUpdate(streak, right) {
  return right ? Number(streak || 0) + 1 : 0
}

// 关卡文案：孩子看得懂就行，别出现「失败」「扣分」这类词
export function verdictText(right) {
  return right ? '对了' : '再看一眼'
}
