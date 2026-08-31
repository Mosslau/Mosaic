// main.cpp —— 跨平台文件工具库 CLI 入口
// 子命令：join <base> <rel> | normalize <path> | ext <path> | info <path> | ls <dir>
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra main.cpp path_util.cpp file_info.cpp -o /tmp/ftool
// 运行：    /tmp/ftool <子命令> <参数...>
// 验证状态：已验证（两种编译器均零警告，示例输出见 project/README.md）
#include <cstdio>
#include <cstring>
#include <string>

#include "file_info.h"
#include "path_util.h"

static int usage() {
    std::printf(
        "usage: ftool <subcommand> <args...>\n"
        "  join <base> <rel>     拼接路径（平台分隔符）\n"
        "  normalize <path>      规范化路径（合并重复分隔符、去结尾分隔符）\n"
        "  ext <path>            提取扩展名\n"
        "  info <path>           文件大小与修改时间\n"
        "  ls <dir>              列出目录条目（排序）\n");
    return 1;
}

int main(int argc, char** argv) {
    if (argc < 2) return usage();
    const std::string cmd = argv[1];

    if (cmd == "join" && argc == 4) {
        std::printf("%s\n", ftool::join(argv[2], argv[3]).c_str());
        return 0;
    }
    if (cmd == "normalize" && argc == 3) {
        std::printf("%s\n", ftool::normalize(argv[2]).c_str());
        return 0;
    }
    if (cmd == "ext" && argc == 3) {
        const std::string e = ftool::extension(argv[2]);
        std::printf("%s\n", e.empty() ? "(none)" : e.c_str());
        return 0;
    }
    if (cmd == "info" && argc == 3) {
        const auto info = ftool::file_info(argv[2]);
        if (!info) {
            std::fprintf(stderr, "error: cannot stat '%s'\n", argv[2]);
            return 1;
        }
        std::printf("size=%llu bytes  modified=%s  %s\n",
                    static_cast<unsigned long long>(info->size),
                    info->modified.c_str(),
                    info->is_dir ? "dir" : "file");
        return 0;
    }
    if (cmd == "ls" && argc == 3) {
        const auto entries = ftool::list_dir(argv[2]);
        if (entries.empty()) {
            std::fprintf(stderr, "error: cannot list '%s'\n", argv[2]);
            return 1;
        }
        for (const auto& e : entries) {
            std::printf("%s\n", e.c_str());
        }
        return 0;
    }
    return usage();
}
