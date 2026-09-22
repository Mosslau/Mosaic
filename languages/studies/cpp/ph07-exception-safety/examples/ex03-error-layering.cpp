// 来源：languages/cpp/ph07-exception-safety/07-exception-safety.md 第 6 章示例 3
// 说明：错误码与异常的策略分层——底层错误码、上层异常、边界转换
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 examples/ex03-error-layering.cpp -o ex03
// 运行：./ex03
// 验证状态：已验证
#include <iostream>
#include <stdexcept>
#include <string>

// 底层：错误码体系 —— 贴近资源/系统层，零异常开销、可跨边界
enum class ErrCode : int {
    Ok = 0, NotFound = 1, InvalidParam = 2, IoError = 3,
};

struct Status {
    ErrCode code = ErrCode::Ok;
    std::string message;
    bool ok() const { return code == ErrCode::Ok; }
};

Status read_config_impl(const std::string& path) {  // 底层：返回错误码，不抛异常
    if (path.empty()) return {ErrCode::InvalidParam, "empty path"};
    if (path != "/tmp/ok.conf") return {ErrCode::NotFound, "no such file: " + path};
    return {ErrCode::Ok, ""};
}

// 上层：异常 —— 面向调用方表达"无法继续"的业务语义
class ConfigError : public std::runtime_error {
public:
    ConfigError(const std::string& msg, ErrCode code)
        : std::runtime_error(msg), code_(code) {}
    ErrCode code() const { return code_; }
private:
    ErrCode code_;
};

std::string load_config(const std::string& path) {   // 边界转换：错误码 → 异常
    Status st = read_config_impl(path);
    if (!st.ok())
        throw ConfigError("load config failed: " + st.message, st.code);
    return "ok";
}

int main() {
    try {
        load_config("/tmp/missing.conf");
    } catch (const ConfigError& e) {
        std::cerr << "ConfigError code=" << static_cast<int>(e.code())
                  << " msg=" << e.what() << "\n";
    }
    std::cout << "loaded: " << load_config("/tmp/ok.conf") << "\n";
    return 0;
}
