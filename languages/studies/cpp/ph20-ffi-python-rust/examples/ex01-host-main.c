/* ex01-host-main.c —— C 宿主：直接 include C 头、链接期绑定调用
 * 验证环境：clang（Apple clang 21.0.0，C11）；dylib 由 clang++ 编出
 * 构建/运行：
 *   clang++ -std=c++20 -Wall -Wextra -dynamiclib ex01-stats-wrap.cpp -o /tmp/libvtest.dylib
 *   clang -std=c11 -Wall -Wextra ex01-host-main.c -L/tmp -lvtest -o /tmp/ph20-ex01-host
 *   /tmp/ph20-ex01-host
 * 验证状态：已验证（双编译器交叉：Homebrew clang 编库 + Apple clang 编宿主同样通过）
 * 教学点：C 语言是这份 C ABI 的「母语」接收方——include 头即可用，无需任何绑定层；
 *        注意错误路径（空样本 mean → VTEST_ERR_EMPTY）也要走到并断言。
 */
#include "ex01-stats-c-api.h"

#include <stdio.h>

int main(void) {
    if (vtest_stats_version() < 1) {
        fprintf(stderr, "version check failed\n");
        return 1;
    }
    vtest_stats* s = vtest_stats_create();
    if (s == NULL) {
        fprintf(stderr, "create failed\n");
        return 1;
    }
    int rc = vtest_stats_add(s, 2.0);
    rc |= vtest_stats_add(s, 4.0);
    rc |= vtest_stats_add(s, 6.0);
    double mean = 0.0;
    long count = 0;
    rc |= vtest_stats_count(s, &count);
    rc |= vtest_stats_mean(s, &mean);
    vtest_stats_destroy(s);

    /* 错误路径：空样本 mean → VTEST_ERR_EMPTY(2) */
    vtest_stats* empty = vtest_stats_create();
    double bogus = 0.0;
    const int err_empty = vtest_stats_mean(empty, &bogus);
    vtest_stats_destroy(empty);

    printf("count=%ld mean=%.1f rc=%d err_empty=%d\n", count, mean, rc, err_empty);
    const int ok = (rc == VTEST_OK && count == 3 && mean == 4.0 &&
                    err_empty == VTEST_ERR_EMPTY);
    if (!ok) {
        fprintf(stderr, "assert failed\n");
        return 1;
    }
    return 0;
}
