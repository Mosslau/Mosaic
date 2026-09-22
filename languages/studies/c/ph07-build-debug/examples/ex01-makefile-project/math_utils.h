// 来源：07-build-debug.md 第 6 章示例 1 —— 多文件项目 + Makefile（math_utils.h）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11 零警告
// 构建：make（在 ex01-makefile-project/ 目录内执行）
// 运行：./app
// 验证状态：已验证
#ifndef MATH_UTILS_H
#define MATH_UTILS_H
int add(int a, int b);
int multiply(int a, int b);
int power(int base, int exp);
#endif
