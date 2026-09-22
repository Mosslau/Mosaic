# examples/ex03-math-module/main_math.py —— 数学工具模块入口脚本
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main_math.py
# 已验证：本环境运行输出与注释中期望值一致

import math_utils

print("7 is prime?", math_utils.is_prime(7))    # True
print("10 is prime?", math_utils.is_prime(10))  # False
print("5! =", math_utils.factorial(5))          # 120
print("primes <= 30:", math_utils.primes_up_to(30))
# [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

if __name__ == "__main__":
    print("main_math.py executed directly")
