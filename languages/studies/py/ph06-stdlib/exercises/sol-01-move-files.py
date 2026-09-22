# exercises/sol-01-move-files.py —— 练习 1 参考实现：批量移动文件（按日期归档，支持 dry-run）
# 来源：06-stdlib.md 第 7 章「动手练习」练习 1
# 验证环境：Python 3.13.12
# 运行：python3 sol-01-move-files.py
# 验证状态：已验证

"""用 pathlib 把散落的日志按文件名中的日期归档到 archive/YYYY-MM-DD/，支持 dry-run 预览。"""

import re
import tempfile
from pathlib import Path

DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def move_logs_by_date(root: Path, dry_run: bool = True) -> int:
    """把 root 下文件名含日期的日志归档到 archive/YYYY-MM-DD/；dry_run=True 只预览不移动。"""
    moved = 0
    for f in sorted(root.glob("*.log")):             # glob 遍历 *.log
        m = DATE_PATTERN.search(f.stem)              # 无日期则跳过
        if not m:
            continue
        target_dir = root / "archive" / m.group(1)
        target = target_dir / f.name
        if dry_run:
            print(f"[DRY-RUN] {f.name} -> {target.relative_to(root)}")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            f.rename(target)
            print(f"{f.name} -> {target.relative_to(root)}")
        moved += 1
    return moved


def main() -> None:
    """在临时目录演示 dry-run 预览与实际移动。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name in ["can_2024-06-01.log", "can_2024-06-02.log",
                     "diag_2024-06-01.log", "bms_2024-06-03.log", "readme.txt"]:
            (root / name).write_text("", encoding="utf-8")

        n = move_logs_by_date(root, dry_run=True)
        remaining = len(list(root.glob("*.log")))
        print(f"预览将移动 {n} 个文件；根目录仍有 {remaining} 个 .log（未实际移动）")

        n = move_logs_by_date(root, dry_run=False)
        archived = len(list((root / "archive").rglob("*.log")))
        print(f"实际移动 {n} 个文件；archive 下现有 {archived} 个 .log")


if __name__ == "__main__":
    main()
