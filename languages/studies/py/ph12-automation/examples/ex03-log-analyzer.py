#!/usr/bin/env python3
# examples/ex03-log-analyzer.py —— 日志分析：正则解析 + Counter 统计 + CSV 报表
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 ex03-log-analyzer.py（离线可跑，已验证；样本日志与 CSV 报表在系统临时目录）
# 说明：对应主文档 3.3/3.5。用正则逐行解析访问日志，统计状态码/小时/IP 分布，
#       结果写 CSV 报表（可审计、可复用）。
import csv
import re
import tempfile
from collections import Counter
from pathlib import Path

# 访问日志一行：时间 IP 方法 路径 状态码 字节数
LINE_RE = re.compile(
    r"^(?P<ts>\S+ \S+) (?P<ip>\S+) (?P<method>\S+) "
    r"(?P<path>\S+) (?P<status>\d{3}) (?P<bytes>\d+)$"
)

SAMPLE = [
    "2026-09-01 10:12:33 192.168.1.10 GET /api/vehicles 200 1532",
    "2026-09-01 10:12:40 192.168.1.11 GET /api/vehicles 200 1488",
    "2026-09-01 10:15:02 10.0.0.5 POST /api/telemetry 201 96",
    "2026-09-01 10:22:17 192.168.1.10 GET /api/devices 404 210",
    "2026-09-01 11:03:44 10.0.0.5 GET /api/vehicles 200 1490",
    "2026-09-01 11:05:09 192.168.1.12 GET /api/vehicles 500 23",
    "2026-09-01 11:20:55 10.0.0.6 GET /api/status 200 512",
    "2026-09-01 14:02:31 192.168.1.10 POST /api/telemetry 201 102",
    "2026-09-01 14:10:12 192.168.1.13 GET /api/vehicles 200 1501",
    "2026-09-01 15:47:08 10.0.0.5 GET /api/devices 200 218",
    "2026-09-01 16:20:44 192.168.1.10 GET /api/vehicles 200 1599",
    "this line is malformed and should be counted as invalid",
]


def analyze(log_path: Path) -> tuple[list[dict], int]:
    """逐行解析日志，返回 (有效记录列表, 无效行数)。"""
    records, invalid = [], 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = LINE_RE.match(line)
        if m is None:
            invalid += 1
            continue
        records.append(m.groupdict())
    return records, invalid


def write_report(records: list[dict], out: Path) -> None:
    """把三张统计表写进一个 CSV 报表（append 模式逐表追加）。"""
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["统计项", "取值", "数量"])
        status = Counter(r["status"] for r in records)
        for code, n in sorted(status.items()):
            writer.writerow(["状态码", code, n])
        hours = Counter(r["ts"].split()[1][:2] for r in records)
        for h, n in sorted(hours.items()):
            writer.writerow(["小时", f"{h}:00", n])
        ips = Counter(r["ip"] for r in records)
        for ip, n in ips.most_common(3):
            writer.writerow(["Top IP", ip, n])


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph12-ex03-"))
    log_path = work / "access.log"
    log_path.write_text("\n".join(SAMPLE) + "\n", encoding="utf-8")

    records, invalid = analyze(log_path)
    print("解析日志 -> 总行数:", len(SAMPLE), "| 有效:", len(records), "| 无效:", invalid)

    status = Counter(r["status"] for r in records)
    hours = Counter(r["ts"].split()[1][:2] for r in records)
    ips = Counter(r["ip"] for r in records)
    print("状态码分布 ->", dict(sorted(status.items())))
    print("最繁忙时段 ->", max(hours, key=hours.get), "时（", max(hours.values()), "条请求）")
    print("Top IP ->", ips.most_common(1)[0][0], "（", ips.most_common(1)[0][1], "条）")

    report = work / "access-report.csv"
    write_report(records, report)
    lines = report.read_text(encoding="utf-8").strip().splitlines()
    print("CSV 报表 ->", report, f"（{len(lines)} 行，含表头）")
    print("报表首行 ->", lines[0])


if __name__ == "__main__":
    main()
