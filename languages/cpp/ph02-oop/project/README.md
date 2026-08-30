# ph02 阶段项目：学生管理系统

## 需求

对应 Roadmap「ph02 面向对象 OOP 阶段」推荐项目之一。用 class 设计实现一个学生管理系统：`Student` 类封装姓名/学号/成绩，`StudentManager` 类用 `std::vector<Student>` 组合管理全部记录，提供简单交互菜单完成增删查改。

## 功能清单

- [ ] 添加学生（姓名、学号、成绩），学号重复时拒绝
- [ ] 列出全部学生
- [ ] 按学号查询单个学生
- [ ] 按学号修改姓名与成绩
- [ ] 按学号删除学生
- [ ] 菜单循环，输入 6 或 EOF 退出

## 验收标准

- `g++ -Wall -Wextra -std=c++17 student_manager.cpp -o student_manager` 编译零警告
- 添加 `Alice 101 85` 后选择 2，输出包含 `Alice [id=101]: 85`
- 学号重复添加输出 `id exists`；查询/修改/删除不存在的学号输出 `not found`
- 数据成员全部私有，只读成员函数标 `const`，构造函数用成员初始化列表
- 不裸用 `new`/`delete`，内存由 `std::string`/`std::vector` 自动管理（RAII）

## 扩展方向（可选）

- 记录持久化到文件（读写在启动/退出时进行）—— 属于 ph09 文件、网络与系统编程阶段
- 用 `std::sort`/`std::find_if` 重写查询与排序 —— 属于 ph04 STL 标准库阶段
- 为 `StudentManager` 写单元测试 —— 属于 ph16 测试、静态分析与代码规范阶段

## 验证环境

Apple clang 17.0.0（g++ 兼容），标准 C++17。

```bash
# 1. 编译
g++ -Wall -Wextra -std=c++17 student_manager.cpp -o student_manager
# 2. 交互运行
./student_manager
# 3. 自动冒烟测试：添加 Alice 后列出全部并退出
printf '1\nAlice 101 85\n2\n6\n' | ./student_manager
```

已在本环境验证：编译零警告，增删查改、重复学号拒绝、EOF 退出行为符合验收标准。
