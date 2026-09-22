/* examples/ex02-is-prime.c —— 判断素数：打印 1~100 内全部素数
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex02-is-prime.c -o ex02
 * 运行：./ex02
 * 已验证：本环境编译零警告，输出 2 3 5 7 11 ... 97
 */
#include <stdio.h>
#include <stdbool.h>

bool is_prime(int n) {
    if (n < 2) return false;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) return false;
    }
    return true;
}

int main(void) {
    for (int i = 1; i <= 100; i++) {
        if (is_prime(i)) printf("%d ", i);
    }
    printf("\n");
    return 0;
}
