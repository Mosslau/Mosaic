// 来源：07-build-debug.md 第 6 章示例 1 —— 多文件项目 + Makefile（main.c）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11 零警告
// 构建：make（在 ex01-makefile-project/ 目录内执行）
// 运行：./app
// 验证状态：已验证
#include <stdio.h>
#include "math_utils.h"
int main(void) {
    printf("add(2,3)=%d multiply(4,5)=%d power(2,10)=%d\n",
           add(2, 3), multiply(4, 5), power(2, 10));
    return 0;
}
