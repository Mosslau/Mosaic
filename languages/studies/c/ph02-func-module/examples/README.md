# ph02 函数与模块化 示例

> 每个示例是主文档对应示例的完整可运行版。验证环境：Apple clang 17.0.0（gcc 兼容），标准 C99。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-basic-func.c | 基础函数：声明与定义、按值传递 | `gcc -Wall -Wextra -std=c99 ex01-basic-func.c -o ex01` | `./ex01` |
| ex02-static-scope.c | 静态局部变量跨调用保留值 | `gcc -Wall -Wextra -std=c99 ex02-static-scope.c -o ex02` | `./ex02` |
| ex03-recursion.c | 递归：阶乘与斐波那契 | `gcc -Wall -Wextra -std=c99 ex03-recursion.c -o ex03` | `./ex03` |
| ex04-math-utils/ | 多文件项目：小型数学工具库 | `gcc -Wall -Wextra -std=c99 ex04-math-utils/main.c ex04-math-utils/math_utils.c -o ex04` | `./ex04` |
| ex05-static-internal.c | static 内部链接，隐藏模块内部实现 | `gcc -Wall -Wextra -std=c99 ex05-static-internal.c -o ex05` | `./ex05` |

全部已在本环境编译运行验证（`-Wall -Wextra` 零警告）。
