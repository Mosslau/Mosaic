// project/mem_store.cpp —— 内存存储引擎插件
// 教学点：插件 = 对 engine_api 的完整实现。本插件把 storage_engine 实现成
// 一个持有 unordered_map 的对象；create/destroy 在**插件这一侧**负责
// new/delete（跨边界释放红线：宿主只调函数指针，绝不动对象内存）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译（由 Makefile 统一执行；也可手跑）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib mem_store.cpp -o build/plugins/libmem_store.dylib
// 验证状态：已验证（双编译器编译零警告）

#include <string>
#include <unordered_map>

#include "storage_api.h"

struct storage_engine {
    std::unordered_map<std::string, std::string> kv;
    std::string scratch;  // 返回给宿主的字符串缓冲：生命周期=到下一次引擎调用
};

static storage_engine* eng_create(const char* /*config*/) {
    // 内存引擎不需要配置参数
    return new storage_engine;  // 由 eng_destroy 在同一侧配对释放
}

static void eng_destroy(storage_engine* engine) {
    delete engine;  // 与 eng_create 的 new 在同一编译单元配对
}

static int eng_put(storage_engine* engine, const char* key, const char* value) {
    engine->kv[std::string(key)] = value;
    return ENGINE_OK;
}

static const char* eng_get(storage_engine* engine, const char* key) {
    const auto it = engine->kv.find(key);
    if (it == engine->kv.end()) {
        return nullptr;  // 不存在：返回 NULL 而非空串（区分「存在空值」）
    }
    // 拷贝进 scratch 再返回：unordered_map 的引用在后续插入 rehash 后会失效，
    // 而 scratch 的地址稳定到下一次引擎调用——这正是文件头承诺的生命周期
    engine->scratch = it->second;
    return engine->scratch.c_str();
}

static int eng_del(storage_engine* engine, const char* key) {
    return engine->kv.erase(key) == 1 ? ENGINE_OK : ENGINE_ERR_MISSING;
}

static const char* eng_describe(storage_engine* engine) {
    engine->scratch = "mem_store: in-memory unordered_map, " +
                      std::to_string(engine->kv.size()) + " entries";
    return engine->scratch.c_str();
}

// 接口版本与功能表（本 demo 所有引擎共享 api_major=1）
extern "C" const engine_api* engine_get_api(void) {
    static const engine_api api = {
        1,  // api_major
        0,  // api_minor
        eng_create,
        eng_destroy,
        eng_put,
        eng_get,
        eng_del,  // 内存后端支持删除
        eng_describe,
    };
    return &api;
}
