# exercises/sol-01-math-tools/math_tools.py —— 数学工具模块参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main.py
# 已验证：本环境运行输出与期望一致

"""数学工具函数集合。"""

def is_prime(n: int) -> bool:
    """判断 n 是否为质数。"""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

def factorial(n: int) -> int:
    """计算 n 的阶乘（n >= 0）。"""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def fibonacci(n: int) -> int:
    """返回第 n 项斐波那契数：F(0)=0, F(1)=1。"""
    if n < 0:
        raise ValueError("n 不能为负")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
