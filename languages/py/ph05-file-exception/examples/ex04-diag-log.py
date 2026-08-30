# examples/ex04-diag-log.py —— 诊断日志分析：正则逐行解析 + 级别/部件统计
# 来源：05-file-exception.md 第 6 章示例 4
# 验证环境：Python 3.13.12
# 运行：python3 ex04-diag-log.py
# 验证状态：已验证

"""用正则逐行解析车联网诊断日志，统计日志级别与部件告警/错误次数。"""

import os
import re
import tempfile
from collections import Counter

# 日志行格式：2024-06-01 08:00:01 INFO  BMS-001 电池温度正常 32C
LINE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+(INFO|WARN|ERROR)"
    r"\s+([A-Z]+-\d+)"
    r"\s+(.+)"
)


def analyze_log(path):
    """逐行解析日志，返回 (级别统计, 部件告警/错误统计)。"""
    level_count = Counter()
    comp_errors = Counter()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = LINE_PATTERN.match(line)
                if m:
                    level, comp = m.group(2), m.group(3)
                    level_count[level] += 1
                    if level in ("ERROR", "WARN"):
                        comp_errors[comp] += 1
    except FileNotFoundError:
        print("日志文件不存在")
    return level_count, comp_errors


def main():
    """生成样例诊断日志并输出分析结果。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "diag.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("2024-06-01 08:00:01 INFO  BMS-001 电池温度正常 32C\n")
            f.write("2024-06-01 08:00:05 WARN  MCU-003 电机温度偏高 85C\n")
            f.write("2024-06-01 08:00:10 ERROR BMS-001 电芯压差异常 0.15V\n")
            f.write("2024-06-01 08:00:15 INFO  VCU-002 车速 60km/h\n")
            f.write("2024-06-01 08:00:20 ERROR MCU-003 过流保护触发 320A\n")

        level_count, comp_errors = analyze_log(path)
        print(f"日志级别统计: {dict(level_count)}")
        print(f"部件告警/错误次数: {dict(comp_errors)}")
        if comp_errors:
            worst = comp_errors.most_common(1)[0]
            print(f"最需关注部件: {worst[0]} (共 {worst[1]} 次)")


if __name__ == "__main__":
    main()
