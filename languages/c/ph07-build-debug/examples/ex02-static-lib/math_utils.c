// 来源：07-build-debug.md 第 6 章示例 1 —— 多文件项目 + Makefile（math_utils.c）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11 零警告
// 构建：make（在 ex01-makefile-project/ 目录内执行）
// 运行：./app
// 验证状态：已验证
#include "math_utils.h"
int add(int a, int b)      { return a + b; }
int multiply(int a, int b) { return a * b; }
int power(int base, int exp) {
    int r = 1;
    for (int i = 0; i < exp; i++) r *= base;
    return r;
}
