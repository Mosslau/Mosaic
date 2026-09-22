# examples/ex04-resource-usage.py —— 资源用量分析：缺失值插值 + 分组/透视 + 关联散点图
# 验证环境：Python 3.13.9，pandas 2.3.3，numpy 2.3.5，matplotlib 3.10.6
# 运行：python3 ex04-resource-usage.py（离线可跑）；PNG 产物写到系统临时目录
# 验证状态：已验证 —— python3 ex04-resource-usage.py：缺失 3 处 → 插值后 0；CPU 与内存相关系数
#           0.9874；resource_usage.png 55212 字节（产物在临时目录）
"""平台资源用量分析：3 个服务实例各 15 个采样点的 CPU/内存读数。

对应主文档 3.3 / 3.5 / 3.7 / 3.8：
- 缺失值显式决策：内存读数缺 3 个点，按服务实例分组线性插值（比填均值更符合连续变化）；
- 分组统计：各实例 CPU/内存均值与峰值、内存峰值利用率；
- 透视表：「CPU 档位 × 实例」的内存均值（长表变宽表）；
- 散点图 + 拟合线：CPU 与内存同向变化的关联证据。
口径与 ph18 全阶段一致：CPU 0~100%、内存 0~256 GB（典型 ~96 GB）。
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

MEMORY_CAPACITY_GB = 256.0  # 单实例内存量程上限（与 ph18 全阶段指标口径一致）
CPU_BAND_BINS = [0, 60, 70, 80, 100]  # CPU 档位分箱边界（%）
CPU_BAND_LABELS = ["<60%", "60~70%", "70~80%", "80~100%"]


def build_usage() -> pd.DataFrame:
    """自造 3 个服务实例各 15 个采样点的 CPU/内存读数，注入 3 个缺失内存值。"""
    rng = np.random.default_rng(7)
    frames = []
    for offset, service_id in enumerate(("S001", "S002", "S003")):
        n = 15
        cpu = np.clip(
            np.linspace(55, 90, n) + (offset - 1) * 6 + rng.normal(0, 1.5, n), 0, 100
        )
        mem = 40 + cpu * 0.9 + rng.normal(0, 2.0, n)  # 内存随 CPU 同向变化
        frames.append(
            pd.DataFrame({"service_id": service_id, "cpu_pct": cpu, "mem_used_gb": mem})
        )
    df = pd.concat(frames, ignore_index=True)
    df.loc[[5, 20, 40], "mem_used_gb"] = np.nan  # 模拟采集缺失（均为组内中间点）
    return df


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex04-"))
    df = build_usage()
    print("清洗前缺失数:", int(df["mem_used_gb"].isna().sum()))

    # 1. 缺失值处理：按服务实例分组线性插值，避免跨实例"借"到别的服务的内存水平
    df["mem_used_gb"] = df.groupby("service_id")["mem_used_gb"].transform(
        lambda s: s.interpolate()
    )
    print("插值后缺失数:", int(df["mem_used_gb"].isna().sum()))

    # 2. 分组统计：各实例 CPU/内存均值、峰值，以及内存峰值利用率
    stats = df.groupby("service_id").agg(
        avg_cpu_pct=("cpu_pct", "mean"),
        max_cpu_pct=("cpu_pct", "max"),
        avg_mem_used_gb=("mem_used_gb", "mean"),
        max_mem_used_gb=("mem_used_gb", "max"),
    )
    stats["mem_peak_pct"] = stats["max_mem_used_gb"] / MEMORY_CAPACITY_GB * 100
    print("\n各服务实例资源用量汇总:")
    print(stats.round(2))

    # 3. 透视表：CPU 档位 × 服务实例的内存均值，服务"高负载下谁更吃内存"的结论
    banded = df.copy()
    banded["cpu_band"] = pd.cut(
        banded["cpu_pct"], bins=CPU_BAND_BINS, labels=CPU_BAND_LABELS
    )
    pt = pd.pivot_table(
        banded,
        values="mem_used_gb",
        index="cpu_band",
        columns="service_id",
        aggfunc="mean",
        observed=False,  # 保留全部 CPU 档位（无样本的组合为 NaN），并显式声明分组语义
    )
    print("\nCPU 档位 × 实例 内存均值透视表 (GB):")
    print(pt.round(1))

    # 4. 关联分析：CPU 与内存的相关系数（线性关系的量化证据）
    corr = df["cpu_pct"].corr(df["mem_used_gb"])
    print("\nCPU 与内存相关系数:", round(corr, 4))

    # 5. 散点图 + 一次拟合线：服务"CPU 与内存同向变化"的结论
    fit = np.polyfit(df["cpu_pct"], df["mem_used_gb"], 1)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(df["cpu_pct"], df["mem_used_gb"], s=14, alpha=0.7)
    ax.plot(
        df["cpu_pct"],
        np.polyval(fit, df["cpu_pct"]),
        "r-",
        label=f"拟合线 y={fit[0]:.3f}x+{fit[1]:.2f}",
    )
    ax.set_title("资源用量关联：CPU-内存")
    ax.set_xlabel("CPU 使用率 (%)")
    ax.set_ylabel("内存占用 (GB)")
    ax.legend()
    plt.tight_layout()
    out = outdir / "resource_usage.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
