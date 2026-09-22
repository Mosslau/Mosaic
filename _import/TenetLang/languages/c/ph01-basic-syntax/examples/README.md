# ph01 基础语法 示例

> 每个示例是主文档对应示例的完整可运行版。验证环境：Apple clang 17.0.0（gcc 兼容），标准 C99。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-calculator.c | 命令行计算器：读算式求值，处理除零 | `gcc -Wall -Wextra -std=c99 ex01-calculator.c -o ex01` | `./ex01` |
| ex02-is-prime.c | 判断素数：打印 1~100 内全部素数 | `gcc -Wall -Wextra -std=c99 ex02-is-prime.c -o ex02` | `./ex02` |
| ex03-array-stats.c | 数组统计：最大值、最小值、平均值 | `gcc -Wall -Wextra -std=c99 ex03-array-stats.c -o ex03` | `./ex03` |
| ex04-multiplication-table.c | 九九乘法表 | `gcc -Wall -Wextra -std=c99 ex04-multiplication-table.c -o ex04` | `./ex04` |

全部已在本环境编译运行验证（`-Wall -Wextra` 零警告）。
