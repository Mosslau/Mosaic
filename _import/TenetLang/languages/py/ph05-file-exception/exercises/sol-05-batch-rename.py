# exercises/sol-05-batch-rename.py —— 练习 5 参考实现：批量重命名（扩展名修改 + dry-run + 冲突检测）
# 来源：05-file-exception.md 第 7 章「动手练习」练习 5
# 验证环境：Python 3.13.12
# 运行：python3 sol-05-batch-rename.py
# 验证状态：已验证

"""批量修改文件扩展名：dry-run 预览、实际执行、冲突抛自定义异常并保留根因。"""

import os
import tempfile


class BatchRenameError(Exception):
    """批量重命名异常，携带失败文件路径和原因。"""

    def __init__(self, path, reason):
        self.path = path
        self.reason = reason
        super().__init__(f"重命名失败: {os.path.basename(path)} - {reason}")


def batch_rename_ext(dir_path, old_ext, new_ext, dry_run=True):
    """批量修改扩展名。dry_run=True 只预览；目标已存在时抛 BatchRenameError。"""
    if not old_ext.startswith("."):
        old_ext = "." + old_ext
    if not new_ext.startswith("."):
        new_ext = "." + new_ext
    renamed = 0
    for fname in os.listdir(dir_path):
        if not fname.endswith(old_ext):
            continue
        old_path = os.path.join(dir_path, fname)
        new_path = os.path.join(dir_path, fname[: -len(old_ext)] + new_ext)
        if os.path.exists(new_path):
            raise BatchRenameError(fname, f"目标文件已存在: {new_path}")
        try:
            if not dry_run:
                os.rename(old_path, new_path)
            renamed += 1
            print(
                f"{'[DRY RUN] ' if dry_run else ''}{fname} -> "
                f"{os.path.basename(new_path)}"
            )
        except OSError as e:
            raise BatchRenameError(fname, str(e)) from e
    return renamed


def main():
    """演示 dry-run、实际执行、冲突抛异常三条路径。"""
    with tempfile.TemporaryDirectory() as d:
        for name in ["a.log", "b.log"]:
            path = os.path.join(d, name)
            with open(path, "w", encoding="utf-8"):
                pass

        print("--- 1. dry-run 预览 ---")
        count = batch_rename_ext(d, ".log", ".csv", dry_run=True)
        logs_left = len([n for n in os.listdir(d) if n.endswith(".log")])
        print(f"预览 {count} 个, 仍存在 {logs_left} 个 .log 文件（未实际修改）")

        print("--- 2. 实际执行 ---")
        count = batch_rename_ext(d, ".log", ".csv", dry_run=False)
        csv_files = [n for n in os.listdir(d) if n.endswith(".csv")]
        print(f"实际重命名 {count} 个, 现目录共 {len(csv_files)} 个 .csv 文件")

        print("--- 3. 冲突检测 ---")
        with open(os.path.join(d, "c.log"), "w", encoding="utf-8"):
            pass
        with open(os.path.join(d, "c.csv"), "w", encoding="utf-8"):
            pass  # 预先创建目标文件制造冲突
        try:
            batch_rename_ext(d, ".log", ".csv", dry_run=False)
        except BatchRenameError as e:
            print(f"捕获异常: {e}")


if __name__ == "__main__":
    main()
