// demo.cpp —— RAII 系统资源库演示 CLI（ph13 project）
// 演示 raii/ 库的三种典型用法：CFile 写文件、CFile 读文件、UniqueFd 分块复制。
// 所有资源（FILE* / fd）都由 RAII 对象持有，作用域结束或异常时自动释放。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra demo.cpp -o build/raii-demo（在 project/ 目录下，与 Makefile 产物路径一致）
// 运行：    build/raii-demo write <path> | read <path> | copy <src> <dst>
// 验证状态：已验证（两种编译器均零警告）
#include <cstdio>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

#include "raii/c_file.h"
#include "raii/unique_fd.h"

namespace {

// open() 的创建模式：0644 = owner rw / group r / other r
constexpr mode_t kFileMode = 0644;

void usage(FILE* out) {
    std::fprintf(out,
                 "用法: raii-demo <命令> [参数]\n"
                 "  write <path>       用 CFile 写入 3 行（构造即打开，析构自动 close）\n"
                 "  read  <path>       用 CFile 读取并打印全部内容\n"
                 "  copy  <src> <dst>  用 UniqueFd 分块复制文件（两端 fd 均 RAII 托管）\n");
}

void cmd_write(const char* path) {
    raii::CFile f(path, "w");          // RAII：fopen 成功才构造，失败抛异常
    for (int i = 1; i <= 3; ++i) {
        const std::string line = "line-" + std::to_string(i) + "\n";
        f.write(line.data(), line.size());
        std::printf("  written: line-%d\n", i);
    }
    std::printf("  write 完成（析构自动 fclose）\n");
}

void cmd_read(const char* path) {
    raii::CFile f(path, "r");
    char buf[256];
    std::string all;
    std::size_t n;
    while ((n = f.read(buf, sizeof buf)) > 0) all.append(buf, n);
    std::printf("  read %zu 字节:\n", all.size());
    std::fputs(all.c_str(), stdout);
    std::printf("  read 完成（析构自动 fclose）\n");
}

void cmd_copy(const char* src, const char* dst) {
    raii::UniqueFd in(::open(src, O_RDONLY));
    if (in.get() < 0) throw std::runtime_error(std::string("open 失败: ") + src);
    raii::UniqueFd out(::open(dst, O_WRONLY | O_CREAT | O_TRUNC, kFileMode));
    if (out.get() < 0) throw std::runtime_error(std::string("open 失败: ") + dst);

    char buf[4096];
    std::size_t total = 0;
    for (;;) {
        const std::size_t n = in.read_some(buf, sizeof buf);
        if (n == 0) break;
        out.write_all(buf, n);         // 写失败抛异常 → 两个 RAII 句柄自动 close
        total += n;
    }
    std::printf("  copy %zu 字节（src/dst 两端 fd 均由 RAII 自动关闭）\n", total);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        usage(stderr);
        return 1;
    }
    try {
        const std::string cmd = argv[1];
        if (cmd == "write" && argc == 3) {
            cmd_write(argv[2]);
            return 0;
        }
        if (cmd == "read" && argc == 3) {
            cmd_read(argv[2]);
            return 0;
        }
        if (cmd == "copy" && argc == 4) {
            cmd_copy(argv[2], argv[3]);
            return 0;
        }
        usage(stderr);
        return 1;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "错误: %s\n", e.what());
        return 1;
    }
}
