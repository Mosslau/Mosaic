"""关联规则 — 暴力枚举基线（小数据对账）。"""

from __future__ import annotations

from impl import brute_force


def run_baseline(transactions, min_support=0.05, max_len=3):
    return brute_force(transactions, min_support, max_len)


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，由 demo.py 调用")
