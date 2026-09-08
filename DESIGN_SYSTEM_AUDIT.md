# 设计系统审查报告

## 🔍 审查日期
2026-09-08

## 📊 发现的问题

### ❌ 严重不一致

#### 1. Border Radius 混乱（13个不同值）

**当前状态**:
- 2px - 小元素
- 4px - 进度条
- 8px - 输入框
- 10px - 标签、徽章
- 12px - 底部标签
- 14px - 导航按钮
- 16px - 今日总结卡片
- 18px - 空状态
- 20px - 卡片
- 22px - 侧边栏容器、大按钮
- 24px - 庆祝卡片
- 50% - 圆形（头像）
- 999px - 胶囊形（pill、标签）

**问题**: 13种不同的圆角值，缺乏统一规范

#### 2. Box Shadow 混乱

**混用模式**:
```css
/* CSS变量 */
box-shadow: var(--sh-1);
box-shadow: var(--sh-2);
box-shadow: var(--sh-card);

/* 内联样式 */
box-shadow: 0 3px 0 rgba(122,77,3,.16);      /* 头像 */
box-shadow: 0 4px 0 rgba(20,70,110,.12);     /* 胶囊 */
box-shadow: 0 8px 24px rgba(60,120,170,.08); /* 侧边栏 */
box-shadow: 0 20px 60px rgba(20,50,80,.25);  /* 庆祝 */
```

**问题**: 
- CSS变量和内联混用
- 不同的颜色、模糊度、透明度
- 没有统一的阴影系统

#### 3. 按钮样式碎片化（7+种）

**不同的按钮模式**:
1. `.cta.check` - accent背景 + 自定义阴影
2. `.nav-checkin` - 紫色渐变
3. `.nav` - 透明 + hover
4. `.shop-fab` - accent色 + 22px圆角
5. `.do` - brand色 + 16px圆角
6. `.ghost` - 纯文字
7. `.foot-add` - brand色 + 12px圆角

**问题**: 同样的语义（主要CTA）在不同上下文使用不同样式

#### 4. 间距混乱

**Padding值**: 2px, 3px, 4px, 6px, 8px, 9px, 10px, 11px, 12px, 14px, 16px, 18px, 22px, 28px, 32px, 44px

**问题**: 没有统一的间距标尺，相邻元素使用任意值

#### 5. 字体大小不一致

**Font Size**: 11px, 12px, 13px, 14px, 15px, 16px, 18px, 20px, 22px, 24px, 28px, 30px, 34px, 64px

**Font Weight**: 600, 700, 800, 850

**问题**: 
- 14种不同字体大小，没有清晰层级
- font-weight 850 是非标准值（应该用700或900）
- 语义元素（按钮、标题）缺乏一致性

#### 6. 卡片模式重复

**三种不同的卡片**:
- `.card` - 20px圆角, 16px/14px padding, 2px边框
- `.shop-item` - 12px圆角, 12px padding, 1px边框
- `.plan-row` - 10px圆角, 10px/12px padding, 1px边框

**问题**: 相同语义（容器卡片）用3种不同样式

#### 7. 混合设计语言

**证据**:
- **Apple风格**: 圆形头像(50%), 胶囊按钮(22px/999px), 玻璃效果
- **Material风格**: 扁平卡片+阴影, 8px网格间距
- **自定义**: 渐变按钮, 自定义阴影, 任意间距

**问题**: 多个设计系统碰撞，缺乏统一方向

#### 8. CSS变量使用不一致

**定义了变量但不总是使用**:
```css
/* 硬编码颜色 */
rgba(255,255,255,.72)  /* 应该用 --surface + opacity */
rgba(122,77,3,.16)     /* 硬编码阴影色 */
rgba(20,70,110,.12)    /* 重复多处 */
rgba(60,120,170,.08)   /* 重复多处 */
```

**问题**: CSS变量存在（--accent, --brand, --warm, --surface）但很多内联颜色绕过了系统

---

## ✅ 推荐的统一设计系统

### 1. Border Radius 标尺

```css
/* 定义统一的圆角尺度 */
--radius-sm: 8px;   /* 小元素: 标签、徽章 */
--radius-md: 12px;  /* 中等: 输入框、小卡片 */
--radius-lg: 16px;  /* 大: 卡片、模态框 */
--radius-xl: 24px;  /* 超大: 主要容器 */
--radius-pill: 999px; /* 胶囊: 完全圆角 */
--radius-circle: 50%; /* 圆形: 头像 */
```

**使用规则**:
- 标签、徽章 → `--radius-sm` (8px)
- 输入框、按钮 → `--radius-md` (12px)
- 卡片、导航项 → `--radius-lg` (16px)
- 容器、模态框 → `--radius-xl` (24px)
- 胶囊按钮 → `--radius-pill` (999px)
- 头像 → `--radius-circle` (50%)

### 2. Shadow 系统

```css
/* 三级阴影系统 */
--shadow-sm: 0 1px 3px rgba(60, 120, 170, 0.08);        /* 微提升 */
--shadow-md: 0 4px 12px rgba(60, 120, 170, 0.12);       /* 中提升 */
--shadow-lg: 0 12px 32px rgba(60, 120, 170, 0.16);      /* 高提升 */

/* 特殊阴影 */
--shadow-inset: inset 0 1px 0 rgba(255, 255, 255, 0.2); /* 玻璃高光 */
--shadow-button: 0 2px 4px rgba(122, 77, 3, 0.16);      /* 按钮立体感 */
```

