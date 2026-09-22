// sol-04-summarize.cpp —— 练习 4 参考实现：格式化文本写进「调用者提供的缓冲」
// 验证环境：Apple clang 21.0.0（C++20）；实测编译零警告、ctypes 断言全绿
// 构建（exercises/ 目录内）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib sol-04-summarize.cpp -o /tmp/libsumm.dylib
// 运行：python3 sol-04-ctypes.py
// 验证状态：已验证
// 缓冲语义（写进注释的契约，Python 侧按它断言）：
//   - out 指向调用者分配的缓冲，cap 是容量（含结尾 NUL 的空间）
//   - 内容放得下：写完整文本并 NUL 结尾，返回 TLS_OK=0
//   - 放不下：返回 TLS_ERR_SMALL=2，且缓冲保持合法 C 字符串（写空串或截断，取「留空」简单语义）
//   - 库从不分配也不释放跨边界内存——「调用者缓冲」= 零所有权转移（主文档 3.8 规则 2）
// 错误码：TLS_OK=0  TLS_ERR_NULL=1  TLS_ERR_SMALL=2  TLS_ERR_INVALID=3（n<=0）
#include <cstddef>
#include <cstdio>
#include <stdexcept>
#include <vector>

namespace {

constexpr int k_ok = 0;
constexpr int k_err_null = 1;
constexpr int k_err_small = 2;
constexpr int k_err_invalid = 3;

}  // namespace

extern "C" int tls_summarize(const double* xs, long n, char* out, long cap) {
    if (xs == nullptr || out == nullptr) return k_err_null;
    if (cap <= 0) return k_err_small;  // 连 NUL 都放不下
    if (n <= 0) return k_err_invalid;
    try {
        double sum = 0.0;
        for (long i = 0; i < n; ++i) sum += xs[i];
        // snprintf 返回「本应写入」的长度（不含 NUL），用它判断是否放得下
        const int need = std::snprintf(out, static_cast<std::size_t>(cap), "n=%ld sum=%.3f", n, sum);
        if (need < 0) {
            out[0] = '\0';
            return k_err_small;  // 编码错误兜底：视同放不下
        }
        if (need >= cap) {  // 放不下：留空并报错（语义写进文件头契约）
            out[0] = '\0';
            return k_err_small;
        }
        return k_ok;
    } catch (...) {
        out[0] = '\0';
        return 99;
    }
}

extern "C" int tls_version(void) {
    return 1;
}
