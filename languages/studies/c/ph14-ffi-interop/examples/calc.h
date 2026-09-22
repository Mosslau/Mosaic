/* calc.h —— 简单的跨语言计算库（C ABI 最小示范）
 *
 * 本头文件就是"跨语言契约"：任何语言只要按 C ABI 链接 libcalc 动态库、
 * 声明与这里一致的函数签名，就能调用。设计原则（roadmap §14 必会概念）：
 *   - 参数与返回值只用"简单稳定的 C 类型"：int32_t 等定宽整数、
 *     const char *（只读借用），不用 int/long 这类平台宽度不定的类型
 *   - 错误码约定：0 = 成功，负数 = 错误（见 calc_div）
 *   - 头文件带 extern "C" 守卫：C++ 包含时保持 C 链接（符号不 mangling）
 */
#ifndef CALC_H
#define CALC_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 简单整数运算：定宽 int32_t，跨语言 ABI 稳定 */
int32_t calc_add(int32_t a, int32_t b);
int32_t calc_mul(int32_t a, int32_t b);

/* 除法：b == 0 或 out == NULL 返回 -1（错误码），结果写 *out；
 * 返回 0 表示成功 */
int calc_div(int32_t a, int32_t b, int32_t *out);

/* 字符串长度（不含结尾 \0）：只读借用 s，不修改、不释放调用方的内存；
 * s == NULL 返回 -1（空指针返回错误码，而不是崩溃） */
int32_t calc_strlen(const char *s);

#ifdef __cplusplus
}
#endif

#endif /* CALC_H */
