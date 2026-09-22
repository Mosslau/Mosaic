// exercises/sol-02-operator-plugin.cpp —— 练习 2 参考实现（插件侧）
// 教学点：插件 = 遵循约定签名的 extern "C" 函数集，编译成独立 dylib；
// 宿主不链接它，运行期 dlopen 按名字找符号。
//
// 接口约定（无共享头文件）：
//   extern "C" const char* op_name(void);                        // 算子名
//   extern "C" long long op_sum(const long long* xs, long long n); // 对数组求和
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++
// 编译：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib sol-02-operator-plugin.cpp -o /tmp/libop_sum.dylib
// 验证状态：已验证（编译零警告）

extern "C" const char* op_name(void) {
    return "sum";
}

extern "C" long long op_sum(const long long* xs, long long n) {
    if (xs == nullptr || n <= 0) {
        return 0;
    }
    long long total = 0;
    for (long long i = 0; i < n; ++i) {
        total += xs[i];
    }
    return total;
}
