# -*- coding: utf-8 -*-
"""静态体检：子组件模板用到的 class，必须在「全局样式表」里有定义。

为什么需要它：Vue 的 <style scoped> 只对父组件自己的元素生效。子组件是多根时不会继承父组件的
scopeId（runtime-core 的 setScopeId 只在 `vnode === parentComponent.subTree` 时向上继承，
dev 分支的 filterSingleRoot 对多根返回 undefined），所以 Admin.vue 的 scoped 规则到不了
AdminXxx.vue 的元素。踩过两次：v0.3.36 的 .a-item（任务页四条规则设置行）和 v0.3.41 的
.kid-card 窄屏覆盖。

用法（仓库根目录）：
    python3 scripts/admin-refactor/check_child_styles.py

输出：
    - 「壳 scoped 里有，子组件拿不到」= 真缺口（退出码 1）
    - 「哪儿都没定义」= 历史上就存在的 no-op class（只提示，不影响退出码）
"""
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'frontend', 'src')
GLOBAL_SHEETS = [os.path.join(ROOT, 'adminBase.css'), os.path.join(ROOT, 'ui.css')]


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def style_of(text):
    return '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', text, re.S))


def classes_used(tpl):
    names = set()
    for m in re.findall(r'(?<!:)class="([^"]*)"', tpl):
        for c in m.split():
            if not re.search(r'[{}$]', c):
                names.add(c)
    for m in re.findall(r':class="([^"]*)"', tpl):
        for lit in re.findall(r"'([^']*)'", m) + re.findall(r'"([^"]*)"', m):
            for c in lit.split():
                if c and not re.search(r'[{}$:]', c):
                    names.add(c)
    return names


def defined_in(css, name):
    return re.search(r'\.' + re.escape(name) + r'(?![\w-])', css) is not None


def main():
    globals_css = {p: read(p) for p in GLOBAL_SHEETS if os.path.exists(p)}
    shell = read(os.path.join(ROOT, 'Admin.vue'))
    shell_css = style_of(shell)
    app_css = style_of(read(os.path.join(ROOT, 'App.vue')))
    gaps = 0
    for p in sorted(glob.glob(os.path.join(ROOT, 'components', '*.vue'))):
        text = read(p)
        m = re.search(r'<template>(.*)</template>', text, re.S)
        if not m:
            continue
        used = classes_used(m.group(1))
        own = style_of(text)
        unreachable, nowhere = [], []
        for c in sorted(used):
            if defined_in(own, c) or any(defined_in(t, c) for t in globals_css.values()):
                continue
            if defined_in(app_css, c):
                continue
            (unreachable if defined_in(shell_css, c) else nowhere).append(c)
        line = '%-20s 用到 %2d 个 class' % (os.path.basename(p), len(used))
        if unreachable:
            gaps += len(unreachable)
            print(line + '  ✗ 拿不到样式：' + ', '.join(unreachable) + '（壳 scoped 里有，搬去 adminBase.css）')
        elif nowhere:
            print(line + '  · 历史 no-op：' + ', '.join(nowhere))
        else:
            print(line + '  OK')
    if gaps:
        print('\n有 %d 个 class 只在壳的 scoped 样式里定义，子组件拿不到。' % gaps)
    return 1 if gaps else 0


if __name__ == '__main__':
    sys.exit(main())
