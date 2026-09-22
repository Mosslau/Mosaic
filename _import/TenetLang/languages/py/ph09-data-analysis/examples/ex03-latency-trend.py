# examples/ex03-latency-trend.py —— 延迟趋势分析：时间序列 + 异常值过滤 + 趋势图
# 验证环境：Python 3.13.9，pandas 2.3.3，numpy 2.3.5，matplotlib 3.10.6
# 运行：python3 ex03-latency-trend.py（离线可跑）；PNG 产物写到系统临时目录
# 验证状态：已验证 —— python3 ex03-latency-trend.py：原始 200 行 → 过滤后 199 行（剔除 1 个 5000 ms
#           越界值）；平均延迟 64.6 ms；latency_trend.png 157823 字节（产物在临时目录）
"""平台服务延迟趋势分析：一条 30 秒粒度的延迟序列，注入一个量程越界点。

对应主文档 3.7 与第 6 章「示例 2」：`set_index` 转日期索引 → 物理量程过滤异常值 →
`resample` 降采样 + `rolling` 滚动均值平滑 → 三条曲线对比看趋势。
口径与 ph18 全阶段一致：延迟量程 0~2000 ms、典型值 40~90 ms。
"""

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退；取列表里第一个已安装的
plt.rcParams["font.sans-serif"] = [
    "PingFang HK",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False  # 负号用 ASCII，避免字体缺失

LATENCY_MIN_MS = 0.0  # 延迟物理下限（与 ph18 全阶段指标口径一致）
LATENCY_MAX_MS = 2000.0  # 延迟物理上限：超过即采集/换算异常


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex03-"))

    # 1. 构造模拟延迟序列（30 秒一条，典型量程 40~90 ms），注入 1 个量程越界点
    rng = np.random.default_rng(42)
    n = 200
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2024-06-01 08:00:00", periods=n, freq="30s"),
            "service_id": "S001",
            "latency_ms": rng.normal(65, 12, n).clip(20, 140),
        }
    )
    df.loc[50, "latency_ms"] = 5000.0  # 注入异常值（物理上不可能的延迟）

    # 2. 时间列变日期索引（时间序列分析的前提）
    df = df.set_index("ts")
    # 3. 过滤异常值：延迟物理量程 0~2000 ms
    valid = df[df["latency_ms"].between(LATENCY_MIN_MS, LATENCY_MAX_MS)]
    print("原始行数:", len(df), " 过滤后:", len(valid), " 剔除:", len(df) - len(valid))

    # 4. 降采样看趋势（5 分钟均值）+ 滚动均值平滑
    trend = valid["latency_ms"].resample("5min").mean()
    smooth = valid["latency_ms"].rolling(10).mean()

    # 5. 折线图：原始 + 5min 均值 + 滚动均值三条序列，服务"延迟趋势"结论
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(valid.index, valid["latency_ms"], alpha=0.3, label="原始")
    ax.plot(trend.index, trend, marker="o", label="5min 均值")
    ax.plot(smooth.index, smooth, label="滚动均值(10)")
    ax.set_title("服务实例 S001 延迟趋势")
    ax.set_ylabel("延迟 (ms)")
    ax.legend()
    plt.tight_layout()
    out = outdir / "latency_trend.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")
    print("平均延迟:", round(valid["latency_ms"].mean(), 1), "ms")


if __name__ == "__main__":
    main()
