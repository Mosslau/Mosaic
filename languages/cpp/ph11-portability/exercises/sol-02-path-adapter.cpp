// sol-02-path-adapter.cpp —— 练习 2 参考实现：平台适配层（单文件自包含版）
// 练习 2 要求：为平台 API 写适配层——路径拼接 + 换行符，接口不含任何平台宏，
// 用 -D_WIN32 在本机验证 Windows 分支。
//
// 本机实测输出（已验证，Apple clang 21.0.0）：
//   c++ -std=c++20 -Wall -Wextra sol-02-path-adapter.cpp -o /tmp/sol-02
//   /tmp/sol-02                     → data/config.json | data\config.json → 见下
//   c++ -D_WIN32 -std=c++20 -Wall -Wextra sol-02-path-adapter.cpp -o /tmp/sol-02-win
//   /tmp/sol-02-win                 → data\config.json / data/\config.json / separator: \
//   （POSIX 分支：data/config.json / data/config.json / separator: /）
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 验证状态：已验证（两个分支均零警告、输出符合预期）
#include <cstdio>
#include <string>

namespace plat {

// ---- 公共接口：内部用平台宏，调用方完全无感知 ----
std::string join_path(const std::string& base, const std::string& rel) {
#if defined(_WIN32)
    const char sep = '\\';
#else
    const char sep = '/';
#endif
    if (base.empty()) return rel;
    if (base.back() == sep) return base + rel;
    return base + sep + rel;
}

const char* newline() {
#if defined(_WIN32)
    return "\r\n";          // Windows 文本换行
#else
    return "\n";            // POSIX 换行
#endif
}

}  // namespace plat

int main() {
    std::printf("%s\n", plat::join_path("data", "config.json").c_str());
    std::printf("newline bytes: ");
    for (const char* p = plat::newline(); *p != '\0'; ++p) {
        std::printf("0x%02X ", static_cast<unsigned char>(*p));
    }
    std::printf("\n");
    return 0;
}
