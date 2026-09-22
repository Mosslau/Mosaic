# project/streamlog/cli.py —— 命令行入口（生成器管线 + ExitStack 资源组合）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 -m streamlog.cli --file app.log --level ERROR --stats
# 测试/lint：见 project/README.md（python3 -m pytest / ruff check .）
# 验证状态：已验证（Python 3.13.9 本机实测：project/tests 全绿、ruff 全绿）
"""streamlog.cli —— 命令行入口。

    python3 -m streamlog.cli --file app.log --level ERROR --stats
    python3 -m streamlog.cli --file app.log --pattern "timeout" --out hits.txt

管线（全部惰性，逐行流动）：
    read_lines ──▶ parse_lines ──▶ [by_level] ──▶ [by_pattern] ──▶ 写 sink + 计数
    各段耗时/条数由 Counted 装饰器横切统计，--stats 时汇总到 stderr
    （stdout 保持纯数据，便于管道衔接）。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from contextlib import ExitStack

from streamlog.filters import Counted, by_level, by_pattern
from streamlog.parser import parse_lines
from streamlog.reader import read_lines
from streamlog.sinks import FileSink

_LEVEL_CHOICES = ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streamlog",
        description=(
            "流式日志处理器：生成器管线逐行解析/过滤/统计大日志，"
            "内存占用与文件大小无关（ph17 阶段项目）。"
        ),
    )
    parser.add_argument("--file", "-f", default="-", help="输入文件路径，默认 '-' 读标准输入")
    parser.add_argument(
        "--level",
        "-l",
        action="append",
        choices=_LEVEL_CHOICES,
        help="只保留该级别（可多次指定，如 -l ERROR -l CRITICAL）",
    )
    parser.add_argument("--pattern", "-p", metavar="REGEX", help="只保留 message 匹配该正则的行")
    parser.add_argument(
        "--stats", action="store_true", help="管线结束后向 stderr 打印条数/耗时统计"
    )
    parser.add_argument(
        "--out", "-o", metavar="FILE", help="命中的原始行写入该文件（缺省打印到 stdout）"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="不打印命中行（只写文件 / 只统计）"
    )
    return parser


def _stats_block(raw: Counted, parsed: Counted, level_counts: Counter[str]) -> list[str]:
    """汇总统计文本（cli 输出到 stderr，不污染 stdout 的数据流）。"""
    matched = sum(level_counts.values())
    skipped = raw.count - parsed.count  # 读到的行 - 成功解析的行
    dist = " ".join(f"{k}={level_counts[k]}" for k in sorted(level_counts)) or "(空)"
    return [
        f"level 分布: {dist}",
        f"raw={raw.count} parsed={parsed.count} matched={matched} skipped={skipped}",
        raw.summary("read"),
        parsed.summary("parse"),
    ]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    raw_stage = Counted(read_lines)  # 装饰器横切：统计读取段
    parse_stage = Counted(parse_lines)  # 统计解析段
    level_counts: Counter[str] = Counter()

    # ExitStack 动态管理输出资源：--out 文件或 stdout（--quiet 时一个都不开）
    try:
        with ExitStack() as stack:
            sinks: list[FileSink] = []
            if args.out:
                sinks.append(stack.enter_context(FileSink(args.out)))
            elif not args.quiet:
                sinks.append(stack.enter_context(FileSink()))  # stdout

            records = parse_stage(raw_stage(args.file))
            if args.level:
                records = by_level(records, set(args.level))
            if args.pattern:
                records = by_pattern(records, args.pattern)

            for record in records:  # 逐条流动：计数 + 写 sink
                level_counts[record.level] += 1
                for sink in sinks:
                    sink.write_line(record.raw)
    except FileNotFoundError as exc:
        print(f"streamlog: 打不开文件: {exc}", file=sys.stderr)
        return 1
    except re.error as exc:  # --pattern 编译失败（消费时惰性抛出）
        print(f"streamlog: 正则错误: {exc}", file=sys.stderr)
        return 2

    if args.stats:
        for line in _stats_block(raw_stage, parse_stage, level_counts):
            print(line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
