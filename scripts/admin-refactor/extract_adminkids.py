# 一次性抽取脚本：把「家庭」页从 frontend/src/Admin.vue 抽到 AdminKids.vue（v0.3.41）。
# 输入必须是抽取前的壳：git show fb68c6b:frontend/src/Admin.vue > frontend/src/Admin.vue
# 用法：在仓库根目录 `python3 scripts/admin-refactor/extract_adminkids.py`
"""AdminKids 抽取（家庭合页：孩子账号 + 家长成员 + 邀请码 + 家长密码，四段合一页）。

沿用 AdminShop 那一版加固过的骨架：
  1) bend() 认缩进空行（不再截断块）+ grab() 括号配平断言；
  2) 样式整条规则搬走，只给选择器那行加 .admin 前缀；
  3) 脏条三件事（isAddDirty/discardAdd/saveCurrentEdit）交给子组件，壳只留委托；
  4) 收尾断言：搬走的标识符在壳里为 0、整文件括号配平、模板不引用壳专属名字、模板用的组件都有导入。

数据（kids / terms / members / invites / inviteProtect / me.account / isOwner）仍由壳按页加载持有，当 prop 传下去；
删孩子时「清掉当前选中孩子」属于壳的状态，子组件用 emit('kid-removed', id) 交回去。
"""
import re

AP = 'frontend/src/Admin.vue'
CHILD = 'frontend/src/components/AdminKids.vue'
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


# ---------- 1) 四段模板 ----------
rngs = []
i = 0
while i < len(lines):
    if lines[i].strip().startswith('<section v-if="section === \'kids\'"'):
        e = next(k for k in range(i, len(lines)) if lines[k].strip() == '</section>')
        rngs.append((i, e))
        i = e + 1
    else:
        i += 1
assert len(rngs) == 4, rngs
t = '\n\n'.join('\n'.join(lines[a:b + 1]) for a, b in rngs)
n = t.count('<section v-if="section === \'kids\'" class="a-card">')
assert n == 1, n
t = t.replace('<section v-if="section === \'kids\'" class="a-card">', '<section class="a-card">')
n = t.count('<section v-if="section === \'kids\'" class="a-card enter">')
assert n == 3, n
t = t.replace('<section v-if="section === \'kids\'" class="a-card enter">', '<section class="a-card enter">')
# 壳的 me.account -> 子组件的 meAccount prop（成员行 + 当前账号两处）
assert t.count('me.account') == 3, t.count('me.account')   # 成员行两个按钮 + 当前账号
t = t.replace('me.account', 'meAccount')
# 邀请码保护开关仍由壳负责（inviteProtect 是壳的 ref）
assert t.count('@click="toggleProtect"') == 1
t = t.replace('@click="toggleProtect"', '@click="$emit(\'toggle-protect\')"')
for bad in ['section ===', 'me.account', 'toggleProtect', 'selectedKid']:
    assert bad not in t, 'leftover ' + bad
print('四段合计 %d 行；模板改写 OK' % (len(t.split('\n'))))

# ---------- 2) 搬函数与状态 ----------
MOVEF = ['addKid', 'saveKid', 'delKid', 'transferOwner', 'delMember', 'makeInvite',
         'inviteStatus', 'copyCode', 'delInvite', 'changePin']
MOVEC = [r'newKid = reactive', r'kidAddOpen = ref', r'pinForm = reactive']
parts = []
for pat in MOVEC:
    a, b = grab(pat)
    print('  grab %-22s %d-%d (%d 行)' % (pat, a + 1, b, b - a))
    parts.append('\n'.join(lines[a:b]))
for f in MOVEF:
    a, b = grab(f)
    print('  grab %-22s %d-%d (%d 行)' % (f, a + 1, b, b - a))
    parts.append('\n'.join(lines[a:b]))
body = '\n'.join(parts)

