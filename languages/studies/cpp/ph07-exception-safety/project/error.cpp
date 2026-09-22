// 来源：languages/cpp/ph07-exception-safety/project/error.cpp
// 说明：错误码体系实现
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -c error.cpp
// 验证状态：已验证
#include "error.h"

namespace ph07 {

const char* err_code_to_string(ErrCode c) noexcept {
    switch (c) {
        case ErrCode::Ok:           return "ok";
        case ErrCode::NotFound:     return "not found";
        case ErrCode::InvalidParam: return "invalid param";
        case ErrCode::IoError:      return "io error";
        case ErrCode::ParseError:   return "parse error";
    }
    return "unknown";
}

AppError::AppError(const std::string& msg, ErrCode code)
    : std::runtime_error(msg), code_(code) {}

void throw_if_error(ErrCode code, const std::string& context) {
    if (code != ErrCode::Ok)
        throw AppError(context + ": " + err_code_to_string(code), code);
}

}  // namespace ph07
