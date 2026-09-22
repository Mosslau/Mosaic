#!/usr/bin/env python3
# exercises/sol-02-vehicle-clean.py —— 参考实现：车辆数据清洗工具（对应 roadmap §18 练习 2）
# 验证环境（目标）：Python 3.13；本机实测 Python 3.13.12，纯标准库（csv/argparse）
# 运行：python3 sol-02-vehicle-clean.py（生成样例 → 清洗 → 打印报告 → 断言自检）
# 指定文件：python3 sol-02-vehicle-clean.py --input path/to/raw.csv --output /tmp/clean.csv
# 测试：python3 -m pytest sol-02-vehicle-clean.py -q
# lint：ruff check sol-02-vehicle-clean.py
# 验证状态：已验证（Python 3.13.12 本机实测：运行自检与 pytest 全绿）
"""车辆数据清洗工具（CSV → CSV）：去重 → 解析/量程 → 剔除异常 → 摘要报告。

练习要求见 README.md。选择纯标准库实现：车联网清洗工具的验收点是「输入脏 CSV 输出
干净 CSV + 可审计报告」，不依赖 pandas 也成立 —— 数据量到 GB 级再上 pandas/polars
（ph09 的技能）做向量化清洗，瓶颈在 IO 时流式读同样重要。
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# 每列的量程规格（与 ex02/项目共用同一份语义：量程=物理允许范围）
RANGES: dict[str, tuple[float, float]] = {
    "speed_kmh": (0.0, 220.0),
    "soc_pct": (0.0, 100.0),
    "pack_voltage_v": (250.0, 420.0),
    "pack_temp_c": (-40.0, 65.0),
    "pack_current_a": (-300.0, 400.0),
    "power_kw": (-300.0, 300.0),
}
KEY_COLS = ("ts", "vehicle_id")  # 去重主键


@dataclass
class CleanSummary:
    """清洗审计：逐项计数（可重复、可核对）。"""

    raw_rows: int = 0
    kept_rows: int = 0
    dropped: Counter[str] = field(default_factory=Counter)  # 原因 → 数量
    parse_errors: int = 0


def parse_row(row: dict[str, str]) -> dict[str, float | str] | None:
    """把 CSV 文本行转成数值行；缺量程列/非法数值返回 None（调用方计 parse_error）。"""
    try:
        ts = float(row["ts"])
        vid = row["vehicle_id"].strip()
        if not vid:
            raise ValueError("空 vehicle_id")
        return {
            "ts": ts,
            "vehicle_id": vid,
            **{col: float(row[col]) for col in RANGES},
        }
    except (KeyError, ValueError):
        return None


def clean_csv(input_path: Path, output_path: Path) -> CleanSummary:
    """单遍清洗：去重 → 量程剔除 → 写干净 CSV，全程不整读（逐行处理）。"""
    summary = CleanSummary()
    seen: set[tuple[str, str]] = set()
    written = 0

    with (
        open(input_path, encoding="utf-8", newline="") as fin,
        open(output_path, "w", encoding="utf-8", newline="") as fout,
    ):
        reader = csv.DictReader(fin)
        fieldnames = ["ts", "vehicle_id", *RANGES]
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            summary.raw_rows += 1
            parsed = parse_row(row)
            if parsed is None:
                summary.parse_errors += 1
                summary.dropped["parse_error"] += 1
                continue
            key = (str(parsed["ts"]), str(parsed["vehicle_id"]))
            if key in seen:
                summary.dropped["duplicate"] += 1
                continue
            seen.add(key)
            out_of_range = False
            for col, (lo, hi) in RANGES.items():
                value = float(parsed[col])
                if not lo <= value <= hi:
                    summary.dropped[f"range:{col}"] += 1
                    out_of_range = True
            if out_of_range:
                continue
            writer.writerow(parsed)
            written += 1
    summary.kept_rows = written
    return summary


def render_report(summary: CleanSummary) -> str:
    lines = [
        "# 清洗报告",
        "",
        f"- 输入行数：{summary.raw_rows}",
        f"- 保留行数：{summary.kept_rows}",
        f"- 解析失败：{summary.parse_errors}",
    ]
    if summary.dropped:
        lines.append("")
        lines.append("剔除明细：")
        for reason, count in summary.dropped.most_common():
            lines.append(f"  - {reason}: {count}")
    return "\n".join(lines)


def generate_raw_sample(path: Path) -> None:
    """写一个带脏数据的样例 CSV（/tmp），保证可复现的演示输入。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        [
            "ts",
            "vehicle_id",
            "speed_kmh",
            "soc_pct",
            "pack_voltage_v",
            "pack_temp_c",
            "pack_current_a",
            "power_kw",
        ]
    ]
    base = 1_700_000_000
    for sec in range(5):
        rows.append([base + sec, "V001", 40 + sec, 80 - sec, 380, 30, -25, -9.5])
        rows.append([base + sec, "V002", 55 + sec, 90 - sec, 385, 32, -30, -11.5])
    # 脏数据：重复行、量程越界、坏数值
    rows.append([base + 2, "V001", 40 + 2, 80 - 2, 380, 30, -25, -9.5])  # 与第 3 行重复
    rows.append([base + 9, "V001", 300, 80, 380, 30, -25, -9.5])  # speed 越界
    rows.append([base + 9, "V002", 55, -5, 385, 32, -30, -11.5])  # soc 越界
    rows.append([base + 9, "V003", "bad", 80, 380, 30, -25, -9.5])  # speed 非法数值
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="车辆数据清洗工具（CSV → CSV）")
    parser.add_argument("--input", type=Path, default=Path("/tmp/ph18-exer02/raw.csv"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/ph18-exer02/clean.csv"))
    args = parser.parse_args(argv)

    generate_raw_sample(args.input)
    summary = clean_csv(args.input, args.output)
    print(render_report(summary))

    # ---- 自检 ----
    assert summary.raw_rows == 14  # 10 正常 + dup + 2 越界 + 1 坏值
    assert summary.parse_errors == 1  # "bad" 行
    assert summary.dropped["duplicate"] == 1
    assert summary.dropped["range:speed_kmh"] == 1
    assert summary.dropped["range:soc_pct"] == 1
    assert summary.kept_rows == 10  # 14 - (1 parse + 1 dup + 2 range)
    with open(args.output, encoding="utf-8") as f:
        kept = [r for r in csv.DictReader(f)]
    assert len(kept) == 10 and all(0 <= float(r["speed_kmh"]) <= 220 for r in kept)
    print("\n自检通过：去重、量程剔除、坏值拒收、保留行数断言全绿")


def test_clean_csv_counts() -> None:
    raw = Path("/tmp/ph18-exer02-test/raw.csv")
    out = Path("/tmp/ph18-exer02-test/clean.csv")
    generate_raw_sample(raw)
    summary = clean_csv(raw, out)
    assert summary.parse_errors == 1 and summary.dropped["duplicate"] == 1
    assert summary.kept_rows == 10


def test_clean_csv_is_idempotent_second_pass() -> None:
    raw = Path("/tmp/ph18-exer02-test/raw.csv")
    once = Path("/tmp/ph18-exer02-test/once.csv")
    twice = Path("/tmp/ph18-exer02-test/twice.csv")
    generate_raw_sample(raw)
    s1 = clean_csv(raw, once)
    s2 = clean_csv(once, twice)  # 干净数据再过一遍不应丢行
    assert s1.kept_rows == 10
    assert s2.dropped == Counter() and s2.kept_rows == 10


def test_missing_column_rejected_as_parse_error() -> None:
    raw = Path("/tmp/ph18-exer02-test/raw2.csv")
    out = Path("/tmp/ph18-exer02-test/clean2.csv")
    raw.write_text("ts,vehicle_id,speed_kmh,soc_pct\n1,V001,10,80\n", encoding="utf-8")  # 缺量程列
    summary = clean_csv(raw, out)
    assert summary.parse_errors == 1 and summary.kept_rows == 0


if __name__ == "__main__":
    main(sys.argv[1:])
