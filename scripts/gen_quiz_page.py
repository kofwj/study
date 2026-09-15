#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/quiz.seed.json 嵌进刷题页的种子块。

刷题页是单文件（frontend/public/quiz/index.html），要能直接双击打开，
所以题库不能靠 fetch 加载，只能内联。改完 data/quiz.seed.json 后跑一次本脚本即可。

用法：python3 scripts/gen_quiz_page.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "quiz.seed.json"
PAGE = ROOT / "frontend" / "public" / "quiz" / "index.html"

BEGIN = '<script id="quizSeed" type="application/json">'
END = "</script>"
PATTERN = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)


def main():
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    payload = json.dumps(seed, ensure_ascii=False, separators=(",", ":"))
    if "</" in payload:
        sys.exit("题库内容里出现了 '</'，会破坏 HTML，需要换一种嵌入方式")

    html = PAGE.read_text(encoding="utf-8")
    if not PATTERN.search(html):
        sys.exit("在 %s 里找不到种子块" % PAGE)

    n_before = len(html)
    html = PATTERN.sub(lambda _: BEGIN + payload + END, html, count=1)
    PAGE.write_text(html, encoding="utf-8")

    banks = seed.get("banks", [])
    total = sum(len(b.get("questions", [])) for b in banks)
    print("已嵌入题库：%s（%d 个题库、%d 题）"
          % (seed.get("curriculum_ver"), len(banks), total))
    for b in banks:
        print("  - %s %s：%d 题，下线日期 %s"
              % (b.get("id"), b.get("name"), len(b.get("questions", [])),
                 b.get("end_at") or "未设置"))
    print("页面：%s（%d → %d 字节）" % (PAGE, n_before, len(html)))


if __name__ == "__main__":
    main()
