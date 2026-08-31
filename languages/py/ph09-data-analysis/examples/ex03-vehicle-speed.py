# examples/ex03-vehicle-speed.py —— 车辆速度分析：时间序列 + 异常值过滤 + 趋势图
# 验证环境：Python 3.13.9，pandas 2.3.3，numpy 2.3.5，matplotlib 3.10.6
# 运行：python3 ex03-vehicle-speed.py（离线可跑，已验证）；PNG 产物写到系统临时目录
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退；取列表里第一个已安装的
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False  # 负号用 ASCII，避免字体缺失


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex03-"))

    # 1. 构造模拟遥测数据（30 秒一条），注入 1 个 GPS 跳变异常值（物理上不可能的速度）
    rng = np.random.default_rng(42)
    n = 200
    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-06-01 08:00:00", periods=n, freq="30s"),
            "speed": rng.normal(60, 15, n).clip(0, 120),
        }
    )
    df.loc[50, "speed"] = 320  # 注入异常值

    # 2. 时间列变日期索引（时间序列分析的前提）
    df = df.set_index("time")
    # 3. 过滤异常值：速度物理范围 0~200 km/h
    valid = df[(df["speed"] >= 0) & (df["speed"] <= 200)]
    print("原始行数:", len(df), " 过滤后:", len(valid), " 剔除:", len(df) - len(valid))

    # 4. 降采样看趋势（5 分钟均值）+ 滚动均值平滑
    trend = valid.resample("5min")["speed"].mean()
    smooth = valid["speed"].rolling(10).mean()

    # 5. 折线图：原始 + 5min 均值 + 滚动均值三条序列，服务"速度趋势"结论
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(valid.index, valid["speed"], alpha=0.3, label="原始")
    ax.plot(trend.index, trend, marker="o", label="5min 均值")
    ax.plot(smooth.index, smooth, label="滚动均值(10)")
    ax.set_title("车辆速度趋势")
    ax.set_ylabel("km/h")
    ax.legend()
    plt.tight_layout()
    out = outdir / "speed_trend.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")
    print("平均速度:", round(valid["speed"].mean(), 1), "km/h")


if __name__ == "__main__":
    main()
