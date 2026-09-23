#!/usr/bin/env python3
# exercises/sol-04-bus-log.py —— 练习 4 参考实现：解析 BUS 日志（candump 格式 + 统计 + CSV）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 sol-04-bus-log.py（离线可跑，已验证；样本与 CSV 报表在系统临时目录）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 实际运行）：
#   解析 -> 有效帧 12 条、无效行 1 条
#   按 ID 统计 -> 0x123 运行速度: 6 条 [30, 60] avg 44.67
#                 0x245 部件电压: 3 条 [95, 112] avg 102.33
#                 0x301 电机温度: 3 条 [90, 110] avg 100.0
#   过滤 0x123 -> 6 条
#   CSV 报表 -> bus_report.csv 4 行（含表头）
import csv
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

# candump 风格日志：(秒.微秒) 接口 ID#负载HEX
FRAME_RE = re.compile(r"^\((\d+\.\d+)\) (\S+) ([0-9A-Fa-f]+)#([0-9A-Fa-f]*)$")

# 设备信号映射：0x123 运行速度、0x245 部件电压、0x301 电机温度（首字节即信号值）
SIGNALS = {0x123: "运行速度", 0x245: "部件电压", 0x301: "电机温度"}

SAMPLE = [
    "(1629946800.123456) can0 123#1E00000000000000",
    "(1629946800.200000) can0 123#2800000000000000",
    "(1629946800.350000) can0 245#6480000000000000",
    "(1629946801.050000) can0 123#3400000000000000",
    "(1629946801.200000) can0 301#5A00000000000000",
    "(1629946801.400000) can0 123#2C00000000000000",
    "(1629946802.100000) can0 245#5F00000000000000",
    "(1629946802.300000) can0 123#3C00000000000000",
    "(1629946802.500000) can0 301#6400000000000000",
    "(1629946803.000000) can0 245#7000000000000000",
    "(1629946803.200000) can0 123#2A00000000000000",
    "(1629946803.400000) can0 301#6E00000000000000",
    "garbage line that is not a can frame",
]


@dataclass
class Frame:
    ts: float
    bus_id: int
    data: bytes


def parse_frame(line: str) -> Frame | None:
    """解析一行 BUS 日志；不匹配返回 None（调用方计入无效行）。"""
    m = FRAME_RE.match(line.strip())
    if m is None:
        return None
    payload = bytes.fromhex(m.group(4))  # 空负载 -> b''
    return Frame(float(m.group(1)), int(m.group(3), 16), payload)


def parse_log(log_path: Path) -> tuple[list[Frame], int]:
    frames, invalid = [], 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        frame = parse_frame(line)
        if frame is None:
            invalid += 1
            continue
        frames.append(frame)
    return frames, invalid


def stats_by_id(frames: list[Frame]) -> dict[int, tuple[int, int, int, float]]:
    """按 ID 统计：条数 / 首字节 min / max / avg。"""
    values: dict[int, list[int]] = defaultdict(list)
    for f in frames:
        values[f.bus_id].append(f.data[0] if f.data else 0)
    result: dict[int, tuple[int, int, int, float]] = {}
    for bus_id, vals in sorted(values.items()):
        result[bus_id] = (len(vals), min(vals), max(vals), round(sum(vals) / len(vals), 2))
    return result


def write_report(stats: dict[int, tuple[int, int, int, float]], out: Path) -> None:
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bus_id", "信号", "条数", "min", "max", "avg"])
        for bus_id, (n, lo, hi, avg) in stats.items():
            writer.writerow([f"0x{bus_id:X}", SIGNALS.get(bus_id, "未知"), n, lo, hi, avg])


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph12-sol04-"))
    log_path = work / "can.log"
    log_path.write_text("\n".join(SAMPLE) + "\n", encoding="utf-8")

    frames, invalid = parse_log(log_path)
    print("解析 -> 有效帧", len(frames), "条、无效行", invalid, "条")

    stats = stats_by_id(frames)
    counts = Counter(f.bus_id for f in frames)
    for bus_id, (n, lo, hi, avg) in stats.items():
        print(f"按 ID 统计 -> 0x{bus_id:X} {SIGNALS[bus_id]}: {n} 条 [{lo}, {hi}] avg {avg}")

    filtered = [f for f in frames if f.bus_id == 0x123]
    print("过滤 0x123 ->", len(filtered), "条")

    report = work / "bus_report.csv"
    write_report(stats, report)
    print("CSV 报表 ->", report, "（", len(report.read_text(encoding="utf-8").splitlines()),
          "行，含表头）")
    print("ID 总类数 ->", len(counts))


if __name__ == "__main__":
    main()
