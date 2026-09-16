// 拼写题的槽位与提交文本：原来在 WordPractice.vue 里各抄了一份，两份都漏了标点，
// 结果答案 "Good morning." 里的句号被当成「一个字母槽位」—— 孩子输入不了句号（输入框只收字母和撇号），
// 拼出来的文本吃掉一个字母，判分永远错（家长端就会看到「错 N 次」，而孩子怎么改都错）。
//
// 规则：答案里的非字母字符（空格、连字符、句号、问号、逗号…）都是「答案里固定」的，原样带出、不吃输入；
// 只有字母和撇号要孩子敲。后端判分（words.normalize_word）只统一引号、转小写，**不忽略标点**，
// 所以标点必须出现在提交文本里才对得上。

const LETTER = /[A-Za-z']/

export function lettersOf(input) {
  return String(input || '').replace(/[^A-Za-z']/g, '')
}

/** 槽位：空格、标点固定（复用 hyphen 的样式），字母/撇号对应孩子输入的下一个字符 */
export function slotCells(word, input) {
  const letters = lettersOf(input)
  let li = 0
  return [...String(word || '')].map((ch) => {
    if (!LETTER.test(ch)) {
      return ch === ' '
        ? { kind: 'space', fill: '', cur: false }
        : { kind: 'hyphen', fill: ch, cur: false }
    }
    const fill = letters[li] || ''
    const cur = li === letters.length
    li += 1
    return { kind: 'letter', fill, cur }
  })
}

/** 提交文本：按答案的形状拼回去，标点原样补齐 */
export function assembleSpelling(word, input) {
  const letters = lettersOf(input)
  let li = 0
  let out = ''
  for (const ch of String(word || '')) {
    if (!LETTER.test(ch)) out += ch
    else out += letters[li++] || ''
  }
  return out.trim().slice(0, 60)
}
