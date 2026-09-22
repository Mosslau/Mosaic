// ex03-raii-file.cpp —— RAII 资源封装（R.1）：FILE* 句柄类 + 异常路径不泄漏
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex03-raii-file.cpp -o /tmp/ph13-ex03
// 运行：/tmp/ph13-ex03（在 /tmp 下写临时文件，结束时删除）
#include <cstdio>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

// RAII 文件句柄：资源生命周期 = 对象生命周期（R.1）
// move-only：拷贝被删除（所有权唯一），移动 noexcept（E.16）
class File {
public:
    explicit File(const char* path, const char* mode)
        : fp_(std::fopen(path, mode)) {
        if (fp_ == nullptr) {
            throw std::runtime_error(std::string("无法打开: ") + path);
        }
        std::printf("  open  %s (%s)\n", path, mode);
    }
    ~File() {
        if (fp_ != nullptr) {
            std::fclose(fp_);
            std::printf("  close（析构自动调用）\n");
        }
    }
    File(const File&) = delete;             // 所有权唯一：禁止拷贝
    File& operator=(const File&) = delete;
    File(File&& o) noexcept : fp_(std::exchange(o.fp_, nullptr)) {
        std::printf("  move（句柄易主，源置空）\n");
    }
    File& operator=(File&& o) noexcept {
        if (this != &o) {
            if (fp_ != nullptr) std::fclose(fp_);
            fp_ = std::exchange(o.fp_, nullptr);
        }
        return *this;
    }

    void write_line(const char* s) {
        if (std::fprintf(fp_, "%s\n", s) < 0) throw std::runtime_error("写入失败");
    }
    std::string read_all() {
        std::string out;
        char buf[64];
        while (std::fgets(buf, sizeof buf, fp_) != nullptr) out += buf;
        return out;
    }

private:
    std::FILE* fp_;
};

const char* kPath = "/tmp/ph13-ex03-demo.txt";

// 场景：写文件写到一半抛异常 —— 观察栈展开时 RAII 是否兜底
void write_then_throw() {
    File f(kPath, "w");
    f.write_line("line-1");
    std::printf("  即将抛异常…\n");
    throw std::runtime_error("模拟处理失败");   // 中途失败
}

int main() {
    std::printf("[1] 正常路径：作用域结束自动 fclose\n");
    {
        File f(kPath, "w");
        f.write_line("hello-raii");
    }

    std::printf("[2] 异常路径：异常穿越作用域，析构照常执行（E.6）\n");
    try {
        write_then_throw();
    } catch (const std::runtime_error& e) {
        std::printf("  捕获: %s\n", e.what());
    }

    std::printf("[3] 所有权转移：句柄移动进容器，旧对象置空\n");
    {
        std::vector<File> pool;
        File f(kPath, "a");
        f.write_line("appended");
        pool.push_back(std::move(f));       // 句柄易主
        std::printf("  pool 大小=%zu\n", pool.size());
    }

    std::printf("[4] 读回验证内容确实落盘\n");
    {
        File f(kPath, "r");
        std::string content = f.read_all();
        std::printf("  文件内容: %s", content.c_str());
    }
    std::remove(kPath);
    std::printf("[5] 临时文件已删除\n");
    return 0;
}
