#!/usr/bin/env python3
# exercises/sol-03-context-manager.py —— 练习 3 参考实现：事务语义上下文管理器
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 sol-03-context-manager.py（main 自检，断言失败退出码非 0）
# 测试：python3 -m pytest sol-03-context-manager.py -q（收集 test_* 跑断言）
# lint：ruff check sol-03-context-manager.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""练习 3 参考实现：类形态 + @contextmanager 形态的事务上下文管理器。

教学点：__exit__ 靠 exc_type 是否为 None 区分 commit/rollback；
@contextmanager 里 try/except 包住 yield 对齐「吞还是抛」语义。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator


class FakeConn:
    """假连接：只记录操作序列，便于断言事务路径。"""

    def __init__(self) -> None:
        self.operations: list[str] = []

    def begin(self) -> None:
        self.operations.append("begin")

    def commit(self) -> None:
        self.operations.append("commit")

    def rollback(self) -> None:
        self.operations.append("rollback")


class Transaction:
    """类形态：__enter__ 开事务；__exit__ 按异常有无决定 commit/rollback。"""

    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    def __enter__(self) -> Transaction:
        self.conn.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False  # 不吞业务异常：调用方仍看得到


@contextlib.contextmanager
def transaction_cm(conn: FakeConn) -> Iterator[None]:
    """@contextmanager 形态：语义与类形态等价。"""
    conn.begin()
    try:
        yield
    except Exception:
        conn.rollback()
        raise  # 重新抛出 → 与类形态的 return False 对齐
    else:
        conn.commit()


def test_commit_path() -> None:
    conn = FakeConn()
    with Transaction(conn):
        pass  # 正常路径
    assert conn.operations == ["begin", "commit"]


def test_rollback_path_and_propagation() -> None:
    conn = FakeConn()
    try:
        with Transaction(conn):
            raise KeyError("boom")
    except KeyError:
        pass
    else:
        raise AssertionError("异常必须传播到 with 之外")
    assert conn.operations == ["begin", "rollback"]


def test_contextmanager_form_matches() -> None:
    ok_conn = FakeConn()
    with transaction_cm(ok_conn):
        pass
    assert ok_conn.operations == ["begin", "commit"]

    bad_conn = FakeConn()
    try:
        with transaction_cm(bad_conn):
            raise ValueError("nope")
    except ValueError:
        pass
    else:
        raise AssertionError("@contextmanager 形态也必须传播异常")
    assert bad_conn.operations == ["begin", "rollback"]


def test_exitstack_manages_multiple() -> None:
    """加分项：ExitStack 同时管「日志文件」与「事务」两个资源。"""
    conn = FakeConn()
    events: list[str] = []

    class LogFile:
        def __init__(self, name: str) -> None:
            self.name = name

        def __enter__(self) -> LogFile:
            events.append(f"open:{self.name}")
            return self

        def __exit__(self, *exc_info) -> bool:
            events.append(f"close:{self.name}")
            return False

    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(Transaction(conn))
            stack.enter_context(LogFile("app.log"))
            raise RuntimeError("mid-flight failure")  # 异常时全部资源按后进先出退出
    except RuntimeError:
        pass  # 异常不吞：只是本用例要接住它
    assert events == ["open:app.log", "close:app.log"]
    assert conn.operations == ["begin", "rollback"]  # 事务正确回滚


def main() -> None:
    print("== 练习 3 自检 ==")
    conn = FakeConn()
    with Transaction(conn):
        pass
    print("正常路径:", conn.operations)
    conn2 = FakeConn()
    try:
        with Transaction(conn2):
            raise KeyError("模拟业务失败")
    except KeyError:
        pass
    print("异常路径:", conn2.operations, "（异常已传播到外层）")
    conn3 = FakeConn()
    with transaction_cm(conn3):
        pass
    print("@contextmanager 正常路径:", conn3.operations)
    test_commit_path()
    test_rollback_path_and_propagation()
    test_contextmanager_form_matches()
    test_exitstack_manages_multiple()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
