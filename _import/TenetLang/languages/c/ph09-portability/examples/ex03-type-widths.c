/* ex03-type-widths.c —— 跨平台类型宽度探测:
 * sizeof 结果随平台 ABI 变(LP64/LLP64/ILP32), 序列化/协议里不能直接写结构体;
 * 把指针存进 long 在 Windows x64 会截断(LLP64), 指针↔整数用 intptr_t/uintptr_t
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 ex03-type-widths.c -o ex03
// 运行：./ex03（装 gcc-multilib 后可加 -m32 对比 ILP32 数据模型）
// 验证状态：已验证（64 位 macOS 输出 int=4, long=8, pointer=8, 即 LP64 数据模型）
#include <stdint.h>
#include <stdio.h>

int main(void) {
    printf("int        = %2zu 字节\n", sizeof(int));
    printf("long       = %2zu 字节\n", sizeof(long));
    printf("void* 指针 = %2zu 字节\n", sizeof(void *));
    printf("int32_t    = %2zu 字节\n", sizeof(int32_t));
    printf("int64_t    = %2zu 字节\n", sizeof(int64_t));
    printf("size_t     = %2zu 字节\n", sizeof(size_t));
    printf("intptr_t   = %2zu 字节\n", sizeof(intptr_t));
    return 0;
}
