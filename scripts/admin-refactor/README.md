# 家长工作台拆子组件：抽取脚本与体检

这条重构线（v0.3.32 起）把 `frontend/src/Admin.vue` 里的每一页搬进 `frontend/src/components/Admin*.vue`，
硬性不变式是**只搬不改：界面与交互不变**。这个目录放两类东西：

- **抽取脚本**：每个页面一份，一次性、可从头重跑（脚本 = 交付物，重跑结果与提交逐字节一致）。
- **体检脚本**：不依赖后端，专门抓「搬完看着没事、其实是运行时才炸」的错。

## 怎么跑

```bash
bash scripts/admin-refactor/run_checks.sh              # 静态体检（秒级）
bash scripts/admin-refactor/run_checks.sh --with-ssr   # 再跑 SSR 渲染体检
bash scripts/admin-refactor/ssr/run_ssr.sh             # 只跑 SSR 渲染体检
```

每页搬完，标准验收仍是：`bash scripts/smoke_frontend.sh`（vite build + 冒烟）+ 上面的体检 + 真后端人工走查。
本机 PATH 经常没有 node，脚本会自己把 `~/.hermes/node/bin` 加到前面（同 smoke_frontend.sh）。

## 抽取脚本（一次性）

| 脚本 | 抽出的页面 | 输入必须是哪一版壳 |
|---|---|---|
| `extract_adminshop.py` | 阳光（商店 / 银行 / 等级 / 扣分）→ `AdminShop.vue` | `git show 40d7a2c:frontend/src/Admin.vue > frontend/src/Admin.vue`（v0.3.39） |
| `extract_adminkids.py` | 家庭（孩子账号 / 成员 / 邀请码 / 家长密码）→ `AdminKids.vue` | `git show fb68c6b:frontend/src/Admin.vue > frontend/src/Admin.vue`（v0.3.40） |

在仓库根目录跑（脚本里的路径是 `frontend/src/...`）。**先复制一份到 /tmp 里试跑**：
脚本会就地改 `Admin.vue` / `adminBase.css` 并新建子组件；工作区是 git 仓库，跑坏了 `git checkout -- frontend/src` 能回来。

脚本里每一步都有断言，红了就说明「这页的形状和当初不一样了」，不要绕过断言，先看差在哪：

- `grab()`：抓到的块括号必须配平（**防止半截函数**）
- 搬走的标识符在壳里必须为 0（防止残引用）
- 壳里每个 `XxxRef.value` 必须有 `const XxxRef = ref(null)`（**防止白屏**，见下）
- 模板里不能出现「壳专属、子组件没有」的名字
- 样式整块搬走、只给选择器那行加 `.admin ` 前缀

## 体检脚本

### `check_undeclared.mjs`
把 `Admin.vue` 的 `<script setup>` 编译出来，找出**用了但没有声明**的标识符。

为什么必须有：`vite build` 和冒烟都抓不到这类错（未声明的名字只是运行时才炸）。v0.3.40 就踩过一次——
抽取脚本插了模板属性 `ref="shopRef"`，但插 `const shopRef = ref(null)` 的判断被前面的字符串短路了，
于是壳里 `shopRef.value` 满天飞却没人声明：`isDirty` 一求值就 `ReferenceError`，**家长工作台白屏**。

正常输出只有噪音：`NaN setup __props __expose __emit ...`。出现别的名字（尤其 `xxxRef`）就是漏声明。

### `check_child_styles.py`
列出每个子组件模板用到的 class，检查它是否在**全局样式表**（`adminBase.css` / `ui.css`）里有定义。

为什么必须有：Vue 的 `<style scoped>` 只作用于父组件自己的元素；子组件是**多根**时不会继承父组件的
scopeId（`runtime-core` 的 `setScopeId` 只在 `vnode === parentComponent.subTree` 时向上继承，
dev 分支的 `filterSingleRoot` 对多根返回 `undefined`）。所以壳 scoped 里的规则**到不了子组件**。
踩过两次：v0.3.36 的 `.a-item`（任务页四条规则设置行没样式，v0.3.42 才修）、v0.3.41 的 `.kid-card`
窄屏覆盖（家庭页孩子卡在窄屏不收单列）。输出里「历史 no-op」是早就没定义的 class，不影响退出码。

### `ssr/run_ssr.sh` + `ssr/fixtures/*.mjs`
把壳 / 子组件用桩数据 `renderToString` 一次，抓 Vue 警告、抛错和关键文案。
能抓：少传 prop、少导入组件（模板引用了不存在的名字）、computed 炸、关键文案丢。
抓不到：只在事件回调里求值的错 —— 那类归 `check_undeclared.mjs`。两套互补。

反向对照（确认体检有牙，改完记得改回来）：在 fixture 里把名字改回壳专属写法再跑：
- `ssr-shop.mjs`：把 `kidName` 出现处改成 `currentKidName` → 应报 `警告 2 条` + 姓名缺失
- `ssr-kids.mjs`：把 `meAccount` 改成 `me.account` → 应报 `警告 2 条` + `THROW`

## 下一页

壳里现在只剩 `cursor`（已学到）一段内联，是下一个抽取对象。搬它时注意：

1. 先读四件事：这一段用到哪些壳的状态/函数、它们的样式在哪、模板里有没有壳专属名字、脏条要不要管它。
2. 数据留在壳（按页加载），表单态和本页提交搬进子组件；壳侧效果用 emit 交回（`reload` 之类）。
3. 壳里要保留的动作（例如 `toggleProtect`、`saveBankGoal`——它们改的是壳持有的值）留在壳，子组件只 `$emit`。
4. 子组件暴露 `isAddDirty / discardAdd / saveCurrentEdit` 三个方法给壳的脏条用（新增表单脏、放弃复位、
   行内编辑保存），壳里 `isDirty` / `discardDirty` / `saveDirty` 三处改成 `xxxRef.value?.…?.()` 委托 ——
   `saveDirty` 的首道闸要把所有子组件的 `isAddDirty` 都算进去，否则脏条「保存」会静默无反应。
5. 搬完按「跑一遍 → 体检 → 真后端走查 → 一个本地提交（`feat: vX.Y.Z 家长工作台XX拆成子组件`）」收尾。
