# examples/ex01-organize-files.py —— pathlib 批量整理文件：按日期归档 + 统一前缀
# 来源：06-stdlib.md 第 6 章示例 1
# 验证环境：Python 3.13.12
# 运行：python3 ex01-organize-files.py
# 验证状态：已验证

"""用 pathlib 把散落的日志文件按文件名中的日期归档到 archive/YYYY-MM-DD/ 并统一加 backup_ 前缀。"""

import re
import tempfile
from pathlib import Path


def organize_logs(root: Path) -> None:
    """把 root 下的 *.log 按文件名中的日期归档到 archive/YYYY-MM-DD/，统一加 backup_ 前缀。"""
    for f in root.glob("*.log"):                 # glob 遍历 *.log
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if not m:
            continue
        target_dir = root / "archive" / m.group(1)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"backup_{f.name}"
        f.rename(target)                         # 移动 + 重命名一步完成
        print(f"{f.name} -> {target.relative_to(root)}")


def main() -> None:
    """在临时目录生成样例日志并执行归档演示。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name in ["can_2024-06-01.log", "can_2024-06-02.log",
                     "diag_2024-06-01.log", "bms_2024-06-03.log", "readme.txt"]:
            (root / name).write_text("", encoding="utf-8")

        organize_logs(root)


if __name__ == "__main__":
    main()
