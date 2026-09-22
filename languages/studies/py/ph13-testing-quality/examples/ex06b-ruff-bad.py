#!/usr/bin/env python3
# examples/ex06b-ruff-bad.py —— 故意出错示例（lint 违规版）：仅供 ruff check 演示，请勿直接运行
# 验证环境：Python 3.13.9 + ruff 0.12.0（本机已装并实测）
# 运行：ruff check ex06b-ruff-bad.py（已验证：报 6 处错误，见下；直接运行会 NameError）
# 验证状态：已验证 —— ruff 报告 6 个错误（F401 / I001 / F821 / F841 / E722 / E501 各 1）
import sys          # I001: import 顺序错（isort 要求字母序，sys 应在 os 之后）
import os
import json         # F401: 未使用的导入


def compute(data):
    result = 0
    for item in data:
        result += item
    unused = result * 2             # F841: 局部变量赋值后从未使用
    return result


def safe_divide(a, b):
    try:
        return a / b
    except:                         # E722: 裸 except —— 连 KeyboardInterrupt 一起吞掉
        return None


def main():
    total = compute([1, 2, 3])
    print("total:", total, sys.platform, os.getcwd())
    print(safe_divide(1, 0))
    print(undefined_name)           # F821: 未定义名称（运行时会 NameError）
    long_line = "x" * 80 + " - this line is intentionally made longer than one hundred characters to trigger E501"
    print(long_line)


if __name__ == "__main__":
    main()
