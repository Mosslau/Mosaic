/* 故意出错示例：栈越界写入 —— 必须用 -fsanitize=address 编译运行，否则勿运行 */
// 来源：exercises/README.md 练习 4 —— ASan 检查参考实现
// 验证环境：Apple clang 17（gcc 兼容）
// 编译：gcc -fsanitize=address -g -Wall -Wextra -std=c99 sol-04-buggy-bounds.c -o sol-04-buggy-bounds
// 运行：./sol-04-buggy-bounds    （预期：ASan 报 stack-buffer-overflow 后中止）
// 验证状态：编译通过（ASan 二进制在本环境沙箱内运行受限，报错输出请读者本机验证；编译时 -Warray-bounds
//           已提示 a[4] 越界，属故意出错示例的预期警告）
#include <stdio.h>

int main(void) {
    int a[4] = {1, 2, 3, 4};
    a[4] = 0;   /* 越界写入：a[4] 超出数组边界（有效下标 0~3） */
    printf("a[4] = %d\n", a[4]);
    return 0;
}
