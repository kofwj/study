# -*- coding: utf-8 -*-
"""前端产物冒烟：Vite 已 build 后跑。拦住当年「login-screen 塞进 desk」那种白屏。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VUE = ROOT / "frontend" / "src" / "App.vue"
DIST = ROOT / "frontend" / "dist"


def fail(msg):
    print("FAIL", msg)
    sys.exit(1)


def template_of(path):
    src = path.read_text(encoding="utf-8")
    m = re.search(r"<template>(.*)</template>", src, re.S)
    if not m:
        fail(f"{path.name} 没有 <template>")
    return m.group(1)


def login_inside_desk(html):
    """login-screen 出现时，外层还开着 .desk → 当年白屏。"""
    stack = []  # (tag, class)
    void = {"input", "img", "br", "hr", "meta", "link"}
    for m in re.finditer(r"<(/?)([A-Za-z][\w.-]*)([^>]*)>", html):
        close, name, attrs = m.group(1), m.group(2), m.group(3)
        self_close = attrs.rstrip().endswith("/") or name.lower() in void
        cls = " ".join(re.findall(r"class=\"([^\"]*)\"", attrs))
        if close:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    stack = stack[:i]
                    break
            continue
        if "login-screen" in cls.split() and any("desk" in s[1].split() for s in stack):
            return True
        if not self_close:
            stack.append((name, cls))
    return False


def check_vue():
    html = template_of(VUE)
    if login_inside_desk(html):
        fail("App.vue：.login-screen 套在 .desk 里（会白屏）")
    if 'class="login-screen"' not in html and "class='login-screen'" not in html:
        fail("App.vue：没有 login-screen")
    if "v-else" not in html:
        fail("App.vue：没有 v-else")


def check_dist():
    index = DIST / "index.html"
    if not index.exists():
        fail("没有 frontend/dist/index.html，先 npm run build")
    html = index.read_text(encoding="utf-8")
    if 'id="app"' not in html:
        fail("index.html 缺 #app")
    js = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    css = re.findall(r'href="(/assets/[^"]+\.css)"', html)
    if not js:
        fail("index.html 没有打包后的 js")
    for rel in js + css:
        p = DIST / rel.lstrip("/")
        if not p.exists():
            fail(f"缺产物 {rel}")
    bundle = (DIST / js[0].lstrip("/")).read_text(encoding="utf-8", errors="replace")
    for needle in ("阳光学习工作台", "login-enter", "createApp"):
        if needle not in bundle:
            fail(f"js 包里没有 {needle!r}")


def _selfcheck():
    bad = '<div class="desk"><div class="login-screen"></div></div>'
    good = '<div class="desk"></div><div class="login-screen"></div>'
    assert login_inside_desk(bad) and not login_inside_desk(good)


if __name__ == "__main__":
    _selfcheck()
    check_vue()
    check_dist()
    print("frontend smoke ok")
