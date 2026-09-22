# examples —— STL 标准库阶段完整示例

> 每个示例是主文档 `04-stl.md` 第 6 章对应示例的完整可运行版。验证环境：Apple clang 17.0.0（g++ 兼容）。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-word-freq.cpp` | 词频统计：map（有序）vs unordered_map（无序）vs 频率降序排序 | `g++ -Wall -Wextra -std=c++17 ex01-word-freq.cpp -o ex01-word-freq` | `./ex01-word-freq` |
| `ex02-id-table.cpp` | ID 查询表：unordered_map 带 struct 值，find 命中/未命中处理 | `g++ -Wall -Wextra -std=c++17 ex02-id-table.cpp -o ex02-id-table` | `./ex02-id-table` |
| `ex03-priority-tasks.cpp` | 优先级任务调度：priority_queue + 反向 operator< 实现小顶堆 | `g++ -Wall -Wextra -std=c++17 ex03-priority-tasks.cpp -o ex03-priority-tasks` | `./ex03-priority-tasks` |
| `ex04-stl-list.cpp` | 用 STL 重写链表操作：std::list 与 std::vector 两种写法对比 | `g++ -Wall -Wextra -std=c++17 ex04-stl-list.cpp -o ex04-stl-list` | `./ex04-stl-list` |
| `ex05-iterator-invalidation.cpp` | 迭代器失效演示：erase 安全模式 + reserve 预防扩容失效 | `g++ -Wall -Wextra -std=c++17 ex05-iterator-invalidation.cpp -o ex05-iterator-invalidation` | `./ex05-iterator-invalidation` |
| `ex06-views-ranges.cpp` | string_view / span / ranges 组合（C++20） | `g++ -Wall -Wextra -std=c++20 ex06-views-ranges.cpp -o ex06-views-ranges` | `./ex06-views-ranges` |

六个示例均已在本环境（Apple clang 17.0.0，g++ 兼容）用上述命令编译零警告并运行验证（已验证）。示例 1~5 使用 C++17，示例 6 使用 C++20（`std::span` / `std::ranges`）。
