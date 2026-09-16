# 一次性抽取脚本：把「阳光」页从 frontend/src/Admin.vue 抽到 AdminShop.vue（v0.3.40）。
# 输入必须是抽取前的壳：git show 40d7a2c:frontend/src/Admin.vue > frontend/src/Admin.vue
# 用法：在仓库根目录 `python3 scripts/admin-refactor/extract_adminshop.py`
# 脚本里每一步都带断言（块括号配平、搬走的标识符在壳里为 0、模板不引用壳专属名字、样式整块搬）；
# 说明与踩过的坑见同目录 README.md。
"""AdminShop 抽取 v2（阳光页：商店 + 银行 + 等级 + 扣分，四段合一页）。

相对上一版的改动：
  1) bend()：缩进过的空行（"  "）不再当成块尾 —— 上一版会在 addPenalty 里截断（一处判断）；
  2) grab()：加括号配平断言，块被截断立刻炸，不再静默生成半截函数（一条断言）；
  3) 样式：.chip 是多行规则，整条搬走（上一版只搬首行 → 壳里残留声明、底座留下无收尾的空规则）；
  4) 壳里 discardDirty：newReward/newRank 两行一起换成子组件委托（上一版只换了一行）；
  5) 壳里 saveDirty：reward/rank 行内编辑交给子组件 saveCurrentEdit（否则 saveReward 搬走后会 ReferenceError）；
  6) 收尾断言：搬走的标识符在壳里为 0、整文件括号配平、子组件 API 面。
"""
import re

AP = 'frontend/src/Admin.vue'
CHILD = 'frontend/src/components/AdminShop.vue'
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


# ---------- 1) 三段模板 ----------
rngs = []
i = 0
while i < len(lines):
    if lines[i].strip().startswith('<section v-if="section === \'shop\'"'):
        e = next(k for k in range(i, len(lines)) if lines[k].strip() == '</section>')
        rngs.append((i, e))
        i = e + 1
    else:
        i += 1
assert len(rngs) == 3, rngs
t = '\n\n'.join('\n'.join(lines[a:b + 1]) for a, b in rngs)
n = t.count('<section v-if="section === \'shop\'" class="a-card enter">')
assert n == 3, n
t = t.replace('<section v-if="section === \'shop\'" class="a-card enter">', '<section class="a-card enter">')
for old, new in [('@click="saveBankGoal"', '@click="$emit(\'save-bank-goal\')"'),
                 ('@click="togglePenalty"', '@click="$emit(\'toggle-penalty\')"')]:
    c = t.count(old)
    assert c == 1, (old, c)
    t = t.replace(old, new)
# 模板里只剩 currentKidName（壳的 ref）没有对应 prop，换成子组件的 kidName
_ck = t.count('currentKidName')
assert _ck == 4, _ck                       # 2 处标题各用两次
t = t.replace('currentKidName', 'kidName')
for bad in ['saveBankGoal', 'togglePenalty', 'section ===']:
    assert bad not in t, 'leftover ' + bad
print('三段合计 %d 行；模板改写 OK' % (len(t.split('\n'))))

# ---------- 2) 搬函数与状态 ----------
MOVEF = ['addReward', 'saveReward', 'delReward', 'addRank', 'saveRank', 'delRank', 'addPenalty',
         'cancelPenalty', 'toggleBank', 'saveBankInterest', 'bankGoalDeliver', 'handleBankRequest',
         'settleInterestNow']
MOVEC = [r'newReward = reactive', r'newRank = reactive', r'newPenalty = reactive',
         r'bankHistoryOpen = ref', r'penaltySubmitting = ref', r'PENALTY_REASONS =', r'PENALTY_AMOUNTS =',
         r'pendingBankRequests = computed', r'historyBankRequests = computed',
         r'penaltyReasonRows = computed', r'maxPenaltyAmount = computed']
parts = []
for pat in MOVEC:
    a, b = grab(pat)
    print('  grab %-26s %d-%d (%d 行)' % (pat, a + 1, b, b - a))
    parts.append('\n'.join(lines[a:b]))
for f in MOVEF:
    a, b = grab(f)
    print('  grab %-26s %d-%d (%d 行)' % (f, a + 1, b, b - a))
    parts.append('\n'.join(lines[a:b]))
body = '\n'.join(parts)

DEF = {'rewards.value': 'props.rewards', 'ranks.value': 'props.ranks', 'penalties.value': 'props.penalties',
       'penaltySummary.value': 'props.penaltySummary', 'penaltyEnabled.value': 'props.penaltyEnabled',
       'bankData.value': 'props.bankData', 'bankRequests.value': 'props.bankRequests',
       'bankInterest': 'props.bankInterest', 'isOwner.value': 'props.isOwner',
       'currentKidName.value': 'props.kidName'}
