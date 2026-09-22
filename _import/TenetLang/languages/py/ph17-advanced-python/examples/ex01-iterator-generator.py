#!/usr/bin/env python3
# examples/ex01-iterator-generator.py —— 迭代器协议与生成器进阶（主文档 3.1/3.2）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 ex01-iterator-generator.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex01-iterator-generator.py -q（收集 test_* 跑断言）
# lint：ruff check ex01-iterator-generator.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""迭代器协议、for 循环展开、iter() 回退协议、生成器的惰性与双向通信。"""

from __future__ import annotations

from collections.abc import Iterator


class Countdown:
    """手写迭代器：实现 __iter__ + __next__ 即可被 for 消费。"""

    def __init__(self, start: int) -> None:
        self.current = start

    def __iter__(self) -> Countdown:
        return self  # 迭代器约定：__iter__ 返回自己

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration  # 耗尽信号：for 循环靠它退出
        value = self.current
        self.current -= 1
        return value


class SequenceFallback:
    """没有 __iter__ 的对象：iter() 会回退到 __getitem__ 序列协议（从 0 试到 IndexError）。"""

    def __init__(self, data: list[int]) -> None:
        self.data = data

    def __getitem__(self, index: int) -> int:
        if index >= len(self.data):
            raise IndexError  # 回退协议以 IndexError 为结束信号
        return self.data[index]


def manual_for_loop(items) -> list[int]:
    """把 for 循环手工展开：iter() → next() 循环 → 捕获 StopIteration。"""
    collected: list[int] = []
    it = iter(items)
    while True:
        try:
            collected.append(next(it))
        except StopIteration:
            break
    return collected


def gen_countdown(n: int) -> Iterator[int]:
    """生成器函数：调用只创建生成器对象，函数体在 next() 时才执行。"""
    while n > 0:
        yield n  # 暂停点：产出并保存帧状态
        n -= 1


def gen_echo() -> Iterator[str]:
    """send 双向通信：yield 表达式的值 = 最近一次 send 的参数。"""
    got = yield "ready"  # 首次 send(None)/next 走到这，产出 ready
    yield f"got:{got}"


def sub_gen(prefix: str) -> Iterator[int]:
    yield from gen_countdown(3)  # 委托：透传产出与 send/throw/close
    return prefix  # return 值 = yield from 表达式的结果


def wrapper_gen(prefix: str) -> str:
    return (yield from sub_gen(prefix))  # 链式委托，返回值一路向上


def test_iterator_protocol() -> None:
    """手写迭代器与 for 展开行为一致。"""
    assert list(Countdown(3)) == [3, 2, 1]
    assert manual_for_loop([10, 20, 30]) == [10, 20, 30]
    assert list(iter(SequenceFallback([7, 8]))) == [7, 8]  # 回退协议生效
    # 可迭代 ≠ 迭代器：list 可重复遍历，迭代器一次性
    xs = [1, 2]
    assert iter(xs) is not xs  # list 有 __iter__ 无 __next__
    it = iter(xs)
    assert it is iter(it)  # 迭代器 __iter__ 返回自己


def test_generator_laziness() -> None:
    """生成器惰性：未消费前不执行体；send 把值送回暂停点。"""
    c = gen_countdown(3)
    assert next(c) == 3  # 函数体只跑到第一个 yield
    assert list(c) == [2, 1]  # 继续消费到 StopIteration
    e = gen_echo()
    assert next(e) == "ready"  # 启动
    assert e.send("ping") == "got:ping"  # send 恢复并注入值


def test_yield_from_return() -> None:
    """yield from 的子生成器 return 值作为整个表达式结果（耗尽后经 StopIteration.value 取得）。"""
    w = wrapper_gen("END")
    drained: list[int] = []
    try:
        while True:
            drained.append(next(w))
    except StopIteration as exc:
        got = exc.value  # 委托链末尾 sub_gen 的 return 值
    assert drained == [3, 2, 1]  # 先透传子生成器的全部产出
    assert got == "END"  # 再取回 return 值


def test_throw_and_close() -> None:
    """throw 在暂停点注入异常；close 抛 GeneratorExit 提前终止。"""

    def probe() -> Iterator[int]:
        try:
            yield 1
            yield 2
        except ValueError as exc:
            yield f"caught:{exc}"

    p = probe()
    assert next(p) == 1
    assert p.throw(ValueError("boom")) == "caught:boom"

    c = gen_countdown(100)
    assert next(c) == 100
    c.close()  # 之后任何 next 都抛 StopIteration
    try:
        next(c)
    except StopIteration:
        pass
    else:
        raise AssertionError("closed generator should raise StopIteration")


def main() -> None:
    print("== 迭代器协议 ==")
    print("Countdown(3):", list(Countdown(3)))
    print("for 展开等价:", manual_for_loop([10, 20, 30]))
    print("序列回退协议:", list(iter(SequenceFallback([7, 8]))))
    print("== 生成器惰性 ==")
    c = gen_countdown(3)
    print("next 推进:", next(c), "-> 剩余:", list(c))
    e = gen_echo()
    print("send 启动:", next(e), "| send 注入:", e.send("ping"))
    print("== yield from 返回值 ==")
    w = wrapper_gen("END")
    drained: list[int] = []
    try:
        while True:
            drained.append(next(w))
    except StopIteration as exc:
        print("wrapper_gen 透传产出:", drained, "| 子生成器 return:", exc.value)
    print("== 内存对照（惰性价值）：range 1 亿的 sum 不建中间列表 ==")
    print("sum(range(100_000_000)) =", sum(range(100_000_000)))
    test_iterator_protocol()
    test_generator_laziness()
    test_yield_from_return()
    test_throw_and_close()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
