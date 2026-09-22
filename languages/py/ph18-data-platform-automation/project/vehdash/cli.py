# project/vehdash/cli.py —— vehdash 命令行入口
# 验证环境：Python 3.13 + pandas + matplotlib；本机实测 Python 3.13.12
"""命令行：`python3 -m vehdash.cli build-dashboard` / `summary`。

流程：读原始车队 CSV → clean_fleet 清洗 → analyze/report 出产物。
不指定 --fleet/--out 时用内置样例生成器跑通全流程（默认产物写 /tmp）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from vehdash.analyze import fleet_table
from vehdash.clean import clean_fleet
from vehdash.data import generate_fleet, read_fleet, write_fleet_csv
from vehdash.report import build_dashboard


def _resolve_input(fleet: Path | None) -> tuple[pd.DataFrame, Path]:
    """样例默认：造一份原始 CSV 到 /tmp 再走同一条读取路径。"""
    if fleet is None:
        fleet = write_fleet_csv(generate_fleet(), Path("/tmp/ph18-project/fleet_raw.csv"))
    return read_fleet(fleet), fleet


def cmd_summary(fleet: Path | None) -> None:
    df, path = _resolve_input(fleet)
    cleaned, stats = clean_fleet(df)
    print(f"输入：{path}（原始 {len(df)} 行 → 清洗后 {len(cleaned)} 行）")
    for line in stats.summary_lines():
        print(line)
    table = fleet_table(cleaned)
    print("\n单车汇总：")
    print(table.to_string(index=False))


def cmd_dashboard(fleet: Path | None, out: Path | None) -> None:
    df, path = _resolve_input(fleet)
    cleaned, stats = clean_fleet(df)
    out = out or Path("/tmp/ph18-project")
    artifacts = build_dashboard(cleaned, out)
    print(f"输入：{path}；清洗 {stats.final_rows} 行")
    for kind, p in artifacts.items():
        print(f"  {kind}: {p}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="vehdash：车辆遥测 Dashboard 流水线")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build-dashboard", help="清洗并输出 HTML Dashboard + JSON")
    p_build.add_argument("--fleet", type=Path, default=None, help="原始车队 CSV（缺省用内置样例）")
    p_build.add_argument(
        "--out", type=Path, default=None, help="输出目录（缺省 /tmp/ph18-project）"
    )

    p_sum = sub.add_parser("summary", help="终端打印清洗报告与单车汇总")
    p_sum.add_argument("--fleet", type=Path, default=None, help="原始车队 CSV（缺省用内置样例）")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build-dashboard":
        cmd_dashboard(args.fleet, args.out)
    elif args.command == "summary":
        cmd_summary(args.fleet)


if __name__ == "__main__":
    main(sys.argv[1:])
