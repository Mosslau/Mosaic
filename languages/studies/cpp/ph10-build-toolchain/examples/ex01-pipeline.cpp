// ex01-pipeline.cpp —— 编译流水线四阶段演示源文件
// 本文件本身是可运行程序；重点是配合 README/主文档用 -E / -S / -c / 链接
// 四个命令观察"预处理 → 编译 → 汇编 → 链接"各阶段的中间产物。
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex01-pipeline.cpp -o ex01-pipeline
// 运行：./ex01-pipeline（sum 应为 24，退出码 0）
// 各阶段命令（产物全部输出到 /tmp，见 examples/README.md）
// 验证状态：已验证（编译零警告 + 运行通过）
#include <cstdint>
#include <cstdio>

// 宏在"预处理"阶段展开：-E 输出里能看到 sizeof 表达式被原位替换
#define ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))
#define SCALE 3

// constexpr 函数在"编译"阶段求值（模板实例化也发生在这一阶段）
constexpr int clamp(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

template <typename T>
T twice(T x) {
    return x * SCALE;
}

// static 函数只在本翻译单元可见：链接后 nm 里是局部符号（小写 t）
static int hidden_helper(int x) {
    return x + 1;
}

int main() {
    const int vals[] = {1, -2, 9, 4};
    int sum = 0;
    for (int i = 0; i < static_cast<int>(ARRAY_LEN(vals)); ++i) {
        sum += clamp(twice(vals[i]), 0, 10);   // 宏在预处理期替换，模板在编译期实例化
    }
    sum = hidden_helper(sum);
    std::printf("sum=%d\n", sum);
    return sum == 24 ? 0 : 1;   // 1,-2,9,4 → ×3 → 3,0,10,10 → 23 → +1 → 24
}
