// 来源：project/ —— 配置管理模块实现
// 一句话说明：load 用 unique_ptr<char[]> 管理读入缓冲（RAII 替代裸 new[]/delete[]），
//             string_view 零拷贝视图逐行解析；值类型用 variant 按内容自动推断。
// 验证环境：Apple clang 17（g++ 兼容），C++23（涉及 <format>）
// 编译：g++ -Wall -Wextra -std=c++23 config.cpp main.cpp -o config_app
// 验证状态：已验证
#include "config.h"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <format>
#include <stdexcept>

namespace tenet {

namespace {

// 去首尾空白（空格 / 制表 / 换行 / 回车）
std::string_view trim(std::string_view s) {
    while (!s.empty() && (s.front() == ' ' || s.front() == '\t' ||
                          s.front() == '\n' || s.front() == '\r'))
        s.remove_prefix(1);
    while (!s.empty() && (s.back() == ' ' || s.back() == '\t' ||
                          s.back() == '\n' || s.back() == '\r'))
        s.remove_suffix(1);
    return s;
}

// 按内容推断配置值类型：bool → int64 → double → string
Value parse_value(std::string_view sv) {
    if (sv == "true") return true;
    if (sv == "false") return false;

    const std::string s(sv);
    errno = 0;
    char* end = nullptr;
    const long long ll = std::strtoll(s.c_str(), &end, 10);
    if (end != s.c_str() && *end == '\0' && errno == 0)
        return static_cast<std::int64_t>(ll);

    errno = 0;
    const double d = std::strtod(s.c_str(), &end);
    if (end != s.c_str() && *end == '\0' && errno == 0)
        return d;

    return std::string(sv);
}

}  // namespace

std::size_t Config::load(std::string_view path) {
    const std::string path_str(path);
    FILE* fp = std::fopen(path_str.c_str(), "rb");
    if (fp == nullptr)
        throw std::runtime_error("无法打开配置文件: " + path_str);

    // 拿文件大小
    std::fseek(fp, 0, SEEK_END);
    const long file_size = std::ftell(fp);
    std::rewind(fp);

    // unique_ptr<char[]> 管理读入缓冲：作用域结束自动释放，无需手写 delete[]
    auto buf = std::make_unique<char[]>(static_cast<std::size_t>(file_size) + 1);
    const auto read_n = std::fread(buf.get(), 1, static_cast<std::size_t>(file_size), fp);
    std::fclose(fp);
    buf[read_n] = '\0';

    // string_view 视图不拷贝数据；读入量以 read_n 为准（防止空文件 ftell 异常）
    const std::string_view text(buf.get(), read_n);
    return parse_lines(text);
}

std::size_t Config::parse_lines(std::string_view text) {
    std::size_t loaded = 0;
    std::size_t pos = 0;
    while (pos < text.size()) {
        // 取一行
        const std::size_t nl = text.find('\n', pos);
        const std::size_t end = (nl == std::string_view::npos) ? text.size() : nl;
        std::string_view line = trim(text.substr(pos, end - pos));
        pos = (nl == std::string_view::npos) ? text.size() : nl + 1;

        if (line.empty() || line.front() == '#') continue;   // 空行 / 注释

        const std::size_t eq = line.find('=');
        if (eq == std::string_view::npos) continue;          // 坏行：缺 '='，跳过

        const std::string_view key = trim(line.substr(0, eq));
        const std::string_view val = trim(line.substr(eq + 1));
        if (key.empty() || val.empty()) continue;            // key 或 value 为空，跳过

        entries_.emplace(std::string(key), parse_value(val));
        ++loaded;
    }
    return loaded;
}

std::optional<Value> Config::get(std::string_view key) const {
    const auto it = entries_.find(std::string(key));
    if (it == entries_.end()) return std::nullopt;   // 缺失：显式"无值"
    return it->second;
}

std::optional<bool> Config::get_bool(std::string_view key) const {
    const auto v = get(key);
    if (!v) return std::nullopt;
    if (const auto* p = std::get_if<bool>(&*v)) return *p;
    return std::nullopt;
}

std::optional<std::int64_t> Config::get_int(std::string_view key) const {
    const auto v = get(key);
    if (!v) return std::nullopt;
    if (const auto* p = std::get_if<std::int64_t>(&*v)) return *p;
    return std::nullopt;
}

std::optional<double> Config::get_double(std::string_view key) const {
    const auto v = get(key);
    if (!v) return std::nullopt;
    if (const auto* p = std::get_if<double>(&*v)) return *p;
    return std::nullopt;
}

std::optional<std::string> Config::get_string(std::string_view key) const {
    const auto v = get(key);
    if (!v) return std::nullopt;
    if (const auto* p = std::get_if<std::string>(&*v)) return *p;
    return std::nullopt;
}

std::string Config::dump() const {
    std::string out;
    for (const auto& [key, value] : entries_) {
        // std::visit 取出 variant 当前分支；std::format 类型安全格式化
        std::visit([&](const auto& v) { out += std::format("{} = {}\n", key, v); },
                   value);
    }
    return out;
}

}  // namespace tenet
