// exercises/sol-04-coverage-report.cpp —— 练习 4 参考实现：生成覆盖率报告（已验证）
// 自包含：被测函数 classify_temp() + 覆盖全部分支的测试。
//
// 验证环境：Homebrew clang++ 21.1.8 + llvm-profdata/llvm-cov 21.1.8（同版本最稳；
//           Apple clang 21.0.0 生成的 profraw 实测也能被 llvm-cov 21.1.8 读取）
// 三步流（已验证）：
//   # 1. 插桩编译
//   clang++ -std=c++20 -Wall -Wextra -O0 -g -fprofile-instr-generate -fcoverage-mapping \
//       sol-04-coverage-report.cpp -o /tmp/ph16cpp-sol04
//   # 2. 运行收集 + 合并
//   LLVM_PROFILE_FILE=/tmp/ph16cpp-sol04.profraw /tmp/ph16cpp-sol04
//   llvm-profdata merge -sparse /tmp/ph16cpp-sol04.profraw -o /tmp/ph16cpp-sol04.profdata
//   # 3. 出报告（llvm-profdata/llvm-cov 在 /opt/homebrew/opt/llvm/bin/）
//   llvm-cov report /tmp/ph16cpp-sol04 -instr-profile=/tmp/ph16cpp-sol04.profdata
//   llvm-cov show   /tmp/ph16cpp-sol04 -instr-profile=/tmp/ph16cpp-sol04.profdata \
//       --name=classify_temp --show-line-counts-or-regions
// 实测（llvm-cov 21.1.8）：classify_temp 区域覆盖 100%；整个文件因失败打印分支
// （只有测试失败才执行）不是 100%——「覆盖率缺口」本身就是报告在说话。
#include <cstdio>

namespace {

enum class Temp { freezing, cold, warm, hot };

// 被测函数：温度分档（4 个分支 + 边界）
Temp classify_temp(int celsius) {
    if (celsius <= 0) {
        return Temp::freezing;
    }
    if (celsius < 15) {
        return Temp::cold;
    }
    if (celsius < 28) {
        return Temp::warm;
    }
    return Temp::hot;
}

int failures = 0;

void expect(int celsius, Temp want) {
    if (classify_temp(celsius) != want) {
        std::printf("[失败] classify_temp(%d)\n", celsius);
        ++failures;
    }
}

}  // namespace

int main() {
    expect(-10, Temp::freezing);
    expect(0, Temp::freezing);    // 边界：0 度结冰
    expect(1, Temp::cold);
    expect(14, Temp::cold);
    expect(15, Temp::warm);       // 边界：15 度转暖
    expect(27, Temp::warm);
    expect(28, Temp::hot);
    expect(40, Temp::hot);

    std::printf(failures == 0 ? "全部通过\n" : "%d 个失败\n", failures);
    return failures == 0 ? 0 : 1;
}
