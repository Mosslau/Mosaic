// examples/ex05-lifecycle-host.cpp —— 插件对象生命周期 + 所有权纪律宿主
// 教学点：
//   1. opaque 对象生命周期由谁管：create → 使用 → destroy，全部经插件导出
//      的 C ABI 函数，宿主绝不直接 delete（对象类型不完整，编译器也禁止）。
//   2. 销毁先于卸载：dlclose 卸载的是代码，若对象还活着、其析构函数代码已被
//      卸载，析构调用就是跳到已卸载内存——UB。所以顺序必须是
//      先 destroy 所有插件对象，再 dlclose 句柄。
//   3. 本文件用 RAII 把这两条纪律固化：ObjHolder 持 destroy 函数指针并在
//      析构时调用；DlHandle 在作用域退出时 dlclose。成员按声明顺序构造、
//      逆序析构：lib(句柄) 先构造 → holder 后构造 → 退出时 holder 先析构
//      （调 ts_destroy）→ lib 后析构（dlclose）。顺序由语言保证，人不会忘。
//   4. 输出会显示每个对象析构发生在 dlclose 之前（看打印顺序即可验证）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 前置：先按 ex05-plugin-object.cpp 文件头编译 /tmp/libtextstats.dylib
// 编译宿主：
//   clang++ -std=c++20 -Wall -Wextra ex05-lifecycle-host.cpp -o /tmp/ph19cpp-ex05-host
// 运行：/tmp/ph19cpp-ex05-host
// 验证状态：已验证（双编译器实测：编译零警告、运行通过、析构先于卸载、
//   "跨侧 delete 被类型系统禁止"以编译错误形式出现，退出码 0）

#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

// —— 插件 C ABI 接口声明（宿主侧只forward-declare opaque 类型）——
struct text_stats;  // 不完整类型：宿主不能 delete、不能取成员——编译器护栏

extern "C" text_stats* ts_create(void);
extern "C" void ts_destroy(text_stats*);
extern "C" void ts_add(text_stats*, const char* word);
extern "C" const char* ts_summary(const text_stats*);

namespace {

class DlHandle {
public:
    explicit DlHandle(const std::string& path) : handle_(dlopen(path.c_str(), RTLD_NOW)) {
        if (handle_ == nullptr) {
            throw std::runtime_error("dlopen 失败: " + std::string(dlerror()));
        }
    }
    ~DlHandle() {
        if (handle_ != nullptr) {
            dlclose(handle_);
        }
    }
    DlHandle(const DlHandle&) = delete;
    DlHandle& operator=(const DlHandle&) = delete;
    void* get() const { return handle_; }

private:
    void* handle_;
};

// 从句柄里解析一个导出函数指针（含 dlerror 错误处理）
void* sym(void* handle, const char* name) {
    (void)dlerror();
    void* p = dlsym(handle, name);
    if (p == nullptr) {
        throw std::runtime_error(std::string("dlsym ") + name + ": " + dlerror());
    }
    return p;
}

using destroy_fn = void (*)(text_stats*);

// opaque 对象的 RAII 持有者：析构调用插件自己的销毁函数（自定义 deleter，
// 与 std::unique_ptr<T, deleter> 的思路一致；deleter 来自 dlsym 而非编译期）
class ObjHolder {
public:
    ObjHolder(text_stats* obj, destroy_fn destroy) : obj_(obj), destroy_(destroy) {}
    ~ObjHolder() {
        if (obj_ != nullptr) {
            std::printf("[host ] ts_destroy() 在 dlclose 之前被调用\n");
            destroy_(obj_);  // 销毁责任回插件侧（new 在插件侧，delete 也在插件侧）
        }
    }
    ObjHolder(const ObjHolder&) = delete;
    ObjHolder& operator=(const ObjHolder&) = delete;
    text_stats* get() const { return obj_; }

private:
    text_stats* obj_;
    destroy_fn destroy_;
};

}  // namespace

int main() {
    try {
        // 顺序演示：lib 先构造，holder 后构造 → holder 先析构，lib 后析构
        DlHandle lib("/tmp/libtextstats.dylib");
        std::printf("[host ] dlopen 成功\n");

        auto create = reinterpret_cast<text_stats* (*)()>(sym(lib.get(), "ts_create"));
        auto destroy = reinterpret_cast<destroy_fn>(sym(lib.get(), "ts_destroy"));
        auto add = reinterpret_cast<void (*)(text_stats*, const char*)>(sym(lib.get(), "ts_add"));
        auto summary = reinterpret_cast<const char* (*)(const text_stats*)>(sym(lib.get(), "ts_summary"));

        text_stats* raw = create();  // new 在插件侧发生
        ObjHolder stats(raw, destroy);
        std::printf("[host ] ts_create() 拿到 opaque 对象 %p\n", static_cast<void*>(raw));

        add(stats.get(), "hello");
        add(stats.get(), "plugin");
        add(stats.get(), "lifecycle");
        std::printf("[host ] ts_summary() = %s\n", summary(stats.get()));

        // 故意破坏纪律的演示（编译期就失败，这就是 opaque + 不完整类型的设计意图）：
        //   delete raw;  // ERROR: 不能对不完整类型 delete
        //   raw->words;  // ERROR: 不能访问不完整类型成员
        // 宿主想销毁对象，唯一合法路径是 ts_destroy → 由本文件 RAII 在析构时执行。

        std::printf("[host ] 退出作用域：holder 先析构（destroy），DlHandle 后析构（dlclose）\n");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[ERROR] %s\n", e.what());
        return 1;
    }
}
