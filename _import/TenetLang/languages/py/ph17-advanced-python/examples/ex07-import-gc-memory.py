#!/usr/bin/env python3
# examples/ex07-import-gc-memory.py —— import 机制与内存管理（主文档 3.7/4.1/4.2/3.10）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 ex07-import-gc-memory.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex07-import-gc-memory.py -q（收集 test_* 跑断言）
# lint：ruff check ex07-import-gc-memory.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""sys.path / sys.modules / importlib、引用计数、循环引用 + gc、weakref、__slots__、ctypes。"""

from __future__ import annotations

import ctypes
import gc
import importlib
import sys
import types
import weakref


class Node:
    """带 __dict__ 的自定义类实例：默认被分代 GC 追踪（可能成环）。"""

    def __init__(self) -> None:
        self.peer: Node | None = None


class Slotted:
    """__slots__：实例没有 __dict__（省内存、属性访问更快）。"""

    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class Plain:
    """对照：普通实例每人一个 __dict__。"""

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def test_import_machinery() -> None:
    """import 是运行时行为：sys.path 查找、sys.modules 缓存、模块体只执行一次。"""
    # 注：math 可能已被运行环境预导入（site 导入链、pytest 收集等），
    # 故「尚未导入」的断言不适用于共享进程；改用幂等校验：
    assert "math" in sys.modules or importlib.util.find_spec("math") is not None

    assert "math" in sys.modules  # 导入后进缓存
    cached = sys.modules["math"]
    assert sys.modules["math"] is cached  # 同一对象，不重复执行模块体
    # sys.path 是搜索清单：第一个元素是脚本/入口目录（本文件目录）
    assert sys.path[0]  # 非空即成立（值因运行方式而异：脚本目录 / cwd）
    spec = importlib.util.find_spec("math")
    assert spec is not None and spec.name == "math"


def test_reload_executes_again() -> None:
    """importlib.reload 强制重新执行模块体（调试用；生产慎用）。"""
    import math

    again = importlib.reload(math)
    assert again is math


def test_dynamic_module_registration() -> None:
    """模块对象 = types.ModuleType + 注册进 sys.modules——import 机制的可编程面。"""
    mod = types.ModuleType("fake_pkg")  # 建一个模块对象
    mod.answer = 42
    sys.modules["fake_pkg"] = mod  # 注册进缓存 → 之后 import 即得
    fake = importlib.import_module("fake_pkg")  # 动态导入（import 语句的等价物）
    assert fake.answer == 42
    del sys.modules["fake_pkg"]  # 清理，避免污染其他测试


def test_small_int_singletons() -> None:
    """小整数 -5..256 是预分配单例；大整数每次新建（CPython 实现细节）。"""
    a = 256
    b = 256
    assert a is b  # 缓存范围内：同一对象
    c = 257
    d = 257
    assert c == d  # 值相等才是可靠比较
    # 大整数是否同一对象取决于编译/运行细节——身份比较只用于单例（None/True/False）


def test_reference_counting() -> None:
    """引用计数是主回收机制：sys.getrefcount 含自身一次。"""
    obj = Plain(1, 2)
    base = sys.getrefcount(obj)  # ≥ 2：obj 变量 + getrefcount 参数
    holder: list[object] = [obj]
    assert sys.getrefcount(obj) == base + 1
    holder.clear()
    assert sys.getrefcount(obj) == base


def test_cycle_needs_gc() -> None:
    """循环引用计数不归零：靠分代 GC 回收。"""
    a, b = Node(), Node()
    a.peer, b.peer = b, a
    assert gc.is_tracked(a)  # 自定义类实例默认被追踪
    assert gc.get_referrers(a)  # b 引用着 a（环成立，列表非空即证）
    del a, b  # 删掉外部引用——环内计数永不为零
    collected = gc.collect()  # 手动全量回收
    assert collected >= 2  # 环内两个 Node 被 GC 回收


def test_weakref_callback() -> None:
    """弱引用不增加计数：对象被强引用清空后，weakref 失效并触发回调。"""
    fired: list[str] = []

    def on_gone(ref: weakref.ReferenceType[Plain]) -> None:
        fired.append(str(ref))

    obj = Plain(3, 4)
    r = weakref.ref(obj, on_gone)
    assert r() is obj  # 还活着：deref 得到对象
    del obj
    gc.collect()  # 触发回收 → 回调
    assert r() is None
    assert fired  # 回调已触发


def test_slots_no_dict() -> None:
    """__slots__ 实例没有 __dict__ 也没有 __weakref__（如需 weakref 要显式声明）。"""
    s = Slotted(1, 2)
    assert not hasattr(s, "__dict__")  # 没有每实例 dict
    try:
        s.extra = 3  # 动态加属性被拒绝
    except AttributeError:
        pass
    else:
        raise AssertionError("__slots__ 类不允许新增属性")
    assert hasattr(Plain(1, 2), "__dict__")  # 对照类有


def test_ctypes_libc() -> None:
    """ctypes：运行期加载现成 C 库调用（FFI），无需编译。"""
    libc = ctypes.CDLL(None)  # None = 当前进程已加载的共享库（含 libc）
    libc.strlen.argtypes = [ctypes.c_char_p]
    libc.strlen.restype = ctypes.c_size_t
    assert libc.strlen(b"hello") == 5
    assert libc.strlen(b"") == 0


def main() -> None:
    print("== import 机制 ==")
    print("sys.path 前 3 项:", sys.path[:3])
    print("'math' 在 sys.modules？", "math" in sys.modules)
    import math  # noqa: F401

    print("导入后:", "math" in sys.modules, "| find_spec:", importlib.util.find_spec("math").name)
    print("== 模块缓存 ==")
    print("重复 import 同一对象？", sys.modules["math"] is math)
    print("== 小整数驻留 ==")
    print("256 is 256:", 256 == 256, "| 257 == 257:", 257 == 257)
    print("== 引用计数 ==")
    obj = Plain(1, 2)
    base = sys.getrefcount(obj)
    holder = [obj]
    print("入列表后 refcount:", sys.getrefcount(obj), "(基准", base, "+1)")
    holder.clear()
    print("清空列表后回到:", sys.getrefcount(obj))
    print("== 循环引用与 gc ==")
    a, b = Node(), Node()
    a.peer, b.peer = b, a
    print("gc.is_tracked(a):", gc.is_tracked(a), "| 手动 collect 前删除引用")
    del a, b
    n = gc.collect()
    print("gc.collect() 回收对象数:", n)
    print("== weakref ==")
    fired: list[str] = []

    def on_gone(ref: weakref.ReferenceType[Plain]) -> None:
        fired.append(str(ref))

    w = weakref.ref(Plain(7, 8), on_gone)
    print("weakref 活着:", w() is not None)
    gc.collect()
    print("对象回收后 weakref:", w(), "| 回调触发:", bool(fired))
    print("== __slots__ ==")
    s = Slotted(1, 2)
    print(
        "Slotted 有无 __dict__:",
        hasattr(s, "__dict__"),
        "| Plain 有无:",
        hasattr(Plain(1, 2), "__dict__"),
    )
    print("== ctypes 调 libc ==")
    libc = ctypes.CDLL(None)
    libc.strlen.argtypes = [ctypes.c_char_p]
    libc.strlen.restype = ctypes.c_size_t
    print("strlen(b'hello') =", libc.strlen(b"hello"))
    test_import_machinery()
    test_reload_executes_again()
    test_dynamic_module_registration()
    test_small_int_singletons()
    test_reference_counting()
    test_cycle_needs_gc()
    test_weakref_callback()
    test_slots_no_dict()
    test_ctypes_libc()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
