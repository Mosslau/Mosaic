// 来源：languages/cpp/ph07-exception-safety/project/config.cpp
// 说明：INI/键值配置模块实现——文件加载、key=value 解析、类型转换
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -c config.cpp
// 验证状态：已验证
#include "config.h"

#include <fstream>

namespace ph07 {

Config Config::load(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw ConfigError("cannot open config: " + path);

    Config cfg;
    std::string line;
    int lineno = 0;
    while (std::getline(in, line)) {
        ++lineno;
        const auto hash = line.find('#');
        if (hash != std::string::npos) line.erase(hash);
        const auto first = line.find_first_not_of(" \t");
        if (first == std::string::npos) continue;
        const auto eq = line.find('=');
        if (eq == std::string::npos)
            throw ConfigError("line " + std::to_string(lineno) + ": missing '='");
        const std::string key = trim(line.substr(0, eq));
        const std::string val = trim(line.substr(eq + 1));
        if (key.empty())
            throw ConfigError("line " + std::to_string(lineno) + ": empty key");
        cfg.kv_[key] = val;
    }
    return cfg;
}

std::string Config::get_string(const std::string& key) const {
    const auto it = kv_.find(key);
    if (it == kv_.end()) throw ConfigError("missing key: " + key);
    return it->second;
}

int Config::get_int(const std::string& key, int fallback) const {
    const auto it = kv_.find(key);
    if (it == kv_.end()) return fallback;
    size_t pos = 0;
    const int v = std::stoi(it->second, &pos);
    if (pos != it->second.size())
        throw ConfigError("key '" + key + "' is not an int: " + it->second);
    return v;
}

double Config::get_double(const std::string& key, double fallback) const {
    const auto it = kv_.find(key);
    if (it == kv_.end()) return fallback;
    size_t pos = 0;
    const double v = std::stod(it->second, &pos);
    if (pos != it->second.size())
        throw ConfigError("key '" + key + "' is not a double: " + it->second);
    return v;
}

std::string Config::trim(const std::string& s) {
    const auto b = s.find_first_not_of(" \t");
    if (b == std::string::npos) return "";
    const auto e = s.find_last_not_of(" \t");
    return s.substr(b, e - b + 1);
}

}  // namespace ph07
