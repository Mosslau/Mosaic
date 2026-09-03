// ex01-stats-wrap.cpp —— C++ 侧包装实现：把 vtest::running_stats 以 C ABI 形态暴露
// 验证环境：Apple clang 21.0.0 + Homebrew clang 21.1.8（C++20），实测编译零警告
// 构建：clang++ -std=c++20 -Wall -Wextra -dynamiclib ex01-stats-wrap.cpp -o /tmp/libvtest.dylib
// 验证状态：已验证（双编译器 dylib；nm 可见 extern "C" 的 _vtest_stats_* 与内部 C++ mangled 符号并存）
#include "ex01-stats-c-api.h"
#include "ex01-stats-core.h"

#include <new>
#include <stdexcept>

// opaque 约定的执行点：C ABI 指针 ↔ C++ 内部类型，靠 reinterpret_cast 完成。
// 本实现内的 new/delete 是「谁创建谁销毁」教学主题：只在包装层 new、只在这里 delete。

extern "C" vtest_stats* vtest_stats_create(void) {
    try {
        auto* obj = new vtest::running_stats{};
        return reinterpret_cast<vtest_stats*>(obj);  // 库内 new，库内 delete
    } catch (...) {
        return nullptr;  // 分配失败（bad_alloc 等）压成空句柄
    }
}

extern "C" void vtest_stats_destroy(vtest_stats* s) {
    // 只在本库 delete：跨侧释放是红线（ph19 3.8 / 主文档 3.8）
    delete reinterpret_cast<vtest::running_stats*>(s);
}

extern "C" int vtest_stats_add(vtest_stats* s, double value) {
    if (s == nullptr) return VTEST_ERR_NULL;  // 指针错误先于 try 判掉
    try {
        reinterpret_cast<vtest::running_stats*>(s)->add(value);
        return VTEST_OK;
    } catch (const std::invalid_argument&) {  // 异常 → 语义化错误码
        return VTEST_ERR_VALUE;
    } catch (...) { return VTEST_ERR_INTERNAL; }  // 兜底：绝不外抛（3.6）
}

extern "C" int vtest_stats_count(const vtest_stats* s, long* out) {
    if (s == nullptr || out == nullptr) return VTEST_ERR_NULL;
    const auto n = reinterpret_cast<const vtest::running_stats*>(s)->count();
    *out = static_cast<long>(n);  // 教学性简化：样本数转 long 时截断风险这里忽略
    return VTEST_OK;
}

extern "C" int vtest_stats_mean(const vtest_stats* s, double* out) {
    if (s == nullptr || out == nullptr) return VTEST_ERR_NULL;
    try {
        *out = reinterpret_cast<const vtest::running_stats*>(s)->mean();
        return VTEST_OK;
    } catch (const std::runtime_error&) {
        return VTEST_ERR_EMPTY;
    } catch (...) { return VTEST_ERR_INTERNAL; }
}

extern "C" int vtest_stats_version(void) {
    return 1;
}
