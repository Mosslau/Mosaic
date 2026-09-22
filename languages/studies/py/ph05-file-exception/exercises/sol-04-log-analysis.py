# exercises/sol-04-log-analysis.py —— 练习 4 参考实现：日志分析（正则统计 ERROR 部件频率 Top-3）
# 来源：05-file-exception.md 第 7 章「动手练习」练习 4
# 验证环境：Python 3.13.12
# 运行：python3 sol-04-log-analysis.py
# 验证状态：已验证

"""正则提取日志中的 ERROR 行，按部件统计故障频率并输出 Top-3。"""

import os
import re
import tempfile
from collections import Counter

# 日志行格式：2024-06-01 08:00:10 ERROR SVC-001 内存水位异常 0.15V
ERROR_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+ERROR\s+([A-Z]+-\d+)"
    r"\s+(.+)"
)


def count_error_components(path):
    """统计各部件 ERROR 次数，无法匹配的行忽略，返回 Counter。"""
    counter = Counter()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = ERROR_PATTERN.match(line)
                if m:
                    counter[m.group(2)] += 1
    except FileNotFoundError:
        print("日志文件不存在")
    return counter


def main():
    """生成含 ERROR/INFO 混排的日志，输出 ERROR 部件频率 Top-3。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "diag.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("2024-06-01 08:00:01 INFO  SVC-001 CPU 温度正常 32C\n")
            f.write("2024-06-01 08:00:05 ERROR SVC-001 内存水位异常 0.15V\n")
            f.write("2024-06-01 08:00:10 ERROR NODE-003 网络限流触发 320MB/s\n")
            f.write("2024-06-01 08:00:15 ERROR NODE-003 网络限流再次触发\n")
            f.write("2024-06-01 08:00:20 ERROR NODE-002 通信超时\n")
            f.write("2024-06-01 08:00:25 ERROR SVC-001 内存水位异常 0.18V\n")
            f.write("2024-06-01 08:00:30 ERROR NODE-003 网络限流三次触发\n")
            f.write("malformed line without level\n")  # 非法行：忽略不崩溃

        stats = count_error_components(path)
        print("ERROR 故障频率 Top-3:")
        for comp, count in stats.most_common(3):
            print(f"  {comp}: {count} 次")


if __name__ == "__main__":
    main()
