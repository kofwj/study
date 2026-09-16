# 一次性抽取脚本：把「已学到」页从 frontend/src/Admin.vue 抽到 AdminCursor.vue（v0.3.44）。
# 输入必须是抽取前的壳：git show ca2824c:frontend/src/Admin.vue > frontend/src/Admin.vue
#                        git show ca2824c:frontend/src/adminBase.css > frontend/src/adminBase.css
# 用法：在仓库根目录 `python3 scripts/admin-refactor/extract_admincursor.py`
#
# 这一页与前几页不同：四个开关都是即时保存，动作（setCursor / toggleLock / toggleSubjectVisible /
# saveSpritesCfg）留在壳里，子组件只 emit —— 所以子组件 0 个函数 prop、不需要 defineExpose，
# 壳的 isDirty / discardDirty / saveDirty 一行都不该变（脚本里断言这一点）。
"""AdminCursor 抽取（已学到：已学到哪一课 + 孩子端显示学科 + 进度锁 + 图鉴与基地，四块合一页）。"""
import re

AP = 'frontend/src/Admin.vue'
CHILD = 'frontend/src/components/AdminCursor.vue'
BP = 'frontend/src/adminBase.css'
src = open(AP, encoding='utf-8').read()
lines = src.split('\n')


def bend(i):
    """第 i 行是一条语句/块的开始，返回块尾下标（不含块后空行）。"""
    j = i + 1
    while j < len(lines):
        l = lines[j]
        if l.startswith((' ', '\t')):        # 缩进行：含只由空白组成的行，都还在块里
            j += 1
            continue
        if not l.strip():                    # 顶格空行 = 块结束
            break
        if l.strip() in ('}', '})', '};'):
            j += 1
        break
    return j


def balanced(t):
    return all(t.count(a) == t.count(b) for a, b in (('{', '}'), ('(', ')'), ('[', ']')))


def grab(pat):
    i = next(k for k, l in enumerate(lines) if re.match(r'^(const|function|async function)\s+' + pat, l))
    j = bend(i)
    blk = '\n'.join(lines[i:j])
    assert balanced(blk), '块被截断（括号不配平）：%s\n%s' % (pat, blk)
    return i, j


def count(pat, s=None):
    return len(re.findall(pat, s if s is not None else '\n'.join(lines)))


# 壳里三处脏条接线：这一页不该动它们，最后逐字比对
DIRTY = {}
for name in ('const isDirty = computed', 'function discardDirty()', 'async function saveDirty()'):
    i = next(k for k, l in enumerate(lines) if l.startswith(name))
    DIRTY[name] = lines[i:bend(i)]
REFS_BEFORE = set(re.findall(r'(?<![\w.$])(\w+Ref)\.value', '\n'.join(lines)))

# ---------- 1) 模板 ----------
rngs = []
i = 0
while i < len(lines):
    if lines[i].strip().startswith('<section v-if="section === \'cursor\'"'):
        e = next(k for k in range(i, len(lines)) if lines[k].strip() == '</section>')
        rngs.append((i, e))
        i = e + 1
    else:
        i += 1
assert len(rngs) == 1, rngs
t = '\n'.join(lines[rngs[0][0]:rngs[0][1] + 1])
old_sec = '<section v-if="section === \'cursor\'" class="a-card enter">'
assert t.count(old_sec) == 1
t = t.replace(old_sec, '<section class="a-card enter">')
REWRITES = [
    ('@change="setCursor(s.id, $event.target.value)"',
     '@change="$emit(\'set-cursor\', s.id, $event.target.value)"', 1),
    ('@click="toggleSubjectVisible(s.id)"', '@click="$emit(\'set-subject-visible\', s.id)"', 1),
    ('@click="toggleLock"', '@click="$emit(\'toggle-lock\')"', 1),
    ('@click="saveSpritesCfg({ enabled: !spriteCfg.enabled })"',
     '@click="$emit(\'save-sprites-cfg\', { enabled: !spriteCfg.enabled })"', 1),
    ('@click="saveSpritesCfg({ base_enabled: !spriteCfg.base_enabled })"',
     '@click="$emit(\'save-sprites-cfg\', { base_enabled: !spriteCfg.base_enabled })"', 1),
    ('currentKidName', 'kidName', 1),
]
for old, new, n in REWRITES:
    c = t.count(old)
    assert c == n, (old, c, n)
    t = t.replace(old, new)
for bad in ['section ===', 'currentKidName', 'setCursor(', 'toggleSubjectVisible(', 'saveSpritesCfg(',
            'toggleLock']:
    assert bad not in t, 'leftover ' + bad
assert t.count('subjectShown(s.id)') == 2, t.count('subjectShown(s.id)')   # 子组件本地同名函数接住
print('段 %d-%d（%d 行）；模板改写 OK' % (rngs[0][0] + 1, rngs[0][1] + 1, len(t.split('\n'))))

