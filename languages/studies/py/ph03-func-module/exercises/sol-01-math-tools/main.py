# exercises/sol-01-math-tools/main.py —— 数学工具模块入口脚本参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main.py
# 已验证：本环境运行输出与期望一致

import math_tools

if __name__ == "__main__":
    print("is_prime(7) =", math_tools.is_prime(7))      # True
    print("is_prime(10) =", math_tools.is_prime(10))    # False
    print("factorial(5) =", math_tools.factorial(5))    # 120
    print("fibonacci(10) =", math_tools.fibonacci(10))  # 55
