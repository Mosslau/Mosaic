// ex05-error-host.cpp —— 异常 → 错误码 → 错误路径逐条触发
// 验证环境：Apple clang 21.0.0（C++20）；前置：先按 ex01 编出 /tmp/libvtest.dylib
// 构建/运行（examples/ 目录内）：
//   clang++ -std=c++20 -Wall -Wextra ex05-error-host.cpp -L/tmp -lvtest -o /tmp/ph20-ex05
//   /tmp/ph20-ex05
// 预期输出：err(NULL)=1 err(empty)=2 err(nan)=3 ok_add=0 error-translate OK，退出码 0
// 验证状态：已验证（本机实测通过）
// 教学点（主文档 3.6）：异常在 extern "C" 函数体内被 catch 干净，边界上只有错误码。
//         互操作测试必须覆盖错误路径——这里把三种错误码全部触发并断言。
#include "ex01-stats-c-api.h"

#include <cstdio>
#include <limits>

int main() {
    // 错误 1：空指针 → VTEST_ERR_NULL(1)
    double out = 0.0;
    const int err_null = vtest_stats_mean(nullptr, &out);

    // 错误 2：空样本 → 内部抛 std::runtime_error，包装层 catch 转 VTEST_ERR_EMPTY(2)
    vtest_stats* empty = vtest_stats_create();
    const int err_empty = vtest_stats_mean(empty, &out);
    vtest_stats_destroy(empty);

    // 错误 3：NaN 输入 → 内部抛 std::invalid_argument，转 VTEST_ERR_VALUE(3)
    vtest_stats* s = vtest_stats_create();
    const int err_nan = vtest_stats_add(s, std::numeric_limits<double>::quiet_NaN());
    const int ok_add = vtest_stats_add(s, 7.0);
    vtest_stats_destroy(s);

    std::printf("err(NULL)=%d err(empty)=%d err(nan)=%d ok_add=%d\n", err_null, err_empty,
                err_nan, ok_add);
    const bool ok = err_null == VTEST_ERR_NULL && err_empty == VTEST_ERR_EMPTY &&
                    err_nan == VTEST_ERR_VALUE && ok_add == VTEST_OK;
    if (!ok) return 1;
    std::printf("error-translate OK\n");
    return 0;
}
