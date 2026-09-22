// project/wal_file.cpp —— RAII 文件类（实现）
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 main.cpp wal_file.cpp -o wal_file
// 已验证：本环境编译零警告
#include "wal_file.h"

#include <cstdio>

WalFile::WalFile(const std::string& path) {
    file_ = std::fopen(path.c_str(), "ab");        // 追加模式打开
}

WalFile::~WalFile() {
    if (file_) { std::fflush(file_); std::fclose(file_); }   // 析构自动关闭
}

WalFile::WalFile(WalFile&& other) noexcept : file_(other.file_) {
    other.file_ = nullptr;                         // 移动后清空源对象
}

WalFile& WalFile::operator=(WalFile&& other) noexcept {
    if (this != &other) {
        if (file_) { std::fflush(file_); std::fclose(file_); }
        file_ = other.file_;
        other.file_ = nullptr;
    }
    return *this;
}

bool WalFile::append(const std::string& key, const std::string& value) {
    if (!file_) return false;
    return std::fprintf(file_, "%s\t%s\n", key.c_str(), value.c_str()) >= 0;
}

bool WalFile::flush() {
    return file_ && std::fflush(file_) == 0;
}

WalFile::operator bool() const {
    return file_ != nullptr;
}
