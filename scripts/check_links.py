#!/usr/bin/env python3
"""Markdown 断链与索引覆盖检查（roadmap 域）。

用法（仓库根执行）：
    python3 scripts/check_links.py                # 默认检查 roadmap/
    python3 scripts/check_links.py roadmap        # 指定目录（可多个）

检查两件事：
1. **断链**：正文里的相对链接/图片必须指向存在的文件或目录；
   跳过 http(s)/mailto、纯锚点（#...）、代码块与行内代码里的内容。
2. **索引覆盖**：目录下每个 .md（README.md 除外）都必须能从该目录的
   README.md 直接链接到——文件存在但没进索引，等同于读者找不到。

退出码：0 = 无问题；1 = 存在断链或未索引文档。

为什么单独一个脚本：`.dsh/skills/tenetlang-notes` 只管辖 languages/studies，
`mindspring-lab` 只管辖 algorithms/，roadmap/ 原先不在任何校验器范围内，
移动/改名文件后索引断链不会被 verify.sh 发现。本脚本补上这个盲区，
只依赖标准库，无第三方依赖。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

# [text](target) 与 ![alt](target)；target 允许被 <> 包裹
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")

DEFAULT_ROOTS = ["roadmap"]


def is_markdown_link_target(target: str) -> bool:
    if not target:
        return False
    if target.startswith("#"):
        return False
    return not SCHEME_RE.match(target)


def normalize(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    # 去掉锚点与查询串，只校验路径部分
    return unquote(target.split("#", 1)[0].split("?", 1)[0])


def iter_links(text: str):
    """逐行产出 (行号, 链接目标)，跳过围栏代码块与行内代码。"""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        cleaned = INLINE_CODE_RE.sub("", line)
        for match in LINK_RE.finditer(cleaned):
            yield lineno, match.group(1)


def check_links(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for lineno, raw in iter_links(text):
            if not is_markdown_link_target(raw):
                continue
            target = normalize(raw)
            if not target:
                continue
            dest = (path.parent / target).resolve()
            if not dest.exists():
                errors.append(f"{path}:{lineno}: 链接目标不存在 -> {raw}")

    # 索引覆盖：目录 README 必须直接链接到该目录下所有 md（README 自身除外）
    readme = root / "README.md"
    if not readme.is_file():
        errors.append(f"{root}: 缺少 README.md（无法建立索引）")
        return errors
    indexed = {
        (readme.parent / normalize(raw)).resolve()
        for _, raw in iter_links(readme.read_text(encoding="utf-8"))
        if is_markdown_link_target(raw) and normalize(raw)
    }
    for path in files:
        if path.name == "README.md":
            continue
        if path.resolve() not in indexed:
            errors.append(f"{path}: 未被索引（{readme.relative_to(root.parent)} 中没有直接链接）")
    return errors


def main(argv: list[str]) -> int:
    cwd = Path.cwd()
    targets = argv or DEFAULT_ROOTS
    failed = False
    for name in targets:
        root = (cwd / name).resolve()
        if not root.is_dir():
            print(f"[check] 目录不存在：{root}", file=sys.stderr)
            failed = True
            continue
        files = sorted(p for p in root.rglob("*.md") if p.is_file())
        if not files:
            print(f"[check] {root}: 没有 .md 文件，跳过")
            continue
        errors = check_links(root, files)
        status = "✅" if not errors else "❌"
        print(f"[check] {root.relative_to(cwd) if root.is_relative_to(cwd) else root}: "
              f"{status} {len(files)} 篇、{len(errors)} 个问题")
        for err in errors:
            print(f"  - {err}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
