// path_util.cpp —— 平台差异隔离实现：所有 #if defined(_WIN32) 只出现在这里
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra path_util.cpp test_path.cpp -o /tmp/test_path
//           c++ -D_WIN32 -std=c++20 -Wall -Wextra path_util.cpp test_path.cpp -o /tmp/test_path_win
// 运行：    /tmp/test_path  与  /tmp/test_path_win
// 验证状态：已验证（两个分支均零警告；POSIX 分隔符 '/'，-D_WIN32 模拟分支 '\\'）
#include "path_util.h"

namespace ftool {

#if defined(_WIN32)
    // Windows：'/' 与 '\\' 都是合法分隔符，规范化时统一按 '\\' 处理
    constexpr char kSep = '\\';
    inline bool is_sep(char c) { return c == '\\' || c == '/'; }
#else
    // POSIX（Linux/macOS）：只有 '/' 是分隔符
    constexpr char kSep = '/';
    inline bool is_sep(char c) { return c == '/'; }
#endif

char separator() { return kSep; }

std::string join(const std::string& base, const std::string& rel) {
    if (base.empty()) return rel;
    if (is_sep(base.back())) return base + rel;      // 已带分隔符，不重复加
    return base + kSep + rel;
}

std::string normalize(const std::string& path) {
    std::string out;
    bool last_sep = false;
    for (char c : path) {
        if (is_sep(c)) {
            if (last_sep) continue;                  // 连续分隔符合并为一个
            out += kSep;
            last_sep = true;
        } else {
            out += c;
            last_sep = false;
        }
    }
    // 去结尾分隔符（保留根路径 "/" 或 "C:\" 的语义由调用方决定，这里只做最小处理）
    if (out.size() > 1 && is_sep(out.back())) out.pop_back();
    if (out.empty()) out = ".";
    return out;
}

std::string extension(const std::string& path) {
    // 找最后一个分隔符之后的最后一个 '.'（Windows 下 '/' 与 '\\' 都算分隔符）
    const std::size_t sep = path.find_last_of("/\\");
    const std::size_t name_start = (sep == std::string::npos) ? 0 : sep + 1;
    const std::size_t dot = path.find_last_of('.');
    if (dot == std::string::npos) return "";
    if (dot == name_start) return "";                           // 点紧跟分隔符：隐藏文件（如 .gitignore）
    if (dot == path.size() - 1) return "";                      // 结尾是点：不算扩展名
    return path.substr(dot);
}

}  // namespace ftool
