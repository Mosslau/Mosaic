/* project/calculator.c —— 命令行计算器（阶段项目）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 calculator.c -o calculator
 * 运行：./calculator   （循环读入中缀算式如 3 + 4，输入 q 退出）
 * 已验证：本环境编译零警告，四则运算/除零/非法输入/退出均正常
 */
#include <stdio.h>

int main(void) {
    char line[128];
    double a, b;
    char op;

    printf("命令行计算器（中缀算式如 3 + 4，输入 q 退出）\n");
    for (;;) {
        printf("> ");
        if (fgets(line, sizeof(line), stdin) == NULL) {
            break;  /* EOF */
        }
        /* 单独一个 q/Q 退出 */
        if (sscanf(line, " %c", &op) == 1 && (op == 'q' || op == 'Q')) {
            break;
        }
        /* 解析中缀算式：<数> <运算符> <数> */
        if (sscanf(line, "%lf %c %lf", &a, &op, &b) != 3) {
            printf("错误: 输入格式不正确，应为 <数> <运算符> <数>\n");
            continue;
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
            default: printf("不支持的操作符 '%c'\n", op); break;
        }
    }
    printf("再见\n");
    return 0;
}
