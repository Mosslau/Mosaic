#!/usr/bin/env python3
# exercises/sol-02-excel-report.py —— 练习 2 参考实现：生成 Excel 报表（CSV → 多 Sheet xlsx）
# 验证环境：Python 3.13.9，openpyxl 3.1.5（pip install openpyxl）
# 运行：python3 sol-02-excel-report.py（离线可跑，已验证；xlsx 写入系统临时目录）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 + openpyxl 3.1.5 实际运行）：
#   CSV 输入 -> 12 行遥测数据（3 台设备 × 4 条）
#   工作簿 -> 2 个 Sheet：原始数据（13 行 × 4 列）、汇总（4 行 × 4 列）
#   汇总 -> EV-001: 4 条 平均速度 56.25 平均电量 85.0
#           EV-002: 4 条 平均速度 49.75 平均电量 89.5
#           EV-003: 4 条 平均速度 45.5  平均电量 73.25
#   重新打开核对 -> 单元格 C2 = 56.25（EV-001 平均速度）
import csv
import tempfile
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

TELEMETRY = [
    ("2026-09-01 08:00", "EV-001", 52, 88),
    ("2026-09-01 08:00", "EV-002", 48, 91),
    ("2026-09-01 08:00", "EV-003", 45, 76),
    ("2026-09-01 09:00", "EV-001", 58, 86),
    ("2026-09-01 09:00", "EV-002", 50, 90),
    ("2026-09-01 09:00", "EV-003", 47, 74),
    ("2026-09-01 10:00", "EV-001", 55, 84),
    ("2026-09-01 10:00", "EV-002", 52, 89),
    ("2026-09-01 10:00", "EV-003", 44, 72),
    ("2026-09-01 11:00", "EV-001", 60, 82),
    ("2026-09-01 11:00", "EV-002", 49, 88),
    ("2026-09-01 11:00", "EV-003", 46, 71),
]


def make_csv(work: Path) -> Path:
    """把遥测数据写成 CSV（模拟「从系统导出」的输入）。"""
    csv_path = work / "telemetry.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["时间", "设备", "速度", "电量"])
        writer.writerows(TELEMETRY)
    return csv_path


def summarize(rows: list[tuple]) -> list[tuple]:
    """按设备分组求 记录数 / 平均速度 / 平均电量。"""
    groups: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for _ts, device, speed, soc in rows:
        groups[device].append((speed, soc))
    result = []
    for device in sorted(groups):
        speeds = [s for s, _ in groups[device]]
        socs = [c for _, c in groups[device]]
        result.append((device, len(groups[device]),
                       round(sum(speeds) / len(speeds), 2),
                       round(sum(socs) / len(socs), 2)))
    return result


def build_workbook(rows: list[tuple], summary: list[tuple], out: Path) -> None:
    wb = Workbook()
    ws_raw = wb.active
    ws_raw.title = "原始数据"
    ws_raw.append(["时间", "设备", "速度", "电量"])
    for r in rows:
        ws_raw.append(r)

    ws_sum = wb.create_sheet("汇总")
    ws_sum.append(["设备", "记录数", "平均速度", "平均电量"])
    for s in summary:
        ws_sum.append(s)
    for sheet in (ws_raw, ws_sum):
        for cell in sheet[1]:  # 表头加粗 + 底色
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="D9E2F3")
    wb.save(out)


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph12-sol02-"))
    make_csv(work)  # 造 CSV 输入（模拟系统导出的原始数据）
    print("CSV 输入 ->", len(TELEMETRY), "行遥测数据（3 台设备 × 4 条）")

    summary = summarize(TELEMETRY)
    out = work / "telemetry-report.xlsx"
    build_workbook(TELEMETRY, summary, out)
    print("工作簿 -> 2 个 Sheet：原始数据（13 行 × 4 列）、汇总（4 行 × 4 列）")
    for device, n, avg_speed, avg_soc in summary:
        print("汇总 ->", device, ":", n, "条 平均速度", avg_speed, "平均电量", avg_soc)

    wb2 = load_workbook(out)  # 重新打开核对：数字可审计
    ws_sum = wb2["汇总"]
    print("重新打开核对 -> 单元格 C2 =", ws_sum["C2"].value, "（EV-001 平均速度）")
    print("文件 ->", out)


if __name__ == "__main__":
    main()
