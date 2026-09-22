// examples/ex02-math.h —— 头文件同时服务 C 与 C++（__cplusplus 守卫）
// 教学点：extern "C" 的正确打开方式是「在头文件里声明一次，实现与调用方都
// include 它」——这样 C 编译器（无 __cplusplus）看到纯 C 声明，C++ 编译器看到
// extern "C" 声明，链接时双方对同一个未 mangling 符号达成一致。
// 被 ex02-extern-c-shared.cpp（库实现）与 ex02-host.cpp（宿主）共同包含。
#ifndef PH19_EX02_MATH_H
#define PH19_EX02_MATH_H

// 同一份头，C 编译时下面这段被跳过；C++ 编译时生效 → 函数按 C 链接编译
#ifdef __cplusplus
extern "C" {
#endif

int math_add(int a, int b);   // C 链接：不 mangling。Mach-O 上导出 _math_add，ELF 上导出 math_add
int math_version(void);       // 简单的接口版本号，宿主可校验

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // PH19_EX02_MATH_H
