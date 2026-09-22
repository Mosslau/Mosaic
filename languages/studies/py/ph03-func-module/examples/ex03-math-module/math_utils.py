# examples/ex03-math-module/math_utils.py —— 数学工具函数集合
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main_math.py
# 已验证：本环境运行输出与注释中期望值一致

"""数学工具函数集合。"""

def is_prime(n):
    """判断 n 是否为质数。"""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

def factorial(n):
    """计算 n 的阶乘（n >= 0）。"""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def primes_up_to(limit):
    """返回 [2, limit] 范围内的所有质数。"""
    return [n for n in range(2, limit + 1) if is_prime(n)]
