// 来源：languages/cpp/ph07-exception-safety/07-exception-safety.md 第 6 章示例 1
// 说明：异常安全资源封装——RAII 文件句柄，异常路径自动释放
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 examples/ex01-raii-file.cpp -o ex01
// 运行：./ex01
// 验证状态：已验证
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>

class FileHandle {
public:
    explicit FileHandle(const std::string& path, const char* mode = "rb") {
        file_ = std::fopen(path.c_str(), mode);
        if (!file_) throw std::runtime_error("cannot open file: " + path);
        std::cout << "[open] " << path << "\n";
    }
    ~FileHandle() {
        if (file_) { std::fclose(file_); std::cout << "[close]\n"; }
    }
    FileHandle(const FileHandle&) = delete;              // 禁拷贝、允移动
    FileHandle& operator=(const FileHandle&) = delete;
    FileHandle(FileHandle&& other) noexcept : file_(other.file_) { other.file_ = nullptr; }
    FileHandle& operator=(FileHandle&& other) noexcept {
        if (this != &other) {
            if (file_) std::fclose(file_);
            file_ = other.file_;
            other.file_ = nullptr;
        }
        return *this;
    }
    size_t read(void* buf, size_t len) {
        if (!file_) throw std::logic_error("read on moved-from handle");
        return std::fread(buf, 1, len, file_);
    }
private:
    std::FILE* file_ = nullptr;
};

void process(const std::string& path) {
    FileHandle f(path);                  // 打开失败 → 异常，f 根本不存在
    char buf[64];
    size_t n = f.read(buf, sizeof(buf)); // 这里即使抛异常…
    std::cout << "read " << n << " bytes\n";
    // …f 的析构依然执行，句柄自动关闭（栈展开保证）
}

int main() {
    try {
        process("/tmp/no_such_file_ph07.txt");   // 异常路径
    } catch (const std::exception& e) {
        std::cerr << "caught: " << e.what() << "\n";
    }
    process("/etc/hosts");                        // 正常路径
    return 0;
}