**使用规则**:
- 悬停卡片 → `--shadow-sm`
- 模态框、侧边栏 → `--shadow-md`
- 重要弹窗 → `--shadow-lg`
- 高亮按钮 → `--shadow-button` + `--shadow-inset`

### 3. 按钮系统

```css
/* 统一按钮基础 */
.btn {
  padding: 12px 20px;
  border-radius: var(--radius-md);
  font-size: 15px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

/* 主要按钮 */
.btn-primary {
  background: var(--accent);
  color: white;
  box-shadow: var(--shadow-button);
}

/* 次要按钮 */
.btn-secondary {
  background: var(--surface);
  color: var(--ink);
  border: 2px solid var(--line);
}

/* 幽灵按钮 */
.btn-ghost {
  background: transparent;
  color: var(--brand);
}

/* 尺寸变体 */
.btn-sm { padding: 8px 16px; font-size: 14px; }
.btn-lg { padding: 14px 24px; font-size: 16px; }
```

### 4. 间距标尺

```css
/* 统一间距系统 (4px基础) */
--space-1: 4px;   /* 极小 */
--space-2: 8px;   /* 小 */
--space-3: 12px;  /* 中 */
--space-4: 16px;  /* 正常 */
--space-6: 24px;  /* 大 */
--space-8: 32px;  /* 很大 */
--space-12: 48px; /* 超大 */
```

**使用规则**:
- 元素内部 padding → `--space-3` 或 `--space-4`
- 元素间距 margin → `--space-4` 或 `--space-6`
- 区块间距 → `--space-6` 或 `--space-8`
- 重要分隔 → `--space-12`

### 5. 字体系统

```css
/* 字体大小层级 */
--text-xs: 12px;   /* 小标签 */
--text-sm: 13px;   /* 次要文本 */
--text-base: 14px; /* 正文 */
--text-lg: 16px;   /* 重要文本 */
--text-xl: 18px;   /* 小标题 */
--text-2xl: 24px;  /* 中标题 */
--text-3xl: 28px;  /* 大标题 */

/* 字重 */
--font-normal: 400;
--font-medium: 600;
--font-bold: 700;
```

**使用规则**:
- 正文 → `--text-base` (14px) + `--font-normal`
- 按钮 → `--text-base` (14px) + `--font-medium`
- 标题 → `--text-2xl` (24px) + `--font-bold`
- 标签 → `--text-xs` (12px) + `--font-medium`

### 6. 卡片系统

```css
/* 基础卡片 */
.card {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  border: 2px solid var(--line);
  box-shadow: var(--shadow-sm);
}

/* 卡片变体 */
.card-hover {
  transition: all 0.2s ease;
}
.card-hover:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

/* 卡片尺寸 */
.card-sm { padding: var(--space-3); border-radius: var(--radius-md); }
.card-lg { padding: var(--space-6); border-radius: var(--radius-xl); }
```

---

## 🎯 迁移策略

### 阶段1: 定义Design Tokens（1天）
1. 在`:root`中定义所有CSS变量
2. 替换硬编码值为变量
3. 删除重复定义

### 阶段2: 统一组件样式（2-3天）
1. **按钮** - 迁移到`.btn-*`系统
2. **卡片** - 统一为`.card`系统
3. **表单** - 标准化输入框样式
4. **导航** - 保持当前Apple风格，统一变量

### 阶段3: 清理和文档（1天）
1. 删除未使用的样式
2. 提取可复用类
3. 编写样式指南

### 阶段4: 测试验证（1天）
1. 视觉回归测试
2. 响应式检查
3. 浏览器兼容性

---

## 📈 预期收益

### 代码质量
- ✅ CSS代码量减少 30-40%
- ✅ 维护性提升（统一修改）
- ✅ 新功能开发更快

### 视觉一致性
- ✅ 统一的视觉语言
- ✅ 专业度提升
- ✅ 品牌识别度增强

### 性能
- ✅ CSS体积减少
- ✅ 重绘/重排优化
- ✅ 加载速度提升

---

## 🚨 风险评估

### 低风险
- 定义CSS变量（不影响现有样式）
- 渐进式迁移（逐个组件）

### 中风险
- 大量样式修改（需要完整测试）
- 可能影响现有布局（需要视觉QA）

### 建议
1. 创建新分支进行重构
2. 每个组件迁移后测试
3. 保留旧样式作为fallback
4. 分阶段合并到主分支

---

## 📝 优先级建议

### P0 - 立即修复
- ❗ 统一border-radius（最影响视觉）
- ❗ 统一按钮样式（最常用）

### P1 - 短期完成
- ⚠️ 统一阴影系统
- ⚠️ 统一间距标尺

### P2 - 长期改进
- 📋 统一字体系统
- 📋 提取卡片组件
- 📋 建立完整设计文档

---

**总结**: 当前CSS存在严重的不一致性问题，需要系统性重构。建议采用渐进式迁移策略，优先解决最影响视觉的问题（圆角、按钮）。

_审查者: code-reviewer + 人工分析_  
_日期: 2026-09-08_
