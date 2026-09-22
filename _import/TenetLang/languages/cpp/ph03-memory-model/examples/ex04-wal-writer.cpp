// examples/ex04-wal-writer.cpp —— RAII 文件句柄（WAL 日志管理）
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex04-wal-writer.cpp -o ex04
// 运行：./ex04
// 已验证：本环境编译零警告，写入 /tmp/ph03_wal_test.log 并回读打印
#include <cstdio>
#include <iostream>
#include <string>
#include <utility>

class WalWriter {
public:
    explicit WalWriter(const std::string& path) {
        file_ = std::fopen(path.c_str(), "ab");
        // 为聚焦 RAII，打开失败用 operator bool 检查而非抛异常——异常属于 ph07 阶段
        if (!file_) std::fprintf(stderr, "error: cannot open %s\n", path.c_str());
    }
    ~WalWriter() {
        if (file_) { std::fflush(file_); std::fclose(file_); }   // 析构自动关闭
    }
    // 文件句柄独占：禁止拷贝，允许移动（Rule of 5）
    WalWriter(const WalWriter&) = delete;
    WalWriter& operator=(const WalWriter&) = delete;
    WalWriter(WalWriter&& o) noexcept : file_(o.file_) { o.file_ = nullptr; }
    WalWriter& operator=(WalWriter&& o) noexcept {
        if (this != &o) {
            if (file_) { std::fflush(file_); std::fclose(file_); }
            file_ = o.file_;
            o.file_ = nullptr;
        }
        return *this;
    }

    bool append(const std::string& key, const std::string& value) {
        if (!file_) return false;
        return std::fprintf(file_, "%s\t%s\n", key.c_str(), value.c_str()) >= 0;
    }
    bool flush() { return file_ && std::fflush(file_) == 0; }
    explicit operator bool() const { return file_ != nullptr; }

private:
    std::FILE* file_ = nullptr;
};

int main() {
    const char* path = "/tmp/ph03_wal_test.log";
    {
        WalWriter wal(path);
        if (!wal) { std::cerr << "failed to open WAL\n"; return 1; }
        wal.append("key1", "value1");
        wal.append("key2", "value2");
        wal.flush();
        std::cout << "WAL records written\n";
    }  // wal 析构自动 fclose

    std::cout << "--- WAL file content ---\n";
    std::FILE* f = std::fopen(path, "r");
    if (f) {
        char buf[256];
        while (std::fgets(buf, sizeof(buf), f)) std::cout << buf;
        std::fclose(f);
    }
    return 0;
}
