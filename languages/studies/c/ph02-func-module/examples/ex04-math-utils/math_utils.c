/* examples/ex04-math-utils/math_utils.c —— 小型数学工具库（实现）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c math_utils.c -o ex04
 * 已验证：本环境编译零警告
 */
#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

/* static 限制为内部链接：仅本文件可见 */
static int helper(int base, int exp) {
    if (exp == 0) return 1;
    return base * helper(base, exp - 1);
}

int power(int base, int exp) {
    if (exp < 0) return 0;
    return helper(base, exp);
}
