#!/usr/bin/env python3
"""cli.py —— telemetry_stats 命令行入口：CSV → 报表。

用法：
    python3 cli.py --demo                                   # 离线演示 + 自检
    python3 cli.py --input telemetry.csv --output-dir out/  # 真实使用
    python3 cli.py --input telemetry.csv --output-dir out/ --filter-vehicle EV-001
"""

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from telemetry_stats.parser import parse_csv
from telemetry_stats.report import write_csv_report, write_summary
from telemetry_stats.stats import filter_vehicle, per_vehicle_stats

# 确定性演示样本：4 有效行 + 1 无效行（"bad,line" 字段数不对）
DEMO_CSV = """ts,vehicle,speed,battery
2026-09-01 10:00:00,EV-001,42.0,88.0
2026-09-01 10:01:00,EV-001,55.0,86.5
bad,line
2026-09-01 10:02:00,EV-002,30.0,91.0
2026-09-01 10:03:00,EV-002,28.5,90.2
"""

logger = logging.getLogger("telemetry_stats.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telemetry-stats", description="车辆遥测数据处理：CSV 清洗 → 分组统计 → 报表"
    )
    parser.add_argument("--input", help="遥测 CSV 路径")
    parser.add_argument("--output-dir", default="out", help="报表输出目录（默认 out/）")
    parser.add_argument("--filter-vehicle", help="只统计指定车辆（如 EV-001）")
    parser.add_argument("--demo", action="store_true", help="离线演示：临时样本 → 全流程 → 自检")
    parser.add_argument("--log-level", default="INFO", help="日志级别（DEBUG/INFO/WARNING）")
    return parser


def run_pipeline(
    source: Path, output_dir: Path, filter_vehicle_id: str | None
) -> tuple[int, int, int]:
    """执行「解析 → 过滤 → 统计 → 报表」主流程，返回 (有效行, 无效行, 车辆数)。"""
    rows, invalid = parse_csv(source)
    if filter_vehicle_id:
        rows = filter_vehicle(rows, filter_vehicle_id)
    stats = per_vehicle_stats(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_report(stats, output_dir / "telemetry_report.csv")
    write_summary(rows, invalid, stats, output_dir / "summary.txt", str(source))
    for s in stats:
        logger.info(
            "%s: %d 条 speed=[%s, %s] avg=%s",
            s.vehicle_id,
            s.count,
            s.speed_min,
            s.speed_max,
            s.speed_avg,
        )
    logger.info("报表已写入 %s（telemetry_report.csv + summary.txt）", output_dir)
    return len(rows), invalid, len(stats)


def demo() -> int:
    """离线演示：临时样本 → 全流程 → 自检断言，退出码 0 表示通过。"""
    work = Path(tempfile.mkdtemp(prefix="ph13-telemetry-demo-"))
    sample = work / "sample.csv"
    sample.write_text(DEMO_CSV, encoding="utf-8")
    out = work / "reports"
    valid, invalid, vehicles = run_pipeline(sample, out, None)

    # 自检断言（演示「测试思维」：连演示脚本也对自己做检查）
    assert valid == 4, f"有效行应为 4，实际 {valid}"
    assert invalid == 1, f"无效行应为 1，实际 {invalid}"
    assert vehicles == 2, f"车辆数应为 2，实际 {vehicles}"
    report = out / "telemetry_report.csv"
    assert report.read_text(encoding="utf-8").count("\n") == 3, "报表应为 3 行（表头 + 2 车）"

    print(f"样本: {sample}")
    print(f"总行数: 有效 {valid} | 无效 {invalid} | 车辆 {vehicles}")
    print(report.read_text(encoding="utf-8").strip())
    print(f"汇总: {out / 'summary.txt'}")
    print("自检通过：解析 / 统计 / 报表全部正确")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(levelname)s %(message)s",
    )

    if args.demo:
        return demo()

    if not args.input:
        print("错误：需要 --input 或 --demo", file=sys.stderr)
        return 2
    source = Path(args.input)
    if not source.exists():
        print(f"错误：输入文件不存在: {source}", file=sys.stderr)
        return 2

    valid, invalid, vehicles = run_pipeline(source, Path(args.output_dir), args.filter_vehicle)
    print(f"完成: 有效 {valid} 行, 无效 {invalid} 行, {vehicles} 辆车 -> {args.output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
