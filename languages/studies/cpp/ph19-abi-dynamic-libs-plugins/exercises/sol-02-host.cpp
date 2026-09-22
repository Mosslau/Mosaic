// exercises/sol-02-host.cpp —— 练习 2 参考实现（dlopen 宿主）
// 教学点：dlopen/dlsym/dlerror/dlclose 四件套 + RAII 句柄；宿主不链接插件，
// 运行期按路径加载、按名字找符号；Windows 对照 LoadLibrary/GetProcAddress/
// FreeLibrary（未在本环境验证）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++
// 前置：先按 sol-02-operator-plugin.cpp 文件头编译 /tmp/libop_sum.dylib
// 编译宿主：
//   clang++ -std=c++20 -Wall -Wextra sol-02-host.cpp -o /tmp/ph19cpp-sol02-host
// 运行：
//   /tmp/ph19cpp-sol02-host                        # 正常路径，输出和 21
//   /tmp/ph19cpp-sol02-host /tmp/nope.dylib        # 错误路径 1：dlopen 失败
//   /tmp/ph19cpp-sol02-host /tmp/libop_sum.dylib   # 正常
// 验证状态：已验证（编译零警告；正常路径输出 op_sum=21、错误路径报错退出非 0）
#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

namespace {

using name_fn = const char* (*)();
using sum_fn = long long (*)(const long long*, long long);

class DlHandle {
public:
    explicit DlHandle(const std::string& path) : handle_(dlopen(path.c_str(), RTLD_NOW)) {
        if (handle_ == nullptr) {
            throw std::runtime_error("dlopen '" + path + "' 失败: " + dlerror());
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
    const std::string plugin_path =
        argc > 1 ? argv[1] : "/tmp/libop_sum.dylib";
    const long long xs[] = {1, 2, 3, 4, 5, 6};
    constexpr long long kExpected = 21;

    try {
        DlHandle lib(plugin_path);
        auto name = reinterpret_cast<name_fn>(lookup(lib.get(), "op_name"));
        auto sum = reinterpret_cast<sum_fn>(lookup(lib.get(), "op_sum"));

        const long long got = sum(xs, 6);
        std::printf("plugin '%s': op_sum = %lld\n", name(), static_cast<long long>(got));
        if (got != kExpected) {
            std::fprintf(stderr, "[FAIL] 期望 %lld，实得 %lld\n", kExpected, got);
            return 1;
        }
        std::printf("[PASS]\n");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[ERROR] %s\n", e.what());
        return 2;  // 错误路径：退出码非 0
    }
}
