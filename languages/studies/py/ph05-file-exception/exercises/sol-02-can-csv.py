# exercises/sol-02-can-csv.py —— 练习 2 参考实现：解析 CSV（统计各 BUS ID 出现次数）
# 来源：05-file-exception.md 第 7 章「动手练习」练习 2
# 验证环境：Python 3.13.12
# 运行：python3 sol-02-can-csv.py
# 验证状态：已验证

"""统计 BUS 日志 CSV 中各 BUS ID 的出现次数，按次数降序输出。"""

import csv
import os
import tempfile
from collections import Counter


def count_bus_ids(path):
    """统计每个 BUS ID 出现次数，返回 Counter。"""
    counter = Counter()
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                counter[row["bus_id"]] += 1
    except FileNotFoundError:
        print("CSV 文件不存在")
    except csv.Error as e:
        print(f"CSV 解析错误: {e}")
    return counter


def main():
    """生成样例 BUS 日志 CSV 并输出降序统计。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bus_log.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "bus_id", "dlc", "data"])
            writer.writerow(["2024-06-01 08:00:01", "0x123", "8", "A1B2C3D4"])
            writer.writerow(["2024-06-01 08:00:02", "0x18F", "4", "11223344"])
            writer.writerow(["2024-06-01 08:00:03", "0x123", "8", "55667788"])
            writer.writerow(["2024-06-01 08:00:04", "0x123", "8", "99AABBCC"])
            writer.writerow(["2024-06-01 08:00:05", "0x2A1", "2", "0001"])

        stats = count_bus_ids(path)
        print("BUS ID 出现次数（降序）:")
        for bus_id, count in stats.most_common():
            print(f"  {bus_id}: {count} 次")


if __name__ == "__main__":
    main()
