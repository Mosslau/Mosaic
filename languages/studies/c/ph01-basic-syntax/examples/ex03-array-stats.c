/* examples/ex03-array-stats.c —— 数组统计：求最大值、最小值、平均值
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex03-array-stats.c -o ex03
 * 运行：./ex03
 * 已验证：本环境编译零警告，输出 人数:6 平均:81.33 最高:99 最低:63
 */
#include <stdio.h>

int main(void) {
    int scores[] = {78, 92, 85, 63, 99, 71};
    int count = sizeof(scores) / sizeof(scores[0]);
    int sum = 0, max = scores[0], min = scores[0];

    for (int i = 0; i < count; i++) {
        sum += scores[i];
        if (scores[i] > max) max = scores[i];
        if (scores[i] < min) min = scores[i];
    }

    printf("人数: %d\n", count);
    printf("平均: %.2f\n", (double)sum / count);
    printf("最高: %d, 最低: %d\n", max, min);
    return 0;
}
