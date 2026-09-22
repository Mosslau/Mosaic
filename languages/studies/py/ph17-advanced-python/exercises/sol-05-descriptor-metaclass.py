#!/usr/bin/env python3
# exercises/sol-05-descriptor-metaclass.py —— 练习 5 参考实现：校验描述符 + __init_subclass__ 注册表
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 sol-05-descriptor-metaclass.py（main 自检，断言失败退出码非 0）
# 测试：python3 -m pytest sol-05-descriptor-metaclass.py -q（收集 test_* 跑断言）
# lint：ruff check sol-05-descriptor-metaclass.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""练习 5 参考实现：Positive 校验描述符（data descriptor）+ BaseCommand 自动注册表。

教学点：__set_name__ 让描述符知道自己被赋给哪个类哪个属性；
data descriptor 的 __set__ 接管赋值（优先于实例 __dict__，见主文档 3.5）；
__init_subclass__ 两行代码替代元类做子类注册（主文档 3.6）。
"""

from __future__ import annotations

from typing import Any


class Positive:
    """data descriptor：绑定到实例的整数属性，负数赋值直接抛 ValueError。"""

    def __init__(self) -> None:
        self.name = ""  # __set_name__ 填充
        self.owner: type | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.owner = owner  # 描述符被赋给类时自动收名
        self.name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> int:
        if obj is None:
            return self  # 类属性访问返回描述符本身
        return obj.__dict__[self.name]  # 数据存实例字典（私有前缀都不需要：
        # 赋值全被 __set__ 拦截，键名不会错位）

    def __set__(self, obj: Any, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError(f"{self.name} must be int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"{self.name} must be >= 0, got {value}")
        obj.__dict__[self.name] = value


class Motor:
    """应用：电机转速只接受非负整数。"""

    max_rpm = Positive()

    def __init__(self, max_rpm: int) -> None:
        self.max_rpm = max_rpm  # 走 __set__，非写普通实例键


class BaseCommand:
    """命令基类：任何子类定义即自动注册（__init_subclass__，无需元类）。"""

    commands: dict[str, type[BaseCommand]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        BaseCommand.commands[cls.__name__] = cls

    def run(self) -> str:  # 子类实现
        raise NotImplementedError


class CmdStart(BaseCommand):
    def run(self) -> str:
        return "starting"


class CmdStop(BaseCommand):
    def run(self) -> str:
        return "stopping"


def run_command(name: str) -> str:
    """按注册表分派：名字 → 类 → 实例 → run()。"""
    try:
        cls = BaseCommand.commands[name]
    except KeyError:
        raise KeyError(f"unknown command: {name}") from None
    return cls().run()


def test_positive_descriptor() -> None:
    m = Motor(8000)
    assert m.max_rpm == 8000  # 读走 __get__
    m.max_rpm = 12_000
    assert m.max_rpm == 12_000
    try:
        m.max_rpm = -5
    except ValueError:
        pass
    else:
        raise AssertionError("负数必须抛 ValueError")
    try:
        m.max_rpm = "fast"
    except TypeError:
        pass
    else:
        raise AssertionError("非 int 必须抛 TypeError")
    # data descriptor 语义：实例 __dict__ 里不出现可绕过的普通键
    assert "max_rpm" not in m.__dict__ or m.__dict__["max_rpm"] == 12_000


def test_set_name_auto() -> None:
    assert Motor.max_rpm.name == "max_rpm"  # 描述符知道自己的属性名
    assert Motor.max_rpm.owner is Motor


def test_registry_and_dispatch() -> None:
    assert sorted(BaseCommand.commands) == ["CmdStart", "CmdStop"]
    assert run_command("CmdStart") == "starting"
    assert run_command("CmdStop") == "stopping"
    try:
        run_command("CmdReboot")  # 未注册
    except KeyError:
        pass
    else:
        raise AssertionError("未知命令必须抛 KeyError")


def test_deep_subclass_also_registers() -> None:
    """__init_subclass__ 沿 MRO 查找：间接子类也会触发（除非中间类覆盖且不转发）。"""

    class CmdRestart(CmdStart):  # 间接子类
        def run(self) -> str:
            return "restarting"

    # CmdRestart 定义时：查找 __init_subclass__ 沿 CmdStart 的 MRO 命中 BaseCommand
    # 的实现（CmdStart 未覆盖），因此它被自动注册——这正是「想拦截谱系注册，
    # 要在中间类覆盖并决定是否 super().__init_subclass__() 转发」的教训。
    assert "CmdRestart" in BaseCommand.commands
    assert run_command("CmdRestart") == "restarting"

    # 对照：中间类覆盖且不转发 → 谱系在它之下断掉
    class NoForward(BaseCommand):
        def __init_subclass__(cls, **kwargs: Any) -> None:
            pass  # 故意不调 super：子孙不再自动注册

    class Orphan(NoForward):
        def run(self) -> str:
            return "orphan"

    assert "Orphan" not in BaseCommand.commands
    del BaseCommand.commands["CmdRestart"]  # 清理，不污染其他测试


def main() -> None:
    print("== 练习 5 自检 ==")
    m = Motor(8000)
    m.max_rpm = 12_000
    print("m.max_rpm =", m.max_rpm, "| 描述符自动收名:", Motor.max_rpm.name)
    try:
        m.max_rpm = -5
    except ValueError as exc:
        print("负数被拦截:", exc)
    print("命令注册表:", sorted(BaseCommand.commands))
    print("run_command('CmdStart') =", run_command("CmdStart"))
    test_positive_descriptor()
    test_set_name_auto()
    test_registry_and_dispatch()
    test_deep_subclass_also_registers()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
