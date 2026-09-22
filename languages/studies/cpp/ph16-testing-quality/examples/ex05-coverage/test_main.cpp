// examples/ex05-coverage/test_main.cpp —— classify() 的测试（覆盖率插桩的载体）
// 验证环境：Apple clang 21.0.0 + llvm-cov/llvm-profdata 21.1.8（Homebrew LLVM）
// 构建/运行：见同目录 Makefile（make report）
#include <cstdio>
#include <stdexcept>

#include "grade.h"

namespace {

int failures = 0;

void expect_grade(int score, Grade want) {
    const Grade got = classify(score);
    if (got != want) {
        std::printf("[失败] classify(%d)\n", score);
        ++failures;
    }
}

}  // namespace

int main() {
    expect_grade(0, Grade::fail);
    expect_grade(59, Grade::fail);
    expect_grade(60, Grade::pass);     // 边界：60 及格
    expect_grade(79, Grade::pass);
    expect_grade(80, Grade::good);
    expect_grade(89, Grade::good);
    expect_grade(90, Grade::excellent);
    expect_grade(100, Grade::excellent);

    bool threw = false;
    try {
        (void)classify(101);           // 非法输入分支
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    if (!threw) {
        std::printf("[失败] classify(101) 未抛异常\n");
        ++failures;
    }

    std::printf(failures == 0 ? "全部通过\n" : "%d 个失败\n", failures);
    return failures == 0 ? 0 : 1;
}
