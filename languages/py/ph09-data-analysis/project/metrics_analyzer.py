# project/metrics_analyzer.py —— ph09 阶段项目：平台指标分析脚本
# 验证环境：Python 3.13.9（numpy 2.3.5 / pandas 2.3.3 / matplotlib 3.10.6 / openpyxl / tabulate）
# 运行：python3 metrics_analyzer.py --demo [-o 输出目录]     （离线演示完整链路）
#       python3 metrics_analyzer.py --input metrics.csv [-o 输出目录]
# 测试：python3 -m pytest tests -q（离线）；质量：ruff check . && ruff format --check .
# 验证状态：已验证 —— python3 metrics_analyzer.py --demo：生成 720 行 → 清洗后 718 行（剔除 2 行）；
#           tests/ 5 个用例全过（pytest -q）；ruff check/format 全绿
"""平台指标分析脚本：读取平台指标 CSV → 清洗（缺失/越界/重复）→ 按服务实例分组统计
→ 图表 + 报表导出。

指标口径与 ph18「全阶段指标口径」一致（列顺序即 CSV 列顺序）：
`ts, service_id, latency_ms, cpu_pct, mem_used_gb, disk_temp_c, net_io_mb_s, power_w`。

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
    "PingFang HK",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False

# 全阶段共用指标口径：列 schema + 物理量程（与 ph18 主文档一致，集中在常量表而非散落代码）
PLATFORM_COLUMNS = (
    "ts",
    "service_id",
    "latency_ms",
    "cpu_pct",
    "mem_used_gb",
    "disk_temp_c",
    "net_io_mb_s",
    "power_w",
)
RANGES: dict[str, tuple[float, float]] = {
    "latency_ms": (0.0, 2000.0),  # 典型 40~90 ms
    "cpu_pct": (0.0, 100.0),  # 典型 55~90%
    "mem_used_gb": (0.0, 256.0),  # 典型 ~96 GB
    "disk_temp_c": (-10.0, 90.0),  # 典型 ~38℃，>75℃ 计过热
    "net_io_mb_s": (0.0, 2000.0),  # 典型 300~450 MB/s
    "power_w": (10.0, 800.0),  # 典型 200~450 W
}
MEMORY_CAPACITY_GB = 256.0  # 内存量程上限，用于换算峰值利用率


def generate_demo_data(seed: int = 42) -> pd.DataFrame:
    """生成模拟平台指标：3 个服务实例、30 秒一条、各 240 行（2 小时）。

    人为注入数据缺陷：3 个缺失延迟 + 2 个量程越界延迟，供 clean() 演示。
    """
    rng = np.random.default_rng(seed)
    frames = []
    for offset, service_id in enumerate(("S001", "S002", "S003")):
        n = 240
        frames.append(
            pd.DataFrame(
                {
                    "ts": pd.date_range("2024-06-01 08:00:00", periods=n, freq="30s"),
                    "service_id": service_id,
                    "latency_ms": rng.normal(65 + offset * 3, 12, n).clip(20, 140),
                    "cpu_pct": np.clip(rng.normal(72 + offset * 2, 8, n), 0, 100),
                    "mem_used_gb": rng.normal(96 + offset * 4, 6, n),
                    "disk_temp_c": rng.normal(38 + offset, 2, n),
                    "net_io_mb_s": rng.normal(380 + offset * 10, 40, n),
                    "power_w": rng.normal(320 + offset * 15, 50, n),
                }
            )
        )
    df = pd.concat(frames, ignore_index=True)
    df.loc[5, "latency_ms"] = np.nan  # 缺失值 1
    df.loc[120, "latency_ms"] = np.nan  # 缺失值 2
    df.loc[250, "latency_ms"] = np.nan  # 缺失值 3
    df.loc[60, "latency_ms"] = 5000.0  # 越界值 1（物理上不可能）
    df.loc[400, "latency_ms"] = 3000.0  # 越界值 2
    return df[list(PLATFORM_COLUMNS)]


def load_metrics(path: str | Path) -> pd.DataFrame:
    """读取平台指标 CSV：service_id 保留字符串，ts 解析为日期时间，并校验列齐全。"""
    df = pd.read_csv(path, dtype={"service_id": str}, parse_dates=["ts"])
    missing = [c for c in PLATFORM_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"平台指标 CSV 缺少列：{missing}（应为 {PLATFORM_COLUMNS}）")
    return df[list(PLATFORM_COLUMNS)]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """清洗四步：缺失值（组内中位数填充）→ 物理量程过滤 → 去重 → 重置索引。

    返回新 DataFrame，不改动入参（呼应主文档 4.3 的复制语义）。
    """
    out = df.copy()
    out["latency_ms"] = out["latency_ms"].fillna(
        out.groupby("service_id")["latency_ms"].transform("median")
    )
    for column, (low, high) in RANGES.items():
        out = out[out[column].between(low, high)]
    out = out.drop_duplicates()
    return out.reset_index(drop=True)


def analyze(df: pd.DataFrame) -> pd.DataFrame:
    """按服务实例分组统计：样本数、延迟均值/峰值、CPU 均值、内存峰值、磁盘温度峰值、平均功率。"""
    stats = (
        df.groupby("service_id")
        .agg(
            samples=("ts", "count"),
            avg_latency_ms=("latency_ms", "mean"),
            max_latency_ms=("latency_ms", "max"),
            avg_cpu_pct=("cpu_pct", "mean"),
            max_mem_used_gb=("mem_used_gb", "max"),
            max_disk_temp_c=("disk_temp_c", "max"),
            avg_power_w=("power_w", "mean"),
        )
        .round(2)
    )
    stats["mem_peak_pct"] = (stats["max_mem_used_gb"] / MEMORY_CAPACITY_GB * 100).round(2)
    return stats.reset_index()


def make_charts(df: pd.DataFrame, outdir: Path) -> list[Path]:
    """两张图：折线趋势（每实例 5 分钟均值延迟）+ 柱状对比（每实例平均延迟）。"""
    ts = df.set_index("ts")
    trend = ts.groupby("service_id")["latency_ms"].resample("5min").mean().unstack(level=0)

    fig, ax = plt.subplots(figsize=(10, 4))
    trend.plot(ax=ax, marker="o", markersize=3)
    ax.set_title("各服务实例延迟趋势（5 分钟均值）")
    ax.set_ylabel("延迟 (ms)")
    ax.legend(title="service_id")
    plt.tight_layout()
    trend_png = outdir / "latency_trend.png"
    fig.savefig(trend_png, dpi=150)
    plt.close(fig)

    avg = df.groupby("service_id")["latency_ms"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(6, 4))
    avg.plot.bar(ax=ax, color="steelblue")
    ax.set_title("各服务实例平均延迟对比")
    ax.set_ylabel("延迟 (ms)")
    ax.set_xlabel("service_id")
    plt.tight_layout()
    compare_png = outdir / "service_compare.png"
    fig.savefig(compare_png, dpi=150)
    plt.close(fig)
    return [trend_png, compare_png]


def export_report(stats: pd.DataFrame, df: pd.DataFrame, outdir: Path) -> list[Path]:
    """导出 Excel（汇总 + 清洗后数据两个 Sheet）与 Markdown 摘要报告。"""
    xlsx = outdir / "metrics_report.xlsx"
    with pd.ExcelWriter(xlsx) as writer:
        stats.to_excel(writer, sheet_name="汇总", index=False)
        df.to_excel(writer, sheet_name="清洗后数据", index=False)
    md = outdir / "metrics_report.md"
    md.write_text(
        "# 平台指标分析报告\n\n"
        "## 按服务实例汇总\n\n"
        + stats.to_markdown(index=False)
        + "\n\n（图表见 latency_trend.png / service_compare.png）",
        encoding="utf-8",
    )
    return [xlsx, md]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="平台指标分析脚本")
    parser.add_argument("--demo", action="store_true", help="用内置模拟数据离线演示完整链路")
    parser.add_argument(
        "--input",
        type=Path,
        help=f"平台指标 CSV（列：{','.join(PLATFORM_COLUMNS)}）",
    )
    parser.add_argument("-o", "--outdir", type=Path, help="产物输出目录（默认系统临时目录）")
    args = parser.parse_args(argv)

    if args.demo:
        raw = generate_demo_data()
        print(f"演示模式：生成平台指标 {len(raw)} 行（含 3 个缺失延迟、2 个越界延迟）")
    elif args.input is not None:
        raw = load_metrics(args.input)
        print(f"读取 {args.input}: {len(raw)} 行")
    else:
        parser.error("必须提供 --input 或 --demo 之一")

    cleaned = clean(raw)
    print(f"清洗后 {len(cleaned)} 行（剔除 {len(raw) - len(cleaned)} 行）")
    stats = analyze(cleaned)
    print("\n按服务实例分组统计:")
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
