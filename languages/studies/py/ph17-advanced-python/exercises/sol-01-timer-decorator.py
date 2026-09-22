#!/usr/bin/env python3
# exercises/sol-01-timer-decorator.py —— 练习 1 参考实现：计时装饰器（累计次数与耗时）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 sol-01-timer-decorator.py（main 自检，断言失败退出码非 0）
# 测试：python3 -m pytest sol-01-timer-decorator.py -q（收集 test_* 跑断言）
# lint：ruff check sol-01-timer-decorator.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""练习 1 参考实现：@timed 与 @timed(unit=...) 双形态计时装饰器。

教学点：闭包捕获状态（calls/total_time 挂在 wrapper 上，而非全局）；
functools.wraps 保函数身份；finally 保证异常路径也计时。
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class TimedFunc:
    """把「函数 + 累计状态」打包成可调用对象，便于暴露 calls/total_time 属性。"""

    def __init__(self, func: Callable[P, T], unit: str) -> None:
        functools.update_wrapper(self, func)
        self.func = func
        self.unit = unit
        self.calls = 0
        self.total_time = 0.0

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        try:
            return self.func(*args, **kwargs)
        finally:
            self.calls += 1
            self.total_time += time.perf_counter() - start

    def reset(self) -> None:
        self.calls = 0
        self.total_time = 0.0


def timed(func: Callable[P, T] | None = None, *, unit: str = "s") -> Any:
    """双形态入口：@timed 直接吃函数；@timed(unit="ms") 先收配置再收函数。"""

    def decorate(f: Callable[P, T]) -> TimedFunc:
        return TimedFunc(f, unit)

    if func is not None:  # @timed 形态：func 就是被装饰函数
        return decorate(func)
    return decorate  # @timed(unit=...) 形态：返回装饰器


@timed
def add(a: int, b: int) -> int:
    """两数相加（计时装饰器演示）。"""
    return a + b


@timed(unit="ms")
def flaky_add(a: int, b: int) -> int:
    """抛异常也要计时的演示。"""
    raise RuntimeError("boom")


def test_plain_usage_counts_and_time() -> None:
    add.reset()
    assert add(1, 2) == 3
    assert add(2, 3) == 5
    assert add(3, 4) == 7
    assert add.calls == 3  # 累计调用次数
    assert add.total_time > 0  # 累计耗时（真实执行必有微小耗时）
    assert add.__name__ == "add"  # wraps 保住了函数名
    add.reset()
    assert add.calls == 0 and add.total_time == 0.0


def test_exception_still_timed() -> None:
    flaky_add.reset()
    try:
        flaky_add(1, 2)
    except RuntimeError:
        pass
    else:
        raise AssertionError("必须抛 RuntimeError")
    assert flaky_add.calls == 1  # 异常路径也计入
    assert flaky_add.total_time > 0
    assert flaky_add.unit == "ms"  # 带参形态生效


def main() -> None:
    print("== 练习 1 自检 ==")
    add.reset()
    print("add(1,2) =", add(1, 2), "| add(2,3) =", add(2, 3))
    print(f"calls = {add.calls}, total_time = {add.total_time:.6f}s, __name__ = {add.__name__}")
    try:
        flaky_add(1, 1)
    except RuntimeError:
        print(f"异常路径计入：calls = {flaky_add.calls}, unit = {flaky_add.unit}")
    test_plain_usage_counts_and_time()
    test_exception_still_timed()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