for a, b in DEF.items():
    body = body.replace(a, b)
_n = len(re.findall(r'props\.bankData = await [^;]*;', body))
assert _n == 2, _n                                     # 就地合并必须成对补右括号（两处同行赋值）
body = re.sub(r'props\.bankData = await ([^;]*);', r'Object.assign(props.bankData, await \1);', body)
body = re.sub(r'(?<![\w.$])showToast\(', 'props.showToast(', body)
body = re.sub(r'(?<![\w.$])withBusy\(', 'props.withBusy(', body)
body = body.replace('await loadBank()', "emit('reload-bank')").replace('await load()', "emit('reload')")
body = re.sub(r'(?<![\w.$])bankBusy\.value', 'busy.value', body)
assert 'loadBank()' not in body and 'await load()' not in body
assert 'props.bankData = ' not in body
assert balanced(body), 'body 括号不配平'
print('搬入 %d 个函数 + %d 个状态块；body %d 行' % (len(MOVEF), len(MOVEC), body.count('\n') + 1))

# ---------- 3) 子组件 ----------
PROPS = [
    ('rewards', 'Array'), ('ranks', 'Array'), ('penalties', 'Array'),
    ('penaltySummary', 'Object'), ('penaltyEnabled', 'Boolean'), ('bankData', 'Object'),
    ('bankRequests', 'Array'), ('bankGoal', 'Object'), ('bankInterest', 'Object'),
    ('bankBusy', 'Boolean'), ('isOwner', 'Boolean'), ('kidName', 'String'),
]
head = '''<script setup>
// 家长工作台 · 阳光（商店 + 银行 + 等级 + 扣分，四段合一页）
// 数据由 Admin.vue 的 shop 包持有；本页表单与提交在子组件，
// 银行目标（脏条快照）与扣分开关仍由壳负责，用 emit 触发。
import { ref, reactive, computed } from 'vue'
import { Star } from '@lucide/vue'
import { api } from '../api.js'
import { rankIcon } from '../icons.js'
import { useAdminEdit } from '../adminEdit.js'

const props = defineProps({
  rewards: { type: Array, default: () => [] },
  ranks: { type: Array, default: () => [] },
  penalties: { type: Array, default: () => [] },
  penaltySummary: { type: Object, default: () => ({ net: 0, count: 0, amount: 0, by_reason: [] }) },
  penaltyEnabled: { type: Boolean, default: false },
  bankData: { type: Object, default: () => ({ enabled: false, balance: 0, pocket_balance: 0, goal: null, requests: [], ledger: [] }) },
  bankRequests: { type: Array, default: () => [] },
  bankGoal: { type: Object, required: true },
  bankInterest: { type: Object, required: true },
  bankBusy: { type: Boolean, default: false },
  isOwner: { type: Boolean, default: false },
  kidName: { type: String, default: '' },
  showToast: { type: Function, required: true },
  withBusy: { type: Function, required: true },
})
const emit = defineEmits(['reload', 'reload-bank', 'save-bank-goal', 'toggle-penalty'])

const { editKind, editId, findEditRow, clearEdit, beginEdit, cancelEdit, isEditing } = useAdminEdit()

// 本页自己的提交忙碌（壳的 bankBusy 只管「保存目标」那一颗按钮）
const busy = ref(false)
const bankBusy = computed(() => props.bankBusy || busy.value)
'''
tail = '''
// ---- 脏条要的三件事（壳通过 ref 调用）----
function filled(v) { return String(v ?? '').trim() !== '' }
function isAddDirty() {
  if (filled(newReward.name) || Number(newReward.price) !== 30 || (newReward.category || '') !== '娱乐') return true
  if (filled(newRank.name) || Number(newRank.min_sunshine) !== 0) return true
  return false
}
function discardAdd() {
  Object.assign(newReward, { name: '', price: 30, category: '娱乐' })
  Object.assign(newRank, { name: '', min_sunshine: 0 })
}
async function saveCurrentEdit() {
  const row = findEditRow(editKind.value, editId.value)
  if (!row) return
  if (editKind.value === 'reward') await saveReward(row)
  else if (editKind.value === 'rank') await saveRank(row)
}
defineExpose({ isAddDirty, discardAdd, saveCurrentEdit })
</script>
'''
child = head + '\n' + body + tail + '\n<template>\n' + t + '\n</template>\n'
open(CHILD, 'w', encoding='utf-8').write(child)
print('AdminShop.vue 写入 %d 行' % (child.count('\n') + 1))

