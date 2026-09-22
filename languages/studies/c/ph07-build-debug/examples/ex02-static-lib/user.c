// 来源：07-build-debug.md 第 6 章示例 2 —— 静态库封装（user.c，调用 libmath.a）
// 设计要点：静态库链接语义是"按需抽取"——只把被引用的成员并入可执行文件
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：ar rcs libmath.a math_utils.o（打包库）后 gcc user.c -L. -lmath -o user
// 运行：./user
// 验证状态：已验证
#include <stdio.h>
#include "math_utils.h"            /* 接口: 只依赖头文件, 不依赖 .c */
int main(void) {
    printf("3 + 4 = %d\n", add(3, 4));
    printf("2^8 = %d\n", power(2, 8));
    return 0;
}
