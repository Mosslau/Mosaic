// ex04-config.cpp —— key=value 配置文件解析：可诊断错误（文件:行号）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex04-config.cpp -o ex04
// 运行：./ex04 [配置文件路径]（默认生成 /tmp/ph09_demo.conf 并解析）
//       ./ex04 /tmp/ph09_bad.conf —— 传入含非法行的文件可观察带行号的报错
// 验证状态：已验证（编译零警告 + 运行通过）
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>

// 配置错误：消息自带 文件:行号
class ConfigError : public std::runtime_error {
public:
    ConfigError(const std::string& file, int line, const std::string& msg)
        : std::runtime_error(file + ":" + std::to_string(line) + ": " + msg) {}
};

class Config {                        // key=value 配置：错误带文件与行号
public:
    static Config load(const std::string& path) {
        std::ifstream in(path);
        if (!in) throw ConfigError(path, 0, "cannot open file");
        Config cfg;
        cfg.file_ = path;
        std::string raw;
        int line_no = 0;
        while (std::getline(in, raw)) {
            ++line_no;
            const std::string line = trim(raw);
            if (line.empty() || line[0] == '#') continue;      // 空行与注释
            const size_t eq = line.find('=');
            if (eq == std::string::npos)
                throw ConfigError(path, line_no,
                                  "expected key=value, got: " + line);
            const std::string key = trim(line.substr(0, eq));
            const std::string val = trim(line.substr(eq + 1));
            cfg.values_[key] = val;
            cfg.lines_[key] = line_no;          // 记录键定义行号（类型错误报错用）
        }
        return cfg;
    }
    int get_int(const std::string& key, int def) const {
        const auto it = values_.find(key);
        if (it == values_.end()) return def;
        try {
            return std::stoi(it->second);
        } catch (const std::exception&) {
            const auto ln = lines_.find(key);
            throw ConfigError(file_, ln == lines_.end() ? 0 : ln->second,
                              "key '" + key + "' value '" + it->second +
                                  "' is not an int");   // 类型错误同样带 文件:行号
        }
    }
    std::string get_str(const std::string& key, std::string def) const {
        const auto it = values_.find(key);
        return it == values_.end() ? std::move(def) : it->second;
    }
private:
    static std::string trim(const std::string& s) {
        const size_t b = s.find_first_not_of(" \t\r\n");
        if (b == std::string::npos) return "";
        const size_t e = s.find_last_not_of(" \t\r\n");
        return s.substr(b, e - b + 1);
    }
    std::string file_;                          // 配置文件路径（错误消息用）
    std::map<std::string, int> lines_;          // 键 → 定义行号
    std::map<std::string, std::string> values_;
};

int main(int argc, char** argv) {
    std::string path = argc > 1 ? argv[1] : "/tmp/ph09_demo.conf";
    if (argc == 1) {                 // 无参数时生成一份示例配置再解析
        std::ofstream out(path);
        out << "# demo config\n"
            << "server.port = 8080\n"
            << "workers = 4\n";
    }
    try {
        const Config cfg = Config::load(path);
        std::cout << "port=" << cfg.get_int("server.port", 0)
                  << " workers=" << cfg.get_int("workers", 1) << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "config error: " << e.what() << '\n';   // 如 xxx.conf:3: expected key=value
        return 1;
    }
}
