# tenet-py — Tenet 语言的 Python 实现

与 [`tenet-rs/`](../impl-rs/) 一一对应的纯 Python 移植版：同样的语言、同样的语义、同样的错误信息、**逐字节一致**的 Go 代码生成输出。

## 目录结构

```
tenet-py/
├── tenet/               # 包源码
│   ├── token.py         # 词法单元（与 impl-rs/src/token.rs 对应）
│   ├── lexer.py         # 词法分析器
│   ├── ast.py           # 抽象语法树（dataclass）
│   ├── parser.py        # 语法分析器（递归下降 + 优先级爬升）
│   ├── value.py         # 运行时值系统（Rust 截断除法语义）
│   ├── env.py           # 作用域环境（词法作用域链）
│   ├── interpreter.py   # 树遍历解释器
│   ├── codegen.py       # Go 代码生成器
│   ├── repl.py          # 交互式 REPL
│   └── __main__.py      # CLI 入口
├── examples/            # 示例程序（与 tenet-rs 相同）
└── tests/               # unittest 测试（镜像 Rust 48 个测试）
```

## 使用

```bash
cd tenet-py

# 解释执行
python3 -m tenet run examples/fib.tenet

# 生成 Go 源码（与 Rust 版输出逐字节一致）
python3 -m tenet codegen examples/fib.tenet > fib.go
go run fib.go

# 交互式 REPL
python3 -m tenet repl
```

## 测试

```bash
cd tenet-py
python3 -m unittest discover -s tests -v
```

## 与 tenet-rs/ 的对应关系

| tenet-rs (Rust) | tenet-py (Python) | 说明 |
|-----------------|-------------------|------|
| `src/token.rs` | `tenet/token.py` | TokenKind 常量 + 描述 |
| `src/lexer.rs` | `tenet/lexer.py` | 最长匹配、i64 范围检查 |
| `src/ast.rs` | `tenet/ast.py` | 表达式 / 语句枚举 → dataclass |
| `src/parser.rs` | `tenet/parser.py` | 同一优先级表与错误信息 |
| `src/value.rs` | `tenet/value.py` | 值运算 + 向零截断的整除/取模 |
| `src/env.rs` | `tenet/env.py` | 作用域链 |
| `src/interpreter.rs` | `tenet/interpreter.py` | Flow 信号传播、短路求值 |
| `src/codegen.rs` | `tenet/codegen.py` | Go 输出逐字节一致 |
| `src/repl.rs` | `tenet/repl.py` | 多行、缺分号容错、回显 |

设计原则：**零第三方依赖**，只用标准库；语义与 Rust 版完全对齐，
包括 `7 / 2 == 3`（截断除法）、`true || (1/0==1)` 不报错（短路）、
`1 == 1.0` 为真、块作用域遮蔽等细节。
