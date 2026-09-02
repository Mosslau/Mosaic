// examples/ex03-formatted.cpp —— ex03-messy.cpp 经 clang-format 格式化后的产物（已验证）
// 生成方式：clang-format --style=file:ex03.clang-format ex03-messy.cpp（再修正文件头注释）
// 验证：clang-format --style=file:ex03.clang-format --dry-run --Werror ex03-formatted.cpp
//       → 零输出、退出码 0（本文件与配置自洽，可直接作为 CI 格式门禁的被检对象）
#include <algorithm>
#include <cstdio>
#include <vector>

static int max_of(const std::vector<int>& v) {
    int best = v.front();
    for (size_t i = 1; i < v.size(); ++i) {
        best = std::max(best, v[i]);
    }
    return best;
}

int main() {
    const std::vector<int> values{3, 1, 4, 1, 5, 9, 2, 6};
    std::printf("max=%d\n", max_of(values));
    return 0;
}
