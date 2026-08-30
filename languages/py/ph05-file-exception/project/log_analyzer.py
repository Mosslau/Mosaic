# project/log_analyzer.py —— 日志分析工具：读日志、统计级别/时间分布/错误 Top-N、输出报告
# 来源：roadmap python.md ph05「推荐项目」第一个「日志分析工具」；05-file-exception.md 第 7 章「阶段项目」
# 验证环境：Python 3.13.12（仅标准库）
# 运行：
#   python3 log_analyzer.py sample_logs.log
#   python3 log_analyzer.py sample_logs.log --top 5 -o report.txt --csv level_stats.csv
# 验证状态：已验证

"""车联网诊断日志分析工具。

读取诊断日志文件，逐行用正则解析出时间戳、级别、部件、消息；
统计日志级别分布、按小时的时间分布、按部件的 ERROR Top-N，
生成文本分析报告（stdout 或 -o 写文件），可选导出「部件 × 级别」交叉表 CSV。
"""

import csv
import os
import re
import sys
from collections import Counter

# 日志行格式：2024-06-01 08:00:01 INFO  BMS-001 电池温度正常 32C
LINE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"  # 时间戳
    r"\s+(INFO|WARN|ERROR)"                   # 级别
    r"\s+([A-Z]+-\d+)"                        # 部件
    r"\s+(.+)"                                # 消息
)
LEVELS = ("INFO", "WARN", "ERROR")


class LogParseError(Exception):
    """日志文件异常：文件缺失或读取失败时抛出，保留根因。"""


def parse_log(path):
    """逐行解析日志，返回记录列表，每条为 dict(ts/hour/level/component/message)。"""
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = LINE_PATTERN.match(line)
                if not m:
                    continue  # 非日志行（注释/空行/表头）自动跳过
                ts = m.group(1)
                records.append(
                    {
                        "ts": ts,
                        "hour": ts[11:13],  # 取 HH 用于时间分布
                        "level": m.group(2),
                        "component": m.group(3),
                        "message": m.group(4),
                    }
                )
    except FileNotFoundError as e:
        raise LogParseError(f"日志文件不存在: {path}") from e
    except OSError as e:
        raise LogParseError(f"读取日志失败: {path}") from e
    return records


def analyze(records):
    """汇总统计，返回 (级别分布, 时间分布, 部件x级别交叉表)。"""
    level_count = Counter(r["level"] for r in records)
    hour_count = Counter(r["hour"] for r in records)
    component_level = Counter((r["component"], r["level"]) for r in records)
    return level_count, hour_count, component_level


def error_top(records, n):
    """按部件统计 ERROR 次数，返回降序前 n 名。"""
    error_counter = Counter(
        r["component"] for r in records if r["level"] == "ERROR"
    )
    return error_counter.most_common(n)


def build_report(path, records, level_count, hour_count, component_level, top_n):
    """生成文本报告字符串。"""
    lines = []
    lines.append("=" * 46)
    lines.append("车联网诊断日志分析报告")
    lines.append("=" * 46)
    lines.append(f"日志文件: {path}")
    lines.append(f"有效记录: {len(records)} 条")
    lines.append("")
    lines.append("[1] 日志级别分布")
    for level in LEVELS:
        lines.append(f"  {level:<5} {level_count.get(level, 0)}")
    lines.append("")
    lines.append("[2] 时间分布（按小时）")
    for hour in sorted(hour_count):
        lines.append(f"  {hour}:00  {hour_count[hour]} 条")
    lines.append("")
    lines.append(f"[3] ERROR Top-{top_n}（按部件）")
    if not component_level:
        lines.append("  （无 ERROR 记录）")
    else:
        for comp, count in error_top(records, top_n):
            lines.append(f"  {comp}  {count} 次")
    lines.append("")
    lines.append("[4] 部件 x 级别交叉表")
    components = sorted({comp for comp, _ in component_level})
    lines.append("  " + "".join(f"{lvl:<6}" for lvl in LEVELS) + "  部件")
    for comp in components:
        row = "  " + "".join(
            f"{component_level.get((comp, lvl), 0):<6}" for lvl in LEVELS
        )
        lines.append(row + f"  {comp}")
    return "\n".join(lines) + "\n"


def export_csv(path, component_level):
    """把部件 x 级别交叉表写入 CSV（含 total 列）。"""
    components = sorted({comp for comp, _ in component_level})
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["component", "INFO", "WARN", "ERROR", "total"])
            for comp in components:
                info = component_level.get((comp, "INFO"), 0)
                warn = component_level.get((comp, "WARN"), 0)
                err = component_level.get((comp, "ERROR"), 0)
                writer.writerow([comp, info, warn, err, info + warn + err])
        print(f"交叉表已导出: {path}")
    except OSError as e:
        print(f"导出 CSV 失败: {e}")


def main(argv):
    """解析命令行参数（--top / -o / --csv），输出报告，返回退出码。"""
    if not argv:
        print("用法: python3 log_analyzer.py <日志文件> [--top N] [-o 报告文件] [--csv 交叉表.csv]")
        return 2

    path = argv[0]
    top_n, report_path, csv_path = 5, None, None
    i = 1
    while i < len(argv):
        if argv[i] == "--top" and i + 1 < len(argv):
            try:
                top_n = int(argv[i + 1])
            except ValueError:
                print(f"参数错误: --top 需要整数, 得到 {argv[i + 1]!r}")
                return 2
            i += 2
        elif argv[i] == "-o" and i + 1 < len(argv):
            report_path = argv[i + 1]
            i += 2
        elif argv[i] == "--csv" and i + 1 < len(argv):
            csv_path = argv[i + 1]
            i += 2
        else:
            print(f"未知参数: {argv[i]}")
            return 2

    try:
        records = parse_log(path)
    except LogParseError as e:
        print(e)
        return 1

    level_count, hour_count, component_level = analyze(records)
    report = build_report(path, records, level_count, hour_count, component_level, top_n)
    print(report, end="")

    if report_path:
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"报告已写入: {report_path}")
        except OSError as e:
            print(f"写报告失败: {e}")
            return 1
    if csv_path:
        export_csv(csv_path, component_level)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
