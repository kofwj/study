// 拼写题的槽位与提交文本。
//
// 口径（v0.3.66 改）：**字母和撇号都要孩子自己敲**；空格和其它标点（句号、问号、逗号、连字符…）
//   由答案原样带出。为什么撇号单独对待：撇号是**单词的一部分**（let's / It's / o'clock），
//   自动补就等于孩子永远没练过它 —— 真到纸笔默写时他会漏掉。句末的句号问号是句子标点，
//   敲它只是让孩子多按一次符号页，收益低。
//   v0.3.58 曾把撇号也算「固定格」，那修的是另一个 bug（撇号被当成要敲的字母、但槽位上看不见它，
//   孩子照槽位敲就整串错位一格）。现在撇号是**看得见、必须填**的格子，那个 bug 不会回来。
// 弯撇号 ’ 和直撇号 ' 等价（平板/输入法常打出弯的）。
// 后端判分同口径：`backend/words.py` 的 `_typed_only` 也只留字母和撇号 —— 两边都有测试钉住。

const TYPABLE = /[A-Za-z'\u2019]/
/** 只留孩子要敲的字符：字母 + 撇号（弯的折成直的）。空格、句号、问号…一律剔掉。
 *  **大小写保留** —— 页面上要照着孩子敲的显示；后端判分时才忽略大小写（`words._typed_only`）。 */
export function typedOf(input) {
  return String(input || '')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[^A-Za-z']/g, '')
}

/** 槽位：字母和撇号是「要敲的格子」（fill 来自孩子输入）；空格和其它标点固定（原样带出）。
 *  caret（可选）= 光标在第几个「要敲的格子」前（0..要敲的字符数）；不传就标第一个空格子。 */
export function slotCells(word, input, caret) {
  const typed = typedOf(input)
  const at = (caret === undefined || caret === null)
    ? typed.length
    : Math.max(0, Math.min(typed.length, Math.floor(Number(caret)) || 0))
  let ti = 0
  return [...String(word || '')].map((ch) => {
    if (!TYPABLE.test(ch)) {
      return ch === ' '
        ? { kind: 'space', fill: '', cur: false }
        : { kind: 'hyphen', fill: ch, cur: false }
    }
    const fill = typed[ti] || ''
    const cur = ti === at
    ti += 1
    return { kind: 'letter', fill, cur }
  })
}

/** 提交文本：按答案的形状拼回去；**只有孩子敲了的格子**用他敲的字符，没敲的空着。
 *  所以漏敲撇号会变成 `lets`，与答案 `let's` 不同 —— 会被判错（这正是要的效果）。 */
export function assembleSpelling(word, input) {
  const typed = typedOf(input)
  let ti = 0
  let out = ''
  for (const ch of String(word || '')) {
    if (!TYPABLE.test(ch)) {
      out += ch
      continue
    }
    out += typed[ti] !== undefined ? typed[ti] : ''
    ti += 1
  }
  return out.trim().slice(0, 60)
}
