# examples/ex05-quality-tools/calc.py —— 主文档 6.5：被测代码
# 验证环境：Python 3.13.9，pytest 8.4.2，ruff 0.12.0，mypy 1.17.1（已验证）
def add(a: int, b: int) -> int:
    return a + b


def parse_speed(raw: str) -> float:
    """解析速度字符串；非法输入抛 ValueError。"""
    value = float(raw)
    if value < 0:
        raise ValueError("speed must be >= 0")
    return value