# ---------- 4) 接线 ----------
tag = """    <AdminShop
      v-if="section === 'shop'"
      ref="shopRef"
      :rewards="rewards"
      :ranks="ranks"
      :penalties="penalties"
      :penalty-summary="penaltySummary"
      :penalty-enabled="penaltyEnabled"
      :bank-data="bankData"
      :bank-requests="bankRequests"
      :bank-goal="bankGoal"
      :bank-interest="bankInterest"
      :bank-busy="bankBusy"
      :is-owner="isOwner"
      :kid-name="currentKidName"
      :show-toast="showToast"
      :with-busy="withBusy"
      @reload="load"
      @reload-bank="loadBank"
      @save-bank-goal="saveBankGoal"
      @toggle-penalty="togglePenalty"
    />""".split('\n')
for a, b in reversed(rngs[1:]):
    del lines[a:b + 1]
lines[rngs[0][0]:rngs[0][1] + 1] = tag
if 'AdminShop.vue' not in '\n'.join(lines):
    i = next(k for k, l in enumerate(lines) if l.strip() == "import AdminReview from './components/AdminReview.vue'")
    lines[i + 1:i + 1] = ["import AdminShop from './components/AdminShop.vue'"]
if not re.search(r'^const shopRef = ref\(null\)', '\n'.join(lines), re.M):
    i = next(k for k, l in enumerate(lines) if l.strip().startswith('const tasksRef = ref(null)'))
    lines[i + 1:i + 1] = ['const shopRef = ref(null)  // 阳光页子组件：脏条要调它的 isAddDirty/discardAdd/saveCurrentEdit']

# ---------- 5) 删壳实现 ----------
for f in MOVEF:
    a, b = grab(f)
    del lines[a:b]
for pat in MOVEC:
    a, b = grab(pat)
    del lines[a:b]

# 5a) isAddDirty：奖励/等级的新增表单交给子组件
ir = [k for k, l in enumerate(lines)
      if l.startswith('  if (filled(newReward.name)') or l.startswith('  if (filled(newRank.name)')]
assert len(ir) == 2, ir
for k in reversed(ir):
    del lines[k]

# 5b) isDirty：加阳光页委托
i = next(k for k, l in enumerate(lines) if l.startswith('const isDirty = computed'))
assert 'isAddDirty() ||' in lines[i], lines[i]
lines[i] = lines[i].replace('isAddDirty() ||', 'isAddDirty() || !!shopRef.value?.isAddDirty?.() ||')

# 5c) discardDirty：newReward/newRank 两行 -> 一行委托
dd = next(k for k, l in enumerate(lines) if l.startswith('function discardDirty()'))
end = next(k for k in range(dd, len(lines)) if lines[k] == '}')
old = [k for k in range(dd, end) if re.match(r'^  Object\.assign\((newReward|newRank)', lines[k])]
assert len(old) == 2, old
lines[old[0]] = '  shopRef.value?.discardAdd?.()'
for k in reversed(old[1:]):
    del lines[k]

# 5d) saveDirty：奖励/等级的行内编辑交给子组件保存
i = next(k for k, l in enumerate(lines) if l.strip() == "if (kind === 'reward') await saveReward(row)")
assert lines[i + 1].strip() == "else if (kind === 'rank') await saveRank(row)", repr(lines[i + 1])
lines[i:i + 2] = ["    if (kind === 'reward' || kind === 'rank') await shopRef.value?.saveCurrentEdit?.()"]

# 5e) saveDirty 的首道闸：新增表单的脏状态现在分布在两个子组件里，一起看
i = next(k for k, l in enumerate(lines) if l.strip() == 'if (isAddDirty()) {')
lines[i] = '  if (isAddDirty() || tasksRef.value?.isAddDirty?.() || shopRef.value?.isAddDirty?.()) {'
assert lines[i].strip().startswith('if (isAddDirty() || tasksRef'), lines[i]

# 5f) 三段搬走后留下的孤儿注释，以及多出来的空行
for orphan in ['    <!-- 扣分 -->', '    <!-- 等级 -->']:
    k = next(k for k, l in enumerate(lines) if l == orphan)
    del lines[k]
    if lines[k] == '' and lines[k - 1] == '':
        del lines[k]
k = next(k for k, l in enumerate(lines) if l == '    <!-- 商店 -->')
lines[k] = '    <!-- 阳光（商店 / 银行 / 等级 / 扣分）-->'

