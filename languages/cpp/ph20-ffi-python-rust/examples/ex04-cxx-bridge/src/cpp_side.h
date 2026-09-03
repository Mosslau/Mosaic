// cpp_side.h —— C++ 侧实现头；Rust 侧 unsafe extern "C++" 的签名以它为准
// 注意 cxx 的类型翻译：Rust 的 Vec/String/&str 在 C++ 侧是
// rust::Vec / rust::String / rust::Str，不是 std::vector / std::string。
#pragma once

#include <cstdint>

#include "rust/cxx.h"

int64_t cpp_sum(const rust::Vec<int64_t>& values);
rust::String cpp_describe(rust::Str name);
int32_t cpp_compose(int32_t x);
