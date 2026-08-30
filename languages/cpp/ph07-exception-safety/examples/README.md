# examples —— 异常、安全与工程规范阶段完整示例

验证环境：Apple clang 17（g++ 兼容），`-Wall -Wextra -std=c++17`。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-raii-file.cpp` | 异常安全资源封装（RAII 文件句柄 + 异常路径自动释放） | `g++ -Wall -Wextra -std=c++17 ex01-raii-file.cpp -o ex01` | `./ex01` |
| `ex02-copy-swap.cpp` | copy-and-swap 实现强异常保证的类 | `g++ -Wall -Wextra -std=c++17 ex02-copy-swap.cpp -o ex02` | `./ex02` |
| `ex03-error-layering.cpp` | 错误码与异常的策略分层（底层错误码、上层异常） | `g++ -Wall -Wextra -std=c++17 ex03-error-layering.cpp -o ex03` | `./ex03` |
| `ex04-logger.cpp` | 日志模块（级别 + 时间戳 + 线程安全预留） | `g++ -Wall -Wextra -std=c++17 ex04-logger.cpp -o ex04 -pthread` | `./ex04` |
| `ex05-assert.cpp` | 断言与防御式编程（assert / static_assert / 前置条件检查） | `g++ -Wall -Wextra -std=c++17 ex05-assert.cpp -o ex05` | `./ex05` |

## 说明

- ex01 演示「构造失败用异常表达 + 栈展开自动析构」；`/etc/hosts` 是 macOS/Linux 都存在的只读文件
- ex02 的 `operator=` 传值参数 + noexcept swap 是强保证的标准手法；自赋值天然安全
- ex03 演示错误码 → 异常的边界转换；`enum class` 杜绝魔法数字
- ex04 的 mutex 是「线程安全预留」——ph08 之前单线程即可运行，加锁为后续并发打底
- ex05 的 `assert` 仅在 debug 构建生效；`static_assert` 在编译期检查

五个示例均已在 Apple clang 17（g++ 兼容）下以 `-Wall -Wextra -std=c++17` 编译零警告并运行验证（已验证）。