# ---------- 2) 搬两个页专属 computed ----------
MOVEC = [r'cursorSubjects = computed', r'displaySubjects = computed']
parts = []
for pat in MOVEC:
    a, b = grab(pat)
    print('  grab %-26s %d-%d (%d 行)' % (pat, a + 1, b, b - a))
    parts.append('\n'.join(lines[a:b]))
body = '\n'.join(parts)
DEF = {'termUnits.value': 'props.termUnits', 'tasks.value': 'props.tasks',
       'subjects.value': 'props.subjects', 'daily.value': 'props.daily'}
for a, b in DEF.items():
    body = body.replace(a, b)
for bad in DEF.keys():
    assert bad not in body, 'leftover ' + bad
assert 'SUBJECT_ORDER' in body, 'displaySubjects 需要 SUBJECT_ORDER'
assert balanced(body), 'body 括号不配平'
print('搬入 %d 个 computed；body %d 行' % (len(MOVEC), body.count('\n') + 1))

# ---------- 3) 子组件 ----------
head = '''<script setup>
// 家长工作台 · 已学到（已学到哪一课 + 孩子端显示学科 + 进度锁 + 图鉴与基地，四块合一段）
// 数据（cursors / progressLock / hiddenSubjects / spriteCfg 等）由 Admin.vue 按页加载持有；
// 这一页四个开关都是即时保存，动作仍由工作台执行（含切孩子在途请求的守卫），子组件只 emit。
import { computed } from 'vue'
import { SUBJECT_ORDER } from '../format.js'

const props = defineProps({
  cursors: { type: Object, default: () => ({}) },
  progressLock: { type: Boolean, default: true },
  hiddenSubjects: { type: Array, default: () => [] },
  spriteCfg: { type: Object, default: () => ({ enabled: true, base_enabled: true }) },
  subjects: { type: Array, default: () => [] },
  tasks: { type: Array, default: () => [] },
  daily: { type: Array, default: () => [] },
  termUnits: { type: Array, default: () => [] },
  tasksBySubject: { type: Object, default: () => ({}) },
  kidName: { type: String, default: '' },
})
defineEmits(['set-cursor', 'toggle-lock', 'set-subject-visible', 'save-sprites-cfg'])
'''
tail = '''
// 开关按钮的「开/关」判定：读 hiddenSubjects（壳里那份 subjectShown 留给 toggleSubjectVisible 用）
function subjectShown(id) {
  return !(props.hiddenSubjects || []).includes(id)
}
</script>
'''
child = head + '\n' + body + tail + '\n<template>\n' + t + '\n</template>\n'
open(CHILD, 'w', encoding='utf-8').write(child)
print('AdminCursor.vue 写入 %d 行' % (child.count('\n') + 1))

# ---------- 4) 接线（不接 ref：这页没有要暴露的方法） ----------
tag = """    <AdminCursor
      v-if="section === 'cursor'"
      :cursors="cursors"
      :progress-lock="progressLock"
      :hidden-subjects="hiddenSubjects"
      :sprite-cfg="spriteCfg"
      :tasks-by-subject="tasksBySubject"
      :kid-name="currentKidName"
      :subjects="subjects"
      :tasks="tasks"
      :daily="daily"
      :term-units="termUnits"
      @set-cursor="setCursor"
      @toggle-lock="toggleLock"
      @set-subject-visible="toggleSubjectVisible"
      @save-sprites-cfg="saveSpritesCfg"
    />""".split('\n')
lines[rngs[0][0]:rngs[0][1] + 1] = tag
if 'AdminCursor.vue' not in '\n'.join(lines):
    i = next(k for k, l in enumerate(lines) if l.strip() == "import AdminKids from './components/AdminKids.vue'")
    lines[i + 1:i + 1] = ["import AdminCursor from './components/AdminCursor.vue'"]

# ---------- 5) 删壳实现 ----------
for pat in MOVEC:
    a, b = grab(pat)
    del lines[a:b]

# 5a) SUBJECT_ORDER 只剩它一处用处 -> 导入整行删掉
_n = count(r'(?<![\w.$])SUBJECT_ORDER(?![\w$])')
assert _n == 1, _n                      # displaySubjects 刚被删掉，只剩导入这一处
i = next(k for k, l in enumerate(lines) if l.strip() == "import { SUBJECT_ORDER } from './format.js'")
del lines[i]
assert count(r'(?<![\w.$])SUBJECT_ORDER(?![\w$])') == 0

# ---------- 6) 样式：3 个规则块 + 1 条媒体覆盖 ----------
WANT = re.compile(r'^\.cursor-')
starts = [k for k, l in enumerate(lines) if WANT.match(l)]
blocks = []
for k in starts:
    e = k
    while not lines[e].rstrip().endswith('}'):
        e += 1
    blocks.append((k, e))
