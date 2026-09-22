// 来源：languages/cpp/ph07-exception-safety/project/error.h
// 说明：错误码体系头文件——ErrCode 枚举、消息表、AppError 异常、边界转换
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -c error.cpp
// 验证状态：已验证
#pragma once

#include <stdexcept>
#include <string>

namespace ph07 {

enum class ErrCode : int {
    Ok = 0,
    NotFound = 1,
    InvalidParam = 2,
    IoError = 3,
    ParseError = 4,
};

const char* err_code_to_string(ErrCode c) noexcept;

class AppError : public std::runtime_error {
public:
    AppError(const std::string& msg, ErrCode code);
    ErrCode code() const noexcept { return code_; }
private:
    ErrCode code_;
};

void throw_if_error(ErrCode code, const std::string& context);

}  // namespace ph07
