/* ex03-uaf.c —— use-after-free 与 double free（UB 演示）
 * 运行前提: 必须用 cc -fsanitize=address 编译运行, 否则勿运行 ——
 * 裸跑会改写已归还堆管理器的内存, 行为不可预测(可能崩溃或静默损坏数据)。
 * 第一个错误(use-after-free)会先被 ASan 捕获并中止, double free 尚未执行;
 * 想单独看 double free 报告, 把第 15 行的 printf 删掉再编译运行。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -fsanitize=address -g ex03-uaf.c -o ex03
// 运行：./ex03（ASan 报 heap-use-after-free 并中止, 退出码非 0）
// 验证状态：已验证（heap-use-after-free 与 attempting double-free 两个报告均实测,
//           见主文档 6 章示例 3; 本环境 ASan 无法启动外部符号器(llvm-symbolizer
//           存在但 spawn 失败 errno 9), 栈帧未符号化）
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int *p = malloc(sizeof(int));
    if (p == NULL) return 1;
    *p = 7;
    free(p);                 /* p 成为悬空指针 */
    printf("%d\n", *p);      /* UB: use-after-free —— 读取已释放的内存 */
    free(p);                 /* UB: double free —— 重复释放 */
    return 0;
}
