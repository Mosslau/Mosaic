# examples/ex04-battery-analysis.py —— 电池数据分析：缺失值插值 + SOC/电压相关 + 散点图
# 验证环境：Python 3.13.9，pandas 2.3.3，numpy 2.3.5，matplotlib 3.10.6
# 运行：python3 ex04-battery-analysis.py（离线可跑，已验证）；PNG 产物写到系统临时目录
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
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex04-"))

    # 1. 构造模拟电池数据：电压随 SOC 近似线性（0.004 V/%），注入噪声与缺失值
    soc = np.arange(0, 101, 1)
    rng = np.random.default_rng(7)
    voltage = 3.0 + soc * 0.004 + rng.normal(0, 0.01, len(soc))
    voltage[[5, 20, 45]] = np.nan  # 挖掉 3 个点模拟采集缺失
    df = pd.DataFrame({"soc": soc, "voltage": voltage})
    print("清洗前缺失数:", int(df["voltage"].isna().sum()))

    # 2. 缺失值处理：线性插值（比填均值更符合电压- SOC 的物理规律）
    df["voltage"] = df["voltage"].interpolate()
    print("插值后缺失数:", int(df["voltage"].isna().sum()))

    # 3. 关联分析：SOC 与电压的相关系数（线性关系的量化证据）
    corr = df["soc"].corr(df["voltage"])
    print("SOC 与电压相关系数:", round(corr, 4))

    # 4. 散点图 + 一次拟合线：服务"SOC 与电压强相关"的结论
    fit = np.polyfit(df["soc"], df["voltage"], 1)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(df["soc"], df["voltage"], s=12, alpha=0.6)
    ax.plot(df["soc"], np.polyval(fit, df["soc"]), "r-", label=f"拟合线 y={fit[0]:.4f}x+{fit[1]:.3f}")
    ax.set_title("电池 SOC-电压 关联")
    ax.set_xlabel("SOC (%)")
    ax.set_ylabel("电压 (V)")
    ax.legend()
    plt.tight_layout()
    out = outdir / "battery_soc_voltage.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
