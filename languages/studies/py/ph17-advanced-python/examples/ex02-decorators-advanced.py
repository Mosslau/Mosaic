#!/usr/bin/env python3
# examples/ex02-decorators-advanced.py —— 装饰器进阶（主文档 3.3）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 ex02-decorators-advanced.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex02-decorators-advanced.py -q（收集 test_* 跑断言）
# lint：ruff check ex02-decorators-advanced.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""闭包、functools.wraps、带参装饰器、叠加顺序、类装饰器与标准库装饰器家族。"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def make_counter(start: int = 0) -> Callable[[], int]:
    """闭包：外层局部变量被内层函数捕获，函数返回后仍存活（cell 对象）。"""
    count = start

    def bump() -> int:
        nonlocal count  # 需要改写捕获变量时声明 nonlocal
        count += 1
        return count

    return bump


def timer(func: Callable[P, T]) -> Callable[P, T]:
    """计时装饰器：functools.wraps 保持函数身份。"""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"{func.__name__} took {time.perf_counter() - start:.6f}s")

    return wrapper


def bare_timer(func: Callable[P, T]) -> Callable[P, T]:
    """计时装饰器（故意省略 wraps）：演示函数身份被破坏的后果。"""

    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:  # type: ignore[no-any-return]
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"{func.__name__} took {time.perf_counter() - start:.6f}s")

    return wrapper


def retry(times: int = 3, allowed: tuple[type[Exception], ...] = (Exception,)):
    """带参装饰器：@retry(times=3) 先返回真正的装饰器，再应用它。"""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last: Exception | None = None
            for _attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except allowed as exc:
                    last = exc  # 白名单内 → 继续重试
            assert last is not None
            raise last  # 全部重试失败 → 原样抛出

        return wrapper

    return decorator


def log_calls(func: Callable[P, T]) -> Callable[P, T]:
    """日志装饰器：与 timer 叠加演示「从下往上应用、从上往下包裹」。"""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        print(f"call {func.__name__}{args!r}")
        return func(*args, **kwargs)

    return wrapper


class CountCalls:
    """类装饰器（可调用对象）：保存跨调用状态。"""

    def __init__(self, func: Callable[P, T]) -> None:
        functools.update_wrapper(self, func)  # 类实例模仿函数身份
        self.func = func
        self.count = 0

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        self.count += 1
        return self.func(*args, **kwargs)


@functools.cache
def fib_cached(n: int) -> int:
    """记忆化 Fibonacci：lru_cache 缓存让指数递归变线性（ph06 见过用法，这里看缓存统计）。"""
    return n if n < 2 else fib_cached(n - 1) + fib_cached(n - 2)


@timer
def slow_add(a: int, b: int) -> int:
    """把两个数相加（计时装饰器演示用）。"""
    time.sleep(0.001)
    return a + b


@bare_timer
def bare_add(a: int, b: int) -> int:
    """演示无 wraps 时的身份问题。"""
    return a + b


@retry(times=3, allowed=(ValueError,))
def flaky() -> str:
    """前两次抛 ValueError，第三次成功——重试装饰器演示。"""
    flaky.attempts = getattr(flaky, "attempts", 0) + 1
    if flaky.attempts < 3:
        raise ValueError("transient")
    return "ok"


@CountCalls
def ping() -> str:
    return "pong"


def test_wraps_preserves_identity() -> None:
    assert slow_add.__name__ == "slow_add"  # @wraps 保留了名字
    assert "相加" in slow_add.__doc__ or slow_add.__doc__ is not None
    assert bare_add.__name__ == "wrapper"  # 无 wraps：名字被污染
    assert hasattr(slow_add, "__wrapped__")  # wraps 记录原函数


def test_closure_counter() -> None:
    c1, c2 = make_counter(), make_counter(10)
    assert c1() == 1 and c1() == 2  # 各自独立的捕获变量
    assert c2() == 11


def test_parameterized_decorator() -> None:
    flaky.attempts = 0
    assert flaky() == "ok"  # 第三次成功
    flaky.attempts = 0


def test_exhausted_retry_raises() -> None:
    @retry(times=2)
    def always_bad() -> None:
        raise RuntimeError("boom")

    try:
        always_bad()
    except RuntimeError:
        pass
    else:
        raise AssertionError("retry 耗尽后必须抛出原异常")


def test_class_decorator_state() -> None:
    ping.count = 0  # 重置，兼容脚本先演示再断言的运行态
    assert ping() == "pong" and ping() == "pong"
    assert ping.count == 2  # 状态在实例上累积


def test_lru_cache_stats() -> None:
    assert fib_cached(30) == 832040
    info = fib_cached.cache_info()
    assert info.hits > 0 and info.currsize > 0  # 缓存真的在工作


def main() -> None:
    print("== 闭包 ==")
    c1 = make_counter()
    print("c1():", c1(), "| c1():", c1())
    print("== wraps 的作用 ==")
    print("slow_add.__name__ =", slow_add.__name__)
    print("bare_add.__name__ =", bare_add.__name__, "（无 wraps 被污染）")
    print("== 装饰器叠加（从下往上应用）==")

    @log_calls
    @timer
    def stacked(x: int) -> int:
        return x + 1

    print("stacked(1) =", stacked(1))
    print("== 带参装饰器（重试）==")
    flaky.attempts = 0
    print("flaky() =", flaky())
    print("== 类装饰器（调用计数）==")
    print("ping():", ping(), "| ping():", ping(), "| count =", ping.count)
    print("== functools.singledispatch：按首参类型分派 ==")

    @functools.singledispatch
    def describe(value: Any) -> str:
        return f"unknown:{type(value).__name__}"

    @describe.register
    def describe_int(value: int) -> str:
        return f"int:{value}"

    @describe.register
    def describe_str(value: str) -> str:
        return f"str:{value}"

    print(describe(42), "|", describe("hi"), "|", describe(1.5))
    print("== functools.lru_cache：缓存统计 ==")
    print("fib_cached(30) =", fib_cached(30))
    print("cache_info =", fib_cached.cache_info())
    test_wraps_preserves_identity()
    test_closure_counter()
    test_parameterized_decorator()
    test_exhausted_retry_raises()
    test_class_decorator_state()
    test_lru_cache_stats()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
