// examples/ex03-host.cpp —— dlopen/dlsym/dlerror 插件宿主
// 教学点：roadmap 学习内容「动态库加载」。宿主不链接插件，而是在运行期
// dlopen 一个路径、dlsym 按名字取函数指针、用完 dlclose——这是插件机制
// 的运行时底座，也是「换插件不换宿主」的根源。
//
// dlopen 三步曲：
//   1. dlopen(path, flag)：把 dylib 映射进进程，返回句柄；失败返回 nullptr
//   2. dlsym(handle, name)：按符号名查找地址；失败返回 nullptr（配合 dlerror 看原因）
//   3. dlclose(handle)：引用计数 -1，归零才真正卸载
// 任何一个失败都要用 dlerror() 取人类可读错误并妥善退出——插件来自外部，
// 路径错、符号缺、ABI 不符都可能在运行期才暴露。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 前置：先按 ex03-plugin-add.cpp / ex03-plugin-mul.cpp 文件头编译两个插件
// 编译宿主：
//   clang++ -std=c++20 -Wall -Wextra ex03-host.cpp -o /tmp/ph19cpp-ex03-host
// 运行（默认加载两个插件）：
//   /tmp/ph19cpp-ex03-host
// 运行（指定插件路径；也能单插件）：
//   /tmp/ph19cpp-ex03-host /tmp/libop_add.dylib
// 对照（Windows 版本见主文档 3.5：LoadLibrary/GetProcAddress/FreeLibrary）：
//   dlopen → LoadLibrary；dlsym → GetProcAddress；dlclose → FreeLibrary
// 验证状态：已验证（双编译器实测：编译零警告、两个插件均加载调用成功、
//   dlsym 未找到符号的错误路径输出正确、退出码 0）

#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

// 插件接口的函数指针类型——「声明即契约」：签名必须与插件源里的约定一致
using kind_fn = int (*)();
using apply_fn = double (*)(double, double);

// RAII 收口 dlopen 句柄：宿主退出前自动 dlclose（R.1 + ph13 手法跨进插件边界）
class DlHandle {
public:
    explicit DlHandle(const std::string& path) : handle_(dlopen(path.c_str(), RTLD_NOW)) {
        if (handle_ == nullptr) {
            const char* err = dlerror();
            throw std::runtime_error("dlopen '" + path + "' 失败: " + (err ? err : "未知错误"));
        }
    }
    ~DlHandle() {
        if (handle_ != nullptr) {
            dlclose(handle_);  // 卸载动态库（引用计数归零时才真正卸载）
        }
    }
    DlHandle(const DlHandle&) = delete;
    DlHandle& operator=(const DlHandle&) = delete;
    void* get() const { return handle_; }

private:
    void* handle_;
};

// 通用 dlsym 封装：清掉陈旧的 dlerror 状态，符号缺失时给带名字的错误信息
void* lookup_symbol(void* handle, const char* name) {
    (void)dlerror();  // 先清空上一次错误，避免误判
    void* sym = dlsym(handle, name);
    const char* err = dlerror();
    if (err != nullptr) {
        throw std::runtime_error(std::string("dlsym '") + name + "' 失败: " + err);
    }
    return sym;
}

void run_plugin(const std::string& path) {
    std::printf("--- 加载插件: %s ---\n", path.c_str());
    DlHandle lib(path);

    // 逐符号查找并 cast 成对应的函数指针类型
    auto version = reinterpret_cast<kind_fn>(lookup_symbol(lib.get(), "plugin_kind"));
    auto apply = reinterpret_cast<apply_fn>(lookup_symbol(lib.get(), "plugin_apply"));

    std::printf("  plugin_kind() = %d\n", version());
    const double a = 6.0;
    const double b = 7.0;
    std::printf("  plugin_apply(%.1f, %.1f) = %.1f\n", a, b, apply(a, b));
}

}  // namespace

int main(int argc, char* argv[]) {
    // 默认路径与文件头编译命令一致；也接受命令行传入自定义插件路径
    std::vector<std::string> plugins;
    if (argc > 1) {
        for (int i = 1; i < argc; ++i) {
            plugins.emplace_back(argv[i]);
        }
    } else {
        plugins = {"/tmp/libop_add.dylib", "/tmp/libop_mul.dylib"};
    }

    try {
        for (const std::string& path : plugins) {
            run_plugin(path);
        }

        // 错误路径演示：dlsym 一个不存在的符号，应被 lookup_symbol 拦下
        std::printf("--- 错误路径: dlsym 不存在的符号 ---\n");
        DlHandle lib(plugins.front());
        (void)dlerror();
        void* missing = dlsym(lib.get(), "no_such_symbol");
        if (missing == nullptr && dlerror() != nullptr) {
            std::printf("  预期内：no_such_symbol 不存在，dlerror() 有输出\n");
        }
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[ERROR] %s\n", e.what());
        return 1;
    }
}
