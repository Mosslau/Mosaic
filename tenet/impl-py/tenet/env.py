"""环境（Environment）：变量作用域的链式结构。

与 Rust 版 impl-rs/src/env.rs 语义一致：

- 块（`{}`）与函数调用创建新的作用域，子作用域通过 parent 访问外层
- 定义（define）只写当前层 → 允许遮蔽
- 查找 / 赋值（get / assign）沿链向上
- 顶层不建作用域：顶层 let 直接进全局环境（REPL 跨行记忆的关键）
"""

from __future__ import annotations

from .error import TenetError


class Env:
    __slots__ = ("vars", "parent")

    def __init__(self, parent: "Env | None" = None):
        self.vars: dict[str, object] = {}
        self.parent = parent

    @classmethod
    def global_(cls) -> "Env":
        """创建一个全局环境（无父作用域）。"""
        return cls(None)

    @classmethod
    def child(cls, parent: "Env") -> "Env":
        """以 parent 为父作用域创建子环境。"""
        return cls(parent)

    def define(self, name: str, value) -> None:
        self.vars[name] = value

    def get(self, name: str) -> object:
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise TenetError(f"未定义的变量 `{name}`")

    def assign(self, name: str, value) -> None:
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise TenetError(f"未定义的变量 `{name}`")
