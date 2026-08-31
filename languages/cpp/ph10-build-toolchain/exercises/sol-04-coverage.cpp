// sol-04-coverage.cpp —— 练习 4 参考实现：--coverage + gcov 覆盖率报告
// 待覆盖库 classify() 有 4 个分支；main 刻意只测分支 1/2/3（95/85/75 分），
// 留下"return 'D'"（<70 分支）不测，让 gcov 输出里的 ##### 有内容可读。
// 验证环境：Apple clang 21（g++ 兼容），C++20，/usr/bin/gcov（llvm-cov gcov 亦可）
// 编译（覆盖率构建，-O0 -g 勿与 -O2 混用）：c++ -std=c++20 -O0 -g --coverage \
//              sol-04-coverage.cpp -o sol-04-coverage
// 运行：./sol-04-coverage            # 生成 .gcda 数据
// 文本报告：gcov sol-04-coverage-sol-04-coverage.gcno
//   （本机 Apple clang 的 --coverage 产物命名为"可执行名-源文件名".gcno；
//     Linux GCC 是"源文件名".gcno，命令改为 gcov sol-04-coverage.cpp）
// HTML 报告（lcov/genhtml 本机未安装，未在本环境验证；安装后执行）：
//   brew install lcov
//   lcov --capture --directory . --output-file coverage.info
//   genhtml coverage.info --output-directory html && open html/index.html
// 验证状态：已验证（编译零警告 + gcov 输出 Lines executed: 88.89%，
//           'return D' 一行显示 ##### 未覆盖）
#include <cstdio>

char classify(int score) {
    if (score >= 90) return 'A';   // 分支 1：测试覆盖
    if (score >= 80) return 'B';   // 分支 2：测试覆盖
    if (score >= 70) return 'C';   // 分支 3：测试覆盖
    return 'D';                    // 分支 4：测试未覆盖 → gcov 显示 #####
}

int main() {
    const char a = classify(95);
    const char b = classify(85);
    const char c = classify(75);
    std::printf("scores: %c %c %c\n", a, b, c);
    const bool ok = (a == 'A') && (b == 'B') && (c == 'C');
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
