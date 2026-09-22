# project/platdash/cli.py —— platdash 命令行入口
# 验证环境：Python 3.13 + pandas + matplotlib；本机实测 Python 3.13.12
"""命令行：`python3 -m platdash.cli build-dashboard` / `summary`。

流程：读原始平台 CSV → clean_platform 清洗 → analyze/report 出产物。
不指定 --platform/--out 时用内置样例生成器跑通全流程（默认产物写 /tmp）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from platdash.analyze import platform_table
from platdash.clean import clean_platform
from platdash.data import generate_platform, read_platform, write_platform_csv
from platdash.report import build_dashboard


def _resolve_input(platform: Path | None) -> tuple[pd.DataFrame, Path]:
    """样例默认：造一份原始 CSV 到 /tmp 再走同一条读取路径。"""
    if platform is None:
        raw = generate_platform()
        platform = write_platform_csv(raw, Path("/tmp/ph18-project/platform_raw.csv"))
    return read_platform(platform), platform


def cmd_summary(platform: Path | None) -> None:
    df, path = _resolve_input(platform)
    cleaned, stats = clean_platform(df)
    print(f"输入：{path}（原始 {len(df)} 行 → 清洗后 {len(cleaned)} 行）")
    for line in stats.summary_lines():
        print(line)
    table = platform_table(cleaned)
    print("\n单实例汇总：")
    print(table.to_string(index=False))


def cmd_dashboard(platform: Path | None, out: Path | None) -> None:
    df, path = _resolve_input(platform)
    cleaned, stats = clean_platform(df)
    out = out or Path("/tmp/ph18-project")
    artifacts = build_dashboard(cleaned, out)
    print(f"输入：{path}；清洗 {stats.final_rows} 行")
    for kind, p in artifacts.items():
        print(f"  {kind}: {p}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="platdash：平台指标 Dashboard 流水线")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build-dashboard", help="清洗并输出 HTML Dashboard + JSON")
    p_build.add_argument(
        "--platform", type=Path, default=None, help="原始平台 CSV（缺省用内置样例）"
    )
    p_build.add_argument(
        "--out", type=Path, default=None, help="输出目录（缺省 /tmp/ph18-project）"
    )

    p_sum = sub.add_parser("summary", help="终端打印清洗报告与单实例汇总")
    p_sum.add_argument("--platform", type=Path, default=None, help="原始平台 CSV（缺省用内置样例）")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build-dashboard":
        cmd_dashboard(args.platform, args.out)
    elif args.command == "summary":
        cmd_summary(args.platform)


if __name__ == "__main__":
    main(sys.argv[1:])
