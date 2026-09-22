// exercises/sol-03-host.cpp —— 练习 3 参考实现（版本校验宿主）
// 教学点：宿主声明自己需要的接口版本，加载插件后「先取版本、再校验、
// 最后才碰业务函数」。校验规则（主文档 3.7）：
//   · major 不同 → 二进制不兼容，直接拒绝（返回可诊断错误、退出码非 0）
//   · major 相同、minor 不足 → 宿主需要的某个能力没有，拒绝或降级
//   · 通过 → 才调用 plugin_behavior 等业务函数
// 顺序为什么重要：版本校验之前调用业务函数 = 用新接口假设调旧实现，
// 轻则返回值错位（sol-03 v1 的 behavior=10 会被当成 v2 语义），重则读越界。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++
// 前置：按 sol-03-versioned-plugin.cpp 文件头编译 v1/v20/v21 三个库
// 编译宿主：
//   clang++ -std=c++20 -Wall -Wextra sol-03-host.cpp -o /tmp/ph19cpp-sol03-host
// 运行：
//   /tmp/ph19cpp-sol03-host /tmp/libplugin_v1.dylib    # 拒绝（major 1 < 2）→ 退出非 0
//   /tmp/ph19cpp-sol03-host /tmp/libplugin_v20.dylib   # 拒绝（minor 0 < 1）→ 退出非 0
//   /tmp/ph19cpp-sol03-host /tmp/libplugin_v21.dylib   # 通过 → behavior=21，退出 0
// 验证状态：已验证（编译零警告；v1/v20 拒绝、v21 通过，退出码语义正确）
#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

namespace {

// 宿主编译时声明的接口需求：需要 major=2 且 minor>=1
constexpr int kNeedMajor = 2;
constexpr int kNeedMinor = 1;

using major_fn = int (*)();
using minor_fn = int (*)();
using behavior_fn = int (*)();
using name_fn = const char* (*)();

class DlHandle {
public:
    explicit DlHandle(const std::string& path) : handle_(dlopen(path.c_str(), RTLD_NOW)) {
        if (handle_ == nullptr) {
            throw std::runtime_error("dlopen 失败: " + std::string(dlerror()));
        }
    }
    ~DlHandle() { dlclose(handle_); }
    DlHandle(const DlHandle&) = delete;
    DlHandle& operator=(const DlHandle&) = delete;
    void* get() const { return handle_; }

private:
    void* handle_;
};

void* lookup(void* handle, const char* symbol) {
    (void)dlerror();
    void* p = dlsym(handle, symbol);
    const char* err = dlerror();
    if (err != nullptr) {
        throw std::runtime_error(std::string("dlsym '") + symbol + "' 失败: " + err);
    }
    return p;
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::fprintf(stderr, "用法: %s <插件路径>\n", argv[0]);
        return 2;
    }
    const std::string path = argv[1];

    try {
        DlHandle lib(path);
        auto get_major = reinterpret_cast<major_fn>(lookup(lib.get(), "plugin_version_major"));
        auto get_minor = reinterpret_cast<minor_fn>(lookup(lib.get(), "plugin_version_minor"));
        auto get_name = reinterpret_cast<name_fn>(lookup(lib.get(), "plugin_name"));

        // —— 版本校验必须在任何业务符号之前 ——
        const int have_major = get_major();
        const int have_minor = get_minor();
        std::printf("插件 %s: version=%d.%d  宿主需求: major=%d minor>=%d\n", get_name(),
                    have_major, have_minor, kNeedMajor, kNeedMinor);

        if (have_major != kNeedMajor) {
            std::fprintf(stderr, "[拒绝] 二进制不兼容：宿主需 major=%d，插件提供 major=%d —— "
                                 "请升级插件或重编译宿主（major 变化=接口布局/签名断裂）\n",
                         kNeedMajor, have_major);
            return 3;
        }
        if (have_minor < kNeedMinor) {
            std::fprintf(stderr, "[拒绝] 能力不足：宿主需 minor>=%d，插件提供 minor=%d —— "
                                 "插件偏旧，缺少宿主依赖的新增能力\n",
                         kNeedMinor, have_minor);
            return 4;
        }

        // —— 校验通过，才取业务函数并使用 ——
        auto behavior = reinterpret_cast<behavior_fn>(lookup(lib.get(), "plugin_behavior"));
        const int got = behavior();
        std::printf("[通过] plugin_behavior() = %d\n", got);
        if (got != kNeedMajor * 10 + have_minor) {
            std::fprintf(stderr, "[FAIL] behavior 与版本语义不符\n");
            return 1;
        }
        std::printf("[PASS]\n");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[ERROR] %s\n", e.what());
        return 2;
    }
}