body = re.sub(r'(?<![\w.$])showToast\(', 'props.showToast(', body)
body = re.sub(r'(?<![\w.$])isOwner\.value', 'props.isOwner', body)
body = body.replace('await load()', "emit('reload')")
assert body.count('await refreshInvites()') == 2, body.count('await refreshInvites()')
body = body.replace('await refreshInvites()', "emit('reload-invites')")
# 删孩子后「清掉当前选中孩子」是壳的状态
_old = "    if (selectedKid.value === k.id) { selectedKid.value = ''; setSelectedKid('') }"
assert body.count(_old) == 1, body.count(_old)
body = body.replace(_old, "    emit('kid-removed', k.id)")
for bad in ['selectedKid', 'setSelectedKid', 'load()', 'refreshInvites', 'isOwner.value',
            'computed(', 'watch(', 'onMounted']:
    assert bad not in body, 'leftover ' + bad
assert balanced(body), 'body 括号不配平'
print('搬入 %d 个函数 + %d 个状态块；body %d 行' % (len(MOVEF), len(MOVEC), body.count('\n') + 1))

# ---------- 3) 子组件 ----------
head = '''<script setup>
// 家长工作台 · 家庭（孩子账号 + 家长成员 + 邀请码 + 家长密码，四段合一页）
// 数据由 Admin.vue 按页加载持有（kids/terms/members/invites/inviteProtect/me），这里只渲染 + 本页表单；
// 邀请码保护开关与「当前选中孩子」仍归壳，用 emit 触发。
import { reactive, ref } from 'vue'
import { api } from '../api.js'
import { useAdminEdit } from '../adminEdit.js'

const props = defineProps({
  kids: { type: Array, default: () => [] },
  terms: { type: Array, default: () => [] },
  members: { type: Array, default: () => [] },
  invites: { type: Array, default: () => [] },
  inviteProtect: { type: Boolean, default: false },
  isOwner: { type: Boolean, default: false },
  meAccount: { type: String, default: '' },
  showToast: { type: Function, required: true },
})
const emit = defineEmits(['reload', 'reload-invites', 'toggle-protect', 'kid-removed'])

const { editKind, editId, findEditRow, clearEdit, beginEdit, cancelEdit, isEditing } = useAdminEdit()
'''
tail = '''
// ---- 脏条要的三件事（壳通过 ref 调用）----
function filled(v) { return String(v ?? '').trim() !== '' }
function isAddDirty() {
  if (filled(newKid.name) || filled(newKid.account) || filled(newKid.pin) || filled(newKid.pin2) || (newKid.term_id || 'g5s1') !== 'g5s1' || (newKid.gender || '')) return true
  return false
}
function discardAdd() {
  Object.assign(newKid, { name: '', account: '', pin: '', pin2: '', term_id: 'g5s1', gender: '' })
  kidAddOpen.value = false
}
async function saveCurrentEdit() {
  const row = findEditRow(editKind.value, editId.value)
  if (!row) return
  if (editKind.value === 'kid') await saveKid(row)
}
defineExpose({ isAddDirty, discardAdd, saveCurrentEdit })
</script>
'''
child = head + '\n' + body + tail + '\n<template>\n' + t + '\n</template>\n'
open(CHILD, 'w', encoding='utf-8').write(child)
print('AdminKids.vue 写入 %d 行' % (child.count('\n') + 1))

# ---------- 4) 接线 ----------
tag = """    <!-- 家庭（孩子账号 / 家长成员 / 邀请码 / 家长密码）-->
    <AdminKids
      v-if="section === 'kids'"
      ref="kidsRef"
      :kids="kids"
      :terms="terms"
      :members="members"
      :invites="invites"
      :invite-protect="inviteProtect"
      :is-owner="isOwner"
      :me-account="me.account"
      :show-toast="showToast"
      @reload="load"
      @reload-invites="refreshInvites"
      @toggle-protect="toggleProtect"
      @kid-removed="onKidRemoved"
    />""".split('\n')
for a, b in reversed(rngs[1:]):
    del lines[a:b + 1]
lines[rngs[0][0]:rngs[0][1] + 1] = tag
if 'AdminKids.vue' not in '\n'.join(lines):
    i = next(k for k, l in enumerate(lines) if l.strip() == "import AdminShop from './components/AdminShop.vue'")
    lines[i + 1:i + 1] = ["import AdminKids from './components/AdminKids.vue'"]
if not re.search(r'^const kidsRef = ref\(null\)', '\n'.join(lines), re.M):
    i = next(k for k, l in enumerate(lines) if l.strip().startswith('const shopRef = ref(null)'))
    lines[i + 1:i + 1] = ['const kidsRef = ref(null)  // 家庭页子组件：脏条要调它的 isAddDirty/discardAdd/saveCurrentEdit']
