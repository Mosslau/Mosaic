// 来源：languages/cpp/ph07-exception-safety/project/config.h
// 说明：INI/键值配置模块头文件——加载、类型转换、默认值
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -c config.cpp
// 验证状态：已验证
#pragma once

#include "error.h"

#include <string>
#include <unordered_map>

namespace ph07 {

class ConfigError : public AppError {
public:
    explicit ConfigError(const std::string& msg)
        : AppError(msg, ErrCode::ParseError) {}
};

class Config {
public:
    static Config load(const std::string& path);

    std::string get_string(const std::string& key) const;
    int get_int(const std::string& key, int fallback) const;
    double get_double(const std::string& key, double fallback) const;

private:
    static std::string trim(const std::string& s);
    std::unordered_map<std::string, std::string> kv_;
};

}  // namespace ph07
