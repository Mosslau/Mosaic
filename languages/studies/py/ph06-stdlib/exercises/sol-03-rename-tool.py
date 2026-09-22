# exercises/sol-03-rename-tool.py —— 练习 3 参考实现：argparse 批量重命名工具
# 来源：06-stdlib.md 第 7 章「动手练习」练习 3
# 验证环境：Python 3.13.12
# 运行：python3 sol-03-rename-tool.py
# 验证状态：已验证

"""用 argparse 实现批量重命名工具：--dir/--ext/--prefix/--dry-run，自动生成 --help。"""

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


def main(argv: list[str] | None = None) -> int:
    """按参数批量重命名；--dry-run 只预览；返回处理文件数。"""
    args = build_parser().parse_args(argv)
    root = Path(args.dir)
    if not args.ext.startswith("."):
        args.ext = "." + args.ext
    renamed = 0
    for f in sorted(root.glob(f"*{args.ext}")):
        new_name = args.prefix + f.name
        print(f"{'[DRY-RUN] ' if args.dry_run else ''}{f.name} -> {new_name}")
        if not args.dry_run:
            f.rename(f.with_name(new_name))
        renamed += 1
    print(f"共处理 {renamed} 个文件（{'预览' if args.dry_run else '已改名'}）")
    return renamed


def demo() -> None:
    """在临时目录演示 dry-run 预览与实际改名。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name in ["a.log", "b.log", "c.txt"]:
            (root / name).write_text("", encoding="utf-8")
        main(["--dir", d, "--ext", ".log", "--prefix", "bak_", "--dry-run"])
        print("dry-run 后不变:", sorted(p.name for p in root.iterdir()))
        main(["--dir", d, "--ext", ".log", "--prefix", "bak_"])
        print("改名后:", sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        demo()
