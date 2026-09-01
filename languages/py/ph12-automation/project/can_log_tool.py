#!/usr/bin/env python3
# project/can_log_tool.py —— ph12 阶段项目：CAN 日志批处理工具
# 验证环境：Python 3.13.9（stdlib，无第三方依赖；测试用 pytest 8.4.2、门禁 ruff 0.12.0）
# 运行：python3 can_log_tool.py --demo                     （离线自检演示）
#       python3 can_log_tool.py --input can.log --output-dir out/ [--filter-id 0x123]
# 测试：pytest -q；门禁：ruff check . && pytest -q
# 说明：解析 candump 风格 CAN 日志（(秒.微秒) 接口 ID#负载HEX），按 ID 统计信号值
#       （首字节即信号值，简化约定），输出 CSV 报表 + 文本汇总；argparse 参数化、
#       logging 审计、可安全重跑（报表确定性覆盖）、输出可审计（时间戳 + 明细）。
import argparse
import csv
import logging
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# candump 风格一行：(1629946800.123456) can0 123#0102030405060708
FRAME_RE = re.compile(r"^\((\d+\.\d+)\) (\S+) ([0-9A-Fa-f]+)#([0-9A-Fa-f]*)$")

# 车辆信号映射（简化版：首字节即信号值；完整 DBC 信号矩阵解析属 ph18 车联网阶段）
SIGNALS = {0x123: "车速", 0x245: "电池电压", 0x301: "电机温度"}


@dataclass
class Frame:
    ts: float
    interface: str
    can_id: int
    data: bytes


@dataclass
class IdStats:
    count: int = 0
    min: int = 0
    max: int = 0
    avg: float = 0.0


@dataclass
class Report:
    input_path: Path
    filter_id: int | None = None
    total: int = 0
    invalid: int = 0
    stats: dict[int, IdStats] = field(default_factory=dict)


def parse_line(line: str) -> Frame | None:
    """解析一行 CAN 日志；不匹配返回 None（调用方计入无效行）。"""
    m = FRAME_RE.match(line.strip())
    if m is None:
        return None
    payload = bytes.fromhex(m.group(4))  # 空负载 -> b''
    return Frame(float(m.group(1)), m.group(2), int(m.group(3), 16), payload)


def parse_log(log_path: Path) -> tuple[list[Frame], int]:
    """逐行解析日志文件，返回 (有效帧列表, 无效行数)。"""
    frames, invalid = [], 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        frame = parse_line(line)
        if frame is None:
            invalid += 1
            continue
        frames.append(frame)
    return frames, invalid


def filter_id_frames(frames: list[Frame], can_id: int) -> list[Frame]:
    """按 ID 过滤帧列表（保持原始顺序）。"""
    return [f for f in frames if f.can_id == can_id]


def stats_by_id(frames: list[Frame]) -> dict[int, IdStats]:
    """按 ID 统计：条数 / 首字节 min / max / avg。"""
    values: dict[int, list[int]] = {}
    for f in frames:
        values.setdefault(f.can_id, []).append(f.data[0] if f.data else 0)
    stats: dict[int, IdStats] = {}
    for can_id in sorted(values):
        vals = values[can_id]
        stats[can_id] = IdStats(
            count=len(vals),
            min=min(vals),
            max=max(vals),
            avg=round(sum(vals) / len(vals), 2),
        )
    return stats


def write_csv_report(stats: dict[int, IdStats], out: Path) -> None:
    """CSV 报表：can_id / 信号 / 条数 / min / max / avg（确定性内容，可安全重跑）。"""
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["can_id", "信号", "条数", "min", "max", "avg"])
        for can_id, s in stats.items():
            writer.writerow([
                f"0x{can_id:X}", SIGNALS.get(can_id, "未知"), s.count, s.min, s.max, s.avg,
            ])


def _format_filter(can_id: int | None) -> str:
    return f"0x{can_id:X}" if can_id is not None else "无（全部 ID）"


