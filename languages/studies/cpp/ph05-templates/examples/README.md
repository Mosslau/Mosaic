# examples —— 模板与泛型编程阶段完整示例

> 每个示例是主文档 `05-templates.md` 第 6 章对应示例的完整可运行版。验证环境：Apple clang 17（g++ 兼容）。示例 1、4、5 涉及 concept / requires / std::ranges，须用 C++20；其余用 C++17。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-func-template.cpp` | 函数模板 max/min + `std::integral` 约束（C++20） | `g++ -Wall -Wextra -std=c++20 ex01-func-template.cpp -o ex01-func-template` | `./ex01-func-template` |
| `ex02-class-template.cpp` | 类模板 Stack<T>：主模板 / bool 全特化 / 指针偏特化 | `g++ -Wall -Wextra -std=c++17 ex02-class-template.cpp -o ex02-class-template` | `./ex02-class-template` |
| `ex03-constexpr-if.cpp` | constexpr 阶乘 + if constexpr 编译期求和 | `g++ -Wall -Wextra -std=c++17 ex03-constexpr-if.cpp -o ex03-constexpr-if` | `./ex03-constexpr-if` |
| `ex04-concept-requires.cpp` | 自定义 concept Printable + ranges/requires 组合约束（C++20） | `g++ -Wall -Wextra -std=c++20 ex04-concept-requires.cpp -o ex04-concept-requires` | `./ex04-concept-requires` |
| `ex05-ring-buffer.cpp` | RingBuffer<T,N>：非类型参数 + requires 约束 + optional pop（C++20） | `g++ -Wall -Wextra -std=c++20 ex05-ring-buffer.cpp -o ex05-ring-buffer` | `./ex05-ring-buffer` |
| `ex06-dependent-name.cpp` | 依赖名称消歧义：typename / template 关键字 | `g++ -Wall -Wextra -std=c++17 ex06-dependent-name.cpp -o ex06-dependent-name` | `./ex06-dependent-name` |

六个示例均已在本环境（Apple clang 17，g++ 兼容）用上述命令编译零警告并运行验证（已验证）。
