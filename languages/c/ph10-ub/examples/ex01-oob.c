/* ex01-oob.c —— 数组越界写（UB 演示）
 * 运行前提: 必须用 cc -fsanitize=address 编译运行, 否则勿运行 ——
 * 裸跑会越界写坏相邻栈内存(可能静默损坏数据或覆盖返回地址)。
 * 故意触发的编译期警告 -Warray-bounds 也是教学点: 编译器在编译期就能
 * 看出 arr[3] 越界, 这是"边界检查"的第一道防线。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -fsanitize=address -g ex01-oob.c -o ex01
// 运行：./ex01（ASan 报 stack-buffer-overflow 并中止, 退出码非 0）
// 验证状态：已验证（实测报告见主文档 6 章示例 1; 本环境 ASan 无法启动外部
//           符号器(llvm-symbolizer 存在但 spawn 失败 errno 9), 栈帧未符号化,
//           但错误类型/读写大小/越界行号信息完整）
#include <stdio.h>

int main(void) {
    int arr[3] = {1, 2, 3};
    int other = 42;
    printf("写前: arr[0]=%d other=%d\n", arr[0], other);
    arr[3] = 100;          /* UB: 故意越界写 1 个元素 —— ASan 应报 stack-buffer-overflow */
    printf("写后: arr[0]=%d other=%d\n", arr[0], other);
    return 0;
}
