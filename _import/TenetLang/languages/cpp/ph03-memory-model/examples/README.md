# ph03 内存模型 示例

> 每个示例是主文档第 6 章对应示例的完整可运行版。验证环境：Apple clang 17.0.0（g++ 兼容），标准 C++17。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-shallow-copy.cpp | 浅拷贝危害演示（double-free，故意崩溃） | `g++ -Wall -Wextra -std=c++17 -fsanitize=address ex01-shallow-copy.cpp -o ex01` | `./ex01`（析构时 double-free 崩溃，属预期） |
| ex02-string.cpp | 完整 String 类（五函数 + 测试） | `g++ -Wall -Wextra -std=c++17 ex02-string.cpp -o ex02` | `./ex02` |
| ex03-dyn-array.cpp | 动态数组类（深拷贝 + 移动） | `g++ -Wall -Wextra -std=c++17 ex03-dyn-array.cpp -o ex03` | `./ex03` |
| ex04-wal-writer.cpp | RAII 文件句柄（WAL 日志管理） | `g++ -Wall -Wextra -std=c++17 ex04-wal-writer.cpp -o ex04` | `./ex04` |
| ex05-rvo-noexcept.cpp | RVO 与 noexcept 综合演示 | `g++ -Wall -Wextra -std=c++17 ex05-rvo-noexcept.cpp -o ex05` | `./ex05` |

除 ex01 外全部已在本环境编译运行验证（`-Wall -Wextra` 零警告）。ex01 已编译零警告，普通运行按预期触发 double-free 崩溃；`-fsanitize=address` 版本在本环境受沙箱限制无法运行（进程被 SIGKILL），ASan 编译命令仅供读者在本机使用。
