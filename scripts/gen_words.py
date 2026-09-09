# -*- coding: utf-8 -*-
"""校验 data/words.seed.multi.json，并写出人工核对表。

词表只维护 JSON；本脚本不从网页抓词。对照实物教材后改 JSON，再跑一遍。
输出：data/words_review.md
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
SEED = DATA / "words.seed.multi.json"
REVIEW = DATA / "words_review.md"


def normalize_word(raw: str) -> str:
    return " ".join((raw or "").strip().replace("’", "'").replace("‘", "'").lower().split())


def main():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    books = data.get("books") or []
    if not books:
        raise SystemExit("words.seed.multi.json 没有 books")
    lines = [
        "# 单词词书核对表",
        "",
        f"> curriculum_ver: `{data.get('curriculum_ver', '')}`",
        "> 系统词书只允许改 JSON 后重新入库；家长不可改。页码空着的条目仍需对照 2026 秋译林 5A Word lists。",
        "",
    ]
    errors = []
    for b in books:
        words = b.get("words") or []
        src = b.get("source") or {}
        lines += [
            f"## {b.get('name')} (`{b.get('id')}`)",
            "",
            f"- unit_id: `{b.get('unit_id')}` · term: `{b.get('term_id')}` · 词数: {len(words)}",
            f"- 来源: {src.get('note', '')}",
            f"- 待实物核对: {'是' if src.get('needs_spot_check') else '否'}",
            "",
            "| # | 单词 | 中文 | 音标 | 分组 | 页码 |",
            "|---|---|---|---|---|---|",
        ]
        seen = set()
        if not (20 <= len(words) <= 30) and b.get("id") == "g5s1-en-1":
            errors.append(f"{b['id']} 试点词数应在 20–30，当前 {len(words)}")
        for i, w in enumerate(words, 1):
            word = (w.get("word") or "").strip()
            cn = (w.get("cn") or "").strip()
            if not word or not cn:
                errors.append(f"{b.get('id')} 第 {i} 行缺 word/cn")
            norm = normalize_word(word)
            if norm in seen:
                errors.append(f"{b.get('id')} 重复词 {word}")
            seen.add(norm)
            if len(word) > 60 or len(cn) > 120:
                errors.append(f"{b.get('id')} 第 {i} 行超长")
            page = w.get("page") or src.get("pages") or ""
            lines.append(
                f"| {w.get('sort', i)} | {word} | {cn} | {w.get('ipa', '')} | {w.get('group', '')} | {page} |"
            )
        lines.append("")
    REVIEW.write_text("\n".join(lines), encoding="utf-8")
    if errors:
        print("words seed 有问题：", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        raise SystemExit(1)
    print("ok", SEED.name, "books", len(books), "review", REVIEW.name)


if __name__ == "__main__":
    main()
