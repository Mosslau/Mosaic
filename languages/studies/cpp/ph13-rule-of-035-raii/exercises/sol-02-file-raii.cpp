// sol-02-file-raii.cpp —— 练习 2 参考实现：把 FILE* 封装成 RAII 类
// 练习 2 要求：move-only、构造失败抛异常、异常路径自动 fclose、写 N 行读回校验。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] 写入 5 行
//     open /tmp/ph13-sol02.txt (w)
//     close（析构）
//   [2] 读回校验
//     open /tmp/ph13-sol02.txt (r)
//     5/5 行内容一致
//     close（析构）
//   [3] 异常路径：打开不存在的目录
//     捕获: fopen 失败: /tmp/no-such-dir-ph13/x.txt
//   [4] 写入中途抛异常：close 照常执行
//     open /tmp/ph13-sol02.txt (w)
//     close（析构）
//     捕获: 模拟第 3 行失败
//   [5] 拷贝被删除（取消注释下行可见编译错误）：
//     // TextFile t2 = t1;  // error: call to deleted constructor
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-02-file-raii.cpp -o /tmp/ph13-sol-02
// 运行：    /tmp/ph13-sol-02
// 验证状态：已验证（两种编译器均零警告，输出一致；异常路径 close 实测先于 catch）
#include <cstdio>
#include <stdexcept>
#include <string>
#include <utility>

class TextFile {
public:
    TextFile(const char* path, const char* mode) : fp_(std::fopen(path, mode)) {
        if (fp_ == nullptr) {
            throw std::runtime_error(std::string("fopen 失败: ") + path);
        }
        std::printf("  open %s (%s)\n", path, mode);
    }
    ~TextFile() {
        if (fp_ != nullptr) {
            std::fclose(fp_);
            std::printf("  close（析构）\n");
        }
    }
    TextFile(const TextFile&) = delete;
    TextFile& operator=(const TextFile&) = delete;
    TextFile(TextFile&& o) noexcept : fp_(std::exchange(o.fp_, nullptr)) {}
    TextFile& operator=(TextFile&& o) noexcept {
        if (this != &o) {
            if (fp_ != nullptr) std::fclose(fp_);
            fp_ = std::exchange(o.fp_, nullptr);
        }
        return *this;
    }

    void put(const std::string& line) {
        if (std::fputs(line.c_str(), fp_) == EOF || std::fputc('\n', fp_) == EOF) {
            throw std::runtime_error("写入失败");
        }
    }
    std::string getline() {
        std::string out;
        int ch;
        while ((ch = std::fgetc(fp_)) != EOF && ch != '\n') {
            out += static_cast<char>(ch);
        }
        return out;
    }
    bool eof() const { return std::feof(fp_) != 0; }

private:
    std::FILE* fp_;
};

const char* kPath = "/tmp/ph13-sol02.txt";

int main() {
    std::printf("[1] 写入 5 行\n");
    {
        TextFile f(kPath, "w");
        for (int i = 1; i <= 5; ++i) f.put("row-" + std::to_string(i));
    }

    std::printf("[2] 读回校验\n");
    {
        TextFile f(kPath, "r");
        int ok = 0;
        for (int i = 1; i <= 5; ++i) {
            if (f.getline() == "row-" + std::to_string(i)) ++ok;
        }
        std::printf("  %d/5 行内容一致\n", ok);
    }

    std::printf("[3] 异常路径：打开不存在的目录\n");
    try {
        TextFile f("/tmp/no-such-dir-ph13/x.txt", "w");
    } catch (const std::runtime_error& e) {
        std::printf("  捕获: %s\n", e.what());
    }

    std::printf("[4] 写入中途抛异常：close 照常执行\n");
    try {
        TextFile f(kPath, "w");
        f.put("row-1");
        throw std::runtime_error("模拟第 3 行失败");
    } catch (const std::runtime_error& e) {
        std::printf("  捕获: %s\n", e.what());
    }

    std::printf("[5] 拷贝被删除（取消注释下行可见编译错误）：\n");
    std::printf("  // TextFile t2 = t1;  // error: call to deleted constructor\n");
    std::remove(kPath);
    return 0;
}
