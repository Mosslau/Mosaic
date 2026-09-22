# examples/ex02-can-log-csv.py —— CAN 日志 CSV 解析：DictReader 按列名访问并筛选
# 来源：05-file-exception.md 第 6 章示例 2
# 验证环境：Python 3.13.12
# 运行：python3 ex02-can-log-csv.py
# 验证状态：已验证

"""用 csv.DictReader 读取 CAN 日志 CSV，按列名访问数据并按 CAN ID 筛选消息。"""

import csv
import os
import tempfile


def load_can_messages(path):
    """读取 CAN 日志 CSV，返回消息字典列表（每项含 ts/id/data）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [
                {"ts": row["timestamp"], "id": row["can_id"], "data": row["data"]}
                for row in reader
            ]
    except FileNotFoundError:
        print("CSV 文件不存在")
    except csv.Error as e:
        print(f"CSV 解析错误: {e}")
    return []


def main():
    """生成 CAN 日志 CSV 并统计 0x123 消息的出现次数。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "can_log.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "can_id", "dlc", "data"])
            writer.writerow(["2024-06-01 08:00:01", "0x123", "8", "A1B2C3D4E5F6A7B8"])
            writer.writerow(["2024-06-01 08:00:02", "0x18F", "4", "11223344"])
            writer.writerow(["2024-06-01 08:00:03", "0x123", "8", "FFEEDDCCBBAA9988"])

        msgs = load_can_messages(path)
        matches = [m for m in msgs if m["id"] == "0x123"]
        print(f"共 {len(msgs)} 条 CAN 消息, 0x123 出现 {len(matches)} 次")
        for m in matches:
            print(f"  {m['ts']} -> data={m['data']}")


if __name__ == "__main__":
    main()