# 删孩子后的收尾（壳的状态）放一个小 handler
if 'function onKidRemoved' not in '\n'.join(lines):
    i = next(k for k, l in enumerate(lines) if l.startswith('async function pickKid(id) {'))
    e = next(k for k in range(i, len(lines)) if lines[k] == '}')
    lines[e + 1:e + 1] = ['', 'function onKidRemoved(id) {',
                          "  if (selectedKid.value === id) { selectedKid.value = ''; setSelectedKid('') }",
                          '}']
# 四段搬走后留下的孤儿注释（连同它后面那行空行）
for orphan in ['    <!-- 家长成员 -->', '    <!-- 邀请码 -->']:
    k = next(k for k, l in enumerate(lines) if l == orphan)
    assert lines[k + 1] == '', repr(lines[k + 1])
    del lines[k:k + 2]

# ---------- 5) 删壳实现 ----------
for f in MOVEF:
    a, b = grab(f)
    del lines[a:b]
for pat in MOVEC:
    a, b = grab(pat)
    del lines[a:b]

i = next(k for k, l in enumerate(lines) if l.startswith('function filled(v) {'))
assert lines[i + 1] == 'function isAddDirty() {', lines[i + 1]
assert lines[i + 2].startswith('  if (filled(newKid.name)'), lines[i + 2]
assert lines[i + 4] == '}', repr(lines[i + 4])
del lines[i:i + 5]

# 5b) isDirty / saveDirty 首道闸：加上家庭页委托
i = next(k for k, l in enumerate(lines) if l.startswith('const isDirty = computed'))
assert 'isAddDirty() ||' in lines[i], lines[i]
lines[i] = lines[i].replace('isAddDirty() ||', '!!kidsRef.value?.isAddDirty?.() ||')
i = next(k for k, l in enumerate(lines) if l.strip().startswith('if (isAddDirty() || tasksRef'))
lines[i] = lines[i].replace('isAddDirty() ||', 'kidsRef.value?.isAddDirty?.() ||')

# 5c) discardDirty：newKid 一行 + kidAddOpen 收尾 -> 一行委托
dd = next(k for k, l in enumerate(lines) if l.startswith('function discardDirty()'))
end = next(k for k in range(dd, len(lines)) if lines[k] == '}')
old = [k for k in range(dd, end) if re.match(r'^  Object\.assign\(newKid', lines[k])]
assert len(old) == 1, old
lines[old[0]] = '  kidsRef.value?.discardAdd?.()'
kid = [k for k in range(dd, end) if lines[k].strip() == 'kidAddOpen.value = false']
assert len(kid) == 1, kid
del lines[kid[0]]

# 5d) saveDirty：孩子资料的行内保存交给子组件
i = next(k for k, l in enumerate(lines) if l.strip() == "else if (kind === 'kid') await saveKid(row)")
lines[i] = "    else if (kind === 'kid') await kidsRef.value?.saveCurrentEdit?.()"

# 5e) refreshInvites：原来错在调用方的 try 里兜，现在由 emit 触发，得自己兜
i = next(k for k, l in enumerate(lines)
         if l.strip() == 'async function refreshInvites() { invites.value = await api.admin.invites() }')
lines[i:i + 1] = ['async function refreshInvites() {',
                  '  try { invites.value = await api.admin.invites() } catch (e) { showToast(e.message) }',
                  '}']

# ---------- 6) 样式：整条规则一起挪 ----------
WANT = re.compile(r'^\.(invite-code|settings-form|member-row|member-info|kid-card|kid-pin)')
starts = [k for k, l in enumerate(lines) if WANT.match(l)]
blocks = []
for k in starts:
    e = k
    while not lines[e].rstrip().endswith('}'):
        e += 1
    blocks.append((k, e))
assert len(blocks) == 9, [(a + 1, b + 1) for a, b in blocks]
assert all(b == a for a, b in blocks), '这九条都是单行规则'   # 有跨行就要连声明一起搬
css_lines = ['.admin ' + lines[a] for a, b in blocks]
assert balanced('\n'.join(css_lines))
# 媒体查询里那条窄屏覆盖（缩进、不在顶层）也要跟着走，断点保持 760px
im = [k for k, l in enumerate(lines) if re.match(r'^\s+\.kid-card\s*\{', l)]
assert len(im) == 1, im
mq = [lines[k].strip() for k in im]
for k in sorted(im + [x for a, b in blocks for x in range(a, b + 1)], reverse=True):
    del lines[k]
