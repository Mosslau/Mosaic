# ph03 数组、字符串、指针 示例

> 每个示例是主文档对应示例的完整可运行版。验证环境：Apple clang 17.0.0（gcc 兼容），标准 C99。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-strlib.c | 手写 strlen/strcpy/strcmp/strcat（带测试） | `gcc -Wall -Wextra -std=c99 ex01-strlib.c -o ex01` | `./ex01` |
| ex02-reverse.c | 数组反转 + 字符串反转（双指针） | `gcc -Wall -Wextra -std=c99 ex02-reverse.c -o ex02` | `./ex02` |
| ex03-strstr.c | 子串查找（朴素匹配） | `gcc -Wall -Wextra -std=c99 ex03-strstr.c -o ex03` | `./ex03` |
| ex04-text-stats.c | 文本统计：字符数/单词数/行数 | `gcc -Wall -Wextra -std=c99 ex04-text-stats.c -o ex04` | `echo "hello world" \| ./ex04` |

全部已在本环境编译运行验证（`-Wall -Wextra` 零警告）。
