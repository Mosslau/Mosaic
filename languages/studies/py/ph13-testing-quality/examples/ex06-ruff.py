#!/usr/bin/env python3
# examples/ex06-ruff.py —— ruff 配置 + 干净代码示例（主文档 3.6）
# 验证环境：Python 3.13.9 + ruff 0.12.0（本机已装并实测）；ruff 配置见同目录 pyproject.toml
# 运行：python3 ex06-ruff.py（离线可跑，已验证）
#      ruff check ex06-ruff.py（已验证：0 错误）
#      ruff format --check ex06-ruff.py（已验证：已格式化）
# 验证状态：已验证 —— ruff check 0 错误；ruff format --check 通过
import csv
import tempfile
from pathlib import Path


def merge_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """按 id 合并重复行：后面的字段覆盖前面的（演示常见数据处理）。"""
    merged: dict[str, dict[str, str]] = {}
    for r in rows:
        merged[r["id"]] = {**merged.get(r["id"], {}), **r}
    return list(merged.values())


def write_report(rows: list[dict[str, str]], out: Path) -> None:
    if not rows:
        raise ValueError("空数据不生成报表")
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph13-ruff-"))
    rows = [
        {"id": "EV-001", "speed": "42.0", "component": "88.0"},
        {"id": "EV-002", "speed": "30.0", "component": "91.0"},
        {"id": "EV-001", "component": "87.5"},  # 重复 id：合并时补上最新电量
    ]
    result = merge_rows(rows)
    report = work / "report.csv"
    write_report(result, report)
    print("合并后行数:", len(result))
    print("报表已写入:", report)
    print(report.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    main()