assert not any(WANT.match(l) for l in lines), '壳里还有家庭页规则'
assert not any(re.match(r'^\s+\.(kid-card|member-|settings-form|invite-code)', l) for l in lines), '还有家庭页的媒体覆盖'
shell = '\n'.join(lines)
open(AP, 'w', encoding='utf-8').write(shell)
b0 = open(BP, encoding='utf-8').read()
open(BP, 'w', encoding='utf-8').write(
    b0.rstrip('\n') + '\n\n/* —— 家庭（孩子账号 / 成员 / 邀请码 / 家长密码）—— */\n' + '\n'.join(css_lines)
    + '\n\n@media (max-width: 760px) {\n' + '\n'.join('.admin ' + m for m in mq) + '\n}\n')
print('已挪 %d 条规则 + %d 条媒体覆盖到全局底座' % (len(blocks), len(mq)))

# ---------- 7) 收尾断言 ----------
c = open(CHILD, encoding='utf-8').read()
plain = '\n'.join(re.sub(r'//.*$', '', l) for l in shell.split('\n'))   # 注释里的名字不算
GONE = MOVEF + ['newKid', 'kidAddOpen', 'pinForm', 'isAddDirty', 'filled']
left = {n: len(re.findall(r'(?<![\w.$])' + n + r'(?![\w$])', plain)) for n in set(GONE)}
assert not any(left.values()), {k: v for k, v in left.items() if v}
# toggleProtect 只该剩下壳自己的定义与接线（inviteProtect 是壳的 ref，函数留在壳）
assert len(re.findall(r'(?<![\w.$])toggleProtect(?![\w$])', plain)) == 2, \
    re.findall(r'.{0,30}toggleProtect.{0,20}', plain)
assert balanced(shell), '壳括号不配平（有残留声明/半截块）'
for must in ('kidsRef.value?.isAddDirty?.()', 'kidsRef.value?.discardAdd?.()', 'kidsRef.value?.saveCurrentEdit?.()',
             'function onKidRemoved(id) {'):
    assert must in shell, must

# 壳里每个 XxxRef.value 都必须有 const XxxRef = ref(null)（只插了模板 ref 属性会漏声明）
for _n in sorted(set(re.findall(r'(?<![\w.$])(\w+Ref)\.value', shell))):
    assert re.search(r'^const ' + _n + r' = ref\(null\)', shell, re.M), '缺声明：' + _n


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
dexp = re.findall(r'\w+', re.search(r'defineExpose\(\{(.*?)\}\)', c, re.S).group(1))
tags = sorted(set(re.findall(r'<([A-Z][A-Za-z0-9]*)', t)))
miss = [x for x in tags if x not in imported(c) and x not in topdecl(c)]
assert not miss, '模板用了没导入的组件：%s' % miss
child_scope = set(dprops) | imported(c) | topdecl(c) | {'props', 'emit'}
used = set(re.findall(r'(?<![\w.$])([A-Za-z_$][\w$]*)', t))
leak = sorted((used & topdecl(shell)) - child_scope)
FP = {'members', 'invites', 'kids'}
FP = {'daily', 'section'}   # 模板里的 class="badge daily" 与 <section> 标签，不是引用
print('Admin.vue %d 行 | 子组件 prop %d 个（函数 %d）+ emit %d 个 + expose %d 个：%s'
      % (len(lines), len(dprops), len(dfunc), len(dems), len(dexp), '/'.join(dexp)))
print('子组件模板用到的组件：%s' % (', '.join(tags) or '无'))
print('模板里引用到的壳专属名字：%s' % (', '.join(leak) or '无'))
dead = sorted(n for n in imported(shell)
              if not re.search(r'(?<![\w.$])' + re.escape(n) + r'(?![\w$])',
                               '\n'.join(l for l in shell.split('\n') if not l.startswith('import'))))
print('壳里变死的导入：%s' % (', '.join(dead) or '无'))
