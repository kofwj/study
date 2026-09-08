# -*- coding: utf-8 -*-
"""批量抓取江苏 1-6 年级主课教材目录，生成 data/catalog.json。

用法：
  python3 scripts/gen_catalog.py --list     # 只列书目（发现了多少本、每本版次）
  python3 scripts/gen_catalog.py --save     # 抓目录并写 data/catalog.json

「2027 春更新下册」= 直接重跑 --save：discover() 每次实时抓站点最新书目，
下册新版 slug 一上线就会被自动发现覆盖，无需改代码。
"""
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import fetch_catalog as fc

OUT = Path(__file__).parent.parent / "data" / "catalog.json"

# 主课版本映射（已核对）：(学科名, 站点版本码, 站点科目码, 标题筛选词)
SUBJECTS = [
    ("语文", "rjb", "yuwen", "语文"),
    ("数学", "sjb", "shuxue", "数学"),
    ("英语", "yilin", "yingyu", "英语"),
    ("科学", "sjb", "kexue", "科学"),
    ("道法", "rjb", "zhengzhi", "道德与法治"),
]

GRADE_CN = "一二三四五六"

# 译林《英语》（一年级起点）。南通一、二年级用这一套，不是人教新起点，也不是沪教牛津。
YIQI_EN = {
    (1, "上"): [
        "Unit 1 I'm Liu Tao",
        "Unit 2 Good morning",
        "Unit 3 This is Miss Li",
        "Unit 4 Is this a teddy?",
        "Unit 5 A cherry, please",
        "Unit 6 Look at my balloon",
        "Unit 7 I can dance",
        "Unit 8 What can you do?",
    ],
    (1, "下"): [
        "Unit 1 Let's count!",
        "Unit 2 This is my pencil",
        "Unit 3 I like carrots",
        "Unit 4 Spring",
        "Unit 5 What's this?",
        "Unit 6 Are you ready?",
        "Unit 7 What's that?",
        "Unit 8 What's in your bag?",
    ],
    (2, "上"): [
        "Unit 1 She's my aunt",
        "Unit 2 I have a rabbit",
        "Unit 3 It has a short tail",
        "Unit 4 Autumn",
        "Unit 5 Have some juice, please!",
        "Unit 6 We like our school",
        "Unit 7 Let's clean up!",
        "Unit 8 My dad is a doctor",
    ],
    (2, "下"): [
        "Unit 1 Where's Kitty?",
        "Unit 2 Dinner is ready",
        "Unit 3 We all like PE",
        "Unit 4 I have big eyes",
        "Unit 5 Can you?",
        "Unit 6 Let's go shopping!",
        "Unit 7 Summer",
        "Unit 8 Don't push, please",
    ],
}


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read().decode("gb2312", "ignore")


def discover():
    """爬各科目录页，返回小学 1-6 年级书目列表。

    不同科目 slug 前缀不一致（xs5s/5s/5a），所以年级和上下册都从书名提取，
    slug 只用于去重和拼 URL。排除五四制（ws 前缀）与初中。
    """
    books = []
    for subject, ver, subj, kw in SUBJECTS:
        html = get(f"{fc.SITE}/books/{ver}/{subj}/")
        pairs = re.findall(
            r'href="(/books/[a-z]+/[a-z]+/([^/]+)/)"[^>]*title="([^"]+)"', html)
        seen = set()
        for path, slug, title in pairs:
            if slug in seen or slug.startswith("ws") or "五四制" in title:
                continue
            if kw not in title:
                continue
            m = re.search(r"([一二三四五六])年级", title)
            if not m:
                continue
            if "上册" in title:
                term = "上"
            elif "下册" in title:
                term = "下"
            else:
                continue
            seen.add(slug)
            year = re.search(r"(\d{4})\s*(?:秋|春)版", title)
            books.append({
                "subject": subject, "grade": GRADE_CN.index(m.group(1)) + 1,
                "term": term,
                "slug": slug, "path": path,
                "edition": "new" if year else "old",
                "year": int(year.group(1)) if year else None,
                "title": title,
            })
    # 译林国家课程是三年级起点。南通小学一年级就开英语，用的是译林《英语》（一年级起点 / 一起，2015 审定）。
    # 电子课本网没有 1A/1B/2A/2B 书页，目录按教材单元手补，--save 时不再去抓。
    have_en = {(b["grade"], b["term"]) for b in books if b["subject"] == "英语"}
    for (grade, term), chapters in YIQI_EN.items():
        if (grade, term) in have_en:
            continue
        sx = "s" if term == "上" else "x"
        books.append({
            "subject": "英语", "grade": grade, "term": term,
            "slug": f"yiqi{grade}{sx}", "path": "",
            "edition": "old", "year": None,
            "title": f"译林版英语（一年级起点）{GRADE_CN[grade-1]}年级{term}册",
            "chapters": list(chapters),
            "source": "manual-yiqi2015",
        })
    books.sort(key=lambda b: ([s[0] for s in SUBJECTS].index(b["subject"]), b["grade"], b["term"]))
    return books


def main():
    books = discover()
    if "--list" in sys.argv or len(sys.argv) == 1:
        for b in books:
            tag = f'{b["year"]}新' if b["edition"] == "new" else "旧版"
            print(f'{b["subject"]}{b["grade"]}年级{b["term"]}  [{tag}]  {b["slug"]}  {b["title"]}')
        print(f"\n共 {len(books)} 本")
        return
    # --save：逐本抓目录
    out = {"generated": datetime.now().isoformat(timespec="seconds"), "books": []}
    for b in books:
        if b.get("chapters"):
            note = "手补"
        else:
            note = ""
            try:
                b["chapters"] = fc.catalog(b["path"])["chapters"]
            except Exception as e:
                b["chapters"] = []
                b["error"] = repr(e)
        out["books"].append(b)
        extra = f"  {note}" if note else ""
        print(f'  {b["subject"]}{b["grade"]}{b["term"]}  {len(b["chapters"])}章{extra}', flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写 {OUT}，共 {len(books)} 本")


if __name__ == "__main__":
    main()