#!/usr/bin/env python3
# exercises/sol-02-retry-decorator.py —— 练习 2 参考实现：带参重试装饰器
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 sol-02-retry-decorator.py（main 自检，断言失败退出码非 0）
# 测试：python3 -m pytest sol-02-retry-decorator.py -q（收集 test_* 跑断言）
# lint：ruff check sol-02-retry-decorator.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""练习 2 参考实现：@retry(times=3, delay=0, exceptions=(ConnectionError,))。

教学点：三层嵌套（配置 → 装饰器 → wrapper）；白名单异常才重试；
重试耗尽后抛最后一次异常；last_error 记录失败原因。
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def retry(
    times: int = 3,
    delay: float = 0.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """带参重试装饰器：白名单 exceptions 内的异常才重试，其余立即抛出。"""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            wrapper.last_error = None  # 每次调用重置记录
            last: BaseException | None = None
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last = exc
                    wrapper.last_error = exc
                    if attempt < times - 1:
                        time.sleep(delay)  # 重试间隔（测试里传 delay=0 免等）
            assert last is not None
            raise last  # 重试耗尽：抛最后一次异常

        wrapper.last_error: BaseException | None = None  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


@retry(times=3, delay=0, exceptions=(ConnectionError,))
def flaky_fetch() -> str:
    """前两次抛 ConnectionError，第三次成功。"""
    flaky_fetch.attempts = getattr(flaky_fetch, "attempts", 0) + 1
    if flaky_fetch.attempts < 3:
        raise ConnectionError("transient network")
    return "payload"


@retry(times=3, delay=0, exceptions=(ConnectionError,))
def never_ok() -> str:
    raise ConnectionError("always down")


def test_retry_eventually_succeeds() -> None:
    flaky_fetch.attempts = 0
    assert flaky_fetch() == "payload"  # 第三次成功
    assert flaky_fetch.attempts == 3  # 正好试了 3 次


def test_retry_exhausted_raises_last() -> None:
    try:
        never_ok()
    except ConnectionError as exc:
        assert isinstance(exc, ConnectionError)
        assert never_ok.last_error is exc  # 记录了最后一次失败
    else:
        raise AssertionError("耗尽后必须抛 ConnectionError")


def test_out_of_whitelist_immediate() -> None:
    """白名单外异常立即抛出：装饰器一次都不重试（只调用 1 次）。"""
    calls: list[int] = []

    @retry(times=5, delay=0, exceptions=(ConnectionError,))
    def bad() -> str:
        calls.append(1)
        raise ValueError("not retryable")

    try:
        bad()
    except ValueError:
        pass
    else:
        raise AssertionError("白名单外必须立即抛出")
    assert len(calls) == 1  # 只调用了一次 → 未重试


def main() -> None:
    print("== 练习 2 自检 ==")
    flaky_fetch.attempts = 0
    print("flaky_fetch() =", flaky_fetch(), f"（尝试次数 {flaky_fetch.attempts}）")
    try:
        never_ok()
    except ConnectionError as exc:
        print(
            "never_ok() 耗尽后抛:",
            type(exc).__name__,
            "| last_error 已记录:",
            never_ok.last_error is exc,
        )
    test_retry_eventually_succeeds()
    test_retry_exhausted_raises_last()
    test_out_of_whitelist_immediate()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
