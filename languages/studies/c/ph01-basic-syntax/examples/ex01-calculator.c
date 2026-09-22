/* examples/ex01-calculator.c —— 命令行计算器：读入算式并求值，处理除零
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex01-calculator.c -o ex01
 * 运行：./ex01   （然后输入如 3 + 4 回车）
 * 已验证：本环境编译零警告，输入 3 + 4 输出 7.00，输入 1 / 0 输出错误提示
 */
#include <stdio.h>

int main(void) {
    double a, b;
    char op;

    printf("输入算式 (如 3 + 4): ");
    if (scanf("%lf %c %lf", &a, &op, &b) != 3) {
        printf("错误: 输入格式不正确\n");
        return 1;
    }

    switch (op) {
        case '+': printf("%.2f\n", a + b); break;
        case '-': printf("%.2f\n", a - b); break;
        case '*': printf("%.2f\n", a * b); break;
        case '/':
            if (b != 0.0)
                printf("%.2f\n", a / b);
            else
                printf("错误: 除数为零\n");
            break;
        default: printf("不支持的操作符\n"); break;
    }
    return 0;
}
