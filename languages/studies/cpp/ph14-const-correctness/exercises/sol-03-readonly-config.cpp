// sol-03-readonly-config.cpp —— 练习 3 参考实现：设计只读配置接口
// 练习 3 要求：设计一个 Config 类，对外只暴露 const 操作（get/contains/size/keys），
//              get 返回 std::string_view（观察不拥有）；内部查找统计用 mutable 计数；
//              用 const 对象 + const& 参数的只读辅助函数实测整条只读链路。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] 构造：解析 key=value 文本，跳过注释与空行
//     entries.size = 3
//   [2] const 对象 + const& 参数的只读接口（dump 全程 const）
//     get("host")    -> "127.0.0.1"
//     get("port")    -> "5432"
//     get("missing") -> nullopt（optional 表示不存在）
//     contains("host") = true
//     keys: host, port, debug
//   [3] 只读接口的统计是 mutable 物理状态（不算逻辑修改）
//     lookup_count = 4（const 成员函数里累加）
//   [4] 接口不可变：Config 没有 public 修改方法——「改配置」只能构造新对象
//     copy.get("host") = "127.0.0.1"
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-03-readonly-config.cpp -o /tmp/ph14-sol-03
// 运行：    /tmp/ph14-sol-03
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// 只读配置：全部 public 接口 const；无任何修改方法（接口即"只读"承诺）
class Config {
public:
    explicit Config(std::string text) : text_(std::move(text)) {
        parse();
    }

    // 查询：返回视图（观察 text_，不拷贝）；不存在返回 nullopt
    std::optional<std::string_view> get(std::string_view key) const {
        lookups_ += 1;                      // mutable 计数：物理状态，不影响逻辑 const
        for (const auto& [k, v] : entries_) {
            if (k == key) {
                return v;
            }
        }
        return std::nullopt;
    }

    bool contains(std::string_view key) const {
        lookups_ += 1;
        for (const auto& [k, v] : entries_) {
            (void)v;
            if (k == key) {
                return true;
            }
        }
        return false;
    }

    std::size_t size() const { return entries_.size(); }

    // 只读枚举：返回 key 列表（拷贝视图，演示用；大配置可改 span 视图）
    std::vector<std::string_view> keys() const {
        std::vector<std::string_view> ks;
        ks.reserve(entries_.size());
        for (const auto& [k, v] : entries_) {
            (void)v;
            ks.push_back(k);
        }
        return ks;
    }

    std::size_t lookup_count() const { return lookups_; }

private:
    void parse() {
        std::size_t pos = 0;
        while (pos < text_.size()) {
            std::size_t eol = text_.find('\n', pos);
            if (eol == std::string::npos) {
                eol = text_.size();
            }
            std::string_view line(text_.data() + pos, eol - pos);
            pos = eol + 1;
            // 去首尾空白（简化：只处理行首）
            while (!line.empty() && (line.front() == ' ' || line.front() == '\t' ||
                                     line.front() == '\r')) {
                line.remove_prefix(1);
            }
            if (line.empty() || line.front() == '#') {
                continue;                   // 空行 / 注释
            }
            std::size_t eq = line.find('=');
            if (eq == std::string_view::npos) {
                continue;                   // 非法行跳过（教学简化）
            }
            std::string_view k = line.substr(0, eq);
            std::string_view v = line.substr(eq + 1);
            while (!k.empty() && k.back() == ' ') {
                k.remove_suffix(1);
            }
            while (!v.empty() && v.front() == ' ') {
                v.remove_prefix(1);
            }
            entries_.emplace_back(k, v);
        }
    }

    std::string text_;                                    // 拥有数据（逻辑状态）
    std::vector<std::pair<std::string_view, std::string_view>> entries_;  // 视图指向 text_
    mutable std::size_t lookups_{0};                      // 物理状态：查询统计
};

// 只读辅助函数：const& 参数，只能调 const 接口（本函数无法修改 cfg）
void dump(const Config& cfg) {
    std::printf("  get(\"host\")    -> \"%s\"\n",
                std::string(cfg.get("host").value_or("<none>")).c_str());
    std::printf("  get(\"port\")    -> \"%s\"\n",
                std::string(cfg.get("port").value_or("<none>")).c_str());
    const auto missing = cfg.get("missing");
    std::printf("  get(\"missing\") -> %s\n",
                missing ? std::string(*missing).c_str() : "nullopt（optional 表示不存在）");
    std::printf("  contains(\"host\") = %s\n", cfg.contains("host") ? "true" : "false");
    bool first = true;
    std::printf("  keys: ");
    for (std::string_view k : cfg.keys()) {
        if (!first) {
            std::printf(", ");
        }
        first = false;
        std::printf("%s", std::string(k).c_str());
    }
    std::printf("\n");
}

int main() {
    const std::string text =
        "# 配置示例\n"
        "host = 127.0.0.1\n"
        "port = 5432\n"
        "\n"
        "debug = true\n";

    std::printf("[1] 构造：解析 key=value 文本，跳过注释与空行\n");
    const Config cfg(text);                 // const 对象：整条链路只读
    std::printf("  entries.size = %zu\n", cfg.size());

    std::printf("[2] const 对象 + const& 参数的只读接口（dump 全程 const）\n");
    dump(cfg);

    std::printf("[3] 只读接口的统计是 mutable 物理状态（不算逻辑修改）\n");
    std::printf("  lookup_count = %zu（const 成员函数里累加）\n", cfg.lookup_count());

    std::printf("[4] 接口不可变：Config 没有 public 修改方法——「改配置」只能构造新对象\n");
    const Config copy = cfg;                // 拷贝即只读快照（值语义 + const 接口）
    std::printf("  copy.get(\"host\") = \"%s\"\n",
                std::string(copy.get("host").value_or("<none>")).c_str());
    return 0;
}
