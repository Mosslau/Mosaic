# examples/ex02-extract-log-fields.py —— 正则提取日志字段（时间/IP/错误码）并统计分布
# 来源：06-stdlib.md 第 6 章示例 2
# 验证环境：Python 3.13.12
# 运行：python3 ex02-extract-log-fields.py
# 验证状态：已验证

"""用 re.findall + 命名分组提取日志中的时间/级别/IP/错误码，用 Counter 统计错误码分布。"""

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


def analyze_log(path: Path) -> list[tuple[str, str, str, str]]:
    """解析日志文件，返回 (time, level, ip, code) 元组列表，并打印错误码分布。"""
    rows = LOG_PATTERN.findall(path.read_text(encoding="utf-8"))
    code_count = Counter(row[3] for row in rows)
    print("错误码分布:", dict(code_count))
    for t, level, ip, code in rows:
        print(f"{t} [{level}] {ip} {code}")
    return rows


def main() -> None:
    """生成样例日志并执行提取演示。"""
    with tempfile.TemporaryDirectory() as d:
        log_path = Path(d) / "vehicle.log"
        log_path.write_text(
            "2024-06-01 08:00:01 ERROR 192.168.1.10 E1001 电芯压差异常\n"
            "2024-06-01 08:00:05 WARN  10.0.0.5   E2003 电机温度偏高\n"
            "2024-06-01 08:00:10 ERROR 192.168.1.11 E1002 BMS 通讯超时\n"
            "2024-06-01 08:00:15 WARN  192.168.1.10 E2003 电机温度偏高\n"
            "2024-06-01 08:00:20 ERROR 10.0.0.5   E1001 电芯压差异常\n",
            encoding="utf-8",
        )
        analyze_log(log_path)


if __name__ == "__main__":
    main()
