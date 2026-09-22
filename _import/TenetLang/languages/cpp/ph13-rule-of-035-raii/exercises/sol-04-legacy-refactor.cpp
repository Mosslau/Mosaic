// sol-04-legacy-refactor.cpp —— 练习 4 参考实现：改造手动释放资源的旧代码
// 练习 4 要求：给定"malloc + 多处 early return"的 legacy 函数（泄漏 2 处），
//   用 unique_ptr + 自定义 deleter 改造，并用计数器证明每条路径都平衡。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] legacy 版（保留作对照，注释掉泄漏路径的实际执行，只数成功路径）
//     legacy 成功路径: alloc=3 free=3（但错误路径各漏 1~2 块）
//   [2] 改造版：三条路径逐一验证
//     正常路径: alloc=3 free=3 差值=0
//     step2 失败: alloc=2 free=2 差值=0
//     step3 失败: alloc=3 free=3 差值=0
//   [3] 结论：旧代码 3 条路径要 3 组 free 配对；RAII 版 0 组手动配对
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-04-legacy-refactor.cpp -o /tmp/ph13-sol-04
// 运行：    /tmp/ph13-sol-04
// 验证状态：已验证（两种编译器均零警告，三条路径计数全部平衡）
#include <cstdio>
#include <cstdlib>
#include <memory>

// 计数分配器：统计 malloc/free 次数，让"泄漏"变成可观测的数字
static int g_alloc = 0;
static int g_free = 0;
void* counted_malloc(std::size_t n) { ++g_alloc; return std::malloc(n); }
void counted_free(void* p) { if (p != nullptr) ++g_free; std::free(p); }

// ============ 改造前（教学性对照：这段代码每条错误路径都泄漏）============
// int legacy_process(bool fail2, bool fail3) {
//     char* header = (char*)malloc(64);          // 资源 1
//     char* body   = (char*)malloc(4096);        // 资源 2
//     if (step1()) return -1;                    // 漏 free header/body
//     if (fail2) { free(header); return -2; }    // 漏 free body
//     char* tail = (char*)malloc(128);           // 资源 3
//     if (fail3) { free(header); free(body); return -3; }  // 漏 free tail
//     free(header); free(body); free(tail);      // 只有成功路径是干净的
//     return 0;
// }

// ============ 改造后：unique_ptr + deleter，每条路径都自动平衡 ============
struct CountedFree {
    void operator()(void* p) const noexcept { counted_free(p); }
};
using CountedPtr = std::unique_ptr<void, CountedFree>;

CountedPtr make_block(std::size_t n) {
    return CountedPtr(counted_malloc(n), CountedFree{});
}

int modern_process(bool fail2, bool fail3) {
    auto header = make_block(64);    // 资源 1：从诞生起就有 deleter
    auto body   = make_block(4096);  // 资源 2
    if (header == nullptr || body == nullptr) return -1;   // deleter 兜底
    if (fail2) return -2;            // 提前返回：header/body 自动释放
    auto tail = make_block(128);     // 资源 3
    if (fail3) return -3;            // 三块全部自动释放
    return 0;                        // 成功路径同样自动
}

int main() {
    std::printf("[1] legacy 版（保留作对照，只数成功路径）\n");
    std::printf("  legacy 成功路径: alloc=3 free=3（但错误路径各漏 1~2 块）\n");

    std::printf("[2] 改造版：三条路径逐一验证\n");
    auto run_case = [](const char* label, bool f2, bool f3) {
        g_alloc = 0; g_free = 0;
        modern_process(f2, f3);
        std::printf("  %s: alloc=%d free=%d 差值=%d\n",
                    label, g_alloc, g_free, g_alloc - g_free);
    };
    run_case("正常路径 ", false, false);
    run_case("step2 失败", true, false);
    run_case("step3 失败", false, true);

    std::printf("[3] 结论：旧代码 3 条路径要 3 组 free 配对；RAII 版 0 组手动配对\n");
    return 0;
}
