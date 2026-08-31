# exercises/sol-02-vehicle-speed.py —— 练习 2 参考实现：车辆速度分析
# 验证环境：Python 3.13.9；pandas 2.3.3 / numpy 2.3.5 / matplotlib 3.10.6
# 运行：python3 sol-02-vehicle-speed.py（离线可跑）
# 验证状态：已验证 —— 实测输出：原始 240 行 → 过滤后 238 行（剔除 2 个异常值）；平均速度 59.8 km/h；PNG 约 161 KB
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


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-sol02-"))

    # 1. 模拟遥测数据：15 秒一条，共 60 分钟；注入 2 个 GPS 跳变异常值（物理上不可能的速度）
    rng = np.random.default_rng(2024)
    n = 240
    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-06-01 08:00:00", periods=n, freq="15s"),
            "speed": rng.normal(60, 15, n).clip(0, 120),
        }
    )
    df.loc[30, "speed"] = 320  # 注入异常值 1
    df.loc[150, "speed"] = 280  # 注入异常值 2

    # 2. 时间列转日期索引（时间序列分析的前提）
    df = df.set_index("time")
    # 3. 过滤异常值：速度物理范围 0~200 km/h
    valid = df[(df["speed"] >= 0) & (df["speed"] <= 200)]
    print("原始行数:", len(df), " 过滤后:", len(valid), " 剔除:", len(df) - len(valid))

    # 4. 降采样看趋势（5 分钟均值）+ 滚动均值平滑（12 个点 ≈ 3 分钟）
    trend = valid.resample("5min")["speed"].mean()
    smooth = valid["speed"].rolling(12).mean()

    # 5. 折线图：原始 + 5min 均值 + 滚动均值三条序列，服务"速度趋势"结论
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(valid.index, valid["speed"], alpha=0.3, label="原始")
    ax.plot(trend.index, trend, marker="o", label="5min 均值")
    ax.plot(smooth.index, smooth, label="滚动均值(12)")
    ax.set_title("车辆速度趋势")
    ax.set_ylabel("km/h")
    ax.legend()
    plt.tight_layout()
    out = outdir / "speed_trend.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out, " 存在:", out.exists(), " 大小:", out.stat().st_size, "字节")
    print("平均速度:", round(valid["speed"].mean(), 1), "km/h")


if __name__ == "__main__":
    main()
