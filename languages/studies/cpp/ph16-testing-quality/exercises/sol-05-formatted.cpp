// exercises/sol-05-formatted.cpp —— 练习 5 参考实现：clang-format 格式化产物（已验证）
// 这是题目中乱格式代码按 examples/ex03.clang-format 配置格式化后的结果。
// 验证：clang-format --style=file:../examples/ex03.clang-format --dry-run --Werror
//       sol-05-formatted.cpp → 零输出、退出码 0（已验证）
// 编译运行：c++ -std=c++20 -Wall -Wextra sol-05-formatted.cpp -o /tmp/ph16cpp-sol05
//           && /tmp/ph16cpp-sol05  →  输出：evens=6
#include <cstdio>
#include <vector>

static int count_even(const std::vector<int>& values) {
    int count = 0;
    for (const int v : values) {
        if (v % 2 == 0) {
            ++count;
        }
    }
    return count;
}

int main() {
    const std::vector<int> values{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    std::printf("evens=%d\n", count_even(values));
    return 0;
}
