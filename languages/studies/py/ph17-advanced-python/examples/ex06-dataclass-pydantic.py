#!/usr/bin/env python3
# examples/ex06-dataclass-pydantic.py —— dataclass 机制与数据类三选一（主文档 3.8）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12 + pydantic 2.x（本机需自行安装）
# 依赖安装：python3 -m pip install "pydantic>=2"
# 运行：python3 ex06-dataclass-pydantic.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex06-dataclass-pydantic.py -q（收集 test_* 跑断言）
# lint：ruff check ex06-dataclass-pydantic.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""@dataclass 的代码生成机制、field/frozen/__post_init__、与 pydantic 的行为对比与桥接。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


@dataclass(frozen=True)
class Point:
    """frozen：实例不可变，自动生成基于字段的 __hash__（可作 dict key）。"""

    x: float
    y: float


@dataclass
class Record:
    """default_factory 处理可变默认值；__post_init__ 做派生字段。"""

    name: str
    tags: list[str] = field(default_factory=list)  # 不能写 = []（共享陷阱）
    slug: str = field(init=False, repr=False)  # 不在 __init__ 参数、不进 repr

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")  # __init__ 末尾自动调用
        self.slug = self.name.lower().replace(" ", "-")


# pydantic 对照：同一个数据形状，pydantic 在构造时强校验 + 类型转换
class PRecord(BaseModel):
    name: str = Field(min_length=1)  # 非空约束（用法深讲在 ph10）
    tags: list[str] = []


def test_dataclass_codegen() -> None:
    """dataclass 生成了 __init__/__eq__/__hash__——与手写类等价；frozen 禁改。"""
    import dataclasses

    p1 = Point(1.0, 2.0)
    p2 = Point(1.0, 2.0)
    assert p1 == p2  # __eq__ 按字段比较
    assert p1.x == 1.0 and p1.y == 2.0
    assert hash(p1) == hash(p2)  # frozen=True → 基于字段的 __hash__
    d = {p1: "origin"}  # 可作 dict key
    assert d[Point(1.0, 2.0)] == "origin"
    try:
        p1.x = 9.0  # frozen：赋值抛 FrozenInstanceError
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("frozen 实例赋值必须抛 FrozenInstanceError")


def test_field_and_post_init() -> None:
    r1 = Record("Hello World")
    r2 = Record("Hello World")  # 各自独立的默认 list
    r1.tags.append("a")
    assert r2.tags == []  # default_factory 每实例新建
    assert r1.slug == "hello-world"  # __post_init__ 派生
    try:
        Record("")  # __post_init__ 校验失败
    except ValueError:
        pass
    else:
        raise AssertionError("空 name 必须抛 ValueError")


def test_asdict_and_replace() -> None:
    p = Point(1.0, 2.0)
    assert asdict(p) == {"x": 1.0, "y": 2.0}
    moved = replace(p, x=9.0)  # frozen 实例的「更新」靠 replace 重建
    assert moved == Point(9.0, 2.0) and p == Point(1.0, 2.0)


def test_dataclass_no_runtime_validation() -> None:
    """dataclass 的类型注解是声明不是校验：脏类型数据不会在构造时被拦。

    对比 pydantic（test_pydantic_validates_and_coerces）：同样是「name 必须非空」，
    dataclass 只能靠 __post_init__ 手动抛 ValueError；类型转换则完全不发生。
    """
    assert isinstance(Record("ok"), Record)


def test_pydantic_validates_and_coerces() -> None:
    """pydantic 在信任边界 fail-fast：非法输入构造即抛 ValidationError。"""
    pr = PRecord(name="a", tags=["x", "y"])
    assert pr.name == "a" and pr.tags == ["x", "y"]
    try:
        PRecord(name="")  # pydantic 约束/必填校验失败
    except ValidationError:
        pass
    else:
        raise AssertionError("空 name 必须抛 ValidationError")
    # 类型强制转换：pydantic v2 对 str 字段默认不把 int 42 转成 "42"
    # （v1 宽松、v2 收紧为 strict 语义；确需转换要显式 ConfigDict(coerce_numbers_to_str=True)）
    try:
        PRecord.model_validate({"name": 42})
    except ValidationError:
        pass
    else:
        raise AssertionError(
            "v2 下 int 输入 str 字段必须抛 ValidationError（除非显式开启 coerce_numbers_to_str）"
        )


def test_type_adapter_bridges_dataclass() -> None:
    """TypeAdapter 让 pydantic 直接消费 dataclass 结构（内部 dataclass + 边界 pydantic）。"""
    adapter = TypeAdapter(Point)  # 把 dataclass 当 pydantic 模型校验
    p = adapter.validate_python({"x": "3.5", "y": 2})  # 数字字符串被转换
    assert p == Point(3.5, 2.0)
    try:
        adapter.validate_python({"x": "oops"})  # 转换失败 → 报错
    except ValidationError:
        pass
    else:
        raise AssertionError("非法数字必须抛 ValidationError")


def main() -> None:
    print("== @dataclass 的代码生成 ==")
    p1 = Point(1.0, 2.0)
    print("Point(1.0, 2.0) == Point(1.0, 2.0)?", p1 == Point(1.0, 2.0))
    print("frozen 可哈希:", hash(p1) == hash(Point(1.0, 2.0)))
    print("== field / __post_init__ ==")
    r = Record("Hello World")
    r.tags.append("a")
    print("r1.tags =", r.tags, "| slug =", r.slug)
    print("asdict =", asdict(Point(1.0, 2.0)))
    print("replace(Point(1,2), x=9) =", replace(Point(1.0, 2.0), x=9.0))
    print("== dataclass 不校验 vs pydantic fail-fast ==")
    print("dataclass 构造 Record('') →", end=" ")
    try:
        Record("")
    except ValueError as exc:
        print("ValueError:", exc)
    print("pydantic 构造 PRecord(name='') →", end=" ")
    try:
        PRecord(name="")
    except ValidationError as exc:
        print(f"ValidationError（{len(exc.errors())} 处）")
    print("== TypeAdapter 桥接 dataclass ==")
    adapter = TypeAdapter(Point)
    print("validate {'x': '3.5', 'y': 2} =", adapter.validate_python({"x": "3.5", "y": 2}))
    test_dataclass_codegen()
    test_field_and_post_init()
    test_asdict_and_replace()
    test_pydantic_validates_and_coerces()
    test_type_adapter_bridges_dataclass()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
