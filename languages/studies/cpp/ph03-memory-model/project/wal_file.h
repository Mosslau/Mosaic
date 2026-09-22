// project/wal_file.h —— RAII 文件类（头文件）
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 main.cpp wal_file.cpp -o wal_file
// 已验证：本环境编译零警告
#ifndef WAL_FILE_H
#define WAL_FILE_H

#include <cstdio>
#include <string>

// RAII 文件类：封装 std::FILE*，追加写入、flush、自动关闭，禁拷贝允移动
class WalFile {
public:
    explicit WalFile(const std::string& path);
    ~WalFile();

    WalFile(const WalFile&) = delete;
    WalFile& operator=(const WalFile&) = delete;
    WalFile(WalFile&& other) noexcept;
    WalFile& operator=(WalFile&& other) noexcept;

    bool append(const std::string& key, const std::string& value);
    bool flush();
    explicit operator bool() const;

private:
    std::FILE* file_ = nullptr;
};

#endif  // WAL_FILE_H
