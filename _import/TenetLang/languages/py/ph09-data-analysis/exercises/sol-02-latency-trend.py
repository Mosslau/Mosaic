# exercises/sol-02-latency-trend.py —— 练习 2 参考实现：服务延迟趋势分析
# 验证环境：Python 3.13.9；pandas 2.3.3 / numpy 2.3.5 / matplotlib 3.10.6
# 运行：python3 sol-02-latency-trend.py（离线可跑）
# 验证状态：已验证 —— python3 sol-02-latency-trend.py：原始 240 行 → 过滤后 238 行（剔除 2 个越界值）；
#           平均延迟 64.9 ms；latency_trend.png 167366 字节（产物在临时目录）
"""练习 2 参考实现：对 15 秒粒度的延迟序列过滤量程越界点，再降采样看趋势。

与 examples/ex03 同题不同参：240 行（60 分钟）、注入 2 个越界延迟、滚动窗口 12。
口径与 ph18 全阶段一致：延迟量程 0~2000 ms、典型值 40~90 ms。
"""

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

LATENCY_MIN_MS = 0.0  # 延迟物理下限（与 ph18 全阶段指标口径一致）
LATENCY_MAX_MS = 2000.0  # 延迟物理上限


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-sol02-"))

    # 1. 模拟延迟数据：15 秒一条、共 60 分钟；注入 2 个量程越界点（物理上不可能的延迟）
    rng = np.random.default_rng(2024)
    n = 240
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2024-06-01 08:00:00", periods=n, freq="15s"),
            "service_id": "S002",
            "latency_ms": rng.normal(65, 12, n).clip(20, 140),
        }
    )
    df.loc[30, "latency_ms"] = 5000.0  # 注入异常值 1
    df.loc[150, "latency_ms"] = 3000.0  # 注入异常值 2

    # 2. 时间列转日期索引（时间序列分析的前提）
    df = df.set_index("ts")
    # 3. 过滤异常值：延迟物理量程 0~2000 ms
    valid = df[df["latency_ms"].between(LATENCY_MIN_MS, LATENCY_MAX_MS)]
    print("原始行数:", len(df), " 过滤后:", len(valid), " 剔除:", len(df) - len(valid))

    # 4. 降采样看趋势（5 分钟均值）+ 滚动均值平滑（12 个点 = 3 分钟）
    trend = valid["latency_ms"].resample("5min").mean()
    smooth = valid["latency_ms"].rolling(12).mean()

    # 5. 折线图：原始 + 5min 均值 + 滚动均值三条序列，服务"延迟趋势"结论
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(valid.index, valid["latency_ms"], alpha=0.3, label="原始")
    ax.plot(trend.index, trend, marker="o", label="5min 均值")
    ax.plot(smooth.index, smooth, label="滚动均值(12)")
    ax.set_title("服务实例 S002 延迟趋势")
    ax.set_ylabel("延迟 (ms)")
    ax.legend()
    plt.tight_layout()
    out = outdir / "latency_trend.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out, " 存在:", out.exists(), " 大小:", out.stat().st_size, "字节")
    print("平均延迟:", round(valid["latency_ms"].mean(), 1), "ms")


if __name__ == "__main__":
    main()
