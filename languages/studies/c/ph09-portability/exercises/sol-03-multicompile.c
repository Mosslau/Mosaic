/* sol-03-multicompile.c —— 参考实现：同一份源码换编译器 / 换 -std= 编译
 * 要点1: __clang__ 与 __GNUC__ 同时定义, 判断"具体是不是 Clang"必须先查 __clang__;
 * 要点2: #if 求值未定义的标识符按 0 处理, 用 __STDC_VERSION__ 门控 C99 特性,
 *        无 C99 时自动落到 C89 回退写法——同一份源码两种模式都能编译
 * 注意: 本文件刻意只用块注释(不用行注释), 因为 C89 严格模式(-pedantic-errors)
 *       下 // 注释是错误; C89 分支的声明放在独立块的块首, 避免"声明与语句混排"
 *
 * 验证环境：Apple clang 21.0.0（cc）+ Homebrew clang 21.1.8，macOS（Darwin arm64）；
 *          本机 gcc 即 Apple clang（未提供真实 GCC）——在 Linux 上用 gcc 同理
 * 编译：cc -Wall -Wextra -std=c11 sol-03-multicompile.c -o sol03a
 *       clang -Wall -Wextra -std=c11 sol-03-multicompile.c -o sol03b   # 双编译器对照
 *       cc -Wall -Wextra -std=c89 -pedantic-errors sol-03-multicompile.c -o sol03c  # C89 严格模式
 * 运行：./sol03a; ./sol03b; ./sol03c（题目与验收见 exercises/README 练习 3）
 * 验证状态：已验证（cc/clang 双编译器 -std=c11 零警告; C89 严格模式零警告走回退分支;
 *           真实 GCC 未在本环境验证——macOS 的 gcc 是 Apple clang）
 */
#include <stdio.h>

/* 编译器扩展包一层并给回退: 非 GCC 家族退化为普通表达式 */
#if defined(__GNUC__)
#  define LIKELY(x) __builtin_expect(!!(x), 1)
#else
#  define LIKELY(x) (x)
#endif

int main(void) {
#if defined(_MSC_VER)
    printf("编译器: MSVC %d\n", _MSC_VER);
#elif defined(__clang__)      /* 必须先查 __clang__: Clang 也定义 __GNUC__ */
    printf("编译器: Clang %s\n", __clang_version__);
#elif defined(__GNUC__)
    printf("编译器: GCC %d.%d\n", __GNUC__, __GNUC_MINOR__);
#else
    printf("编译器: 未知\n");
#endif

    if (LIKELY(1))            /* 提示分支预测: 大多数时候成立 */
        printf("LIKELY 扩展: 可用\n");
    else
        printf("LIKELY 扩展: 回退\n");

#if __STDC_VERSION__ >= 199901L   /* C99+: for 循环内声明变量可用 */
    for (int i = 0; i < 3; i++)
        printf("C99 循环内声明: %d\n", i);
#else                              /* C89: 声明必须前置到块开头 */
    {
        int i;
        for (i = 0; i < 3; i++)
            printf("C89 前置声明: %d\n", i);
    }
#endif
    return 0;
}
