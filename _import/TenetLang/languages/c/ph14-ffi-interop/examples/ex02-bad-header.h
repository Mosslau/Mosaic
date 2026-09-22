/* ex02-bad-header.h —— 【故意出错】没有 extern "C" 守卫的"C 头文件"副本
 *
 * 运行前提：仅供 ex02-mangle-fail.cpp 演示"忘记 extern \"C\" 守卫 →
 * 链接失败"。它与 calc.h 的唯一区别是去掉了
 *   #ifdef __cplusplus / extern "C" { ... } / #endif
 * 守卫——头文件本身没错，错的是"C++ 包含 C 头文件必须加守卫"这条约定。
 * 不要在生产代码里使用它：它无法链接成功。
 */
#ifndef EX02_BAD_HEADER_H
#define EX02_BAD_HEADER_H

#include <stdint.h>

/* 无 extern "C" 守卫：C++ 编译器会把 calc_add 的名字改编（mangling） */
int32_t calc_add(int32_t a, int32_t b);

#endif /* EX02_BAD_HEADER_H */
