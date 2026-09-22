# project/rename_tool.py —— ph06 阶段项目：批量重命名工具
# 来源：python.md ph06「推荐项目」第一个「批量重命名工具」
# 验证环境：Python 3.13.12
# 运行：python3 rename_tool.py --help / --selftest / --make-samples demo / rename_tool.py <目录>
# 验证状态：已验证

"""批量重命名工具：扩展名过滤 + 前缀/后缀 + 正则匹配 + 递归目录 + --dry-run + 统计报告。"""

import argparse
import logging
import re
import shutil
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("rename_tool")

SAMPLE_NAMES = [
    "can_2024-06-01.log",
    "can_2024-06-02.log",
    "diag_2024-06-01.log",
    "bms_2024-06-03.log",
    "bms_cell_01.log",
    "readme.txt",
]


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="批量重命名工具（前缀/后缀/正则匹配，支持 dry-run）")
    parser.add_argument("dir", nargs="?", default=".", help="目标目录（默认当前目录）")
    parser.add_argument("--ext", default=".log", help="只处理指定扩展名，如 .log（默认 .log）")
    parser.add_argument("--prefix", default="", help="新文件名前缀")
    parser.add_argument("--suffix", default="", help="新文件名后缀（插在扩展名前，如 _bak）")
    parser.add_argument("--pattern", default="", help="只处理文件名匹配该正则的文件（re.search）")
    parser.add_argument("--recursive", "-r", action="store_true", help="递归处理子目录")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不实际改名")
    parser.add_argument("--make-samples", metavar="DIR", help="在 DIR 生成样例文件后退出")
    parser.add_argument("--selftest", action="store_true", help="在临时目录运行自测后退出")
    return parser


def setup_logging() -> None:
    """配置 root logger：INFO 级别、带时间戳。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def make_sample_files(root: Path) -> None:
    """在 root 生成一批样例文件（含一个嵌套子目录），便于演示批量重命名。"""
    for name in SAMPLE_NAMES:
        (root / name).write_text(f"样例文件 {name}\n", encoding="utf-8")
    nested = root / "archive" / "2024-06-01"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "can_old_001.log").write_text("嵌套子目录样例\n", encoding="utf-8")
    print(f"已在 {root} 生成 {len(SAMPLE_NAMES) + 1} 个样例文件（含子目录）")


def normalize_ext(ext: str) -> str:
    """补全扩展名的 '.' 前缀；空串原样返回。"""
    if not ext:
        return ""
    return ext if ext.startswith(".") else "." + ext


def collect_files(root: Path, recursive: bool) -> list[Path]:
    """收集目录下全部文件（跳过目录），递归或非递归，按路径排序。"""
    iterator = root.rglob("*") if recursive else root.glob("*")
    return sorted(f for f in iterator if f.is_file())


def matches(f: Path, args: argparse.Namespace) -> bool:
    """判断文件是否应被处理：扩展名过滤 + 正则匹配文件名。"""
    if args.ext and f.suffix != normalize_ext(args.ext):
        return False
    if args.pattern and not re.search(args.pattern, f.name):
        return False
    return True


def build_target(f: Path, prefix: str, suffix: str) -> Path:
    """计算新文件名：prefix + stem + suffix + ext。"""
    return f.with_name(prefix + f.stem + suffix + f.suffix)


def run(args: argparse.Namespace) -> dict[str, int]:
    """执行批量重命名，返回统计 {planned, renamed, conflict, other}。"""
    stats = {"planned": 0, "renamed": 0, "conflict": 0, "other": 0}
    root = Path(args.dir)
    if not root.is_dir():
        logger.error("目录不存在: %s", root)
        raise SystemExit(1)
    for f in collect_files(root, args.recursive):
        if not matches(f, args):
            continue
        target = build_target(f, args.prefix, args.suffix)
        if target == f:
            stats["other"] += 1
            logger.info("跳过（新名与原文件名相同）: %s", f.name)
            continue
        if target.exists():
            stats["conflict"] += 1
            logger.warning("冲突跳过: %s -> %s（目标已存在）", f.name, target.name)
            continue
        stats["planned"] += 1
        if args.dry_run:
            logger.info("[DRY-RUN] %s -> %s", f.name, target.name)
            continue
        try:
            f.rename(target)                       # 同目录改名，通常原子
        except OSError:
            shutil.move(str(f), str(target))       # 兜底：跨设备等场景
        logger.info("%s -> %s", f.name, target.name)
        stats["renamed"] += 1
    return stats


def report(stats: dict[str, int], dry_run: bool) -> None:
    """打印统计报告。"""
    logger.info(
        "统计报告: 计划 %d 个, 已改名 %d 个, 冲突跳过 %d 个, 其他跳过 %d 个%s",
        stats["planned"],
        stats["renamed"],
        stats["conflict"],
        stats["other"],
        "（dry-run，未实际修改）" if dry_run else "",
    )


def selftest() -> None:
    """在临时目录运行完整流程并断言：dry-run 不改文件、实际改名、冲突跳过。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_sample_files(root)

        # 场景 1：dry-run 预览（递归），应计划 6 个 .log 且目录内容不变
        ns = argparse.Namespace(
            dir=d, ext=".log", prefix="bak_", suffix="",
            pattern="", recursive=True, dry_run=True,
        )
        stats = run(ns)
        assert stats["planned"] == 6, f"dry-run 应计划 6 个, 实际 {stats['planned']}"
        assert len(list(root.rglob("*.log"))) == 6, "dry-run 后 .log 数量不应变化"
        print(f"自测场景 1 通过: dry-run 计划 {stats['planned']} 个, 文件未变")

        # 场景 2：实际改名（递归），6 个 .log 全部加 bak_ 前缀
        ns.dry_run = False
        stats = run(ns)
        assert stats["renamed"] == 6, f"应改名 6 个, 实际 {stats['renamed']}"
        assert len(list(root.rglob("bak_*.log"))) == 6, "应有 6 个 bak_*.log"
        print(f"自测场景 2 通过: 改名 {stats['renamed']} 个, 全部带 bak_ 前缀")

        # 场景 3：冲突跳过 —— 先占用 bak_readme.txt，再处理 readme.txt 应冲突
        # 用正则 ^readme 只匹配 readme.txt，避免 bak_readme.txt 先被改名导致检测失效
        (root / "bak_readme.txt").write_text("occupied\n", encoding="utf-8")
        ns2 = argparse.Namespace(
            dir=d, ext=".txt", prefix="bak_", suffix="",
            pattern=r"^readme", recursive=False, dry_run=False,
        )
        stats2 = run(ns2)
        assert stats2["conflict"] == 1, f"应冲突 1 个, 实际 {stats2['conflict']}"
        assert stats2["renamed"] == 0, f"冲突文件不应改名, 实际改名 {stats2['renamed']}"
        print(f"自测场景 3 通过: 正则过滤匹配 1 个文件, 冲突跳过 {stats2['conflict']} 个, 未改名")

        print("自测全部通过")


def main() -> None:
    """解析参数并分发：--selftest / --make-samples / 正常执行。"""
    args = build_parser().parse_args()
    if args.selftest:
        selftest()
        return
    if args.make_samples:
        root = Path(args.make_samples)
        root.mkdir(parents=True, exist_ok=True)
        make_sample_files(root)
        return
    setup_logging()
    stats = run(args)
    report(stats, args.dry_run)


if __name__ == "__main__":
    main()
