# exercises/sol-02-extract-log.py —— 练习 2 参考实现：正则提取日志字段并统计错误码分布
# 来源：06-stdlib.md 第 7 章「动手练习」练习 2
# 验证环境：Python 3.13.12
# 运行：python3 sol-02-extract-log.py
# 验证状态：已验证

"""用 re.findall + 命名分组提取日志的时间/IP/错误码，用 Counter 统计错误码分布；非法行忽略。"""

import re
import tempfile
from collections import Counter
from pathlib import Path

LOG_PATTERN = re.compile(
    r"(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"   # 时间
    r"\s+(?P<level>\w+)"                                # 级别
    r"\s+(?P<ip>\d+\.\d+\.\d+\.\d+)"                    # IP
    r"\s+(?P<code>E\d+)"                                # 错误码
)


def analyze_log(path: Path) -> list[tuple[str, int]]:
    """解析日志，返回错误码按次数降序的分布；非法行自动忽略。"""
    rows = LOG_PATTERN.findall(path.read_text(encoding="utf-8"))
    distribution = Counter(row[3] for row in rows).most_common()
    for t, level, ip, code in rows:
        print(f"{t} [{level}] {ip} {code}")
    return distribution


def main() -> None:
    """生成含非法行的样例日志并演示提取与统计。"""
    with tempfile.TemporaryDirectory() as d:
        log_path = Path(d) / "vehicle.log"
        log_path.write_text(
            "2024-06-01 08:00:01 ERROR 192.168.1.10 E1001 电芯压差异常\n"
            "2024-06-01 08:00:05 WARN  10.0.0.5   E2003 电机温度偏高\n"
            "这条是非法行, 应被忽略\n"
            "2024-06-01 08:00:10 ERROR 192.168.1.11 E1002 BMS 通讯超时\n"
            "2024-06-01 08:00:15 WARN  192.168.1.10 E2003 电机温度偏高\n"
            "2024-06-01 08:00:20 ERROR 10.0.0.5   E1001 电芯压差异常\n",
            encoding="utf-8",
        )
        distribution = analyze_log(log_path)
        print("错误码分布（降序）:", distribution)


if __name__ == "__main__":
    main()