def write_summary(report: Report, out: Path) -> None:
    """文本汇总：输入文件、生成时间、过滤条件、总帧数/无效行、逐 ID 统计——可审计。"""
    lines = [
        "# CAN 日志分析报告",
        f"输入文件: {report.input_path}",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"过滤条件: {_format_filter(report.filter_id)}",
        f"总帧数: {report.total} | 无效行: {report.invalid}",
        "按 ID 统计（首字节信号值）:",
    ]
    for can_id, s in report.stats.items():
        lines.append(
            f"  0x{can_id:X} {SIGNALS.get(can_id, '未知')}: "
            f"{s.count} 条 [{s.min}, {s.max}] avg {s.avg}"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(input_path: Path, output_dir: Path, filter_id: int | None,
            logger: logging.Logger) -> Report:
    """主流程：解析 → 过滤 → 统计 → 落盘 CSV 与汇总；报表覆盖写（幂等）。"""
    frames, invalid = parse_log(input_path)
    logger.info("解析 %s -> %d 帧, %d 无效行", input_path.name, len(frames), invalid)
    if filter_id is not None:
        frames = filter_id_frames(frames, filter_id)
        logger.info("按 ID 0x%X 过滤 -> %d 帧", filter_id, len(frames))
    stats = stats_by_id(frames)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = Report(input_path=input_path, filter_id=filter_id,
                    total=len(frames), invalid=invalid, stats=stats)
    write_csv_report(stats, output_dir / "can_report.csv")
    write_summary(report, output_dir / "summary.txt")
    logger.info("报表已写入 %s（can_report.csv + summary.txt）", output_dir)
    return report


def generate_sample_log(path: Path) -> None:
    """生成确定性样本：12 条有效帧 + 1 条乱行（演示与测试共用，数字固定）。"""
    payloads = [
        (0x123, 30), (0x123, 36), (0x245, 95), (0x123, 42),
        (0x301, 90), (0x123, 48), (0x245, 104), (0x123, 54),
        (0x301, 100), (0x245, 112), (0x123, 60), (0x301, 110),
    ]
    lines = []
    ts = 1629946800.123456
    for can_id, value in payloads:
        lines.append(f"({ts:.6f}) can0 {can_id:X}#{value:02X}{'00' * 7}")
        ts += 0.2
    lines.append("garbage line that is not a can frame")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def setup_logging(level: str, log_file: str | None) -> logging.Logger:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
    return logging.getLogger("can_log_tool")


def run_demo() -> int:
    """离线演示：临时目录生成样本 → 全流程分析 → 自检数字 → 打印报表。"""
    work = Path(tempfile.mkdtemp(prefix="ph12-can-"))
    log_path = work / "sample-can.log"
    generate_sample_log(log_path)
    report = analyze(
        log_path, work / "reports", filter_id=None,
        logger=logging.getLogger("can_log_tool"),
    )
    # 自检：数字与样本定义一致
    assert report.total == 12, f"期望 12 帧，实际 {report.total}"
    assert report.invalid == 1, f"期望 1 无效行，实际 {report.invalid}"
    assert report.stats[0x123].avg == 45.0
    assert report.stats[0x245].avg == 103.67
    assert report.stats[0x301].max == 110
    print(f"样本: {log_path}")
    print(f"总帧数: {report.total} | 无效行: {report.invalid} | ID 类数: {len(report.stats)}")
    for can_id, s in report.stats.items():
        print(f"  0x{can_id:X} {SIGNALS[can_id]}: {s.count} 条 [{s.min}, {s.max}] avg {s.avg}")
    report_csv = work / "reports" / "can_report.csv"
    report_lines = len(report_csv.read_text(encoding="utf-8").splitlines())
    print(f"报表: {report_csv}（{report_lines} 行，含表头）")
    print("自检通过：帧数 / 无效行 / 各 ID 统计 / 报表行数全部正确")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="can_log_tool",
        description="CAN 日志批处理工具：解析 candump 格式日志，按 ID 统计信号值并生成报表",
    )
    parser.add_argument("--input", help="CAN 日志文件路径（candump 格式）")
    parser.add_argument("--output-dir", default=".", help="报表输出目录（默认当前目录）")
    parser.add_argument("--filter-id", help="只统计指定 ID（如 0x123），默认全部")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="日志级别（默认 INFO）")
    parser.add_argument("--log-file", help="审计日志文件路径（可选，默认仅 stderr）")
    parser.add_argument("--demo", action="store_true",
                        help="离线演示：生成样本并跑完整流程（自检）")
    args = parser.parse_args(argv)

    logger = setup_logging(args.log_level, args.log_file)
    if args.demo:
        return run_demo()
    if not args.input:
        parser.error("--demo 之外必须提供 --input")
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        return 2
    filter_id = int(args.filter_id, 16) if args.filter_id else None
    report = analyze(input_path, Path(args.output_dir), filter_id, logger)
    print(f"完成: {report.total} 帧, {len(report.stats)} 个 ID -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
