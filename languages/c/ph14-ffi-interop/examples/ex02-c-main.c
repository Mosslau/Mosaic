/* ex02-c-main.c —— C 调用 C++ 包装层：.c 文件里调用 extern "C" 导出的函数
 *
 * 编译（macOS）：
 *   c++ -Wall -Wextra -std=c++17 -dynamiclib ex02-cpp-lib.cpp \
 *       -o /tmp/ph14-ex/libcppwrap.dylib
 *   cc  -Wall -Wextra -std=c11 ex02-c-main.c -L/tmp/ph14-ex -lcppwrap \
 *       -o /tmp/ph14-ex/ex02-c
 * 运行：/tmp/ph14-ex/ex02-c
 * 要点：C 语言没有 name mangling 这回事——C 侧的每个函数声明天然就是
 *   C 链接，与 libcppwrap.dylib 导出的符号直接对上，不需要任何特殊标记。
 */
#include <stdint.h>
#include <stdio.h>

/* 只声明 C 链接的函数原型（C 侧不需要 extern "C"，声明即 C 链接） */
const char *cw_greet(void);
int32_t cw_double(int32_t x);
void cw_set_greeting(const char *s);

int main(void) {
    printf("c: greet()      = %s\n", cw_greet());
    printf("c: double(21)   = %d\n", (int)cw_double(21));
    cw_set_greeting("hello from C!");
    printf("c: after set, greet() = %s\n", cw_greet());
    return 0;
}
