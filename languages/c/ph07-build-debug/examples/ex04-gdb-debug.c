// 来源：07-build-debug.md 第 6 章示例 4 —— GDB 调试段错误（故意越界）
/* 故意出错示例：数组越界（i <= len 应为 i < len）—— 必须用 -g 编译后用 gdb 运行，观察 bt/print 定位 */
// 验证环境：Apple clang 17（gcc 兼容），-g -Wall -Wextra 零警告
// 编译：gcc -g -Wall -Wextra ex04-gdb-debug.c -o crash
// 运行：./crash（预期段错误）；gdb ./crash 后 run/bt/print
// 验证状态：已验证（-g 编译通过，-Wall -Wextra 提示 i 在 fill 中未使用[故意]，段错误定位用 GDB）
#include <stdio.h>

void fill(int *arr, int len) {
    for (int i = 0; i <= len; i++) {   /* 应为 i < len: 越界 */
        arr[i] = i * i;
    }
}

int main(void) {
    int nums[3] = {0};
    fill(nums, 3);
    for (int i = 0; i < 3; i++)
        printf("%d\n", nums[i]);
    return 0;
}
