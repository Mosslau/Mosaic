# project/telemetry_analyzer.py —— ph09 阶段项目：车辆遥测分析脚本
# 验证环境：Python 3.13.9；numpy 2.3.5 / pandas 2.3.3 / matplotlib 3.10.6 / openpyxl 3.1.5 / tabulate 0.9.0
# 运行：python3 telemetry_analyzer.py --demo [-o 输出目录]     （离线演示完整链路）
#       python3 telemetry_analyzer.py --input telemetry.csv [-o 输出目录]
# 测试：pytest -q（离线）；质量：ruff check .（均已在本环境验证）
"""车辆遥测分析脚本：读取遥测 CSV → 清洗（缺失/异常值）→ 按车辆分组统计 → 图表 + 报表导出。

分层设计（为可离线测试）：
- 解析/清洗/统计/导出均为纯函数：输入 DataFrame 或路径，输出结果，不碰全局状态；
- CLI（main）只负责编排：参数解析 → 取数 → 清洗 → 统计 → 落盘。
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False

SPEED_MIN = 0  # 速度物理下限 km/h
SPEED_MAX = 200  # 速度物理上限 km/h（GPS 跳变异常值过滤阈值）


def generate_demo_data(seed: int = 42) -> pd.DataFrame:
    """生成模拟遥测数据：3 辆车、30 秒一条、各 240 行（2 小时）。

    人为注入数据缺陷：3 个缺失速度 + 2 个 GPS 跳变异常速度，供 clean() 演示。
    """
    rng = np.random.default_rng(seed)
    frames = []
    for vehicle_id in ("V001", "V002", "V003"):
        n = 240
        speed = rng.normal(60, 15, n).clip(0, 120)
        # 每行视为一个 30 秒行驶段：里程与速度成正比，能耗与里程相关
        mileage = speed * (30 / 3600) + rng.normal(0, 0.1, n)
        energy = mileage * 0.18 + rng.normal(0, 0.05, n)
        frames.append(
            pd.DataFrame(
                {
                    "vehicle_id": vehicle_id,
                    "time": pd.date_range("2024-06-01 08:00:00", periods=n, freq="30s"),
                    "speed": speed,
                    "mileage": mileage,
                    "energy": energy,
                }
            )
        )
    df = pd.concat(frames, ignore_index=True)
    df.loc[5, "speed"] = np.nan  # 缺失值 1
    df.loc[120, "speed"] = np.nan  # 缺失值 2
    df.loc[250, "speed"] = np.nan  # 缺失值 3
    df.loc[60, "speed"] = 320  # 异常值 1（物理上不可能）
    df.loc[400, "speed"] = 280  # 异常值 2
    return df


def load_telemetry(path: str | Path) -> pd.DataFrame:
    """读取遥测 CSV：vehicle_id 保留字符串，time 解析为日期时间。"""
    return pd.read_csv(path, dtype={"vehicle_id": str}, parse_dates=["time"])


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """清洗四步：缺失值（组内中位数填充）→ 异常值（速度物理范围过滤）→ 去重 → 重置索引。

    返回新 DataFrame，不改动入参（呼应主文档 4.3 的复制语义）。
    """
    out = df.copy()
    out["speed"] = out["speed"].fillna(
        out.groupby("vehicle_id")["speed"].transform("median")
    )
    out = out[(out["speed"] >= SPEED_MIN) & (out["speed"] <= SPEED_MAX)]
    out = out.drop_duplicates()
    return out.reset_index(drop=True)


def analyze(df: pd.DataFrame) -> pd.DataFrame:
    """按车辆分组统计：出车段数、总里程、总能耗、平均速度、百公里能耗。"""
    stats = (
        df.groupby("vehicle_id")
        .agg(
            trips=("time", "count"),
            total_mileage=("mileage", "sum"),
            total_energy=("energy", "sum"),
            avg_speed=("speed", "mean"),
        )
        .round(2)
    )
    stats["energy_per_100km"] = stats["total_energy"] / stats["total_mileage"] * 100
    return stats.round(2).reset_index()


def make_charts(df: pd.DataFrame, outdir: Path) -> list[Path]:
    """两张图：折线趋势（每车 5 分钟均速）+ 柱状对比（每车平均速度）。"""
    ts = df.set_index("time")
    trend = ts.groupby("vehicle_id")["speed"].resample("5min").mean().unstack(level=0)

    fig, ax = plt.subplots(figsize=(10, 4))
    trend.plot(ax=ax, marker="o", markersize=3)
    ax.set_title("各车速度趋势（5 分钟均值）")
    ax.set_ylabel("km/h")
    ax.legend(title="vehicle_id")
    plt.tight_layout()
    trend_png = outdir / "speed_trend.png"
    fig.savefig(trend_png, dpi=150)
    plt.close(fig)

    avg = df.groupby("vehicle_id")["speed"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(6, 4))
    avg.plot.bar(ax=ax, color="steelblue")
    ax.set_title("各车平均速度对比")
    ax.set_ylabel("km/h")
    ax.set_xlabel("vehicle_id")
    plt.tight_layout()
    compare_png = outdir / "vehicle_compare.png"
    fig.savefig(compare_png, dpi=150)
    plt.close(fig)
    return [trend_png, compare_png]


def export_report(stats: pd.DataFrame, df: pd.DataFrame, outdir: Path) -> list[Path]:
    """导出 Excel（汇总 + 清洗后数据两个 Sheet）与 Markdown 摘要报告。"""
    xlsx = outdir / "telemetry_report.xlsx"
    with pd.ExcelWriter(xlsx) as writer:
        stats.to_excel(writer, sheet_name="汇总", index=False)
        df.to_excel(writer, sheet_name="清洗后数据", index=False)
    md = outdir / "telemetry_report.md"
    md.write_text(
        "# 车辆遥测分析报告\n\n"
        "## 按车辆汇总\n\n"
        + stats.to_markdown(index=False)
        + "\n\n（图表见 speed_trend.png / vehicle_compare.png）",
        encoding="utf-8",
    )
    return [xlsx, md]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="车辆遥测分析脚本")
    parser.add_argument("--demo", action="store_true", help="用内置模拟数据离线演示完整链路")
    parser.add_argument(
        "--input", type=Path, help="遥测 CSV（列：vehicle_id,time,speed,mileage,energy）"
    )
    parser.add_argument("-o", "--outdir", type=Path, help="产物输出目录（默认系统临时目录）")
    args = parser.parse_args(argv)

    if args.demo:
        raw = generate_demo_data()
        print(f"演示模式：生成模拟遥测 {len(raw)} 行（含 3 个缺失速度、2 个异常速度）")
    elif args.input is not None:
        raw = load_telemetry(args.input)
        print(f"读取 {args.input}: {len(raw)} 行")
    else:
        parser.error("必须提供 --input 或 --demo 之一")

    cleaned = clean(raw)
    print(f"清洗后 {len(cleaned)} 行（剔除 {len(raw) - len(cleaned)} 行）")
    stats = analyze(cleaned)
    print("\n按车辆分组统计:")
    print(stats.to_string(index=False))

    outdir = args.outdir or Path(tempfile.mkdtemp(prefix="ph09-project-"))
    outdir.mkdir(parents=True, exist_ok=True)
    charts = make_charts(cleaned, outdir)
    reports = export_report(stats, cleaned, outdir)
    print("\n图表:")
    for p in charts:
        print(" ", p)
    print("报告:")
    for p in reports:
        print(" ", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