# ---------- 6) 样式：整条规则一起挪 ----------
WANT = re.compile(r'^\.(chip|pen-amt|pen-sum)')
starts = [k for k, l in enumerate(lines) if WANT.match(l)]
blocks = []
for k in starts:
    e = k
    while not lines[e].rstrip().endswith('}'):
        e += 1
    blocks.append((k, e))
assert len(blocks) == 7, [(a + 1, b + 1) for a, b in blocks]          # 5 条 chip 群 + 2 条 pen
multi = [(a, b) for a, b in blocks if b > a]
assert len(multi) == 1 and lines[multi[0][0]].startswith('.chip {'), multi
css_lines = []
for a, b in blocks:
    css_lines.append('.admin ' + lines[a])          # 只有选择器那行加 .admin
    css_lines.extend(lines[a + 1:b + 1])
moved = sum(b - a + 1 for a, b in blocks)
assert moved == 11, moved                            # .chip 那 5 行必须整块跟着走
assert balanced('\n'.join(css_lines))
for a, b in reversed(blocks):
    del lines[a:b + 1]
assert not any(WANT.match(l) for l in lines), '壳里还有 chip/pen 规则'
print('已挪 %d 条规则（%d 行；.chip 多行块整块）' % (len(blocks), moved))

# ---------- 7) 壳里因为这一搬而变死的导入 ----------
shell = '\n'.join(lines)


def nobar(t):
    return '\n'.join(l for l in t.split('\n') if not l.startswith('import'))


k = next(k for k, l in enumerate(lines) if l.strip() == "import { rankIcon } from './icons.js'")
assert not re.findall(r'(?<![\w.$])rankIcon(?![\w$])', nobar(shell)), 'rankIcon 还有用，别删导入'
del lines[k]
k = next(k for k, l in enumerate(lines) if l.startswith('import { Eye, Baby, Store'))
assert not re.findall(r'(?<![\w.$])Star(?![\w$])', nobar(shell)), 'Star 还有用，别从导入里去'
lines[k] = lines[k].replace(' Star,', '')
shell = '\n'.join(lines)
assert 'rankIcon' not in shell
assert 'rankIcon' not in shell
open(AP, 'w', encoding='utf-8').write(shell)
b0 = open(BP, encoding='utf-8').read()
open(BP, 'w', encoding='utf-8').write(b0.rstrip('\n') + '\n\n/* —— 扣分 chip / 净扣 —— */\n' + '\n'.join(css_lines) + '\n')
print('底座追加 %d 行；壳 %d 行' % (len(css_lines), len(lines)))

# ---------- 8) 收尾断言 ----------
c = open(CHILD, encoding='utf-8').read()
GONE = MOVEF + ['newReward', 'newRank', 'newPenalty', 'PENALTY_REASONS', 'PENALTY_AMOUNTS', 'bankHistoryOpen',
                'penaltySubmitting', 'pendingBankRequests', 'historyBankRequests', 'penaltyReasonRows',
                'maxPenaltyAmount', 'saveReward', 'saveRank']
left = {n: len(re.findall(r'(?<![\w.$])' + n + r'(?![\w$])', shell)) for n in set(GONE)}
assert not any(left.values()), {k: v for k, v in left.items() if v}
assert balanced(shell), '壳括号不配平（有残留声明/半截块）'
for must in ('shopRef.value?.isAddDirty?.()', 'shopRef.value?.discardAdd?.()', 'shopRef.value?.saveCurrentEdit?.()'):
    assert must in shell, must

# 壳里每个 XxxRef.value 都必须有 const XxxRef = ref(null)（只插了模板 ref 属性会漏声明）
for _n in sorted(set(re.findall(r'(?<![\w.$])(\w+Ref)\.value', shell))):
    assert re.search(r'^const ' + _n + r' = ref\(null\)', shell, re.M), '缺声明：' + _n


def imported(t):
    out = set()
    for m in re.findall(r'import \{([^}]*)\}', t):
        out |= {x.strip() for x in m.split(',') if x.strip()}
    return out


def topdecl(t):
    return set(re.findall(r'^(?:const|let|function|async function)\s+([A-Za-z_$][\w$]*)', t, re.M))


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
print('Admin.vue %d 行 | 子组件 prop %d 个（函数 %d）+ emit %d 个 + expose %d 个：%s'
      % (len(lines), len(dprops), len(dfunc), len(dems), len(dexp), '/'.join(dexp)))
print('子组件模板用到的组件：%s（均已导入）' % (', '.join(tags) or '无'))
print('模板里引用到的壳专属名字：%s' % (', '.join(leak) if leak else '无'))
# 模板里除了这几个「看着像标识符的普通词」，不该再出现壳专属名字
FP = {'daily', 'weekly', 'section'}
assert set(leak) <= FP, leak
