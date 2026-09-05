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
    ("英语", "sjb", "yingyu", "英语"),
    ("科学", "sjb", "kexue", "科学"),
    ("道法", "bbb", "zhengzhi", "道德与法治"),
]

GRADE_CN = "一二三四五六"


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
        try:
            b["chapters"] = fc.catalog(b["path"])["chapters"]
        except Exception as e:
            b["chapters"] = []
            b["error"] = repr(e)
        out["books"].append(b)
        print(f'  {b["subject"]}{b["grade"]}{b["term"]}  {len(b["chapters"])}章', flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写 {OUT}，共 {len(books)} 本")


if __name__ == "__main__":
    main()