assert len(blocks) == 3, [(a + 1, b + 1) for a, b in blocks]
assert [b - a + 1 for a, b in blocks] == [4, 1, 5], [(a + 1, b + 1) for a, b in blocks]
css_lines = []
for a, b in blocks:
    css_lines.append('.admin ' + lines[a])          # 只有选择器那行加 .admin
    css_lines.extend(lines[a + 1:b + 1])
assert balanced('\n'.join(css_lines))
im = [k for k, l in enumerate(lines) if re.match(r'^\s+\.cursor-row\s*\{', l)]
assert len(im) == 1, im                              # 窄屏那条缩进覆盖
mq = [lines[k].strip() for k in im]
for k in sorted(im + [x for a, b in blocks for x in range(a, b + 1)], reverse=True):
    del lines[k]
assert not any(WANT.match(l) for l in lines), '壳里还有 .cursor- 规则'
assert not any(re.match(r'^\s+\.cursor-', l) for l in lines), '壳里还有 .cursor- 媒体覆盖'
shell = '\n'.join(lines)
open(AP, 'w', encoding='utf-8').write(shell)
b0 = open(BP, encoding='utf-8').read()
open(BP, 'w', encoding='utf-8').write(
    b0.rstrip('\n') + '\n\n/* —— 已学到（已学到哪一课 / 显示学科 / 进度锁）—— */\n' + '\n'.join(css_lines)
    + '\n\n@media (max-width: 760px) {\n' + '\n'.join('.admin ' + m for m in mq) + '\n}\n')
print('已挪 %d 个规则块 + %d 条媒体覆盖' % (len(blocks), len(mq)))

# ---------- 7) 收尾断言 ----------
c = open(CHILD, encoding='utf-8').read()
plain = '\n'.join(re.sub(r'//.*$', '', l) for l in shell.split('\n'))   # 注释里的名字不算
GONE = ['cursorSubjects', 'displaySubjects', 'SUBJECT_ORDER']
left = {n: len(re.findall(r'(?<![\w.$])' + n + r'(?![\w$])', plain)) for n in GONE}
assert not any(left.values()), {k: v for k, v in left.items() if v}
assert balanced(shell), '壳括号不配平'
# 这一页不该动脏条：三处接线逐字未变
for name, keep in DIRTY.items():
    i = next(k for k, l in enumerate(lines) if l.startswith(name))
    assert lines[i:bend(i)] == keep, '脏条接线被改动了：' + name
# 也不该新增 xxxRef（这页没有要暴露的方法）
refs_after = set(re.findall(r'(?<![\w.$])(\w+Ref)\.value', shell))
assert refs_after == REFS_BEFORE, (REFS_BEFORE, refs_after)
for must in ('@set-cursor="setCursor"', '@toggle-lock="toggleLock"',
             '@set-subject-visible="toggleSubjectVisible"', '@save-sprites-cfg="saveSpritesCfg"'):
    assert must in shell, must
assert 'ref="cursorRef"' not in shell


def imported(x):
    out = set()
    for m in re.findall(r'import \{([^}]*)\}', x):
        out |= {w.strip() for w in m.split(',') if w.strip()}
    return out


def topdecl(x):
    return set(re.findall(r'^(?:const|let|function|async function)\s+([A-Za-z_$][\w$]*)', x, re.M))


dprops = re.findall(r'^  (\w+): \{ type:', c, re.M)
dfunc = re.findall(r'^  (\w+): \{ type: Function', c, re.M)
dems = re.findall(r"'([\w-]+)'", re.search(r'defineEmits\(\[(.*?)\]\)', c, re.S).group(1))
assert 'defineExpose' not in c, '这一页不该有 defineExpose'
tags = sorted(set(re.findall(r'<([A-Z][A-Za-z0-9]*)', t)))
miss = [x for x in tags if x not in imported(c) and x not in topdecl(c)]
assert not miss, '模板用了没导入的组件：%s' % miss
child_scope = set(dprops) | imported(c) | topdecl(c) | {'props', 'emit'}
used = set(re.findall(r'(?<![\w.$])([A-Za-z_$][\w$]*)', t))
leak = sorted((used & topdecl(shell)) - child_scope)
assert set(leak) <= {'section'}, leak                # section 是 <section> 标签那个词
print('Admin.vue %d 行 | 子组件 prop %d 个（函数 %d）+ emit %d 个 + expose 0 个'
      % (len(lines), len(dprops), len(dfunc), len(dems)))
print('子组件模板用到的组件：%s' % (', '.join(tags) or '无'))
print('模板里引用到的壳专属名字：%s' % (', '.join(leak) or '无'))
dead = sorted(n for n in imported(shell)
              if not re.search(r'(?<![\w.$])' + re.escape(n) + r'(?![\w$])',
                               '\n'.join(l for l in shell.split('\n') if not l.startswith('import'))))
print('壳里变死的导入：%s' % (', '.join(dead) or '无'))
