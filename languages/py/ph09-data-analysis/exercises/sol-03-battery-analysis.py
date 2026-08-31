# exercises/sol-03-battery-analysis.py —— 练习 3 参考实现：电池数据分析
# 验证环境：Python 3.13.9；pandas 2.3.3 / numpy 2.3.5 / matplotlib 3.10.6
# 运行：python3 sol-03-battery-analysis.py（离线可跑）
# 验证状态：已验证 —— 实测输出：插值后缺失 0；SOC 与电压相关系数 0.9975；PNG 约 64 KB
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
    outdir = Path(tempfile.mkdtemp(prefix="ph09-sol03-"))

    # 1. 模拟电池数据：电压随 SOC 近似线性（0.0035 V/%），加噪声，挖掉 3 个点
    soc = np.arange(0, 101, 1)
    rng = np.random.default_rng(11)
    voltage = 3.2 + soc * 0.0035 + rng.normal(0, 0.008, len(soc))
    voltage[[8, 33, 77]] = np.nan  # 模拟采集缺失
    df = pd.DataFrame({"soc": soc, "voltage": voltage})
    print("清洗前缺失数:", int(df["voltage"].isna().sum()))

    # 2. 缺失值处理：线性插值（电压随 SOC 变化平滑，比填均值更符合物理规律）
    df["voltage"] = df["voltage"].interpolate()
    print("插值后缺失数:", int(df["voltage"].isna().sum()))

    # 3. 关联分析：相关系数量化"线性相关"的强度与方向
    corr = df["soc"].corr(df["voltage"])
    print("SOC 与电压相关系数:", round(corr, 4))

    # 4. 散点图 + 一次拟合线：服务"SOC 与电压强正相关"的结论
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
    print("已保存:", out, " 存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
