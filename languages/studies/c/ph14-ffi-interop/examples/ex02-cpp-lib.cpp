// ex02-cpp-lib.cpp —— C 调 C++ 包装层：用 C++ 实现、以 extern "C" 导出 C 接口
//
// 场景（roadmap 学习内容"C 调 C++ 包装层"）：项目主体是 C++，但要暴露给
//   只认 C 接口的调用方（C 程序、Python ctypes、Rust FFI 都算）。
//   做法：写一层 extern "C" 的 C 风格包装函数，把 C++ 实现藏在后面，
//   C 调用方（.c 文件）只看到 C 函数签名。
//
// 编译（macOS）：
//   c++ -Wall -Wextra -std=c++17 -dynamiclib ex02-cpp-lib.cpp \
//       -o /tmp/ph14-ex/libcppwrap.dylib
// 注意：extern "C" 只是链接约定，函数体仍是 C++ —— 这里内部用了 std::string。
#include <cstdint>
#include <string>

namespace {
std::string g_greeting = "hello from C++";   // C++ 设施藏在包装层后面
}

extern "C" {

/* 借用内部 std::string 的缓冲区；调用方不得 free，且任何修改
 * g_greeting 的调用都可能使先前拿到的指针失效 */
const char *cw_greet(void) {
    return g_greeting.c_str();
}

int32_t cw_double(int32_t x) {
    return x * 2;
}

void cw_set_greeting(const char *s) {
    if (s != nullptr)
        g_greeting = s;
}

}  // extern "C"
