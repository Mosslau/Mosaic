// main.cpp —— 值语义配置对象 CLI（ph12 project）
// 子命令：
//   load  <file>            解析并逐行打印配置
//   get   <file> <key>      打印键对应的值（缺失打印 (missing)，退出码 1）
//   clone <file>            拷贝一份并在副本上 with()，打印原件与副本证明值语义
//   merge <fileA> <fileB>   合并两个配置并打印结果
// 错误统一走 stderr 且退出码非零；文件读取失败、缺 '=' 的行都会报错。
// 编译：  c++ -std=c++20 -Wall -Wextra main.cpp config.cpp -o build/cfgcli
// 验证状态：已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8 均零警告，
//           全部子命令实测输出见 project/README.md）
#include "config.h"

#include <cstdio>
#include <fstream>
#include <iterator>
#include <sstream>
#include <string>
#include <string_view>

namespace {

// 读取整个文件；失败返回 false 并写 stderr
bool read_file(const std::string& path, std::string& out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "error: cannot open '%s'\n", path.c_str());
        return false;
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    if (in.bad()) {
        std::fprintf(stderr, "error: failed to read '%s'\n", path.c_str());
        return false;
    }
    out = ss.str();
    return true;
}

void print_config(const cfg::Config& c) {
    for (const auto& e : c.entries()) {
        std::printf("%s=%s\n", e.key.c_str(), e.value.c_str());
    }
}

int cmd_load(const std::string& path) {
    std::string text;
    if (!read_file(path, text)) return 1;
    const cfg::Config c = cfg::parse(text);      // 按值返回：保证省略
    print_config(c);
    return 0;
}

int cmd_get(const std::string& path, const std::string& key) {
    std::string text;
    if (!read_file(path, text)) return 1;
    const cfg::Config c = cfg::parse(text);
    const std::string_view v = c.find(key);      // 借用：c 存活期间有效
    if (v.empty()) {
        std::fprintf(stderr, "error: key '%s' not found\n", key.c_str());
        return 1;
    }
    std::printf("%.*s\n", static_cast<int>(v.size()), v.data());
    return 0;
}

int cmd_clone(const std::string& path) {
    std::string text;
    if (!read_file(path, text)) return 1;
    const cfg::Config original = cfg::parse(text);
    const cfg::Config copy = original.with("app.mode", "debug");   // 值语义分叉
    std::printf("-- original (unchanged) --\n");
    print_config(original);
    std::printf("-- copy (with app.mode=debug) --\n");
    print_config(copy);
    return 0;
}

int cmd_merge(const std::string& path_a, const std::string& path_b) {
    std::string text_a;
    std::string text_b;
    if (!read_file(path_a, text_a)) return 1;
    if (!read_file(path_b, text_b)) return 1;
    const cfg::Config a = cfg::parse(text_a);
    const cfg::Config b = cfg::parse(text_b);
    const cfg::Config merged = a.merged_with(b);   // 值语义合并，a/b 不变
    print_config(merged);
    return 0;
}

void usage() {
    std::fprintf(stderr,
                 "usage:\n"
                 "  cfgcli load  <file>\n"
                 "  cfgcli get   <file> <key>\n"
                 "  cfgcli clone <file>\n"
                 "  cfgcli merge <fileA> <fileB>\n");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        usage();
        return 2;
    }
    const std::string_view cmd = argv[1];
    if (cmd == "load" && argc == 3) {
        return cmd_load(argv[2]);
    }
    if (cmd == "get" && argc == 4) {
        return cmd_get(argv[2], argv[3]);
    }
    if (cmd == "clone" && argc == 3) {
        return cmd_clone(argv[2]);
    }
    if (cmd == "merge" && argc == 4) {
        return cmd_merge(argv[2], argv[3]);
    }
    usage();
    return 2;
}
