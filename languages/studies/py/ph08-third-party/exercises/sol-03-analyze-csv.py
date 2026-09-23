# exercises/sol-03-analyze-csv.py —— 练习 3 参考实现：分析 CSV（pandas 筛选 + groupby）
# 验证环境：Python 3.13.9，pandas 2.3.3
# 运行：python3 sol-03-analyze-csv.py（离线可跑，已验证）；产物 result.csv 写到当前目录
import pandas as pd

# 1. 造一份输入 CSV（真实场景换成自己的文件）
pd.DataFrame(
    {
        "device_id": ["V001"] * 4 + ["V002"] * 4,
        "time": [1, 2, 3, 4] * 2,
        "speed": [80, 95, 60, 72, 55, 63, 70, 68],
        "soc": [78.5, 76.0, 74.2, 72.8, 90.1, 88.4, 86.0, 85.2],
    }
).to_csv("input.csv", index=False)

# 2. 读取 → 看类型 → 布尔筛选 → 分组统计
df = pd.read_csv("input.csv")
print(df.info())

fast = df[df["speed"] > 70].reset_index(drop=True)  # 筛选后恢复连续索引
print("\nspeed > 70 的记录:")
print(fast)

summary = df.groupby("device_id").agg(
    avg_speed=("speed", "mean"),
    max_speed=("speed", "max"),
    samples=("speed", "count"),
)
print("\n按设备分组统计:")
print(summary)

# 3. 输出（题目要求 index=False：先 reset_index() 把 device_id 从索引变回普通列，再写）
summary.reset_index().to_csv("result.csv", index=False)
print("\n已写入 result.csv")
