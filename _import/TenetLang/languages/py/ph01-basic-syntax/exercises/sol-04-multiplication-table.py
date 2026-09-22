# exercises/sol-04-multiplication-table.py —— 九九乘法表
# 验证环境：Python 3.13.12（macOS）
# 运行：python3 sol-04-multiplication-table.py
# 验证状态：已验证

for i in range(1, 10):
    for j in range(1, i + 1):
        print(f"{j}×{i}={i*j:<2}", end="  ")
    print()
