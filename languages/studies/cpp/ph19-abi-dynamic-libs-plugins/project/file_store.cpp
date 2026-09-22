// project/file_store.cpp —— 文件存储引擎插件（append-only 日志式）
// 教学点：同一 engine_api 下的「能力差异」后端。本插件把 put 实现成向数据
// 文件 append 一行 "key\tvalue"，get 全量扫文件取最后匹配；del 不提供
// （返回 ENGINE_ERR_UNSUPPORTED）——append-only 日志语义下物理删除需要
// compaction，超出本 demo 范围。宿主通过错误码感知能力，而不是靠猜插件名。
//
// 说明：这是教学 demo，每次 get 读全文件 O(n)；真实引擎需要索引/MemTable
// 分层——那是 roadmap 第 22 节存储引擎与数据库内核专项阶段（目录待建）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译（由 Makefile 统一执行）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib file_store.cpp -o build/plugins/libfile_store.dylib
// 验证状态：已验证（双编译器编译零警告）

#include <cstdio>

#include <fstream>
#include <sstream>
#include <string>

#include "storage_api.h"

struct storage_engine {
    std::string data_path;  // 数据文件路径（来自 create 的 config）
    std::string scratch;    // get/describe 的返回缓冲
};

static storage_engine* eng_create(const char* config) {
    auto* engine = new storage_engine;  // 由 eng_destroy 同一侧配对释放
    engine->data_path = (config != nullptr && config[0] != '\0')
                            ? config
                            : "/tmp/ph19_file_store.dat";
    return engine;
}

static void eng_destroy(storage_engine* engine) {
    delete engine;
}

static int eng_put(storage_engine* engine, const char* key, const char* value) {
    // append-only：新值追加在末尾，get 取最后一行匹配，天然支持覆盖语义
    std::ofstream out(engine->data_path, std::ios::app);
    if (!out) {
        return ENGINE_ERR_IO;
    }
    out << key << '\t' << value << '\n';
    return out ? ENGINE_OK : ENGINE_ERR_IO;
}

static const char* eng_get(storage_engine* engine, const char* key) {
    std::ifstream in(engine->data_path);
    if (!in) {
        return nullptr;  // 文件不存在 = 还没有任何数据
    }
    const std::string want(key);
    const std::size_t prefix_len = want.size() + 1;  // key + '\t'
    std::string line;
    bool found = false;
    while (std::getline(in, line)) {
        if (line.size() > prefix_len && line.compare(0, want.size(), want) == 0 &&
            line[want.size()] == '\t') {
            engine->scratch = line.substr(prefix_len);  // 最后匹配覆盖之前的
            found = true;
        }
    }
    return found ? engine->scratch.c_str() : nullptr;
}

static int eng_del(storage_engine* engine, const char* key) {
    (void)engine;
    (void)key;
    // append-only 日志的物理删除需要 compaction/tombstone，超出本 demo 范围
    return ENGINE_ERR_UNSUPPORTED;
}

static const char* eng_describe(storage_engine* engine) {
    engine->scratch = "file_store: append-only log at " + engine->data_path +
                      " (get 线性扫描; del 不支持)";
    return engine->scratch.c_str();
}

extern "C" const engine_api* engine_get_api(void) {
    static const engine_api api = {
        1,  // api_major
        0,  // api_minor
        eng_create,
        eng_destroy,
        eng_put,
        eng_get,
        eng_del,  // 能力差异：返回 ENGINE_ERR_UNSUPPORTED
        eng_describe,
    };
    return &api;
}
