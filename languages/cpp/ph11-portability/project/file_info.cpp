// file_info.cpp —— 基于 std::filesystem 的可移植实现
// 教学点：路径规范化、文件元数据这类"标准库已替你跨平台"的能力，直接用
// std::filesystem（C++17），适配层只留给 filesystem 管不到的 API。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra file_info.cpp main.cpp path_util.cpp -o /tmp/ftool
// 运行：    /tmp/ftool info <路径>   /tmp/ftool ls <目录>
// 验证状态：已验证（两种编译器均零警告；POSIX 分支的 gmtime_r 实际编译运行通过，
//           Windows 分支的 gmtime_s 需 MSVC，未在本环境验证——但它是同一 API 的
//           MSVC 标准替代，std::filesystem 部分在 Windows 上同样可移植，输出见 README）
#include "file_info.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <iomanip>
#include <sstream>

namespace fs = std::filesystem;

namespace ftool {

std::optional<FileInfo> file_info(const std::string& path) {
    std::error_code ec;
    const fs::path p(path);
    const bool is_dir = fs::is_directory(p, ec);
    if (ec) return std::nullopt;

    // 文件大小：目录没有 file_size 语义，单独处理
    const std::uintmax_t size = is_dir ? 0 : fs::file_size(p, ec);
    if (ec) return std::nullopt;

    // 修改时间：file_time_type 转 system_clock 再转可读字符串
    const fs::file_time_type mtime = fs::last_write_time(p, ec);
    if (ec) return std::nullopt;
    const auto sctp = std::chrono::time_point_cast<std::chrono::system_clock::duration>(
        mtime - fs::file_time_type::clock::now() + std::chrono::system_clock::now());
    const std::time_t tt = std::chrono::system_clock::to_time_t(sctp);
    std::tm tmv{};
#if defined(_WIN32)
    gmtime_s(&tmv, &tt);       // MSVC 提供 gmtime_s
#else
    gmtime_r(&tt, &tmv);       // POSIX 提供 gmtime_r
#endif
    std::ostringstream os;
    os << std::put_time(&tmv, "%Y-%m-%d %H:%M:%S");

    return FileInfo{size, os.str(), is_dir};
}

std::vector<std::string> list_dir(const std::string& dir) {
    std::vector<std::string> out;
    std::error_code ec;
    fs::directory_iterator it(dir, ec), end;
    if (ec) return out;                    // 目录不存在/不可读：返回空
    for (; it != end; it.increment(ec)) {
        if (ec) break;
        out.push_back(it->path().filename().string());
    }
    std::sort(out.begin(), out.end());
    return out;
}

}  // namespace ftool
