#!/usr/bin/env python3
# examples/ex03-context-managers.py —— 上下文管理器协议与 contextlib（主文档 3.4）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 ex03-context-managers.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex03-context-managers.py -q（收集 test_* 跑断言）
# lint：ruff check ex03-context-managers.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""上下文管理器协议（异常三态）、@contextmanager、ExitStack、suppress 与事务形态。"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator


class ManagedFile:
    """协议最小形态（主文档 3.4 摘录于此）：__enter__ 拿资源、__exit__ 必释放。

    用法：with ManagedFile("app.log") as fh: ... —— 本示例不实际打开文件
    （避免落盘产物，见 examples/README 产物纪律），语义由下方
    Timer/Transaction/Swallow 的同类协议实测。
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self):
        self.f = open(self.path)
        return self.f  # as 绑定的是 __enter__ 的返回值

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.f.close()
        return False  # False：异常继续传播；True：吞掉异常


class Timer:
    """类形态上下文管理器：__enter__ 记录起点，__exit__ 打印耗时。"""

    def __init__(self, label: str) -> None:
        self.label = label
        self.elapsed: float | None = None

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self  # as 绑定 __enter__ 的返回值

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.elapsed = time.perf_counter() - self._start
        print(f"[{self.label}] took {self.elapsed:.4f}s")
        return False  # False：不吞异常，异常照常传播


class Transaction:
    """事务语义：__exit__ 看有没有异常决定 commit / rollback。"""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> Transaction:
        print("BEGIN")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self.committed = True
            print("COMMIT")
        else:
            self.rolled_back = True
            print(f"ROLLBACK ({exc_type.__name__})")
        return False  # 事务层不吞业务异常


class Swallow:
    """__exit__ 返回 True：吞掉块内异常。"""

    def __enter__(self) -> Swallow:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        print(f"suppress {exc_type.__name__ if exc_type else 'None'}")
        return True


@contextlib.contextmanager
def timer_cm(label: str) -> Iterator[None]:
    """@contextmanager 形态：yield 前是 __enter__，yield 后是 __exit__。"""
    start = time.perf_counter()
    try:
        yield  # 块内异常在此处被抛出
    finally:
        print(f"[{label}] took {time.perf_counter() - start:.4f}s")


@contextlib.contextmanager
def rollback_on_error() -> Iterator[None]:
    """@contextmanager 里用 try/except 决定吞还是抛：等价于类形态的 __exit__ 返回值。"""
    print("acquire resource")
    try:
        yield
    except Exception as exc:
        print(f"rollback after {type(exc).__name__}")
        raise  # 重新抛出 → 调用方仍看得到异常


def test_exception_propagation() -> None:
    """默认（返回 False）异常传播；Swallow 吞掉。"""
    with Timer("ok"):
        pass
    try:
        with Timer("boom"):
            raise ValueError("x")
    except ValueError:
        pass
    else:
        raise AssertionError("异常必须传播")
    with Swallow():
        raise ValueError("y")  # 被吞：不会走到 except
    print("Swallow swallowed ok")


def test_transaction_semantics() -> None:
    """commit / rollback 由 exc_type 是否为 None 决定。"""
    with Transaction() as tx:
        pass
    assert tx.committed and not tx.rolled_back

    try:
        with Transaction() as tx2:
            raise KeyError("missing")
    except KeyError:
        pass
    assert tx2.rolled_back and not tx2.committed


def test_contextmanager_form() -> None:
    with timer_cm("cm"):
        time.sleep(0.001)
    try:
        with rollback_on_error():
            raise OSError("io failed")
    except OSError:
        pass
    else:
        raise AssertionError("rollback_on_error 必须重新抛出异常")


def test_exitstack_and_suppress() -> None:
    """ExitStack 动态管理多个上下文管理器；suppress 显式吞指定异常。"""
    events: list[str] = []

    class Item:
        def __init__(self, name: str) -> None:
            self.name = name

        def __enter__(self) -> Item:
            events.append(f"enter:{self.name}")
            return self

        def __exit__(self, *exc_info) -> bool:
            events.append(f"exit:{self.name}")
            return False

    with contextlib.ExitStack() as stack:
        for name in ("a", "b", "c"):
            stack.enter_context(Item(name))
    assert events == [
        "enter:a",
        "enter:b",
        "enter:c",
        "exit:c",
        "exit:b",
        "exit:a",  # 后进先出
    ]

    with contextlib.suppress(ValueError):
        raise ValueError("ignored")  # 不用再写 try/except: pass
    with contextlib.suppress(FileNotFoundError):
        open("/no/such/file").close()  # type: ignore[attr-defined]


def main() -> None:
    print("== 类形态上下文管理器（异常三态）==")
    with Timer("sleep"):
        time.sleep(0.01)
    try:
        with Timer("boom"):
            raise ValueError("演示异常传播")
    except ValueError:
        print("ValueError 传播到外层 ✓")
    print("== 事务语义 ==")
    with Transaction():
        pass
    try:
        with Transaction():
            raise KeyError("模拟业务失败")
    except KeyError:
        print("KeyError 传播 ✓（事务已 ROLLBACK）")
    print("== @contextmanager 形态 ==")
    with timer_cm("cm"):
        time.sleep(0.01)
    print("== ExitStack 后进先出 ==")
    with contextlib.ExitStack() as stack:
        for i in range(3):
            stack.enter_context(contextlib.nullcontext(f"ctx{i}"))
    print("== suppress ==")
    with contextlib.suppress(ValueError):
        raise ValueError("被 suppress 吞掉")
    print("== redirect_stdout：块内捕获打印 ==")
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print("hidden output")
    print("捕获到:", repr(buf.getvalue().strip()))
    print("== closing：退出时调 close（对没有 __enter__ 的资源）==")
    sink = io.StringIO()
    with contextlib.closing(sink) as buf2:
        buf2.write("buffered text")
        content = buf2.getvalue()  # 关闭前取内容（关闭后不可再读）
    print("已关闭:", sink.closed, "| 内容:", repr(content))
    test_exception_propagation()
    test_transaction_semantics()
    test_contextmanager_form()
    test_exitstack_and_suppress()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
