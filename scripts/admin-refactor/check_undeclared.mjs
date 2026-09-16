// 静态体检：找出 <script setup> 里「用了但没有声明」的标识符。
//
// 为什么需要它：vite build 和冒烟都抓不到这类错（未声明的名字只是运行时才炸）。
// v0.3.40 就踩过一次——抽取脚本只插了模板属性 ref="shopRef"，漏了 `const shopRef = ref(null)`，
// 结果 isDirty 一求值就 ReferenceError，家长工作台白屏。
//
// 用法（仓库根目录）：
//   node scripts/admin-refactor/check_undeclared.mjs                 # 默认查 frontend/src/Admin.vue
//   node scripts/admin-refactor/check_undeclared.mjs frontend/src/components/AdminShop.vue
//
// 输出只有「未声明候选」一行：正常的噪音是 NaN / setup / __props / __expose / __emit ；
// 出现别的名字（尤其形如 xxxRef）就是漏声明了。反向对照：删掉任意一个 `const xxx = ref(null)`
// 再跑，应该能看到那个 xxx 被列出来。
import { readFileSync } from 'fs'
import { fileURLToPath, pathToFileURL } from 'url'
import { dirname, resolve } from 'path'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')                     // scripts/admin-refactor -> 仓库根
const SFC = resolve(ROOT, 'frontend/node_modules/@vue/compiler-sfc/dist/compiler-sfc.esm-browser.js')
const { parse, compileScript } = await import(pathToFileURL(SFC).href)

const target = process.argv[2] || 'frontend/src/Admin.vue'
const src = readFileSync(resolve(ROOT, target), 'utf8')
const { descriptor } = parse(src, { filename: target })
const code = compileScript(descriptor, { id: 'x' }).content

// 去注释与字符串，避免把文案/键名当成引用
let s = code.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/\/\/[^\n]*/g, ' ')
s = s.replace(/`(?:\\.|[^`\\])*`/g, '``').replace(/'(?:\\.|[^'\\])*'/g, "''").replace(/"(?:\\.|[^"\\])*"/g, '""')

const used = []
for (const m of s.matchAll(/(?<![\w.$])([A-Za-z_$][\w$]*)/g)) {
  if (/^\s*:/.test(s.slice(m.index + m[1].length))) continue        // 对象键
  used.push(m[1])
}
const decl = new Set()
for (const m of s.matchAll(/\b(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)/g)) decl.add(m[1])
for (const m of s.matchAll(/\b(?:const|let|var)\s*\{([^}]*)\}/g))
  for (const p of m[1].split(',')) { const n = p.split(':').pop().trim().replace(/^\.\.\./, ''); if (/^[A-Za-z_$][\w$]*$/.test(n)) decl.add(n) }
for (const m of s.matchAll(/\b(?:const|let|var)\s*\[([^\]]*)\]/g))
  for (const p of m[1].split(',')) { const n = p.trim(); if (/^[A-Za-z_$][\w$]*$/.test(n)) decl.add(n) }
for (const m of s.matchAll(/import\s+(?:([A-Za-z_$][\w$]*)\s*,?\s*)?(?:\{([^}]*)\})?\s*from/g)) {
  if (m[1]) decl.add(m[1])
  if (m[2]) for (const p of m[2].split(',')) { const n = p.split(' as ').pop().trim(); if (/^[A-Za-z_$][\w$]*$/.test(n)) decl.add(n) }
}
for (const m of s.matchAll(/function\s*[A-Za-z_$]*\s*\(([^)]*)\)/g))
  for (const p of m[1].split(',')) { const n = p.split('=')[0].trim().replace(/[.{}[\]]/g, ''); if (/^[A-Za-z_$][\w$]*$/.test(n)) decl.add(n) }
for (const m of s.matchAll(/\(([^()]*)\)\s*=>/g))
  for (const p of m[1].split(',')) { const n = p.split('=')[0].trim(); if (/^[A-Za-z_$][\w$]*$/.test(n)) decl.add(n) }
for (const m of s.matchAll(/catch\s*\(([^)]*)\)/g))
  for (const p of m[1].split(',')) { const n = p.trim(); if (/^[A-Za-z_$][\w$]*$/.test(n)) decl.add(n) }
for (const m of s.matchAll(/\bfor\s*\(\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g)) decl.add(m[1])

const KW = new Set(('Math JSON Number String Boolean Object Array Date RegExp Set Map Promise Error console window document navigator localStorage sessionStorage confirm alert setTimeout clearTimeout setInterval clearInterval requestAnimationFrame undefined null true false this new typeof instanceof in of return if else for while do break continue function const let var class extends super try catch finally throw switch case default delete void await async yield static get set import export from as NaN Infinity arguments globalThis fetch URL Blob FileReader CustomEvent Event Intl parseInt parseFloat isNaN').split(' '))
const missing = [...new Set(used)].filter(n => !decl.has(n) && !KW.has(n))
console.log('%s：未声明候选 %d 个：%s', target, missing.length, missing.join(' '))
