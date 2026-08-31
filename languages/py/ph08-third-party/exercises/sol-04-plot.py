# exercises/sol-04-plot.py —— 练习 4 参考实现：画图（matplotlib 折线 + 柱状）
# 验证环境：Python 3.13.9，matplotlib 3.10.6，pandas 2.3.3
# 运行：python3 sol-04-plot.py（离线可跑，已验证）；产物 chart.png 写到当前目录
import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig
import matplotlib.pyplot as plt
import pandas as pd

# 复用练习 3 的统计思路：按车分组的平均速度/电量
df = pd.DataFrame(
    {
        "vehicle_id": ["V001"] * 4 + ["V002"] * 4,
        "time": [1, 2, 3, 4] * 2,
        "speed": [80, 95, 60, 72, 55, 63, 70, 68],
        "soc": [78.5, 76.0, 74.2, 72.8, 90.1, 88.4, 86.0, 85.2],
    }
)
avg = df.groupby("vehicle_id")[["speed", "soc"]].mean()

fig, ax = plt.subplots(1, 2, figsize=(9, 3))

# 左：折线图（多序列 + 图例）
for vid, g in df.groupby("vehicle_id"):
    ax[0].plot(g["time"], g["speed"], marker="o", label=vid)
ax[0].set_title("Speed Trend")
ax[0].set_xlabel("time")
ax[0].set_ylabel("speed")
ax[0].legend()

# 右：柱状图（分组统计结果）
avg.plot.bar(ax=ax[1])
ax[1].set_title("Average by Vehicle")
ax[1].set_xlabel("vehicle_id")

plt.tight_layout()
plt.savefig("chart.png", dpi=150)
print("已保存 chart.png")
