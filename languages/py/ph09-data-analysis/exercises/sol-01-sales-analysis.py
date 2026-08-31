# exercises/sol-01-sales-analysis.py —— 练习 1 参考实现：销售数据分析
# 验证环境：Python 3.13.9；pandas 2.3.3 / matplotlib 3.10.6
# 运行：python3 sol-01-sales-analysis.py（离线可跑）
# 验证状态：已验证 —— 实测输出：缺失 1、重复行 1；月均销售额降序 华东店 144.4 / 华北店 123.2 / 华南店 102.0；
#           透视表（华东店 2024-01=136.2 / 2024-02=152.5 ...）；PNG 约 24 KB，产物在临时目录
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-sol01-"))

    # 1. 自造销售数据：含 1 个缺失值 + 1 个重复行（真实场景换成 read_csv）
    sales = pd.DataFrame(
        {
            "store": ["华东店", "华东店", "华东店", "华东店", "华南店", "华南店",
                      "华南店", "华南店", "华北店", "华北店", "华北店", "华北店", "华北店"],
            "month": ["2024-01", "2024-02", "2024-01", "2024-02"] * 3 + ["2024-02"],
            "amount": [150, 160, None, 145, 98, 105, 95, 110, 120, 130, 118, 125, 125],
        }
    )

    # 2. 动手前先摸清数据：类型与空值
    print(sales.info())
    print("缺失:", int(sales["amount"].isna().sum()), " 重复行:", int(sales.duplicated().sum()))

    # 3. 清洗：缺失值显式决策（填中位数）+ 去重
    sales["amount"] = sales["amount"].fillna(sales["amount"].median())
    sales = sales.drop_duplicates()

    # 4. 分组统计：各门店月均销售额（降序）
    avg = sales.groupby("store")["amount"].mean().sort_values(ascending=False)
    print("\n各门店月均销售额（万元）:")
    print(avg.round(1))

    # 5. 透视表：门店 × 月份
    pt = pd.pivot_table(sales, values="amount", index="store", columns="month", aggfunc="mean")
    print("\n透视表（门店 × 月份）:")
    print(pt.round(1))

    # 6. 柱状图：服务"哪家门店卖得好"的结论
    avg.plot.bar(figsize=(6, 4), color="steelblue")
    plt.title("各门店月均销售额对比")
    plt.ylabel("金额（万元）")
    plt.tight_layout()
    out = outdir / "sales_summary.png"
    plt.savefig(out, dpi=150)
    print("\n已保存:", out, " 存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
