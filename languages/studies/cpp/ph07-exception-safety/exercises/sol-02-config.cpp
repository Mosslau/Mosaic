// 来源：languages/cpp/ph07-exception-safety/exercises/README.md 练习 2
// 说明：配置读取模块——key=value 解析 + 类型转换 + 默认值 + 明确异常
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 exercises/sol-02-config.cpp -o sol02
// 运行：./sol02
// 验证状态：已验证
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace ph07 {

class ConfigError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class Config {
public:
    static Config load(const std::string& path) {
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
            if (first == std::string::npos) continue;          // 空行
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

    std::string get_string(const std::string& key) const {
        const auto it = kv_.find(key);
        if (it == kv_.end()) throw ConfigError("missing key: " + key);
        return it->second;
    }
    int get_int(const std::string& key, int fallback) const {
        const auto it = kv_.find(key);
        if (it == kv_.end()) return fallback;
        try {
            size_t pos = 0;
            const int v = std::stoi(it->second, &pos);
            if (pos != it->second.size()) throw ConfigError("bad int");
            return v;
        } catch (const std::exception&) {
            throw ConfigError("key '" + key + "' is not an int: " + it->second);
        }
    }
    double get_double(const std::string& key, double fallback) const {
        const auto it = kv_.find(key);
        if (it == kv_.end()) return fallback;
        try {
            size_t pos = 0;
            const double v = std::stod(it->second, &pos);
            if (pos != it->second.size()) throw ConfigError("bad double");
            return v;
        } catch (const std::exception&) {
            throw ConfigError("key '" + key + "' is not a double: " + it->second);
        }
    }

private:
    static std::string trim(const std::string& s) {
        const auto b = s.find_first_not_of(" \t");
        if (b == std::string::npos) return "";
        const auto e = s.find_last_not_of(" \t");
        return s.substr(b, e - b + 1);
    }
    std::unordered_map<std::string, std::string> kv_;
};

}  // namespace ph07

int main() {
    const char* path = "/tmp/ph07_sol02.conf";
    {
        std::ofstream out(path);
        out << "# comment\n"
            << "host = 127.0.0.1\n"
            << "port = 8080\n"
            << "ratio = 0.75\n"
            << "\n";
    }
    const ph07::Config cfg = ph07::Config::load(path);
    std::cout << "host=" << cfg.get_string("host") << "\n";
    std::cout << "port=" << cfg.get_int("port", -1) << "\n";
    std::cout << "ratio=" << cfg.get_double("ratio", 0.0) << "\n";
    std::cout << "missing=" << cfg.get_int("missing", 42) << "\n";

    try {
        ph07::Config::load("/tmp/no_such_ph07.conf");
    } catch (const ph07::ConfigError& e) {
        std::cerr << "caught: " << e.what() << "\n";
    }
    return 0;
}
