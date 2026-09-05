# -*- coding: utf-8 -*-
"""从电子课本网(dzkbw.com)抓取某本教材的「目录」，转成结构化 JSON。

用法：
  python3 scripts/fetch_catalog.py "/books/rjb/yuwen/xs5s_2026/"      # 输出 JSON
  python3 scripts/fetch_catalog.py http://www.dzkbw.com/books/sjb/shuxue/xs5s_2026/

目录抽自每页右侧 <div class="mululist"> 的章节链接（站点 HTML 是 gb2312 编码）。
只抓目录（单元/章名），不抓课文正文；正文还是以「基本智慧教育平台」官方为准。
"""
import json
import re
import sys
import urllib.request

SITE = "http://www.dzkbw.com"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read().decode("gb2312", "ignore")


def norm_path(p: str) -> str:
    if p.startswith("http"):
        return p.rstrip("/") + "/001.htm"
    return (SITE + p if not p.startswith("/") else SITE + p).rstrip("/") + "/001.htm"


def parse_chapters(html: str):
    """返回目录章节名列表。

    不按 <div class="mululist"> 截取（里面会插广告 div 提前截断），
    而是全局匹配所有指向本书页面的章节链接，按 href 去重、过滤封面页。
    """
    seen, chapters = set(), []
    for href, text in re.findall(
        r'<a[^>]+href="(/books/[a-z]+/[a-z]+/[0-9a-z_]+/\d+\.htm)"[^>]*>(.*?)</a>',
        html, re.S):
        if href in seen:
            continue
        seen.add(href)
        text = re.sub(r"<[^>]+>", "", text)            # 去 span 等内层标签
        text = text.replace("&nbsp;", " ").replace("\xa0", " ").strip()
        if not text or "封面" in text or "前言" in text or "目录" in text:
            continue
        chapters.append(text)
    return chapters


def catalog(path: str) -> dict:
    url = norm_path(path)
    html = fetch(url)
    m = re.search(r'<h1>([^<]+)</h1>', html)
    page_title = m.group(1).strip() if m else ""
    chapters = parse_chapters(html)
    return {"source": url, "title": page_title or "未知", "chapters": chapters}


def demo():
    """自检：苏教版数学五年级上册(2026秋版)。目录第一单元应是「一 图形的运动」。"""
    path = "/books/sjb/shuxue/xs5s_2026/"
    out = catalog(path)
    assert out["chapters"][:2] == ["一 图形的运动", "☆ 图案的还原"], out["chapters"][:5]
    print("OK 目录前 3 章:", out["chapters"][:3])
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    elif len(sys.argv) > 1:
        print(json.dumps(catalog(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        print("用法: fetch_catalog.py <书本路径或URL>  或  fetch_catalog.py demo")