// 庆祝动效共享：彩纸样式（伙伴进化、升级、成就 NEW 共用）
export const CONFETTI_COLORS = ['#f5a524', '#f26f5f', '#3aa4e0', '#2e9e63']

export function confettiStyle(i, n = 18) {
  return {
    left: ((i + 1) * (100 / (n + 1))) + '%',
    animationDelay: (i * 0.08) + 's',
    '--confetti-color': CONFETTI_COLORS[i % CONFETTI_COLORS.length],
  }
}
