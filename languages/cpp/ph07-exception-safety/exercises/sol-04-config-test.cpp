// 来源：languages/cpp/ph07-exception-safety/exercises/README.md 练习 4
// 说明：给练习 2 的 Config 模块补单元测试——assert + 手写 main，正常/异常路径全覆盖
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 exercises/sol-04-config-test.cpp -o sol04
// 运行：./sol04
// 验证状态：已验证
#include <cassert>
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

    std::string get_string(const std::string& key) const {
        const auto it = kv_.find(key);
        if (it == kv_.end()) throw ConfigError("missing key: " + key);
        return it->second;
    }
    int get_int(const std::string& key, int fallback) const {
        const auto it = kv_.find(key);
        if (it == kv_.end()) return fallback;
        size_t pos = 0;
        const int v = std::stoi(it->second, &pos);
        if (pos != it->second.size())
            throw ConfigError("key '" + key + "' is not an int: " + it->second);
        return v;
    }
    double get_double(const std::string& key, double fallback) const {
        const auto it = kv_.find(key);
        if (it == kv_.end()) return fallback;
        size_t pos = 0;
        const double v = std::stod(it->second, &pos);
        if (pos != it->second.size())
            throw ConfigError("key '" + key + "' is not a double: " + it->second);
        return v;
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

namespace {

void write_file(const char* path, const std::string& content) {
    std::ofstream out(path);
    out << content;
}

void test_normal_path() {
    const char* path = "/tmp/ph07_test_ok.conf";
    write_file(path, "# c\nhost=127.0.0.1\nport=8080\nratio=0.75\n");
    const ph07::Config cfg = ph07::Config::load(path);
    assert(cfg.get_string("host") == "127.0.0.1");
    assert(cfg.get_int("port", -1) == 8080);
    assert(cfg.get_double("ratio", 0.0) == 0.75);
    assert(cfg.get_int("missing", 42) == 42);   // 默认值
    std::cout << "test_normal_path ok\n";
}

void test_file_not_found() {
    bool caught = false;
    try {
        ph07::Config::load("/tmp/no_such_ph07_test.conf");
    } catch (const ph07::ConfigError&) {
        caught = true;
    }
    assert(caught);
    std::cout << "test_file_not_found ok\n";
}

void test_bad_format() {
    const char* path = "/tmp/ph07_test_bad.conf";
    write_file(path, "host=127.0.0.1\nno_equal_sign_here\n");
    bool caught = false;
    try {
        ph07::Config::load(path);
    } catch (const ph07::ConfigError&) {
        caught = true;
    }
    assert(caught);
    std::cout << "test_bad_format ok\n";
}

void test_bad_type() {
    const char* path = "/tmp/ph07_test_type.conf";
    write_file(path, "port=not_a_number\n");
    const ph07::Config cfg = ph07::Config::load(path);
    bool caught = false;
    try {
        cfg.get_int("port", -1);
    } catch (const ph07::ConfigError&) {
        caught = true;
    } catch (const std::invalid_argument&) {
        caught = true;   // std::stoi 未消费时也可能抛
    }
    assert(caught);
    std::cout << "test_bad_type ok\n";
}

}  // namespace

int main() {
    test_normal_path();
    test_file_not_found();
    test_bad_format();
    test_bad_type();
    std::cout << "all tests passed\n";
    return 0;
}
