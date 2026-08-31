# examples/ex02-sales-analysis.py —— 销售数据分析：读取 → 清洗 → 分组统计 → 柱状图
# 验证环境：Python 3.13.9，pandas 2.3.3，matplotlib 3.10.6
# 运行：python3 ex02-sales-analysis.py（离线可跑，已验证）；CSV/PNG 产物写到系统临时目录
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退；取列表里第一个已安装的
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False  # 负号用 ASCII，避免字体缺失


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex02-"))

    # 1. 构造模拟销售数据（真实场景换成 pd.read_csv("sales.csv")），并落盘供 read_csv 演示
    sales_raw = pd.DataFrame(
        {
            "store": ["东区店"] * 4 + ["西区店"] * 4 + ["南区店"] * 4,
            "month": ["2024-01", "2024-02"] * 6,
            "amount": [120, 135, None, 110, 88, 92, 150, 145, 80, 95, 88, 105],
        }
    )
    csv_path = outdir / "sales.csv"
    sales_raw.to_csv(csv_path, index=False)

    # 2. 读取后第一件事：info()/describe() 摸清类型与空值再动手
    sales = pd.read_csv(csv_path)
    print("读取后 shape:", sales.shape)
    print("amount 缺失:", int(sales["amount"].isna().sum()), " 重复行:", int(sales.duplicated().sum()))

    # 3. 清洗：缺失值填中位数 + 去重
    sales["amount"] = sales["amount"].fillna(sales["amount"].median())
    sales = sales.drop_duplicates()

    # 4. 分组统计：各门店月均销售额（降序）
    avg = sales.groupby("store")["amount"].mean().sort_values(ascending=False)
    print("\n各门店月均销售额（万元）:")
    print(avg.round(1))

    # 5. 透视表：门店 × 月份
    pt = sales.pivot_table(values="amount", index="store", columns="month", aggfunc="mean")
    print("\n透视表（门店 × 月份）:")
    print(pt.round(1))

    # 6. 柱状图：服务"哪家门店卖得好"的结论
    ax = avg.plot.bar(figsize=(6, 4), color="steelblue")
    ax.set_title("门店月均销售额对比")
    ax.set_ylabel("金额（万元）")
    plt.tight_layout()
    out = outdir / "sales_summary.png"
    plt.savefig(out, dpi=150)
    print("\n已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
