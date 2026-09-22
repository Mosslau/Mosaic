#!/usr/bin/env python3
# examples/ex04-descriptor-metaclass.py —— 描述符协议与元类（主文档 3.5/3.6）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 ex04-descriptor-metaclass.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex04-descriptor-metaclass.py -q（收集 test_* 跑断言）
# lint：ruff check ex04-descriptor-metaclass.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""手写 property/classmethod 等价描述符、data vs 非 data 优先级、__set_name__ 与元类。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class my_property:
    """property 的纯 Python 教学等价物：data descriptor（有 __set__）。"""

    def __init__(
        self,
        fget: Callable[[Any], Any] | None = None,
        fset: Callable[[Any, Any], None] | None = None,
    ) -> None:
        self.fget = fget
        self.fset = fset

    def setter(self, fset: Callable[[Any, Any], None]) -> my_property:
        """支持 @x.setter 链式写法。"""
        self.fset = fset
        return self

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self  # 类属性访问返回描述符本身
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def __set__(self, obj: Any, value: Any) -> None:
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(obj, value)


class my_classmethod:
    """classmethod 的教学等价物：非 data descriptor，绑定类而非实例。"""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func

    def __get__(self, obj: Any, objtype: type | None = None) -> Callable[..., Any]:
        cls = objtype if objtype is not None else type(obj)
        return lambda *args, **kwargs: self.func(cls, *args, **kwargs)


class NonData:
    """只有 __get__：非 data descriptor，会被实例 __dict__ 遮蔽。"""

    def __init__(self, value: str) -> None:
        self.value = value

    def __get__(self, obj: Any, objtype: type | None = None) -> str:
        return f"{self.value} (non-data, via class)"


class Data:
    """有 __get__ + __set__：data descriptor，优先于实例 __dict__。"""

    def __init__(self, value: str) -> None:
        self.value = value

    def __get__(self, obj: Any, objtype: type | None = None) -> str:
        return f"{self.value} (data, via class)"

    def __set__(self, obj: Any, value: str) -> None:
        self.value = value


class Demo:
    non = NonData("n")
    data = Data("d")

    def __init__(self) -> None:
        self.plain = "instance dict"  # 普通实例属性

    @my_property
    def doubled(self) -> int:
        """手写 property：访问 self.doubled 触发 fget。"""
        return self._n * 2

    @doubled.setter
    def doubled(self, value: int) -> None:
        self._n = value // 2

    @my_classmethod
    def who(cls) -> str:
        """手写 classmethod：拿到的是类不是实例。"""
        return cls.__name__


class AutoName:
    """__set_name__：描述符被赋给类时自动收到所属类与属性名。"""

    def __init__(self) -> None:
        self.name = ""
        self.owner = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.owner = owner
        self.name = name  # 不再需要靠约定猜属性名


class UsesAutoName:
    field_a = AutoName()
    field_b = AutoName()


def test_my_property() -> None:
    d = Demo()
    d.doubled = 20  # setter：_n = 10
    assert d.doubled == 20  # getter：10 * 2
    assert Demo.doubled is not None  # 类属性访问不触发 fget


def test_my_classmethod() -> None:
    assert Demo.who() == "Demo"
    assert Demo().who() == "Demo"  # 实例访问同样绑定类


def test_data_vs_non_data() -> None:
    d = Demo()
    assert d.non == "n (non-data, via class)"  # 未遮蔽：走类的非 data 描述符
    d.non = "shadowed"  # 实例 dict 写入 → 遮蔽非 data
    assert d.non == "shadowed"
    del d.non
    assert d.non == "n (non-data, via class)"  # 删除遮蔽后恢复
    d.data = "attempt"  # data descriptor 的 __set__ 接管
    assert d.data == "attempt (data, via class)"  # 实例 dict 里没有 data 这个键


def test_set_name() -> None:
    u = UsesAutoName()
    assert u.field_a.owner is UsesAutoName  # owner 收到的是所属类对象本身
    assert u.field_a.name == "field_a"
    assert u.field_b.name == "field_b"


def test_function_is_descriptor() -> None:
    """方法自动绑定 self 的机制：函数是非 data 描述符。"""
    d = Demo()
    bound = d.who  # 实例访问 → 绑定
    assert bound() == "Demo"
    unbound = Demo.who  # 类访问 → 原函数（教学实现里是 lambda）
    assert callable(unbound)


# ---- 元类部分 ----


class UpperMeta(type):
    """元类：类创建时改写 namespace（演示「造类的类」）。"""

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kw: Any
    ) -> UpperMeta:
        cleaned = {
            k: (v.upper() if isinstance(v, str) and not k.startswith("__") else v)
            for k, v in namespace.items()
        }
        return super().__new__(mcls, name, bases, cleaned, **kw)


class Greeting(metaclass=UpperMeta):
    hello = "hi"


class PluginBase:
    registry: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        PluginBase.registry[cls.__name__] = cls


class LogPlugin(PluginBase):
    pass


class MetricsPlugin(PluginBase):
    pass


def test_metaclass() -> None:
    assert Greeting.hello == "HI"  # 类体定义期即被改写
    assert isinstance(Greeting, UpperMeta)  # 实例是类：元类的语义


def test_init_subclass_registry() -> None:
    assert sorted(PluginBase.registry) == ["LogPlugin", "MetricsPlugin"]
    assert PluginBase.registry["LogPlugin"] is LogPlugin


def main() -> None:
    print("== 手写 my_property ==")
    d = Demo()
    d.doubled = 20
    print("d.doubled =", d.doubled)
    print("== 手写 my_classmethod ==")
    print("Demo.who() =", Demo.who(), "| Demo().who() =", Demo().who())
    print("== data vs 非 data 优先级 ==")
    d2 = Demo()
    d2.non = "shadowed"
    print("实例遮蔽非 data:", d2.non)
    del d2.non
    d2.data = "attempt"
    print("data descriptor 接管赋值:", d2.data)
    print("== __set_name__ ==")
    u = UsesAutoName()
    print("field_a.name =", u.field_a.name, "| owner =", type(u.field_a.owner).__name__)
    print("== 元类与注册表 ==")
    print("Greeting.hello =", Greeting.hello)
    print("plugin registry =", sorted(PluginBase.registry))
    test_my_property()
    test_my_classmethod()
    test_data_vs_non_data()
    test_set_name()
    test_function_is_descriptor()
    test_metaclass()
    test_init_subclass_registry()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
