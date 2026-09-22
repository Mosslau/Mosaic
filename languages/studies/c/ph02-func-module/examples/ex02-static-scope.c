/* examples/ex02-static-scope.c —— 静态局部变量：生命周期贯穿整个程序
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex02-static-scope.c -o ex02
 * 运行：./ex02
 * 已验证：本环境编译零警告，输出 第 1 次调用 / 第 2 次调用 / 第 3 次调用
 */
#include <stdio.h>

void demo_scope(void) {
    static int call_count = 0;  // 静态局部变量：只初始化一次，值跨调用保留
    call_count++;
    printf("第 %d 次调用\n", call_count);
}

int main(void) {
    for (int i = 0; i < 3; i++) {
        demo_scope();
    }
    return 0;
}
