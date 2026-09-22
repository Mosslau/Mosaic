# exercises/sol-05-upgrade-rename.py —— 练习 5 参考实现：批量重命名升级为 logging + argparse 版本
# 来源：06-stdlib.md 第 7 章「动手练习」练习 5（升级 ph05 的 examples/ex05-batch-rename.py）
# 验证环境：Python 3.13.12
# 运行：python3 sol-05-upgrade-rename.py
# 验证状态：已验证

"""把 ph05 的批量重命名示例升级为 logging + argparse 版本：print 换 logger，支持 --dry-run。"""

import argparse
import logging
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="批量重命名工具（logging + argparse 升级版）")
    parser.add_argument("--dir", default=".", help="目标目录（默认当前目录）")
    parser.add_argument("--old-ext", default=".log", help="旧扩展名（默认 .log）")
    parser.add_argument("--new-ext", default=".csv", help="新扩展名（默认 .csv）")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不实际改名")
    return parser


def normalize_ext(ext: str) -> str:
    """补全扩展名的 '.' 前缀，如 'log' -> '.log'。"""
    return ext if ext.startswith(".") else "." + ext


def main(argv: list[str] | None = None) -> int:
    """按参数批量替换扩展名；--dry-run 只写日志不改名；返回处理文件数。"""
    args = build_parser().parse_args(argv)
    root = Path(args.dir)
    old_ext = normalize_ext(args.old_ext)
    new_ext = normalize_ext(args.new_ext)
    renamed = 0
    for f in sorted(root.glob(f"*{old_ext}")):
        new_name = f.stem + new_ext
        logger.info("%s %s -> %s", "[DRY-RUN]" if args.dry_run else "", f.name, new_name)
        if not args.dry_run:
            f.rename(f.with_name(new_name))
        renamed += 1
    logger.info("共处理 %d 个文件（%s）", renamed, "预览" if args.dry_run else "已改名")
    return renamed


def setup_logging() -> None:
    """配置 root logger：INFO 级别、带时间戳。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def demo() -> None:
    """在临时目录演示 dry-run 预览与实际替换扩展名。"""
    setup_logging()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name in ["can_001.log", "can_002.log", "diag_003.log", "readme.txt"]:
            (root / name).write_text("", encoding="utf-8")
        main(["--dir", d, "--old-ext", ".log", "--new-ext", ".csv", "--dry-run"])
        print("dry-run 后 .log 数量不变:", len(list(root.glob("*.log"))))
        main(["--dir", d, "--old-ext", ".log", "--new-ext", ".csv"])
        csv_files = sorted(p.name for p in root.iterdir() if p.suffix == ".csv")
        print("改名后 .csv:", csv_files)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        setup_logging()
        main()
    else:
        demo()
