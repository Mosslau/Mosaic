/* examples/ex03-recursion.c —— 递归：阶乘与斐波那契
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex03-recursion.c -o ex03
 * 运行：./ex03   （输入一个非负整数，如 5）
 * 已验证：本环境编译零警告，输入 5 输出 5! = 120 / fib(5) = 5
 */
#include <stdio.h>

long long factorial(int n) {
    if (n < 0) return -1;
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

long long fib(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    int n;
    printf("请输入非负整数 n: ");
    if (scanf("%d", &n) != 1) {
        printf("输入格式错误\n");
        return 1;
    }

    if (n < 0) {
        printf("n 必须 >= 0\n");
        return 1;
    }

    printf("%d! = %lld\n", n, factorial(n));
    printf("fib(%d) = %lld\n", n, fib(n));
    return 0;
}
