// app/main.cpp —— ph10 工程模板：app 可执行入口
// 用法：./app 1 2 3 4    输出 mean/median/stddev/min/max
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建/运行：make && ./build/app 1 2 3 4（无参数时打印用法并退出 1）
// 验证状态：已验证（make 零警告 + 运行断言通过）
#include "core/stats_utils.h"

#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <n1> <n2> ...\n", argv[0]);
        return 1;
    }
    std::vector<double> data;
    try {
        for (int i = 1; i < argc; ++i) {
            data.push_back(std::stod(argv[i]));
        }
    } catch (const std::exception& e) {
        std::fprintf(stderr, "bad number: %s\n", e.what());
        return 1;
    }
    try {
        const auto [lo, hi] = stats::min_max(data);
        std::printf("n=%zu  mean=%.6f  median=%.6f  stddev=%.6f  min=%.6f  max=%.6f\n",
                    data.size(), stats::mean(data), stats::median(data),
                    stats::stddev(data), lo, hi);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "error: %s\n", e.what());
        return 1;
    }
    return 0;
}
