# ph02 阶段项目：小型数学工具库

## 需求

对应 Roadmap「ph02 函数与模块化阶段」推荐项目之一。实现一个小型数学工具库：加、减、乘、除、幂、最大公约数（gcd）、最小公倍数（lcm）。采用多文件组织：`math_lib.h`（声明 + include guard）、`math_lib.c`（实现）、`main.c`（演示入口）。

## 功能清单

- [ ] 加减乘除四则运算（除法处理除零）
- [ ] 幂运算 `power`（非负整数次幂，内部用递归 helper，static 隐藏）
- [ ] 最大公约数 `gcd`（欧几里得算法）
- [ ] 最小公倍数 `lcm`（基于 gcd：`lcm(a,b) = a / gcd(a,b) * b`，先除后乘防溢出）
- [ ] 头文件用 include guard 防重复包含

## 验收标准

- `gcc -Wall -Wextra -std=c99 main.c math_lib.c -o mathlib` 编译零警告
- `power(2, 10)` = 1024；`gcd(48, 36)` = 12；`lcm(4, 6)` = 12
- 除零时返回 0.0 并提示
- `math_lib.c` 中的递归 helper 用 `static` 限制为内部链接

## 扩展方向（可选）

- 加单元测试（用断言验证每个函数）—— 属于 ph11 测试阶段
- 把编译过程写成 Makefile —— 属于 ph07 编译工程化阶段

## 验证环境

Apple clang 17.0.0（gcc 兼容），标准 C99。编译：`gcc -Wall -Wextra -std=c99 main.c math_lib.c -o mathlib`；运行：`./mathlib`。已在本环境验证。
