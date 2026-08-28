# tenet-cpp — Tenet 语言的 C++17 实现

与 [`tenet-rs/`](../tenet-rs/)、[`tenet-py/`](../tenet-py/) 三端对齐的 C++17 移植版：
同样的语言、同样的语义、同样的错误信息、**逐字节一致**的 Go 代码生成输出。

## 目录结构

```
tenet-cpp/
├── src/                    # 源码（header-only，模块与 Rust 版一一对应）
│   ├── error.hpp           # 统一错误类型（[行:列]）
│   ├── token.hpp           # 词法单元（enum class）
│   ├── lexer.hpp           # 词法分析器
│   ├── ast.hpp             # 抽象语法树（标签结构体）
│   ├── parser.hpp          # 语法分析器（递归下降 + 优先级爬升）
│   ├── value.hpp           # 运行时值系统（std::variant）
│   ├── env.hpp             # 作用域环境（词法作用域链）
│   ├── interpreter.hpp     # 树遍历解释器
│   ├── codegen.hpp         # Go 代码生成器
│   ├── repl.hpp            # 交互式 REPL
│   └── main.cpp            # CLI 入口
├── examples/               # 示例程序（与 tenet-rs 相同）
└── tests/test_main.cpp     # 测试（镜像 Rust 48 个测试）
```

## 构建与使用

```bash
cd tenet-cpp
make                # 构建 tenet 与 test_tenet，并运行测试
make tenet          # 仅构建 CLI

./tenet run examples/fib.tenet        # 解释执行
./tenet repl                          # 交互式 REPL
./tenet codegen examples/fib.tenet    # 生成 Go 源码（stdout）
```

要求：C++17 编译器（clang 14+ / GCC 11+，需要 `std::to_chars` 浮点支持）、
零第三方依赖。

## 测试

```bash
cd tenet-cpp
make test
```

## 三端对应关系

| tenet-rs (Rust) | tenet-py (Python) | tenet-cpp (C++) | 说明 |
|-----------------|-------------------|-----------------|------|
| `src/token.rs` | `tenet/token.py` | `src/token.hpp` | TokenKind → enum class |
| `src/lexer.rs` | `tenet/lexer.py` | `src/lexer.hpp` | 最长匹配、i64 范围检查 |
| `src/ast.rs` | `tenet/ast.py` | `src/ast.hpp` | 枚举 → dataclass → 标签结构体 |
| `src/parser.rs` | `tenet/parser.py` | `src/parser.hpp` | 同一优先级表与错误信息 |
| `src/value.rs` | `tenet/value.py` | `src/value.hpp` | 枚举 → 原生类型 → std::variant |
| `src/env.rs` | `tenet/env.py` | `src/env.hpp` | 作用域链（Rc → 共享指针） |
| `src/interpreter.rs` | `tenet/interpreter.py` | `src/interpreter.hpp` | Flow 信号、短路求值 |
| `src/codegen.rs` | `tenet/codegen.py` | `src/codegen.hpp` | Go 输出逐字节一致 |
| `src/repl.rs` | `tenet/repl.py` | `src/repl.hpp` | 多行、缺分号容错、回显 |

设计原则：**零第三方依赖**，只用标准库；语义与 Rust/Python 版完全对齐，
包括 `7 / 2 == 3`（C++ 原生向零截断）、`true || (1/0==1)` 不报错（短路）、
`1 == 1.0` 为真、块作用域遮蔽等细节。

C++ 特有实现要点：
- AST 用「标签 + 可选载荷」的单一结构体（tagged struct），等价于 Rust 枚举
- 值系统用 `std::variant<int64_t, double, bool, std::string, Nil>`
- 浮点格式化用 `std::to_chars(fixed)` 的最短往返表示，对齐 Rust f64 Display
