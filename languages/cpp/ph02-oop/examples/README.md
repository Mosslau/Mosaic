# ph02 面向对象 OOP 示例

> 每个示例是主文档对应示例的完整可运行版。验证环境：Apple clang 17.0.0（g++ 兼容），标准 C++17。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-student.cpp | Student 类：封装、成员初始化列表、const 成员函数 | `g++ -Wall -Wextra -std=c++17 ex01-student.cpp -o ex01` | `./ex01` |
| ex02-page-block-segment.cpp | Page/Block/Segment 建模：组合优于继承 | `g++ -Wall -Wextra -std=c++17 ex02-page-block-segment.cpp -o ex02` | `./ex02` |
| ex03-logger-static.cpp | Logger：static 成员属于类而非对象 | `g++ -Wall -Wextra -std=c++17 ex03-logger-static.cpp -o ex03` | `./ex03` |
| ex04-istorage-iexecutor.cpp | IStorage/IExecutor 抽象接口：纯虚函数、override、虚析构 | `g++ -Wall -Wextra -std=c++17 ex04-istorage-iexecutor.cpp -o ex04` | `./ex04` |
| ex05-student-manager.cpp | 学生管理系统：用 std::vector 组合多个对象 | `g++ -Wall -Wextra -std=c++17 ex05-student-manager.cpp -o ex05` | `./ex05` |

全部已在本环境编译运行验证（`-Wall -Wextra` 零警告）。
