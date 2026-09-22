// exercises/sol-04-raii-file.cpp —— 用 RAII 管理文件句柄参考实现
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-04-raii-file.cpp -o sol04
// 运行：./sol04
// 已验证：本环境编译零警告，全部断言通过
#include <cassert>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>
#include <utility>

class WalFile {
public:
    explicit WalFile(const std::string& path) {
        file_ = std::fopen(path.c_str(), "ab");    // 追加模式打开
    }
    ~WalFile() {
        if (file_) { std::fflush(file_); std::fclose(file_); }   // 析构自动关闭
    }
    // 文件句柄独占：禁止拷贝，允许移动
    WalFile(const WalFile&) = delete;
    WalFile& operator=(const WalFile&) = delete;
    WalFile(WalFile&& o) noexcept : file_(o.file_) { o.file_ = nullptr; }
    WalFile& operator=(WalFile&& o) noexcept {
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
    const char* path = "/tmp/ph03_sol04_test.log";
    std::remove(path);                             // 清理旧文件

    {
        WalFile wal(path);
        assert(wal);                               // 打开成功
        assert(wal.append("k1", "v1"));
        assert(wal.append("k2", "v2"));
        assert(wal.flush());

        WalFile moved = std::move(wal);            // 移动构造
        assert(!wal);                              // 源对象失效
        assert(moved);                             // 目标持有句柄
        assert(moved.append("k3", "v3"));
    }  // 离开作用域自动 flush + fclose

    // 回读验证：文件内容与写入顺序一致
    std::FILE* f = std::fopen(path, "r");
    assert(f != nullptr);
    char line[256];
    assert(std::fgets(line, sizeof(line), f) != nullptr);
    assert(std::strcmp(line, "k1\tv1\n") == 0);
    assert(std::fgets(line, sizeof(line), f) != nullptr);
    assert(std::strcmp(line, "k2\tv2\n") == 0);
    assert(std::fgets(line, sizeof(line), f) != nullptr);
    assert(std::strcmp(line, "k3\tv3\n") == 0);
    std::fclose(f);
    std::remove(path);

    std::cout << "sol-04 全部断言通过\n";
    return 0;
}
