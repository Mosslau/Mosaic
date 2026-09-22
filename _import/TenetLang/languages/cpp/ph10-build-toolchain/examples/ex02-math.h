// ex02-math.h —— 静态库示例：头文件（声明）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 使用方式：与 ex02-libstat.cpp / ex02-libmath.cpp 一起 ar 打包成静态库，
//           消费者 #include 本头文件并链接库（见 examples/README.md 示例 2）
#ifndef EX02_MATH_H
#define EX02_MATH_H

int gcd(int a, int b);          // 最大公约数（欧几里得算法）
int lcm(int a, int b);          // 最小公倍数
bool is_prime(int n);           // 素数判断
long long factorial(int n);     // 阶乘（本示例中消费者未调用，用于演示按需抽取）

#endif  // EX02_MATH_H
