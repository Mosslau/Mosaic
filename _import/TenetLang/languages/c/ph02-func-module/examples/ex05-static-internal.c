/* examples/ex05-static-internal.c —— static 内部链接：隐藏模块内部实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex05-static-internal.c -o ex05
 * 运行：./ex05
 * 已验证：本环境编译零警告，输出 internal helper / secret = 42
 */
#include <stdio.h>

static int secret = 42;

static void internal_helper(void) {
    printf("internal helper\n");
}

int get_secret(void) {
    internal_helper();
    return secret;
}

int main(void) {
    printf("secret = %d\n", get_secret());
    return 0;
}
