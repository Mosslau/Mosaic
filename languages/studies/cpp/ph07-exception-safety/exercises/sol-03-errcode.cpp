// 来源：languages/cpp/ph07-exception-safety/exercises/README.md 练习 3
// 说明：错误码体系——enum class + 消息表 + AppError + 边界转换
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 exercises/sol-03-errcode.cpp -o sol03
// 运行：./sol03
// 验证状态：已验证
#include <iostream>
#include <stdexcept>
#include <string>

namespace ph07 {

enum class ErrCode : int {
    Ok = 0,
    NotFound = 1,
    InvalidParam = 2,
    IoError = 3,
};

const char* err_code_to_string(ErrCode c) {
    switch (c) {
        case ErrCode::Ok:           return "ok";
        case ErrCode::NotFound:     return "not found";
        case ErrCode::InvalidParam: return "invalid param";
        case ErrCode::IoError:      return "io error";
    }
    return "unknown";
}

class AppError : public std::runtime_error {
public:
    AppError(const std::string& msg, ErrCode code)
        : std::runtime_error(msg), code_(code) {}
    ErrCode code() const { return code_; }
private:
    ErrCode code_;
};

void throw_if_error(ErrCode code, const std::string& context) {
    if (code != ErrCode::Ok)
        throw AppError(context + ": " + err_code_to_string(code), code);
}

// 底层：返回错误码，不抛异常
ErrCode low_level_read(const std::string& path) {
    if (path.empty()) return ErrCode::InvalidParam;
    if (path != "/tmp/ok") return ErrCode::NotFound;
    return ErrCode::Ok;
}

}  // namespace ph07

int main() {
    try {
        ph07::throw_if_error(ph07::low_level_read("/tmp/missing"), "read config");
    } catch (const ph07::AppError& e) {
        std::cerr << "caught code=" << static_cast<int>(e.code())
                  << " msg=" << e.what() << "\n";
    }
    ph07::throw_if_error(ph07::low_level_read("/tmp/ok"), "read config");
    std::cout << "ok path passed\n";
    return 0;
}
