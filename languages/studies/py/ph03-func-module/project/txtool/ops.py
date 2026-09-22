# project/txtool/ops.py —— 文本处理纯函数（输入行列表，输出结果，不做 IO）
# 验证环境：Python 3.13.12
# 运行：通过 python3 -m txtool 各子命令调用
# 已验证：本环境经 wc/grep/head/tail 子命令验证

"""文本处理纯函数集合。"""

def count_stats(lines: list[str]) -> dict[str, int]:
    """统计行数、词数、字符数。"""
    words = sum(len(line.split()) for line in lines)
    chars = sum(len(line) for line in lines)
    return {"行数": len(lines), "词数": words, "字符数": chars}

def filter_lines(lines: list[str], keyword: str) -> list[tuple[int, str]]:
    """返回包含 keyword 的 (行号, 内容) 列表，行号从 1 开始。"""
    return [(i, line) for i, line in enumerate(lines, 1) if keyword in line]

def take_first(lines: list[str], n: int) -> list[str]:
    """返回前 n 行。"""
    return lines[:n]

def take_last(lines: list[str], n: int) -> list[str]:
    """返回后 n 行。"""
    return lines[-n:] if n > 0 else []
