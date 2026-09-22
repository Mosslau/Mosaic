/* examples/ex04-math-utils/main.c —— 小型数学工具库（入口）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c math_utils.c -o ex04
 * 运行：./ex04
 * 已验证：本环境编译零警告
 */
#include <stdio.h>
#include "math_utils.h"

int main(void) {
    printf("add(2, 3) = %d\n", add(2, 3));
    printf("multiply(4, 5) = %d\n", multiply(4, 5));
    printf("power(2, 10) = %d\n", power(2, 10));
    return 0;
}
