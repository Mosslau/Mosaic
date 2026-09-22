# examples —— 现代 C++ 阶段完整示例

> 每个示例是主文档 `06-modern-cpp.md` 第 6 章对应示例的完整可运行版。验证环境：Apple clang 17（g++ 兼容）。示例 1~4 用 `-std=c++17`，示例 5 涉及 `<format>`/`<print>` 用 `-std=c++23`。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-smart-ptr.cpp` | 智能指针管理资源：unique_ptr 所有权转移 / shared_ptr 引用计数 / weak_ptr 观察 | `g++ -Wall -Wextra -std=c++17 ex01-smart-ptr.cpp -o ex01-smart-ptr` | `./ex01-smart-ptr` |
| `ex02-lambda-sort.cpp` | lambda 定义排序规则 + capture 阈值过滤 + std::function 回调 | `g++ -Wall -Wextra -std=c++17 ex02-lambda-sort.cpp -o ex02-lambda-sort` | `./ex02-lambda-sort` |
| `ex03-optional-lookup.cpp` | optional 表达查找结果（拒绝哨兵值）+ value_or 默认值 + emplace | `g++ -Wall -Wextra -std=c++17 ex03-optional-lookup.cpp -o ex03-optional-lookup` | `./ex03-optional-lookup` |
| `ex04-variant-state.cpp` | variant 建模设备三态 + holds_alternative/get + std::visit 统一处理 | `g++ -Wall -Wextra -std=c++17 ex04-variant-state.cpp -o ex04-variant-state` | `./ex04-variant-state` |
| `ex05-format.cpp` | std::format 类型安全格式化 + 自定义 formatter 特化 + std::println（C++23） | `g++ -Wall -Wextra -std=c++23 ex05-format.cpp -o ex05-format` | `./ex05-format` |

五个示例均已在本环境（Apple clang 17，g++ 兼容）用上述命令编译零警告并运行验证（已验证）。
