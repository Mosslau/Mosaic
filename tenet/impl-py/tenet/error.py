"""统一错误类型：所有阶段（词法 / 语法 / 解释 / 代码生成）共用。

错误携带源码位置 `[行:列]`，与 Rust 版 impl-rs/src/error.rs 一致。
"""

from __future__ import annotations


class Position:
    """源码位置：1 起始的行号与列号。"""

    __slots__ = ("line", "col")

    def __init__(self, line: int, col: int):
        self.line = line
        self.col = col

    @classmethod
    def new(cls, line: int, col: int) -> "Position":
        return cls(line, col)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Position)
            and self.line == other.line
            and self.col == other.col
        )

    def __repr__(self) -> str:
        return f"Position(line={self.line}, col={self.col})"


class TenetError(Exception):
    """带可选位置的错误。"""

    def __init__(self, message: str, pos: Position | None = None):
        super().__init__(message)
        self.message = message
        self.pos = pos

    @classmethod
    def at(cls, message: str, line: int, col: int) -> "TenetError":
        return cls(message, Position(line, col))

    @classmethod
    def at_pos(cls, message: str, pos: Position) -> "TenetError":
        return cls(message, pos)

    def __str__(self) -> str:
        if self.pos is not None:
            return f"[{self.pos.line}:{self.pos.col}] {self.message}"
        return self.message
