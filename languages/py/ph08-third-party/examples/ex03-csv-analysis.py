# examples/ex03-csv-analysis.py —— 主文档 6.3：CSV 数据分析（pandas + groupby + matplotlib 出图）
# 验证环境：Python 3.13.9，pandas 2.3.3，matplotlib 3.10.6
# 运行：python3 ex03-csv-analysis.py（离线可跑，已验证）；产物 vehicle.csv 与 vehicle_analysis.png 写到当前目录
import matplotlib

matplotlib.use("Agg")  # 无显示环境（服务器/CI）也能 savefig
import matplotlib.pyplot as plt
import pandas as pd

# 1. 生成模拟车辆数据 CSV（真实场景换成 pd.read_csv("你的文件.csv")）
data = pd.DataFrame(
    {
        "vehicle_id": ["V001"] * 4 + ["V002"] * 4,
        "time": [1, 2, 3, 4] * 2,
        "speed": [80, 95, 60, 72, 55, 63, 70, 68],
        "soc": [78.5, 76.0, 74.2, 72.8, 90.1, 88.4, 86.0, 85.2],
    }
)
data.to_csv("vehicle.csv", index=False)

# 2. pandas 读取 + 分组统计
df = pd.read_csv("vehicle.csv")
print(df.info())
avg = df.groupby("vehicle_id")[["speed", "soc"]].mean()
print(avg)

# 3. matplotlib 出图：左折线、右柱状
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
for vid, g in df.groupby("vehicle_id"):
    ax[0].plot(g["time"], g["speed"], marker="o", label=vid)
avg.plot.bar(ax=ax[1])
ax[0].set_title("Speed Trend")
ax[0].set_xlabel("time")
ax[0].legend()
plt.tight_layout()
plt.savefig("vehicle_analysis.png", dpi=150)
print("已保存 vehicle_analysis.png")
