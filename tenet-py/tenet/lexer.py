"""词法分析器（Lexer）：把 Tenet 源码字符串切成带位置的 Token 流。

与 Rust 版 tenet-rs/src/lexer.rs 语义一致：

- 空白（空格 / 制表 / 换行）跳过；`//` 行注释与 `/* ... */` 块注释跳过
- 数字：`42` 为 int，`3.14` / `3.` 为 float（小数点后不要求有数字）
- 字符串：双引号包裹，支持转义 `\\n \\t \\" \\\\`
- 标识符 / 关键字：字母、数字、下划线，不能以数字开头
- 运算符按最长匹配：`==`、`!=`、`<=`、`>=`、`&&`、`||`、`->`
"""

from __future__ import annotations

from . import token as tk
from .error import Position, TenetError

# i64 范围（与 Rust 的 i64 对齐）
I64_MIN = -(2**63)
I64_MAX = 2**63 - 1

_KEYWORDS = {
    "let": tk.LET,
    "fn": tk.FN,
    "if": tk.IF,
    "else": tk.ELSE,
    "while": tk.WHILE,
    "return": tk.RETURN,
    "break": tk.BREAK,
    "true": tk.TRUE,
    "false": tk.FALSE,
    "int": tk.INT_TYPE,
    "float": tk.FLOAT_TYPE,
    "bool": tk.BOOL_TYPE,
    "string": tk.STR_TYPE,
}

# 多字符运算符：最长匹配
_MULTI_OPS = {
    ("=", "="): tk.EQ,
    ("!", "="): tk.NEQ,
    ("<", "="): tk.LTE,
    (">", "="): tk.GTE,
    ("&", "&"): tk.AND,
    ("|", "|"): tk.OR,
    ("-", ">"): tk.ARROW,
}

_SINGLE_OPS = {
    "(": tk.LPAREN,
    ")": tk.RPAREN,
    "{": tk.LBRACE,
    "}": tk.RBRACE,
    ",": tk.COMMA,
    ":": tk.COLON,
    ";": tk.SEMI,
    "=": tk.ASSIGN,
    "+": tk.PLUS,
    "-": tk.MINUS,
    "*": tk.STAR,
    "/": tk.SLASH,
    "%": tk.PERCENT,
    "<": tk.LT,
    ">": tk.GT,
    "!": tk.NOT,
}


class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1

    @classmethod
    def tokenize(cls, source: str) -> list[tk.Token]:
        """把整个源码切成 Token 序列（以 EOF 结尾）。"""
        lexer = cls(source)
        tokens = []
        while True:
            tok = lexer.next_token()
            tokens.append(tok)
            if tok.kind == tk.EOF:
                break
        return tokens

    # ---- 底层字符操作 ----

    def peek(self) -> str | None:
        if self.pos < len(self.src):
            return self.src[self.pos]
        return None

    def peek2(self) -> str | None:
        if self.pos + 1 < len(self.src):
            return self.src[self.pos + 1]
        return None

    def advance(self) -> str | None:
        c = self.peek()
        if c is None:
            return None
        self.pos += 1
        if c == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return c

    # ---- 主循环 ----

    def next_token(self) -> tk.Token:
        self.skip_trivia()
        line, col = self.line, self.col

        def make(kind, value=None):
            return tk.Token(kind, value, Position(line, col))

        c = self.peek()
        if c is None:
            return make(tk.EOF)

        if c.isdigit():
            return self.lex_number(line, col)
        if c == '"':
            return self.lex_string(line, col)
        if c.isalpha() or c == "_":
            return self.lex_ident(line, col)

        # 多字符运算符（最长匹配）
        nxt = self.peek2()
        if (c, nxt) in _MULTI_OPS:
            self.advance()
            self.advance()
            return make(_MULTI_OPS[(c, nxt)])

        return self.lex_single(c, line, col)

    def skip_trivia(self):
        while True:
            while self.peek() in (" ", "\t", "\r", "\n"):
                self.advance()
            if self.peek() == "/" and self.peek2() == "/":
                # 行注释：读到换行
                while True:
                    c = self.advance()
                    if c is None or c == "\n":
                        break
                continue
            if self.peek() == "/" and self.peek2() == "*":
                # 块注释：读到 */
                self.advance()
                self.advance()
                while True:
                    if self.peek() == "*" and self.peek2() == "/":
                        self.advance()
                        self.advance()
                        break
                    if self.peek() is None:
                        break
                    self.advance()
                continue
            break

    def lex_number(self, line: int, col: int) -> tk.Token:
        text = []
        is_float = False
        while True:
            c = self.peek()
            if c is not None and c.isdigit():
                text.append(self.advance())
            elif c == ".":
                # 小数点后不要求必须有数字（支持 `3.` 这种 Go 风格字面量）
                is_float = True
                text.append(self.advance())
            else:
                break
        raw = "".join(text)
        if is_float:
            try:
                value = float(raw)
            except ValueError:
                raise TenetError.at("无效的浮点数", line, col)
            return tk.Token(tk.FLOAT, value, Position(line, col))
        try:
            value = int(raw)
        except ValueError:
            raise TenetError.at("无效的整数", line, col)
        if not (I64_MIN <= value <= I64_MAX):
            raise TenetError.at("整数超出 i64 范围", line, col)
        return tk.Token(tk.INT, value, Position(line, col))

    def lex_string(self, line: int, col: int) -> tk.Token:
        self.advance()  # 开头的 "
        value = []
        while True:
            c = self.advance()
            if c is None:
                raise TenetError.at("未闭合的字符串字面量", line, col)
            if c == '"':
                break
            if c == "\\":
                esc = self.advance()
                if esc is None:
                    raise TenetError.at("字符串以反斜杠结尾", line, col)
                if esc == "n":
                    value.append("\n")
                elif esc == "t":
                    value.append("\t")
                elif esc == '"':
                    value.append('"')
                elif esc == "\\":
                    value.append("\\")
                else:
                    raise TenetError.at(f"未知的转义序列 `\\{esc}`", line, col)
            else:
                value.append(c)
        return tk.Token(tk.STR, "".join(value), Position(line, col))

    def lex_ident(self, line: int, col: int) -> tk.Token:
        text = []
        while True:
            c = self.peek()
            if c is not None and (c.isalnum() or c == "_"):
                text.append(self.advance())
            else:
                break
        name = "".join(text)
        kind = _KEYWORDS.get(name, tk.IDENT)
        return tk.Token(kind, name if kind == tk.IDENT else None, Position(line, col))

    def lex_single(self, c: str, line: int, col: int) -> tk.Token:
        self.advance()
        kind = _SINGLE_OPS.get(c)
        if kind is None:
            raise TenetError.at(f"无法识别的字符 `{c}`", line, col)
        return tk.Token(kind, None, Position(line, col))
