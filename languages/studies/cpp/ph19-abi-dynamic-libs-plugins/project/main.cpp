// project/main.cpp —— 存储引擎插件宿主（dlopen 加载后端）
// 教学点：宿主把「插件边界纪律」串成一条完整链路——
//   1. dlopen 加载插件 → 2. dlsym 拿 engine_get_api → 3. 校验接口版本
//      → 4. create 拿 opaque 引擎 → 5. 通过功能表调用 put/get/del/describe
//      → 6. destroy 再 dlclose（顺序：对象先毁、库后卸）。
//   7. 能力探测：del 对不同后端可能 OK 也可能 UNSUPPORTED——宿主按错误码
//      分支，而不是按插件文件名特判（插件不该被宿主"点名"）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译/运行：见 Makefile（make / make run / make run-file / make test）
// 手工运行示例：
//   ./build/store_host ./build/plugins/libmem_store.dylib
//   ./build/store_host ./build/plugins/libfile_store.dylib /tmp/ph19_fs.dat
// 验证状态：已验证（双编译器编译零警告；make test 两个引擎自测全绿、退出码 0）

#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

#include "storage_api.h"

namespace {

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

// 插件句柄 + 引擎指针的 RAII 组合：对象（engine）在 dlclose 之前析构。
// 成员声明顺序 lib → engine 确保构造顺序，析构则逆序：engine 先 destroy，
// lib 再 dlclose。
class EngineSession {
public:
    EngineSession(const std::string& path, const char* config, int need_major)
        : lib_(path) {
        // 1) 取功能表入口
        const char* err_str = nullptr;
        (void)dlerror();
        void* sym = dlsym(lib_.get(), "engine_get_api");
        if (sym == nullptr) {
            err_str = dlerror();
            throw std::runtime_error("dlsym engine_get_api 失败: " +
                                     std::string(err_str != nullptr ? err_str : "未知错误"));
        }
        auto get_api = reinterpret_cast<const engine_api* (*)()>(sym);
        api_ = get_api();
        if (api_ == nullptr) {
            throw std::runtime_error("engine_get_api 返回空");
        }
        // 2) 版本校验：major 不符=接口断裂，拒绝使用
        if (api_->api_major != need_major) {
            throw std::runtime_error("接口版本不兼容：宿主需 major=" +
                                     std::to_string(need_major) + "，插件提供 major=" +
                                     std::to_string(api_->api_major));
        }
        // 3) 创建引擎（谁创建谁销毁：对应 destroy 在下面析构函数里）
        engine_ = api_->create(config);
        if (engine_ == nullptr) {
            throw std::runtime_error("create 返回空引擎");
        }
        std::printf("[host] 已加载 %s (api %d.%d)\n", path.c_str(), api_->api_major,
                    api_->api_minor);
    }

    ~EngineSession() {
        if (engine_ != nullptr) {
            api_->destroy(engine_);  // 先 destroy：析构函数代码还在库里
        }
        std::printf("[host] 引擎已销毁，随后 dlclose 卸载库\n");
    }

    EngineSession(const EngineSession&) = delete;
    EngineSession& operator=(const EngineSession&) = delete;

    const engine_api& api() const { return *api_; }
    storage_engine* engine() const { return engine_; }

private:
    DlHandle lib_;           // 先构造 → 后析构（dlclose 最后执行）
    const engine_api* api_ = nullptr;
    storage_engine* engine_ = nullptr;
};

void print_err(int rc, const char* what) {
    switch (rc) {
    case ENGINE_ERR_MISSING:
        std::printf("    %s -> ENGINE_ERR_MISSING（key 不存在）\n", what);
        break;
    case ENGINE_ERR_UNSUPPORTED:
        std::printf("    %s -> ENGINE_ERR_UNSUPPORTED（该后端不支持此操作）\n", what);
        break;
    default:
        std::printf("    %s -> 错误码 %d\n", what, rc);
        break;
    }
}

int run_session(const std::string& path, const char* config) {
    EngineSession session(path, config, /*need_major=*/1);
    const engine_api& api = session.api();
    storage_engine* e = session.engine();

    std::printf("[host] describe: %s\n", api.describe(e));

    // —— 确定性操作序列：对两个后端结果一致，除了 del（能力差异教学点）——
    int failures = 0;
    const auto expect = [&](bool cond, const char* msg) {
        if (!cond) {
            ++failures;
            std::fprintf(stderr, "    [FAIL] %s\n", msg);
        }
    };

    std::printf("[host] put(k1, hello), put(k2, world)\n");
    expect(api.put(e, "k1", "hello") == ENGINE_OK, "put k1");
    expect(api.put(e, "k2", "world") == ENGINE_OK, "put k2");

    const char* got_k1 = api.get(e, "k1");
    std::printf("[host] get(k1) -> %s\n", got_k1 != nullptr ? got_k1 : "(nullptr)");
    expect(got_k1 != nullptr && std::string(got_k1) == "hello", "get(k1) == hello");
    const char* got_k2 = api.get(e, "k2");
    std::printf("[host] get(k2) -> %s\n", got_k2 != nullptr ? got_k2 : "(nullptr)");
    expect(got_k2 != nullptr && std::string(got_k2) == "world", "get(k2) == world");
    const char* got_missing = api.get(e, "no_such_key");
    std::printf("[host] get(no_such_key) -> %s\n", got_missing == nullptr ? "(nullptr)" : got_missing);
    expect(got_missing == nullptr, "get(不存在) == nullptr");

    std::printf("[host] 覆盖语义: put(k1, bye) 后 get(k1)\n");
    expect(api.put(e, "k1", "bye") == ENGINE_OK, "put k1 覆盖");
    const char* v1 = api.get(e, "k1");
    std::printf("[host] get(k1) -> %s\n", v1);
    expect(v1 != nullptr && std::string(v1) == "bye", "覆盖后 get(k1) == bye");

    std::printf("[host] del(k1)（能力探测：mem 应 OK，file 应 UNSUPPORTED）\n");
    const int rc = api.del(e, "k1");
    if (rc == ENGINE_OK) {
        std::printf("    del -> ENGINE_OK；再 get(k1) 应为 nullptr\n");
        expect(api.get(e, "k1") == nullptr, "del 后 get(k1) == nullptr");
        expect(api.del(e, "k1") == ENGINE_ERR_MISSING, "重复 del 报 MISSING");
    } else {
        print_err(rc, "del(k1)");
        expect(rc == ENGINE_ERR_UNSUPPORTED, "file 后端 del 报 UNSUPPORTED");
    }

    if (failures == 0) {
        std::printf("[PASS] %s 全部断言通过\n\n", path.c_str());
        return 0;
    }
    std::fprintf(stderr, "[FAIL] %s 有 %d 项断言失败\n\n", path.c_str(), failures);
    return 1;
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc < 2 || argc > 3) {
        std::fprintf(stderr,
                     "用法: %s <引擎插件路径> [config]\n"
                     "  例: %s ./build/plugins/libmem_store.dylib\n"
                     "      %s ./build/plugins/libfile_store.dylib /tmp/ph19_fs.dat\n",
                     argv[0], argv[0], argv[0]);
        return 2;
    }
    const std::string plugin_path = argv[1];
    const char* config = argc >= 3 ? argv[2] : nullptr;

    try {
        return run_session(plugin_path, config);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[ERROR] %s\n", e.what());
        return 3;
    }
}
