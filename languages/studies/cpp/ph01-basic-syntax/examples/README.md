# ph01 基础语法 示例

> 每个示例是主文档对应示例的完整可运行版。验证环境：Apple clang 17.0.0（g++ 兼容），标准 C++17。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-contacts.cpp | 通讯录：`struct` + `std::vector`，按名字查找联系人 | `g++ -Wall -Wextra -std=c++17 ex01-contacts.cpp -o ex01` | `./ex01` |
| ex02-word-frequency.cpp | 词频统计：`std::sort` 排序后线性扫描计数 | `g++ -Wall -Wextra -std=c++17 ex02-word-frequency.cpp -o ex02` | `./ex02` |
| ex03-auto-range-for.cpp | CTAD、range-for 与迭代器遍历对比 | `g++ -Wall -Wextra -std=c++17 ex03-auto-range-for.cpp -o ex03` | `./ex03` |

全部已在本环境编译运行验证（`-Wall -Wextra -std=c++17` 零警告）。
