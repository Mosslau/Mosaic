// cpp_side.cc —— C++ 侧实现；include 生成的桥接头以回调 extern "Rust" 函数
// 生成的桥接头路径 = <package 名>/src/main.rs.h（本工程 package 名为 cxx_bridge_ex04）
#include "cpp_side.h"

#include "cxx_bridge_ex04/src/main.rs.h"

int64_t cpp_sum(const rust::Vec<int64_t>& values) {
    int64_t acc = 0;
    for (const int64_t v : values) {
        acc += v;
    }
    return acc;
}

rust::String cpp_describe(rust::Str name) {
    // C++ 侧主动调用 extern "Rust" 的 rust_greeting —— 双向的 R→C→R 路径
    return rust_greeting(name);
}

int32_t cpp_compose(int32_t x) {
    return rust_triple(x) + 1;  // 3x + 1：来自 C++ 侧对 rust_triple 的回调
}
