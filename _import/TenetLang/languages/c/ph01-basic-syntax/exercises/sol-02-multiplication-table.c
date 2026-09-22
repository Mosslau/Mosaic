/* exercises/sol-02-multiplication-table.c —— 九九乘法表
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex04-multiplication-table.c -o ex04
 * 运行：./ex04
 * 已验证：本环境编译零警告，输出标准九九乘法表
 */
#include <stdio.h>

int main(void) {
    for (int i = 1; i <= 9; i++) {
        for (int j = 1; j <= i; j++) {
            printf("%d×%d=%-2d  ", j, i, i * j);
        }
        printf("\n");
    }
    return 0;
}
