# examples/ex04-rename-tool.py —— argparse 命令行工具：批量重命名（统一加前缀，支持 --dry-run）
# 来源：06-stdlib.md 第 6 章示例 4
# 验证环境：Python 3.13.12
# 运行：python3 ex04-rename-tool.py --help / python3 ex04-rename-tool.py
# 验证状态：已验证

"""用 argparse 构建批量重命名工具（--dir/--ext/--prefix/--dry-run）；无参数时在临时目录演示两种模式。"""

import argparse
import sys
import tempfile
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="批量重命名工具（统一加前缀）")
    parser.add_argument("--dir", default=".", help="目标目录（默认当前目录）")
    parser.add_argument("--ext", default=".log", help="要处理的扩展名（默认 .log）")
    parser.add_argument("--prefix", default="backup_", help="新文件名前缀")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不实际改名")
    return parser


def main(argv: list[str] | None = None) -> None:
    """按参数批量重命名；--dry-run 时只打印不改名。"""
    args = build_parser().parse_args(argv)
    root = Path(args.dir)
    if not args.ext.startswith("."):
        args.ext = "." + args.ext
    for f in sorted(root.glob(f"*{args.ext}")):
        new_name = args.prefix + f.name
        print(f"{'[DRY-RUN] ' if args.dry_run else ''}{f.name} -> {new_name}")
        if not args.dry_run:
            f.rename(f.with_name(new_name))


def demo() -> None:
    """在临时目录演示实际改名与 dry-run 两种模式。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name in ["a.log", "b.log", "c.txt"]:
            (root / name).write_text("", encoding="utf-8")
        main(["--dir", d, "--ext", ".log"])                       # 实际改名
        print("改名后:", sorted(p.name for p in root.iterdir()))
        main(["--dir", d, "--ext", ".log", "--prefix", "again_", "--dry-run"])
        print("dry-run 后不变:", sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        demo()
